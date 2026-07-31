from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lore2mud.content.loader import load_content_pack
from lore2mud.content.models import ReachRoomQuestDefinition
from lore2mud.engine.commands import CommandProcessor
from lore2mud.engine.save import SaveLoadError, SaveLoadService
from lore2mud.engine.world import World, WorldRuleError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = PROJECT_ROOT / "examples" / "original_demo"


class OriginalAdventureDefinitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pack = load_content_pack(DEMO_PATH)

    def test_finale_requires_the_climax_loot_and_has_a_persistent_confirmation(self) -> None:
        self.assertEqual(self.pack.version, "0.10.0")
        platform = self.pack.rooms["room_afterglow_beacon_platform"]
        finale_exit = platform.exits["east"]
        self.assertEqual(finale_exit.target_room_id, "room_beacon_heart")
        self.assertEqual(finale_exit.required_item_id, "item_beacon_core")

        sentinel = self.pack.monsters["monster_prism_sentinel"]
        self.assertIsNotNone(sentinel.loot_item)
        self.assertEqual(sentinel.loot_item.item_id, "item_beacon_core")

        quest = self.pack.quests["quest_restore_beacon"]
        self.assertIsInstance(quest, ReachRoomQuestDefinition)
        self.assertEqual(quest.trigger_room_id, platform.id)
        self.assertEqual(quest.target_room_id, "room_beacon_heart")

        echo = self.pack.characters["character_beacon_echo"]
        self.assertEqual(echo.room_id, "room_beacon_heart")
        dialogue = self.pack.dialogues["dialogue_beacon_echo"]
        effects = dialogue.nodes[dialogue.start_node_id].options[0].effects
        self.assertEqual(len(effects), 1)
        self.assertEqual(effects[0].flag_id, "flag_beacon_restored")


class OriginalAdventureScenarioTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(self.pack, player_name="远行者")

    @staticmethod
    def _defeat(world: World, monster_id: str):
        for _ in range(12):
            outcome = world.attack(monster_id)
            if outcome.combat.monster_defeated:
                return outcome
        raise AssertionError(f"{monster_id} was not defeated deterministically")

    @staticmethod
    def _equip_starting_gear(world: World) -> None:
        world.take("item_crystal_blade")
        world.equip("item_crystal_blade")
        world.take("item_bronze_scale_mail")
        world.equip("item_bronze_scale_mail")

    @staticmethod
    def _reach_platform(world: World) -> None:
        for direction in ("east", "east", "east", "east", "east", "east"):
            world.move(direction)

    def test_finale_gate_failure_preserves_state_until_the_sentinel_falls(self) -> None:
        self._equip_starting_gear(self.world)
        self._reach_platform(self.world)
        self.assertFalse(self.world.quest_states["quest_restore_beacon"].completed)
        hp_before = self.world.monsters["monster_prism_sentinel"].hp

        with self.assertRaisesRegex(WorldRuleError, "需要持有.*信标核心"):
            self.world.move_with_outcome("east")

        self.assertEqual(self.world.current_room.id, "room_afterglow_beacon_platform")
        self.assertEqual(self.world.monsters["monster_prism_sentinel"].hp, hp_before)
        self.assertFalse(self.world.quest_states["quest_restore_beacon"].completed)
        self.assertNotIn("flag_beacon_restored", self.world.flags)

        self._defeat(self.world, "monster_prism_sentinel")
        self.world.take("item_beacon_core")
        move = self.world.move_with_outcome("east")
        self.assertEqual(move.room.id, "room_beacon_heart")
        self.assertEqual(
            tuple(outcome.quest_id for outcome in move.quest_outcomes),
            ("quest_restore_beacon",),
        )

    def test_optional_north_branch_trades_risk_for_a_climax_heal(self) -> None:
        self._equip_starting_gear(self.world)
        for direction in ("east", "east", "east", "east"):
            self.world.move(direction)
        self.assertEqual(self.world.current_room.id, "room_broken_rail_junction")

        self.world.move("north")
        first_round = self.world.attack("monster_mist_crawler")
        self.assertGreater(first_round.combat.damage_to_player, 0)
        self._defeat(self.world, "monster_mist_crawler")
        self.world.take("item_condensed_mist")
        self.assertTrue(self.world.player.inventory.has_item("item_condensed_mist"))

        self.world.player.hp = self.world.player.max_hp - 10
        hp_before_use = self.world.player.hp
        self.world.use("item_condensed_mist")
        self.assertGreater(self.world.player.hp, hp_before_use)
        self.assertIsNone(self.world.player.inventory.find_stack("item_condensed_mist"))
        self.assertTrue(self.world.quest_states["quest_clear_mist_crawler"].completed)

    def test_complete_adventure_and_final_state_round_trip(self) -> None:
        commands = CommandProcessor(self.world)
        for command in (
            "take item_crystal_blade",
            "equip item_crystal_blade",
            "take item_bronze_scale_mail",
            "equip item_bronze_scale_mail",
            "take item_linglu_pill 2",
            "go east",
            "talk character_elder_chen",
            "1",
            "1",
            "2",
            "go east",
        ):
            commands.execute(command)

        self._defeat(self.world, "monster_ash_mite")
        self.world.take("item_ash_mite_gel")
        self.world.move("east")
        self._defeat(self.world, "monster_spark_hound")
        self.world.move("east")
        self.world.move("north")
        self._defeat(self.world, "monster_mist_crawler")
        self.world.take("item_condensed_mist")
        self.world.move("south")
        self.world.move("east")
        self.world.move("east")

        with tempfile.TemporaryDirectory() as temp_dir:
            service = SaveLoadService(self.pack, Path(temp_dir))
            service.save(self.world, "before_climax")
            self.world = service.load("before_climax")

            self._defeat(self.world, "monster_prism_sentinel")
            self.world.take("item_beacon_core")
            finale = self.world.move_with_outcome("east")
            self.assertEqual(finale.room.id, "room_beacon_heart")
            self.world.start_dialogue("character_beacon_echo")
            ending = self.world.select_option(1)
            self.assertTrue(ending.ended)
            self.assertTrue(self.world.flags["flag_beacon_restored"])
            self.assertTrue(all(state.completed for state in self.world.quest_states.values()))

            experience_at_ending = self.world.player.experience
            service.save(self.world, "ending")
            loaded = service.load("ending")

        self.assertEqual(loaded.current_room.id, "room_beacon_heart")
        self.assertTrue(loaded.flags["flag_beacon_restored"])
        self.assertTrue(loaded.quest_states["quest_restore_beacon"].completed)
        self.assertEqual(loaded.player.experience, experience_at_ending)
        self.assertEqual(loaded.monsters["monster_prism_sentinel"].hp, 0)

    def test_old_demo_save_is_rejected_with_an_explicit_new_game_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = SaveLoadService(self.pack, Path(temp_dir))
            service.save(self.world)
            old_save = service.save_path.read_text("utf-8").replace(
                '"version": "0.10.0"',
                '"version": "0.8.0"',
            )
            service.save_path.write_text(old_save, encoding="utf-8")

            with self.assertRaisesRegex(SaveLoadError, "内容包版本不匹配"):
                service.load()


if __name__ == "__main__":
    unittest.main()
