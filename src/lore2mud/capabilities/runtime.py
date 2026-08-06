"""Deterministic capability execution inside the application turn transaction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from lore2mud.application.contracts import (
    DeterminismContext,
    GameEventKind,
    GameEventPayload,
    GameView,
)
from lore2mud.capabilities.contracts import (
    CanonicalJsonObject,
    CapabilityActionDescriptor,
    CapabilityDescriptor,
    CapabilityEffectData,
    CapabilityEffectResult,
    CapabilityEventData,
    CapabilityExecutionContext,
    CapabilityIntent,
    CapabilityObserverDescriptor,
    CapabilityPlayerViewEntry,
    CapabilityStateEntry,
    CapabilityTurnObservation,
    ResolvedCapability,
    ResolvedCapabilityPlan,
)
from lore2mud.capabilities.serialization import (
    CapabilitySchemaError,
    CapabilitySerializationError,
    canonical_json_object,
    capability_value_to_document,
    parse_canonical_json_object,
)


class CapabilityRuntimeError(RuntimeError):
    """Raised when an engine-owned implementation violates its runtime contract."""


class CapabilityIntentInvalidError(CapabilityRuntimeError):
    rejection_code = "capability_intent_invalid"


class CapabilityIntentInadmissibleError(CapabilityRuntimeError):
    rejection_code = "capability_intent_inadmissible"


_EventDraft = tuple[GameEventKind, GameEventPayload]


@dataclass(frozen=True, slots=True)
class CapabilityRuntimeSnapshot:
    states: tuple[CapabilityStateEntry, ...]


@dataclass(frozen=True, slots=True)
class PreparedCapabilityTurn:
    states: tuple[CapabilityStateEntry, ...]
    effects: tuple[CapabilityEffectData, ...] = ()
    events: tuple[CapabilityEventData, ...] = ()


@dataclass(frozen=True, slots=True)
class _RuntimeBinding:
    resolved: ResolvedCapability
    descriptor: CapabilityDescriptor
    implementation: Any


class CapabilityRuntimeHost:
    """Own namespaced capability state without becoming a second game runtime."""

    def __init__(
        self,
        plan: ResolvedCapabilityPlan,
        implementation_registry: object | None = None,
        *,
        registry: object | None = None,
        states: tuple[CapabilityStateEntry, ...] | None = None,
    ) -> None:
        if type(plan) is not ResolvedCapabilityPlan:
            raise CapabilityRuntimeError("resolved capability plan is invalid")
        if implementation_registry is None:
            implementation_registry = registry
        if implementation_registry is None:
            raise CapabilityRuntimeError("capability implementation registry is invalid")
        binding_method = getattr(implementation_registry, "binding", None)
        if binding_method is None:
            raise CapabilityRuntimeError("capability implementation registry is invalid")

        bindings: list[_RuntimeBinding] = []
        for resolved in plan.capabilities:
            binding = binding_method(resolved.capability_id, resolved.version)
            if binding is None:
                raise CapabilityRuntimeError("resolved capability implementation is missing")
            descriptor = binding.descriptor
            if (
                type(descriptor) is not CapabilityDescriptor
                or descriptor.capability_id != resolved.capability_id
                or descriptor.version != resolved.version
                or descriptor.state_namespace != resolved.state_namespace
            ):
                raise CapabilityRuntimeError("resolved capability descriptor mismatch")
            bindings.append(
                _RuntimeBinding(resolved, descriptor, binding.implementation)
            )

        selected_states = plan.initial_states if states is None else states
        self._plan = plan
        self._bindings = tuple(bindings)
        self._states = self._validate_states(selected_states)

    @property
    def plan(self) -> ResolvedCapabilityPlan:
        return self._plan

    @property
    def states(self) -> tuple[CapabilityStateEntry, ...]:
        return self._states

    def snapshot(self) -> CapabilityRuntimeSnapshot:
        return CapabilityRuntimeSnapshot(self._states)

    def prepare_restore(
        self,
        states: tuple[CapabilityStateEntry, ...],
    ) -> CapabilityRuntimeSnapshot:
        return CapabilityRuntimeSnapshot(self._validate_states(states))

    def restore(self, snapshot: object) -> None:
        # Session only supplies snapshots produced above; assignment must stay infallible.
        self._states = cast(CapabilityRuntimeSnapshot, snapshot).states

    def prepare_turn(
        self,
        intent: object,
        *,
        before_view: GameView,
        after_view: GameView,
        event: _EventDraft | None,
        determinism: DeterminismContext,
        event_sequence: int,
    ) -> PreparedCapabilityTurn:
        context = self._execution_context(
            determinism,
            event_sequence,
            after_view,
        )
        if type(intent) is CapabilityIntent:
            return self._prepare_action(cast(CapabilityIntent, intent), context)
        return self._prepare_observers(
            intent,
            before_view,
            after_view,
            event,
            context,
        )

    def prepared_events(
        self,
        prepared: object,
    ) -> tuple[CapabilityEventData, ...]:
        return cast(PreparedCapabilityTurn, prepared).events

    def prepared_effects(
        self,
        prepared: object,
    ) -> tuple[CapabilityEffectData, ...]:
        return cast(PreparedCapabilityTurn, prepared).effects

    def commit(self, prepared: object) -> None:
        # All validation occurs in prepare_turn/project_view before deferred save I/O.
        self._states = cast(PreparedCapabilityTurn, prepared).states

    def project_view(
        self,
        view: GameView,
        prepared: object | None = None,
        *,
        determinism: DeterminismContext | None = None,
        event_sequence: int = 0,
    ) -> tuple[CapabilityPlayerViewEntry, ...] | None:
        if not self._bindings:
            return None
        states = self._states if prepared is None else cast(PreparedCapabilityTurn, prepared).states
        state_by_id = {state.capability_id: state for state in states}
        context = self._execution_context(
            DeterminismContext() if determinism is None else determinism,
            event_sequence,
            view,
        )
        projected: list[CapabilityPlayerViewEntry] = []
        for binding in self._bindings:
            state = state_by_id[binding.resolved.capability_id]
            try:
                entry = binding.implementation.project(state, context)
            except Exception as exc:
                raise CapabilityRuntimeError("capability projection failed") from exc
            if type(entry) is not CapabilityPlayerViewEntry:
                raise CapabilityRuntimeError("capability projection returned an invalid entry")
            if (
                entry.capability_id != binding.resolved.capability_id
                or entry.version != binding.resolved.version
            ):
                raise CapabilityRuntimeError("capability projection identity mismatch")
            self._validate_canonical_object(
                entry.view,
                binding.descriptor.player_view_schema,
                "capability player view",
            )
            intents = self._validate_admissible_intents(
                entry.admissible_intents,
                binding,
                state,
                context,
            )
            projected.append(
                CapabilityPlayerViewEntry(
                    entry.capability_id,
                    entry.version,
                    entry.view,
                    intents,
                )
            )
        return tuple(projected)

    def _prepare_action(
        self,
        intent: CapabilityIntent,
        context: CapabilityExecutionContext,
    ) -> PreparedCapabilityTurn:
        if (
            type(intent.capability_id) is not str
            or type(intent.action_id) is not str
            or not intent.capability_id
            or not intent.action_id
        ):
            raise CapabilityIntentInvalidError("capability intent identifiers are invalid")
        binding = self._binding_by_id(intent.capability_id)
        if binding is None:
            raise CapabilityIntentInvalidError("capability is not resolved")
        action = next(
            (
                candidate
                for candidate in binding.descriptor.actions
                if candidate.action_id == intent.action_id
            ),
            None,
        )
        if action is None:
            raise CapabilityIntentInvalidError("capability action is unknown")
        self._validate_intent_parameters(intent, action)

        state_by_id = {state.capability_id: state for state in self._states}
        state = state_by_id[intent.capability_id]
        if not self._predicates_match(
            binding,
            action.predicate_ids,
            state,
            context,
        ):
            raise CapabilityIntentInadmissibleError("capability predicates are false")
        try:
            result = binding.implementation.apply(intent, state, context)
        except CapabilityIntentInadmissibleError:
            raise
        except Exception as exc:
            raise CapabilityRuntimeError("capability action failed") from exc
        next_state, effects, events = self._validated_result(
            result,
            binding,
            state,
            allowed_effect_ids=action.effect_ids,
            allowed_event_ids=action.event_ids,
        )
        state_by_id[intent.capability_id] = next_state
        ordered_states = tuple(
            state_by_id[item.resolved.capability_id] for item in self._bindings
        )
        return PreparedCapabilityTurn(ordered_states, effects, events)

    def _prepare_observers(
        self,
        intent: object,
        before_view: GameView,
        after_view: GameView,
        event: _EventDraft | None,
        context: CapabilityExecutionContext,
    ) -> PreparedCapabilityTurn:
        observation = CapabilityTurnObservation(
            intent=self._canonical_contract_value(intent),
            events=self._observation_events(event),
            before_view=self._canonical_contract_value(before_view),
            after_view=self._canonical_contract_value(after_view),
        )
        state_by_id = {state.capability_id: state for state in self._states}
        effects: list[CapabilityEffectData] = []
        events: list[CapabilityEventData] = []
        event_type = None if event is None else event[0].value

        for binding in self._bindings:
            observers = self._eligible_observers(
                binding.descriptor.observers,
                event_type,
                binding,
                state_by_id[binding.resolved.capability_id],
                context,
            )
            if not observers:
                continue
            state = state_by_id[binding.resolved.capability_id]
            try:
                result = binding.implementation.observe(observation, state, context)
            except Exception as exc:
                raise CapabilityRuntimeError("capability observer failed") from exc
            allowed_effect_ids = tuple(
                sorted({item for observer in observers for item in observer.effect_ids})
            )
            allowed_event_ids = tuple(
                sorted({item for observer in observers for item in observer.event_ids})
            )
            next_state, emitted_effects, emitted_events = self._validated_result(
                result,
                binding,
                state,
                allowed_effect_ids=allowed_effect_ids,
                allowed_event_ids=allowed_event_ids,
            )
            state_by_id[binding.resolved.capability_id] = next_state
            effects.extend(emitted_effects)
            events.extend(emitted_events)

        ordered_states = tuple(
            state_by_id[item.resolved.capability_id] for item in self._bindings
        )
        return PreparedCapabilityTurn(ordered_states, tuple(effects), tuple(events))

    def _eligible_observers(
        self,
        observers: tuple[CapabilityObserverDescriptor, ...],
        event_type: str | None,
        binding: _RuntimeBinding,
        state: CapabilityStateEntry,
        context: CapabilityExecutionContext,
    ) -> tuple[CapabilityObserverDescriptor, ...]:
        eligible: list[CapabilityObserverDescriptor] = []
        for observer in observers:
            if observer.event_types and event_type not in observer.event_types:
                continue
            if self._predicates_match(
                binding,
                observer.predicate_ids,
                state,
                context,
            ):
                eligible.append(observer)
        return tuple(eligible)

    def _predicates_match(
        self,
        binding: _RuntimeBinding,
        predicate_ids: tuple[str, ...],
        state: CapabilityStateEntry,
        context: CapabilityExecutionContext,
    ) -> bool:
        for predicate_id in predicate_ids:
            try:
                matched = binding.implementation.evaluate_predicate(
                    predicate_id,
                    state,
                    context,
                )
            except Exception as exc:
                raise CapabilityRuntimeError("capability predicate failed") from exc
            if type(matched) is not bool:
                raise CapabilityRuntimeError("capability predicate returned a non-boolean")
            if not matched:
                return False
        return True

    def _validated_result(
        self,
        result: object,
        binding: _RuntimeBinding,
        prior_state: CapabilityStateEntry,
        *,
        allowed_effect_ids: tuple[str, ...],
        allowed_event_ids: tuple[str, ...],
    ) -> tuple[
        CapabilityStateEntry,
        tuple[CapabilityEffectData, ...],
        tuple[CapabilityEventData, ...],
    ]:
        if type(result) is not CapabilityEffectResult:
            raise CapabilityRuntimeError("capability implementation returned an invalid result")
        typed = cast(CapabilityEffectResult, result)
        self._validate_canonical_object(
            typed.next_state,
            binding.descriptor.state_schema,
            "capability state",
        )
        effects = self._validate_effects(
            typed.effects,
            binding.descriptor,
            allowed_effect_ids,
        )
        events = self._validate_events(
            typed.events,
            binding.descriptor,
            allowed_event_ids,
        )
        next_state = CapabilityStateEntry(
            prior_state.capability_id,
            prior_state.version,
            prior_state.namespace,
            typed.next_state,
        )
        return next_state, effects, events

    def _validate_effects(
        self,
        effects: tuple[CapabilityEffectData, ...],
        descriptor: CapabilityDescriptor,
        allowed_ids: tuple[str, ...],
    ) -> tuple[CapabilityEffectData, ...]:
        if type(effects) is not tuple:
            raise CapabilityRuntimeError("capability effects must be a tuple")
        declared = {item.effect_id: item for item in descriptor.effects}
        validated: list[CapabilityEffectData] = []
        for effect in effects:
            if type(effect) is not CapabilityEffectData:
                raise CapabilityRuntimeError("capability effect is invalid")
            definition = declared.get(effect.effect_id)
            if definition is None or effect.effect_id not in allowed_ids:
                raise CapabilityRuntimeError("capability emitted an undeclared effect")
            self._validate_canonical_object(
                effect.payload,
                definition.payload_schema,
                "capability effect payload",
            )
            validated.append(effect)
        return tuple(validated)

    def _validate_events(
        self,
        events: tuple[CapabilityEventData, ...],
        descriptor: CapabilityDescriptor,
        allowed_ids: tuple[str, ...],
    ) -> tuple[CapabilityEventData, ...]:
        if type(events) is not tuple:
            raise CapabilityRuntimeError("capability events must be a tuple")
        declared = {item.event_id: item for item in descriptor.events}
        validated: list[CapabilityEventData] = []
        for event in events:
            if type(event) is not CapabilityEventData:
                raise CapabilityRuntimeError("capability event is invalid")
            definition = declared.get(event.event_id)
            if (
                event.capability_id != descriptor.capability_id
                or definition is None
                or event.event_id not in allowed_ids
            ):
                raise CapabilityRuntimeError("capability emitted an undeclared event")
            self._validate_canonical_object(
                event.payload,
                definition.payload_schema,
                "capability event payload",
            )
            validated.append(event)
        return tuple(validated)

    def _validate_admissible_intents(
        self,
        intents: tuple[CapabilityIntent, ...],
        binding: _RuntimeBinding,
        state: CapabilityStateEntry,
        context: CapabilityExecutionContext,
    ) -> tuple[CapabilityIntent, ...]:
        if type(intents) is not tuple:
            raise CapabilityRuntimeError("admissible capability intents must be a tuple")
        actions = {item.action_id: item for item in binding.descriptor.actions}
        validated: list[CapabilityIntent] = []
        seen: set[tuple[str, bytes]] = set()
        for intent in intents:
            if type(intent) is not CapabilityIntent:
                raise CapabilityRuntimeError("admissible capability intent is invalid")
            action = actions.get(intent.action_id)
            if intent.capability_id != binding.resolved.capability_id or action is None:
                raise CapabilityRuntimeError("admissible capability intent identity mismatch")
            self._validate_intent_parameters(intent, action)
            if not self._predicates_match(
                binding,
                action.predicate_ids,
                state,
                context,
            ):
                raise CapabilityRuntimeError("projection exposed an inadmissible action")
            key = (intent.action_id, intent.parameters.canonical_bytes)
            if key in seen:
                raise CapabilityRuntimeError("projection exposed duplicate capability actions")
            seen.add(key)
            validated.append(intent)
        return tuple(
            sorted(
                validated,
                key=lambda item: (item.action_id, item.parameters.canonical_bytes),
            )
        )

    @staticmethod
    def _validate_intent_parameters(
        intent: CapabilityIntent,
        action: CapabilityActionDescriptor,
    ) -> None:
        try:
            parse_canonical_json_object(
                intent.parameters,
                schema=action.parameters_schema,
            )
        except (CapabilitySchemaError, CapabilitySerializationError) as exc:
            raise CapabilityIntentInvalidError(
                "capability intent parameters are invalid"
            ) from exc

    @staticmethod
    def _validate_canonical_object(
        value: CanonicalJsonObject,
        schema: CanonicalJsonObject,
        label: str,
    ) -> None:
        try:
            parse_canonical_json_object(value, schema=schema)
        except (CapabilitySchemaError, CapabilitySerializationError) as exc:
            raise CapabilityRuntimeError(f"{label} is invalid") from exc

    def _validate_states(
        self,
        states: tuple[CapabilityStateEntry, ...],
    ) -> tuple[CapabilityStateEntry, ...]:
        if type(states) is not tuple:
            raise CapabilityRuntimeError("capability states must be a tuple")
        state_by_id: dict[str, CapabilityStateEntry] = {}
        for state in states:
            if type(state) is not CapabilityStateEntry or state.capability_id in state_by_id:
                raise CapabilityRuntimeError("capability state entry is invalid")
            state_by_id[state.capability_id] = state
        ordered: list[CapabilityStateEntry] = []
        for binding in self._bindings:
            state = state_by_id.get(binding.resolved.capability_id)
            if (
                state is None
                or state.version != binding.resolved.version
                or state.namespace != binding.resolved.state_namespace
            ):
                raise CapabilityRuntimeError("capability state identity mismatch")
            self._validate_canonical_object(
                state.state,
                binding.descriptor.state_schema,
                "capability state",
            )
            ordered.append(state)
        if len(ordered) != len(states):
            raise CapabilityRuntimeError("capability states do not match the resolved plan")
        return tuple(ordered)

    def _binding_by_id(self, capability_id: str) -> _RuntimeBinding | None:
        return next(
            (
                binding
                for binding in self._bindings
                if binding.resolved.capability_id == capability_id
            ),
            None,
        )

    @staticmethod
    def _execution_context(
        determinism: DeterminismContext,
        event_sequence: int,
        view: GameView,
    ) -> CapabilityExecutionContext:
        return CapabilityExecutionContext(
            seed=determinism.seed,
            clock=determinism.clock,
            turn_index=event_sequence + 1,
            event_sequence=event_sequence,
            player_view=CapabilityRuntimeHost._canonical_contract_value(view),
        )

    @staticmethod
    def _canonical_contract_value(value: object) -> CanonicalJsonObject:
        try:
            document = capability_value_to_document(value)
            if type(document) is not dict:
                document = {"value": document}
            return canonical_json_object(document)
        except (CapabilitySchemaError, CapabilitySerializationError) as exc:
            raise CapabilityRuntimeError("capability observation data is invalid") from exc

    @staticmethod
    def _observation_events(
        event: _EventDraft | None,
    ) -> tuple[CanonicalJsonObject, ...]:
        if event is None:
            return ()
        kind, payload = event
        return (
            canonical_json_object(
                {
                    "kind": kind.value,
                    "payload": capability_value_to_document(payload),
                }
            ),
        )
