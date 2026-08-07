"""Canonical sealed GamePackage v2 and evidence-manifest identity contracts."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
import re
import tempfile
from typing import cast

from lore2mud import __version__
from lore2mud._bounded_json import DEFAULT_JSON_READ_LIMITS, parse_bounded_json
from lore2mud.authoring.anchors import (
    AnchorMigration,
    AnchorMigrationReport,
    AnchorValidationError,
    StoryAnchor,
    anchor_migration_report_bytes,
    anchor_migration_report_to_document,
    load_anchor_migration_document,
    load_anchor_migration_report_document,
    load_story_anchor_document,
    story_anchor_set_sha256,
    validate_anchor_migrations,
    validate_anchor_set,
)
from lore2mud.authoring.contracts import (
    CapabilitySimulationReport,
    CanonicalContentFile,
    GameProject,
    SimulationReport,
    WorkspaceMetadataEntry,
)
from lore2mud.authoring.provenance import (
    AdaptationMode,
    PublicProvenanceAliases,
    ProvenanceManifest,
    ProvenanceValidationError,
    is_opaque_public_id,
    is_public_safe_text,
    load_provenance_manifest_document,
    provenance_manifest_to_document,
    public_provenance_manifest_sha256,
    public_provenance_manifest,
    public_provenance_aliases,
    public_provenance_manifest_to_document,
    validate_provenance_manifest,
)
from lore2mud.authoring.project import (
    REQUIRED_V1_CONTENT_FILES,
    V1_CONTENT_FILE_ORDER,
    load_project_document,
    validate_project,
)
from lore2mud.authoring.serialization import (
    canonical_json_bytes,
    canonical_content_file_to_document,
    normalize_bounded_json_document,
    sha256_bytes,
)
from lore2mud.content.loader import ContentValidationError, load_content_pack


_STABLE_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_PUBLIC_SAFE_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN_KEYS = {
    "python",
    "code",
    "eval",
    "exec",
    "script",
    "import_path",
    "module",
    "module_path",
    "plugin",
    "submodule",
    "native_module",
    "runtime",
    "loader",
    "dynamic",
    "git_submodule",
    "wasm",
    "binary",
    "library",
    "shell",
    "process",
    "executable",
    "network",
    "filesystem",
    "webhook",
    "fetch",
    "request",
    "environment",
    "env",
    "command",
    "private",
    "secret",
    "raw_text",
    "source_hash",
    "file_path",
    "source_path",
}
_FORBIDDEN_KEY_TOKENS = frozenset(
    {
        "python",
        "code",
        "eval",
        "exec",
        "script",
        "import",
        "module",
        "plugin",
        "submodule",
        "native",
        "runtime",
        "loader",
        "dynamic",
        "git",
        "wasm",
        "binary",
        "library",
        "shell",
        "process",
        "executable",
        "network",
        "filesystem",
        "webhook",
        "fetch",
        "request",
        "environment",
        "env",
        "endpoint",
        "socket",
        "command",
        "host",
        "url",
        "uri",
        "path",
        "private",
        "secret",
    }
)
_FORBIDDEN_COMPOUND_KEY_PARTS = _FORBIDDEN_KEY_TOKENS | frozenset(
    {
        "file",
        "source",
        "raw",
        "hash",
        "text",
        "system",
        "http",
        "https",
        "ftp",
        "ssh",
        "mailto",
        "data",
        "javascript",
        "urn",
        "about",
        "blob",
        "tel",
        "web",
        "hook",
        "io",
    }
)
_FORBIDDEN_COMPOUND_KEY_PATTERN = "|".join(
    sorted(_FORBIDDEN_COMPOUND_KEY_PARTS, key=lambda value: (-len(value), value))
)
_FORBIDDEN_COMPOUND_KEY_RE = re.compile(
    rf"^(?:{_FORBIDDEN_COMPOUND_KEY_PATTERN})_*(?:{_FORBIDDEN_COMPOUND_KEY_PATTERN})"
    rf"(?:_*(?:{_FORBIDDEN_COMPOUND_KEY_PATTERN}))*$"
)
_MAX_COLLECTION = 4096
PACKAGE_FORMAT_VERSION = 2
EVIDENCE_FORMAT_VERSION = 1
PROVENANCE_EVIDENCE_KIND = "public_provenance_manifest_v1"
SIMULATION_EVIDENCE_KIND = "simulation_report_v1"
CAPABILITY_SIMULATION_EVIDENCE_KIND = "capability_simulation_report_v1"
_PROVENANCE_EVIDENCE_ID = "evidence_provenance_projection"
_SIMULATION_EVIDENCE_PREFIX = "evidence_simulation_"
_CAPABILITY_EVIDENCE_PREFIX = "evidence_capability_"
_EVIDENCE_KINDS = frozenset(
    {
        PROVENANCE_EVIDENCE_KIND,
        SIMULATION_EVIDENCE_KIND,
        CAPABILITY_SIMULATION_EVIDENCE_KIND,
    }
)


class SealMode(str, Enum):
    """Whether a candidate starts a lineage or advances a sealed predecessor."""

    INITIAL = "initial"
    INCREMENTAL = "incremental"


@dataclass(frozen=True, slots=True)
class PackageElement:
    package_element_id: str
    project_element_id: str
    element_kind: str
    data: object

    def __post_init__(self) -> None:
        try:
            normalized = normalize_bounded_json_document(_mutable_package_data(self.data))
        except (RecursionError, TypeError, ValueError):
            return
        object.__setattr__(self, "data", _freeze_package_data(normalized))


@dataclass(frozen=True, slots=True, eq=False)
class _FrozenJsonObject(Mapping[str, object]):
    """An immutable JSON object used inside sealed package values."""

    _items: tuple[tuple[str, object], ...]

    def __getitem__(self, key: str) -> object:
        for item_key, item_value in self._items:
            if item_key == key:
                return item_value
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (key for key, _ in self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Mapping):
            return False
        return _mutable_package_data(self) == _mutable_package_data(other)


def _freeze_package_data(value: object) -> object:
    if type(value) is dict:
        mapping = cast(dict[str, object], value)
        return _FrozenJsonObject(
            tuple((key, _freeze_package_data(item)) for key, item in sorted(mapping.items()))
        )
    if type(value) is list:
        return tuple(_freeze_package_data(item) for item in cast(list[object], value))
    return value


def _mutable_package_data(value: object) -> object:
    if type(value) is _FrozenJsonObject:
        return {
            key: _mutable_package_data(item)
            for key, item in cast(_FrozenJsonObject, value)._items
        }
    if type(value) is tuple:
        return [_mutable_package_data(item) for item in cast(tuple[object, ...], value)]
    if isinstance(value, Mapping):
        return {key: _mutable_package_data(item) for key, item in value.items()}
    return value


@dataclass(frozen=True, slots=True)
class EvidenceEntry:
    evidence_id: str
    kind: str
    artifact_sha256: str
    admitted: bool = True


@dataclass(frozen=True, slots=True)
class EvidenceManifest:
    format_version: int
    candidate_input_sha256: str
    provenance_manifest_sha256: str
    entries: tuple[EvidenceEntry, ...]
    candidate_id: str
    manifest_sha256: str
    presentation_metadata: tuple[WorkspaceMetadataEntry, ...] = ()
    identity_scope: str = "sealed_evidence_manifest"


@dataclass(frozen=True, slots=True)
class GamePackageV2:
    format_version: int
    candidate_id: str
    project_id: str
    engine_version: str
    content_files: tuple[CanonicalContentFile, ...]
    capability_requirement_ids: tuple[str, ...]
    elements: tuple[PackageElement, ...]
    anchors: tuple[StoryAnchor, ...]
    seal_mode: SealMode
    predecessor_candidate_id: str | None
    predecessor_package_sha256: str | None
    predecessor_anchors_sha256: str | None
    evidence_manifest_sha256: str
    package_sha256: str
    sealed: bool = True
    distributable: bool = False
    release_evidence: bool = False
    presentation_metadata: tuple[WorkspaceMetadataEntry, ...] = ()
    kind: str = "game_package_v2"
    anchor_migration_sha256: str = "0" * 64


@dataclass(frozen=True, slots=True)
class SealCandidate:
    format_version: int
    candidate_id: str
    package: GamePackageV2
    evidence_manifest: EvidenceManifest
    seal_input_sha256: str
    provenance_manifest: ProvenanceManifest | None = None
    anchor_migration_report: AnchorMigrationReport | None = None
    anchor_migration_sha256: str = "0" * 64
    predecessor_package: GamePackageV2 | None = None


@dataclass(frozen=True, slots=True)
class SealRequest:
    """Transport-neutral input for one sealing attempt."""

    project: GameProject
    provenance: ProvenanceManifest
    elements: tuple[PackageElement, ...]
    anchors: tuple[StoryAnchor, ...]
    simulation_reports: tuple[SimulationReport | CapabilitySimulationReport, ...]
    seal_mode: SealMode
    engine_version: str = __version__
    predecessor_package: GamePackageV2 | None = None
    anchor_migrations: tuple[AnchorMigration, ...] = ()
    presentation_metadata: tuple[WorkspaceMetadataEntry, ...] = ()


class PackageValidationError(ValueError):
    """Raised when package/evidence data cannot be safely sealed or loaded."""

    def __init__(self, issues: Sequence[str]) -> None:
        self.issues = tuple(issues)
        super().__init__("; ".join(self.issues))


def package_element_to_document(value: PackageElement) -> dict[str, object]:
    if type(value) is not PackageElement:
        raise PackageValidationError(("package element must be a typed value",))
    if not is_opaque_public_id(value.package_element_id) or not is_opaque_public_id(
        value.project_element_id
    ):
        raise PackageValidationError(("package element IDs must be opaque public-safe IDs",))
    _validate_public_text(value.element_kind, "package element kind")
    mutable_data = _mutable_package_data(value.data)
    _validate_runtime_data(mutable_data)
    return {
        "package_element_id": value.package_element_id,
        "project_element_id": value.project_element_id,
        "element_kind": value.element_kind,
        "data": normalize_bounded_json_document(mutable_data),
    }


def evidence_entry_to_document(value: EvidenceEntry) -> dict[str, object]:
    if type(value) is not EvidenceEntry:
        raise PackageValidationError(("evidence entry must be a typed value",))
    if not is_opaque_public_id(value.evidence_id):
        raise PackageValidationError(("evidence IDs must be opaque public-safe IDs",))
    if value.kind not in _EVIDENCE_KINDS:
        raise PackageValidationError(("evidence kind is not admitted by the seal contract",))
    if not _SHA256_RE.fullmatch(value.artifact_sha256):
        raise PackageValidationError(("evidence artifacts must use SHA-256",))
    if value.admitted is not True:
        raise PackageValidationError(("sealed evidence must be admitted",))
    expected_id = _expected_evidence_id(value.kind, value.artifact_sha256)
    if value.evidence_id != expected_id:
        raise PackageValidationError(("evidence ID is not bound to its admitted artifact",))
    return {
        "evidence_id": value.evidence_id,
        "kind": value.kind,
        "artifact_sha256": value.artifact_sha256,
        "admitted": value.admitted,
    }


def _expected_evidence_id(kind: str, artifact_sha256: str) -> str:
    if kind == PROVENANCE_EVIDENCE_KIND:
        return _PROVENANCE_EVIDENCE_ID
    if kind == SIMULATION_EVIDENCE_KIND:
        return f"{_SIMULATION_EVIDENCE_PREFIX}{artifact_sha256[:16]}"
    if kind == CAPABILITY_SIMULATION_EVIDENCE_KIND:
        return f"{_CAPABILITY_EVIDENCE_PREFIX}{artifact_sha256[:16]}"
    return "invalid_evidence_id"


def evidence_manifest_semantic_to_document(
    value: EvidenceManifest,
) -> dict[str, object]:
    return {
        "format_version": value.format_version,
        "identity_scope": value.identity_scope,
        "candidate_input_sha256": value.candidate_input_sha256,
        "provenance_manifest_sha256": value.provenance_manifest_sha256,
        "entries": [
            evidence_entry_to_document(item)
            for item in sorted(value.entries, key=lambda item: item.evidence_id)
        ],
    }


def evidence_manifest_to_document(value: EvidenceManifest) -> dict[str, object]:
    return {
        **evidence_manifest_semantic_to_document(value),
        "candidate_id": value.candidate_id,
        "manifest_sha256": value.manifest_sha256,
        "presentation_metadata": [
            {"key": item.key, "value": item.value} for item in value.presentation_metadata
        ],
    }


def package_input_to_document(value: GamePackageV2) -> dict[str, object]:
    """Return the package identity input before the evidence sidecar is bound."""
    return {
        "format_version": value.format_version,
        "kind": value.kind,
        "project_id": value.project_id,
        "engine_version": value.engine_version,
        "content_files": [
            canonical_content_file_to_document(item)
            for item in sorted(
                value.content_files,
                key=lambda item: (V1_CONTENT_FILE_ORDER.index(item.name), item.name),
            )
        ],
        "capability_requirement_ids": sorted(value.capability_requirement_ids),
        "elements": [
            package_element_to_document(item)
            for item in sorted(value.elements, key=lambda item: item.package_element_id)
        ],
        "anchors": [
            {
                "anchor_id": item.anchor_id,
                "kind": item.kind.value,
                "project_element_id": item.project_element_id,
                "package_element_id": item.package_element_id,
            }
            for item in sorted(value.anchors, key=lambda item: item.anchor_id)
        ],
        "seal_mode": value.seal_mode.value,
        "predecessor_candidate_id": value.predecessor_candidate_id,
        "predecessor_package_sha256": value.predecessor_package_sha256,
        "predecessor_anchors_sha256": value.predecessor_anchors_sha256,
        "anchor_migration_sha256": value.anchor_migration_sha256,
        "sealed": value.sealed,
        "distributable": value.distributable,
        "release_evidence": value.release_evidence,
    }


def package_semantic_to_document(value: GamePackageV2) -> dict[str, object]:
    return {
        **package_input_to_document(value),
        "evidence_manifest_sha256": value.evidence_manifest_sha256,
    }


def game_package_to_document(value: GamePackageV2) -> dict[str, object]:
    return {
        **package_semantic_to_document(value),
        "candidate_id": value.candidate_id,
        "package_sha256": value.package_sha256,
        "presentation_metadata": [
            {"key": item.key, "value": item.value} for item in value.presentation_metadata
        ],
    }


def seal_candidate_to_document(value: SealCandidate) -> dict[str, object]:
    document: dict[str, object] = {
        "format_version": value.format_version,
        "candidate_id": value.candidate_id,
        "package": game_package_to_document(value.package),
        "evidence_manifest": evidence_manifest_to_document(value.evidence_manifest),
        "seal_input_sha256": value.seal_input_sha256,
        "anchor_migration_sha256": value.anchor_migration_sha256,
        "anchor_migration_report": anchor_migration_report_to_document(
            value.anchor_migration_report
            if value.anchor_migration_report is not None
            else AnchorMigrationReport(1, (), ())
        ),
        "predecessor_package": (
            None
            if value.predecessor_package is None
            else game_package_to_document(value.predecessor_package)
        ),
    }
    if value.provenance_manifest is not None:
        document["provenance_manifest"] = public_provenance_manifest_to_document(
            value.provenance_manifest
        )
    return document


def seal_request_to_document(value: SealRequest) -> dict[str, object]:
    from lore2mud.authoring.serialization import (
        capability_simulation_report_to_document,
        project_to_document,
        simulation_report_to_document,
    )

    report_documents: list[dict[str, object]] = []
    for item in value.simulation_reports:
        if isinstance(item, CapabilitySimulationReport):
            report_documents.append(capability_simulation_report_to_document(item))
        else:
            report_documents.append(simulation_report_to_document(item))

    return {
        "project": project_to_document(value.project),
        "provenance": provenance_manifest_to_document(value.provenance),
        "elements": [package_element_to_document(item) for item in value.elements],
        "anchors": [
            {
                "anchor_id": item.anchor_id,
                "kind": item.kind.value,
                "project_element_id": item.project_element_id,
                "package_element_id": item.package_element_id,
            }
            for item in value.anchors
        ],
        "simulation_reports": report_documents,
        "seal_mode": value.seal_mode.value,
        "engine_version": value.engine_version,
        "predecessor_package": (
            None
            if value.predecessor_package is None
            else game_package_to_document(value.predecessor_package)
        ),
        "anchor_migrations": [
            {
                "migration_id": item.migration_id,
                "from_anchor_id": item.from_anchor_id,
                "to_anchor_ids": list(item.to_anchor_ids),
                "decision_id": item.decision_id,
            }
            for item in value.anchor_migrations
        ],
        "presentation_metadata": [
            {"key": item.key, "value": item.value} for item in value.presentation_metadata
        ],
    }


def canonical_package_input_bytes(value: GamePackageV2) -> bytes:
    return canonical_json_bytes(package_input_to_document(value))


def canonical_game_package_bytes(value: GamePackageV2) -> bytes:
    """Canonical semantic bytes; presentation metadata and identity fields are excluded."""
    return canonical_json_bytes(package_semantic_to_document(value))


def package_input_sha256(value: GamePackageV2) -> str:
    return sha256_bytes(canonical_package_input_bytes(value))


def game_package_sha256(value: GamePackageV2) -> str:
    return sha256_bytes(canonical_game_package_bytes(value))


def game_package_candidate_id(value: GamePackageV2) -> str:
    return f"package_{game_package_sha256(value)[:24]}"


def canonical_evidence_manifest_bytes(value: EvidenceManifest) -> bytes:
    return canonical_json_bytes(evidence_manifest_semantic_to_document(value))


def evidence_manifest_sha256(value: EvidenceManifest) -> str:
    return sha256_bytes(canonical_evidence_manifest_bytes(value))


def evidence_manifest_candidate_id(value: EvidenceManifest) -> str:
    return f"evidence_{evidence_manifest_sha256(value)[:24]}"


def _validate_provenance_evidence_binding(
    provenance_sha256: str,
    entries: Sequence[EvidenceEntry],
) -> None:
    provenance_entry = next(
        (item for item in entries if item.kind == PROVENANCE_EVIDENCE_KIND),
        None,
    )
    if (
        provenance_entry is not None
        and provenance_entry.artifact_sha256 != provenance_sha256
    ):
        raise PackageValidationError(
            ("provenance evidence must match provenance_manifest_sha256",)
        )


def build_evidence_manifest(
    *,
    candidate_input_sha256: str,
    provenance_sha256: str,
    entries: Sequence[EvidenceEntry],
    presentation_metadata: Sequence[WorkspaceMetadataEntry] = (),
) -> EvidenceManifest:
    normalized_entries = _validate_evidence_entries(entries)
    if not _SHA256_RE.fullmatch(candidate_input_sha256):
        raise PackageValidationError(("candidate_input_sha256 must be a SHA-256 digest",))
    if not _SHA256_RE.fullmatch(provenance_sha256):
        raise PackageValidationError(("provenance_manifest_sha256 must be a SHA-256 digest",))
    _validate_provenance_evidence_binding(provenance_sha256, normalized_entries)
    metadata = _validate_presentation_metadata(presentation_metadata)
    without_identity = EvidenceManifest(
        format_version=EVIDENCE_FORMAT_VERSION,
        candidate_input_sha256=candidate_input_sha256,
        provenance_manifest_sha256=provenance_sha256,
        entries=normalized_entries,
        candidate_id="evidence_pending",
        manifest_sha256="0" * 64,
        presentation_metadata=metadata,
    )
    digest = evidence_manifest_sha256(without_identity)
    return EvidenceManifest(
        format_version=without_identity.format_version,
        candidate_input_sha256=without_identity.candidate_input_sha256,
        provenance_manifest_sha256=without_identity.provenance_manifest_sha256,
        entries=without_identity.entries,
        candidate_id=f"evidence_{digest[:24]}",
        manifest_sha256=digest,
        presentation_metadata=without_identity.presentation_metadata,
        identity_scope=without_identity.identity_scope,
    )


def _derive_evidence_entries(
    project: GameProject,
    provenance: ProvenanceManifest,
    reports: Sequence[SimulationReport | CapabilitySimulationReport],
) -> tuple[EvidenceEntry, ...]:
    """Admit only replay-verified reports and a recomputable provenance projection."""
    if type(reports) not in {tuple, list} or not reports:
        raise PackageValidationError(
            ("sealed packages require at least one simulation evidence report",)
        )
    if len(reports) > _MAX_COLLECTION:
        raise PackageValidationError(
            (f"simulation evidence reports must contain at most {_MAX_COLLECTION} entries",)
        )
    from lore2mud.authoring.simulation import (
        SimulationValidationError,
        replay_report,
        validate_simulation_report,
    )

    entries = [
        EvidenceEntry(
            _PROVENANCE_EVIDENCE_ID,
            PROVENANCE_EVIDENCE_KIND,
            public_provenance_manifest_sha256(provenance),
        )
    ]
    seen_fingerprints: set[str] = set()
    for report in reports:
        if type(report) not in {SimulationReport, CapabilitySimulationReport}:
            raise PackageValidationError(("simulation evidence reports must be typed values",))
        try:
            normalized = validate_simulation_report(report)
        except (SimulationValidationError, AttributeError, TypeError, ValueError) as exc:
            raise PackageValidationError(("simulation evidence report is invalid",)) from exc
        report_project_id = normalized.project_id
        if report_project_id != project.project_id:
            raise PackageValidationError(("simulation evidence report belongs to another project",))
        if isinstance(normalized, SimulationReport):
            player_name = normalized.player_name
        else:
            player_name = normalized.base_report.player_name
        if not is_public_safe_text(player_name):
            raise PackageValidationError(("simulation evidence report is not public-safe",))
        try:
            replayed = replay_report(project, normalized)
        except (AttributeError, RecursionError, TypeError, ValueError) as exc:
            raise PackageValidationError(
                ("simulation evidence report could not be replayed",)
            ) from exc
        if not replayed.ok or replayed.artifact != normalized:
            raise PackageValidationError(("simulation evidence report is not replay-verified",))
        fingerprint = normalized.fingerprint
        if not _SHA256_RE.fullmatch(fingerprint) or fingerprint in seen_fingerprints:
            raise PackageValidationError(
                ("simulation evidence report fingerprints must be unique",)
            )
        seen_fingerprints.add(fingerprint)
        kind = (
            SIMULATION_EVIDENCE_KIND
            if type(normalized) is SimulationReport
            else CAPABILITY_SIMULATION_EVIDENCE_KIND
        )
        entries.append(EvidenceEntry(_expected_evidence_id(kind, fingerprint), kind, fingerprint))
    return tuple(entries)


def seal_game_package(
    project: GameProject,
    provenance: ProvenanceManifest,
    *,
    elements: Sequence[PackageElement],
    anchors: Sequence[StoryAnchor],
    simulation_reports: Sequence[SimulationReport | CapabilitySimulationReport],
    seal_mode: SealMode,
    engine_version: str = __version__,
    predecessor_package: GamePackageV2 | None = None,
    anchor_migrations: Sequence[AnchorMigration] = (),
    presentation_metadata: Sequence[WorkspaceMetadataEntry] = (),
) -> SealCandidate:
    """Build one immutable sealed candidate; an existing package is never mutated."""
    try:
        normalized_project = validate_project(project)
    except Exception as exc:
        raise PackageValidationError(("GameProject v1 is invalid",)) from exc
    if not is_opaque_public_id(normalized_project.project_id):
        raise PackageValidationError(("GameProject project_id must be opaque public-safe",))
    if any(
        not is_opaque_public_id(item)
        for item in normalized_project.blueprint.capability_requirement_ids
    ):
        raise PackageValidationError(("capability requirement IDs must be opaque public-safe",))
    _validate_v1_content_files(normalized_project.content_files)
    try:
        normalized_provenance = validate_provenance_manifest(provenance)
    except ProvenanceValidationError as exc:
        raise PackageValidationError(exc.issues) from exc
    if normalized_provenance.mode is not AdaptationMode.SEALED:
        raise PackageValidationError(("sealing requires a sealed provenance manifest",))
    if type(engine_version) is not str or engine_version != __version__:
        raise PackageValidationError(("engine_version is not supported",))
    normalized_elements = _validate_package_elements(elements)
    normalized_anchors = validate_anchor_set(anchors)
    _validate_project_trace_bindings(normalized_project, normalized_provenance)
    _validate_element_bindings(normalized_provenance, normalized_elements)
    _validate_anchor_elements(normalized_anchors, normalized_elements)
    aliases = public_provenance_aliases(normalized_provenance)
    public_provenance = public_provenance_manifest(normalized_provenance)
    public_elements = _public_package_elements(normalized_elements, aliases)
    public_anchors = _public_anchor_set(normalized_anchors, aliases)
    _validate_element_bindings(public_provenance, public_elements)
    _validate_anchor_elements(public_anchors, public_elements)
    if type(seal_mode) is not SealMode:
        raise PackageValidationError(("seal mode is invalid",))
    normalized_predecessor: GamePackageV2 | None = None
    if seal_mode is SealMode.INITIAL:
        if predecessor_package is not None or anchor_migrations:
            raise PackageValidationError(
                ("initial seal lineage cannot include a predecessor or migrations",)
            )
        migration_report = AnchorMigrationReport(1, (), ())
        predecessor_candidate_id = None
        predecessor_package_sha = None
        predecessor_anchors_sha = None
    else:
        if type(predecessor_package) is not GamePackageV2:
            raise PackageValidationError(
                ("incremental seal lineage requires a predecessor package",)
            )
        try:
            normalized_predecessor = validate_game_package(predecessor_package)
        except PackageValidationError as exc:
            raise PackageValidationError(
                ("incremental seal predecessor package is invalid",)
            ) from exc
        if normalized_predecessor.project_id != normalized_project.project_id:
            raise PackageValidationError(
                ("incremental seal predecessor belongs to another project lineage",)
            )
        migration_report = validate_anchor_migrations(
            normalized_predecessor.anchors,
            public_anchors,
            anchor_migrations,
        )
        predecessor_candidate_id = normalized_predecessor.candidate_id
        predecessor_package_sha = normalized_predecessor.package_sha256
        predecessor_anchors_sha = story_anchor_set_sha256(normalized_predecessor.anchors)
    _validate_anchor_decisions(normalized_provenance, migration_report.migrations)
    decision_aliases = aliases.decision_ids
    public_migration_report = replace(
        migration_report,
        migrations=tuple(
            replace(
                migration,
                decision_id=decision_aliases.get(migration.decision_id, migration.decision_id),
            )
            for migration in migration_report.migrations
        ),
    )
    anchor_migration_digest = sha256_bytes(anchor_migration_report_bytes(public_migration_report))
    metadata = _validate_presentation_metadata(presentation_metadata)
    draft = GamePackageV2(
        format_version=PACKAGE_FORMAT_VERSION,
        candidate_id="package_pending",
        project_id=normalized_project.project_id,
        engine_version=engine_version,
        content_files=normalized_project.content_files,
        capability_requirement_ids=normalized_project.blueprint.capability_requirement_ids,
        elements=public_elements,
        anchors=public_anchors,
        seal_mode=seal_mode,
        predecessor_candidate_id=predecessor_candidate_id,
        predecessor_package_sha256=predecessor_package_sha,
        predecessor_anchors_sha256=predecessor_anchors_sha,
        evidence_manifest_sha256="0" * 64,
        package_sha256="0" * 64,
        presentation_metadata=metadata,
        anchor_migration_sha256=anchor_migration_digest,
    )
    base_digest = package_input_sha256(draft)
    public_provenance_digest = public_provenance_manifest_sha256(public_provenance)
    evidence_entries = _derive_evidence_entries(
        normalized_project,
        public_provenance,
        simulation_reports,
    )
    evidence = build_evidence_manifest(
        candidate_input_sha256=base_digest,
        provenance_sha256=public_provenance_digest,
        entries=evidence_entries,
        presentation_metadata=metadata,
    )
    package_without_identity = GamePackageV2(
        format_version=draft.format_version,
        candidate_id="package_pending",
        project_id=draft.project_id,
        engine_version=draft.engine_version,
        content_files=draft.content_files,
        capability_requirement_ids=draft.capability_requirement_ids,
        elements=draft.elements,
        anchors=draft.anchors,
        seal_mode=draft.seal_mode,
        predecessor_candidate_id=draft.predecessor_candidate_id,
        predecessor_package_sha256=draft.predecessor_package_sha256,
        predecessor_anchors_sha256=draft.predecessor_anchors_sha256,
        evidence_manifest_sha256=evidence.manifest_sha256,
        package_sha256="0" * 64,
        sealed=True,
        distributable=False,
        release_evidence=False,
        presentation_metadata=draft.presentation_metadata,
        anchor_migration_sha256=anchor_migration_digest,
    )
    package_digest = game_package_sha256(package_without_identity)
    package = GamePackageV2(
        format_version=package_without_identity.format_version,
        candidate_id=f"package_{package_digest[:24]}",
        project_id=package_without_identity.project_id,
        engine_version=package_without_identity.engine_version,
        content_files=package_without_identity.content_files,
        capability_requirement_ids=package_without_identity.capability_requirement_ids,
        elements=package_without_identity.elements,
        anchors=package_without_identity.anchors,
        seal_mode=package_without_identity.seal_mode,
        predecessor_candidate_id=package_without_identity.predecessor_candidate_id,
        predecessor_package_sha256=package_without_identity.predecessor_package_sha256,
        predecessor_anchors_sha256=package_without_identity.predecessor_anchors_sha256,
        evidence_manifest_sha256=package_without_identity.evidence_manifest_sha256,
        package_sha256=package_digest,
        sealed=True,
        distributable=False,
        release_evidence=False,
        presentation_metadata=package_without_identity.presentation_metadata,
        anchor_migration_sha256=anchor_migration_digest,
    )
    seal_input = {
        "package_sha256": package_digest,
        "evidence_manifest_sha256": evidence.manifest_sha256,
        "provenance_manifest_sha256": public_provenance_digest,
        "anchor_migration_sha256": anchor_migration_digest,
        "seal_mode": seal_mode.value,
        "predecessor_package_sha256": predecessor_package_sha,
    }
    seal_input_sha = sha256_bytes(canonical_json_bytes(seal_input))
    return SealCandidate(
        format_version=1,
        candidate_id=package.candidate_id,
        package=package,
        evidence_manifest=evidence,
        seal_input_sha256=seal_input_sha,
        provenance_manifest=public_provenance,
        anchor_migration_report=public_migration_report,
        anchor_migration_sha256=anchor_migration_digest,
        predecessor_package=normalized_predecessor,
    )


def reseal_game_package(value: GamePackageV2) -> None:
    """Reject an attempted in-place reseal; changes require a new candidate."""
    if type(value) is GamePackageV2 and value.sealed:
        raise PackageValidationError(
            ("sealed packages are immutable; create a new candidate for every change",)
        )
    raise PackageValidationError(("only a sealed GamePackage v2 can be checked for resealing",))


def validate_game_package(value: GamePackageV2) -> GamePackageV2:
    if type(value) is not GamePackageV2:
        raise PackageValidationError(("value must be a typed GamePackage v2",))
    try:
        normalized = normalize_bounded_json_document(game_package_to_document(value))
    except (AttributeError, TypeError, ValueError) as exc:
        raise PackageValidationError(("typed GamePackage v2 could not be normalized",)) from exc
    return load_game_package_document(normalized)


def load_game_package_document(document: object) -> GamePackageV2:
    issues: list[str] = []
    data = _mapping(document, "package", issues)
    _keys(
        data,
        {
            "format_version",
            "kind",
            "candidate_id",
            "project_id",
            "engine_version",
            "content_files",
            "capability_requirement_ids",
            "elements",
            "anchors",
            "seal_mode",
            "predecessor_candidate_id",
            "predecessor_package_sha256",
            "predecessor_anchors_sha256",
            "evidence_manifest_sha256",
            "package_sha256",
            "sealed",
            "distributable",
            "release_evidence",
            "presentation_metadata",
            "anchor_migration_sha256",
        },
        "package",
        issues,
    )
    if (
        _integer(data.get("format_version"), "package.format_version", issues)
        != PACKAGE_FORMAT_VERSION
    ):
        issues.append("package.format_version must be 2")
    if data.get("kind") != "game_package_v2":
        issues.append("package.kind must be game_package_v2")
    package = GamePackageV2(
        format_version=PACKAGE_FORMAT_VERSION,
        candidate_id=_stable_id(data.get("candidate_id"), "package.candidate_id", issues),
        project_id=_stable_id(data.get("project_id"), "package.project_id", issues),
        engine_version=_text(data.get("engine_version"), "package.engine_version", issues),
        content_files=_load_content_files(data.get("content_files"), issues),
        capability_requirement_ids=_stable_id_set(
            data.get("capability_requirement_ids"),
            "package.capability_requirement_ids",
            issues,
        ),
        elements=_load_package_elements(data.get("elements"), issues),
        anchors=_load_anchors(data.get("anchors"), issues),
        seal_mode=_seal_mode(data.get("seal_mode"), "package.seal_mode", issues),
        predecessor_candidate_id=_optional_stable_id(
            data.get("predecessor_candidate_id"), "package.predecessor_candidate_id", issues
        ),
        predecessor_package_sha256=_optional_sha256(
            data.get("predecessor_package_sha256"),
            "package.predecessor_package_sha256",
            issues,
        ),
        predecessor_anchors_sha256=_optional_sha256(
            data.get("predecessor_anchors_sha256"),
            "package.predecessor_anchors_sha256",
            issues,
        ),
        evidence_manifest_sha256=_sha256(
            data.get("evidence_manifest_sha256"),
            "package.evidence_manifest_sha256",
            issues,
        ),
        package_sha256=_sha256(data.get("package_sha256"), "package.package_sha256", issues),
        sealed=_boolean(data.get("sealed"), "package.sealed", issues),
        distributable=_boolean(data.get("distributable"), "package.distributable", issues),
        release_evidence=_boolean(
            data.get("release_evidence"), "package.release_evidence", issues
        ),
        presentation_metadata=_load_presentation_metadata(
            data.get("presentation_metadata"), "package.presentation_metadata", issues
        ),
        anchor_migration_sha256=_sha256(
            data.get("anchor_migration_sha256"),
            "package.anchor_migration_sha256",
            issues,
        ),
    )
    if (
        package.sealed is not True
        or package.distributable is not False
        or package.release_evidence is not False
    ):
        issues.append(
            "GamePackage v2 must be sealed, non-distributable, and non-release evidence"
        )
    if package.seal_mode is SealMode.INITIAL and any(
        value is not None
        for value in (
            package.predecessor_candidate_id,
            package.predecessor_package_sha256,
            package.predecessor_anchors_sha256,
        )
    ):
        issues.append("initial package lineage cannot contain predecessor identity")
    if package.seal_mode is SealMode.INCREMENTAL and any(
        value is None
        for value in (
            package.predecessor_candidate_id,
            package.predecessor_package_sha256,
            package.predecessor_anchors_sha256,
        )
    ):
        issues.append("incremental package lineage requires predecessor identity")
    if package.engine_version != __version__:
        issues.append("package.engine_version is not supported")
    if not issues:
        try:
            _validate_v1_content_files(package.content_files)
            _validate_anchor_elements(package.anchors, package.elements)
        except PackageValidationError as exc:
            issues.extend(exc.issues)
    if not issues:
        if package.package_sha256 != game_package_sha256(package):
            issues.append("package.package_sha256 does not match canonical semantic bytes")
        if package.candidate_id != game_package_candidate_id(package):
            issues.append("package.candidate_id does not match canonical semantic bytes")
    if issues:
        raise PackageValidationError(issues)
    return package


def load_evidence_manifest_document(document: object) -> EvidenceManifest:
    issues: list[str] = []
    data = _mapping(document, "evidence_manifest", issues)
    _keys(
        data,
        {
            "format_version",
            "identity_scope",
            "candidate_input_sha256",
            "provenance_manifest_sha256",
            "entries",
            "candidate_id",
            "manifest_sha256",
            "presentation_metadata",
        },
        "evidence_manifest",
        issues,
    )
    if _integer(data.get("format_version"), "evidence_manifest.format_version", issues) != 1:
        issues.append("evidence_manifest.format_version must be 1")
    if data.get("identity_scope") != "sealed_evidence_manifest":
        issues.append("evidence_manifest.identity_scope is invalid")
    entries = _load_evidence_entries(data.get("entries"), issues)
    value = EvidenceManifest(
        format_version=1,
        candidate_input_sha256=_sha256(
            data.get("candidate_input_sha256"),
            "evidence_manifest.candidate_input_sha256",
            issues,
        ),
        provenance_manifest_sha256=_sha256(
            data.get("provenance_manifest_sha256"),
            "evidence_manifest.provenance_manifest_sha256",
            issues,
        ),
        entries=entries,
        candidate_id=_stable_id(data.get("candidate_id"), "evidence_manifest.candidate_id", issues),
        manifest_sha256=_sha256(
            data.get("manifest_sha256"), "evidence_manifest.manifest_sha256", issues
        ),
        presentation_metadata=_load_presentation_metadata(
            data.get("presentation_metadata"),
            "evidence_manifest.presentation_metadata",
            issues,
        ),
    )
    try:
        _validate_provenance_evidence_binding(
            value.provenance_manifest_sha256,
            value.entries,
        )
    except PackageValidationError as exc:
        issues.extend(exc.issues)
    if value.manifest_sha256 != evidence_manifest_sha256(value):
        issues.append("evidence manifest hash does not match canonical bytes")
    if value.candidate_id != evidence_manifest_candidate_id(value):
        issues.append("evidence manifest candidate identity is invalid")
    if issues:
        raise PackageValidationError(issues)
    return value


def load_seal_candidate_document(document: object) -> SealCandidate:
    issues: list[str] = []
    data = _mapping(document, "seal_candidate", issues)
    _keys(
        data,
        {
            "format_version",
            "candidate_id",
            "package",
            "evidence_manifest",
            "seal_input_sha256",
            "provenance_manifest",
            "anchor_migration_report",
            "anchor_migration_sha256",
            "predecessor_package",
        },
        "seal_candidate",
        issues,
    )
    if _integer(data.get("format_version"), "seal_candidate.format_version", issues) != 1:
        issues.append("seal_candidate.format_version must be 1")
    try:
        package = load_game_package_document(data.get("package"))
    except PackageValidationError as exc:
        issues.extend(exc.issues)
        package = _fallback_package()
    try:
        evidence = load_evidence_manifest_document(data.get("evidence_manifest"))
    except PackageValidationError as exc:
        issues.extend(exc.issues)
        evidence = _fallback_evidence()
    try:
        provenance = load_provenance_manifest_document(data.get("provenance_manifest"))
    except ProvenanceValidationError as exc:
        issues.extend(exc.issues)
        provenance = _fallback_provenance()
    try:
        migration_report = load_anchor_migration_report_document(
            data.get("anchor_migration_report")
        )
    except AnchorValidationError as exc:
        issues.extend(exc.issues)
        migration_report = AnchorMigrationReport(1, (), ())
    predecessor: GamePackageV2 | None = None
    raw_predecessor = data.get("predecessor_package")
    if raw_predecessor is not None:
        try:
            predecessor = load_game_package_document(raw_predecessor)
        except PackageValidationError:
            issues.append("incremental seal predecessor package is invalid")
    candidate_id = _stable_id(data.get("candidate_id"), "seal_candidate.candidate_id", issues)
    seal_input_sha = _sha256(
        data.get("seal_input_sha256"), "seal_candidate.seal_input_sha256", issues
    )
    migration_sha = _sha256(
        data.get("anchor_migration_sha256"),
        "seal_candidate.anchor_migration_sha256",
        issues,
    )
    if candidate_id != package.candidate_id:
        issues.append("seal candidate identity does not match package identity")
    if package.evidence_manifest_sha256 != evidence.manifest_sha256:
        issues.append("package is not bound to the supplied evidence manifest")
    try:
        if evidence.candidate_input_sha256 != package_input_sha256(package):
            issues.append("evidence manifest is not bound to package input bytes")
    except (PackageValidationError, TypeError, ValueError):
        issues.append("package input bytes could not be recomputed")
    if isinstance(
        provenance, ProvenanceManifest
    ) and evidence.provenance_manifest_sha256 != public_provenance_manifest_sha256(provenance):
        issues.append("seal candidate is not bound to the supplied provenance manifest")
    expected_migration_sha = sha256_bytes(anchor_migration_report_bytes(migration_report))
    if migration_sha != expected_migration_sha:
        issues.append("seal candidate anchor migration hash is invalid")
    if package.anchor_migration_sha256 != migration_sha:
        issues.append("package is not bound to the supplied anchor migration report")
    if package.seal_mode is SealMode.INITIAL:
        if predecessor is not None:
            issues.append("initial seal candidate cannot include a predecessor package")
        if migration_report.previous_anchors or migration_report.required_anchor_ids:
            issues.append("initial seal candidate cannot include previous anchor requirements")
        if migration_report.migrations or migration_report.resolutions:
            issues.append("initial seal candidate cannot include anchor migrations")
    else:
        if predecessor is None:
            issues.append("incremental seal candidate requires a predecessor package lineage")
        else:
            if predecessor.project_id != package.project_id:
                issues.append("predecessor package belongs to another project lineage")
            if package.predecessor_candidate_id != predecessor.candidate_id:
                issues.append("package predecessor candidate identity is invalid")
            if package.predecessor_package_sha256 != predecessor.package_sha256:
                issues.append("package predecessor hash is invalid")
            if package.predecessor_anchors_sha256 != story_anchor_set_sha256(predecessor.anchors):
                issues.append("package predecessor anchor hash is invalid")
            if migration_report.previous_anchors != predecessor.anchors:
                issues.append("anchor migration report is not bound to predecessor anchors")
    if isinstance(provenance, ProvenanceManifest):
        if provenance.mode is not AdaptationMode.SEALED:
            issues.append("seal candidate provenance must be sealed")
        try:
            _validate_element_bindings(provenance, package.elements)
            _validate_anchor_elements(package.anchors, package.elements)
            _validate_anchor_decisions(provenance, migration_report.migrations)
            expected_report = validate_anchor_migrations(
                migration_report.previous_anchors,
                package.anchors,
                migration_report.migrations,
            )
            if anchor_migration_report_bytes(expected_report) != anchor_migration_report_bytes(
                migration_report
            ):
                issues.append("seal candidate anchor migration report is not reproducible")
        except (PackageValidationError, AnchorValidationError):
            issues.append("seal candidate trace or anchor bindings are invalid")
        expected_seal_input = sha256_bytes(
            canonical_json_bytes(
                {
                    "package_sha256": package.package_sha256,
                    "evidence_manifest_sha256": evidence.manifest_sha256,
                    "provenance_manifest_sha256": public_provenance_manifest_sha256(provenance),
                    "anchor_migration_sha256": migration_sha,
                    "seal_mode": package.seal_mode.value,
                    "predecessor_package_sha256": package.predecessor_package_sha256,
                }
            )
        )
        if seal_input_sha != expected_seal_input:
            issues.append("seal candidate seal_input_sha256 is invalid")
    if issues:
        raise PackageValidationError(issues)
    return SealCandidate(
        1,
        candidate_id,
        package,
        evidence,
        seal_input_sha,
        provenance,
        migration_report,
        migration_sha,
        predecessor,
    )


def load_seal_request_document(document: object) -> SealRequest:
    """Load one bounded, path-free sealing request used by SDK/CLI/Web."""
    issues: list[str] = []
    data = _mapping(document, "seal_request", issues)
    _keys(
        data,
        {
            "project",
            "provenance",
            "elements",
            "anchors",
            "simulation_reports",
            "seal_mode",
            "engine_version",
            "predecessor_package",
            "anchor_migrations",
            "presentation_metadata",
        },
        "seal_request",
        issues,
    )
    try:
        project = load_project_document(data.get("project"))
    except Exception:
        issues.append("seal_request.project is invalid")
        project = _fallback_project()
    try:
        provenance = load_provenance_manifest_document(data.get("provenance"))
    except ProvenanceValidationError as exc:
        issues.extend(exc.issues)
        provenance = _fallback_provenance()
    elements = _load_package_elements(data.get("elements"), issues)
    anchors = _load_anchors(data.get("anchors"), issues)
    seal_mode = _seal_mode(data.get("seal_mode"), "seal_request.seal_mode", issues)
    predecessor: GamePackageV2 | None = None
    raw_predecessor = data.get("predecessor_package")
    if raw_predecessor is not None:
        try:
            predecessor = load_game_package_document(raw_predecessor)
        except PackageValidationError as exc:
            issues.extend(exc.issues)
    migrations: list[AnchorMigration] = []
    raw_migrations = data.get("anchor_migrations")
    if type(raw_migrations) is not list:
        issues.append("seal_request.anchor_migrations must be an array")
    else:
        if len(raw_migrations) > _MAX_COLLECTION:
            issues.append(f"seal_request.anchor_migrations exceeds {_MAX_COLLECTION} entries")
        for index, raw in enumerate(cast(list[object], raw_migrations)[:_MAX_COLLECTION]):
            try:
                migrations.append(
                    load_anchor_migration_document(
                        raw, location=f"seal_request.anchor_migrations[{index}]"
                    )
                )
            except (AnchorValidationError, PackageValidationError) as exc:
                issues.extend(exc.issues)
            except (AttributeError, TypeError, ValueError):
                issues.append("seal_request.anchor_migrations contains an invalid record")
    simulation_reports = _load_simulation_reports(data.get("simulation_reports"), issues)
    metadata = _load_presentation_metadata(
        data.get("presentation_metadata"),
        "seal_request.presentation_metadata",
        issues,
    )
    engine_version = _text(data.get("engine_version"), "seal_request.engine_version", issues)
    if seal_mode is SealMode.INITIAL and (predecessor is not None or migrations):
        issues.append("initial seal lineage cannot include a predecessor or migrations")
    if seal_mode is SealMode.INCREMENTAL and predecessor is None:
        issues.append("incremental seal lineage requires a predecessor package")
    if issues:
        raise PackageValidationError(issues)
    return SealRequest(
        project=project,
        provenance=provenance,
        elements=elements,
        anchors=anchors,
        simulation_reports=simulation_reports,
        seal_mode=seal_mode,
        engine_version=engine_version,
        predecessor_package=predecessor,
        anchor_migrations=tuple(migrations),
        presentation_metadata=metadata,
    )


def _load_simulation_reports(
    value: object,
    issues: list[str],
) -> tuple[SimulationReport | CapabilitySimulationReport, ...]:
    if type(value) is not list:
        issues.append("seal_request.simulation_reports must be an array")
        return ()
    raw_values = cast(list[object], value)
    if len(raw_values) > _MAX_COLLECTION:
        issues.append(f"seal_request.simulation_reports exceeds {_MAX_COLLECTION} entries")
    from lore2mud.authoring.simulation import load_simulation_report_document

    reports: list[SimulationReport | CapabilitySimulationReport] = []
    for index, raw in enumerate(raw_values[:_MAX_COLLECTION]):
        try:
            reports.append(load_simulation_report_document(raw))
        except (AttributeError, TypeError, ValueError):
            issues.append(
                f"seal_request.simulation_reports[{index}] is not a valid simulation evidence report"
            )
    if not reports:
        issues.append("seal_request requires at least one simulation evidence report")
    return tuple(reports)


def _validate_element_bindings(
    provenance: ProvenanceManifest,
    elements: Sequence[PackageElement],
) -> None:
    element_ids = {item.package_element_id for item in elements}
    project_ids = {item.project_element_id for item in elements}
    binding_ids = {item.package_element_id for item in provenance.trace_bindings}
    binding_project_ids = {item.project_element_id for item in provenance.trace_bindings}
    if element_ids != binding_ids:
        raise PackageValidationError(
            ("every package element must have exactly one provenance binding",)
        )
    if project_ids != {item.element_id for item in provenance.project_elements}:
        raise PackageValidationError(("package elements must cover every project element",))
    if binding_project_ids != project_ids:
        raise PackageValidationError(
            ("provenance bindings must cover every package project element",)
        )
    element_pairs = {item.package_element_id: item.project_element_id for item in elements}
    project_kinds = {item.element_id: item.element_kind for item in provenance.project_elements}
    for binding in provenance.trace_bindings:
        if element_pairs.get(binding.package_element_id) != binding.project_element_id:
            raise PackageValidationError(("provenance package/project binding is inconsistent",))
    for element in elements:
        if project_kinds.get(element.project_element_id) != element.element_kind:
            raise PackageValidationError(
                ("package element kind does not match project element kind",)
            )
    for item in elements:
        if not is_opaque_public_id(item.project_element_id):
            raise PackageValidationError(
                ("package element project IDs must be opaque public-safe IDs",)
            )


def _public_package_elements(
    elements: Sequence[PackageElement],
    aliases: PublicProvenanceAliases,
) -> tuple[PackageElement, ...]:
    """Project package references through the same aliases as public provenance."""
    return _validate_package_elements(
        tuple(
            replace(
                element,
                package_element_id=aliases.package_element_ids.get(
                    element.package_element_id,
                    element.package_element_id,
                ),
                project_element_id=aliases.project_element_ids.get(
                    element.project_element_id,
                    element.project_element_id,
                ),
            )
            for element in elements
        )
    )


def _public_anchor_set(
    anchors: Sequence[StoryAnchor],
    aliases: PublicProvenanceAliases,
) -> tuple[StoryAnchor, ...]:
    """Keep opaque anchor identities stable while projecting their bindings."""
    return validate_anchor_set(
        tuple(
            replace(
                anchor,
                project_element_id=aliases.project_element_ids.get(
                    anchor.project_element_id,
                    anchor.project_element_id,
                ),
                package_element_id=aliases.package_element_ids.get(
                    anchor.package_element_id,
                    anchor.package_element_id,
                ),
            )
            for anchor in anchors
        )
    )


def _validate_project_trace_bindings(
    project: GameProject,
    provenance: ProvenanceManifest,
) -> None:
    """Bind every sealed provenance edge to the immutable GameProject trace graph."""
    provenance_decision_ids = {item.decision_id for item in provenance.creator_decisions}
    project_decision_ids = {item.decision_id for item in project.creator_decisions}
    if not provenance_decision_ids.issubset(project_decision_ids):
        raise PackageValidationError(
            ("GameProject creator decisions do not cover the provenance chain",)
        )

    expected_edges = {
        (binding.source_id, binding.project_element_id, binding.decision_id)
        for binding in provenance.trace_bindings
    }
    project_element_ids = {item.element_id for item in provenance.project_elements}
    actual_edges = {
        (record.source_artifact_id, record.target_artifact_id, record.decision_id)
        for record in project.trace_records
        if record.target_artifact_id in project_element_ids
    }
    if not expected_edges.issubset(actual_edges):
        raise PackageValidationError(
            ("GameProject trace records do not cover the provenance chain",)
        )


def _validate_anchor_elements(
    anchors: Sequence[StoryAnchor], elements: Sequence[PackageElement]
) -> None:
    element_ids = {item.package_element_id for item in elements}
    project_ids = {item.project_element_id for item in elements}
    element_pairs = {item.package_element_id: item.project_element_id for item in elements}
    for anchor in anchors:
        if (
            anchor.package_element_id not in element_ids
            or anchor.project_element_id not in project_ids
        ):
            raise PackageValidationError(("anchor references an unknown package element",))
        if element_pairs.get(anchor.package_element_id) != anchor.project_element_id:
            raise PackageValidationError(("anchor package/project binding is inconsistent",))


def _validate_anchor_decisions(
    provenance: ProvenanceManifest,
    migrations: Sequence[AnchorMigration],
) -> None:
    decisions = {item.decision_id: item for item in provenance.creator_decisions}
    for migration in migrations:
        decision = decisions.get(migration.decision_id)
        if decision is None:
            raise PackageValidationError(
                ("anchor migration references an unknown creator decision",)
            )
        if provenance.mode is AdaptationMode.SEALED and not decision.approved:
            raise PackageValidationError(
                ("sealed anchor migrations require approved creator decisions",)
            )


def _validate_package_elements(elements: Sequence[PackageElement]) -> tuple[PackageElement, ...]:
    if type(elements) not in {tuple, list} or len(elements) > _MAX_COLLECTION:
        raise PackageValidationError(
            (f"package elements must contain at most {_MAX_COLLECTION} entries",)
        )
    if not elements:
        raise PackageValidationError(("GamePackage v2 requires at least one package element",))
    normalized: list[PackageElement] = []
    seen: set[str] = set()
    for index, value in enumerate(elements):
        if type(value) is not PackageElement:
            raise PackageValidationError(("package elements must be typed values",))
        try:
            _validate_public_text(value.element_kind, "package element kind")
            document = package_element_to_document(value)
            normalized_data = _freeze_package_data(
                normalize_bounded_json_document(document["data"])
            )
        except PackageValidationError:
            raise
        except (AttributeError, TypeError, ValueError) as exc:
            raise PackageValidationError((f"package element {index} is not bounded data",)) from exc
        if not is_opaque_public_id(value.package_element_id):
            raise PackageValidationError(("package element IDs must be opaque public-safe IDs",))
        if value.package_element_id in seen:
            raise PackageValidationError(("package element IDs must be unique",))
        seen.add(value.package_element_id)
        normalized.append(
            PackageElement(
                value.package_element_id,
                value.project_element_id,
                value.element_kind,
                normalized_data,
            )
        )
    return tuple(sorted(normalized, key=lambda item: item.package_element_id))


def _validate_runtime_data(value: object) -> None:
    normalized = normalize_bounded_json_document(_mutable_package_data(value))
    stack = [normalized]
    while stack:
        current = stack.pop()
        if type(current) is dict:
            mapping = cast(dict[str, object], current)
            for key, item in mapping.items():
                if _is_forbidden_package_key(key):
                    raise PackageValidationError(
                        ("package data cannot contain executable or host-I/O fields",)
                    )
                if not _is_public_safe_key(key):
                    raise PackageValidationError(("package data is not public-safe",))
                stack.append(item)
        elif type(current) is list:
            stack.extend(cast(list[object], current))
        elif type(current) is str:
            if not is_public_safe_text(current):
                raise PackageValidationError(("package data is not public-safe",))


def _validate_evidence_entries(entries: Sequence[EvidenceEntry]) -> tuple[EvidenceEntry, ...]:
    if type(entries) not in {tuple, list} or len(entries) > _MAX_COLLECTION:
        raise PackageValidationError(
            (f"evidence entries must contain at most {_MAX_COLLECTION} entries",)
        )
    if not entries:
        raise PackageValidationError(("a sealed package requires at least one evidence entry",))
    normalized: list[EvidenceEntry] = []
    seen: set[str] = set()
    provenance_count = 0
    simulation_count = 0
    for value in entries:
        if type(value) is not EvidenceEntry:
            raise PackageValidationError(("evidence entries must be typed values",))
        if value.evidence_id in seen:
            raise PackageValidationError(("evidence IDs must be unique",))
        evidence_entry_to_document(value)
        if value.kind == PROVENANCE_EVIDENCE_KIND:
            provenance_count += 1
        else:
            simulation_count += 1
        seen.add(value.evidence_id)
        normalized.append(value)
    if provenance_count != 1:
        raise PackageValidationError(
            ("evidence manifest requires one provenance projection entry",)
        )
    if simulation_count < 1:
        raise PackageValidationError(("evidence manifest requires one simulation evidence entry",))
    return tuple(sorted(normalized, key=lambda item: item.evidence_id))


def _validate_presentation_metadata(
    values: Sequence[WorkspaceMetadataEntry],
) -> tuple[WorkspaceMetadataEntry, ...]:
    if type(values) not in {tuple, list} or len(values) > _MAX_COLLECTION:
        raise PackageValidationError(
            (f"presentation metadata must contain at most {_MAX_COLLECTION} entries",)
        )
    normalized: list[WorkspaceMetadataEntry] = []
    seen: set[str] = set()
    for value in values:
        if type(value) is not WorkspaceMetadataEntry:
            raise PackageValidationError(("presentation metadata must be typed values",))
        _validate_public_key(value.key, "presentation metadata key")
        _validate_public_text(value.value, "presentation metadata value")
        if value.key in seen:
            raise PackageValidationError(("presentation metadata keys must be unique",))
        seen.add(value.key)
        normalized.append(value)
    return tuple(sorted(normalized, key=lambda item: item.key))


def _validate_public_text(value: object, label: str) -> str:
    if type(value) is not str or not value.strip() or len(value) > 512:
        raise PackageValidationError((f"{label} must be bounded non-blank text",))
    if is_public_safe_text(value) is False or any(ord(character) < 32 for character in value):
        raise PackageValidationError((f"{label} is not public-safe text",))
    return value.strip()


def _validate_public_key(value: object, label: str) -> str:
    if type(value) is not str or not _is_public_safe_key(value):
        raise PackageValidationError((f"{label} is not a public-safe key",))
    return value


def _is_public_safe_key(value: str) -> bool:
    if _PUBLIC_SAFE_KEY_RE.fullmatch(value) is None:
        return False
    return not _is_forbidden_package_key(value)


def _is_forbidden_package_key(value: str) -> bool:
    normalized = value.casefold()
    parts = set(normalized.split("_"))
    if normalized in _FORBIDDEN_KEYS or bool(parts & _FORBIDDEN_KEY_TOKENS):
        return True
    return _FORBIDDEN_COMPOUND_KEY_RE.search(normalized) is not None


def _load_content_files(value: object, issues: list[str]) -> tuple[CanonicalContentFile, ...]:
    if type(value) is not list:
        issues.append("package.content_files must be an array")
        return ()
    raw_values = cast(list[object], value)
    if len(raw_values) > _MAX_COLLECTION:
        issues.append(f"package.content_files exceeds {_MAX_COLLECTION} entries")
    entries: dict[str, CanonicalContentFile] = {}
    for index, raw in enumerate(raw_values[:_MAX_COLLECTION]):
        location = f"package.content_files[{index}]"
        data = _mapping(raw, location, issues)
        _keys(data, {"name", "sha256", "document"}, location, issues)
        raw_name = data.get("name")
        name = raw_name if type(raw_name) is str else "invalid"
        if name not in V1_CONTENT_FILE_ORDER:
            issues.append("package content file names must be unique relative names")
        if name in entries:
            issues.append("package content file names must be unique relative names")
        digest = _sha256(data.get("sha256"), f"{location}.sha256", issues)
        try:
            payload = canonical_json_bytes(normalize_bounded_json_document(data.get("document")))
            _validate_runtime_data(parse_bounded_json(payload, DEFAULT_JSON_READ_LIMITS))
        except (TypeError, ValueError):
            issues.append("package content file document is not safe canonical JSON")
            payload = b"{}\n"
        if digest != sha256_bytes(payload):
            issues.append("package content file hash does not match its document")
        entries[name] = CanonicalContentFile(name, digest, payload)
    if not set(REQUIRED_V1_CONTENT_FILES).issubset(entries):
        issues.append("package content files are missing required V1 inputs")
    if set(entries) - set(V1_CONTENT_FILE_ORDER):
        issues.append("package content files contain unsupported runtime inputs")
    return tuple(entries[name] for name in V1_CONTENT_FILE_ORDER if name in entries)


def _load_package_elements(value: object, issues: list[str]) -> tuple[PackageElement, ...]:
    if type(value) is not list:
        issues.append("package.elements must be an array")
        return ()
    raw_values = cast(list[object], value)
    if len(raw_values) > _MAX_COLLECTION:
        issues.append(f"package.elements exceeds {_MAX_COLLECTION} entries")
    values: list[PackageElement] = []
    for index, raw in enumerate(raw_values[:_MAX_COLLECTION]):
        location = f"package.elements[{index}]"
        data = _mapping(raw, location, issues)
        _keys(
            data,
            {"package_element_id", "project_element_id", "element_kind", "data"},
            location,
            issues,
        )
        try:
            item = PackageElement(
                package_element_id=_stable_id(
                    data.get("package_element_id"), f"{location}.package_element_id", issues
                ),
                project_element_id=_stable_id(
                    data.get("project_element_id"), f"{location}.project_element_id", issues
                ),
                element_kind=_text(data.get("element_kind"), f"{location}.element_kind", issues),
                data=normalize_bounded_json_document(data.get("data")),
            )
            _validate_runtime_data(item.data)
        except PackageValidationError as exc:
            issues.extend(exc.issues)
            item = PackageElement("invalid_id", "invalid_id", "invalid", {})
        except (TypeError, ValueError):
            issues.append(f"{location} data is invalid")
            item = PackageElement("invalid_id", "invalid_id", "invalid", {})
        values.append(item)
    try:
        normalized = _validate_package_elements(values)
    except PackageValidationError as exc:
        issues.extend(exc.issues)
        return tuple(values)
    return normalized


def _load_anchors(value: object, issues: list[str]) -> tuple[StoryAnchor, ...]:
    if type(value) is not list:
        issues.append("package.anchors must be an array")
        return ()
    raw_values = cast(list[object], value)
    if len(raw_values) > _MAX_COLLECTION:
        issues.append(f"package.anchors exceeds {_MAX_COLLECTION} entries")
    values: list[StoryAnchor] = []
    for index, raw in enumerate(raw_values[:_MAX_COLLECTION]):
        try:
            values.append(load_story_anchor_document(raw, location=f"package.anchors[{index}]"))
        except AnchorValidationError as exc:
            issues.extend(exc.issues)
    try:
        return validate_anchor_set(values)
    except AnchorValidationError as exc:
        issues.extend(exc.issues)
        return tuple(values)


def _load_evidence_entries(value: object, issues: list[str]) -> tuple[EvidenceEntry, ...]:
    if type(value) is not list:
        issues.append("evidence_manifest.entries must be an array")
        return ()
    raw_values = cast(list[object], value)
    if len(raw_values) > _MAX_COLLECTION:
        issues.append(f"evidence_manifest.entries exceeds {_MAX_COLLECTION} entries")
    values: list[EvidenceEntry] = []
    for index, raw in enumerate(raw_values[:_MAX_COLLECTION]):
        location = f"evidence_manifest.entries[{index}]"
        data = _mapping(raw, location, issues)
        _keys(data, {"evidence_id", "kind", "artifact_sha256", "admitted"}, location, issues)
        values.append(
            EvidenceEntry(
                evidence_id=_stable_id(data.get("evidence_id"), f"{location}.evidence_id", issues),
                kind=_text(data.get("kind"), f"{location}.kind", issues),
                artifact_sha256=_sha256(
                    data.get("artifact_sha256"), f"{location}.artifact_sha256", issues
                ),
                admitted=_boolean(data.get("admitted"), f"{location}.admitted", issues),
            )
        )
    try:
        return _validate_evidence_entries(values)
    except PackageValidationError as exc:
        issues.extend(exc.issues)
        return tuple(values)


def _load_presentation_metadata(
    value: object,
    location: str,
    issues: list[str],
) -> tuple[WorkspaceMetadataEntry, ...]:
    if type(value) is not list:
        issues.append(f"{location} must be an array")
        return ()
    raw_values = cast(list[object], value)
    if len(raw_values) > _MAX_COLLECTION:
        issues.append(f"{location} exceeds {_MAX_COLLECTION} entries")
    values: list[WorkspaceMetadataEntry] = []
    for index, raw in enumerate(raw_values[:_MAX_COLLECTION]):
        item_location = f"{location}[{index}]"
        data = _mapping(raw, item_location, issues)
        _keys(data, {"key", "value"}, item_location, issues)
        values.append(
            WorkspaceMetadataEntry(
                _text(data.get("key"), f"{item_location}.key", issues),
                _text(data.get("value"), f"{item_location}.value", issues),
            )
        )
    try:
        return _validate_presentation_metadata(values)
    except PackageValidationError as exc:
        issues.extend(exc.issues)
        return tuple(values)


def _stable_id_set(value: object, location: str, issues: list[str]) -> tuple[str, ...]:
    if type(value) is not list:
        issues.append(f"{location} must be an array")
        return ()
    values = cast(list[object], value)
    if len(values) > _MAX_COLLECTION:
        issues.append(f"{location} exceeds {_MAX_COLLECTION} entries")
    identifiers = [
        _stable_id(item, f"{location}[{index}]", issues)
        for index, item in enumerate(values[:_MAX_COLLECTION])
    ]
    if len(set(identifiers)) != len(identifiers):
        issues.append(f"{location} contains duplicate IDs")
    return tuple(sorted(set(identifiers)))


def _stable_id(value: object, location: str, issues: list[str]) -> str:
    if not is_opaque_public_id(value):
        issues.append(f"{location} must be an opaque public-safe ID")
        return "invalid_id"
    assert isinstance(value, str)
    return value


def _optional_stable_id(value: object, location: str, issues: list[str]) -> str | None:
    if value is None:
        return None
    return _stable_id(value, location, issues)


def _sha256(value: object, location: str, issues: list[str]) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        issues.append(f"{location} must be a SHA-256 digest")
        return "0" * 64
    return value


def _optional_sha256(value: object, location: str, issues: list[str]) -> str | None:
    if value is None:
        return None
    return _sha256(value, location, issues)


def _seal_mode(value: object, location: str, issues: list[str]) -> SealMode:
    if type(value) is not str:
        issues.append(f"{location} must be initial or incremental")
        return SealMode.INITIAL
    try:
        return SealMode(value)
    except ValueError:
        issues.append(f"{location} must be initial or incremental")
        return SealMode.INITIAL


def _text(value: object, location: str, issues: list[str]) -> str:
    if not is_public_safe_text(value):
        issues.append(f"{location} is not public-safe text")
        return "invalid"
    assert isinstance(value, str)
    return value.strip()


def _integer(value: object, location: str, issues: list[str]) -> int:
    if type(value) is not int:
        issues.append(f"{location} must be an integer")
        return 0
    return value


def _boolean(value: object, location: str, issues: list[str]) -> bool:
    if type(value) is not bool:
        issues.append(f"{location} must be a boolean")
        return False
    return value


def _mapping(value: object, location: str, issues: list[str]) -> dict[str, object]:
    if type(value) is not dict:
        issues.append(f"{location} must be an object")
        return {}
    if not all(type(key) is str for key in value):
        issues.append(f"{location} keys must be strings")
        return {}
    return cast(dict[str, object], value)


def _keys(data: dict[str, object], expected: set[str], location: str, issues: list[str]) -> None:
    if set(data) != expected:
        issues.append(f"{location} fields are invalid")


def _validate_v1_content_files(files: Sequence[CanonicalContentFile]) -> None:
    """Require the current V1 runtime content boundary before accepting package data."""
    if not files:
        raise PackageValidationError(("GamePackage v2 requires V1 content files",))
    names = [item.name for item in files]
    if len(names) != len(set(names)):
        raise PackageValidationError(("package content file names must be unique",))
    if not set(REQUIRED_V1_CONTENT_FILES).issubset(names):
        raise PackageValidationError(("package content files are missing required V1 inputs",))
    if set(names) - set(V1_CONTENT_FILE_ORDER):
        raise PackageValidationError(("package content files contain unsupported runtime inputs",))
    try:
        with tempfile.TemporaryDirectory(prefix="lore2mud-v2-package-") as directory:
            root = Path(directory)
            for value in files:
                try:
                    _validate_runtime_data(
                        parse_bounded_json(value.canonical_json, DEFAULT_JSON_READ_LIMITS)
                    )
                except (PackageValidationError, TypeError, ValueError) as exc:
                    raise PackageValidationError(
                        ("GamePackage v2 content files contain private or executable data",)
                    ) from exc
                (root / value.name).write_bytes(value.canonical_json)
            load_content_pack(root)
    except (ContentValidationError, OSError) as exc:
        raise PackageValidationError(("GamePackage v2 content files fail V1 validation",)) from exc


def _fallback_package() -> GamePackageV2:
    return GamePackageV2(
        format_version=PACKAGE_FORMAT_VERSION,
        candidate_id="package_invalid",
        project_id="invalid_project",
        engine_version=__version__,
        content_files=(),
        capability_requirement_ids=(),
        elements=(),
        anchors=(),
        seal_mode=SealMode.INITIAL,
        predecessor_candidate_id=None,
        predecessor_package_sha256=None,
        predecessor_anchors_sha256=None,
        evidence_manifest_sha256="0" * 64,
        package_sha256="0" * 64,
    )


def _fallback_evidence() -> EvidenceManifest:
    return EvidenceManifest(
        EVIDENCE_FORMAT_VERSION,
        "0" * 64,
        "0" * 64,
        (),
        "evidence_invalid",
        "0" * 64,
    )


def _fallback_project() -> GameProject:
    return cast(GameProject, object())


def _fallback_provenance() -> ProvenanceManifest:
    return cast(ProvenanceManifest, object())
