"""Tests for the typed M3 quest system and its public command behavior."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

from lore2mud.content.loader import ContentValidationError, load_content_pack
from lore2mud.content.models import (
    CollectItemQuestDefinition,
    MonsterDefeatedQuestDefinition,
    ReachRoomQuestDefinition,
)
from lore2mud.engine.commands import CommandProcessor
from lore2mud.engine.models import Monster, QuestState
from lore2mud.engine.save import (
    SAVE_FORMAT_VERSION,
    SaveLoadError,
    SaveLoadService,
    _serialize_world,
)
from lore2mud.engine.world import MoveOutcome, World

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = PROJECT_ROOT / "examples" / "original_demo"


def _replace_quests(pack: object, definitions: list[object]) -> None:
    """Replace the mutable definition map on a test-local content pack."""
    quests = pack.quests  # type: ignore[attr-defined]
    quests.clear()
    quests.update({definition.id: definition for definition in definitions})


class QuestContentLoadingTests(unittest.TestCase):
    """The loader and public schema enforce the frozen three-way union."""

    def _assert_rejected(
        self,
        mutate: object,
        expected_text: str,
    ) -> None:
        with tempfile.TemporaryDirectory() as td:
            bad_pack = Path(td) / "bad"
            shutil.copytree(DEMO_PATH, bad_pack)
            quests = json.loads((bad_pack / "quests.json").read_text("utf-8"))
            mutate(quests)  # type: ignore[operator]
            (bad_pack / "quests.json").write_text(
                json.dumps(quests, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            with self.assertRaises(ContentValidationError) as context:
                load_content_pack(bad_pack)
        self.assertIn(expected_text, str(context.exception))

    def test_demo_loads_all_three_typed_variants(self) -> None:
        pack = load_content_pack(DEMO_PATH)

        monster = pack.quests["quest_clear_ash_mite"]
        reach = pack.quests["quest_reach_silent_observatory"]
        collect = pack.quests["quest_collect_linglu_pills"]

        self.assertIsInstance(monster, MonsterDefeatedQuestDefinition)
        self.assertEqual(monster.kind, "monster_defeated")
        self.assertEqual(monster.target_monster_id, "monster_ash_mite")
        self.assertFalse(hasattr(monster, "target_room_id"))
        with self.assertRaises(FrozenInstanceError):
            monster.target_monster_id = "monster_other"  # type: ignore[misc]

        self.assertIsInstance(reach, ReachRoomQuestDefinition)
        self.assertEqual(reach.kind, "reach_room")
        self.assertEqual(reach.target_room_id, "room_silent_observatory")
        self.assertFalse(hasattr(reach, "target_item_id"))

        self.assertIsInstance(collect, CollectItemQuestDefinition)
        self.assertEqual(collect.kind, "collect_item")
        self.assertEqual(collect.target_item_id, "item_linglu_pill")
        self.assertEqual(collect.required_quantity, 2)
        self.assertFalse(hasattr(collect, "target_monster_id"))

    def test_schema_declares_three_exclusive_branches(self) -> None:
        schema = json.loads(
            (PROJECT_ROOT / "schemas" / "quest.schema.json").read_text("utf-8")
        )
        self.assertEqual(len(schema["oneOf"]), 3)
        definitions = schema["$defs"]
        self.assertEqual(
            definitions["monster_defeated"]["properties"]["kind"]["const"],
            "monster_defeated",
        )
        self.assertEqual(
            definitions["reach_room"]["properties"]["kind"]["const"],
            "reach_room",
        )
        self.assertEqual(
            definitions["collect_item"]["properties"]["kind"]["const"],
            "collect_item",
        )
        self.assertTrue(definitions["monster_defeated"]["additionalProperties"] is False)
        self.assertTrue(definitions["reach_room"]["additionalProperties"] is False)
        self.assertTrue(definitions["collect_item"]["additionalProperties"] is False)
        self.assertEqual(
            definitions["collect_item"]["properties"]["required_quantity"]["minimum"],
            1,
        )

    def test_kind_is_required_and_known(self) -> None:
        self._assert_rejected(
            lambda quests: quests[0].pop("kind"),
            "kind",
        )
        self._assert_rejected(
            lambda quests: quests[0].update(kind="unknown_kind"),
            "monster_defeated",
        )

    def test_target_fields_are_mutually_exclusive(self) -> None:
        self._assert_rejected(
            lambda quests: quests[0].update(target_room_id="room_ember_wharf"),
            "target_room_id",
        )
        self._assert_rejected(
            lambda quests: quests[1].update(target_item_id="item_linglu_pill"),
            "target_item_id",
        )
        self._assert_rejected(
            lambda quests: quests[2].update(target_monster_id="monster_ash_mite"),
            "target_monster_id",
        )

    def test_each_branch_requires_its_own_target_field(self) -> None:
        for index, field_name in (
            (0, "target_monster_id"),
            (1, "target_room_id"),
            (2, "target_item_id"),
        ):
            with self.subTest(field_name=field_name):
                self._assert_rejected(
                    lambda quests, i=index, field=field_name: quests[i].pop(field),
                    field_name,
                )

    def test_target_references_must_exist(self) -> None:
        for index, field_name, bad_id in (
            (0, "target_monster_id", "monster_missing"),
            (1, "target_room_id", "room_missing"),
            (2, "target_item_id", "item_missing"),
        ):
            with self.subTest(field_name=field_name):
                self._assert_rejected(
                    lambda quests, i=index, field=field_name, value=bad_id:
                    quests[i].update({field: value}),
                    field_name,
                )

    def test_collect_quantity_is_positive_integer_and_within_stack_limit(self) -> None:
        for value in (0, True, 6):
            with self.subTest(value=value):
                self._assert_rejected(
                    lambda quests, quantity=value:
                    quests[2].update(required_quantity=quantity),
                    "required_quantity",
                )

    def test_duplicate_concrete_conditions_are_rejected_per_kind(self) -> None:
        for index, kind, target_field in (
            (0, "monster_defeated", "target_monster_id"),
            (1, "reach_room", "target_room_id"),
            (2, "collect_item", "target_item_id"),
        ):
            with self.subTest(kind=kind):
                def add_duplicate(
                    quests: list[dict[str, object]],
                    i: int = index,
                    name: str = kind,
                ) -> None:
                    duplicate = dict(quests[i])
                    duplicate["id"] = f"quest_duplicate_{name}"
                    quests.append(duplicate)

                self._assert_rejected(add_duplicate, kind)

    def test_reward_experience_remains_a_non_negative_integer(self) -> None:
        self._assert_rejected(
            lambda quests: quests[0].update(reward_experience=-1),
            "reward_experience",
        )
        self._assert_rejected(
            lambda quests: quests[0].update(reward_experience=True),
            "reward_experience",
        )


class QuestAcceptanceTests(unittest.TestCase):
    """World owns acceptance and evaluates a newly accepted task immediately."""

    def test_start_room_accepts_all_demo_quests_without_completion(self) -> None:
        world = World.from_content_pack(load_content_pack(DEMO_PATH))
        self.assertEqual(
            tuple(sorted(world.quest_states)),
            (
                "quest_clear_ash_mite",
                "quest_collect_linglu_pills",
                "quest_reach_silent_observatory",
            ),
        )
        self.assertFalse(any(state.completed for state in world.quest_states.values()))

    def test_moving_into_trigger_accepts_and_settles_ready_collect_quest(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        quest = CollectItemQuestDefinition(
            id="quest_collect_at_path",
            name="小径备药",
            description="到达小径时持有一枚灵露丸。",
            trigger_room_id="room_glassgrass_path",
            target_item_id="item_linglu_pill",
            required_quantity=1,
            reward_experience=5,
        )
        _replace_quests(pack, [quest])
        world = World.from_content_pack(pack)
        world.player.inventory.add_stack("item_linglu_pill", 1)

        outcome = world.move_with_outcome("east")

        self.assertEqual(
            tuple(item.quest_id for item in outcome.quest_outcomes),
            ("quest_collect_at_path",),
        )
        self.assertTrue(world.quest_states[quest.id].completed)
        self.assertEqual(world.player.experience, 5)

    def test_read_only_look_never_accepts_or_settles(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        quest = ReachRoomQuestDefinition(
            id="quest_delayed_acceptance",
            name="延后接取",
            description="测试只读操作。",
            trigger_room_id="room_glassgrass_path",
            target_room_id="room_silent_observatory",
            reward_experience=1,
        )
        _replace_quests(pack, [quest])
        world = World.from_content_pack(pack)

        result = CommandProcessor(world).execute("look")

        self.assertIn("余烬渡台", result.text)
        self.assertEqual(world.quest_states, {})


class QuestCompletionTests(unittest.TestCase):
    """Each tagged quest branch settles only through the relevant World action."""

    def setUp(self) -> None:
        self.world = World.from_content_pack(load_content_pack(DEMO_PATH))

    def test_collect_item_completes_at_required_inventory_quantity(self) -> None:
        outcome = self.world.take("item_linglu_pill", 2)

        self.assertEqual(
            tuple(item.quest_id for item in outcome.quest_outcomes),
            ("quest_collect_linglu_pills",),
        )
        self.assertEqual(outcome.quest_outcomes[0].kind, "collect_item")
        self.assertTrue(self.world.quest_states["quest_collect_linglu_pills"].completed)
        self.assertEqual(
            self.world.player.inventory.find_stack("item_linglu_pill").quantity,
            2,
        )

    def test_reach_room_uses_additive_result_while_move_keeps_room_contract(self) -> None:
        first_room = self.world.move("east")
        self.assertEqual(first_room.id, "room_glassgrass_path")

        outcome = self.world.move_with_outcome("east")

        self.assertIsInstance(outcome, MoveOutcome)
        self.assertEqual(outcome.room.id, "room_silent_observatory")
        self.assertEqual(
            tuple(item.quest_id for item in outcome.quest_outcomes),
            ("quest_reach_silent_observatory",),
        )
        self.assertEqual(outcome.quest_outcomes[0].kind, "reach_room")
        self.assertTrue(
            self.world.quest_states["quest_reach_silent_observatory"].completed
        )

    def test_monster_defeat_completes_its_typed_quest(self) -> None:
        self.world.move("east")
        self.world.move("east")
        self.world.attack("monster_ash_mite")
        outcome = self.world.attack("monster_ash_mite")

        self.assertEqual(
            tuple(item.quest_id for item in outcome.quest_outcomes),
            ("quest_clear_ash_mite",),
        )
        self.assertEqual(outcome.quest_outcomes[0].kind, "monster_defeated")
        self.assertTrue(self.world.quest_states["quest_clear_ash_mite"].completed)
        # Monster 12 + task 15 is still included in the historical attack-wide
        # aggregate, while quest_outcomes carries the typed task detail.
        self.assertEqual(self.world.player.level, 2)
        self.assertEqual(self.world.player.experience, 17)
        self.assertTrue(outcome.level_gains)

    def test_completion_is_not_revoked_or_rewarded_again_after_drop_and_use(self) -> None:
        self.world.take("item_linglu_pill", 2)
        experience_after_completion = self.world.player.experience

        self.world.drop("item_linglu_pill", 1)
        self.world.player.hp = 10
        self.world.use("item_linglu_pill", 1)

        self.assertTrue(self.world.quest_states["quest_collect_linglu_pills"].completed)
        self.assertEqual(self.world.player.experience, experience_after_completion)
        self.assertIsNone(self.world.player.inventory.find_stack("item_linglu_pill"))

    def test_completed_monster_quest_never_rewards_a_second_defeat(self) -> None:
        self.world.move("east")
        self.world.move("east")
        self.world.attack("monster_ash_mite")
        self.world.attack("monster_ash_mite")
        experience_after_completion = self.world.player.experience
        level_after_completion = self.world.player.level

        self.world.monsters["monster_ash_mite"] = Monster(
            id="monster_ash_mite",
            name="灰壳兽",
            description="重生测试体。",
            max_hp=8,
            attack=3,
            defense=1,
            experience_reward=0,
        )
        self.world.current_room.monster_ids.append("monster_ash_mite")
        self.world.attack("monster_ash_mite")
        self.world.attack("monster_ash_mite")

        self.assertEqual(self.world.player.experience, experience_after_completion)
        self.assertEqual(self.world.player.level, level_after_completion)


class QuestSettlementOrderTests(unittest.TestCase):
    """A single action settles all kinds in quest-ID order."""

    def _settlement_ready_world(self) -> World:
        pack = load_content_pack(DEMO_PATH)
        _replace_quests(
            pack,
            [
                ReachRoomQuestDefinition(
                    id="quest_a_reach",
                    name="先到渡台",
                    description="排序测试。",
                    trigger_room_id="room_glassgrass_path",
                    target_room_id="room_ember_wharf",
                    reward_experience=10,
                ),
                CollectItemQuestDefinition(
                    id="quest_m_collect",
                    name="再拿药丸",
                    description="排序测试。",
                    trigger_room_id="room_glassgrass_path",
                    target_item_id="item_linglu_pill",
                    required_quantity=1,
                    reward_experience=20,
                ),
                MonsterDefeatedQuestDefinition(
                    id="quest_z_monster",
                    name="最后清怪",
                    description="排序测试。",
                    trigger_room_id="room_glassgrass_path",
                    target_monster_id="monster_ash_mite",
                    reward_experience=30,
                ),
            ],
        )
        world = World.from_content_pack(pack)
        # The test is intentionally about deterministic settlement, so make the
        # already accepted state ready and let take perform the commit.
        world.quest_states = {
            quest_id: QuestState(quest_id)
            for quest_id in ("quest_a_reach", "quest_m_collect", "quest_z_monster")
        }
        world.monsters["monster_ash_mite"].hp = 0
        return world

    def test_cross_kind_rewards_and_level_gains_follow_quest_id_order(self) -> None:
        world = self._settlement_ready_world()

        outcome = world.take("item_linglu_pill")

        self.assertEqual(
            tuple(item.quest_id for item in outcome.quest_outcomes),
            ("quest_a_reach", "quest_m_collect", "quest_z_monster"),
        )
        self.assertEqual(
            tuple(item.kind for item in outcome.quest_outcomes),
            ("reach_room", "collect_item", "monster_defeated"),
        )
        self.assertEqual(
            tuple(item.reward_experience for item in outcome.quest_outcomes),
            (10, 20, 30),
        )
        self.assertEqual(
            tuple(gain.new_level for gain in outcome.level_gains),
            (2, 3, 4),
        )
        self.assertTrue(all(state.completed for state in world.quest_states.values()))


class QuestAtomicityTests(unittest.TestCase):
    """Action mutations and task settlement roll back together on failure."""

    def test_move_rolls_back_room_and_task_state_when_reward_fails(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        quest = ReachRoomQuestDefinition(
            id="quest_move_atomic",
            name="原子移动",
            description="移动回滚测试。",
            trigger_room_id="room_ember_wharf",
            target_room_id="room_glassgrass_path",
            reward_experience=1,
        )
        _replace_quests(pack, [quest])
        world = World.from_content_pack(pack)

        with patch(
            "lore2mud.engine.world.grant_experience",
            side_effect=RuntimeError("reward failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "reward failure"):
                world.move_with_outcome("east")

        self.assertEqual(world.player.room_id, "room_ember_wharf")
        self.assertFalse(world.quest_states[quest.id].completed)
        self.assertEqual(world.player.experience, 0)

    def test_take_rolls_back_stacks_and_task_state_when_reward_fails(self) -> None:
        world = World.from_content_pack(load_content_pack(DEMO_PATH))

        with patch(
            "lore2mud.engine.world.grant_experience",
            side_effect=RuntimeError("reward failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "reward failure"):
                world.take("item_linglu_pill", 2)

        source = world.current_room.find_stack("item_linglu_pill")
        self.assertIsNotNone(source)
        self.assertEqual(source.quantity, 3)
        self.assertIsNone(world.player.inventory.find_stack("item_linglu_pill"))
        self.assertFalse(world.quest_states["quest_collect_linglu_pills"].completed)

    def test_attack_rolls_back_combat_loot_and_task_when_task_reward_fails(self) -> None:
        world = World.from_content_pack(load_content_pack(DEMO_PATH))
        world.move("east")
        world.move("east")
        world.attack("monster_ash_mite")
        hp_before_terminal_attack = world.monsters["monster_ash_mite"].hp
        player_hp_before_terminal_attack = world.player.hp

        with patch(
            "lore2mud.engine.world.grant_experience",
            side_effect=[[], RuntimeError("task reward failure")],
        ):
            with self.assertRaisesRegex(RuntimeError, "task reward failure"):
                world.attack("monster_ash_mite")

        monster = world.monsters["monster_ash_mite"]
        self.assertEqual(monster.hp, hp_before_terminal_attack)
        self.assertIn("monster_ash_mite", world.current_room.monster_ids)
        self.assertIsNone(world.current_room.find_stack("item_ash_mite_gel"))
        self.assertFalse(world.quest_states["quest_clear_ash_mite"].completed)
        self.assertEqual(world.player.hp, player_hp_before_terminal_attack)
        self.assertEqual(world.player.experience, 0)

    def test_dialogue_reward_rolls_back_item_and_dialogue_state_when_task_fails(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        quest = CollectItemQuestDefinition(
            id="quest_dialogue_atomic",
            name="原子对话奖励",
            description="对话奖励回滚测试。",
            trigger_room_id="room_ember_wharf",
            target_item_id="item_chen_token",
            required_quantity=1,
            reward_experience=1,
        )
        _replace_quests(pack, [quest])
        world = World.from_content_pack(pack)
        world.move("east")
        world.start_dialogue("character_elder_chen")
        world.select_option(1)
        world.select_option(1)
        node_before = world.active_dialogue

        with patch(
            "lore2mud.engine.world.grant_experience",
            side_effect=RuntimeError("reward failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "reward failure"):
                world.select_option(2)

        self.assertEqual(world.active_dialogue, node_before)
        self.assertIsNone(world.player.inventory.find_stack("item_chen_token"))
        self.assertFalse(world.quest_states[quest.id].completed)


class QuestDialogueAndSaveTests(unittest.TestCase):
    """Dialogue grants use the same task path; load restores facts without replay."""

    def _dialogue_collect_world(self) -> tuple[World, CollectItemQuestDefinition]:
        pack = load_content_pack(DEMO_PATH)
        quest = CollectItemQuestDefinition(
            id="quest_collect_token",
            name="收集旧铜牌",
            description="从陈伯处获得旧铜牌。",
            trigger_room_id="room_ember_wharf",
            target_item_id="item_chen_token",
            required_quantity=1,
            reward_experience=15,
        )
        _replace_quests(pack, [quest])
        world = World.from_content_pack(pack)
        world.move("east")
        world.start_dialogue("character_elder_chen")
        world.select_option(1)
        world.select_option(1)
        return world, quest

    def test_dialogue_item_grant_settles_collect_quest_once(self) -> None:
        world, quest = self._dialogue_collect_world()

        outcome = world.select_option(2)

        self.assertIsNotNone(outcome.granted_item)
        self.assertEqual(
            tuple(item.quest_id for item in outcome.quest_outcomes),
            (quest.id,),
        )
        self.assertTrue(world.quest_states[quest.id].completed)
        self.assertEqual(world.player.level, 2)
        self.assertEqual(world.player.experience, 5)

    def test_command_renders_dialogue_task_outcome(self) -> None:
        world, _ = self._dialogue_collect_world()
        commands = CommandProcessor(world)

        result = commands.execute("2")

        self.assertIn("你获得了 旧铜牌", result.text)
        self.assertIn("任务完成：收集旧铜牌", result.text)
        self.assertIn("你升到了 2 级", result.text)

    def test_load_restores_quest_state_without_rechecking_or_rewarding(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        default = pack.quests["quest_collect_linglu_pills"]
        assert isinstance(default, CollectItemQuestDefinition)
        pack.quests[default.id] = CollectItemQuestDefinition(
            id=default.id,
            name=default.name,
            description=default.description,
            trigger_room_id=default.trigger_room_id,
            target_item_id=default.target_item_id,
            required_quantity=default.required_quantity,
            reward_experience=15,
            metadata=default.metadata,
        )
        world = World.from_content_pack(pack)
        # Create a deliberately already-satisfied, uncompleted persisted state.
        # Load must restore this fact rather than invoking World acceptance or
        # settlement; the next real action is the only place it may settle.
        world.player.inventory.add_stack("item_linglu_pill", 2)

        with tempfile.TemporaryDirectory() as td:
            service = SaveLoadService(pack, Path(td))
            service.save(world)
            saved = json.loads(service.save_path.read_text("utf-8"))
            self.assertEqual(saved["save_format_version"], 6)
            self.assertEqual(
                set(saved["quest_states"][default.id]),
                {"completed"},
            )

            loaded = service.load()

            self.assertFalse(loaded.quest_states[default.id].completed)
            self.assertEqual(loaded.player.experience, 0)
            self.assertEqual(
                loaded.player.inventory.find_stack("item_linglu_pill").quantity,
                2,
            )
            outcome = loaded.take("item_linglu_pill")
            self.assertEqual(
                tuple(item.quest_id for item in outcome.quest_outcomes),
                (default.id,),
            )
            self.assertEqual(loaded.player.level, 2)
            self.assertEqual(loaded.player.experience, 5)

    def test_v6_rejects_a_save_from_the_old_0_3_content_pack(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack)
        with tempfile.TemporaryDirectory() as td:
            service = SaveLoadService(pack, Path(td))
            service.save(world)
            save_text = service.save_path.read_text("utf-8")
            service.save_path.write_text(
                save_text.replace('"version": "0.4.0"', '"version": "0.3.0"'),
                encoding="utf-8",
            )
            with self.assertRaises(SaveLoadError) as context:
                service.load()
        self.assertIn("版本", str(context.exception))

    def test_save_format_and_quest_state_shape_remain_v6(self) -> None:
        world = World.from_content_pack(load_content_pack(DEMO_PATH))
        serialized = _serialize_world(world)

        self.assertEqual(SAVE_FORMAT_VERSION, 6)
        self.assertEqual(serialized["save_format_version"], 6)
        self.assertEqual(
            set(serialized["quest_states"]["quest_clear_ash_mite"]),
            {"completed"},
        )


class QuestCommandTests(unittest.TestCase):
    """The public CLI exposes progress for all typed task branches."""

    def test_quests_render_three_targets_and_collect_progress(self) -> None:
        world = World.from_content_pack(load_content_pack(DEMO_PATH))
        result = CommandProcessor(world).execute("quests")

        self.assertIn("清除灰壳兽", result.text)
        self.assertIn("击败 灰壳兽", result.text)
        self.assertIn("抵达静默观测站", result.text)
        self.assertIn("到达 静默观测站", result.text)
        self.assertIn("收集 灵露丸 ×2（当前 0/2）", result.text)
        self.assertLess(
            result.text.index("清除灰壳兽"),
            result.text.index("收集灵露丸"),
        )

    def test_cli_renders_collect_reach_and_monster_completion_once_each(self) -> None:
        world = World.from_content_pack(load_content_pack(DEMO_PATH))
        commands = CommandProcessor(world)

        collect = commands.execute("take item_linglu_pill 2")
        commands.execute("go east")
        reach = commands.execute("go east")
        commands.execute("attack monster_ash_mite")
        monster = commands.execute("attack monster_ash_mite")
        repeat = commands.execute("take item_linglu_pill")

        self.assertIn("任务完成：收集灵露丸", collect.text)
        self.assertIn("任务完成：抵达静默观测站", reach.text)
        self.assertIn("任务完成：清除灰壳兽", monster.text)
        self.assertNotIn("任务完成：收集灵露丸", repeat.text)

    def test_look_hint_disappears_when_all_start_tasks_are_completed(self) -> None:
        world = World.from_content_pack(load_content_pack(DEMO_PATH))
        commands = CommandProcessor(world)
        commands.execute("take item_linglu_pill 2")
        commands.execute("go east")
        commands.execute("go east")
        commands.execute("attack monster_ash_mite")
        commands.execute("attack monster_ash_mite")
        commands.execute("go west")
        commands.execute("go west")

        result = commands.execute("look")

        self.assertNotIn("任务提示", result.text)

    def test_quests_when_no_task_is_accepted(self) -> None:
        world = World.from_content_pack(load_content_pack(DEMO_PATH))
        world.quest_states.clear()

        result = CommandProcessor(world).execute("quests")

        self.assertIn("没有", result.text)


if __name__ == "__main__":
    unittest.main()
