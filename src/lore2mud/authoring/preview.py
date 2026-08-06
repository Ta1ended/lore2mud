"""Fixed-profile, non-distributable V2-2 preview construction."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
import tempfile
from typing import cast

from lore2mud import __version__
from lore2mud.authoring.contracts import (
    PREVIEW_IDENTITY_SCOPE,
    V1_COMPATIBILITY_PROFILE_ID,
    AuthoringDiagnostic,
    AuthoringResult,
    AuthoringStage,
    AuthoringStatus,
    CanonicalContentFile,
    DiagnosticSeverity,
    GameProject,
    PreviewBuild,
)
from lore2mud.authoring.project import (
    BlueprintValidationError,
    ProjectValidationError,
    REQUIRED_V1_CONTENT_FILES,
    V1_CONTENT_FILE_ORDER,
    capability_requirement_diagnostics,
    diagnostic_artifact_id,
    read_authoring_json,
    validate_project,
)
from lore2mud.authoring.serialization import (
    canonical_json_bytes,
    fingerprint_document,
    preview_to_document,
    sha256_bytes,
)
from lore2mud.content.loader import ContentPack, ContentValidationError, load_content_pack


class PreviewValidationError(ValueError):
    """Raised when an untrusted preview document violates the V2-2 contract."""

    def __init__(self, issues: Sequence[str]) -> None:
        self.issues = tuple(issues)
        super().__init__("; ".join(self.issues))


def build_preview(project: GameProject) -> AuthoringResult[PreviewBuild]:
    """Build one deterministic fixed-profile preview without retaining runtime state."""
    try:
        normalized = validate_project(project)
    except (BlueprintValidationError, ProjectValidationError):
        return _rejected(
            "build_preview",
            (
                _diagnostic(
                    normalized_id(project),
                    "preview_project_invalid",
                    "/",
                    "The project is invalid for the fixed V1 preview profile.",
                    "Correct the public-safe project inputs and rebuild the preview.",
                ),
            ),
        )

    capability_diagnostics = capability_requirement_diagnostics(normalized)
    if capability_diagnostics:
        return _rejected("build_preview", capability_diagnostics)

    try:
        with _materialized_content_pack(normalized.content_files):
            pass
    except (ContentValidationError, OSError):
        return _rejected(
            "build_preview",
            (
                _diagnostic(
                    normalized_id(project),
                    "preview_content_invalid",
                    "/content_files",
                    "The captured V1 content could not be materialized as a preview.",
                    "Correct the public-safe V1 content documents and retry.",
                ),
            ),
        )

    project_sha256 = fingerprint_document(_project_semantic_document(normalized))
    preview_without_fingerprint = PreviewBuild(
        format_version=1,
        preview_id=f"preview_{project_sha256[:24]}",
        project_id=normalized.project_id,
        blueprint_sha256=normalized.blueprint_sha256,
        project_sha256=project_sha256,
        engine_version=__version__,
        content_files=normalized.content_files,
        fingerprint="",
    )
    fingerprint = fingerprint_document(
        preview_to_document(preview_without_fingerprint, include_fingerprint=False)
    )
    preview = PreviewBuild(
        format_version=preview_without_fingerprint.format_version,
        preview_id=preview_without_fingerprint.preview_id,
        project_id=preview_without_fingerprint.project_id,
        blueprint_sha256=preview_without_fingerprint.blueprint_sha256,
        project_sha256=preview_without_fingerprint.project_sha256,
        engine_version=preview_without_fingerprint.engine_version,
        content_files=preview_without_fingerprint.content_files,
        fingerprint=fingerprint,
    )
    return AuthoringResult(
        format_version=1,
        operation="build_preview",
        status=AuthoringStatus.SUCCESS,
        artifact=preview,
        diagnostics=(),
        exit_code=0,
    )


def load_preview(path: Path) -> PreviewBuild:
    """Read and validate a bounded preview JSON document."""
    return load_preview_document(read_authoring_json(path))


def load_preview_document(document: object) -> PreviewBuild:
    """Validate one preview document, including content and fingerprint integrity."""
    data = _object(document, "preview")
    _exact_keys(
        data,
        {
            "format_version",
            "preview_id",
            "project_id",
            "kind",
            "sealed",
            "distributable",
            "release_evidence",
            "identity_scope",
            "profile_id",
            "blueprint_sha256",
            "project_sha256",
            "engine_version",
            "content_files",
            "fingerprint",
        },
        "preview",
    )
    if _integer(data["format_version"], "preview.format_version") != 1:
        raise PreviewValidationError(("preview.format_version must be 1",))
    if data["kind"] != "preview":
        raise PreviewValidationError(("preview.kind must be preview",))
    for field in ("sealed", "distributable", "release_evidence"):
        if data[field] is not False:
            raise PreviewValidationError((f"preview.{field} must be false",))
    if data["identity_scope"] != PREVIEW_IDENTITY_SCOPE:
        raise PreviewValidationError(("preview.identity_scope is invalid",))
    if data["profile_id"] != V1_COMPATIBILITY_PROFILE_ID:
        raise PreviewValidationError(("preview.profile_id is invalid",))

    files = _content_files(data["content_files"])
    engine_version = _text(data["engine_version"], "preview.engine_version", maximum=64)
    if engine_version != __version__:
        raise PreviewValidationError(("preview.engine_version is not supported",))
    preview = PreviewBuild(
        format_version=1,
        preview_id=_stable_id(data["preview_id"], "preview.preview_id", maximum=96),
        project_id=_stable_id(data["project_id"], "preview.project_id"),
        blueprint_sha256=_sha256(data["blueprint_sha256"], "preview.blueprint_sha256"),
        project_sha256=_sha256(data["project_sha256"], "preview.project_sha256"),
        engine_version=engine_version,
        content_files=files,
        fingerprint=_sha256(data["fingerprint"], "preview.fingerprint"),
    )
    expected = fingerprint_document(preview_to_document(preview, include_fingerprint=False))
    if preview.fingerprint != expected:
        raise PreviewValidationError(("preview.fingerprint does not match canonical bytes",))
    try:
        with _materialized_content_pack(files):
            pass
    except (ContentValidationError, OSError):
        raise PreviewValidationError(("preview.content_files is not valid V1 content",)) from None
    return preview


@contextmanager
def materialized_preview_pack(preview: PreviewBuild) -> Iterator[ContentPack]:
    """Yield a fresh ContentPack loaded only from immutable preview bytes."""
    validated = load_preview_document(preview_to_document(preview))
    with _materialized_content_pack(validated.content_files) as pack:
        yield pack


@contextmanager
def _materialized_content_pack(
    files: tuple[CanonicalContentFile, ...],
) -> Iterator[ContentPack]:
    with tempfile.TemporaryDirectory(prefix="lore2mud-v2-preview-") as directory:
        root = Path(directory)
        for value in files:
            (root / value.name).write_bytes(value.canonical_json)
        yield load_content_pack(root)


def _project_semantic_document(project: GameProject) -> dict[str, object]:
    # Importing here keeps preview identity coupled to the frozen serializer only.
    from lore2mud.authoring.serialization import project_semantic_to_document

    return project_semantic_to_document(project)


def _content_files(value: object) -> tuple[CanonicalContentFile, ...]:
    if type(value) is not list:
        raise PreviewValidationError(("preview.content_files must be an array",))
    loaded: dict[str, CanonicalContentFile] = {}
    for index, raw in enumerate(cast(list[object], value)):
        item = _object(raw, f"preview.content_files[{index}]")
        _exact_keys(item, {"name", "sha256", "document"}, f"preview.content_files[{index}]")
        name = _text(item["name"], f"preview.content_files[{index}].name", maximum=64)
        if name not in V1_CONTENT_FILE_ORDER or name in loaded:
            raise PreviewValidationError(("preview.content_files names are invalid",))
        payload = canonical_json_bytes(item["document"])
        digest = _sha256(item["sha256"], f"preview.content_files[{index}].sha256")
        if digest != sha256_bytes(payload):
            raise PreviewValidationError(("preview content hash does not match document",))
        loaded[name] = CanonicalContentFile(name, digest, payload)
    if not set(REQUIRED_V1_CONTENT_FILES).issubset(loaded):
        raise PreviewValidationError(("preview.content_files is missing required V1 content",))
    ordered_names = [name for name in V1_CONTENT_FILE_ORDER if name in loaded]
    if [item.name for item in loaded.values()] != ordered_names:
        raise PreviewValidationError(("preview.content_files order is not canonical",))
    return tuple(loaded[name] for name in ordered_names)


def _rejected(
    operation: str, diagnostics: tuple[AuthoringDiagnostic, ...]
) -> AuthoringResult[PreviewBuild]:
    return AuthoringResult(
        format_version=1,
        operation=operation,
        status=AuthoringStatus.REJECTED,
        artifact=None,
        diagnostics=diagnostics,
        exit_code=1,
    )


def _diagnostic(
    artifact_id: str,
    code: str,
    pointer: str,
    message: str,
    remediation: str,
) -> AuthoringDiagnostic:
    return AuthoringDiagnostic(
        stage=AuthoringStage.PREVIEW,
        code=code,
        severity=DiagnosticSeverity.ERROR,
        artifact_id=artifact_id,
        json_pointer=pointer,
        source_span=None,
        message=message,
        remediation=remediation,
    )


def normalized_id(project: object) -> str:
    if type(project) is not GameProject:
        return "project"
    return diagnostic_artifact_id(project.project_id)


def _object(value: object, location: str) -> dict[str, object]:
    if type(value) is not dict:
        raise PreviewValidationError((f"{location} must be an object",))
    return cast(dict[str, object], value)


def _exact_keys(data: dict[str, object], expected: set[str], location: str) -> None:
    if set(data) != expected:
        raise PreviewValidationError((f"{location} fields are invalid",))


def _text(value: object, location: str, *, maximum: int) -> str:
    if type(value) is not str or not value.strip() or len(value) > maximum:
        raise PreviewValidationError((f"{location} must be a bounded non-blank string",))
    return value


def _stable_id(value: object, location: str, *, maximum: int = 64) -> str:
    text = _text(value, location, maximum=maximum)
    if text[0] not in "abcdefghijklmnopqrstuvwxyz" or not all(
        character in "abcdefghijklmnopqrstuvwxyz0123456789_" for character in text
    ):
        raise PreviewValidationError((f"{location} must be a stable lowercase ID",))
    return text


def _sha256(value: object, location: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise PreviewValidationError((f"{location} must be a lowercase SHA-256",))
    return value


def _integer(value: object, location: str) -> int:
    if type(value) is not int:
        raise PreviewValidationError((f"{location} must be an integer",))
    return value
