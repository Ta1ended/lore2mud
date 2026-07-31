from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lore2mud.content.loader import load_content_pack
from lore2mud.content.models import MonsterDefeatedQuestDefinition
from lore2mud.engine.commands import CommandProcessor
from lore2mud.engine.save import SaveLoadError, SaveLoadService
from lore2mud.engine.world import World


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = PROJECT_ROOT / "examples" / "original_demo"


class M7SecondEncounterContentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pack = load_content_pack(DEMO_PATH)

    def test_pack_has_the_second_original_encounter_without_new_mechanics(self) -> None:
        self.assertEqual(self.pack.version, "0.10.0")
        self.assertGreaterEqual(len(self.pack.rooms), 8)
        self.assertEqual(len(self.pack.monsters), 4)
        self.assertGreaterEqual(len(self.pack.quests), 7)

        observatory = self.pack.rooms["room_silent_observatory"]
        spur = self.pack.rooms["room_shattered_signal_spur"]
        self.assertEqual(
            observatory.exits["east"].target_room_id,
            "room_shattered_signal_spur",
        )
        self.assertEqual(spur.exits["west"].target_room_id, "room_silent_observatory")

        hound = self.pack.monsters["monster_spark_hound"]
        self.assertEqual(hound.room_id, spur.id)
        self.assertIsNone(hound.loot_item)

        quest = self.pack.quests["quest_clear_spark_hound"]
        self.assertIsInstance(quest, MonsterDefeatedQuestDefinition)
        self.assertEqual(quest.trigger_room_id, "room_silent_observatory")
        self.assertEqual(quest.target_monster_id, hound.id)

    def test_v8_rejects_a_save_from_the_old_0_8_content_pack(self) -> None:
        world = World.from_content_pack(self.pack, player_name="测试旅人")
        with tempfile.TemporaryDirectory() as temp_dir:
            service = SaveLoadService(self.pack, Path(temp_dir))
            service.save(world)
            save_text = service.save_path.read_text(encoding="utf-8")
            self.assertIn('"version": "0.10.0"', save_text)
            service.save_path.write_text(
                save_text.replace('"version": "0.10.0"', '"version": "0.8.0"'),
                encoding="utf-8",
            )

            with self.assertRaises(SaveLoadError) as caught:
                service.load()

        self.assertIn("版本", str(caught.exception))


class M7SecondEncounterScenarioTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = World.from_content_pack(
            load_content_pack(DEMO_PATH), player_name="测试旅人"
        )

    def _reach_second_encounter(self) -> None:
        self.world.move("east")
        self.world.move("east")
        self.assertIn("quest_clear_spark_hound", self.world.quest_states)
        self.assertFalse(self.world.quest_states["quest_clear_spark_hound"].completed)

        self.world.attack("monster_ash_mite")
        self.world.attack("monster_ash_mite")
        self.world.move("east")

    def test_second_encounter_completes_the_existing_monster_quest_flow(self) -> None:
        self._reach_second_encounter()
        self.assertEqual(self.world.current_room.id, "room_shattered_signal_spur")

        for _ in range(2):
            outcome = self.world.attack("monster_spark_hound")
            self.assertFalse(outcome.combat.monster_defeated)
            self.assertEqual(outcome.quest_outcomes, ())

        outcome = self.world.attack("monster_spark_hound")
        self.assertTrue(outcome.combat.monster_defeated)
        self.assertEqual(
            tuple(item.quest_id for item in outcome.quest_outcomes),
            ("quest_clear_spark_hound",),
        )
        self.assertTrue(self.world.quest_states["quest_clear_spark_hound"].completed)
        self.assertNotIn("monster_spark_hound", self.world.current_room.monster_ids)

    def test_cli_renders_the_second_encounter_and_quest_completion(self) -> None:
        commands = CommandProcessor(self.world)
        commands.execute("go east")
        commands.execute("go east")
        commands.execute("attack monster_ash_mite")
        commands.execute("attack monster_ash_mite")

        arrival = commands.execute("go east")
        self.assertIn("碎讯支线", arrival.text)
        self.assertIn("火花巡兽", arrival.text)

        commands.execute("attack monster_spark_hound")
        commands.execute("attack monster_spark_hound")
        defeated = commands.execute("attack monster_spark_hound")

        self.assertIn("火花巡兽 被击败", defeated.text)
        self.assertIn("任务完成：清除火花巡兽", defeated.text)
        quest_text = commands.execute("quests").text
        self.assertIn("清除火花巡兽", quest_text)
        self.assertIn("击败 火花巡兽", quest_text)


if __name__ == "__main__":
    unittest.main()
