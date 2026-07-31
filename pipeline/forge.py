"""Run the public registry pipeline as a resumable local Forge workspace.

Forge v1 deliberately starts at an already reviewed CanonRegistry. It turns that
registry into two useful, validated artifacts: a read-only inspection report and
a playable micro content pack. Inputs stay immutable and every successful run is
published under a new path, so interrupted or forced reruns cannot overwrite the
last known-good result.

CLI::

    python -m pipeline.forge init WORKSPACE --template examples/forge_workbench
    python -m pipeline.forge status WORKSPACE
    python -m pipeline.forge run WORKSPACE
    python -m pipeline.forge rerun WORKSPACE --stage adaptation
    python -m pipeline.forge check WORKSPACE
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Literal, TypeAlias

from lore2mud.content.loader import ContentValidationError, load_content_pack
from pipeline.canon_registry import (
    CanonRegistryValidationError,
    validate_canon_registry_document,
)
from pipeline.registry_adaptation import (
    RegistryAdaptationValidationError,
    RegistryCompilationError,
    compile_registry_micro_pack,
    registry_pack_to_documents,
    validate_registry_adaptation_manifest_document,
    validate_registry_adaptation_plan,
    write_registry_micro_pack,
)
from pipeline.registry_inspection import (
    RegistryInspectionBuildError,
    RegistryInspectionValidationError,
    compile_registry_inspection,
    registry_inspection_report_to_document,
    validate_registry_inspection_report_document,
    validate_registry_inspection_plan,
    write_registry_inspection_report,
)


WORKSPACE_FILENAME = "forge-workspace.json"
STATE_RELATIVE_PATH = PurePosixPath(".forge/state.json")
LOCK_RELATIVE_PATH = PurePosixPath(".forge/run.lock")

StageName: TypeAlias = Literal["inspection", "adaptation"]
StageStatus: TypeAlias = Literal["READY", "CURRENT", "STALE", "FAILED", "BLOCKED"]

_STAGES: tuple[StageName, ...] = ("inspection", "adaptation")
_STABLE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_WINDOWS_FORBIDDEN_CHARS = frozenset('<>:"|?*')
_WINDOWS_RESERVED_NAMES = frozenset(
    {"con", "prn", "aux", "nul"}
    | {f"com{index}" for index in range(1, 10)}
    | {f"lpt{index}" for index in range(1, 10)}
)
_ADAPTATION_FILES = frozenset(
    {
        "pack.json",
        "rooms.json",
        "items.json",
        "characters.json",
        "quests.json",
        "dialogues.json",
        "monsters.json",
        "shops.json",
        "registry_adaptation_manifest.json",
    }
)


class ForgeValidationError(ValueError):
    """Raised when a workspace, state file, or path is invalid."""

    def __init__(self, issues: Sequence[str]) -> None:
        self.issues = tuple(issues)
        super().__init__("\n".join(f"- {issue}" for issue in self.issues))


class ForgeExecutionError(RuntimeError):
    """Raised when a safe workspace operation cannot be completed."""


@dataclass(frozen=True, slots=True)
class ForgeWorkspace:
    format_version: int
    workspace_id: str
    source_registry: PurePosixPath
    inspection_plan: PurePosixPath
    adaptation_plan: PurePosixPath
    artifact_root: PurePosixPath


@dataclass(frozen=True, slots=True)
class LoadedWorkspace:
    root: Path
    config: ForgeWorkspace


@dataclass(frozen=True, slots=True)
class StageInputSnapshot:
    stage: StageName
    records: tuple[dict[str, object], ...]
    payloads: tuple[bytes | None, ...]
    fingerprint: str


def _unknown_keys(
    value: dict[str, Any], allowed: frozenset[str], loc: str, issues: list[str]
) -> None:
    for key in sorted(set(value) - allowed):
        issues.append(f"{loc} contains unknown field: {key}")


def _required_text(
    value: dict[str, Any], key: str, loc: str, issues: list[str]
) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result.strip():
        issues.append(f"{loc}.{key} must be a non-blank string")
        return ""
    return result


def _workspace_path(raw: str, loc: str, issues: list[str]) -> PurePosixPath:
    if "\\" in raw:
        issues.append(f"{loc} must use forward slashes")
        return PurePosixPath("invalid")
    components = raw.split("/")
    if not raw or any(part in {"", ".", ".."} for part in components):
        issues.append(f"{loc} must be a normalized relative workspace path")
        return PurePosixPath("invalid")
    if any(ord(character) < 32 or ord(character) == 127 for character in raw):
        issues.append(f"{loc} must not contain control characters")
        return PurePosixPath("invalid")
    if any(character in _WINDOWS_FORBIDDEN_CHARS for character in raw):
        issues.append(f"{loc} contains a character forbidden in Windows paths")
        return PurePosixPath("invalid")
    for component in components:
        if component.endswith((".", " ")):
            issues.append(f"{loc} components must not end with a dot or space")
            return PurePosixPath("invalid")
        device_name = component.split(".", 1)[0].casefold()
        if device_name in _WINDOWS_RESERVED_NAMES:
            issues.append(f"{loc} contains a reserved Windows device name")
            return PurePosixPath("invalid")
    result = PurePosixPath(raw)
    if result.is_absolute():
        issues.append(f"{loc} must be relative to the workspace")
        return PurePosixPath("invalid")
    return result


def _path_key(path: PurePosixPath) -> tuple[str, ...]:
    """Return a component key using the host filesystem's case semantics."""

    return tuple(os.path.normcase(component) for component in path.parts)


def _path_is_same_or_below(path: PurePosixPath, parent: PurePosixPath) -> bool:
    path_key = _path_key(path)
    parent_key = _path_key(parent)
    return len(path_key) >= len(parent_key) and path_key[: len(parent_key)] == parent_key


def validate_forge_workspace(data: object) -> ForgeWorkspace:
    """Strictly validate and canonicalize a Forge workspace manifest."""

    if not isinstance(data, dict):
        raise ForgeValidationError(("workspace manifest root must be an object",))
    issues: list[str] = []
    allowed = frozenset(
        {
            "format_version",
            "workspace_id",
            "source_registry",
            "inspection_plan",
            "adaptation_plan",
            "artifact_root",
        }
    )
    _unknown_keys(data, allowed, "workspace", issues)
    format_version = data.get("format_version")
    if isinstance(format_version, bool) or format_version != 1:
        issues.append("workspace.format_version must be integer 1")
    workspace_id = _required_text(data, "workspace_id", "workspace", issues)
    if workspace_id and not _STABLE_ID_RE.fullmatch(workspace_id):
        issues.append("workspace.workspace_id must be a stable ID")

    paths: dict[str, PurePosixPath] = {}
    for key in (
        "source_registry",
        "inspection_plan",
        "adaptation_plan",
        "artifact_root",
    ):
        raw = _required_text(data, key, "workspace", issues)
        paths[key] = _workspace_path(raw, f"workspace.{key}", issues)

    input_paths = (
        paths["source_registry"],
        paths["inspection_plan"],
        paths["adaptation_plan"],
    )
    if len({_path_key(path) for path in input_paths}) != 3:
        issues.append("workspace input paths must be distinct")
    artifact_root = paths["artifact_root"]
    if os.path.normcase(artifact_root.parts[0]) == os.path.normcase(".forge"):
        issues.append("workspace.artifact_root must not be inside .forge")
    for input_path in input_paths:
        if _path_is_same_or_below(input_path, artifact_root):
            issues.append(
                f"workspace input must not be inside artifact_root: {input_path.as_posix()}"
            )
    if issues:
        raise ForgeValidationError(issues)
    return ForgeWorkspace(
        format_version=1,
        workspace_id=workspace_id,
        source_registry=paths["source_registry"],
        inspection_plan=paths["inspection_plan"],
        adaptation_plan=paths["adaptation_plan"],
        artifact_root=artifact_root,
    )


def forge_workspace_to_document(workspace: ForgeWorkspace) -> dict[str, object]:
    if not isinstance(workspace, ForgeWorkspace):
        raise TypeError("workspace must be ForgeWorkspace")
    return {
        "format_version": workspace.format_version,
        "workspace_id": workspace.workspace_id,
        "source_registry": workspace.source_registry.as_posix(),
        "inspection_plan": workspace.inspection_plan.as_posix(),
        "adaptation_plan": workspace.adaptation_plan.as_posix(),
        "artifact_root": workspace.artifact_root.as_posix(),
    }


def _read_json(path: Path) -> object:
    with open(path, "r", encoding="utf-8") as stream:
        return json.load(stream)


def _stat_is_reparse(stat_result: os.stat_result | Any) -> bool:
    return bool(getattr(stat_result, "st_file_attributes", 0) & _REPARSE_POINT)


def _is_link_or_junction(path: Path) -> bool:
    """Reject symlinks and Windows reparse points, including junctions."""

    try:
        if os.path.islink(path):
            return True
        return _stat_is_reparse(os.lstat(path))
    except OSError:
        return False


def _existing_symlink(root: Path, relative: PurePosixPath) -> Path | None:
    current = root
    for part in relative.parts:
        current /= part
        if _is_link_or_junction(current):
            return current
        if not os.path.lexists(current):
            break
    return None


def _resolve_member(root: Path, relative: PurePosixPath) -> Path:
    symlink = _existing_symlink(root, relative)
    if symlink is not None:
        raise ForgeValidationError(
            (f"workspace path traverses a symbolic link: {relative.as_posix()}",)
        )
    candidate = root.joinpath(*relative.parts)
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ForgeValidationError(
            (f"workspace path escapes the root: {relative.as_posix()}",)
        ) from exc
    return candidate


def _same_file(first: Path, second: Path) -> bool:
    try:
        return first.exists() and second.exists() and os.path.samefile(first, second)
    except OSError:
        return False


def load_forge_workspace(workspace_root: str | os.PathLike[str]) -> LoadedWorkspace:
    """Load a workspace without creating or changing any files."""

    supplied_root = Path(workspace_root)
    if _is_link_or_junction(supplied_root):
        raise ForgeValidationError(("workspace root must not be a symbolic link or junction",))
    root = supplied_root.resolve(strict=True)
    if not root.is_dir():
        raise ForgeValidationError((f"workspace root is not a directory: {root}",))
    manifest_path = root / WORKSPACE_FILENAME
    if _is_link_or_junction(manifest_path):
        raise ForgeValidationError(("workspace manifest must not be a symbolic link or junction",))
    if not manifest_path.is_file():
        raise ForgeValidationError((f"missing {WORKSPACE_FILENAME}",))
    workspace = validate_forge_workspace(_read_json(manifest_path))

    input_members = (
        workspace.source_registry,
        workspace.inspection_plan,
        workspace.adaptation_plan,
    )
    input_paths = [_resolve_member(root, member) for member in input_members]
    _resolve_member(root, workspace.artifact_root)
    for index, first in enumerate(input_paths):
        for second in input_paths[index + 1 :]:
            if _same_file(first, second):
                raise ForgeValidationError(
                    (
                        "workspace inputs point to the same file: "
                        f"{first.relative_to(root).as_posix()} and "
                        f"{second.relative_to(root).as_posix()}",
                    )
                )
    return LoadedWorkspace(root=root, config=workspace)


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _iter_safe_tree(
    root: Path, *, context: str
) -> Iterator[tuple[Path, PurePosixPath, os.stat_result | Any]]:
    """Walk without descending into a link or reparse point."""

    def walk(directory: Path, prefix: PurePosixPath) -> Iterator[
        tuple[Path, PurePosixPath, os.stat_result | Any]
    ]:
        entries: list[tuple[str, Path, os.stat_result | Any]] = []
        with os.scandir(directory) as scanner:
            for entry in scanner:
                entries.append(
                    (entry.name, Path(entry.path), entry.stat(follow_symlinks=False))
                )
        for name, source, stat_result in sorted(entries, key=lambda item: item[0]):
            relative = prefix / name if prefix.parts else PurePosixPath(name)
            if stat.S_ISLNK(stat_result.st_mode) or _stat_is_reparse(stat_result):
                raise ForgeValidationError(
                    (
                        f"{context} contains a symbolic link or junction: "
                        f"{relative.as_posix()}",
                    )
                )
            yield source, relative, stat_result
            if stat.S_ISDIR(stat_result.st_mode):
                yield from walk(source, relative)

    yield from walk(root, PurePosixPath())


def _sha256_directory(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    total_size = 0
    for candidate, relative_path, stat_result in _iter_safe_tree(
        path, context="artifact directory"
    ):
        relative = relative_path.as_posix().encode("utf-8")
        digest.update(b"D" if stat.S_ISDIR(stat_result.st_mode) else b"F")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        if stat.S_ISREG(stat_result.st_mode):
            file_digest, size = _sha256_file(candidate)
            digest.update(bytes.fromhex(file_digest))
            digest.update(size.to_bytes(8, "big"))
            total_size += size
        elif not stat.S_ISDIR(stat_result.st_mode):
            raise ForgeValidationError(
                (f"unsupported artifact entry: {relative_path.as_posix()}",)
            )
    return digest.hexdigest(), total_size


def _artifact_record(
    loaded: LoadedWorkspace, relative: PurePosixPath
) -> dict[str, object]:
    path = _resolve_member(loaded.root, relative)
    base: dict[str, object] = {"path": relative.as_posix()}
    if not os.path.lexists(path):
        return {**base, "state": "missing"}
    if path.is_file():
        digest, size = _sha256_file(path)
        return {
            **base,
            "state": "present",
            "kind": "file",
            "sha256": digest,
            "size": size,
        }
    if path.is_dir():
        digest, size = _sha256_directory(path)
        return {
            **base,
            "state": "present",
            "kind": "directory",
            "sha256": digest,
            "size": size,
        }
    return {**base, "state": "unsafe", "reason": "not a regular file or directory"}


def _stage_inputs(workspace: ForgeWorkspace, stage: StageName) -> tuple[PurePosixPath, ...]:
    if stage == "inspection":
        return workspace.source_registry, workspace.inspection_plan
    return workspace.source_registry, workspace.adaptation_plan


def _fingerprint(stage: StageName, records: Sequence[dict[str, object]]) -> str:
    payload = json.dumps(
        {"stage": stage, "inputs": records},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _capture_stage_inputs(
    loaded: LoadedWorkspace, stage: StageName
) -> StageInputSnapshot:
    records: list[dict[str, object]] = []
    payloads: list[bytes | None] = []
    for relative in _stage_inputs(loaded.config, stage):
        path = _resolve_member(loaded.root, relative)
        base: dict[str, object] = {"path": relative.as_posix()}
        try:
            stream = open(path, "rb")
        except FileNotFoundError:
            records.append({**base, "state": "missing"})
            payloads.append(None)
            continue
        with stream:
            stat_result = os.fstat(stream.fileno())
            if not stat.S_ISREG(stat_result.st_mode) or _stat_is_reparse(stat_result):
                records.append(
                    {
                        **base,
                        "state": "unsafe",
                        "reason": "not a regular file",
                    }
                )
                payloads.append(None)
                continue
            payload = stream.read()
        records.append(
            {
                **base,
                "state": "present",
                "kind": "file",
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size": len(payload),
            }
        )
        payloads.append(payload)
    return StageInputSnapshot(
        stage=stage,
        records=tuple(records),
        payloads=tuple(payloads),
        fingerprint=_fingerprint(stage, records),
    )


def _json_from_snapshot(payload: bytes | None, relative: PurePosixPath) -> object:
    if payload is None:
        raise FileNotFoundError(f"missing or unsafe input: {relative.as_posix()}")
    return json.loads(payload.decode("utf-8"))


def _compile_stage_snapshot(
    loaded: LoadedWorkspace, snapshot: StageInputSnapshot
) -> tuple[Any, Any]:
    input_paths = _stage_inputs(loaded.config, snapshot.stage)
    registry = validate_canon_registry_document(
        _json_from_snapshot(snapshot.payloads[0], input_paths[0])
    )
    if snapshot.stage == "inspection":
        plan = validate_registry_inspection_plan(
            _json_from_snapshot(snapshot.payloads[1], input_paths[1])
        )
        return registry, compile_registry_inspection(registry, plan)
    plan = validate_registry_adaptation_plan(
        _json_from_snapshot(snapshot.payloads[1], input_paths[1])
    )
    return registry, compile_registry_micro_pack(registry, plan)


def _validate_artifact_record(
    data: object,
    loc: str,
    issues: list[str],
    expected_root: PurePosixPath | None = None,
    workspace_root: Path | None = None,
) -> None:
    if not isinstance(data, dict):
        issues.append(f"{loc} must be an object")
        return
    _unknown_keys(
        data, frozenset({"path", "kind", "sha256", "size"}), loc, issues
    )
    path = _required_text(data, "path", loc, issues)
    parsed_path: PurePosixPath | None = None
    if path:
        issue_count = len(issues)
        parsed_path = _workspace_path(path, f"{loc}.path", issues)
        if len(issues) == issue_count and expected_root is not None:
            if not _path_is_same_or_below(parsed_path, expected_root) or (
                _path_key(parsed_path) == _path_key(expected_root)
            ):
                issues.append(f"{loc}.path must be under {expected_root.as_posix()}")
            elif workspace_root is not None:
                try:
                    resolved_root = _resolve_member(
                        workspace_root, expected_root
                    ).resolve(strict=False)
                    resolved_candidate = _resolve_member(
                        workspace_root, parsed_path
                    ).resolve(strict=False)
                    relative_candidate = resolved_candidate.relative_to(resolved_root)
                    if not relative_candidate.parts:
                        raise ValueError("artifact path equals its stage root")
                except (ForgeValidationError, OSError, RuntimeError, ValueError):
                    issues.append(
                        f"{loc}.path must resolve under {expected_root.as_posix()}"
                    )
    if data.get("kind") not in {"file", "directory"}:
        issues.append(f"{loc}.kind must be file or directory")
    digest = data.get("sha256")
    if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
        issues.append(f"{loc}.sha256 must be lowercase SHA-256")
    size = data.get("size")
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        issues.append(f"{loc}.size must be an integer >= 0")


def _validate_run_record(
    data: object,
    loc: str,
    issues: list[str],
    expected_root: PurePosixPath | None = None,
    workspace_root: Path | None = None,
) -> None:
    if not isinstance(data, dict):
        issues.append(f"{loc} must be an object")
        return
    _unknown_keys(
        data,
        frozenset({"status", "input_fingerprint", "outputs", "error"}),
        loc,
        issues,
    )
    status = data.get("status")
    if status not in {"succeeded", "failed"}:
        issues.append(f"{loc}.status must be succeeded or failed")
    fingerprint = data.get("input_fingerprint")
    if not isinstance(fingerprint, str) or not _SHA256_RE.fullmatch(fingerprint):
        issues.append(f"{loc}.input_fingerprint must be lowercase SHA-256")
    outputs = data.get("outputs")
    if not isinstance(outputs, list):
        issues.append(f"{loc}.outputs must be an array")
    else:
        for index, output in enumerate(outputs):
            _validate_artifact_record(
                output,
                f"{loc}.outputs[{index}]",
                issues,
                expected_root,
                workspace_root,
            )
    error = data.get("error")
    if status == "succeeded" and error is not None:
        issues.append(f"{loc}.error must be null after success")
    if status == "succeeded" and isinstance(outputs, list) and len(outputs) != 1:
        issues.append(f"{loc}.outputs must contain exactly one artifact after success")
    if status == "failed" and (not isinstance(error, str) or not error.strip()):
        issues.append(f"{loc}.error must explain a failure")
    if status == "failed" and isinstance(outputs, list) and outputs:
        issues.append(f"{loc}.outputs must be empty after failure")


def validate_forge_state(
    data: object,
    workspace_id: str,
    artifact_root: PurePosixPath | None = None,
    workspace_root: Path | None = None,
) -> dict[str, object]:
    """Validate the internal v1 state document before trusting or writing it."""

    if not isinstance(data, dict):
        raise ForgeValidationError(("Forge state root must be an object",))
    issues: list[str] = []
    _unknown_keys(
        data, frozenset({"format_version", "workspace_id", "stages"}), "state", issues
    )
    version = data.get("format_version")
    if isinstance(version, bool) or version != 1:
        issues.append("state.format_version must be integer 1")
    if data.get("workspace_id") != workspace_id:
        issues.append("state.workspace_id must match the workspace manifest")
    stages = data.get("stages")
    if not isinstance(stages, dict):
        issues.append("state.stages must be an object")
    else:
        _unknown_keys(stages, frozenset(_STAGES), "state.stages", issues)
        for stage, record in stages.items():
            loc = f"state.stages.{stage}"
            if not isinstance(record, dict):
                issues.append(f"{loc} must be an object")
                continue
            _unknown_keys(
                record,
                frozenset({"attempts", "last_run", "last_success"}),
                loc,
                issues,
            )
            attempts = record.get("attempts")
            if isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 1:
                issues.append(f"{loc}.attempts must be an integer >= 1")
            last_run = record.get("last_run")
            stage_root = None
            if artifact_root is not None and stage in _STAGES:
                run_name = "inspection_runs" if stage == "inspection" else "adaptation_runs"
                stage_root = artifact_root / run_name
            _validate_run_record(
                last_run,
                f"{loc}.last_run",
                issues,
                stage_root,
                workspace_root,
            )
            last_success = record.get("last_success")
            if last_success is not None:
                _validate_run_record(
                    last_success,
                    f"{loc}.last_success",
                    issues,
                    stage_root,
                    workspace_root,
                )
                if isinstance(last_success, dict) and last_success.get("status") != "succeeded":
                    issues.append(f"{loc}.last_success.status must be succeeded")
    if issues:
        raise ForgeValidationError(issues)
    return data


def _empty_state(workspace_id: str) -> dict[str, object]:
    return {"format_version": 1, "workspace_id": workspace_id, "stages": {}}


def _load_state(loaded: LoadedWorkspace) -> dict[str, object]:
    state_path = _resolve_member(loaded.root, STATE_RELATIVE_PATH)
    if not os.path.lexists(state_path):
        return _empty_state(loaded.config.workspace_id)
    if not state_path.is_file():
        raise ForgeValidationError((".forge/state.json must be a regular file",))
    return validate_forge_state(
        _read_json(state_path),
        loaded.config.workspace_id,
        loaded.config.artifact_root,
        loaded.root,
    )


def _json_bytes(data: object) -> bytes:
    return (
        json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _write_state(loaded: LoadedWorkspace, state: dict[str, object]) -> None:
    validate_forge_state(
        state,
        loaded.config.workspace_id,
        loaded.config.artifact_root,
        loaded.root,
    )
    forge_dir = _resolve_member(loaded.root, PurePosixPath(".forge"))
    if os.path.lexists(forge_dir) and not forge_dir.is_dir():
        raise ForgeValidationError((".forge must be a directory",))
    forge_dir.mkdir(exist_ok=True)
    state_path = forge_dir / "state.json"
    payload = _json_bytes(state)
    descriptor: int | None = None
    temporary: str | None = None
    try:
        descriptor, temporary = tempfile.mkstemp(
            dir=forge_dir, prefix=".state.", suffix=".tmp"
        )
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, state_path)
        temporary = None
    except BaseException:
        if descriptor is not None:
            os.close(descriptor)
        if temporary is not None:
            try:
                os.remove(temporary)
            except OSError:
                pass
        raise


def _open_windows_lock_descriptor(path: Path) -> int:
    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    create_file.restype = wintypes.HANDLE
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL
    handle = create_file(
        str(path),
        0x80000000 | 0x40000000,  # GENERIC_READ | GENERIC_WRITE
        0x00000001 | 0x00000002 | 0x00000004,  # share read/write/delete
        None,
        4,  # OPEN_ALWAYS
        0x00000080 | 0x00200000,  # NORMAL | OPEN_REPARSE_POINT
        None,
    )
    invalid_handle = ctypes.c_void_p(-1).value
    if handle == invalid_handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return msvcrt.open_osfhandle(
            int(handle), os.O_RDWR | getattr(os, "O_BINARY", 0)
        )
    except BaseException:
        close_handle(handle)
        raise


def _open_lock_stream(path: Path) -> BinaryIO:
    if _is_link_or_junction(path):
        raise ForgeValidationError((".forge/run.lock must not be a link or junction",))
    if os.name == "nt":
        descriptor = _open_windows_lock_descriptor(path)
    else:
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags, 0o600)
    try:
        stat_result = os.fstat(descriptor)
        if not stat.S_ISREG(stat_result.st_mode) or _stat_is_reparse(stat_result):
            raise ForgeValidationError((".forge/run.lock must be a regular file",))
        if stat_result.st_nlink != 1:
            raise ForgeValidationError((".forge/run.lock must not be a hard link",))
        return os.fdopen(descriptor, "r+b", buffering=0)
    except BaseException:
        os.close(descriptor)
        raise


class _WorkspaceLock:
    def __init__(self, loaded: LoadedWorkspace) -> None:
        self._loaded = loaded
        self._stream: Any = None

    def __enter__(self) -> "_WorkspaceLock":
        forge_dir = _resolve_member(self._loaded.root, PurePosixPath(".forge"))
        if os.path.lexists(forge_dir) and not forge_dir.is_dir():
            raise ForgeValidationError((".forge must be a directory",))
        forge_dir.mkdir(exist_ok=True)
        lock_path = _resolve_member(self._loaded.root, LOCK_RELATIVE_PATH)
        self._stream = _open_lock_stream(lock_path)
        try:
            self._stream.seek(0, os.SEEK_END)
            if self._stream.tell() == 0:
                self._stream.write(b"0")
                self._stream.flush()
            self._stream.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self._stream.close()
            self._stream = None
            raise ForgeExecutionError("workspace is already running") from exc
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self._stream is None:
            return
        try:
            self._stream.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._stream.fileno(), fcntl.LOCK_UN)
        finally:
            self._stream.close()
            self._stream = None


def _load_stage_inputs(loaded: LoadedWorkspace, stage: StageName) -> tuple[Any, Any]:
    return _compile_stage_snapshot(loaded, _capture_stage_inputs(loaded, stage))


def _output_matches_expected(
    loaded: LoadedWorkspace,
    stage: StageName,
    relative: PurePosixPath,
    compiled: Any,
) -> bool:
    path = _resolve_member(loaded.root, relative)
    for input_relative in (
        loaded.config.source_registry,
        loaded.config.inspection_plan,
        loaded.config.adaptation_plan,
    ):
        if _same_file(path, _resolve_member(loaded.root, input_relative)):
            return False
    if stage == "inspection":
        if not path.is_file():
            return False
        payload = path.read_bytes()
        report = validate_registry_inspection_report_document(
            json.loads(payload.decode("utf-8"))
        )
        expected_payload = _json_bytes(
            registry_inspection_report_to_document(compiled)
        )
        return payload == expected_payload and report == compiled

    if not path.is_dir():
        return False
    actual_files: dict[str, bytes] = {}
    for candidate, candidate_relative, stat_result in _iter_safe_tree(
        path, context="adaptation artifact"
    ):
        if not stat.S_ISREG(stat_result.st_mode) or len(candidate_relative.parts) != 1:
            return False
        actual_files[candidate_relative.name] = candidate.read_bytes()
    if set(actual_files) != _ADAPTATION_FILES:
        return False
    expected_files = dict(registry_pack_to_documents(compiled))
    if actual_files != expected_files:
        return False
    load_content_pack(path)
    validate_registry_adaptation_manifest_document(
        json.loads(actual_files["registry_adaptation_manifest.json"].decode("utf-8"))
    )
    return True


def _record_matches(
    loaded: LoadedWorkspace,
    expected: object,
    stage: StageName,
    compiled: Any,
) -> bool:
    if not isinstance(expected, dict):
        return False
    path = expected.get("path")
    if not isinstance(path, str):
        return False
    try:
        relative = PurePosixPath(path)
        actual = _artifact_record(loaded, relative)
        if actual != {**expected, "state": "present"}:
            return False
        return _output_matches_expected(loaded, stage, relative, compiled)
    except (
        ContentValidationError,
        ForgeValidationError,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        RegistryAdaptationValidationError,
        RegistryInspectionValidationError,
    ):
        return False


def _stage_snapshot(
    loaded: LoadedWorkspace,
    state: dict[str, object],
    stage: StageName,
    input_snapshot: StageInputSnapshot | None = None,
) -> dict[str, object]:
    captured = input_snapshot or _capture_stage_inputs(loaded, stage)
    if captured.stage != stage:
        raise ForgeValidationError(("input snapshot stage does not match",))
    input_records = [dict(record) for record in captured.records]
    fingerprint = captured.fingerprint
    stage_state = state["stages"].get(stage)  # type: ignore[index,union-attr]
    last_run = stage_state.get("last_run") if isinstance(stage_state, dict) else None
    last_success = (
        stage_state.get("last_success") if isinstance(stage_state, dict) else None
    )
    attempts = stage_state.get("attempts", 0) if isinstance(stage_state, dict) else 0
    outputs = last_success.get("outputs", []) if isinstance(last_success, dict) else []

    missing = [
        record["path"] for record in input_records if record.get("state") != "present"
    ]
    if (
        isinstance(last_run, dict)
        and last_run.get("status") == "failed"
        and last_run.get("input_fingerprint") == fingerprint
    ):
        status: StageStatus = "FAILED"
        reason = str(last_run.get("error"))
    elif missing:
        status = "BLOCKED"
        reason = f"missing or unsafe inputs: {', '.join(str(item) for item in missing)}"
    else:
        try:
            _, compiled = _compile_stage_snapshot(loaded, captured)
            semantic_error: str | None = None
        except Exception as exc:
            compiled = None
            semantic_error = f"{type(exc).__name__}: {exc}"
        if semantic_error is not None:
            status = "BLOCKED"
            reason = semantic_error
        elif isinstance(last_success, dict):
            same_input = last_success.get("input_fingerprint") == fingerprint
            outputs_current = bool(outputs) and compiled is not None and all(
                _record_matches(loaded, output, stage, compiled) for output in outputs
            )
            if same_input and outputs_current:
                status = "CURRENT"
                reason = None
            else:
                status = "STALE"
                reason = (
                    "inputs changed since the last successful run"
                    if not same_input
                    else "a successful output is missing, changed, or invalid"
                )
        else:
            status = "READY"
            reason = None

    result: dict[str, object] = {
        "stage": stage,
        "status": status,
        "attempts": attempts,
        "input_fingerprint": fingerprint,
        "inputs": input_records,
        "outputs": outputs,
    }
    if reason is not None:
        result["reason"] = reason
    return result


def inspect_forge_workspace(
    workspace_root: str | os.PathLike[str],
) -> dict[str, object]:
    """Return a read-only status report with inputs, outputs, and failure reasons."""

    loaded = load_forge_workspace(workspace_root)
    state = _load_state(loaded)
    stages = [_stage_snapshot(loaded, state, stage) for stage in _STAGES]
    statuses = {str(stage["status"]) for stage in stages}
    if statuses == {"CURRENT"}:
        overall = "CURRENT"
    elif "FAILED" in statuses or "BLOCKED" in statuses:
        overall = "ATTENTION"
    elif "STALE" in statuses:
        overall = "STALE"
    else:
        overall = "READY"
    return {
        "format_version": 1,
        "workspace_id": loaded.config.workspace_id,
        "overall_status": overall,
        "stages": stages,
    }


def _next_output_path(
    loaded: LoadedWorkspace, stage: StageName, fingerprint: str
) -> PurePosixPath:
    if stage == "inspection":
        runs = loaded.config.artifact_root / "inspection_runs"
        stem = "inspection"
        suffix = ".json"
    else:
        runs = loaded.config.artifact_root / "adaptation_runs"
        stem = "content-pack"
        suffix = ""
    runs_path = _resolve_member(loaded.root, runs)
    if os.path.lexists(runs_path) and not runs_path.is_dir():
        raise ForgeValidationError((f"artifact run root is not a directory: {runs}",))
    runs_path.mkdir(parents=True, exist_ok=True)
    for index in range(1, 1_000_000):
        name = f"{stem}-{index:06d}-{fingerprint[:12]}{suffix}"
        relative = runs / name
        if not os.path.lexists(_resolve_member(loaded.root, relative)):
            return relative
    raise ForgeExecutionError(f"no free output name for stage {stage}")


def _remove_output_artifact(
    loaded: LoadedWorkspace, output: dict[str, object]
) -> None:
    raw_path = output.get("path")
    if not isinstance(raw_path, str):
        raise ForgeExecutionError("cannot roll back an output without a path")
    path = _resolve_member(loaded.root, PurePosixPath(raw_path))
    if _is_link_or_junction(path):
        raise ForgeExecutionError(f"refusing to remove linked output: {raw_path}")
    if path.is_dir():
        shutil.rmtree(path)
    elif path.is_file():
        path.unlink()
    elif os.path.lexists(path):
        raise ForgeExecutionError(f"cannot remove unsupported output: {raw_path}")
    else:
        raise ForgeExecutionError(f"published output disappeared: {raw_path}")
    if os.path.lexists(path):
        raise ForgeExecutionError(f"failed to remove published output: {raw_path}")


def _execute_stage(
    loaded: LoadedWorkspace, input_snapshot: StageInputSnapshot
) -> dict[str, object]:
    stage = input_snapshot.stage
    fingerprint = input_snapshot.fingerprint
    _, compiled = _compile_stage_snapshot(loaded, input_snapshot)
    output_relative = _next_output_path(loaded, stage, fingerprint)
    output_path = _resolve_member(loaded.root, output_relative)
    if stage == "inspection":
        write_registry_inspection_report(compiled, output_path)
    else:
        write_registry_micro_pack(compiled, output_path)
    rollback_record: dict[str, object] = {"path": output_relative.as_posix()}
    try:
        record = _artifact_record(loaded, output_relative)
        if record.get("state") != "present":
            raise ForgeExecutionError(f"stage {stage} did not publish its output")
        output = {key: value for key, value in record.items() if key != "state"}
        post_snapshot = _capture_stage_inputs(loaded, stage)
        if post_snapshot.fingerprint != fingerprint:
            raise ForgeExecutionError(f"stage {stage} inputs changed during execution")
        return output
    except BaseException as execution_error:
        if os.path.lexists(output_path):
            try:
                _remove_output_artifact(loaded, rollback_record)
            except Exception as cleanup_error:
                raise ForgeExecutionError(
                    f"stage validation failed and output rollback failed: {cleanup_error}"
                ) from execution_error
        raise


def run_forge_workspace(
    workspace_root: str | os.PathLike[str],
    *,
    stages: Sequence[StageName] = _STAGES,
    force: bool = False,
) -> tuple[dict[str, object], bool]:
    """Run selected stages, safely resuming current work unless force is true."""

    if isinstance(stages, (str, bytes)) or not stages:
        raise ForgeValidationError(("stages must be a non-empty stage sequence",))
    selected: list[StageName] = []
    for stage in stages:
        if stage not in _STAGES:
            raise ForgeValidationError((f"unknown Forge stage: {stage}",))
        if stage not in selected:
            selected.append(stage)

    loaded = load_forge_workspace(workspace_root)
    actions: list[dict[str, object]] = []
    succeeded = True
    with _WorkspaceLock(loaded):
        state = _load_state(loaded)
        for stage in selected:
            input_snapshot = _capture_stage_inputs(loaded, stage)
            snapshot = _stage_snapshot(loaded, state, stage, input_snapshot)
            fingerprint = input_snapshot.fingerprint
            if snapshot["status"] == "CURRENT" and not force:
                actions.append({"stage": stage, "action": "skipped", "status": "CURRENT"})
                continue

            state_stages = state["stages"]
            assert isinstance(state_stages, dict)
            previous = state_stages.get(stage)
            attempts = (
                int(previous.get("attempts", 0)) + 1
                if isinstance(previous, dict)
                else 1
            )
            last_success = (
                previous.get("last_success") if isinstance(previous, dict) else None
            )
            try:
                output = _execute_stage(loaded, input_snapshot)
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                run_record = {
                    "status": "failed",
                    "input_fingerprint": fingerprint,
                    "outputs": [],
                    "error": error,
                }
                stage_record = {
                    "attempts": attempts,
                    "last_run": run_record,
                    "last_success": last_success,
                }
                actions.append(
                    {"stage": stage, "action": "failed", "status": "FAILED", "error": error}
                )
                succeeded = False
                state_stages[stage] = stage_record
                _write_state(loaded, state)
                continue

            run_record = {
                "status": "succeeded",
                "input_fingerprint": fingerprint,
                "outputs": [output],
                "error": None,
            }
            stage_record = {
                "attempts": attempts,
                "last_run": run_record,
                "last_success": run_record,
            }
            state_stages[stage] = stage_record
            try:
                _write_state(loaded, state)
            except BaseException as state_error:
                if previous is None:
                    state_stages.pop(stage, None)
                else:
                    state_stages[stage] = previous
                try:
                    _remove_output_artifact(loaded, output)
                except Exception as cleanup_error:
                    raise ForgeExecutionError(
                        f"state publication failed and output rollback failed: {cleanup_error}"
                    ) from state_error
                raise
            actions.append(
                {
                    "stage": stage,
                    "action": "reran" if force else "ran",
                    "status": "CURRENT",
                    "outputs": [output],
                }
            )

    report = inspect_forge_workspace(workspace_root)
    report["actions"] = actions
    return report, succeeded


def _iter_template_entries(template: Path) -> Iterator[tuple[Path, Path]]:
    for source, relative, stat_result in _iter_safe_tree(
        template, context="template"
    ):
        if not stat.S_ISDIR(stat_result.st_mode) and not stat.S_ISREG(
            stat_result.st_mode
        ):
            raise ForgeValidationError(
                (f"template contains an unsupported entry: {relative.as_posix()}",)
            )
        yield source, Path(*relative.parts)


def initialize_forge_workspace(
    workspace_root: str | os.PathLike[str],
    template_root: str | os.PathLike[str],
) -> Path:
    """Atomically create a workspace from a public, symlink-free template."""

    target = Path(workspace_root)
    if os.path.lexists(target):
        raise ForgeExecutionError(f"workspace already exists: {target}")
    parent = target.resolve(strict=False).parent
    if not parent.is_dir():
        raise ForgeExecutionError(f"workspace parent does not exist: {parent}")
    template_supplied = Path(template_root)
    if _is_link_or_junction(template_supplied):
        raise ForgeValidationError(("template root must not be a symbolic link or junction",))
    template = template_supplied.resolve(strict=True)
    if not template.is_dir():
        raise ForgeValidationError((f"template is not a directory: {template}",))
    try:
        target.resolve(strict=False).relative_to(template)
    except ValueError:
        pass
    else:
        raise ForgeValidationError(("workspace target must not be inside its template",))

    staging = Path(tempfile.mkdtemp(dir=parent, prefix=f".{target.name}.forge-init-"))
    try:
        for source, relative in _iter_template_entries(template):
            if _is_link_or_junction(source):
                raise ForgeValidationError(
                    (
                        "template contains a symbolic link or junction: "
                        f"{relative.as_posix()}",
                    )
                )
            destination = staging / relative
            if source.is_dir():
                destination.mkdir()
            elif source.is_file():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
            else:
                raise ForgeValidationError(
                    (f"template contains an unsupported entry: {relative.as_posix()}",)
                )
        if (staging / ".forge").exists():
            raise ForgeValidationError(("template must not contain generated .forge state",))
        loaded = load_forge_workspace(staging)
        artifact_root = _resolve_member(staging, loaded.config.artifact_root)
        if os.path.lexists(artifact_root):
            raise ForgeValidationError(("template artifact_root must start absent",))
        artifact_root.mkdir(parents=True)
        report = inspect_forge_workspace(staging)
        bad = [
            stage
            for stage in report["stages"]  # type: ignore[index]
            if stage["status"] == "BLOCKED"
        ]
        if bad:
            reasons = "; ".join(str(stage.get("reason")) for stage in bad)
            raise ForgeValidationError((f"template is not runnable: {reasons}",))
        if os.path.lexists(target):
            raise ForgeExecutionError(f"workspace was created concurrently: {target}")
        os.replace(staging, target)
        return target.resolve()
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _render_report(report: dict[str, object]) -> str:
    lines = [
        f"Forge workspace: {report['workspace_id']}",
        f"Overall: {report['overall_status']}",
    ]
    actions = report.get("actions")
    if isinstance(actions, list):
        for action in actions:
            lines.append(
                f"Action {action['stage']}: {str(action['action']).upper()}"
            )
    for stage in report["stages"]:  # type: ignore[index]
        lines.append(f"{stage['stage']}: {stage['status']}")
        reason = stage.get("reason")
        if reason:
            lines.append(f"  reason: {reason}")
        for artifact in stage["inputs"]:
            digest = artifact.get("sha256", "-")
            lines.append(
                f"  input: {artifact['path']} [{artifact['state']}] {str(digest)[:12]}"
            )
        for artifact in stage["outputs"]:
            lines.append(
                f"  output: {artifact['path']} [{artifact['kind']}] "
                f"{str(artifact['sha256'])[:12]}"
            )
    return "\n".join(lines)


def _selected_stages(value: str) -> tuple[StageName, ...]:
    return _STAGES if value == "all" else (value,)  # type: ignore[return-value]


def _status_parser(subparsers: Any, command: str, help_text: str) -> None:
    parser = subparsers.add_parser(command, help=help_text)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="create a Forge workspace")
    init_parser.add_argument("workspace", type=Path)
    init_parser.add_argument("--template", required=True, type=Path)
    _status_parser(subparsers, "status", "show workspace stage status")
    _status_parser(subparsers, "check", "require every stage to be current")
    for command, help_text in (
        ("run", "resume runnable stages"),
        ("rerun", "force new immutable outputs"),
    ):
        run_parser = subparsers.add_parser(command, help=help_text)
        run_parser.add_argument("workspace", type=Path)
        run_parser.add_argument(
            "--stage", choices=("all", *_STAGES), default="all"
        )
        run_parser.add_argument("--json", action="store_true", dest="as_json")

    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            initialize_forge_workspace(args.workspace, args.template)
            print("Initialized Forge workspace.")
            return 0
        if args.command in {"status", "check"}:
            report = inspect_forge_workspace(args.workspace)
            print(
                json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2)
                if args.as_json
                else _render_report(report)
            )
            if args.command == "check" and report["overall_status"] != "CURRENT":
                return 1
            return 0

        report, succeeded = run_forge_workspace(
            args.workspace,
            stages=_selected_stages(args.stage),
            force=args.command == "rerun",
        )
        print(
            json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2)
            if args.as_json
            else _render_report(report)
        )
        return 0 if succeeded else 1
    except json.JSONDecodeError as exc:
        print(f"Forge JSON error: {exc}", file=sys.stderr)
        return 1
    except UnicodeDecodeError as exc:
        print(f"Forge UTF-8 error: {exc}", file=sys.stderr)
        return 1
    except (
        ForgeValidationError,
        ForgeExecutionError,
        CanonRegistryValidationError,
        RegistryInspectionValidationError,
        RegistryInspectionBuildError,
        RegistryAdaptationValidationError,
        RegistryCompilationError,
        ContentValidationError,
        OSError,
    ) as exc:
        print(f"Forge error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
