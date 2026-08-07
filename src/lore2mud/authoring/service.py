"""Shared application service used by the V2-2/V2-3 SDK and structured CLI."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
import re

from lore2mud._bounded_json import BoundedJsonError, JsonReadErrorCode
from lore2mud.authoring.contracts import (
    AuthoringDiagnostic,
    AuthoringResult,
    AuthoringStage,
    AuthoringStatus,
    CapabilitySimulationReport,
    CapabilitySimulationRequest,
    CreatorDecision,
    DiagnosticSeverity,
    GameBlueprint,
    GameProject,
    PublicInputDescriptor,
    SimulationReport,
    SimulationRequest,
    TraceRecord,
    WorkspaceMetadataEntry,
)
from lore2mud.authoring.anchors import (
    AnchorMigration,
    AnchorMigrationReport,
    AnchorValidationError,
    StoryAnchor,
    load_anchor_migration_document,
    load_story_anchor_document,
    validate_anchor_migrations,
)
from lore2mud.authoring.packages import (
    PackageValidationError,
    SealCandidate,
    SealRequest,
    load_seal_request_document,
    seal_game_package,
)
from lore2mud.authoring.project import (
    BlueprintValidationError,
    ProjectValidationError,
    create_game_project,
    diagnostic_artifact_id,
    load_blueprint_document,
    load_project_document,
    validate_blueprint,
    validate_project,
)
from lore2mud.authoring.provenance import (
    ProvenanceManifest,
    ProvenanceValidationError,
    load_provenance_manifest_document,
    public_provenance_manifest,
    validate_provenance_manifest,
)
from lore2mud.authoring.preview import PreviewResult, build_preview
from lore2mud.authoring.proofing import ProofingResult, build_proofing_projection
from lore2mud.authoring.simulation import (
    SimulationResult,
    SimulationValidationError,
    replay_report,
    simulate_project,
    validate_simulation_report,
)
from lore2mud.authoring.serialization import (
    AuthoringDocumentTraversalError,
    InvalidUnicodeScalarError,
    validate_unicode_scalars,
)


class AuthoringService:
    """Coordinate one deterministic authoring implementation for every client."""

    def create_project(
        self,
        *,
        project_id: str,
        blueprint: GameBlueprint,
        content_root: Path,
        public_inputs: Iterable[PublicInputDescriptor] = (),
        creator_decisions: Iterable[CreatorDecision] = (),
        trace_records: Iterable[TraceRecord] = (),
        workspace_metadata: Iterable[WorkspaceMetadataEntry] = (),
    ) -> AuthoringResult[GameProject]:
        try:
            normalized_blueprint = validate_blueprint(blueprint)
        except InvalidUnicodeScalarError:
            return _unsafe_text_rejection("create_project", "blueprint")
        except AuthoringDocumentTraversalError:
            return _bounded_input_rejection(
                "create_project", "blueprint", JsonReadErrorCode.TOO_COMPLEX
            )
        except BoundedJsonError as exc:
            return _bounded_input_rejection("create_project", "blueprint", exc.code)
        except BlueprintValidationError:
            return _rejected(
                "create_project",
                AuthoringStage.PROJECT,
                "project_invalid",
                diagnostic_artifact_id(project_id),
                "/",
                "The GameProject v1 inputs are invalid.",
                "Correct the blueprint or public V1 content inputs and retry.",
            )
        except (AttributeError, RecursionError, TypeError, ValueError):
            return _rejected(
                "create_project",
                AuthoringStage.PROJECT,
                "project_invalid",
                diagnostic_artifact_id(project_id),
                "/",
                "The typed GameProject v1 inputs are invalid.",
                "Correct the blueprint and typed public inputs, then retry.",
            )

        try:
            project = create_game_project(
                project_id=project_id,
                blueprint=normalized_blueprint,
                content_root=content_root,
                public_inputs=public_inputs,
                creator_decisions=creator_decisions,
                trace_records=trace_records,
                workspace_metadata=workspace_metadata,
            )
        except InvalidUnicodeScalarError:
            return _unsafe_text_rejection("create_project", diagnostic_artifact_id(project_id))
        except AuthoringDocumentTraversalError:
            return _bounded_input_rejection(
                "create_project",
                diagnostic_artifact_id(project_id),
                JsonReadErrorCode.TOO_COMPLEX,
            )
        except BoundedJsonError as exc:
            return _bounded_input_rejection(
                "create_project", diagnostic_artifact_id(project_id), exc.code
            )
        except (BlueprintValidationError, ProjectValidationError):
            return _rejected(
                "create_project",
                AuthoringStage.PROJECT,
                "project_invalid",
                diagnostic_artifact_id(project_id),
                "/",
                "The GameProject v1 inputs are invalid.",
                "Correct the blueprint or public V1 content inputs and retry.",
            )
        except (AttributeError, RecursionError, TypeError, ValueError):
            return _rejected(
                "create_project",
                AuthoringStage.PROJECT,
                "project_invalid",
                diagnostic_artifact_id(project_id),
                "/",
                "The typed GameProject v1 inputs are invalid.",
                "Correct the blueprint and typed public inputs, then retry.",
            )
        except OSError:
            return _rejected(
                "create_project",
                AuthoringStage.PROJECT,
                "project_input_io_error",
                diagnostic_artifact_id(project_id),
                "/content_files",
                "The public content input could not be read.",
                "Provide a readable public-safe V1 content directory.",
            )
        return _success("create_project", project)

    def validate_blueprint_document(self, document: object) -> AuthoringResult[GameBlueprint]:
        try:
            validate_unicode_scalars(document)
            blueprint = load_blueprint_document(document)
        except InvalidUnicodeScalarError:
            return _unsafe_text_rejection("validate_blueprint", "blueprint")
        except BlueprintValidationError:
            return _rejected(
                "validate_blueprint",
                AuthoringStage.BLUEPRINT,
                "blueprint_invalid",
                "blueprint",
                "/",
                "The GameBlueprint v1 document is invalid.",
                "Correct the document to match GameBlueprint v1.",
            )
        except (AttributeError, RecursionError, TypeError, ValueError):
            return _rejected(
                "validate_blueprint",
                AuthoringStage.BLUEPRINT,
                "blueprint_invalid",
                "blueprint",
                "/",
                "The GameBlueprint v1 document is invalid.",
                "Correct the document to match GameBlueprint v1.",
            )
        return _success("validate_blueprint", blueprint)

    def validate_project_document(self, document: object) -> AuthoringResult[GameProject]:
        try:
            validate_unicode_scalars(document)
            project = load_project_document(document)
        except InvalidUnicodeScalarError:
            return _unsafe_text_rejection("validate_project", "project")
        except (BlueprintValidationError, ProjectValidationError):
            return _rejected(
                "validate_project",
                AuthoringStage.PROJECT,
                "project_invalid",
                "project",
                "/",
                "The GameProject v1 document is invalid.",
                "Correct the document to match GameProject v1.",
            )
        except (AttributeError, RecursionError, TypeError, ValueError):
            return _rejected(
                "validate_project",
                AuthoringStage.PROJECT,
                "project_invalid",
                "project",
                "/",
                "The GameProject v1 document is invalid.",
                "Correct the document to match GameProject v1.",
            )
        return _success("validate_project", project)

    def validate_project(self, project: GameProject) -> AuthoringResult[GameProject]:
        try:
            validated = validate_project(project)
        except InvalidUnicodeScalarError:
            return _unsafe_text_rejection("validate_project", "project")
        except AuthoringDocumentTraversalError:
            return _bounded_input_rejection(
                "validate_project", "project", JsonReadErrorCode.TOO_COMPLEX
            )
        except BoundedJsonError as exc:
            return _bounded_input_rejection("validate_project", "project", exc.code)
        except (BlueprintValidationError, ProjectValidationError):
            return _rejected(
                "validate_project",
                AuthoringStage.PROJECT,
                "project_invalid",
                _project_artifact_id(project),
                "/",
                "The typed GameProject v1 value is invalid.",
                "Correct the project inputs and rebuild the project.",
            )
        return _success("validate_project", validated)

    def build_preview(self, project: GameProject) -> PreviewResult:
        try:
            normalized = validate_project(project)
        except InvalidUnicodeScalarError:
            return _unsafe_text_rejection("build_preview", "project")
        except AuthoringDocumentTraversalError:
            return _bounded_input_rejection(
                "build_preview", "project", JsonReadErrorCode.TOO_COMPLEX
            )
        except BoundedJsonError as exc:
            return _bounded_input_rejection("build_preview", "project", exc.code)
        except (BlueprintValidationError, ProjectValidationError):
            return build_preview(project)
        return build_preview(normalized)

    def simulate(
        self,
        project: GameProject,
        request: SimulationRequest | CapabilitySimulationRequest,
    ) -> SimulationResult:
        return simulate_project(project, request)

    def replay(
        self,
        project: GameProject,
        report: SimulationReport | CapabilitySimulationReport,
    ) -> SimulationResult:
        try:
            normalized_project = validate_project(project)
        except InvalidUnicodeScalarError:
            return _unsafe_text_rejection("replay", "project")
        except AuthoringDocumentTraversalError:
            return _bounded_input_rejection("replay", "project", JsonReadErrorCode.TOO_COMPLEX)
        except BoundedJsonError as exc:
            return _bounded_input_rejection("replay", "project", exc.code)
        except (BlueprintValidationError, ProjectValidationError):
            return replay_report(project, report)

        try:
            normalized_report = validate_simulation_report(report)
        except InvalidUnicodeScalarError:
            return _unsafe_text_rejection("replay", "report")
        except AuthoringDocumentTraversalError:
            return _bounded_input_rejection("replay", "report", JsonReadErrorCode.TOO_COMPLEX)
        except BoundedJsonError as exc:
            return _bounded_input_rejection("replay", "report", exc.code)
        except SimulationValidationError:
            return replay_report(normalized_project, report)
        return replay_report(normalized_project, normalized_report)

    def proof(self, project: GameProject) -> ProofingResult:
        try:
            normalized = validate_project(project)
        except InvalidUnicodeScalarError:
            return _unsafe_text_rejection("proof", "project")
        except AuthoringDocumentTraversalError:
            return _bounded_input_rejection("proof", "project", JsonReadErrorCode.TOO_COMPLEX)
        except BoundedJsonError as exc:
            return _bounded_input_rejection("proof", "project", exc.code)
        except (BlueprintValidationError, ProjectValidationError):
            return build_proofing_projection(project)
        return build_proofing_projection(normalized)

    def validate_provenance_document(self, document: object) -> AuthoringResult[ProvenanceManifest]:
        try:
            validate_unicode_scalars(document)
            manifest = load_provenance_manifest_document(document)
            public_manifest = public_provenance_manifest(manifest)
        except InvalidUnicodeScalarError:
            return _bounded_input_rejection(
                "validate_provenance", "provenance", JsonReadErrorCode.TOO_COMPLEX
            )
        except AuthoringDocumentTraversalError:
            return _bounded_input_rejection(
                "validate_provenance", "provenance", JsonReadErrorCode.TOO_COMPLEX
            )
        except BoundedJsonError as exc:
            return _bounded_input_rejection("validate_provenance", "provenance", exc.code)
        except ProvenanceValidationError as exc:
            return _v2_rejected(
                "validate_provenance",
                AuthoringStage.PROVENANCE,
                _provenance_code(exc.issues),
                "provenance",
                "The provenance and rights manifest is invalid.",
                "Correct the public-safe references, rights assertions, and trace chain.",
            )
        except (AttributeError, RecursionError, TypeError, ValueError):
            return _v2_rejected(
                "validate_provenance",
                AuthoringStage.PROVENANCE,
                "provenance_invalid",
                "provenance",
                "The provenance and rights manifest is invalid.",
                "Correct the public-safe references, rights assertions, and trace chain.",
            )
        return _success("validate_provenance", public_manifest)

    def validate_provenance(
        self, manifest: ProvenanceManifest
    ) -> AuthoringResult[ProvenanceManifest]:
        try:
            normalized = validate_provenance_manifest(manifest)
            public_manifest = public_provenance_manifest(normalized)
        except InvalidUnicodeScalarError:
            return _bounded_input_rejection(
                "validate_provenance", "provenance", JsonReadErrorCode.TOO_COMPLEX
            )
        except AuthoringDocumentTraversalError:
            return _bounded_input_rejection(
                "validate_provenance", "provenance", JsonReadErrorCode.TOO_COMPLEX
            )
        except BoundedJsonError as exc:
            return _bounded_input_rejection("validate_provenance", "provenance", exc.code)
        except ProvenanceValidationError as exc:
            return _v2_rejected(
                "validate_provenance",
                AuthoringStage.PROVENANCE,
                _provenance_code(exc.issues),
                "provenance",
                "The provenance and rights manifest is invalid.",
                "Correct the public-safe references, rights assertions, and trace chain.",
            )
        except (AttributeError, RecursionError, TypeError, ValueError):
            return _v2_rejected(
                "validate_provenance",
                AuthoringStage.PROVENANCE,
                "provenance_invalid",
                "provenance",
                "The provenance and rights manifest is invalid.",
                "Correct the public-safe references, rights assertions, and trace chain.",
            )
        return _success("validate_provenance", public_manifest)

    def validate_anchor_migrations(
        self,
        previous_anchors: tuple[StoryAnchor, ...],
        current_anchors: tuple[StoryAnchor, ...],
        migrations: tuple[AnchorMigration, ...],
    ) -> AuthoringResult[AnchorMigrationReport]:
        try:
            report = validate_anchor_migrations(
                previous_anchors,
                current_anchors,
                migrations,
            )
        except AnchorValidationError as exc:
            return _v2_rejected(
                "validate_anchors",
                AuthoringStage.ANCHOR,
                _anchor_code(exc.issues),
                "anchors",
                "The anchor migration set is invalid or unresolved.",
                "Preserve each anchor or provide an explicit migration to current anchors.",
            )
        except (AttributeError, RecursionError, TypeError, ValueError):
            return _v2_rejected(
                "validate_anchors",
                AuthoringStage.ANCHOR,
                "anchor_migration_invalid",
                "anchors",
                "The anchor migration set is invalid or unresolved.",
                "Preserve each anchor or provide an explicit migration to current anchors.",
            )
        return _success("validate_anchors", report)

    def validate_anchor_migrations_document(
        self, document: object
    ) -> AuthoringResult[AnchorMigrationReport]:
        try:
            validate_unicode_scalars(document)
            data = _object(document, "anchor_request")
            _exact_keys(
                data,
                {
                    "previous_anchors",
                    "current_anchors",
                    "migrations",
                },
                "anchor_request",
            )
            previous = tuple(
                load_story_anchor_document(value, location=f"previous_anchors[{index}]")
                for index, value in enumerate(_array(data["previous_anchors"], "previous_anchors"))
            )
            current = tuple(
                load_story_anchor_document(value, location=f"current_anchors[{index}]")
                for index, value in enumerate(_array(data["current_anchors"], "current_anchors"))
            )
            migrations = tuple(
                load_anchor_migration_document(value, location=f"migrations[{index}]")
                for index, value in enumerate(_array(data["migrations"], "migrations"))
            )
        except InvalidUnicodeScalarError:
            return _bounded_input_rejection(
                "validate_anchors", "anchors", JsonReadErrorCode.TOO_COMPLEX
            )
        except AuthoringDocumentTraversalError:
            return _bounded_input_rejection(
                "validate_anchors", "anchors", JsonReadErrorCode.TOO_COMPLEX
            )
        except BoundedJsonError as exc:
            return _bounded_input_rejection("validate_anchors", "anchors", exc.code)
        except (AnchorValidationError, AttributeError, RecursionError, TypeError, ValueError):
            return _v2_rejected(
                "validate_anchors",
                AuthoringStage.ANCHOR,
                "anchor_migration_invalid",
                "anchors",
                "The anchor migration request is invalid.",
                "Provide bounded anchor records and explicit migration targets.",
            )
        return self.validate_anchor_migrations(previous, current, migrations)

    def seal(self, request: SealRequest) -> AuthoringResult[SealCandidate]:
        try:
            candidate = seal_game_package(
                request.project,
                request.provenance,
                elements=request.elements,
                anchors=request.anchors,
                simulation_reports=request.simulation_reports,
                engine_version=request.engine_version,
                seal_mode=request.seal_mode,
                predecessor_package=request.predecessor_package,
                anchor_migrations=request.anchor_migrations,
                presentation_metadata=request.presentation_metadata,
            )
        except (PackageValidationError, ProvenanceValidationError, AnchorValidationError) as exc:
            return _v2_rejected(
                "seal",
                AuthoringStage.SEAL,
                _seal_code(getattr(exc, "issues", ())),
                "seal_request",
                "The sealed package request was rejected.",
                "Resolve rights, trace, package, evidence, anchor, and public-safe input diagnostics before sealing.",
            )
        except (AttributeError, RecursionError, TypeError, ValueError):
            return _v2_rejected(
                "seal",
                AuthoringStage.SEAL,
                "seal_input_invalid",
                "seal_request",
                "The sealed package request was rejected.",
                "Resolve rights, trace, package, evidence, anchor, and public-safe input diagnostics before sealing.",
            )
        return _success("seal", candidate)

    def seal_document(self, document: object) -> AuthoringResult[SealCandidate]:
        try:
            validate_unicode_scalars(document)
            request = load_seal_request_document(document)
        except InvalidUnicodeScalarError:
            return _bounded_input_rejection("seal", "seal_request", JsonReadErrorCode.TOO_COMPLEX)
        except AuthoringDocumentTraversalError:
            return _bounded_input_rejection("seal", "seal_request", JsonReadErrorCode.TOO_COMPLEX)
        except BoundedJsonError as exc:
            return _bounded_input_rejection("seal", "seal_request", exc.code)
        except PackageValidationError as exc:
            return _v2_rejected(
                "seal",
                AuthoringStage.SEAL,
                _seal_code(exc.issues),
                "seal_request",
                "The sealed package request was rejected.",
                "Resolve rights, trace, package, evidence, anchor, and public-safe input diagnostics before sealing.",
            )
        except (AttributeError, RecursionError, TypeError, ValueError):
            return _v2_rejected(
                "seal",
                AuthoringStage.SEAL,
                "seal_input_invalid",
                "seal_request",
                "The sealed package request was rejected.",
                "Resolve rights, trace, package, evidence, anchor, and public-safe input diagnostics before sealing.",
            )
        return self.seal(request)


def _success(operation: str, artifact: object) -> AuthoringResult:
    return AuthoringResult(
        format_version=1,
        operation=operation,
        status=AuthoringStatus.SUCCESS,
        artifact=artifact,
        diagnostics=(),
        exit_code=0,
    )


def _unsafe_text_rejection(operation: str, artifact_id: str) -> AuthoringResult:
    return _bounded_input_rejection(
        operation,
        artifact_id,
        JsonReadErrorCode.TOO_COMPLEX,
    )


def _bounded_input_rejection(
    operation: str,
    artifact_id: str,
    code: JsonReadErrorCode,
) -> AuthoringResult:
    return _rejected(
        operation,
        AuthoringStage.SERIALIZATION,
        f"authoring_input_{code.value}",
        artifact_id,
        "/",
        "The authoring JSON input could not be read safely.",
        "Provide readable UTF-8 JSON within the documented resource limits.",
    )


def _project_artifact_id(project: object) -> str:
    if type(project) is not GameProject:
        return "project"
    return diagnostic_artifact_id(project.project_id)


def _rejected(
    operation: str,
    stage: AuthoringStage,
    code: str,
    artifact_id: str,
    pointer: str,
    message: str,
    remediation: str,
) -> AuthoringResult:
    return AuthoringResult(
        format_version=1,
        operation=operation,
        status=AuthoringStatus.REJECTED,
        artifact=None,
        diagnostics=(
            AuthoringDiagnostic(
                stage=stage,
                code=code,
                severity=DiagnosticSeverity.ERROR,
                artifact_id=artifact_id,
                json_pointer=pointer,
                source_span=None,
                message=message,
                remediation=remediation,
            ),
        ),
        exit_code=1,
    )


def _v2_rejected(
    operation: str,
    stage: AuthoringStage,
    code: str,
    artifact_id: str,
    message: str,
    remediation: str,
) -> AuthoringResult:
    return _rejected(
        operation,
        stage,
        code,
        diagnostic_artifact_id(artifact_id, fallback=artifact_id),
        "/",
        message,
        remediation,
    )


def _provenance_code(value: object) -> str:
    text = " ".join(str(item) for item in value) if isinstance(value, (tuple, list)) else str(value)
    lowered = text.casefold()
    if "cycle" in lowered:
        return "provenance_cycle"
    if "duplicate" in lowered:
        return "provenance_duplicate_id"
    if "rights" in lowered or "denied" in lowered or "authorized" in lowered:
        return "rights_assertion_invalid"
    if "public-safe" in lowered:
        return "provenance_private_data"
    if "unknown" in lowered or "reference" in lowered:
        return "provenance_reference_missing"
    return "provenance_invalid"


def _anchor_code(value: object) -> str:
    text = " ".join(str(item) for item in value) if isinstance(value, (tuple, list)) else str(value)
    lowered = text.casefold()
    if "cycle" in lowered:
        return "anchor_migration_cycle"
    if "unresolved" in lowered or "absent" in lowered:
        return "anchor_unresolved"
    if "duplicate" in lowered:
        return "anchor_duplicate_id"
    return "anchor_migration_invalid"


def _seal_code(value: object) -> str:
    text = " ".join(str(item) for item in value) if isinstance(value, (tuple, list)) else str(value)
    lowered = text.casefold()
    if any(
        token in lowered
        for token in (
            "fields are invalid",
            "must be an array",
            "must be an object",
            "exceeds 4096",
            "at most 4096",
        )
    ):
        return "seal_input_invalid"
    if "private-safe" in lowered or "public-safe" in lowered or "executable" in lowered:
        return "seal_private_or_executable_data"
    if "lineage" in lowered or "predecessor" in lowered or "seal mode" in lowered:
        return "seal_lineage_invalid"
    if "anchor" in lowered or "migration" in lowered:
        return "seal_anchor_invalid"
    if "evidence" in lowered:
        return "seal_evidence_invalid"
    if "identity" in lowered or "hash" in lowered:
        return "seal_identity_invalid"
    if "provenance" in lowered or "rights" in lowered:
        return "seal_provenance_invalid"
    return "seal_rejected"


def _object(value: object, location: str) -> dict[str, object]:
    if type(value) is not dict or not all(type(key) is str for key in value):
        raise ValueError(f"{location} must be an object")
    return value


def _exact_keys(data: dict[str, object], expected: set[str], location: str) -> None:
    if set(data) != expected:
        raise ValueError(f"{location} fields are invalid")


def _array(value: object, location: str) -> list[object]:
    if type(value) is not list or len(value) > 4096:
        raise ValueError(f"{location} is invalid")
    return value


def _stable_ids(value: object, location: str) -> list[str]:
    values = _array(value, location)
    result: list[str] = []
    for item in values:
        if type(item) is not str or re.fullmatch(r"^[a-z][a-z0-9_]{0,63}$", item) is None:
            raise ValueError(f"{location} contains an invalid ID")
        result.append(item)
    if len(set(result)) != len(result):
        raise ValueError(f"{location} contains duplicate IDs")
    return result
