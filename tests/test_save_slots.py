"""Tests for safe, named local save slots."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lore2mud.content.loader import load_content_pack
from lore2mud.engine.commands import CommandProcessor
from lore2mud.engine.save import SaveLoadError, SaveLoadService
from lore2mud.engine.world import World


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = PROJECT_ROOT / "examples" / "original_demo"


def _runtime_snapshot(world: World) -> dict[str, object]:
    return {
        "room": world.player.room_id,
        "hp": world.player.hp,
        "inventory": list(world.player.inventory.item_ids),
        "equipped": (world.equipped.hand, world.equipped.body),
        "quests": {
            quest_id: state.completed
            for quest_id, state in world.quest_states.items()
        },
        "active_dialogue": world.active_dialogue,
        "room_items": {
            room_id: list(room.item_ids)
            for room_id, room in world.rooms.items()
        },
        "monster_hp": {
            monster_id: monster.hp
            for monster_id, monster in world.monsters.items()
        },
    }


class NamedSaveSlotServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(self.pack, player_name="测试旅人")
        self.temp_dir = tempfile.TemporaryDirectory()
        self.save_dir = Path(self.temp_dir.name) / "saves"
        self.service = SaveLoadService(self.pack, self.save_dir)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_default_slot_remains_backward_compatible(self) -> None:
        self.service.save(self.world)

        self.assertEqual(self.service.save_path, self.save_dir / "default.json")
        self.assertEqual(self.service.slot_path("default"), self.service.save_path)
        loaded = self.service.load()
        self.assertEqual(loaded.player.room_id, self.world.player.room_id)

    def test_named_slots_are_isolated_and_round_trip(self) -> None:
        self.service.save(self.world, "start")
        self.world.take("item_spark_lantern")
        self.world.move("east")
        self.service.save(self.world, "lantern_run")

        start = self.service.load("start")
        lantern_run = self.service.load("lantern_run")

        self.assertEqual(self.service.slot_path("start"), self.save_dir / "start.json")
        self.assertEqual(start.player.room_id, "room_ember_wharf")
        self.assertEqual(start.player.inventory.item_ids, [])
        self.assertEqual(lantern_run.player.room_id, "room_glassgrass_path")
        self.assertEqual(lantern_run.player.inventory.item_ids, ["item_spark_lantern"])

    def test_invalid_slot_never_writes_a_file(self) -> None:
        self.service.save(self.world)
        default_content = self.service.save_path.read_text(encoding="utf-8")
        paths_before = {path.name for path in self.save_dir.iterdir()}

        for invalid_slot in (
            "",
            "../outside",
            r"..\outside",
            "slot.json",
            "Upper",
            "two words",
            "con",
            "com1",
            "lpt9",
            "-leading",
            "_leading",
            "a" * 33,
            123,
        ):
            with self.subTest(invalid_slot=invalid_slot):
                with self.assertRaisesRegex(SaveLoadError, "存档槽位"):
                    self.service.save(self.world, invalid_slot)  # type: ignore[arg-type]

        self.assertEqual(
            self.service.save_path.read_text(encoding="utf-8"),
            default_content,
        )
        self.assertEqual({path.name for path in self.save_dir.iterdir()}, paths_before)

    def test_invalid_named_load_is_rejected_before_file_access(self) -> None:
        with self.assertRaisesRegex(SaveLoadError, "存档槽位"):
            self.service.load("../outside")

    def test_missing_valid_named_slot_reports_its_path(self) -> None:
        with self.assertRaises(SaveLoadError) as caught:
            self.service.load("missing_slot")

        self.assertIn("missing_slot.json", str(caught.exception))


class NamedSaveSlotCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(self.pack, player_name="测试旅人")
        self.temp_dir = tempfile.TemporaryDirectory()
        self.service = SaveLoadService(self.pack, Path(self.temp_dir.name))
        self.commands = CommandProcessor(self.world, save_service=self.service)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_commands_save_and_load_distinct_named_slots(self) -> None:
        start = self.commands.execute("save start")
        self.assertIn("start.json", start.text)

        self.commands.execute("take item_spark_lantern")
        self.commands.execute("go east")
        lantern_run = self.commands.execute("save lantern_run")
        self.assertIn("lantern_run.json", lantern_run.text)

        fresh_world = World.from_content_pack(self.pack, player_name="测试旅人")
        fresh_commands = CommandProcessor(fresh_world, save_service=self.service)
        self.assertIn("读档成功", fresh_commands.execute("load start").text)
        self.assertEqual(fresh_commands.world.player.inventory.item_ids, [])

        self.assertIn("读档成功", fresh_commands.execute("load lantern_run").text)
        self.assertEqual(
            fresh_commands.world.player.inventory.item_ids,
            ["item_spark_lantern"],
        )
        self.assertEqual(fresh_commands.world.player.room_id, "room_glassgrass_path")

    def test_invalid_named_load_preserves_command_world(self) -> None:
        before_world = self.commands.world
        before = _runtime_snapshot(before_world)

        result = self.commands.execute("load ../outside")

        self.assertIn("读档失败", result.text)
        self.assertIn("存档槽位", result.text)
        self.assertIs(self.commands.world, before_world)
        self.assertEqual(_runtime_snapshot(self.commands.world), before)

    def test_command_rejects_multiple_slot_arguments(self) -> None:
        self.assertEqual(
            self.commands.execute("save first second").text,
            "用法：save [槽位]",
        )
        self.assertEqual(
            self.commands.execute("load first second").text,
            "用法：load [槽位]",
        )

    def test_help_documents_optional_slot(self) -> None:
        help_text = self.commands.execute("help").text
        self.assertIn("save [槽位]", help_text)
        self.assertIn("load [槽位]", help_text)


if __name__ == "__main__":
    unittest.main()
