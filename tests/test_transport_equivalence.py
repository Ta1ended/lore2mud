"""CLI/Web parity tests over the shared V2-1 application boundary."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from lore2mud.application import DeterminismContext, GameSession, TurnResult
from lore2mud.content.loader import load_content_pack
from lore2mud.engine.commands import CommandProcessor
from lore2mud.engine.save import SaveLoadService, _serialize_world
from lore2mud.engine.world import World
from lore2mud.web.app import JsonValue, PlayerSession


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


class TransportEquivalenceTests(unittest.TestCase):
    def test_original_demo_turns_and_save_load_are_equivalent(self) -> None:
        pack = load_content_pack(DEMO)
        context = DeterminismContext(seed=20260804, clock=730)
        with tempfile.TemporaryDirectory() as cli_dir, tempfile.TemporaryDirectory() as web_dir:
            cli_service = SaveLoadService(pack, Path(cli_dir))
            web_service = SaveLoadService(pack, Path(web_dir))
            cli_session = GameSession.from_content_pack(
                pack,
                cli_service,
                player_name="同路旅人",
                determinism=context,
            )
            commands = CommandProcessor.from_session(cli_session)
            web = PlayerSession(
                pack,
                web_service,
                player_name="同路旅人",
                determinism=context,
            )

            steps: tuple[tuple[str, dict[str, object]], ...] = (
                ("take item_crystal_blade", {"type": "take", "target": "item_crystal_blade"}),
                ("equip item_crystal_blade", {"type": "equip", "target": "item_crystal_blade"}),
                ("go east", {"type": "move", "direction": "east"}),
                ("buy item_linglu_pill 2", {"type": "buy", "target": "item_linglu_pill", "quantity": 2}),
                ("go east", {"type": "move", "direction": "east"}),
                ("attack monster_ash_mite", {"type": "attack", "target": "monster_ash_mite"}),
                ("save trail", {"type": "save", "slot": "trail"}),
                ("attack monster_ash_mite", {"type": "attack", "target": "monster_ash_mite"}),
                ("load trail", {"type": "load", "slot": "trail"}),
            )
            for command, action in steps:
                with self.subTest(command=command):
                    self._assert_turn_equivalent(commands, web, command, action)

            self.assertEqual(
                cli_service.slot_path("trail").read_bytes(),
                web_service.slot_path("trail").read_bytes(),
            )

    def test_runtime_campaign_rejection_and_progression_are_equivalent(self) -> None:
        pack = load_content_pack(MAGIC)
        context = DeterminismContext(seed=7, clock=11)
        with tempfile.TemporaryDirectory() as cli_dir, tempfile.TemporaryDirectory() as web_dir:
            cli_service = SaveLoadService(pack, Path(cli_dir))
            web_service = SaveLoadService(pack, Path(web_dir))
            commands = CommandProcessor.from_session(
                GameSession.from_content_pack(pack, cli_service, determinism=context)
            )
            web = PlayerSession(pack, web_service, determinism=context)

            steps: tuple[tuple[str, dict[str, object]], ...] = (
                (
                    "act action_finish_ward",
                    {"type": "campaign_action", "action_id": "action_finish_ward"},
                ),
                (
                    "act action_open_ward",
                    {"type": "campaign_action", "action_id": "action_open_ward"},
                ),
                (
                    "act action_finish_ward",
                    {"type": "campaign_action", "action_id": "action_finish_ward"},
                ),
                ("save ward", {"type": "save", "slot": "ward"}),
            )
            for command, action in steps:
                with self.subTest(command=command):
                    self._assert_turn_equivalent(commands, web, command, action)

            self.assertEqual(
                cli_service.slot_path("ward").read_bytes(),
                web_service.slot_path("ward").read_bytes(),
            )

    def _assert_turn_equivalent(
        self,
        commands: CommandProcessor,
        web: PlayerSession,
        command: str,
        action: dict[str, object],
    ) -> None:
        cli_result = commands.execute(command)
        web_response = web.dispatch(action)
        cli_turn = cli_result.turn_result
        web_turn = web.last_turn_result

        self.assertIsInstance(cli_turn, TurnResult)
        self.assertIsInstance(web_turn, TurnResult)
        assert cli_turn is not None and web_turn is not None
        self.assertEqual(cli_turn, web_turn)
        self.assertEqual(_world_bytes(commands.world), _world_bytes(web.world))
        self.assertEqual(web_response["status"], cli_turn.status.value)
        self.assertEqual(
            web_response["events"],
            [PlayerSession._event_json(event) for event in cli_turn.events],
        )
        self.assertEqual(
            web_response["view"],
            PlayerSession._json_value(cli_turn.view),
        )
        self.assertIsInstance(web_response["view"], dict)
        self.assertIsInstance(web_response["events"], list)
        self.assertTrue(self._is_json_value(web_response))

    @staticmethod
    def _is_json_value(value: JsonValue) -> bool:
        if value is None or isinstance(value, (str, int, bool)):
            return True
        if isinstance(value, list):
            return all(TransportEquivalenceTests._is_json_value(item) for item in value)
        return all(
            isinstance(key, str) and TransportEquivalenceTests._is_json_value(item)
            for key, item in value.items()
        )


if __name__ == "__main__":
    unittest.main()
