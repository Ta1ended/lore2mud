"""Frozen public contracts for the V2-2 authoring interface."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Generic, TypeVar

from lore2mud.application.contracts import DeterminismContext, GameIntent

if TYPE_CHECKING:
    from lore2mud.capabilities.contracts import (
        CapabilityIntent,
        CapabilityPlayerViewEntry,
        CapabilityStateEntry,
        ResolvedCapabilityPlan,
    )


V1_COMPATIBILITY_PROFILE_ID = "lore2mud.v1.compatibility.fixed"
CAPABILITY_DIAGNOSTIC_CODE = "capability_requirement_unsupported_v2_2"
PREVIEW_IDENTITY_SCOPE = "preview_reproducibility_only"
REPORT_IDENTITY_SCOPE = "simulation_reproducibility_only"
CAPABILITY_PREVIEW_IDENTITY_SCOPE = "capability_preview_reproducibility_only"
CAPABILITY_REPORT_IDENTITY_SCOPE = "capability_simulation_reproducibility_only"


class AuthoringStage(str, Enum):
    BLUEPRINT = "blueprint"
    PROJECT = "project"
    PREVIEW = "preview"
    SIMULATION = "simulation"
    PROOFING = "proofing"
    SERIALIZATION = "serialization"
    PROVENANCE = "provenance"
    ANCHOR = "anchor"
    PACKAGE = "package"
    SEAL = "seal"


class DiagnosticSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class AuthoringStatus(str, Enum):
    SUCCESS = "success"
    REJECTED = "rejected"


class ConditionOutcome(str, Enum):
    WIN = "win"
    LOSS = "loss"


class SimulationOutcome(str, Enum):
    WIN = "win"
    LOSS = "loss"
    UNDETERMINED = "undetermined"


class SimulationConditionKind(str, Enum):
    PLAYER_ALIVE = "player_alive"
    ROOM_ID = "room_id"
    QUEST_COMPLETED = "quest_completed"
    OBJECTIVE_STATUS = "objective_status"
    KNOWLEDGE_STATUS = "knowledge_status"


@dataclass(frozen=True, slots=True)
class AuthorizedSourceSpan:
    source_artifact_id: str
    start_line: int
    start_column: int
    end_line: int
    end_column: int


SourceSpan = AuthorizedSourceSpan


@dataclass(frozen=True, slots=True)
class AuthoringDiagnostic:
    stage: AuthoringStage
    code: str
    severity: DiagnosticSeverity
    artifact_id: str
    json_pointer: str
    message: str
    remediation: str
    source_span: AuthorizedSourceSpan | None = None


@dataclass(frozen=True, slots=True)
class ApprovalRecord:
    approved: bool
    decision_id: str
    approver: str


@dataclass(frozen=True, slots=True)
class PlayLength:
    minimum_minutes: int
    target_minutes: int
    maximum_minutes: int


@dataclass(frozen=True, slots=True)
class AdaptationBoundaries:
    allowed: tuple[str, ...]
    excluded: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AcceptanceScenario:
    scenario_id: str
    description: str
    outcome: ConditionOutcome


@dataclass(frozen=True, slots=True)
class GameBlueprint:
    format_version: int
    blueprint_id: str
    title: str
    approval: ApprovalRecord
    audience: str
    genre: str
    tone: str
    play_length: PlayLength
    adaptation_boundaries: AdaptationBoundaries
    required_game_loops: tuple[str, ...]
    acceptance_scenarios: tuple[AcceptanceScenario, ...]
    capability_requirement_ids: tuple[str, ...]
    asset_requirements: tuple[str, ...]
    provenance_requirements: tuple[str, ...]
    rights_assertions: tuple[str, ...]
    default_determinism: DeterminismContext


@dataclass(frozen=True, slots=True)
class PublicInputDescriptor:
    artifact_id: str
    media_type: str
    label: str
    visibility: str = "public_safe"


@dataclass(frozen=True, slots=True)
class CanonicalContentFile:
    name: str
    sha256: str
    canonical_json: bytes


@dataclass(frozen=True, slots=True)
class CreatorDecision:
    decision_id: str
    statement: str


@dataclass(frozen=True, slots=True)
class TraceRecord:
    trace_id: str
    source_artifact_id: str
    target_artifact_id: str
    decision_id: str


@dataclass(frozen=True, slots=True)
class WorkspaceMetadataEntry:
    key: str
    value: str


@dataclass(frozen=True, slots=True)
class BuildLock:
    input_sha256: str


@dataclass(frozen=True, slots=True)
class GameProject:
    format_version: int
    project_id: str
    blueprint: GameBlueprint
    blueprint_sha256: str
    public_inputs: tuple[PublicInputDescriptor, ...]
    content_files: tuple[CanonicalContentFile, ...]
    creator_decisions: tuple[CreatorDecision, ...]
    trace_records: tuple[TraceRecord, ...]
    build_lock: BuildLock
    workspace_metadata: tuple[WorkspaceMetadataEntry, ...] = ()


@dataclass(frozen=True, slots=True)
class PreviewBuild:
    format_version: int
    preview_id: str
    project_id: str
    blueprint_sha256: str
    project_sha256: str
    engine_version: str
    content_files: tuple[CanonicalContentFile, ...]
    fingerprint: str
    profile_id: str = V1_COMPATIBILITY_PROFILE_ID
    kind: str = "preview"
    sealed: bool = False
    distributable: bool = False
    release_evidence: bool = False
    identity_scope: str = PREVIEW_IDENTITY_SCOPE


@dataclass(frozen=True, slots=True)
class SimulationCondition:
    condition_id: str
    outcome: ConditionOutcome
    kind: SimulationConditionKind
    expected: str | bool


@dataclass(frozen=True, slots=True)
class SimulationRequest:
    format_version: int
    seed: int
    clock: int
    player_name: str
    intents: tuple[GameIntent, ...]
    conditions: tuple[SimulationCondition, ...] = ()
    checkpoint_after_steps: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class IntentFieldDescriptor:
    name: str
    value: str | int | bool | None


@dataclass(frozen=True, slots=True)
class AdmissibleIntentDescriptor:
    descriptor_id: str
    intent: GameIntent
    fields: tuple[IntentFieldDescriptor, ...]


@dataclass(frozen=True, slots=True)
class SimulationTurn:
    index: int
    intent: GameIntent
    status: str
    rejection_code: str | None
    event_types: tuple[str, ...]
    view_sha256: str


WitnessStep = SimulationTurn


@dataclass(frozen=True, slots=True)
class SimulationConditionResult:
    condition: SimulationCondition
    matched: bool


@dataclass(frozen=True, slots=True)
class SimulationCheckpoint:
    after_step: int
    before_state_sha256: str
    loaded_state_sha256: str
    before_view_sha256: str
    loaded_view_sha256: str
    equivalent: bool


@dataclass(frozen=True, slots=True)
class SimulationReport:
    format_version: int
    project_id: str
    blueprint_sha256: str
    project_sha256: str
    preview_fingerprint: str
    request_sha256: str
    engine_version: str
    seed: int
    clock: int
    player_name: str
    initial_state_sha256: str
    final_state_sha256: str
    initial_view_sha256: str
    final_view_sha256: str
    turns: tuple[SimulationTurn, ...]
    condition_results: tuple[SimulationConditionResult, ...]
    outcome: SimulationOutcome
    witness_trace: tuple[WitnessStep, ...]
    replay_verified: bool
    checkpoints: tuple[SimulationCheckpoint, ...]
    fingerprint: str
    identity_scope: str = REPORT_IDENTITY_SCOPE


@dataclass(frozen=True, slots=True)
class CapabilitySimulationRequest:
    format_version: int
    seed: int
    clock: int
    player_name: str
    steps: tuple[GameIntent | CapabilityIntent, ...]
    conditions: tuple[SimulationCondition, ...] = ()
    checkpoint_after_steps: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class CapabilityPreview:
    format_version: int
    base_preview: PreviewBuild
    resolved_plan: "ResolvedCapabilityPlan"
    plan_sha256: str
    initial_states: tuple["CapabilityStateEntry", ...]
    initial_state_sha256: str
    engine_version: str
    fingerprint: str
    kind: str = "capability_preview"
    sealed: bool = False
    distributable: bool = False
    release_evidence: bool = False
    identity_scope: str = CAPABILITY_PREVIEW_IDENTITY_SCOPE


@dataclass(frozen=True, slots=True)
class CapabilitySimulationTurn:
    index: int
    step: GameIntent | CapabilityIntent
    status: str
    rejection_code: str | None
    event_sha256: str
    view_sha256: str
    capability_state_sha256: str
    event_sequence_after: int


CapabilityWitnessStep = CapabilitySimulationTurn


@dataclass(frozen=True, slots=True)
class CapabilitySimulationCheckpoint:
    after_step: int
    checkpoint_sha256: str
    restored_state_sha256: str
    restored_view_sha256: str
    restored_event_sequence: int
    equivalent: bool


@dataclass(frozen=True, slots=True)
class CapabilitySimulationReport:
    format_version: int
    project_id: str
    base_report: SimulationReport
    request_sha256: str
    capability_preview_fingerprint: str
    plan_sha256: str
    initial_capability_state_sha256: str
    final_capability_state_sha256: str
    turns: tuple[CapabilitySimulationTurn, ...]
    witness_trace: tuple[CapabilityWitnessStep, ...]
    capability_event_sha256: str
    capability_view_sha256: str
    replay_verified: bool
    checkpoints: tuple[CapabilitySimulationCheckpoint, ...]
    fingerprint: str
    identity_scope: str = CAPABILITY_REPORT_IDENTITY_SCOPE


@dataclass(frozen=True, slots=True)
class ProofingNode:
    node_id: str
    kind: str
    label: str


@dataclass(frozen=True, slots=True)
class ProofingEdge:
    source_id: str
    target_id: str
    kind: str


@dataclass(frozen=True, slots=True)
class ProofingProjection:
    format_version: int
    project_id: str
    preview_fingerprint: str
    nodes: tuple[ProofingNode, ...]
    edges: tuple[ProofingEdge, ...]
    admissible_intents: tuple[AdmissibleIntentDescriptor, ...]
    diagnostics: tuple[AuthoringDiagnostic, ...] = ()


@dataclass(frozen=True, slots=True)
class CapabilityProofingProjection:
    format_version: int
    project_id: str
    capability_preview_fingerprint: str
    base_proofing: ProofingProjection
    capability_views: tuple["CapabilityPlayerViewEntry", ...]
    fingerprint: str
    diagnostics: tuple[AuthoringDiagnostic, ...] = ()


ArtifactT = TypeVar("ArtifactT")
CapabilityArtifactT = TypeVar("CapabilityArtifactT")


@dataclass(frozen=True, slots=True)
class AuthoringResult(Generic[ArtifactT]):
    format_version: int
    operation: str
    status: AuthoringStatus
    artifact: ArtifactT | None
    diagnostics: tuple[AuthoringDiagnostic, ...]
    exit_code: int

    @property
    def ok(self) -> bool:
        return self.status is AuthoringStatus.SUCCESS


@dataclass(frozen=True, slots=True)
class CapabilityAuthoringResult(Generic[CapabilityArtifactT]):
    format_version: int
    operation: str
    status: AuthoringStatus
    artifact: CapabilityArtifactT | None
    diagnostics: tuple[AuthoringDiagnostic, ...]
    exit_code: int
    kind: str = "capability_authoring_result"

    @property
    def ok(self) -> bool:
        return self.status is AuthoringStatus.SUCCESS
