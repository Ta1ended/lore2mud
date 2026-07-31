"""Structured PlayerSession scenarios for the local browser interface."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lore2mud.content.loader import load_content_pack
from lore2mud.engine.save import SaveLoadService
from lore2mud.web.app import PlayerSession


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = PROJECT_ROOT / "examples" / "original_demo"


class PlayerSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.pack = load_content_pack(DEMO_PATH)
        self.session = PlayerSession(
            self.pack,
            SaveLoadService(self.pack, Path(self.temp_dir.name)),
            player_name="浏览器旅人",
        )

    def action(self, action_type: str, **fields: object) -> dict:
        return self.session.dispatch({"type": action_type, **fields})

    def test_initial_snapshot_is_structured_and_marks_locked_exit(self) -> None:
        snapshot = self.session.snapshot()

        self.assertEqual(snapshot["pack"]["id"], "original_demo")
        self.assertEqual(snapshot["player"]["name"], "浏览器旅人")
        self.assertEqual(snapshot["room"]["id"], "room_ember_wharf")
        self.assertEqual(snapshot["room"]["exits"][0]["direction"], "east")
        self.assertFalse(snapshot["room"]["exits"][0]["locked"])
        self.assertEqual(len(snapshot["room"]["items"]), 4)
        self.assertEqual(len(snapshot["quests"]), 3)
        self.assertIsNone(snapshot["dialogue"])
        self.assertIsNone(snapshot["shop"])

    def test_inventory_equipment_and_status_follow_world_actions(self) -> None:
        take = self.action("take", target="item_crystal_blade")
        equip = self.action("equip", target="item_crystal_blade")

        self.assertTrue(take["ok"])
        self.assertEqual(take["event"]["type"], "take")
        self.assertTrue(equip["ok"])
        self.assertEqual(equip["snapshot"]["equipment"]["hand"]["id"], "item_crystal_blade")
        self.assertEqual(equip["snapshot"]["player"]["attack"], 8)
        item = next(
            value for value in equip["snapshot"]["inventory"]
            if value["id"] == "item_crystal_blade"
        )
        self.assertTrue(item["equipped"])

    def test_failed_structured_action_preserves_snapshot(self) -> None:
        before = self.session.snapshot()

        result = self.action("take", target="item_linglu_pill", quantity=True)

        self.assertFalse(result["ok"])
        self.assertEqual(result["event"]["type"], "error")
        self.assertEqual(result["snapshot"], before)

    def test_dialogue_snapshot_and_effects_use_typed_world_results(self) -> None:
        self.action("move", direction="east")
        started = self.action("talk", target="character_elder_chen")

        self.assertTrue(started["ok"])
        self.assertEqual(
            started["snapshot"]["dialogue"]["character_id"],
            "character_elder_chen",
        )
        self.assertGreaterEqual(len(started["snapshot"]["dialogue"]["options"]), 1)

        advanced = self.action("choose_dialogue", index=1)
        self.assertTrue(advanced["ok"])
        self.assertIsNotNone(advanced["snapshot"]["dialogue"])

    def test_shop_snapshot_and_transactions_are_structured(self) -> None:
        self.action("move", direction="east")
        snapshot = self.session.snapshot()
        self.assertEqual(snapshot["shop"]["id"], "shop_chen_travel_goods")

        bought = self.action("buy", target="item_linglu_pill", quantity=2)
        self.assertTrue(bought["ok"])
        self.assertEqual(bought["event"]["data"]["quantity"], 2)
        self.assertEqual(bought["snapshot"]["player"]["coins"], 12)

        sold = self.action("sell", target="item_linglu_pill")
        self.assertTrue(sold["ok"])
        self.assertEqual(sold["snapshot"]["player"]["coins"], 14)

    def test_combat_event_and_snapshot_do_not_depend_on_rendered_text(self) -> None:
        self.action("take", target="item_crystal_blade")
        self.action("equip", target="item_crystal_blade")
        self.action("move", direction="east")
        self.action("move", direction="east")

        result = self.action("attack", target="monster_ash_mite")

        self.assertTrue(result["ok"])
        self.assertEqual(result["event"]["type"], "attack")
        self.assertEqual(result["event"]["data"]["combat"]["damage_to_monster"], 7)
        monster = result["snapshot"]["room"]["monsters"][0]
        self.assertEqual(monster["hp"], 1)

    def test_save_and_load_replace_authoritative_world(self) -> None:
        saved_world = self.session.world
        self.assertTrue(self.action("save", slot="trail")["ok"])
        self.action("move", direction="east")

        loaded = self.action("load", slot="trail")

        self.assertTrue(loaded["ok"])
        self.assertIsNot(self.session.world, saved_world)
        self.assertEqual(loaded["snapshot"]["room"]["id"], "room_ember_wharf")
        command = self.action("command", command="status")
        self.assertTrue(command["ok"])
        self.assertIn("浏览器旅人", command["event"]["message"])

    def test_command_mutations_are_structured_failures_without_state_change(self) -> None:
        before = self.session.snapshot()
        for command in ("go west", "save command_slot", "load missing"):
            with self.subTest(command=command):
                result = self.action("command", command=command)
                self.assertFalse(result["ok"])
                self.assertEqual(result["event"]["type"], "error")
                self.assertIn("仅接受无参数只读指令", result["event"]["message"])
                self.assertEqual(result["snapshot"], before)

    def test_command_fallback_accepts_only_reliable_read_only_matrix(self) -> None:
        for command in ("look", "inventory", "i", "quests", "status", "help"):
            with self.subTest(command=command):
                result = self.action("command", command=command)
                self.assertTrue(result["ok"])
                self.assertEqual(result["event"]["type"], "command")
                self.assertTrue(result["event"]["message"])

        for command in ("help status", "shop", "examine room", 'look "'):
            with self.subTest(command=command):
                result = self.action("command", command=command)
                self.assertFalse(result["ok"])
                self.assertEqual(result["event"]["type"], "error")

    def test_action_schema_rejects_unknown_missing_and_extra_fields(self) -> None:
        cases = (
            {"type": "teleport", "target": "room_silent_observatory"},
            {"type": "move"},
            {"type": "move", "direction": "east", "rule_override": True},
            ["move", "east"],
        )
        before = self.session.snapshot()
        for action in cases:
            with self.subTest(action=action):
                result = self.session.dispatch(action)
                self.assertFalse(result["ok"])
                self.assertEqual(result["snapshot"], before)

    def test_recover_action_is_available_after_defeat(self) -> None:
        self.session.world.player.hp = 0

        result = self.action("recover")

        self.assertTrue(result["ok"])
        self.assertTrue(result["snapshot"]["player"]["alive"])
        self.assertEqual(result["snapshot"]["room"]["id"], "room_ember_wharf")


if __name__ == "__main__":
    unittest.main()
