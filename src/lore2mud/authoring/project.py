"""Validation and immutable capture for GameBlueprint v1 and GameProject v1."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
import re
from pathlib import Path, PurePosixPath
import tempfile
from typing import TypeVar, cast

from lore2mud._bounded_json import (
    BoundedJsonError,
    DEFAULT_JSON_READ_LIMITS,
    read_bounded_json,
)
from lore2mud.application.contracts import DeterminismContext
from lore2mud.authoring.contracts import (
    CAPABILITY_DIAGNOSTIC_CODE,
    AcceptanceScenario,
    AdaptationBoundaries,
    ApprovalRecord,
    AuthoringDiagnostic,
    AuthoringStage,
    BuildLock,
    CanonicalContentFile,
    ConditionOutcome,
    CreatorDecision,
    DiagnosticSeverity,
    GameBlueprint,
    GameProject,
    PlayLength,
    PublicInputDescriptor,
    TraceRecord,
    WorkspaceMetadataEntry,
)
from lore2mud.authoring.serialization import (
    blueprint_to_document,
    blueprint_bytes,
    canonical_json_bytes,
    fingerprint_document,
    normalize_bounded_json_document,
    project_core_to_document,
    project_to_document,
    sha256_bytes,
)
from lore2mud.content.loader import ContentValidationError, load_content_pack


REQUIRED_V1_CONTENT_FILES = (
    "pack.json",
    "rooms.json",
    "items.json",
    "monsters.json",
    "characters.json",
    "quests.json",
    "dialogues.json",
    "shops.json",
)
OPTIONAL_V1_CONTENT_FILES = ("narrative_state.json", "campaign.json")
V1_CONTENT_FILE_ORDER = REQUIRED_V1_CONTENT_FILES + OPTIONAL_V1_CONTENT_FILES

_STABLE_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MAX_TEXT = 4096
_MAX_PROJECT_COLLECTION = 4096
_MAX_TRACE_RECORDS = 8192


class BlueprintValidationError(ValueError):
    def __init__(self, issues: Sequence[str]) -> None:
        self.issues = tuple(issues)
        super().__init__("; ".join(self.issues))


class ProjectValidationError(ValueError):
    def __init__(self, issues: Sequence[str]) -> None:
        self.issues = tuple(issues)
        super().__init__("; ".join(self.issues))


def read_authoring_json(path: Path) -> object:
    try:
        return read_bounded_json(path, DEFAULT_JSON_READ_LIMITS)
    except BoundedJsonError as exc:
        raise ProjectValidationError((f"unable to read {path.name}: {exc.code.value}",)) from None


def load_blueprint(path: Path) -> GameBlueprint:
    return load_blueprint_document(read_authoring_json(path))


def load_blueprint_document(document: object) -> GameBlueprint:
    issues: list[str] = []
    data = _mapping(document, "blueprint", issues)
    _keys(
        data,
        {
            "format_version",
            "blueprint_id",
            "title",
            "approval",
            "audience",
            "genre",
            "tone",
            "play_length",
            "adaptation_boundaries",
            "required_game_loops",
            "acceptance_scenarios",
            "capability_requirement_ids",
            "asset_requirements",
            "provenance_requirements",
            "rights_assertions",
            "default_determinism",
        },
        "blueprint",
        issues,
    )
    format_version = _integer(data.get("format_version"), "format_version", issues)
    if format_version != 1:
        issues.append("format_version must be 1")
    blueprint_id = _stable_id(data.get("blueprint_id"), "blueprint_id", issues)
    title = _text(data.get("title"), "title", issues)

    approval_data = _mapping(data.get("approval"), "approval", issues)
    _keys(approval_data, {"approved", "decision_id", "approver"}, "approval", issues)
    approved = _boolean(approval_data.get("approved"), "approval.approved", issues)
    approval = ApprovalRecord(
        approved=approved,
        decision_id=_stable_id(
            approval_data.get("decision_id"), "approval.decision_id", issues
        ),
        approver=_text(approval_data.get("approver"), "approval.approver", issues),
    )

    play_data = _mapping(data.get("play_length"), "play_length", issues)
    _keys(
        play_data,
        {"minimum_minutes", "target_minutes", "maximum_minutes"},
        "play_length",
        issues,
    )
    minimum = _positive_int(
        play_data.get("minimum_minutes"), "play_length.minimum_minutes", issues
    )
    target = _positive_int(
        play_data.get("target_minutes"), "play_length.target_minutes", issues
    )
    maximum = _positive_int(
        play_data.get("maximum_minutes"), "play_length.maximum_minutes", issues
    )
    if not minimum <= target <= maximum:
        issues.append("play_length must satisfy minimum <= target <= maximum")

    boundary_data = _mapping(
        data.get("adaptation_boundaries"), "adaptation_boundaries", issues
    )
    _keys(boundary_data, {"allowed", "excluded"}, "adaptation_boundaries", issues)
    boundaries = AdaptationBoundaries(
        allowed=_text_set(
            boundary_data.get("allowed"), "adaptation_boundaries.allowed", issues
        ),
        excluded=_text_set(
            boundary_data.get("excluded"), "adaptation_boundaries.excluded", issues
        ),
    )

    scenarios: list[AcceptanceScenario] = []
    seen_scenarios: set[str] = set()
    for index, raw in enumerate(
        _bounded_list(
            data.get("acceptance_scenarios"),
            "acceptance_scenarios",
            issues,
            _MAX_PROJECT_COLLECTION,
        )
    ):
        location = f"acceptance_scenarios[{index}]"
        item = _mapping(raw, location, issues)
        _keys(item, {"scenario_id", "description", "outcome"}, location, issues)
        scenario_id = _stable_id(item.get("scenario_id"), f"{location}.scenario_id", issues)
        if scenario_id in seen_scenarios:
            issues.append(f"{location}.scenario_id is duplicated")
        seen_scenarios.add(scenario_id)
        try:
            outcome = ConditionOutcome(
                _text(item.get("outcome"), f"{location}.outcome", issues)
            )
        except ValueError:
            issues.append(f"{location}.outcome must be win or loss")
            outcome = ConditionOutcome.WIN
        scenarios.append(
            AcceptanceScenario(
                scenario_id=scenario_id,
                description=_text(
                    item.get("description"), f"{location}.description", issues
                ),
                outcome=outcome,
            )
        )

    determinism_data = _mapping(
        data.get("default_determinism"), "default_determinism", issues
    )
    _keys(determinism_data, {"seed", "clock"}, "default_determinism", issues)
    determinism = DeterminismContext(
        seed=_bounded_integer(
            determinism_data.get("seed"), "default_determinism.seed", issues
        ),
        clock=_bounded_integer(
            determinism_data.get("clock"), "default_determinism.clock", issues
        ),
    )

    blueprint = GameBlueprint(
        format_version=1,
        blueprint_id=blueprint_id,
        title=title,
        approval=approval,
        audience=_text(data.get("audience"), "audience", issues),
        genre=_text(data.get("genre"), "genre", issues),
        tone=_text(data.get("tone"), "tone", issues),
        play_length=PlayLength(minimum, target, maximum),
        adaptation_boundaries=boundaries,
        required_game_loops=_stable_id_set(
            data.get("required_game_loops"), "required_game_loops", issues
        ),
        acceptance_scenarios=tuple(sorted(scenarios, key=lambda value: value.scenario_id)),
        capability_requirement_ids=_stable_id_set(
            data.get("capability_requirement_ids"),
            "capability_requirement_ids",
            issues,
        ),
        asset_requirements=_text_set(
            data.get("asset_requirements"), "asset_requirements", issues
        ),
        provenance_requirements=_text_set(
            data.get("provenance_requirements"), "provenance_requirements", issues
        ),
        rights_assertions=_text_set(
            data.get("rights_assertions"), "rights_assertions", issues
        ),
        default_determinism=determinism,
    )
    if issues:
        raise BlueprintValidationError(issues)
    return blueprint


def capture_v1_content(content_root: Path) -> tuple[CanonicalContentFile, ...]:
    root = content_root.resolve()
    if not root.is_dir():
        raise ProjectValidationError(("content directory does not exist",))

    files: list[CanonicalContentFile] = []
    for name in V1_CONTENT_FILE_ORDER:
        path = root / name
        if name in OPTIONAL_V1_CONTENT_FILES and not path.exists():
            continue
        try:
            document = read_bounded_json(path, DEFAULT_JSON_READ_LIMITS)
        except BoundedJsonError as exc:
            raise ProjectValidationError((f"unable to capture {name}: {exc.code.value}",)) from None
        payload = canonical_json_bytes(document)
        files.append(CanonicalContentFile(name, sha256_bytes(payload), payload))
    captured = tuple(files)
    # The legacy loader only sees the already bounded immutable snapshot, never the
    # caller's mutable source directory.
    _validate_captured_content(captured)
    return captured


def create_game_project(
    *,
    project_id: str,
    blueprint: GameBlueprint,
    content_root: Path,
    public_inputs: Iterable[PublicInputDescriptor] = (),
    creator_decisions: Iterable[CreatorDecision] = (),
    trace_records: Iterable[TraceRecord] = (),
    workspace_metadata: Iterable[WorkspaceMetadataEntry] = (),
) -> GameProject:
    normalized_blueprint = validate_blueprint(blueprint)
    if not normalized_blueprint.approval.approved:
        raise ProjectValidationError(("blueprint approval must be approved",))
    normalized_id = _validated_stable_id(project_id, "project_id")
    blueprint_sha = sha256_bytes(blueprint_bytes(normalized_blueprint))
    project = GameProject(
        format_version=1,
        project_id=normalized_id,
        blueprint=normalized_blueprint,
        blueprint_sha256=blueprint_sha,
        public_inputs=_normalize_public_inputs(public_inputs),
        content_files=capture_v1_content(content_root),
        creator_decisions=_normalize_creator_decisions(creator_decisions),
        trace_records=_normalize_trace_records(trace_records),
        build_lock=BuildLock("0" * 64),
        workspace_metadata=_normalize_workspace_metadata(workspace_metadata),
    )
    lock = fingerprint_document(project_core_to_document(project))
    finalized = GameProject(
        format_version=project.format_version,
        project_id=project.project_id,
        blueprint=project.blueprint,
        blueprint_sha256=project.blueprint_sha256,
        public_inputs=project.public_inputs,
        content_files=project.content_files,
        creator_decisions=project.creator_decisions,
        trace_records=project.trace_records,
        build_lock=BuildLock(lock),
        workspace_metadata=project.workspace_metadata,
    )
    # Re-read the exact captured bytes so SDK callers cannot bypass field checks and
    # a source-directory race cannot return a project whose immutable snapshot fails.
    return validate_project(finalized)


def load_project(path: Path) -> GameProject:
    return load_project_document(read_authoring_json(path))


def load_project_document(document: object) -> GameProject:
    issues: list[str] = []
    data = _mapping(document, "project", issues)
    _keys(
        data,
        {
            "format_version",
            "project_id",
            "blueprint",
            "blueprint_sha256",
            "public_inputs",
            "content_files",
            "creator_decisions",
            "trace_records",
            "build_lock",
            "workspace_metadata",
        },
        "project",
        issues,
    )
    if _integer(data.get("format_version"), "format_version", issues) != 1:
        issues.append("format_version must be 1")
    project_id = _stable_id(data.get("project_id"), "project_id", issues)
    try:
        blueprint = load_blueprint_document(data.get("blueprint"))
    except BlueprintValidationError as exc:
        issues.extend(f"blueprint: {issue}" for issue in exc.issues)
        blueprint = _fallback_blueprint()
    if not blueprint.approval.approved:
        issues.append("blueprint approval must be approved")
    blueprint_sha = _sha256(data.get("blueprint_sha256"), "blueprint_sha256", issues)
    if blueprint_sha != sha256_bytes(blueprint_bytes(blueprint)):
        issues.append("blueprint_sha256 does not match canonical blueprint bytes")

    public_inputs = _load_public_inputs(data.get("public_inputs"), issues)
    content_files = _load_content_files(data.get("content_files"), issues)
    creator_decisions = _load_creator_decisions(data.get("creator_decisions"), issues)
    trace_records = _load_trace_records(data.get("trace_records"), issues)
    workspace_metadata = _load_workspace_metadata(data.get("workspace_metadata"), issues)
    lock_data = _mapping(data.get("build_lock"), "build_lock", issues)
    _keys(lock_data, {"input_sha256"}, "build_lock", issues)
    lock = BuildLock(_sha256(lock_data.get("input_sha256"), "build_lock.input_sha256", issues))

    project = GameProject(
        format_version=1,
        project_id=project_id,
        blueprint=blueprint,
        blueprint_sha256=blueprint_sha,
        public_inputs=public_inputs,
        content_files=content_files,
        creator_decisions=creator_decisions,
        trace_records=trace_records,
        build_lock=lock,
        workspace_metadata=workspace_metadata,
    )
    expected_lock = fingerprint_document(project_core_to_document(project))
    if lock.input_sha256 != expected_lock:
        issues.append("build_lock.input_sha256 does not match project inputs")
    if not issues:
        _validate_captured_content(content_files)
    if issues:
        raise ProjectValidationError(issues)
    return project


def validate_blueprint(blueprint: GameBlueprint) -> GameBlueprint:
    if type(blueprint) is not GameBlueprint:
        raise BlueprintValidationError(("value must be a typed GameBlueprint v1",))
    try:
        document = blueprint_to_document(blueprint)
    except (AttributeError, TypeError, ValueError):
        raise BlueprintValidationError(
            ("typed GameBlueprint v1 could not be normalized",)
        ) from None
    return load_blueprint_document(normalize_bounded_json_document(document))


def validate_project(project: GameProject) -> GameProject:
    if type(project) is not GameProject:
        raise ProjectValidationError(("value must be a typed GameProject v1",))
    try:
        document = project_to_document(project)
    except (AttributeError, TypeError, ValueError):
        raise ProjectValidationError(
            ("typed GameProject v1 could not be normalized",)
        ) from None
    return load_project_document(normalize_bounded_json_document(document))


def capability_requirement_pointer(index: int) -> str:
    return f"/blueprint/capability_requirement_ids/{index}"


def diagnostic_artifact_id(value: object, fallback: str = "project") -> str:
    """Return only a validated stable ID for public authoring diagnostics."""
    return (
        value
        if type(value) is str and _STABLE_ID_RE.fullmatch(value) is not None
        else fallback
    )


def capability_requirement_diagnostics(
    project: GameProject,
) -> tuple[AuthoringDiagnostic, ...]:
    try:
        requirements = project.blueprint.capability_requirement_ids
    except AttributeError:
        return ()
    if type(requirements) is not tuple:
        return ()
    return tuple(
        AuthoringDiagnostic(
            stage=AuthoringStage.PREVIEW,
            code=CAPABILITY_DIAGNOSTIC_CODE,
            severity=DiagnosticSeverity.ERROR,
            artifact_id=diagnostic_artifact_id(project.project_id),
            json_pointer=capability_requirement_pointer(index),
            source_span=None,
            message=(
                "V2 capability requirements are not supported by the fixed "
                "V2-2 preview profile."
            ),
            remediation=(
                "Remove the requirement for V2-2 preview/simulation or wait for V2-3."
            ),
        )
        for index, _requirement in enumerate(requirements[:_MAX_PROJECT_COLLECTION])
    )


def _validate_captured_content(files: tuple[CanonicalContentFile, ...]) -> None:
    try:
        with tempfile.TemporaryDirectory(prefix="lore2mud-v2-project-") as directory:
            root = Path(directory)
            for value in files:
                (root / value.name).write_bytes(value.canonical_json)
            load_content_pack(root)
    except (ContentValidationError, OSError) as exc:
        raw_issues = getattr(exc, "issues", ("V1 content validation failed",))
        raise ProjectValidationError(tuple(_public_issue(value) for value in raw_issues)) from None


def _load_content_files(
    value: object, issues: list[str]
) -> tuple[CanonicalContentFile, ...]:
    loaded: dict[str, CanonicalContentFile] = {}
    for index, raw in enumerate(_list(value, "content_files", issues)):
        location = f"content_files[{index}]"
        item = _mapping(raw, location, issues)
        _keys(item, {"name", "sha256", "document"}, location, issues)
        name = _safe_content_name(item.get("name"), f"{location}.name", issues)
        if name in loaded:
            issues.append(f"{location}.name is duplicated")
        try:
            payload = canonical_json_bytes(item.get("document"))
        except (TypeError, ValueError):
            issues.append(f"{location}.document is not canonical JSON data")
            payload = b"null\n"
        digest = _sha256(item.get("sha256"), f"{location}.sha256", issues)
        if digest != sha256_bytes(payload):
            issues.append(f"{location}.sha256 does not match document")
        loaded[name] = CanonicalContentFile(name, digest, payload)
    expected = set(REQUIRED_V1_CONTENT_FILES)
    if not expected.issubset(loaded):
        issues.append("content_files is missing required V1 content files")
    if set(loaded) - set(V1_CONTENT_FILE_ORDER):
        issues.append("content_files contains unsupported runtime inputs")
    return tuple(loaded[name] for name in V1_CONTENT_FILE_ORDER if name in loaded)


def _load_public_inputs(
    value: object, issues: list[str]
) -> tuple[PublicInputDescriptor, ...]:
    result: list[PublicInputDescriptor] = []
    for index, raw in enumerate(
        _bounded_list(value, "public_inputs", issues, _MAX_PROJECT_COLLECTION)
    ):
        location = f"public_inputs[{index}]"
        item = _mapping(raw, location, issues)
        _keys(item, {"artifact_id", "media_type", "label", "visibility"}, location, issues)
        visibility = _text(item.get("visibility"), f"{location}.visibility", issues)
        if visibility != "public_safe":
            issues.append(f"{location}.visibility must be public_safe")
        result.append(
            PublicInputDescriptor(
                _stable_id(item.get("artifact_id"), f"{location}.artifact_id", issues),
                _text(item.get("media_type"), f"{location}.media_type", issues),
                _text(item.get("label"), f"{location}.label", issues),
                "public_safe",
            )
        )
    return _normalize_public_inputs(result, issues=issues)


def _load_creator_decisions(
    value: object, issues: list[str]
) -> tuple[CreatorDecision, ...]:
    result: list[CreatorDecision] = []
    for index, raw in enumerate(
        _bounded_list(value, "creator_decisions", issues, _MAX_PROJECT_COLLECTION)
    ):
        location = f"creator_decisions[{index}]"
        item = _mapping(raw, location, issues)
        _keys(item, {"decision_id", "statement"}, location, issues)
        result.append(
            CreatorDecision(
                _stable_id(item.get("decision_id"), f"{location}.decision_id", issues),
                _text(item.get("statement"), f"{location}.statement", issues),
            )
        )
    return _normalize_creator_decisions(result, issues=issues)


def _load_trace_records(
    value: object, issues: list[str]
) -> tuple[TraceRecord, ...]:
    result: list[TraceRecord] = []
    for index, raw in enumerate(
        _bounded_list(value, "trace_records", issues, _MAX_TRACE_RECORDS)
    ):
        location = f"trace_records[{index}]"
        item = _mapping(raw, location, issues)
        _keys(
            item,
            {"trace_id", "source_artifact_id", "target_artifact_id", "decision_id"},
            location,
            issues,
        )
        result.append(
            TraceRecord(
                _stable_id(item.get("trace_id"), f"{location}.trace_id", issues),
                _stable_id(
                    item.get("source_artifact_id"),
                    f"{location}.source_artifact_id",
                    issues,
                ),
                _stable_id(
                    item.get("target_artifact_id"),
                    f"{location}.target_artifact_id",
                    issues,
                ),
                _stable_id(item.get("decision_id"), f"{location}.decision_id", issues),
            )
        )
    return _normalize_trace_records(result, issues=issues)


def _load_workspace_metadata(
    value: object, issues: list[str]
) -> tuple[WorkspaceMetadataEntry, ...]:
    result: list[WorkspaceMetadataEntry] = []
    for index, raw in enumerate(
        _bounded_list(value, "workspace_metadata", issues, _MAX_PROJECT_COLLECTION)
    ):
        location = f"workspace_metadata[{index}]"
        item = _mapping(raw, location, issues)
        _keys(item, {"key", "value"}, location, issues)
        result.append(
            WorkspaceMetadataEntry(
                _text(item.get("key"), f"{location}.key", issues),
                _text(item.get("value"), f"{location}.value", issues),
            )
        )
    return _normalize_workspace_metadata(result, issues=issues)


def _normalize_public_inputs(
    values: Iterable[PublicInputDescriptor], *, issues: list[str] | None = None
) -> tuple[PublicInputDescriptor, ...]:
    return _unique_sorted(
        values,
        lambda value: value.artifact_id,
        "public input",
        issues,
        maximum=_MAX_PROJECT_COLLECTION,
    )


def _normalize_creator_decisions(
    values: Iterable[CreatorDecision], *, issues: list[str] | None = None
) -> tuple[CreatorDecision, ...]:
    return _unique_sorted(
        values,
        lambda value: value.decision_id,
        "creator decision",
        issues,
        maximum=_MAX_PROJECT_COLLECTION,
    )


def _normalize_trace_records(
    values: Iterable[TraceRecord], *, issues: list[str] | None = None
) -> tuple[TraceRecord, ...]:
    return _unique_sorted(
        values,
        lambda value: value.trace_id,
        "trace record",
        issues,
        maximum=_MAX_TRACE_RECORDS,
    )


def _normalize_workspace_metadata(
    values: Iterable[WorkspaceMetadataEntry], *, issues: list[str] | None = None
) -> tuple[WorkspaceMetadataEntry, ...]:
    return _unique_sorted(
        values,
        lambda value: value.key,
        "workspace metadata",
        issues,
        maximum=_MAX_PROJECT_COLLECTION,
    )


_ValueT = TypeVar("_ValueT")


def _unique_sorted(
    values: Iterable[_ValueT],
    key: Callable[[_ValueT], str],
    label: str,
    issues: list[str] | None,
    *,
    maximum: int,
) -> tuple[_ValueT, ...]:
    collected: list[_ValueT] = []
    for value in values:
        if len(collected) >= maximum:
            issue = f"{label} collection exceeds {maximum} entries"
            if issues is None:
                raise ProjectValidationError((issue,))
            issues.append(issue)
            break
        collected.append(value)
    ordered = sorted(collected, key=key)
    keys = [key(value) for value in ordered]
    if len(keys) != len(set(keys)):
        if issues is None:
            raise ProjectValidationError((f"duplicate {label} id",))
        issues.append(f"duplicate {label} id")
    return tuple(ordered)


def _mapping(value: object, location: str, issues: list[str]) -> dict[str, object]:
    if type(value) is not dict:
        issues.append(f"{location} must be an object")
        return {}
    return cast(dict[str, object], value)


def _list(value: object, location: str, issues: list[str]) -> list[object]:
    if type(value) is not list:
        issues.append(f"{location} must be an array")
        return []
    return value


def _bounded_list(
    value: object,
    location: str,
    issues: list[str],
    maximum: int,
) -> list[object]:
    values = _list(value, location, issues)
    if len(values) > maximum:
        issues.append(f"{location} exceeds {maximum} entries")
        return values[:maximum]
    return values


def _keys(
    data: dict[str, object], expected: set[str], location: str, issues: list[str]
) -> None:
    missing = expected - set(data)
    extra = set(data) - expected
    if missing:
        issues.append(f"{location} is missing fields: {sorted(missing)}")
    if extra:
        issues.append(f"{location} has unknown fields: {sorted(extra)}")


def _text(value: object, location: str, issues: list[str]) -> str:
    if type(value) is not str or not value.strip() or len(value) > _MAX_TEXT:
        issues.append(f"{location} must be a bounded non-blank string")
        return "invalid"
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        issues.append(f"{location} contains an invalid Unicode surrogate")
        return "invalid"
    return value


def _stable_id(value: object, location: str, issues: list[str]) -> str:
    text = _text(value, location, issues)
    if not _STABLE_ID_RE.fullmatch(text):
        issues.append(f"{location} must be a lower_snake stable ID")
        return "invalid"
    return text


def _validated_stable_id(value: str, location: str) -> str:
    issues: list[str] = []
    result = _stable_id(value, location, issues)
    if issues:
        raise ProjectValidationError(issues)
    return result


def _integer(value: object, location: str, issues: list[str]) -> int:
    if type(value) is not int:
        issues.append(f"{location} must be an integer")
        return 0
    return value


def _bounded_integer(value: object, location: str, issues: list[str]) -> int:
    result = _integer(value, location, issues)
    if result < -(2**63) or result > 2**63 - 1:
        issues.append(f"{location} must be within the signed 64-bit range")
        return 0
    return result


def _positive_int(value: object, location: str, issues: list[str]) -> int:
    result = _integer(value, location, issues)
    if result < 1 or result > 1440:
        issues.append(f"{location} must be between 1 and 1440")
        return 1
    return result


def _boolean(value: object, location: str, issues: list[str]) -> bool:
    if type(value) is not bool:
        issues.append(f"{location} must be a boolean")
        return False
    return value


def _sha256(value: object, location: str, issues: list[str]) -> str:
    text = _text(value, location, issues)
    if not _SHA256_RE.fullmatch(text):
        issues.append(f"{location} must be a lowercase SHA-256")
        return "0" * 64
    return text


def _text_set(value: object, location: str, issues: list[str]) -> tuple[str, ...]:
    values = tuple(
        _text(item, f"{location}[{index}]", issues)
        for index, item in enumerate(
            _bounded_list(value, location, issues, _MAX_PROJECT_COLLECTION)
        )
    )
    if len(values) != len(set(values)):
        issues.append(f"{location} must not contain duplicates")
    return tuple(sorted(values))


def _stable_id_set(value: object, location: str, issues: list[str]) -> tuple[str, ...]:
    values = tuple(
        _stable_id(item, f"{location}[{index}]", issues)
        for index, item in enumerate(
            _bounded_list(value, location, issues, _MAX_PROJECT_COLLECTION)
        )
    )
    if len(values) != len(set(values)):
        issues.append(f"{location} must not contain duplicates")
    return tuple(sorted(values))


def _safe_content_name(value: object, location: str, issues: list[str]) -> str:
    name = _text(value, location, issues)
    path = PurePosixPath(name)
    if path.is_absolute() or len(path.parts) != 1 or name not in V1_CONTENT_FILE_ORDER:
        issues.append(f"{location} must be an allowed relative V1 content file")
        return "pack.json"
    return name


def _public_issue(value: object) -> str:
    del value
    return "V1 content validation failed"


def _fallback_blueprint() -> GameBlueprint:
    return GameBlueprint(
        format_version=1,
        blueprint_id="invalid",
        title="invalid",
        approval=ApprovalRecord(False, "invalid", "invalid"),
        audience="invalid",
        genre="invalid",
        tone="invalid",
        play_length=PlayLength(1, 1, 1),
        adaptation_boundaries=AdaptationBoundaries((), ()),
        required_game_loops=(),
        acceptance_scenarios=(),
        capability_requirement_ids=(),
        asset_requirements=(),
        provenance_requirements=(),
        rights_assertions=(),
        default_determinism=DeterminismContext(),
    )
