"""Typed Python facade for the shared V2-2 authoring service."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

from lore2mud.authoring.contracts import (
    AuthoringResult,
    CreatorDecision,
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
from lore2mud.authoring.service import AuthoringService


class AuthoringServiceProtocol(Protocol):
    """Structural contract implemented by the shared application service."""

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
    ) -> AuthoringResult[GameProject]: ...

    def validate_blueprint_document(
        self, document: object
    ) -> AuthoringResult[GameBlueprint]: ...

    def validate_project_document(
        self, document: object
    ) -> AuthoringResult[GameProject]: ...

    def validate_project(
        self, project: GameProject
    ) -> AuthoringResult[GameProject]: ...

    def build_preview(
        self, project: GameProject
    ) -> AuthoringResult[PreviewBuild]: ...

    def simulate(
        self, project: GameProject, request: SimulationRequest
    ) -> AuthoringResult[SimulationReport]: ...

    def replay(
        self, project: GameProject, report: SimulationReport
    ) -> AuthoringResult[SimulationReport]: ...

    def proof(
        self, project: GameProject
    ) -> AuthoringResult[ProofingProjection]: ...


class AgentAuthoringSDK:
    """Agent-facing typed facade with no independent authoring rules."""

    def __init__(self, service: AuthoringServiceProtocol | None = None) -> None:
        self._service = service if service is not None else _default_service()

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
        return self._service.create_project(
            project_id=project_id,
            blueprint=blueprint,
            content_root=content_root,
            public_inputs=public_inputs,
            creator_decisions=creator_decisions,
            trace_records=trace_records,
            workspace_metadata=workspace_metadata,
        )

    def validate_blueprint_document(
        self, document: object
    ) -> AuthoringResult[GameBlueprint]:
        return self._service.validate_blueprint_document(document)

    def validate_project_document(
        self, document: object
    ) -> AuthoringResult[GameProject]:
        return self._service.validate_project_document(document)

    def validate_project(
        self, project: GameProject
    ) -> AuthoringResult[GameProject]:
        return self._service.validate_project(project)

    def build_preview(
        self, project: GameProject
    ) -> AuthoringResult[PreviewBuild]:
        return self._service.build_preview(project)

    def simulate(
        self, project: GameProject, request: SimulationRequest
    ) -> AuthoringResult[SimulationReport]:
        return self._service.simulate(project, request)

    def replay(
        self, project: GameProject, report: SimulationReport
    ) -> AuthoringResult[SimulationReport]:
        return self._service.replay(project, report)

    def proof(
        self, project: GameProject
    ) -> AuthoringResult[ProofingProjection]:
        return self._service.proof(project)


def _default_service() -> AuthoringServiceProtocol:
    return AuthoringService()
