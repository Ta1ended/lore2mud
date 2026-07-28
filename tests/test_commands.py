from __future__ import annotations

import unittest
from pathlib import Path

from lore2mud.content.loader import load_content_pack
from lore2mud.engine.commands import CommandProcessor
from lore2mud.engine.world import World


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = PROJECT_ROOT / "examples" / "original_demo"


class CommandScenarioTests(unittest.TestCase):
    def setUp(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(pack, player_name="测试旅人")
        self.commands = CommandProcessor(self.world)

    def test_look_describes_current_room_and_entities(self) -> None:
        result = self.commands.execute("look")
        self.assertIn("余烬渡台", result.text)
        self.assertIn("room_ember_wharf", result.text)
        self.assertIn("微火提灯", result.text)
        self.assertIn("east", result.text)

    def test_go_moves_only_through_existing_exit(self) -> None:
        result = self.commands.execute("go east")
        self.assertEqual(self.world.player.room_id, "room_glassgrass_path")
        self.assertIn("琉草小径", result.text)

        blocked = self.commands.execute("go north")
        self.assertEqual(self.world.player.room_id, "room_glassgrass_path")
        self.assertIn("不能", blocked.text)

    def test_take_moves_item_to_inventory(self) -> None:
        result = self.commands.execute("take item_spark_lantern")
        self.assertIn("微火提灯", result.text)
        self.assertNotIn(
            "item_spark_lantern",
            [s.item_id for s in self.world.current_room.item_stacks],
        )
        self.assertEqual(
            [s.item_id for s in self.world.player.inventory.stacks],
            ["item_spark_lantern"],
        )

        inventory = self.commands.execute("inventory")
        self.assertIn("item_spark_lantern", inventory.text)

    def test_attack_defeats_monster_and_levels_player(self) -> None:
        self.commands.execute("go east")
        self.commands.execute("go east")

        first = self.commands.execute("attack monster_ash_mite")
        self.assertIn("反击", first.text)
        self.assertEqual(self.world.player.hp, 18)

        second = self.commands.execute("attack monster_ash_mite")
        self.assertIn("被击败", second.text)
        self.assertIn("升到了 2 级", second.text)
        self.assertIn("任务完成", second.text)
        self.assertIn("清除灰壳兽", second.text)
        self.assertEqual(self.world.player.level, 2)
        self.assertEqual(self.world.player.experience, 17)
        self.assertEqual(self.world.player.hp, self.world.player.max_hp)
        self.assertNotIn(
            "monster_ash_mite",
            self.world.current_room.monster_ids,
        )

    def test_help_and_quit(self) -> None:
        self.assertIn("attack", self.commands.execute("help").text)
        self.assertIn("equip", self.commands.execute("help").text)
        self.assertTrue(self.commands.execute("quit").should_quit)

    def test_equip_unequip_via_commands(self) -> None:
        """CLI smoke: take → equip → status → unequip."""
        self.commands.execute("take item_crystal_blade")
        r = self.commands.execute("equip item_crystal_blade")
        self.assertIn("装备了", r.text)
        s = self.commands.execute("status")
        self.assertIn("8", s.text)
        r = self.commands.execute("unequip")
        self.assertIn("卸下了", r.text)
        s = self.commands.execute("status")
        self.assertIn("5", s.text)


if __name__ == "__main__":
    unittest.main()
