from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lore2mud.content.loader import load_content_pack
from lore2mud.content.models import MonsterDefeatedQuestDefinition
from lore2mud.engine.commands import CommandProcessor
from lore2mud.engine.save import SaveLoadService
from lore2mud.engine.world import World


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = PROJECT_ROOT / "examples" / "original_demo"


class M7ContentScaleDefinitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pack = load_content_pack(DEMO_PATH)

    def test_m7_scale_target_is_reached_with_reciprocal_content_references(self) -> None:
        self.assertEqual(self.pack.version, "0.8.0")
        self.assertEqual(len(self.pack.rooms), 8)
        self.assertEqual(len(self.pack.monsters), 4)
        self.assertEqual(len(self.pack.quests), 7)

        junction = self.pack.rooms["room_broken_rail_junction"]
        well = self.pack.rooms["room_mist_condenser_well"]
        archive = self.pack.rooms["room_lens_archive"]
        beacon = self.pack.rooms["room_afterglow_beacon_platform"]
        spur = self.pack.rooms["room_shattered_signal_spur"]

        self.assertEqual(
            spur.exits["east"].target_room_id,
            "room_broken_rail_junction",
        )
        self.assertEqual(
            junction.exits["west"].target_room_id,
            "room_shattered_signal_spur",
        )
        self.assertEqual(
            junction.exits["north"].target_room_id,
            "room_mist_condenser_well",
        )
        self.assertEqual(
            well.exits["south"].target_room_id,
            "room_broken_rail_junction",
        )
        self.assertEqual(
            junction.exits["east"].target_room_id,
            "room_lens_archive",
        )
        self.assertEqual(
            archive.exits["west"].target_room_id,
            "room_broken_rail_junction",
        )
        self.assertEqual(
            archive.exits["east"].target_room_id,
            "room_afterglow_beacon_platform",
        )
        self.assertEqual(
            beacon.exits["west"].target_room_id,
            "room_lens_archive",
        )

        expected_encounters = {
            "monster_mist_crawler": (
                "room_mist_condenser_well",
                "quest_clear_mist_crawler",
            ),
            "monster_prism_sentinel": (
                "room_afterglow_beacon_platform",
                "quest_clear_prism_sentinel",
            ),
        }
        for monster_id, (room_id, quest_id) in expected_encounters.items():
            with self.subTest(monster_id=monster_id):
                monster = self.pack.monsters[monster_id]
                self.assertEqual(monster.room_id, room_id)
                self.assertIn(monster_id, self.pack.rooms[room_id].monster_ids)
                self.assertIsNone(monster.loot_item)

                quest = self.pack.quests[quest_id]
                self.assertIsInstance(quest, MonsterDefeatedQuestDefinition)
                self.assertEqual(quest.trigger_room_id, junction.id)
                self.assertEqual(quest.target_monster_id, monster_id)


class M7ContentScaleScenarioTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(self.pack, player_name="测试旅人")

    def _equip_starting_gear(self) -> None:
        self.world.take("item_crystal_blade")
        self.world.equip("item_crystal_blade")
        self.world.take("item_bronze_scale_mail")
        self.world.equip("item_bronze_scale_mail")

    def _defeat(self, monster_id: str):
        for _ in range(10):
            outcome = self.world.attack(monster_id)
            if outcome.combat.monster_defeated:
                return outcome
        self.fail(f"{monster_id} should be defeated within ten deterministic attacks")

    def _reach_junction_after_existing_encounters(self) -> None:
        self._equip_starting_gear()
        self.world.move("east")
        self.world.move("east")
        self._defeat("monster_ash_mite")
        self.world.move("east")
        self._defeat("monster_spark_hound")
        self.world.move("east")

    def test_both_new_branches_complete_unique_existing_kind_quests(self) -> None:
        self._reach_junction_after_existing_encounters()
        self.assertEqual(self.world.current_room.id, "room_broken_rail_junction")
        self.assertFalse(self.world.quest_states["quest_clear_mist_crawler"].completed)
        self.assertFalse(self.world.quest_states["quest_clear_prism_sentinel"].completed)

        self.world.move("north")
        mist_outcome = self._defeat("monster_mist_crawler")
        self.assertEqual(
            tuple(item.quest_id for item in mist_outcome.quest_outcomes),
            ("quest_clear_mist_crawler",),
        )
        self.assertTrue(self.world.quest_states["quest_clear_mist_crawler"].completed)
        self.assertFalse(self.world.quest_states["quest_clear_prism_sentinel"].completed)
        self.assertNotIn("monster_mist_crawler", self.world.current_room.monster_ids)

        self.world.move("south")
        self.world.move("east")
        self.world.move("east")
        prism_outcome = self._defeat("monster_prism_sentinel")
        self.assertEqual(
            tuple(item.quest_id for item in prism_outcome.quest_outcomes),
            ("quest_clear_prism_sentinel",),
        )
        self.assertTrue(self.world.quest_states["quest_clear_prism_sentinel"].completed)
        self.assertNotIn("monster_prism_sentinel", self.world.current_room.monster_ids)

    def test_cli_reaches_a_new_branch_and_renders_its_quest_completion(self) -> None:
        commands = CommandProcessor(self.world)
        for command in (
            "take item_crystal_blade",
            "equip item_crystal_blade",
            "take item_bronze_scale_mail",
            "equip item_bronze_scale_mail",
            "go east",
            "go east",
            "go east",
        ):
            commands.execute(command)

        arrival = commands.execute("go east")
        self.assertIn("断轨岔口", arrival.text)
        quest_text = commands.execute("quests").text
        self.assertIn("清除雾核潜行者", quest_text)
        self.assertIn("清除棱镜哨卫", quest_text)

        commands.execute("go north")
        commands.execute("attack monster_mist_crawler")
        commands.execute("attack monster_mist_crawler")
        defeated = commands.execute("attack monster_mist_crawler")

        self.assertIn("雾核潜行者 被击败", defeated.text)
        self.assertIn("任务完成：清除雾核潜行者", defeated.text)

    def test_completed_scale_path_round_trips_through_v7_save(self) -> None:
        self._reach_junction_after_existing_encounters()
        self.world.move("north")
        self._defeat("monster_mist_crawler")
        self.world.move("south")
        self.world.move("east")
        self.world.move("east")
        self._defeat("monster_prism_sentinel")

        with tempfile.TemporaryDirectory() as temp_dir:
            service = SaveLoadService(self.pack, Path(temp_dir))
            service.save(self.world)
            loaded = service.load()

        self.assertEqual(loaded.current_room.id, "room_afterglow_beacon_platform")
        self.assertTrue(loaded.quest_states["quest_clear_mist_crawler"].completed)
        self.assertTrue(loaded.quest_states["quest_clear_prism_sentinel"].completed)
        self.assertEqual(loaded.monsters["monster_mist_crawler"].hp, 0)
        self.assertEqual(loaded.monsters["monster_prism_sentinel"].hp, 0)
        self.assertNotIn(
            "monster_prism_sentinel",
            loaded.current_room.monster_ids,
        )


if __name__ == "__main__":
    unittest.main()
