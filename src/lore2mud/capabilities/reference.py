"""Engine-shipped synthetic capability used to prove the V2-3 runtime surface."""

from __future__ import annotations

from lore2mud.capabilities.catalog import (
    CapabilityCatalog,
    CapabilityImplementationBinding,
    CapabilityImplementationContract,
    CapabilityImplementationRegistry,
)
from lore2mud.capabilities.contracts import (
    CapabilityActionDescriptor,
    CapabilityDescriptor,
    CapabilityEffectData,
    CapabilityEffectDescriptor,
    CapabilityEffectResult,
    CapabilityEventData,
    CapabilityEventDescriptor,
    CapabilityExecutionContext,
    CapabilityIntent,
    CapabilityPlayerViewEntry,
    CapabilityPredicateDescriptor,
    CapabilitySafetyLevel,
    CapabilityStateEntry,
    CapabilityTurnObservation,
)
from lore2mud.capabilities.runtime import (
    CapabilityIntentInadmissibleError,
    CapabilityRuntimeError,
)
from lore2mud.capabilities.semver import SemanticVersion
from lore2mud.capabilities.serialization import (
    canonical_json_object,
    parse_canonical_json_object,
)


REFERENCE_COUNTER_ID = "reference_counter"
REFERENCE_COUNTER_VERSION = SemanticVersion.parse("1.0.0")
REFERENCE_COUNTER_NAMESPACE = "reference_counter"
_COUNT_NONZERO_PREDICATE = "count_nonzero"
_SET_COUNT_EFFECT = "set_count"
_COUNTER_CHANGED_EVENT = "counter_changed"

_EMPTY_OBJECT_SCHEMA = canonical_json_object(
    {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }
)
_STATE_SCHEMA = canonical_json_object(
    {
        "type": "object",
        "properties": {
            "count": {"type": "integer", "minimum": 0, "maximum": 1000},
        },
        "required": ["count"],
        "additionalProperties": False,
    }
)
_INCREMENT_PARAMETERS_SCHEMA = canonical_json_object(
    {
        "type": "object",
        "properties": {
            "amount": {"type": "integer", "minimum": 1, "maximum": 10},
        },
        "required": ["amount"],
        "additionalProperties": False,
    }
)
_CHANGE_SCHEMA = canonical_json_object(
    {
        "type": "object",
        "properties": {
            "old": {"type": "integer", "minimum": 0, "maximum": 1000},
            "new": {"type": "integer", "minimum": 0, "maximum": 1000},
            "reason": {"type": "string", "enum": ["increment", "reset"]},
        },
        "required": ["old", "new", "reason"],
        "additionalProperties": False,
    }
)
_PLAYER_VIEW_SCHEMA = canonical_json_object(
    {
        "type": "object",
        "properties": {
            "count": {"type": "integer", "minimum": 0, "maximum": 1000},
        },
        "required": ["count"],
        "additionalProperties": False,
    }
)


REFERENCE_COUNTER_DESCRIPTOR = CapabilityDescriptor(
    format_version=1,
    capability_id=REFERENCE_COUNTER_ID,
    version=REFERENCE_COUNTER_VERSION,
    safety_level=CapabilitySafetyLevel.L1,
    state_namespace=REFERENCE_COUNTER_NAMESPACE,
    initial_state=canonical_json_object({"count": 0}),
    state_schema=_STATE_SCHEMA,
    actions=(
        CapabilityActionDescriptor(
            action_id="increment",
            parameters_schema=_INCREMENT_PARAMETERS_SCHEMA,
            effect_ids=(_SET_COUNT_EFFECT,),
            event_ids=(_COUNTER_CHANGED_EVENT,),
        ),
        CapabilityActionDescriptor(
            action_id="reset",
            parameters_schema=_EMPTY_OBJECT_SCHEMA,
            predicate_ids=(_COUNT_NONZERO_PREDICATE,),
            effect_ids=(_SET_COUNT_EFFECT,),
            event_ids=(_COUNTER_CHANGED_EVENT,),
        ),
    ),
    observers=(),
    predicates=(
        CapabilityPredicateDescriptor(_COUNT_NONZERO_PREDICATE),
    ),
    effects=(
        CapabilityEffectDescriptor(_SET_COUNT_EFFECT, _CHANGE_SCHEMA),
    ),
    events=(
        CapabilityEventDescriptor(_COUNTER_CHANGED_EVENT, _CHANGE_SCHEMA),
    ),
    player_view_schema=_PLAYER_VIEW_SCHEMA,
)


class ReferenceCounterImplementation:
    """Pure counter rules with no World, RNG, filesystem, or host-I/O access."""

    contract = CapabilityImplementationContract(
        capability_id=REFERENCE_COUNTER_ID,
        version=REFERENCE_COUNTER_VERSION,
        action_ids=("increment", "reset"),
        observer_ids=(),
        predicate_ids=(_COUNT_NONZERO_PREDICATE,),
        effect_ids=(_SET_COUNT_EFFECT,),
        event_ids=(_COUNTER_CHANGED_EVENT,),
        migration_ids=(),
    )

    def apply(
        self,
        intent: CapabilityIntent,
        state: CapabilityStateEntry,
        context: CapabilityExecutionContext,
    ) -> CapabilityEffectResult:
        del context
        count = _count(state)
        parameters = parse_canonical_json_object(intent.parameters)
        if intent.action_id == "increment":
            amount = parameters.get("amount")
            if type(amount) is not int or not 1 <= amount <= 10:
                raise CapabilityRuntimeError("reference increment parameters are invalid")
            next_count = count + amount
            if next_count > 1000:
                raise CapabilityIntentInadmissibleError(
                    "reference counter would exceed its maximum"
                )
            return _change_result(count, next_count, "increment")
        if intent.action_id == "reset":
            if parameters:
                raise CapabilityRuntimeError("reference reset parameters are invalid")
            if count == 0:
                raise CapabilityIntentInadmissibleError(
                    "reference counter is already zero"
                )
            return _change_result(count, 0, "reset")
        raise CapabilityRuntimeError("reference counter action is unknown")

    def observe(
        self,
        observation: CapabilityTurnObservation,
        state: CapabilityStateEntry,
        context: CapabilityExecutionContext,
    ) -> CapabilityEffectResult:
        del observation, context
        return CapabilityEffectResult(state.state)

    def project(
        self,
        state: CapabilityStateEntry,
        context: CapabilityExecutionContext,
    ) -> CapabilityPlayerViewEntry:
        del context
        count = _count(state)
        increment_limit = min(10, 1000 - count)
        intents = tuple(
            CapabilityIntent(
                REFERENCE_COUNTER_ID,
                "increment",
                canonical_json_object({"amount": amount}),
            )
            for amount in range(1, increment_limit + 1)
        )
        if count:
            intents += (
                CapabilityIntent(
                    REFERENCE_COUNTER_ID,
                    "reset",
                    canonical_json_object({}),
                ),
            )
        return CapabilityPlayerViewEntry(
            capability_id=REFERENCE_COUNTER_ID,
            version=REFERENCE_COUNTER_VERSION,
            view=canonical_json_object({"count": count}),
            admissible_intents=intents,
        )

    def evaluate_predicate(
        self,
        predicate_id: str,
        state: CapabilityStateEntry,
        context: CapabilityExecutionContext,
    ) -> bool:
        del context
        if predicate_id == _COUNT_NONZERO_PREDICATE:
            return _count(state) != 0
        raise CapabilityRuntimeError("reference counter predicate is unknown")

    def migrate(
        self,
        migration_id: str,
        state: CapabilityStateEntry,
        context: CapabilityExecutionContext,
    ) -> CapabilityStateEntry:
        del migration_id, state, context
        raise CapabilityRuntimeError("reference counter has no migrations")


REFERENCE_COUNTER_IMPLEMENTATION = ReferenceCounterImplementation()
REFERENCE_COUNTER_BINDING = CapabilityImplementationBinding(
    REFERENCE_COUNTER_DESCRIPTOR,
    REFERENCE_COUNTER_IMPLEMENTATION,
)
ENGINE_CAPABILITY_BINDINGS = (REFERENCE_COUNTER_BINDING,)


def engine_capability_registry() -> CapabilityImplementationRegistry:
    return CapabilityImplementationRegistry(ENGINE_CAPABILITY_BINDINGS)


def engine_capability_catalog() -> CapabilityCatalog:
    return CapabilityCatalog.from_bindings(ENGINE_CAPABILITY_BINDINGS)


def _count(state: CapabilityStateEntry) -> int:
    if (
        state.capability_id != REFERENCE_COUNTER_ID
        or state.version != REFERENCE_COUNTER_VERSION
        or state.namespace != REFERENCE_COUNTER_NAMESPACE
    ):
        raise CapabilityRuntimeError("reference counter state identity mismatch")
    document = parse_canonical_json_object(state.state, schema=_STATE_SCHEMA)
    count = document.get("count")
    if type(count) is not int:
        raise CapabilityRuntimeError("reference counter state is invalid")
    return count


def _change_result(old: int, new: int, reason: str) -> CapabilityEffectResult:
    payload = canonical_json_object({"old": old, "new": new, "reason": reason})
    return CapabilityEffectResult(
        next_state=canonical_json_object({"count": new}),
        effects=(CapabilityEffectData(_SET_COUNT_EFFECT, payload),),
        events=(
            CapabilityEventData(
                REFERENCE_COUNTER_ID,
                _COUNTER_CHANGED_EVENT,
                payload,
            ),
        ),
    )
