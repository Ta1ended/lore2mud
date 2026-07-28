"""Tests for read-only inspection of items visible to the player."""

from __future__ import annotations

import copy
from dataclasses import replace
import tempfile
import unittest
from pathlib import Path

from lore2mud.content.loader import load_content_pack
from lore2mud.engine.commands import CommandProcessor
from lore2mud.engine.save import SaveLoadService
from lore2mud.engine.world import InspectItemOutcome, World, WorldRuleError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = PROJECT_ROOT / "examples" / "original_demo"


def _runtime_snapshot(world: World) -> dict[str, object]:
    """Capture mutable runtime state to prove inspection is read-only."""
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
        "inventory": list(world.player.inventory.item_ids),
        "equipped": (world.equipped.hand, world.equipped.body),
        "quests": copy.deepcopy(world.quest_states),
        "active_dialogue": copy.deepcopy(world.active_dialogue),
        "rooms": {
            room_id: (list(room.item_ids), list(room.monster_ids))
            for room_id, room in world.rooms.items()
        },
        "monsters": {
            monster_id: monster.hp
            for monster_id, monster in world.monsters.items()
        },
    }


class InspectItemWorldTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(self.pack, player_name="测试旅人")

    def test_room_item_returns_typed_details_without_state_change(self) -> None:
        before = _runtime_snapshot(self.world)

        outcome = self.world.inspect_item("item_spark_lantern")

        self.assertIsInstance(outcome, InspectItemOutcome)
        self.assertEqual(outcome.item_id, "item_spark_lantern")
        self.assertEqual(outcome.item_name, "微火提灯")
        self.assertIn("淡蓝火星", outcome.description)
        self.assertEqual(_runtime_snapshot(self.world), before)

    def test_inventory_item_resolves_by_name_without_state_change(self) -> None:
        self.world.take("item_spark_lantern")
        before = _runtime_snapshot(self.world)

        outcome = self.world.inspect_item("微火提灯")

        self.assertEqual(outcome.item_id, "item_spark_lantern")
        self.assertIn("淡蓝火星", outcome.description)
        self.assertEqual(_runtime_snapshot(self.world), before)

    def test_hidden_dialogue_reward_is_not_exposed(self) -> None:
        before = _runtime_snapshot(self.world)

        with self.assertRaisesRegex(WorldRuleError, "这里或背包中没有") as caught:
            self.world.inspect_item("item_chen_token")

        self.assertNotIn("旧铜牌", str(caught.exception))
        self.assertEqual(_runtime_snapshot(self.world), before)

    def test_duplicate_visible_names_require_stable_id_without_state_change(self) -> None:
        blade = self.world.items["item_crystal_blade"]
        self.world.items["item_crystal_blade"] = replace(blade, name="微火提灯")
        before = _runtime_snapshot(self.world)

        with self.assertRaisesRegex(WorldRuleError, "名称不唯一"):
            self.world.inspect_item("微火提灯")

        outcome = self.world.inspect_item("item_crystal_blade")
        self.assertEqual(outcome.item_id, "item_crystal_blade")
        self.assertEqual(_runtime_snapshot(self.world), before)

    def test_active_dialogue_remains_active_after_inspection(self) -> None:
        self.world.take("item_spark_lantern")
        self.world.move("east")
        self.world.start_dialogue("character_elder_chen")
        before = _runtime_snapshot(self.world)

        outcome = self.world.inspect_item("item_spark_lantern")

        self.assertEqual(outcome.item_id, "item_spark_lantern")
        self.assertEqual(_runtime_snapshot(self.world), before)


class InspectItemCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(pack, player_name="测试旅人")
        self.commands = CommandProcessor(self.world)

    def test_command_renders_id_and_description(self) -> None:
        result = self.commands.execute("inspect item_spark_lantern")

        self.assertEqual(
            result.text,
            "微火提灯 [item_spark_lantern]\n"
            "一盏封着淡蓝火星的小灯，足以照亮近处的路。",
        )

    def test_command_requires_an_item_query(self) -> None:
        self.assertEqual(
            self.commands.execute("inspect").text,
            "用法：inspect <物品ID或名称>",
        )

    def test_help_includes_inspect(self) -> None:
        self.assertIn("inspect <物品ID或名称>", self.commands.execute("help").text)


class InspectItemSaveRoundTripTests(unittest.TestCase):
    def test_inventory_item_remains_inspectable_after_save_load(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack, player_name="测试旅人")
        world.take("item_spark_lantern")

        with tempfile.TemporaryDirectory() as temp_dir:
            service = SaveLoadService(pack, Path(temp_dir))
            service.save(world)
            loaded = service.load()

        outcome = loaded.inspect_item("item_spark_lantern")
        self.assertEqual(outcome.item_name, "微火提灯")
        self.assertIn("淡蓝火星", outcome.description)


if __name__ == "__main__":
    unittest.main()
