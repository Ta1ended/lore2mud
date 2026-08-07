"""Focused V2-3 capability runtime, transaction, and checkpoint tests."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from lore2mud.application import (
    DeterminismContext,
    GameSession,
    MoveIntent,
    RejectionCode,
    SaveIntent,
    TurnStatus,
)
from lore2mud.capabilities import (
    CapabilityActionDescriptor,
    CapabilityCatalog,
    CapabilityDependencyDescriptor,
    CapabilityDescriptor,
    CapabilityEffectResult,
    CapabilityImplementationBinding,
    CapabilityImplementationContract,
    CapabilityImplementationRegistry,
    CapabilityIntent,
    CapabilityObserverDescriptor,
    CapabilityPlayerViewEntry,
    CapabilitySafetyLevel,
    CapabilityStateEntry,
    SemanticVersion,
    VersionRequirement,
    canonical_json_object,
    parse_canonical_json_object,
    resolve_capabilities,
)
from lore2mud.capabilities.persistence import (
    _checkpoint_fingerprint,
    create_capability_checkpoint,
    restore_capability_checkpoint,
)
from lore2mud.capabilities.reference import (
    REFERENCE_COUNTER_ID,
    REFERENCE_COUNTER_NAMESPACE,
    REFERENCE_COUNTER_VERSION,
    engine_capability_catalog,
    engine_capability_registry,
)
from lore2mud.capabilities.runtime import (
    CapabilityRuntimeError,
    CapabilityRuntimeHost,
)
from lore2mud.content.loader import load_content_pack
from lore2mud.engine.save import SaveLoadError, _serialize_world


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "original_demo"
VERSION = SemanticVersion.parse("1.0.0")


def _world_bytes(session: GameSession) -> bytes:
    return json.dumps(
        _serialize_world(session.world),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _object_schema(properties: dict[str, object]) -> object:
    return canonical_json_object(
        {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        }
    )


_OBSERVER_STATE_SCHEMA = _object_schema(
    {"count": {"type": "integer", "minimum": 0, "maximum": 1000}}
)
_SEQUENCE_VIEW_SCHEMA = _object_schema(
    {
        "count": {"type": "integer", "minimum": 0, "maximum": 1000},
        "event_sequence": {"type": "integer", "minimum": 0},
    }
)
_PROJECTION_INTENT_PARAMETER_SCHEMA = _object_schema(
    {"index": {"type": "integer", "minimum": 0, "maximum": 1024}}
)


class _ObserverImplementation:
    def __init__(
        self,
        capability_id: str,
        trace: list[str],
        *,
        fail: bool = False,
        project_sequence: bool = False,
    ) -> None:
        self.contract = CapabilityImplementationContract(
            capability_id,
            VERSION,
            observer_ids=("watch_turn",),
        )
        self._capability_id = capability_id
        self._trace = trace
        self._fail = fail
        self._project_sequence = project_sequence

    def apply(self, intent, state, context):
        del intent, state, context
        raise AssertionError("observer-only capability cannot apply actions")

    def observe(self, observation, state, context):
        del observation, context
        self._trace.append(self._capability_id)
        if self._fail:
            raise RuntimeError("forced observer failure")
        document = parse_canonical_json_object(state.state)
        count = document["count"]
        assert type(count) is int
        return CapabilityEffectResult(canonical_json_object({"count": count + 1}))

    def project(self, state, context):
        if self._project_sequence:
            document = parse_canonical_json_object(state.state)
            return CapabilityPlayerViewEntry(
                self._capability_id,
                VERSION,
                canonical_json_object(
                    {
                        "count": document["count"],
                        "event_sequence": context.event_sequence,
                    }
                ),
            )
        return CapabilityPlayerViewEntry(
            self._capability_id,
            VERSION,
            state.state,
        )

    def evaluate_predicate(self, predicate_id, state, context):
        del predicate_id, state, context
        raise AssertionError("observer fixture declares no predicates")

    def migrate(self, migration_id, state, context):
        del migration_id, state, context
        raise AssertionError("observer fixture declares no migrations")


class _ProjectionIntentImplementation:
    def __init__(self, capability_id: str, intent_count: int) -> None:
        self.contract = CapabilityImplementationContract(
            capability_id,
            VERSION,
            action_ids=("offer",),
        )
        self._capability_id = capability_id
        self._intent_count = intent_count

    def apply(self, intent, state, context):
        del intent, state, context
        raise AssertionError("projection fixture does not apply actions")

    def observe(self, observation, state, context):
        del observation, context
        return CapabilityEffectResult(state.state)

    def project(self, state, context):
        del context
        return CapabilityPlayerViewEntry(
            self._capability_id,
            VERSION,
            state.state,
            tuple(
                CapabilityIntent(
                    self._capability_id,
                    "offer",
                    canonical_json_object({"index": index}),
                )
                for index in range(self._intent_count)
            ),
        )

    def evaluate_predicate(self, predicate_id, state, context):
        del predicate_id, state, context
        raise AssertionError("projection fixture declares no predicates")

    def migrate(self, migration_id, state, context):
        del migration_id, state, context
        raise AssertionError("projection fixture declares no migrations")


class _SpySaveService:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.save_calls = 0

    def save(self, world, slot=None):
        del world, slot
        self.save_calls += 1
        self.path.write_bytes(b"changed")
        return "saved"

    @property
    def save_path(self) -> Path:
        return self.path

    def slot_path(self, slot: str) -> Path:
        del slot
        return self.path

    def load(self, slot=None):
        del slot
        raise SaveLoadError("load unavailable")


class CapabilityRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pack = load_content_pack(DEMO)

    def test_empty_plan_preserves_legacy_views_and_turn_results(self) -> None:
        catalog = CapabilityCatalog.from_bindings(())
        resolution = resolve_capabilities(catalog, ())
        self.assertTrue(resolution.ok)
        assert resolution.plan is not None
        empty_host = CapabilityRuntimeHost(
            resolution.plan,
            CapabilityImplementationRegistry(),
        )
        legacy = GameSession.from_content_pack(self.pack)
        extended = GameSession.from_content_pack(self.pack, capability_host=empty_host)

        self.assertEqual(legacy.view(), extended.view())
        self.assertIsNone(extended.view().capabilities)
        self.assertEqual(
            legacy.submit(MoveIntent("east")),
            extended.submit(MoveIntent("east")),
        )

    def test_reference_counter_rejects_malformed_and_inadmissible_intents_unchanged(
        self,
    ) -> None:
        session, host = self._reference_session()

        malformed = CapabilityIntent(
            REFERENCE_COUNTER_ID,
            "increment",
            canonical_json_object({"amount": True}),
        )
        self._assert_rejected_unchanged(
            session,
            host,
            malformed,
            RejectionCode.CAPABILITY_INTENT_INVALID,
        )
        reset = CapabilityIntent(
            REFERENCE_COUNTER_ID,
            "reset",
            canonical_json_object({}),
        )
        self._assert_rejected_unchanged(
            session,
            host,
            reset,
            RejectionCode.CAPABILITY_INTENT_INADMISSIBLE,
        )

    def test_reference_counter_boundaries_events_and_projection(self) -> None:
        plan = self._reference_plan()
        near_limit = CapabilityStateEntry(
            REFERENCE_COUNTER_ID,
            REFERENCE_COUNTER_VERSION,
            REFERENCE_COUNTER_NAMESPACE,
            canonical_json_object({"count": 995}),
        )
        host = CapabilityRuntimeHost(
            plan,
            engine_capability_registry(),
            states=(near_limit,),
        )
        session = GameSession.from_content_pack(self.pack, capability_host=host)

        accepted = session.submit(
            CapabilityIntent(
                REFERENCE_COUNTER_ID,
                "increment",
                canonical_json_object({"amount": 5}),
            )
        )
        self.assertEqual(accepted.status, TurnStatus.ACCEPTED)
        self.assertEqual([event.sequence for event in accepted.events], [1])
        self.assertEqual(accepted.events[0].kind.value, "capability")
        payload = accepted.events[0].payload
        self.assertEqual(payload.event_id, "counter_changed")  # type: ignore[union-attr]
        self.assertEqual(
            parse_canonical_json_object(payload.payload),  # type: ignore[union-attr]
            {"new": 1000, "old": 995, "reason": "increment"},
        )
        entry = accepted.view.capabilities
        assert entry is not None
        self.assertEqual(parse_canonical_json_object(entry[0].view), {"count": 1000})
        self.assertEqual(
            tuple(intent.action_id for intent in entry[0].admissible_intents),
            ("reset",),
        )

        overflow = CapabilityIntent(
            REFERENCE_COUNTER_ID,
            "increment",
            canonical_json_object({"amount": 1}),
        )
        self._assert_rejected_unchanged(
            session,
            host,
            overflow,
            RejectionCode.CAPABILITY_INTENT_INADMISSIBLE,
        )
        reset = session.submit(
            CapabilityIntent(
                REFERENCE_COUNTER_ID,
                "reset",
                canonical_json_object({}),
            )
        )
        self.assertEqual([event.sequence for event in reset.events], [2])
        self.assertEqual(self._counter_value(host), 0)

    def test_capability_projection_enforces_public_intent_cardinality_bound(self) -> None:
        within_limit, _ = self._projection_intent_session(1024)

        view = within_limit.view()

        assert view.capabilities is not None
        self.assertEqual(len(view.capabilities[0].admissible_intents), 1024)

        above_limit, host = self._projection_intent_session(1025)
        before_states = host.states
        with self.assertRaisesRegex(CapabilityRuntimeError, "too many"):
            above_limit.view()
        self.assertEqual(host.states, before_states)
        self.assertEqual(above_limit.event_sequence, 0)

    def test_capability_and_world_events_share_one_sequence(self) -> None:
        session, _ = self._reference_session()

        moved = session.submit(MoveIntent("east"))
        incremented = session.submit(
            CapabilityIntent(
                REFERENCE_COUNTER_ID,
                "increment",
                canonical_json_object({"amount": 2}),
            )
        )

        self.assertEqual([event.sequence for event in moved.events], [1])
        self.assertEqual([event.sequence for event in incremented.events], [2])
        self.assertEqual(session.event_sequence, 2)

    def test_observers_run_in_resolved_plan_order(self) -> None:
        trace: list[str] = []
        host = self._observer_host(trace)
        session = GameSession.from_content_pack(self.pack, capability_host=host)

        result = session.submit(MoveIntent("east"))

        self.assertEqual(result.status, TurnStatus.ACCEPTED)
        self.assertEqual(trace, ["observer_base", "observer_dependent"])
        self.assertEqual(
            [parse_canonical_json_object(state.state)["count"] for state in host.states],
            [1, 1],
        )
        self.assertEqual([event.sequence for event in result.events], [1])

    def test_accepted_result_view_matches_immediate_sequence_sensitive_view(self) -> None:
        trace: list[str] = []
        descriptor = self._observer_descriptor(
            "observer_sequence",
            player_view_schema=_SEQUENCE_VIEW_SCHEMA,
        )
        binding = CapabilityImplementationBinding(
            descriptor,
            _ObserverImplementation(
                "observer_sequence",
                trace,
                project_sequence=True,
            ),
        )
        catalog = CapabilityCatalog.from_bindings((binding,))
        resolution = resolve_capabilities(catalog, ("observer_sequence",))
        self.assertTrue(resolution.ok)
        assert resolution.plan is not None
        host = CapabilityRuntimeHost(
            resolution.plan,
            CapabilityImplementationRegistry((binding,)),
        )
        session = GameSession.from_content_pack(self.pack, capability_host=host)

        result = session.submit(MoveIntent("east"))

        self.assertEqual(result.status, TurnStatus.ACCEPTED)
        self.assertEqual(result.view, session.view())
        assert result.view.capabilities is not None
        projected = parse_canonical_json_object(result.view.capabilities[0].view)
        self.assertEqual(projected["event_sequence"], 1)

    def test_observer_failure_restores_world_host_rng_context_and_sequence(self) -> None:
        trace: list[str] = []
        host = self._observer_host(trace, fail_dependent=True)
        session = GameSession.from_content_pack(
            self.pack,
            capability_host=host,
            determinism=DeterminismContext(seed=17, clock=31),
        )
        before_world = _world_bytes(session)
        before_view = session.view()
        before_states = host.states
        before_context = session.determinism
        before_rng = session._rng.getstate()  # noqa: SLF001

        with self.assertRaises(CapabilityRuntimeError):
            session.submit(MoveIntent("east"))

        self.assertEqual(trace, ["observer_base", "observer_dependent"])
        self.assertEqual(_world_bytes(session), before_world)
        self.assertEqual(session.view(), before_view)
        self.assertEqual(host.states, before_states)
        self.assertIs(session.determinism, before_context)
        self.assertEqual((session.determinism.seed, session.determinism.clock), (17, 31))
        self.assertEqual(session._rng.getstate(), before_rng)  # noqa: SLF001
        self.assertEqual(session.event_sequence, 0)

    def test_observer_failure_precedes_and_preserves_save_bytes(self) -> None:
        trace: list[str] = []
        host = self._observer_host(trace, fail_dependent=True)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "guarded.json"
            path.write_bytes(b"prior-save-bytes")
            service = _SpySaveService(path)
            session = GameSession.from_content_pack(
                self.pack,
                service,
                capability_host=host,
            )

            with self.assertRaises(CapabilityRuntimeError):
                session.submit(SaveIntent("guarded"))

            self.assertEqual(service.save_calls, 0)
            self.assertEqual(path.read_bytes(), b"prior-save-bytes")
            self.assertEqual(session.event_sequence, 0)

    def test_post_save_failure_restores_default_and_named_slot_bytes(self) -> None:
        for slot, prior_bytes in ((None, b"prior-save-bytes"), ("guarded", None)):
            with self.subTest(slot=slot), tempfile.TemporaryDirectory() as temp_dir:
                trace: list[str] = []
                host = self._observer_host(trace)
                before_states = host.states
                path = Path(temp_dir) / "guarded.json"
                if prior_bytes is not None:
                    path.write_bytes(prior_bytes)
                service = _SpySaveService(path)
                session = GameSession.from_content_pack(
                    self.pack,
                    service,
                    capability_host=host,
                )
                original_commit = host.commit

                def fail_after_commit(
                    prepared: object,
                    commit=original_commit,
                ) -> None:
                    commit(prepared)
                    raise CapabilityRuntimeError("forced post-save failure")

                with mock.patch.object(host, "commit", side_effect=fail_after_commit):
                    with self.assertRaises(CapabilityRuntimeError):
                        session.submit(SaveIntent(slot))

                self.assertEqual(service.save_calls, 1)
                if prior_bytes is None:
                    self.assertFalse(path.exists())
                else:
                    self.assertEqual(path.read_bytes(), prior_bytes)
                self.assertEqual(host.states, before_states)
                self.assertEqual(session.event_sequence, 0)

    def test_capability_checkpoint_round_trip_matches_uninterrupted_execution(self) -> None:
        session, host = self._reference_session(
            determinism=DeterminismContext(seed=41, clock=73)
        )
        session.submit(
            CapabilityIntent(
                REFERENCE_COUNTER_ID,
                "increment",
                canonical_json_object({"amount": 4}),
            )
        )
        session.submit(MoveIntent("east"))
        session._rng.gauss(0.0, 1.0)  # noqa: SLF001 - exact checkpoint probe
        source_rng_state = session._rng.getstate()  # noqa: SLF001
        checkpoint = create_capability_checkpoint(session, self.pack)
        self.assertIsNotNone(checkpoint.rng_state)

        restored_host = CapabilityRuntimeHost(
            self._reference_plan(),
            engine_capability_registry(),
        )
        restored = GameSession.from_content_pack(
            self.pack,
            capability_host=restored_host,
            determinism=DeterminismContext(seed=999, clock=1001),
        )
        restore_capability_checkpoint(restored, self.pack, checkpoint)

        self.assertEqual(_world_bytes(restored), _world_bytes(session))
        self.assertEqual(restored_host.states, host.states)
        self.assertEqual(restored.view(), session.view())
        self.assertEqual(restored.event_sequence, session.event_sequence)
        self.assertEqual(restored._rng.getstate(), source_rng_state)  # noqa: SLF001
        self.assertEqual(
            (restored.determinism.seed, restored.determinism.clock),
            (41, 73),
        )
        self.assertEqual(restored._rng.random(), session._rng.random())  # noqa: SLF001
        self.assertEqual(
            restored._rng.gauss(0.0, 1.0),  # noqa: SLF001
            session._rng.gauss(0.0, 1.0),  # noqa: SLF001
        )
        next_intent = CapabilityIntent(
            REFERENCE_COUNTER_ID,
            "increment",
            canonical_json_object({"amount": 2}),
        )
        self.assertEqual(restored.submit(next_intent), session.submit(next_intent))
        self.assertEqual(restored_host.states, host.states)

    def test_checkpoint_view_failure_restores_target_rng_and_session(self) -> None:
        source, _ = self._reference_session(
            determinism=DeterminismContext(seed=41, clock=73)
        )
        source.submit(
            CapabilityIntent(
                REFERENCE_COUNTER_ID,
                "increment",
                canonical_json_object({"amount": 4}),
            )
        )
        source._rng.gauss(0.0, 1.0)  # noqa: SLF001 - exact checkpoint probe
        checkpoint = create_capability_checkpoint(source, self.pack)
        mismatched = replace(checkpoint, view_sha256="0" * 64)
        mismatched = replace(
            mismatched,
            fingerprint=_checkpoint_fingerprint(mismatched),
        )

        target, target_host = self._reference_session(
            determinism=DeterminismContext(seed=97, clock=101)
        )
        target.submit(MoveIntent("east"))
        target._rng.gauss(0.0, 1.0)  # noqa: SLF001 - rollback probe
        before_world = _world_bytes(target)
        before_view = target.view()
        before_states = target_host.states
        before_context = target.determinism
        before_context_values = (before_context.seed, before_context.clock)
        before_rng = target._rng.getstate()  # noqa: SLF001
        before_sequence = target.event_sequence

        with self.assertRaisesRegex(SaveLoadError, "view hash"):
            restore_capability_checkpoint(target, self.pack, mismatched)

        self.assertEqual(_world_bytes(target), before_world)
        self.assertEqual(target.view(), before_view)
        self.assertEqual(target_host.states, before_states)
        self.assertIs(target.determinism, before_context)
        self.assertEqual(
            (target.determinism.seed, target.determinism.clock),
            before_context_values,
        )
        self.assertEqual(target._rng.getstate(), before_rng)  # noqa: SLF001
        self.assertEqual(target.event_sequence, before_sequence)

    def test_checkpoint_restore_rejects_missing_rng_state_unchanged(self) -> None:
        source, _ = self._reference_session()
        checkpoint = create_capability_checkpoint(source, self.pack)
        missing_rng = replace(checkpoint, rng_state=None)
        target, target_host = self._reference_session(
            determinism=DeterminismContext(seed=97, clock=101)
        )
        before_world = _world_bytes(target)
        before_states = target_host.states
        before_rng = target._rng.getstate()  # noqa: SLF001

        with self.assertRaisesRegex(SaveLoadError, "RNG state is missing"):
            restore_capability_checkpoint(target, self.pack, missing_rng)

        self.assertEqual(_world_bytes(target), before_world)
        self.assertEqual(target_host.states, before_states)
        self.assertEqual(target._rng.getstate(), before_rng)  # noqa: SLF001

    def _reference_plan(self):
        resolution = resolve_capabilities(
            engine_capability_catalog(),
            (REFERENCE_COUNTER_ID,),
        )
        self.assertTrue(resolution.ok)
        assert resolution.plan is not None
        return resolution.plan

    def _reference_session(
        self,
        *,
        determinism: DeterminismContext | None = None,
    ) -> tuple[GameSession, CapabilityRuntimeHost]:
        host = CapabilityRuntimeHost(
            self._reference_plan(),
            engine_capability_registry(),
        )
        return (
            GameSession.from_content_pack(
                self.pack,
                capability_host=host,
                determinism=determinism,
            ),
            host,
        )

    def _observer_host(
        self,
        trace: list[str],
        *,
        fail_dependent: bool = False,
    ) -> CapabilityRuntimeHost:
        base = self._observer_descriptor("observer_base")
        dependent = self._observer_descriptor(
            "observer_dependent",
            dependency_id="observer_base",
        )
        bindings = (
            CapabilityImplementationBinding(
                dependent,
                _ObserverImplementation(
                    "observer_dependent",
                    trace,
                    fail=fail_dependent,
                ),
            ),
            CapabilityImplementationBinding(
                base,
                _ObserverImplementation("observer_base", trace),
            ),
        )
        catalog = CapabilityCatalog.from_bindings(bindings)
        resolution = resolve_capabilities(catalog, ("observer_dependent",))
        self.assertTrue(resolution.ok)
        assert resolution.plan is not None
        return CapabilityRuntimeHost(
            resolution.plan,
            CapabilityImplementationRegistry(bindings),
        )

    def _projection_intent_session(
        self,
        intent_count: int,
    ) -> tuple[GameSession, CapabilityRuntimeHost]:
        capability_id = "projection_intent_bound"
        descriptor = CapabilityDescriptor(
            format_version=1,
            capability_id=capability_id,
            version=VERSION,
            safety_level=CapabilitySafetyLevel.L1,
            state_namespace=capability_id,
            initial_state=canonical_json_object({"count": 0}),
            state_schema=_OBSERVER_STATE_SCHEMA,
            actions=(
                CapabilityActionDescriptor(
                    "offer",
                    _PROJECTION_INTENT_PARAMETER_SCHEMA,
                ),
            ),
            observers=(),
            predicates=(),
            effects=(),
            events=(),
            player_view_schema=_OBSERVER_STATE_SCHEMA,
        )
        binding = CapabilityImplementationBinding(
            descriptor,
            _ProjectionIntentImplementation(capability_id, intent_count),
        )
        catalog = CapabilityCatalog.from_bindings((binding,))
        resolution = resolve_capabilities(catalog, (capability_id,))
        self.assertTrue(resolution.ok)
        assert resolution.plan is not None
        host = CapabilityRuntimeHost(
            resolution.plan,
            CapabilityImplementationRegistry((binding,)),
        )
        return GameSession.from_content_pack(self.pack, capability_host=host), host

    @staticmethod
    def _observer_descriptor(
        capability_id: str,
        *,
        dependency_id: str | None = None,
        player_view_schema: object = _OBSERVER_STATE_SCHEMA,
    ) -> CapabilityDescriptor:
        dependencies = (
            ()
            if dependency_id is None
            else (
                CapabilityDependencyDescriptor(
                    dependency_id,
                    VersionRequirement.parse("1.0.0"),
                ),
            )
        )
        return CapabilityDescriptor(
            format_version=1,
            capability_id=capability_id,
            version=VERSION,
            safety_level=CapabilitySafetyLevel.L1,
            state_namespace=capability_id,
            initial_state=canonical_json_object({"count": 0}),
            state_schema=_OBSERVER_STATE_SCHEMA,
            actions=(),
            observers=(
                CapabilityObserverDescriptor(
                    "watch_turn",
                    event_types=("move", "save"),
                ),
            ),
            predicates=(),
            effects=(),
            events=(),
            player_view_schema=player_view_schema,
            dependencies=dependencies,
        )

    def _assert_rejected_unchanged(
        self,
        session: GameSession,
        host: CapabilityRuntimeHost,
        intent: CapabilityIntent,
        code: RejectionCode,
    ) -> None:
        before_world = _world_bytes(session)
        before_view = session.view()
        before_states = host.states
        before_context = session.determinism
        before_context_values = (before_context.seed, before_context.clock)
        before_rng = session._rng.getstate()  # noqa: SLF001
        before_sequence = session.event_sequence

        result = session.submit(intent)

        self.assertEqual(result.status, TurnStatus.REJECTED)
        self.assertEqual(result.events, ())
        self.assertIsNotNone(result.rejection)
        assert result.rejection is not None
        self.assertEqual(result.rejection.code, code)
        self.assertEqual(_world_bytes(session), before_world)
        self.assertEqual(result.view, before_view)
        self.assertEqual(host.states, before_states)
        self.assertIs(session.determinism, before_context)
        self.assertEqual(
            (session.determinism.seed, session.determinism.clock),
            before_context_values,
        )
        self.assertEqual(session._rng.getstate(), before_rng)  # noqa: SLF001
        self.assertEqual(session.event_sequence, before_sequence)

    @staticmethod
    def _counter_value(host: CapabilityRuntimeHost) -> int:
        document = parse_canonical_json_object(host.states[0].state)
        value = document["count"]
        assert type(value) is int
        return value


if __name__ == "__main__":
    unittest.main()
