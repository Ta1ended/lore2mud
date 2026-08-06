"""Shared application service used by the V2-2 SDK and structured CLI."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from lore2mud._bounded_json import BoundedJsonError, JsonReadErrorCode
from lore2mud.authoring.contracts import (
    AuthoringDiagnostic,
    AuthoringResult,
    AuthoringStage,
    AuthoringStatus,
    CreatorDecision,
    DiagnosticSeverity,
    GameBlueprint,
    GameProject,
    PreviewBuild,
    ProofingProjection,
    PublicInputDescriptor,
    SimulationReport,
    SimulationRequest,
    TraceRecord,
    WorkspaceMetadataEntry,
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
from lore2mud.authoring.preview import build_preview
from lore2mud.authoring.proofing import build_proofing_projection
from lore2mud.authoring.simulation import (
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
            return _unsafe_text_rejection(
                "create_project", diagnostic_artifact_id(project_id)
            )
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

    def validate_blueprint_document(
        self, document: object
    ) -> AuthoringResult[GameBlueprint]:
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

    def build_preview(self, project: GameProject) -> AuthoringResult[PreviewBuild]:
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
        self, project: GameProject, request: SimulationRequest
    ) -> AuthoringResult[SimulationReport]:
        return simulate_project(project, request)

    def replay(
        self, project: GameProject, report: SimulationReport
    ) -> AuthoringResult[SimulationReport]:
        try:
            normalized_project = validate_project(project)
        except InvalidUnicodeScalarError:
            return _unsafe_text_rejection("replay", "project")
        except AuthoringDocumentTraversalError:
            return _bounded_input_rejection(
                "replay", "project", JsonReadErrorCode.TOO_COMPLEX
            )
        except BoundedJsonError as exc:
            return _bounded_input_rejection("replay", "project", exc.code)
        except (BlueprintValidationError, ProjectValidationError):
            return replay_report(project, report)

        try:
            normalized_report = validate_simulation_report(report)
        except InvalidUnicodeScalarError:
            return _unsafe_text_rejection("replay", "report")
        except AuthoringDocumentTraversalError:
            return _bounded_input_rejection(
                "replay", "report", JsonReadErrorCode.TOO_COMPLEX
            )
        except BoundedJsonError as exc:
            return _bounded_input_rejection("replay", "report", exc.code)
        except SimulationValidationError:
            return replay_report(normalized_project, report)
        return replay_report(normalized_project, normalized_report)

    def proof(self, project: GameProject) -> AuthoringResult[ProofingProjection]:
        try:
            normalized = validate_project(project)
        except InvalidUnicodeScalarError:
            return _unsafe_text_rejection("proof", "project")
        except AuthoringDocumentTraversalError:
            return _bounded_input_rejection(
                "proof", "project", JsonReadErrorCode.TOO_COMPLEX
            )
        except BoundedJsonError as exc:
            return _bounded_input_rejection("proof", "project", exc.code)
        except (BlueprintValidationError, ProjectValidationError):
            return build_proofing_projection(project)
        return build_proofing_projection(normalized)


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
