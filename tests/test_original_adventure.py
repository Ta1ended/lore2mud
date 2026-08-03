from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lore2mud.content.loader import load_content_pack
from lore2mud.content.models import (
    MonsterDefeatedQuestDefinition,
    ReachRoomQuestDefinition,
)
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

    def test_monster_quest_text_matches_free_movement_rules(self) -> None:
        expected = {
            "quest_clear_ash_mite": "静默观测站里盘踞着一只灰壳兽，守在破裂的仪器旁。击败它，安全检查遗留设备。",
            "quest_clear_spark_hound": "火花巡兽在碎讯支线上游荡，持续威胁探索者。击败它。",
            "quest_clear_mist_crawler": "雾核潜行者潜伏在雾凝机井深处。击败它，取得那里的补给。",
            "quest_clear_prism_sentinel": "棱镜哨卫守在余辉信标台上。击败它，夺回信标核心。",
        }
        for quest_id, description in expected.items():
            with self.subTest(quest_id=quest_id):
                quest = self.pack.quests[quest_id]
                self.assertIsInstance(quest, MonsterDefeatedQuestDefinition)
                self.assertEqual(quest.description, description)
                for misleading in ("挡住", "阻断", "阻挡"):
                    self.assertNotIn(misleading, quest.description)

    def test_optional_token_has_room_hint_and_direct_dialogue_route(self) -> None:
        path = self.pack.rooms["room_glassgrass_path"]
        self.assertIn("歇脚的老人", path.description)
        self.assertIn("愿意聊聊", path.description)

        dialogue = self.pack.dialogues["dialogue_elder_chen"]
        warning = dialogue.nodes[dialogue.start_node_id].options[3]
        self.assertEqual(warning.id, "opt_warning")
        self.assertEqual(warning.next_node_id, "node_observatory")

    def test_beacon_core_is_a_non_droppable_key_with_an_explicit_room_hint(self) -> None:
        core = self.pack.items["item_beacon_core"]
        platform = self.pack.rooms["room_afterglow_beacon_platform"]
        self.assertFalse(core.droppable)
        self.assertIn("唯一钥匙", core.description)
        self.assertIn("唯一钥匙", platform.description)
        self.assertIn("必须随身带走", platform.description)


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

    def test_direct_chen_conversation_route_grants_the_optional_token(self) -> None:
        self.world.move("east")
        commands = CommandProcessor(self.world)
        looked = commands.execute("look")
        self.assertIn("歇脚的老人", looked.text)
        self.assertFalse(self.world.player.inventory.has_item("item_chen_token"))

        greeting = commands.execute("talk character_elder_chen")
        self.assertIn("这附近有什么需要留意的吗？", greeting.text)
        warning = commands.execute("4")
        self.assertIn("灰壳兽", warning.text)
        reward = commands.execute("2")

        self.assertIn("你获得了 旧铜牌。", reward.text)
        self.assertTrue(self.world.player.inventory.has_item("item_chen_token"))
        self.assertEqual(self.world.move("west").id, "room_ember_wharf")

    def test_beacon_core_drop_attempt_cannot_soft_lock_the_finale(self) -> None:
        self._equip_starting_gear(self.world)
        self._reach_platform(self.world)
        self._defeat(self.world, "monster_prism_sentinel")
        self.world.take("item_beacon_core")

        with tempfile.TemporaryDirectory() as temp_dir:
            service = SaveLoadService(self.pack, Path(temp_dir))
            service.save(self.world, "core_held")
            self.world = service.load("core_held")

        self.assertFalse(self.world.items["item_beacon_core"].droppable)
        commands = CommandProcessor(self.world)

        blocked = commands.execute("drop item_beacon_core")

        self.assertIn("关键物品", blocked.text)
        self.assertIn("不能丢弃", blocked.text)
        self.assertTrue(self.world.player.inventory.has_item("item_beacon_core"))
        self.assertIsNone(self.world.current_room.find_stack("item_beacon_core"))
        self.assertIn("折光档案室", commands.execute("go west").text)
        self.assertIn("余辉信标台", commands.execute("go east").text)
        self.assertIn("信标心室", commands.execute("go east").text)
        commands.execute("talk character_beacon_echo")
        ending = commands.execute("1")
        self.assertIn("flag_beacon_restored", ending.text)
        self.assertTrue(self.world.flags["flag_beacon_restored"])

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
