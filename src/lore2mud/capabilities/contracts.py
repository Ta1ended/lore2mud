"""Frozen transport-neutral contracts for V2-3 capability modules."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias

from lore2mud.capabilities.semver import SemanticVersion, VersionRequirement


JsonScalar: TypeAlias = str | int | bool | None


@dataclass(frozen=True, slots=True)
class CanonicalJsonObject:
    """An immutable canonical UTF-8 JSON object, including its final LF."""

    canonical_bytes: bytes

    def __post_init__(self) -> None:
        if type(self.canonical_bytes) is not bytes:
            raise TypeError("canonical_bytes must be immutable bytes")


class CapabilitySafetyLevel(str, Enum):
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"


@dataclass(frozen=True, slots=True)
class CapabilityActionDescriptor:
    action_id: str
    parameters_schema: CanonicalJsonObject
    predicate_ids: tuple[str, ...] = ()
    effect_ids: tuple[str, ...] = ()
    event_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CapabilityObserverDescriptor:
    observer_id: str
    event_types: tuple[str, ...] = ()
    predicate_ids: tuple[str, ...] = ()
    effect_ids: tuple[str, ...] = ()
    event_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CapabilityPredicateDescriptor:
    predicate_id: str
    parameters_schema: CanonicalJsonObject | None = None


@dataclass(frozen=True, slots=True)
class CapabilityEffectDescriptor:
    effect_id: str
    payload_schema: CanonicalJsonObject


@dataclass(frozen=True, slots=True)
class CapabilityEventDescriptor:
    event_id: str
    payload_schema: CanonicalJsonObject


@dataclass(frozen=True, slots=True)
class CapabilityDependencyDescriptor:
    capability_id: str
    requirement: VersionRequirement


@dataclass(frozen=True, slots=True)
class CapabilityConflictDescriptor:
    capability_id: str
    requirement: VersionRequirement | None = None


@dataclass(frozen=True, slots=True)
class CapabilityMigrationDescriptor:
    migration_id: str
    from_version: SemanticVersion
    to_version: SemanticVersion


@dataclass(frozen=True, slots=True)
class CapabilityDescriptor:
    format_version: int
    capability_id: str
    version: SemanticVersion
    safety_level: CapabilitySafetyLevel
    state_namespace: str
    initial_state: CanonicalJsonObject
    state_schema: CanonicalJsonObject
    actions: tuple[CapabilityActionDescriptor, ...]
    observers: tuple[CapabilityObserverDescriptor, ...]
    predicates: tuple[CapabilityPredicateDescriptor, ...]
    effects: tuple[CapabilityEffectDescriptor, ...]
    events: tuple[CapabilityEventDescriptor, ...]
    player_view_schema: CanonicalJsonObject
    dependencies: tuple[CapabilityDependencyDescriptor, ...] = ()
    conflicts: tuple[CapabilityConflictDescriptor, ...] = ()
    migrations: tuple[CapabilityMigrationDescriptor, ...] = ()


@dataclass(frozen=True, slots=True)
class CapabilityIntent:
    capability_id: str
    action_id: str
    parameters: CanonicalJsonObject


@dataclass(frozen=True, slots=True)
class CapabilityEffectData:
    effect_id: str
    payload: CanonicalJsonObject


@dataclass(frozen=True, slots=True)
class CapabilityEventData:
    capability_id: str
    event_id: str
    payload: CanonicalJsonObject


@dataclass(frozen=True, slots=True)
class CapabilityStateEntry:
    capability_id: str
    version: SemanticVersion
    namespace: str
    state: CanonicalJsonObject


@dataclass(frozen=True, slots=True)
class CapabilityStateVersion:
    capability_id: str
    version: SemanticVersion


@dataclass(frozen=True, slots=True)
class CapabilityExecutionContext:
    seed: int
    clock: int
    turn_index: int
    event_sequence: int
    player_view: CanonicalJsonObject


@dataclass(frozen=True, slots=True)
class CapabilityTurnObservation:
    intent: CanonicalJsonObject
    events: tuple[CanonicalJsonObject, ...]
    before_view: CanonicalJsonObject
    after_view: CanonicalJsonObject


@dataclass(frozen=True, slots=True)
class CapabilityEffectResult:
    next_state: CanonicalJsonObject
    effects: tuple[CapabilityEffectData, ...] = ()
    events: tuple[CapabilityEventData, ...] = ()


@dataclass(frozen=True, slots=True)
class CapabilityPlayerViewEntry:
    capability_id: str
    version: SemanticVersion
    view: CanonicalJsonObject
    admissible_intents: tuple[CapabilityIntent, ...] = ()


@dataclass(frozen=True, slots=True)
class CapabilityDependencyEdge:
    dependent_capability_id: str
    dependency_capability_id: str
    requirement: VersionRequirement


@dataclass(frozen=True, slots=True)
class CapabilityMigrationStep:
    capability_id: str
    from_version: SemanticVersion
    to_version: SemanticVersion
    migration_id: str


@dataclass(frozen=True, slots=True)
class ResolvedCapability:
    capability_id: str
    version: SemanticVersion
    safety_level: CapabilitySafetyLevel
    state_namespace: str
    descriptor_sha256: str


@dataclass(frozen=True, slots=True)
class ResolvedCapabilityPlan:
    format_version: int
    requirement_ids: tuple[str, ...]
    capabilities: tuple[ResolvedCapability, ...]
    dependency_edges: tuple[CapabilityDependencyEdge, ...]
    migrations: tuple[CapabilityMigrationStep, ...]
    initial_states: tuple[CapabilityStateEntry, ...]
    catalog_sha256: str
    fingerprint: str


class CapabilityDiagnosticCode(str, Enum):
    CAPABILITY_NOT_FOUND = "capability_not_found"
    CAPABILITY_VERSION_UNSATISFIED = "capability_version_unsatisfied"
    CAPABILITY_CATALOG_DUPLICATE = "capability_catalog_duplicate"
    CAPABILITY_DEPENDENCY_CYCLE = "capability_dependency_cycle"
    CAPABILITY_CONFLICT = "capability_conflict"
    CAPABILITY_NAMESPACE_OVERLAP = "capability_namespace_overlap"
    CAPABILITY_SAFETY_DENIED = "capability_safety_denied"
    CAPABILITY_STATE_INVALID = "capability_state_invalid"
    CAPABILITY_IMPLEMENTATION_MISSING = "capability_implementation_missing"
    CAPABILITY_MIGRATION_UNAVAILABLE = "capability_migration_unavailable"
    CAPABILITY_INTENT_INVALID = "capability_intent_invalid"
    CAPABILITY_INTENT_INADMISSIBLE = "capability_intent_inadmissible"
    CAPABILITY_DESCRIPTOR_INVALID = "capability_descriptor_invalid"


@dataclass(frozen=True, slots=True)
class CapabilityDiagnostic:
    code: CapabilityDiagnosticCode
    message: str
    capability_id: str | None = None
    requirement: str | None = None
    json_pointer: str = ""
    related_capability_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CapabilityResolutionResult:
    plan: ResolvedCapabilityPlan | None
    diagnostics: tuple[CapabilityDiagnostic, ...] = ()

    @property
    def ok(self) -> bool:
        return self.plan is not None and not self.diagnostics


@dataclass(frozen=True, slots=True)
class CapabilityCheckpoint:
    format_version: int
    plan: ResolvedCapabilityPlan
    plan_sha256: str
    save_document: CanonicalJsonObject
    save_sha256: str
    states: tuple[CapabilityStateEntry, ...]
    state_sha256: str
    seed: int
    clock: int
    event_sequence: int
    view_sha256: str
    fingerprint: str

