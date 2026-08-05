"""Focused M4 contracts for typed dialogue effects and persisted flags."""

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
    AcceptQuestEffect,
    CollectItemQuestDefinition,
    DialogueDefinition,
    DialogueNode,
    DialogueOption,
    GrantExperienceEffect,
    GrantItemEffect,
    SetFlagEffect,
)
from lore2mud.engine.commands import CommandProcessor
from lore2mud.engine.models import Character, QuestState
from lore2mud.engine.save import SAVE_FORMAT_VERSION, SaveLoadError, SaveLoadService
from lore2mud.engine.world import (
    AcceptQuestEffectOutcome,
    GrantExperienceEffectOutcome,
    GrantItemEffectOutcome,
    SetFlagEffectOutcome,
    World,
    WorldRuleError,
)
from lore2mud.inventory.models import Item, ItemStack


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = PROJECT_ROOT / "examples" / "original_demo"


def _world_with_effects(*effects: object) -> World:
    """Return a path-room World with one isolated, selectable effect option."""
    world = World.from_content_pack(load_content_pack(DEMO_PATH))
    world.move("east")
    world.characters["character_effect_probe"] = Character(
        "character_effect_probe",
        "效果探针",
        "仅用于强类型效果测试。",
        "room_glassgrass_path",
    )
    world.dialogue_defs["dialogue_effect_probe"] = DialogueDefinition(
        id="dialogue_effect_probe",
        character_id="character_effect_probe",
        start_node_id="node_start",
        nodes={
            "node_start": DialogueNode(
                id="node_start",
                text="请选择效果。",
                options=(
                    DialogueOption(
                        id="option_apply",
                        text="执行。",
                        effects=tuple(effects),  # type: ignore[arg-type]
                    ),
                ),
            )
        },
    )
    world.start_dialogue("character_effect_probe")
    return world


class DialogueEffectsContentTests(unittest.TestCase):
    def _mutate_dialogues(self, mutate: object) -> None:
        with tempfile.TemporaryDirectory() as td:
            pack_path = Path(td) / "pack"
            shutil.copytree(DEMO_PATH, pack_path)
            dialogues = json.loads((pack_path / "dialogues.json").read_text("utf-8"))
            mutate(dialogues)  # type: ignore[operator]
            (pack_path / "dialogues.json").write_text(
                json.dumps(dialogues, ensure_ascii=False), "utf-8"
            )
            with self.assertRaises(ContentValidationError):
                load_content_pack(pack_path)

    def test_effect_union_is_frozen_and_preserves_content_order(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        option = pack.dialogues["dialogue_elder_chen"].nodes[
            "node_observatory"
        ].options[1]
        self.assertEqual(
            tuple(type(effect) for effect in option.effects),
            (
                SetFlagEffect,
                AcceptQuestEffect,
                GrantExperienceEffect,
                GrantItemEffect,
            ),
        )
        with self.assertRaises(FrozenInstanceError):
            option.effects[0].value = False  # type: ignore[misc]
        for effect, attribute, replacement in (
            (GrantItemEffect("item_chen_token", 1), "quantity", 2),
            (GrantExperienceEffect(1), "amount", 2),
            (AcceptQuestEffect("quest_collect_ash_mite_gel"), "quest_id", "quest_other"),
            (SetFlagEffect("flag_probe", True), "value", False),
        ):
            with self.subTest(effect=type(effect).__name__):
                with self.assertRaises(FrozenInstanceError):
                    setattr(effect, attribute, replacement)

    def test_effects_are_required_but_empty_array_is_valid(self) -> None:
        self._mutate_dialogues(
            lambda dialogues: dialogues[0]["nodes"][0]["options"][0].pop(
                "effects"
            )
        )
        pack = load_content_pack(DEMO_PATH)
        self.assertEqual(
            pack.dialogues["dialogue_elder_chen"].nodes["node_greeting"].options[0].effects,
            (),
        )

    def test_legacy_field_unknown_kind_mixed_fields_and_bad_types_rejected(self) -> None:
        cases = (
            lambda options: options[0].update(
                grant_item={"item_id": "item_chen_token", "quantity": 1}
            ),
            lambda options: options[0].update(effects=[{"amount": 1}]),
            lambda options: options[0].update(
                effects=[{"kind": "unknown", "amount": 1}]
            ),
            lambda options: options[0].update(
                effects=[
                    {
                        "kind": "grant_item",
                        "item_id": "item_chen_token",
                        "quantity": 1,
                        "amount": 1,
                    }
                ]
            ),
            lambda options: options[0].update(
                effects=[
                    {
                        "kind": "grant_experience",
                        "amount": True,
                    }
                ]
            ),
            lambda options: options[0].update(
                effects=[
                    {
                        "kind": "grant_item",
                        "item_id": "item_chen_token",
                        "quantity": True,
                    }
                ]
            ),
            lambda options: options[0].update(
                effects=[
                    {
                        "kind": "set_flag",
                        "flag_id": "flag_probe",
                        "value": 1,
                    }
                ]
            ),
        )
        for case, mutate_options in enumerate(cases, 1):
            with self.subTest(case=case):
                self._mutate_dialogues(
                    lambda dialogues, mutate_options=mutate_options:
                    mutate_options(dialogues[0]["nodes"][0]["options"])
                )

    def test_invalid_references_and_per_option_duplicates_rejected(self) -> None:
        cases = (
            [{"kind": "grant_item", "item_id": "item_missing", "quantity": 1}],
            [{"kind": "accept_quest", "quest_id": "quest_missing"}],
            [{"kind": "set_flag", "flag_id": "Bad-ID", "value": True}],
            [
                {"kind": "grant_item", "item_id": "item_chen_token", "quantity": 1},
                {"kind": "grant_item", "item_id": "item_chen_token", "quantity": 1},
            ],
            [
                {"kind": "accept_quest", "quest_id": "quest_collect_ash_mite_gel"},
                {"kind": "accept_quest", "quest_id": "quest_collect_ash_mite_gel"},
            ],
            [
                {"kind": "set_flag", "flag_id": "flag_probe", "value": True},
                {"kind": "set_flag", "flag_id": "flag_probe", "value": False},
            ],
            [
                {"kind": "grant_experience", "amount": 1},
                {"kind": "grant_experience", "amount": 2},
            ],
        )
        for effects in cases:
            with self.subTest(effects=effects):
                self._mutate_dialogues(
                    lambda dialogues, effects=effects: dialogues[0]["nodes"][0]["options"][0].update(
                        effects=effects
                    )
                )


class DialogueEffectsWorldTests(unittest.TestCase):
    def test_all_four_effects_succeed_with_typed_ordered_outcomes(self) -> None:
        world = World.from_content_pack(load_content_pack(DEMO_PATH))
        world.move("east")
        world.start_dialogue("character_elder_chen")
        world.select_option(1)
        world.select_option(1)

        outcome = world.select_option(2)

        self.assertEqual(
            tuple(type(item) for item in outcome.effect_outcomes),
            (
                SetFlagEffectOutcome,
                AcceptQuestEffectOutcome,
                GrantExperienceEffectOutcome,
                GrantItemEffectOutcome,
            ),
        )
        self.assertEqual(world.flags, {"flag_chen_warned_ash_mite": True})
        self.assertIn("quest_collect_ash_mite_gel", world.quest_states)
        self.assertEqual(world.player.experience, 3)
        self.assertTrue(world.player.inventory.has_item("item_chen_token"))
        self.assertIsNone(world.active_dialogue)

    def test_accepting_an_already_ready_quest_completes_once(self) -> None:
        world = _world_with_effects(
            AcceptQuestEffect("quest_collect_ash_mite_gel")
        )
        world.player.inventory.add_stack("item_ash_mite_gel", 1)

        outcome = world.select_option(1)

        accepted = outcome.effect_outcomes[0]
        self.assertIsInstance(accepted, AcceptQuestEffectOutcome)
        self.assertEqual(
            tuple(item.quest_id for item in accepted.quest_outcomes),
            ("quest_collect_ash_mite_gel",),
        )
        self.assertTrue(world.quest_states["quest_collect_ash_mite_gel"].completed)
        self.assertEqual(world.player.experience, 5)
        with self.assertRaises(WorldRuleError):
            world.accept_quest("quest_collect_ash_mite_gel")
        self.assertEqual(world.player.experience, 5)

    def test_grant_item_uses_m3_collect_settlement(self) -> None:
        world = _world_with_effects(GrantItemEffect("item_chen_token", 1))
        quest = CollectItemQuestDefinition(
            id="quest_effect_token",
            name="收集效果铜牌",
            description="从效果中获得一枚铜牌。",
            trigger_room_id="room_ember_wharf",
            target_item_id="item_chen_token",
            required_quantity=1,
            reward_experience=5,
        )
        world.quest_defs[quest.id] = quest
        world.quest_states[quest.id] = QuestState(quest.id)

        outcome = world.select_option(1)

        granted = outcome.effect_outcomes[0]
        self.assertIsInstance(granted, GrantItemEffectOutcome)
        self.assertEqual(
            tuple(item.quest_id for item in granted.quest_outcomes), (quest.id,)
        )
        self.assertTrue(world.quest_states[quest.id].completed)
        self.assertEqual(world.player.experience, 5)

    def test_set_flag_missing_overwrite_and_idempotent_outcomes(self) -> None:
        first = _world_with_effects(SetFlagEffect("flag_probe", True))
        first_outcome = first.select_option(1).effect_outcomes[0]
        self.assertIsInstance(first_outcome, SetFlagEffectOutcome)
        self.assertEqual((first_outcome.old_value, first_outcome.new_value, first_outcome.changed), (None, True, True))

        second = _world_with_effects(SetFlagEffect("flag_probe", False))
        second.flags = dict(first.flags)
        second_outcome = second.select_option(1).effect_outcomes[0]
        self.assertEqual((second_outcome.old_value, second_outcome.new_value, second_outcome.changed), (True, False, True))

        third = _world_with_effects(SetFlagEffect("flag_probe", False))
        third.flags = dict(second.flags)
        third_outcome = third.select_option(1).effect_outcomes[0]
        self.assertEqual((third_outcome.old_value, third_outcome.new_value, third_outcome.changed), (False, False, False))

    def test_preflight_and_post_exception_leave_everything_unchanged(self) -> None:
        capacity_world = _world_with_effects(
            SetFlagEffect("flag_before_capacity", True),
            GrantItemEffect("item_chen_token", 1),
        )
        capacity_world.player.inventory.stacks = [
            ItemStack(item_id=f"item_fake_{index}", quantity=1)
            for index in range(capacity_world.player.inventory.capacity)
        ]
        dialogue_before = capacity_world.active_dialogue
        with self.assertRaises(WorldRuleError):
            capacity_world.select_option(1)
        self.assertEqual(capacity_world.flags, {})
        self.assertEqual(capacity_world.active_dialogue, dialogue_before)

        overflow_world = _world_with_effects(
            SetFlagEffect("flag_before_overflow", True),
            GrantItemEffect("item_stack_probe", 1),
        )
        overflow_world.items["item_stack_probe"] = Item(
            id="item_stack_probe",
            name="Stack probe",
            description="Runtime-only stack-limit probe.",
            stack_limit=2,
        )
        overflow_world.player.inventory.add_stack("item_stack_probe", 2)
        dialogue_before = overflow_world.active_dialogue
        with self.assertRaises(WorldRuleError):
            overflow_world.select_option(1)
        self.assertEqual(overflow_world.flags, {})
        self.assertEqual(overflow_world.active_dialogue, dialogue_before)

        failure_world = _world_with_effects(
            SetFlagEffect("flag_before_failure", True),
            GrantExperienceEffect(3),
        )
        dialogue_before = failure_world.active_dialogue
        with patch(
            "lore2mud.engine.world.grant_experience",
            side_effect=RuntimeError("post effect failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "post effect failure"):
                failure_world.select_option(1)
        self.assertEqual(failure_world.flags, {})
        self.assertEqual(failure_world.player.experience, 0)
        self.assertEqual(failure_world.active_dialogue, dialogue_before)

    def test_explicit_duplicate_accept_rejects_the_entire_option(self) -> None:
        for completed in (False, True):
            with self.subTest(completed=completed):
                world = _world_with_effects(
                    SetFlagEffect("flag_should_not_change", True),
                    AcceptQuestEffect("quest_collect_ash_mite_gel"),
                )
                world.quest_states["quest_collect_ash_mite_gel"] = QuestState(
                    "quest_collect_ash_mite_gel", completed=completed
                )
                dialogue_before = world.active_dialogue

                with self.assertRaises(WorldRuleError):
                    world.select_option(1)

                self.assertEqual(world.flags, {})
                self.assertEqual(world.player.experience, 0)
                self.assertEqual(world.active_dialogue, dialogue_before)


class DialogueEffectsCommandAndSaveTests(unittest.TestCase):
    def test_cli_renders_effects_in_order_without_duplicate_task_or_level_lines(self) -> None:
        world = World.from_content_pack(load_content_pack(DEMO_PATH))
        world.move("east")
        world.player.inventory.add_stack("item_ash_mite_gel", 1)
        world.player.experience = 9
        commands = CommandProcessor(world)
        commands.execute("talk character_elder_chen")
        commands.execute("1")
        commands.execute("1")

        result = commands.execute("2")

        self.assertLess(result.text.index("标记 flag_chen_warned_ash_mite"), result.text.index("你接取了任务"))
        self.assertLess(result.text.index("你接取了任务"), result.text.index("你获得了 3 点经验"))
        self.assertLess(result.text.index("你获得了 3 点经验"), result.text.index("你获得了 旧铜牌"))
        self.assertEqual(result.text.count("任务完成：收集灰壳凝胶"), 1)
        self.assertEqual(result.text.count("你升到了 2 级！"), 1)

    def test_v8_flags_round_trip_and_load_does_not_execute_pending_effects(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack)
        world.move("east")
        world.start_dialogue("character_elder_chen")
        world.select_option(1)
        world.select_option(1)
        self.assertEqual(world.active_dialogue.current_node_id, "node_observatory")
        self.assertNotIn("quest_collect_ash_mite_gel", world.quest_states)

        with tempfile.TemporaryDirectory() as td:
            service = SaveLoadService(pack, Path(td))
            service.save(world)
            loaded = service.load()
            self.assertEqual(SAVE_FORMAT_VERSION, 9)
            self.assertEqual(loaded.flags, {})
            self.assertNotIn("quest_collect_ash_mite_gel", loaded.quest_states)
            self.assertEqual(loaded.player.experience, 0)
            self.assertFalse(loaded.player.inventory.has_item("item_chen_token"))

            save_data = json.loads(service.save_path.read_text("utf-8"))
            for invalid_flags in ({"Bad-ID": True}, {"flag_ok": 1}):
                save_data["flags"] = invalid_flags
                service.save_path.write_text(json.dumps(save_data), "utf-8")
                with self.assertRaises(SaveLoadError):
                    service.load()


if __name__ == "__main__":
    unittest.main()
