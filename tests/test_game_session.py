"""V2-1 application contract and rejection-invariance tests."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import FrozenInstanceError, asdict, dataclass, is_dataclass
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import lore2mud.application.contracts as contracts
from lore2mud.application import (
    AttackIntent,
    DeterminismContext,
    GameSession,
    LoadIntent,
    MoveIntent,
    RejectionCode,
    SaveIntent,
    TakeIntent,
    TurnStatus,
    UseIntent,
    ViewIntent,
    ViewKind,
)
from lore2mud.content.loader import load_content_pack
from lore2mud.engine.commands import CommandProcessor
from lore2mud.engine.save import SaveLoadError, SaveLoadService, _serialize_world
from lore2mud.engine.world import World, WorldRuleError


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "original_demo"
MAGIC = ROOT / "tests" / "fixtures" / "campaign_magic"


def _world_bytes(world: World) -> bytes:
    return json.dumps(
        _serialize_world(world),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


class _MutatingFailureService:
    def save(self, world: World, slot: str | None = None) -> str:
        world.player.coins += 99
        world.flags["flag_should_rollback"] = True
        raise SaveLoadError("forced save failure")

    def load(self, slot: str | None = None) -> World:
        raise SaveLoadError("forced load failure")


class _FormattingFailureService:
    def __init__(self, error: SaveLoadError) -> None:
        self._error = error

    def save(self, world: World, slot: str | None = None) -> str:
        raise self._error

    def load(self, slot: str | None = None) -> World:
        raise self._error


class _MutatingSaveLoadError(SaveLoadError):
    def __init__(self, mutation: Callable[[], None]) -> None:
        super().__init__("forced save failure")
        self._mutation = mutation

    def __str__(self) -> str:
        self._mutation()
        return super().__str__()


class _MutatingWorldRuleError(WorldRuleError):
    def __init__(self, mutation: Callable[[], None]) -> None:
        super().__init__("forced rule failure")
        self._mutation = mutation

    def __str__(self) -> str:
        self._mutation()
        return super().__str__()


@dataclass(frozen=True, slots=True)
class _ExtendedMoveIntent(MoveIntent):
    plugin_payload: object = None


class _MutatingString(str):
    _mutation: Callable[[], None]

    def __new__(
        cls,
        value: str,
        mutation: Callable[[], None],
    ) -> _MutatingString:
        instance = str.__new__(cls, value)
        instance._mutation = mutation
        return instance

    def strip(self, chars: str | None = None) -> str:
        self._mutation()
        return super().strip(chars)


class _MutatingInt(int):
    _mutation: Callable[[], None]

    def __new__(
        cls,
        value: int,
        mutation: Callable[[], None],
    ) -> _MutatingInt:
        instance = int.__new__(cls, value)
        instance._mutation = mutation
        return instance

    def __lt__(self, other: object) -> bool:
        self._mutation()
        if type(other) is not int:
            return False
        return int(self) < other


class GameSessionContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pack = load_content_pack(DEMO)

    def test_all_application_contract_dataclasses_are_frozen(self) -> None:
        dataclass_types = [
            value
            for value in vars(contracts).values()
            if isinstance(value, type)
            and value.__module__ == contracts.__name__
            and is_dataclass(value)
        ]
        self.assertTrue(dataclass_types)
        for value in dataclass_types:
            with self.subTest(contract=value.__name__):
                self.assertTrue(value.__dataclass_params__.frozen)

        intent = MoveIntent("east")
        with self.assertRaises(FrozenInstanceError):
            intent.direction = "west"  # type: ignore[misc]

    def test_event_sequence_is_stable_and_read_only_turns_do_not_advance_it(self) -> None:
        session = GameSession.from_content_pack(self.pack)

        first = session.submit(MoveIntent("east"))
        viewed = session.submit(ViewIntent(ViewKind.STATUS))
        second = session.submit(MoveIntent("east"))

        self.assertEqual(first.status, TurnStatus.ACCEPTED)
        self.assertEqual([event.sequence for event in first.events], [1])
        self.assertEqual(viewed.status, TurnStatus.ACCEPTED)
        self.assertEqual(viewed.events, ())
        self.assertEqual([event.sequence for event in second.events], [2])
        with self.assertRaises(FrozenInstanceError):
            first.events[0].sequence = 99  # type: ignore[misc]

    def test_malformed_intent_rejection_preserves_all_session_state(self) -> None:
        session = GameSession.from_content_pack(
            self.pack,
            determinism=DeterminismContext(seed=742, clock=1904),
        )
        accepted = session.submit(MoveIntent("east"))
        self.assertEqual(accepted.status, TurnStatus.ACCEPTED)

        self._assert_rejected_unchanged(
            session,
            TakeIntent("item_linglu_pill", True),  # type: ignore[arg-type]
            RejectionCode.MALFORMED_INTENT,
        )

    def test_undeclared_intent_subclass_is_rejected_without_state_change(self) -> None:
        session = GameSession.from_content_pack(self.pack)

        self._assert_rejected_unchanged(
            session,
            _ExtendedMoveIntent("east", {"kind": "extension"}),
            RejectionCode.MALFORMED_INTENT,
        )

    def test_primitive_subclasses_are_rejected_before_behavior_runs(self) -> None:
        session = GameSession.from_content_pack(self.pack)
        invoked: list[str] = []

        def mutate(label: str) -> None:
            invoked.append(label)
            session.world.player.coins += 99

        cases = (
            MoveIntent(_MutatingString("west", lambda: mutate("str"))),
            TakeIntent(
                "item_linglu_pill",
                _MutatingInt(1, lambda: mutate("int")),
            ),
        )
        for intent in cases:
            with self.subTest(intent=type(intent).__name__):
                self._assert_rejected_unchanged(
                    session,
                    intent,
                    RejectionCode.MALFORMED_INTENT,
                )

        command = CommandProcessor.from_session(session).execute(
            _MutatingString("go east", lambda: mutate("command"))
        )
        self.assertIsNotNone(command.turn_result)
        assert command.turn_result is not None
        self.assertEqual(command.turn_result.status, TurnStatus.REJECTED)
        self.assertEqual(command.turn_result.events, ())
        self.assertEqual(invoked, [])
        self.assertEqual(session.world.player.coins, 20)

    def test_inadmissible_intent_rejection_preserves_all_session_state(self) -> None:
        session = GameSession.from_content_pack(
            self.pack,
            determinism=DeterminismContext(seed=11, clock=29),
        )

        self._assert_rejected_unchanged(
            session,
            MoveIntent("west"),
            RejectionCode.INADMISSIBLE_INTENT,
        )

    def test_persistence_rejection_rolls_back_even_a_mutating_service(self) -> None:
        world = World.from_content_pack(self.pack)
        session = GameSession(
            world,
            _MutatingFailureService(),
            determinism=DeterminismContext(seed=91, clock=37),
        )

        save_result = self._assert_rejected_unchanged(
            session,
            SaveIntent("broken"),
            RejectionCode.PERSISTENCE_ERROR,
        )
        assert save_result.rejection is not None
        self.assertEqual(save_result.rejection.message, "写入存档失败。")
        self.assertNotIn("forced save failure", save_result.rejection.message)

        load_result = self._assert_rejected_unchanged(
            session,
            LoadIntent("missing"),
            RejectionCode.PERSISTENCE_ERROR,
        )
        assert load_result.rejection is not None
        self.assertEqual(load_result.rejection.message, "读取存档失败。")
        self.assertNotIn("forced load failure", load_result.rejection.message)

    def test_exception_message_formatting_is_rolled_back_before_rejection_view(
        self,
    ) -> None:
        save_world = World.from_content_pack(self.pack)
        save_session: GameSession | None = None

        def mutate_save_state() -> None:
            save_world.player.coins = 97
            assert save_session is not None
            object.__setattr__(save_session.determinism, "seed", 997)
            object.__setattr__(save_session.determinism, "clock", 999)

        save_error = _MutatingSaveLoadError(mutate_save_state)
        save_session = GameSession(
            save_world,
            _FormattingFailureService(save_error),
            determinism=DeterminismContext(seed=17, clock=31),
        )

        save_result = self._assert_rejected_unchanged(
            save_session,
            SaveIntent("probe"),
            RejectionCode.PERSISTENCE_ERROR,
        )
        assert save_result.rejection is not None
        self.assertEqual(save_result.rejection.message, "写入存档失败。")

        rule_world = World.from_content_pack(self.pack)
        rule_session = GameSession(
            rule_world,
            determinism=DeterminismContext(seed=19, clock=37),
        )

        def mutate_rule_state() -> None:
            rule_world.player.coins = 88
            object.__setattr__(rule_session.determinism, "seed", 887)
            object.__setattr__(rule_session.determinism, "clock", 889)

        rule_error = _MutatingWorldRuleError(mutate_rule_state)

        with patch.object(World, "move_with_outcome", side_effect=rule_error):
            rule_result = self._assert_rejected_unchanged(
                rule_session,
                MoveIntent("east"),
                RejectionCode.INADMISSIBLE_INTENT,
            )
        assert rule_result.rejection is not None
        self.assertEqual(rule_result.rejection.message, "forced rule failure")

    def test_persistence_rejection_omits_private_save_path_from_session_and_cli(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = SaveLoadService(self.pack, Path(temp_dir))
            session = GameSession.from_content_pack(self.pack, service)

            result = session.submit(LoadIntent("missing"))

            self.assertEqual(result.status, TurnStatus.REJECTED)
            self.assertIsNotNone(result.rejection)
            assert result.rejection is not None
            self.assertEqual(result.rejection.message, "存档文件不存在。")
            self.assertNotIn(str(Path(temp_dir).resolve()), result.rejection.message)

            command = CommandProcessor.from_session(session).execute("load missing")
            self.assertEqual(command.text, "读档失败：存档文件不存在。")
            self.assertNotIn(str(Path(temp_dir).resolve()), command.text)

    def test_nonlethal_combat_remains_an_accepted_in_world_outcome(self) -> None:
        session = GameSession.from_content_pack(self.pack)
        session.submit(TakeIntent("item_crystal_blade"))
        from lore2mud.application import EquipIntent

        session.submit(EquipIntent("item_crystal_blade"))
        session.submit(MoveIntent("east"))
        session.submit(MoveIntent("east"))

        result = session.submit(AttackIntent("monster_ash_mite"))

        self.assertEqual(result.status, TurnStatus.ACCEPTED)
        self.assertEqual(len(result.events), 1)
        payload = result.events[0].payload
        self.assertIsInstance(payload, contracts.CombatEventData)
        assert isinstance(payload, contracts.CombatEventData)
        self.assertFalse(payload.monster_defeated)
        self.assertEqual(result.view.room.monsters[0].hp, 1)

    def test_player_view_omits_hidden_state_and_unavailable_actions(self) -> None:
        world = World.from_content_pack(load_content_pack(MAGIC))
        world.flags = {"flag_z": False, "flag_a": True}
        session = GameSession(world)

        view = session.view()
        document = asdict(view)
        rendered = json.dumps(document, ensure_ascii=False, sort_keys=True)
        action_ids = [action.id for action in view.campaign.actions]

        self.assertNotIn("narrative_state", rendered)
        self.assertNotIn("state_ward_power", rendered)
        self.assertNotIn("knowledge_ward_nature", rendered)
        self.assertNotIn("action_finish_ward", action_ids)
        self.assertEqual([flag.id for flag in view.flags], ["flag_a", "flag_z"])

        demo = GameSession.from_content_pack(self.pack)
        demo.submit(TakeIntent("item_linglu_pill"))
        pill = next(item for item in demo.view().inventory if item.id == "item_linglu_pill")
        self.assertNotIn(UseIntent("item_linglu_pill"), pill.actions)
        demo.submit(MoveIntent("east"))
        west = next(
            exit_view
            for exit_view in demo.view().room.exits
            if exit_view.direction == "west"
        )
        self.assertTrue(west.locked)
        self.assertIsNone(west.move)

    def _assert_rejected_unchanged(
        self,
        session: GameSession,
        intent: contracts.GameIntent,
        code: RejectionCode,
    ) -> contracts.TurnResult:
        original_world = session.world
        before_world = _world_bytes(original_world)
        before_view = session.view()
        before_context = session.determinism
        before_determinism = (before_context.seed, before_context.clock)
        before_rng = session._rng.getstate()  # noqa: SLF001 - contract invariant probe
        before_sequence = session.event_sequence

        result = session.submit(intent)

        self.assertEqual(result.status, TurnStatus.REJECTED)
        self.assertEqual(result.events, ())
        self.assertIsNotNone(result.rejection)
        assert result.rejection is not None
        self.assertEqual(result.rejection.code, code)
        self.assertIs(session.world, original_world)
        self.assertEqual(_world_bytes(session.world), before_world)
        self.assertEqual(result.view, before_view)
        self.assertIs(session.determinism, before_context)
        self.assertEqual(
            (session.determinism.seed, session.determinism.clock),
            before_determinism,
        )
        self.assertEqual(session._rng.getstate(), before_rng)  # noqa: SLF001
        self.assertEqual(session.event_sequence, before_sequence)
        return result


if __name__ == "__main__":
    unittest.main()
