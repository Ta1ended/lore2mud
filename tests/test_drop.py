"""Tests for dropping an unequipped inventory item into the current room."""

from __future__ import annotations

import copy
from dataclasses import replace
import tempfile
import unittest
from pathlib import Path

from lore2mud.content.loader import load_content_pack
from lore2mud.engine.commands import CommandProcessor
from lore2mud.engine.save import SaveLoadService
from lore2mud.engine.world import DropOutcome, World, WorldRuleError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = PROJECT_ROOT / "examples" / "original_demo"


def _runtime_snapshot(world: World) -> dict[str, object]:
    """Capture mutable runtime state for failed-action invariance checks."""
    return {
        "room": world.player.room_id,
        "player_stats": (
            world.player.hp,
            world.player.max_hp,
            world.player.attack,
            world.player.defense,
            world.player.level,
            world.player.experience,
        ),
        "inventory": [s.item_id for s in world.player.inventory.stacks],
        "equipped": (world.equipped.hand, world.equipped.body),
        "quests": copy.deepcopy(world.quest_states),
        "active_dialogue": copy.deepcopy(world.active_dialogue),
        "rooms": {
            room_id: ([s.item_id for s in room.item_stacks], list(room.monster_ids))
            for room_id, room in world.rooms.items()
        },
        "monsters": {
            monster_id: monster.hp
            for monster_id, monster in world.monsters.items()
        },
    }


class DropWorldTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(self.pack, player_name="测试旅人")

    def test_drop_by_id_moves_item_from_inventory_to_current_room(self) -> None:
        self.world.take("item_spark_lantern")

        outcome = self.world.drop("item_spark_lantern")

        self.assertIsInstance(outcome, DropOutcome)
        self.assertEqual(outcome.item_id, "item_spark_lantern")
        self.assertEqual(outcome.item_name, "微火提灯")
        self.assertNotIn("item_spark_lantern", [s.item_id for s in self.world.player.inventory.stacks])
        self.assertEqual(
            [s.item_id for s in self.world.current_room.item_stacks].count("item_spark_lantern"), 1
        )

    def test_drop_by_unique_display_name(self) -> None:
        self.world.take("item_spark_lantern")

        outcome = self.world.drop("微火提灯")

        self.assertEqual(outcome.item_id, "item_spark_lantern")
        self.assertIn("item_spark_lantern", [s.item_id for s in self.world.current_room.item_stacks])

    def test_drop_keeps_active_dialogue_open(self) -> None:
        self.world.take("item_spark_lantern")
        self.world.move("east")
        self.world.start_dialogue("character_elder_chen")
        active_before = copy.deepcopy(self.world.active_dialogue)

        self.world.drop("item_spark_lantern")

        self.assertEqual(self.world.active_dialogue, active_before)

    def test_missing_item_leaves_runtime_state_unchanged(self) -> None:
        before = _runtime_snapshot(self.world)

        with self.assertRaisesRegex(WorldRuleError, "背包中没有"):
            self.world.drop("item_spark_lantern")

        self.assertEqual(_runtime_snapshot(self.world), before)

    def test_duplicate_inventory_names_require_stable_id_without_mutation(self) -> None:
        lantern = self.world.items["item_spark_lantern"]
        self.world.items["item_linglu_pill"] = replace(
            self.world.items["item_linglu_pill"], name=lantern.name
        )
        self.world.take("item_spark_lantern")
        self.world.take("item_linglu_pill")
        before = _runtime_snapshot(self.world)

        with self.assertRaisesRegex(WorldRuleError, "名称不唯一"):
            self.world.drop("微火提灯")

        self.assertEqual(_runtime_snapshot(self.world), before)

    def test_equipped_hand_item_is_rejected_without_mutation(self) -> None:
        self.world.take("item_crystal_blade")
        self.world.equip("item_crystal_blade")
        before = _runtime_snapshot(self.world)

        with self.assertRaisesRegex(WorldRuleError, "正在装备中"):
            self.world.drop("item_crystal_blade")

        self.assertEqual(_runtime_snapshot(self.world), before)

    def test_equipped_body_item_is_rejected_without_mutation(self) -> None:
        self.world.take("item_bronze_scale_mail")
        self.world.equip("item_bronze_scale_mail")
        before = _runtime_snapshot(self.world)

        with self.assertRaisesRegex(WorldRuleError, "正在装备中"):
            self.world.drop("item_bronze_scale_mail")

        self.assertEqual(_runtime_snapshot(self.world), before)


class DropCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(pack, player_name="测试旅人")
        self.commands = CommandProcessor(self.world)

    def test_command_renders_drop_and_allows_item_to_be_taken_again(self) -> None:
        self.commands.execute("take item_spark_lantern")

        result = self.commands.execute("drop item_spark_lantern")

        self.assertEqual(result.text, "你放下了 微火提灯。")
        self.assertIn("微火提灯", self.commands.execute("look").text)
        self.assertIn("拾取了", self.commands.execute("take item_spark_lantern").text)

    def test_command_requires_an_item_query(self) -> None:
        self.assertEqual(
            self.commands.execute("drop").text,
            "用法：take <物品ID或名称> [数量]",
        )

    def test_help_includes_drop(self) -> None:
        self.assertIn("drop <物品ID或名称>", self.commands.execute("help").text)


class DropSaveRoundTripTests(unittest.TestCase):
    def test_dropped_item_survives_save_load_and_can_be_taken_again(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack, player_name="测试旅人")
        world.take("item_spark_lantern")
        world.drop("item_spark_lantern")

        with tempfile.TemporaryDirectory() as temp_dir:
            service = SaveLoadService(pack, Path(temp_dir))
            service.save(world)
            loaded = service.load()

        self.assertIn("item_spark_lantern", [s.item_id for s in loaded.current_room.item_stacks])
        loaded.take("item_spark_lantern")
        self.assertIn("item_spark_lantern", [s.item_id for s in loaded.player.inventory.stacks])


if __name__ == "__main__":
    unittest.main()
