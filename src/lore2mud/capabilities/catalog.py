"""Engine-shipped immutable capability catalog and implementation registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cmp_to_key
import re
from typing import Protocol, runtime_checkable

from lore2mud.capabilities.contracts import (
    CapabilityDescriptor,
    CapabilityDiagnostic,
    CapabilityDiagnosticCode,
    CapabilityEffectResult,
    CapabilityExecutionContext,
    CapabilityIntent,
    CapabilityPlayerViewEntry,
    CapabilitySafetyLevel,
    CapabilityStateEntry,
    CapabilityTurnObservation,
)
from lore2mud.capabilities.semver import (
    SemanticVersion,
    VersionRequirement,
    compare_precedence,
)
from lore2mud.capabilities.serialization import (
    CapabilitySchemaError,
    CapabilitySerializationError,
    canonical_json_bytes,
    capability_value_to_document,
    parse_canonical_json_object,
    sha256_bytes,
    validate_json_schema,
    validate_schema_contract,
)


_STABLE_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_NAMESPACE_RE = re.compile(
    r"^[a-z][a-z0-9_]{0,63}(?:\.[a-z][a-z0-9_]{0,63})*$"
)


class CapabilityCatalogError(ValueError):
    """Raised when static catalog bytes cannot form a safe immutable catalog."""

    def __init__(self, diagnostics: tuple[CapabilityDiagnostic, ...]) -> None:
        self.diagnostics = sort_capability_diagnostics(diagnostics)
        message = "; ".join(diagnostic.message for diagnostic in self.diagnostics)
        super().__init__(message or "capability catalog is invalid")


@dataclass(frozen=True, slots=True)
class CapabilityImplementationContract:
    capability_id: str
    version: SemanticVersion
    action_ids: tuple[str, ...] = ()
    observer_ids: tuple[str, ...] = ()
    predicate_ids: tuple[str, ...] = ()
    effect_ids: tuple[str, ...] = ()
    event_ids: tuple[str, ...] = ()
    migration_ids: tuple[str, ...] = ()


@runtime_checkable
class CapabilityImplementation(Protocol):
    @property
    def contract(self) -> CapabilityImplementationContract: ...

    def apply(
        self,
        intent: CapabilityIntent,
        state: CapabilityStateEntry,
        context: CapabilityExecutionContext,
    ) -> CapabilityEffectResult: ...

    def observe(
        self,
        observation: CapabilityTurnObservation,
        state: CapabilityStateEntry,
        context: CapabilityExecutionContext,
    ) -> CapabilityEffectResult: ...

    def project(
        self,
        state: CapabilityStateEntry,
        context: CapabilityExecutionContext,
    ) -> CapabilityPlayerViewEntry: ...

    def evaluate_predicate(
        self,
        predicate_id: str,
        state: CapabilityStateEntry,
        context: CapabilityExecutionContext,
    ) -> bool: ...

    def migrate(
        self,
        migration_id: str,
        state: CapabilityStateEntry,
        context: CapabilityExecutionContext,
    ) -> CapabilityStateEntry: ...


@dataclass(frozen=True, slots=True)
class CapabilityImplementationBinding:
    descriptor: CapabilityDescriptor
    implementation: CapabilityImplementation


@dataclass(frozen=True, slots=True)
class CapabilityImplementationRegistry:
    bindings: tuple[CapabilityImplementationBinding, ...] = ()

    def __post_init__(self) -> None:
        if type(self.bindings) is not tuple:
            raise CapabilityCatalogError(
                (_descriptor_diagnostic("implementation registry must be tuple-backed"),)
            )
        ordered = tuple(sorted(self.bindings, key=cmp_to_key(_compare_bindings)))
        object.__setattr__(self, "bindings", ordered)
        diagnostics: list[CapabilityDiagnostic] = []
        seen: list[tuple[str, SemanticVersion]] = []
        for binding in ordered:
            descriptor = binding.descriptor
            if not isinstance(descriptor, CapabilityDescriptor):
                diagnostics.append(_descriptor_diagnostic("registry binding has no descriptor"))
                continue
            for capability_id, version in seen:
                if capability_id == descriptor.capability_id and compare_precedence(
                    version, descriptor.version
                ) == 0:
                    diagnostics.append(
                        CapabilityDiagnostic(
                            code=CapabilityDiagnosticCode.CAPABILITY_CATALOG_DUPLICATE,
                            capability_id=descriptor.capability_id,
                            message=(
                                "implementation registry contains equal-precedence bindings for "
                                f"{descriptor.capability_id}@{descriptor.version}"
                            ),
                        )
                    )
            seen.append((descriptor.capability_id, descriptor.version))
            diagnostics.extend(_validate_binding(binding))
        if diagnostics:
            raise CapabilityCatalogError(tuple(diagnostics))

    def binding(
        self,
        capability_id: str,
        version: SemanticVersion,
    ) -> CapabilityImplementationBinding | None:
        for binding in self.bindings:
            if (
                binding.descriptor.capability_id == capability_id
                and binding.descriptor.version == version
            ):
                return binding
        return None

    def get(
        self,
        capability_id: str,
        version: SemanticVersion,
    ) -> CapabilityImplementation | None:
        binding = self.binding(capability_id, version)
        return None if binding is None else binding.implementation

    def with_binding(
        self,
        binding: CapabilityImplementationBinding,
    ) -> CapabilityImplementationRegistry:
        return CapabilityImplementationRegistry(self.bindings + (binding,))


@dataclass(frozen=True, slots=True)
class CapabilityCatalog:
    descriptors: tuple[CapabilityDescriptor, ...]
    implementation_registry: CapabilityImplementationRegistry = field(
        default_factory=CapabilityImplementationRegistry
    )
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.descriptors) is not tuple:
            raise CapabilityCatalogError(
                (_descriptor_diagnostic("capability catalog must be tuple-backed"),)
            )
        ordered = tuple(sorted(self.descriptors, key=cmp_to_key(_compare_descriptors)))
        object.__setattr__(self, "descriptors", ordered)
        diagnostics: list[CapabilityDiagnostic] = []
        seen: list[CapabilityDescriptor] = []
        for descriptor in ordered:
            diagnostics.extend(validate_capability_descriptor(descriptor))
            for previous in seen:
                if (
                    previous.capability_id == descriptor.capability_id
                    and compare_precedence(previous.version, descriptor.version) == 0
                ):
                    build_note = (
                        " with different build metadata"
                        if previous.version.build != descriptor.version.build
                        else ""
                    )
                    diagnostics.append(
                        CapabilityDiagnostic(
                            code=CapabilityDiagnosticCode.CAPABILITY_CATALOG_DUPLICATE,
                            capability_id=descriptor.capability_id,
                            message=(
                                "catalog contains duplicate equal-precedence version "
                                f"{descriptor.capability_id}@{descriptor.version}{build_note}"
                            ),
                        )
                    )
            seen.append(descriptor)
            binding = self.implementation_registry.binding(
                descriptor.capability_id,
                descriptor.version,
            )
            if binding is None:
                diagnostics.append(
                    CapabilityDiagnostic(
                        code=CapabilityDiagnosticCode.CAPABILITY_IMPLEMENTATION_MISSING,
                        capability_id=descriptor.capability_id,
                        message=(
                            "catalog has no engine-shipped implementation for "
                            f"{descriptor.capability_id}@{descriptor.version}"
                        ),
                    )
                )
            elif binding.descriptor != descriptor:
                diagnostics.append(
                    _descriptor_diagnostic(
                        "catalog descriptor does not match its implementation binding",
                        descriptor.capability_id,
                    )
                )
        descriptor_keys = {(item.capability_id, item.version) for item in ordered}
        for binding in self.implementation_registry.bindings:
            key = (binding.descriptor.capability_id, binding.descriptor.version)
            if key not in descriptor_keys:
                diagnostics.append(
                    _descriptor_diagnostic(
                        "implementation registry contains a descriptor outside the catalog",
                        binding.descriptor.capability_id,
                    )
                )
        if diagnostics:
            raise CapabilityCatalogError(tuple(diagnostics))
        document = {
            "format_version": 1,
            "descriptors": [capability_value_to_document(item) for item in ordered],
        }
        object.__setattr__(self, "fingerprint", sha256_bytes(canonical_json_bytes(document)))

    @classmethod
    def from_bindings(
        cls,
        bindings: tuple[CapabilityImplementationBinding, ...],
    ) -> CapabilityCatalog:
        registry = CapabilityImplementationRegistry(bindings)
        return cls(tuple(binding.descriptor for binding in registry.bindings), registry)

    def get(
        self,
        capability_id: str,
        version: SemanticVersion,
    ) -> CapabilityDescriptor | None:
        for descriptor in self.descriptors:
            if descriptor.capability_id == capability_id and descriptor.version == version:
                return descriptor
        return None

    def versions(self, capability_id: str) -> tuple[CapabilityDescriptor, ...]:
        return tuple(
            descriptor
            for descriptor in self.descriptors
            if descriptor.capability_id == capability_id
        )

    def implementation(
        self,
        capability_id: str,
        version: SemanticVersion,
    ) -> CapabilityImplementation | None:
        return self.implementation_registry.get(capability_id, version)


def validate_capability_descriptor(
    descriptor: CapabilityDescriptor,
) -> tuple[CapabilityDiagnostic, ...]:
    diagnostics: list[CapabilityDiagnostic] = []
    if not isinstance(descriptor, CapabilityDescriptor):
        return (_descriptor_diagnostic("catalog entry is not a CapabilityDescriptor"),)
    capability_id = descriptor.capability_id
    if descriptor.format_version != 1:
        diagnostics.append(_descriptor_diagnostic("descriptor format_version must be 1", capability_id))
    if not is_stable_id(capability_id):
        diagnostics.append(_descriptor_diagnostic("capability_id must be a stable ID", capability_id))
    if not isinstance(descriptor.version, SemanticVersion):
        diagnostics.append(_descriptor_diagnostic("descriptor version must be SemanticVersion", capability_id))
    if (
        type(descriptor.state_namespace) is not str
        or _NAMESPACE_RE.fullmatch(descriptor.state_namespace) is None
    ):
        diagnostics.append(
            _descriptor_diagnostic("state_namespace must use stable dotted segments", capability_id)
        )
    if not isinstance(descriptor.safety_level, CapabilitySafetyLevel):
        diagnostics.append(_descriptor_diagnostic("safety_level is invalid", capability_id))

    collections = (
        ("actions", descriptor.actions),
        ("observers", descriptor.observers),
        ("predicates", descriptor.predicates),
        ("effects", descriptor.effects),
        ("events", descriptor.events),
        ("dependencies", descriptor.dependencies),
        ("conflicts", descriptor.conflicts),
        ("migrations", descriptor.migrations),
    )
    for name, values in collections:
        if type(values) is not tuple:
            diagnostics.append(_descriptor_diagnostic(f"{name} must be tuple-backed", capability_id))

    schema_values = (
        ("state_schema", descriptor.state_schema),
        ("player_view_schema", descriptor.player_view_schema),
    )
    for name, schema in schema_values:
        try:
            validate_schema_contract(schema)
        except (CapabilitySchemaError, CapabilitySerializationError, TypeError) as exc:
            diagnostics.append(
                _descriptor_diagnostic(f"{name} is invalid: {exc}", capability_id)
            )
    try:
        initial_state = parse_canonical_json_object(descriptor.initial_state)
        validate_json_schema(initial_state, descriptor.state_schema)
    except (CapabilitySchemaError, CapabilitySerializationError, TypeError) as exc:
        diagnostics.append(
            CapabilityDiagnostic(
                code=CapabilityDiagnosticCode.CAPABILITY_STATE_INVALID,
                capability_id=capability_id,
                message=f"initial capability state is invalid: {exc}",
            )
        )

    id_groups = (
        ("action", tuple(item.action_id for item in descriptor.actions)),
        ("observer", tuple(item.observer_id for item in descriptor.observers)),
        ("predicate", tuple(item.predicate_id for item in descriptor.predicates)),
        ("effect", tuple(item.effect_id for item in descriptor.effects)),
        ("event", tuple(item.event_id for item in descriptor.events)),
        ("migration", tuple(item.migration_id for item in descriptor.migrations)),
    )
    known: dict[str, set[str]] = {}
    for kind, identifiers in id_groups:
        known[kind] = set(identifiers)
        if len(known[kind]) != len(identifiers):
            diagnostics.append(_descriptor_diagnostic(f"duplicate {kind} IDs", capability_id))
        if any(not is_stable_id(identifier) for identifier in identifiers):
            diagnostics.append(_descriptor_diagnostic(f"invalid {kind} stable ID", capability_id))

    for action in descriptor.actions:
        diagnostics.extend(_validate_schema_field(action.parameters_schema, capability_id, "action"))
        diagnostics.extend(
            _validate_declared_references(
                capability_id,
                f"action {action.action_id}",
                action.predicate_ids,
                action.effect_ids,
                action.event_ids,
                known,
            )
        )
    for observer in descriptor.observers:
        if any(not is_stable_id(event_type) for event_type in observer.event_types):
            diagnostics.append(
                _descriptor_diagnostic(
                    f"observer {observer.observer_id} has invalid event type",
                    capability_id,
                )
            )
        diagnostics.extend(
            _validate_declared_references(
                capability_id,
                f"observer {observer.observer_id}",
                observer.predicate_ids,
                observer.effect_ids,
                observer.event_ids,
                known,
            )
        )
    for predicate in descriptor.predicates:
        if predicate.parameters_schema is not None:
            diagnostics.extend(
                _validate_schema_field(predicate.parameters_schema, capability_id, "predicate")
            )
    for effect in descriptor.effects:
        diagnostics.extend(_validate_schema_field(effect.payload_schema, capability_id, "effect"))
    for event in descriptor.events:
        diagnostics.extend(_validate_schema_field(event.payload_schema, capability_id, "event"))

    dependency_ids = tuple(item.capability_id for item in descriptor.dependencies)
    if len(set(dependency_ids)) != len(dependency_ids):
        diagnostics.append(_descriptor_diagnostic("duplicate dependency IDs", capability_id))
    for dependency in descriptor.dependencies:
        if (
            not is_stable_id(dependency.capability_id)
            or dependency.capability_id == capability_id
            or not isinstance(dependency.requirement, VersionRequirement)
        ):
            diagnostics.append(_descriptor_diagnostic("dependency ID is invalid", capability_id))
    conflict_ids = tuple(item.capability_id for item in descriptor.conflicts)
    if len(set(conflict_ids)) != len(conflict_ids):
        diagnostics.append(_descriptor_diagnostic("duplicate conflict IDs", capability_id))
    for conflict in descriptor.conflicts:
        if (
            not is_stable_id(conflict.capability_id)
            or conflict.capability_id == capability_id
            or (
                conflict.requirement is not None
                and not isinstance(conflict.requirement, VersionRequirement)
            )
        ):
            diagnostics.append(_descriptor_diagnostic("conflict ID is invalid", capability_id))
    for migration in descriptor.migrations:
        if compare_precedence(migration.from_version, migration.to_version) >= 0:
            diagnostics.append(_descriptor_diagnostic("migration versions must increase", capability_id))
        if migration.to_version != descriptor.version:
            diagnostics.append(
                _descriptor_diagnostic(
                    "migration target must equal the declaring descriptor version",
                    capability_id,
                )
            )
    return sort_capability_diagnostics(tuple(diagnostics))


def is_stable_id(value: object) -> bool:
    return type(value) is str and _STABLE_ID_RE.fullmatch(value) is not None


def descriptor_fingerprint(descriptor: CapabilityDescriptor) -> str:
    return sha256_bytes(canonical_json_bytes(capability_value_to_document(descriptor)))


def sort_capability_diagnostics(
    diagnostics: tuple[CapabilityDiagnostic, ...] | list[CapabilityDiagnostic],
) -> tuple[CapabilityDiagnostic, ...]:
    return tuple(
        sorted(
            diagnostics,
            key=lambda value: (
                value.code.value,
                value.capability_id or "",
                value.requirement or "",
                value.json_pointer,
                value.related_capability_ids,
                value.message,
            ),
        )
    )


def _validate_binding(binding: CapabilityImplementationBinding) -> tuple[CapabilityDiagnostic, ...]:
    descriptor = binding.descriptor
    capability_id = descriptor.capability_id
    implementation = binding.implementation
    if not isinstance(implementation, CapabilityImplementation):
        return (
            CapabilityDiagnostic(
                code=CapabilityDiagnosticCode.CAPABILITY_IMPLEMENTATION_MISSING,
                capability_id=capability_id,
                message=f"implementation for {capability_id}@{descriptor.version} is incomplete",
            ),
        )
    try:
        contract = implementation.contract
    except (AttributeError, RuntimeError) as exc:
        return (
            CapabilityDiagnostic(
                code=CapabilityDiagnosticCode.CAPABILITY_IMPLEMENTATION_MISSING,
                capability_id=capability_id,
                message=f"implementation contract is unavailable: {exc}",
            ),
        )
    diagnostics: list[CapabilityDiagnostic] = []
    if not isinstance(contract, CapabilityImplementationContract):
        diagnostics.append(_descriptor_diagnostic("implementation contract has wrong type", capability_id))
        return tuple(diagnostics)
    if contract.capability_id != capability_id or contract.version != descriptor.version:
        diagnostics.append(
            _descriptor_diagnostic("implementation contract ID/version does not match descriptor", capability_id)
        )
    expected = {
        "action": tuple(item.action_id for item in descriptor.actions),
        "observer": tuple(item.observer_id for item in descriptor.observers),
        "predicate": tuple(item.predicate_id for item in descriptor.predicates),
        "effect": tuple(item.effect_id for item in descriptor.effects),
        "event": tuple(item.event_id for item in descriptor.events),
        "migration": tuple(item.migration_id for item in descriptor.migrations),
    }
    actual = {
        "action": contract.action_ids,
        "observer": contract.observer_ids,
        "predicate": contract.predicate_ids,
        "effect": contract.effect_ids,
        "event": contract.event_ids,
        "migration": contract.migration_ids,
    }
    for kind, identifiers in actual.items():
        if type(identifiers) is not tuple or len(set(identifiers)) != len(identifiers):
            diagnostics.append(_descriptor_diagnostic(f"implementation {kind} IDs are invalid", capability_id))
            continue
        if any(not is_stable_id(identifier) for identifier in identifiers):
            diagnostics.append(_descriptor_diagnostic(f"implementation {kind} ID is invalid", capability_id))
        if set(identifiers) != set(expected[kind]):
            diagnostics.append(
                _descriptor_diagnostic(
                    f"implementation {kind} IDs do not match descriptor",
                    capability_id,
                )
            )
    return tuple(diagnostics)


def _validate_schema_field(
    schema: object,
    capability_id: str,
    kind: str,
) -> tuple[CapabilityDiagnostic, ...]:
    try:
        validate_schema_contract(schema)  # type: ignore[arg-type]
    except (CapabilitySchemaError, CapabilitySerializationError, TypeError) as exc:
        return (_descriptor_diagnostic(f"{kind} schema is invalid: {exc}", capability_id),)
    return ()


def _validate_declared_references(
    capability_id: str,
    owner: str,
    predicate_ids: tuple[str, ...],
    effect_ids: tuple[str, ...],
    event_ids: tuple[str, ...],
    known: dict[str, set[str]],
) -> tuple[CapabilityDiagnostic, ...]:
    diagnostics: list[CapabilityDiagnostic] = []
    for kind, identifiers in (
        ("predicate", predicate_ids),
        ("effect", effect_ids),
        ("event", event_ids),
    ):
        if type(identifiers) is not tuple or len(set(identifiers)) != len(identifiers):
            diagnostics.append(_descriptor_diagnostic(f"{owner} has invalid {kind} references", capability_id))
        elif not set(identifiers).issubset(known[kind]):
            diagnostics.append(_descriptor_diagnostic(f"{owner} references unknown {kind}", capability_id))
    return tuple(diagnostics)


def _descriptor_diagnostic(
    message: str,
    capability_id: str | None = None,
) -> CapabilityDiagnostic:
    return CapabilityDiagnostic(
        code=CapabilityDiagnosticCode.CAPABILITY_DESCRIPTOR_INVALID,
        capability_id=capability_id,
        message=message,
    )


def _compare_descriptors(left: CapabilityDescriptor, right: CapabilityDescriptor) -> int:
    if left.capability_id < right.capability_id:
        return -1
    if left.capability_id > right.capability_id:
        return 1
    precedence = compare_precedence(left.version, right.version)
    if precedence:
        return -precedence
    left_text = str(left.version)
    right_text = str(right.version)
    return -1 if left_text < right_text else (1 if left_text > right_text else 0)


def _compare_bindings(
    left: CapabilityImplementationBinding,
    right: CapabilityImplementationBinding,
) -> int:
    return _compare_descriptors(left.descriptor, right.descriptor)
