"""Tests for the dialogue system."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from lore2mud.content.loader import ContentValidationError, load_content_pack
from lore2mud.content.models import GrantItemEffect
from lore2mud.engine.commands import CommandProcessor
from lore2mud.inventory.models import ItemStack
from lore2mud.engine.models import Character, DialogueState
from lore2mud.engine.save import (
    SAVE_FORMAT_VERSION,
    SaveLoadError,
    SaveLoadService,
    _serialize_world,
)
from lore2mud.engine.world import (
    DialogueEndOutcome,
    GrantItemEffectOutcome,
    TalkOutcome,
    World,
    WorldRuleError,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = PROJECT_ROOT / "examples" / "original_demo"


def _demo_world() -> World:
    pack = load_content_pack(DEMO_PATH)
    return World.from_content_pack(pack, player_name="测试旅人")


def _world_at_chen() -> World:
    """World with player moved to room_glassgrass_path (where elder_chen is)."""
    w = _demo_world()
    w.move("east")
    return w


class ContentLoadingTests(unittest.TestCase):
    """A. Content loading tests for dialogues."""

    def test_valid_dialogue_loads(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        self.assertIn("dialogue_elder_chen", pack.dialogues)
        dlg = pack.dialogues["dialogue_elder_chen"]
        self.assertEqual(dlg.character_id, "character_elder_chen")
        self.assertIn("node_greeting", dlg.nodes)

    def test_reward_option_loads(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        option = pack.dialogues["dialogue_elder_chen"].nodes[
            "node_observatory"
        ].options[1]
        self.assertIsInstance(option.effects[-1], GrantItemEffect)
        self.assertEqual(option.effects[-1].item_id, "item_chen_token")

    def test_empty_dialogues_array_valid(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pack_path = Path(td) / "pack"
            shutil.copytree(DEMO_PATH, pack_path)
            (pack_path / "dialogues.json").write_text("[]", "utf-8")
            pack = load_content_pack(pack_path)
            self.assertEqual(pack.dialogues, {})

    def test_missing_dialogues_json_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pack_path = Path(td) / "pack"
            shutil.copytree(DEMO_PATH, pack_path)
            (pack_path / "dialogues.json").unlink()
            with self.assertRaises(ContentValidationError):
                load_content_pack(pack_path)

    def test_dialogue_references_nonexistent_character(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pack_path = Path(td) / "pack"
            shutil.copytree(DEMO_PATH, pack_path)
            dlg = [{"id": "d1", "character_id": "no_such_char",
                    "start_node_id": "n1",
                    "nodes": [{"id": "n1", "text": "Hi", "options": []}]}]
            (pack_path / "dialogues.json").write_text(
                json.dumps(dlg, ensure_ascii=False), "utf-8"
            )
            with self.assertRaises(ContentValidationError) as ctx:
                load_content_pack(pack_path)
            self.assertIn("no_such_char", str(ctx.exception))

    def test_start_node_not_in_nodes_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pack_path = Path(td) / "pack"
            shutil.copytree(DEMO_PATH, pack_path)
            dlg = [{"id": "d1", "character_id": "character_elder_chen",
                    "start_node_id": "no_such_node",
                    "nodes": [{"id": "n1", "text": "Hi", "options": []}]}]
            (pack_path / "dialogues.json").write_text(
                json.dumps(dlg, ensure_ascii=False), "utf-8"
            )
            with self.assertRaises(ContentValidationError) as ctx:
                load_content_pack(pack_path)
            self.assertIn("no_such_node", str(ctx.exception))

    def test_next_node_not_in_nodes_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pack_path = Path(td) / "pack"
            shutil.copytree(DEMO_PATH, pack_path)
            dlg = [{"id": "d1", "character_id": "character_elder_chen",
                    "start_node_id": "n1",
                    "nodes": [{"id": "n1", "text": "Hi", "options": [
                        {"id": "o1", "text": "Go", "next_node_id": "n2", "effects": []}
                    ]}]}]
            (pack_path / "dialogues.json").write_text(
                json.dumps(dlg, ensure_ascii=False), "utf-8"
            )
            with self.assertRaises(ContentValidationError) as ctx:
                load_content_pack(pack_path)
            self.assertIn("n2", str(ctx.exception))

    def test_duplicate_node_id_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pack_path = Path(td) / "pack"
            shutil.copytree(DEMO_PATH, pack_path)
            dlg = [{"id": "d1", "character_id": "character_elder_chen",
                    "start_node_id": "n1",
                    "nodes": [
                        {"id": "n1", "text": "A", "options": []},
                        {"id": "n1", "text": "B", "options": []},
                    ]}]
            (pack_path / "dialogues.json").write_text(
                json.dumps(dlg, ensure_ascii=False), "utf-8"
            )
            with self.assertRaises(ContentValidationError) as ctx:
                load_content_pack(pack_path)
            self.assertIn("重复", str(ctx.exception))

    def test_duplicate_option_id_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pack_path = Path(td) / "pack"
            shutil.copytree(DEMO_PATH, pack_path)
            dlg = [{"id": "d1", "character_id": "character_elder_chen",
                    "start_node_id": "n1",
                    "nodes": [{"id": "n1", "text": "Hi", "options": [
                        {"id": "o1", "text": "A", "effects": []},
                        {"id": "o1", "text": "B", "effects": []},
                    ]}]}]
            (pack_path / "dialogues.json").write_text(
                json.dumps(dlg, ensure_ascii=False), "utf-8"
            )
            with self.assertRaises(ContentValidationError) as ctx:
                load_content_pack(pack_path)
            self.assertIn("重复", str(ctx.exception))

    def test_empty_node_text_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pack_path = Path(td) / "pack"
            shutil.copytree(DEMO_PATH, pack_path)
            dlg = [{"id": "d1", "character_id": "character_elder_chen",
                    "start_node_id": "n1",
                    "nodes": [{"id": "n1", "text": "", "options": []}]}]
            (pack_path / "dialogues.json").write_text(
                json.dumps(dlg, ensure_ascii=False), "utf-8"
            )
            with self.assertRaises(ContentValidationError):
                load_content_pack(pack_path)

    def test_empty_option_text_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pack_path = Path(td) / "pack"
            shutil.copytree(DEMO_PATH, pack_path)
            dlg = [{"id": "d1", "character_id": "character_elder_chen",
                    "start_node_id": "n1",
                    "nodes": [{"id": "n1", "text": "Hi", "options": [
                        {"id": "o1", "text": "", "effects": []}
                    ]}]}]
            (pack_path / "dialogues.json").write_text(
                json.dumps(dlg, ensure_ascii=False), "utf-8"
            )
            with self.assertRaises(ContentValidationError):
                load_content_pack(pack_path)

    def test_multiple_dialogues_per_character_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pack_path = Path(td) / "pack"
            shutil.copytree(DEMO_PATH, pack_path)
            dlg = [
                {"id": "d1", "character_id": "character_elder_chen",
                 "start_node_id": "n1",
                 "nodes": [{"id": "n1", "text": "A", "options": []}]},
                {"id": "d2", "character_id": "character_elder_chen",
                 "start_node_id": "n2",
                 "nodes": [{"id": "n2", "text": "B", "options": []}]},
            ]
            (pack_path / "dialogues.json").write_text(
                json.dumps(dlg, ensure_ascii=False), "utf-8"
            )
            with self.assertRaises(ContentValidationError) as ctx:
                load_content_pack(pack_path)
            self.assertIn("多个", str(ctx.exception))

    def test_invalid_stable_id_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pack_path = Path(td) / "pack"
            shutil.copytree(DEMO_PATH, pack_path)
            dlg = [{"id": "Bad-ID", "character_id": "character_elder_chen",
                    "start_node_id": "n1",
                    "nodes": [{"id": "n1", "text": "Hi", "options": []}]}]
            (pack_path / "dialogues.json").write_text(
                json.dumps(dlg, ensure_ascii=False), "utf-8"
            )
            with self.assertRaises(ContentValidationError):
                load_content_pack(pack_path)

    def test_terminal_node_empty_options_valid(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pack_path = Path(td) / "pack"
            shutil.copytree(DEMO_PATH, pack_path)
            dlg = [{"id": "d1", "character_id": "character_elder_chen",
                    "start_node_id": "n1",
                    "nodes": [{"id": "n1", "text": "Bye.", "options": []}]}]
            (pack_path / "dialogues.json").write_text(
                json.dumps(dlg, ensure_ascii=False), "utf-8"
            )
            pack = load_content_pack(pack_path)
            self.assertIn("d1", pack.dialogues)

    def test_missing_options_key_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pack_path = Path(td) / "pack"
            shutil.copytree(DEMO_PATH, pack_path)
            dlg = [{"id": "d1", "character_id": "character_elder_chen",
                    "start_node_id": "n1",
                    "nodes": [{"id": "n1", "text": "Hi"}]}]
            (pack_path / "dialogues.json").write_text(
                json.dumps(dlg, ensure_ascii=False), "utf-8"
            )
            with self.assertRaises(ContentValidationError) as ctx:
                load_content_pack(pack_path)
            self.assertIn("options", str(ctx.exception))

    def test_unknown_field_in_dialogue_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pack_path = Path(td) / "pack"
            shutil.copytree(DEMO_PATH, pack_path)
            dlg = [{"id": "d1", "character_id": "character_elder_chen",
                    "start_node_id": "n1", "bogus": True,
                    "nodes": [{"id": "n1", "text": "Hi", "options": []}]}]
            (pack_path / "dialogues.json").write_text(
                json.dumps(dlg, ensure_ascii=False), "utf-8"
            )
            with self.assertRaises(ContentValidationError) as ctx:
                load_content_pack(pack_path)
            self.assertIn("bogus", str(ctx.exception))

    def test_unknown_field_in_node_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pack_path = Path(td) / "pack"
            shutil.copytree(DEMO_PATH, pack_path)
            dlg = [{"id": "d1", "character_id": "character_elder_chen",
                    "start_node_id": "n1",
                    "nodes": [{"id": "n1", "text": "Hi", "options": [],
                                "bogus": True}]}]
            (pack_path / "dialogues.json").write_text(
                json.dumps(dlg, ensure_ascii=False), "utf-8"
            )
            with self.assertRaises(ContentValidationError) as ctx:
                load_content_pack(pack_path)
            self.assertIn("bogus", str(ctx.exception))

    def test_unknown_field_in_option_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pack_path = Path(td) / "pack"
            shutil.copytree(DEMO_PATH, pack_path)
            dlg = [{"id": "d1", "character_id": "character_elder_chen",
                    "start_node_id": "n1",
                    "nodes": [{"id": "n1", "text": "Hi", "options": [
                        {"id": "o1", "text": "Go", "effects": [], "bogus": True}
                    ]}]}]
            (pack_path / "dialogues.json").write_text(
                json.dumps(dlg, ensure_ascii=False), "utf-8"
            )
            with self.assertRaises(ContentValidationError) as ctx:
                load_content_pack(pack_path)
            self.assertIn("bogus", str(ctx.exception))

    def test_option_omitted_next_node_id_treated_as_null(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pack_path = Path(td) / "pack"
            shutil.copytree(DEMO_PATH, pack_path)
            dlg = [{"id": "d1", "character_id": "character_elder_chen",
                    "start_node_id": "n1",
                    "nodes": [{"id": "n1", "text": "Hi", "options": [
                        {"id": "o1", "text": "Bye", "effects": []}
                    ]}]}]
            (pack_path / "dialogues.json").write_text(
                json.dumps(dlg, ensure_ascii=False), "utf-8"
            )
            pack = load_content_pack(pack_path)
            opt = pack.dialogues["d1"].nodes["n1"].options[0]
            self.assertIsNone(opt.next_node_id)

    def test_reward_item_must_exist(self) -> None:
        self._assert_invalid_grant("item_missing")

    def test_reward_item_must_be_nonempty_stable_id(self) -> None:
        self._assert_invalid_grant("")
        self._assert_invalid_grant("Bad-ID")

    def test_reward_item_rejects_non_string(self) -> None:
        self._assert_invalid_grant(123)
        self._assert_invalid_grant(None)

    def test_reward_item_cannot_be_consumable(self) -> None:
        self._assert_invalid_grant("item_linglu_pill")

    def test_reward_item_cannot_be_placed_in_room(self) -> None:
        self._assert_invalid_grant("item_spark_lantern")

    def test_reward_item_cannot_be_granted_by_multiple_options(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pack_path = Path(td) / "pack"
            shutil.copytree(DEMO_PATH, pack_path)
            dialogues = json.loads(
                (pack_path / "dialogues.json").read_text("utf-8")
            )
            dialogues[0]["nodes"][0]["options"][0]["effects"] = [
                {"kind": "grant_item", "item_id": "item_chen_token", "quantity": 1}
            ]
            (pack_path / "dialogues.json").write_text(
                json.dumps(dialogues, ensure_ascii=False), "utf-8"
            )
            with self.assertRaises(ContentValidationError) as ctx:
                load_content_pack(pack_path)
            self.assertIn("被多个来源引用", str(ctx.exception))

    def test_reward_validation_errors_are_aggregated(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pack_path = Path(td) / "pack"
            shutil.copytree(DEMO_PATH, pack_path)
            dialogues = json.loads(
                (pack_path / "dialogues.json").read_text("utf-8")
            )
            dialogues[0]["nodes"][0]["options"][0]["effects"] = [
                {"kind": "grant_item", "item_id": "item_chen_token", "quantity": 1}
            ]
            dialogues[0]["nodes"][0]["options"][1]["effects"] = [
                {"kind": "grant_item", "item_id": "item_linglu_pill", "quantity": 1}
            ]
            (pack_path / "dialogues.json").write_text(
                json.dumps(dialogues, ensure_ascii=False), "utf-8"
            )
            with self.assertRaises(ContentValidationError) as ctx:
                load_content_pack(pack_path)
            self.assertIn("被多个来源引用", str(ctx.exception))
            self.assertIn("消耗品", str(ctx.exception))

    def _assert_invalid_grant(self, value: object) -> None:
        with tempfile.TemporaryDirectory() as td:
            pack_path = Path(td) / "pack"
            shutil.copytree(DEMO_PATH, pack_path)
            dialogues = json.loads(
                (pack_path / "dialogues.json").read_text("utf-8")
            )
            dialogues[0]["nodes"][0]["options"][0]["effects"] = [
                {"kind": "grant_item", "item_id": value, "quantity": 1}
            ]
            (pack_path / "dialogues.json").write_text(
                json.dumps(dialogues, ensure_ascii=False), "utf-8"
            )
            with self.assertRaises(ContentValidationError):
                load_content_pack(pack_path)


class WorldDialogueNormalTests(unittest.TestCase):
    """B. World dialogue tests — normal paths."""

    def test_start_dialogue_normal(self) -> None:
        w = _world_at_chen()
        o = w.start_dialogue("character_elder_chen")
        self.assertIsInstance(o, TalkOutcome)
        self.assertEqual(o.character_id, "character_elder_chen")
        self.assertEqual(o.character_name, "老陈")
        self.assertEqual(o.dialogue_id, "dialogue_elder_chen")
        self.assertIsNotNone(o.node_id)
        self.assertIsNotNone(o.node_text)
        self.assertGreater(len(o.options), 0)
        self.assertFalse(o.ended)

    def test_select_option_advance(self) -> None:
        w = _world_at_chen()
        w.start_dialogue("character_elder_chen")
        o = w.select_option(1)  # 你是谁？
        self.assertFalse(o.ended)
        self.assertIn("陈伯", o.node_text)
        self.assertEqual(o.effect_outcomes, ())

    def test_select_farewell_option_ends(self) -> None:
        w = _world_at_chen()
        w.start_dialogue("character_elder_chen")
        o = w.select_option(3)  # 告辞
        self.assertTrue(o.ended)
        self.assertIsNone(o.node_id)
        self.assertIsNone(o.node_text)
        self.assertIsNone(w.active_dialogue)

    def test_select_option_to_terminal_node(self) -> None:
        """Selecting an option whose target has no options auto-ends."""
        w = _world_at_chen()
        from lore2mud.content.models import (
            DialogueDefinition,
            DialogueNode,
            DialogueOption,
        )
        # Add a new character with a dialogue containing a terminal node
        w.characters["char_term"] = Character(
            "char_term", "终端者", "desc", "room_glassgrass_path"
        )
        nodes = {
            "n1": DialogueNode("n1", "Hello", (
                DialogueOption("o1", "Go", "n2"),
            )),
            "n2": DialogueNode("n2", "Goodbye.", ()),
        }
        w.dialogue_defs["d_term"] = DialogueDefinition(
            "d_term", "char_term", "n1", nodes
        )
        o = w.start_dialogue("char_term")
        self.assertFalse(o.ended)
        o = w.select_option(1)
        self.assertTrue(o.ended)
        self.assertEqual(o.node_id, "n2")
        self.assertEqual(o.node_text, "Goodbye.")
        self.assertIsNone(w.active_dialogue)

    def test_end_dialogue_normal(self) -> None:
        w = _world_at_chen()
        w.start_dialogue("character_elder_chen")
        o = w.end_dialogue()
        self.assertIsInstance(o, DialogueEndOutcome)
        self.assertEqual(o.character_name, "老陈")
        self.assertIsNone(w.active_dialogue)

    def test_start_dialogue_redisplays_same_character(self) -> None:
        w = _world_at_chen()
        o1 = w.start_dialogue("character_elder_chen")
        o2 = w.start_dialogue("character_elder_chen")
        self.assertEqual(o1.node_id, o2.node_id)
        self.assertEqual(o1.node_text, o2.node_text)

    def test_start_dialogue_switches_character(self) -> None:
        """Starting dialogue with a different character ends old one."""
        w = _world_at_chen()
        w.start_dialogue("character_elder_chen")
        self.assertIsNotNone(w.active_dialogue)
        # Add a second character in the same room
        w.characters["char2"] = Character("char2", "B", "desc",
                                          "room_glassgrass_path")
        from lore2mud.content.models import (
            DialogueDefinition,
            DialogueNode,
        )
        w.dialogue_defs["d2"] = DialogueDefinition(
            "d2", "char2", "n1",
            {"n1": DialogueNode("n1", "Hi", ())}
        )
        o = w.start_dialogue("char2")
        self.assertTrue(o.ended)  # terminal node
        self.assertNotEqual(o.dialogue_id, "dialogue_elder_chen")

    def test_move_clears_active_dialogue(self) -> None:
        w = _world_at_chen()
        w.start_dialogue("character_elder_chen")
        self.assertIsNotNone(w.active_dialogue)
        w.move("east")
        self.assertIsNone(w.active_dialogue)


class DialogueItemGrantWorldTests(unittest.TestCase):
    """Dialogue item grants are atomic and are the only dialogue side effect."""

    @staticmethod
    def _at_reward_option() -> World:
        world = _world_at_chen()
        world.start_dialogue("character_elder_chen")
        world.select_option(1)
        world.select_option(1)
        return world

    def test_ending_option_grants_hidden_item(self) -> None:
        world = self._at_reward_option()

        outcome = world.select_option(2)

        self.assertTrue(outcome.ended)
        granted = outcome.effect_outcomes[-1]
        self.assertIsInstance(granted, GrantItemEffectOutcome)
        self.assertEqual(granted.item_id, "item_chen_token")
        self.assertEqual(granted.item_name, "旧铜牌")
        self.assertIn("item_chen_token", [s.item_id for s in world.player.inventory.stacks])
        self.assertIsNone(world.active_dialogue)

    def test_full_inventory_rejects_without_state_change(self) -> None:
        world = self._at_reward_option()
        world.player.inventory.stacks = [ItemStack(item_id=f"item_{index}", quantity=1) for index in range(10)]
        inventory_before = [s.item_id for s in world.player.inventory.stacks]
        rooms_before = {key: [s.item_id for s in room.item_stacks] for key, room in world.rooms.items()}
        equipped_before = (world.equipped.hand, world.equipped.body)
        quests_before = dict(world.quest_states)
        dialogue_before = world.active_dialogue

        with self.assertRaises(WorldRuleError) as ctx:
            world.select_option(2)

        self.assertIn("背包已满", str(ctx.exception))
        self.assertEqual([s.item_id for s in world.player.inventory.stacks], inventory_before)
        self.assertEqual(
            {key: [s.item_id for s in room.item_stacks] for key, room in world.rooms.items()},
            rooms_before,
        )
        self.assertEqual((world.equipped.hand, world.equipped.body), equipped_before)
        self.assertEqual(dict(world.quest_states), quests_before)
        self.assertEqual(world.active_dialogue, dialogue_before)

    def test_repeated_reward_selection_is_rejected_without_state_change(self) -> None:
        from lore2mud.content.models import (
            DialogueDefinition,
            DialogueNode,
            DialogueOption,
        )

        world = _world_at_chen()
        world.characters["char_repeat"] = Character(
            "char_repeat", "循环者", "desc", "room_glassgrass_path"
        )
        world.dialogue_defs["dialogue_repeat"] = DialogueDefinition(
            "dialogue_repeat",
            "char_repeat",
            "node_repeat",
            {
                "node_repeat": DialogueNode(
                    "node_repeat",
                    "再试一次。",
                    (
                        DialogueOption(
                            "opt_repeat",
                            "领取铜牌",
                            "node_repeat",
                            effects=(GrantItemEffect("item_chen_token", 1),),
                        ),
                    ),
                )
            },
        )
        world.start_dialogue("char_repeat")
        world.select_option(1)
        dialogue_before = world.active_dialogue

        with self.assertRaises(WorldRuleError) as ctx:
            world.select_option(1)

        self.assertIn("已经拥有", str(ctx.exception))
        self.assertEqual([s.item_id for s in world.player.inventory.stacks], ["item_chen_token"])
        self.assertEqual(world.active_dialogue, dialogue_before)

    def test_reward_can_end_at_terminal_node(self) -> None:
        from lore2mud.content.models import (
            DialogueDefinition,
            DialogueNode,
            DialogueOption,
        )

        world = _world_at_chen()
        world.characters["char_terminal"] = Character(
            "char_terminal", "终端者", "desc", "room_glassgrass_path"
        )
        world.dialogue_defs["dialogue_terminal_reward"] = DialogueDefinition(
            "dialogue_terminal_reward",
            "char_terminal",
            "node_start",
            {
                "node_start": DialogueNode(
                    "node_start",
                    "拿好。",
                    (
                        DialogueOption(
                            "opt_take",
                            "收下",
                            "node_terminal",
                            effects=(GrantItemEffect("item_chen_token", 1),),
                        ),
                    ),
                ),
                "node_terminal": DialogueNode("node_terminal", "再会。", ()),
            },
        )
        world.start_dialogue("char_terminal")

        outcome = world.select_option(1)

        self.assertTrue(outcome.ended)
        self.assertEqual(outcome.node_id, "node_terminal")
        self.assertIsInstance(outcome.effect_outcomes[0], GrantItemEffectOutcome)
        self.assertEqual(outcome.effect_outcomes[0].item_id, "item_chen_token")
        self.assertIn("item_chen_token", [s.item_id for s in world.player.inventory.stacks])


class WorldDialogueFailureTests(unittest.TestCase):
    """C. World dialogue tests — failure paths."""

    def test_start_unknown_character(self) -> None:
        w = _world_at_chen()
        with self.assertRaises(WorldRuleError) as ctx:
            w.start_dialogue("nobody")
        self.assertIn("这里没有", str(ctx.exception))

    def test_start_character_not_in_room(self) -> None:
        w = _demo_world()  # player in room_ember_wharf, chen in room_glassgrass
        with self.assertRaises(WorldRuleError) as ctx:
            w.start_dialogue("character_elder_chen")
        self.assertIn("这里没有", str(ctx.exception))

    def test_start_character_without_dialogue(self) -> None:
        w = _world_at_chen()
        w.characters["char_no_dlg"] = Character(
            "char_no_dlg", "沉默者", "desc", "room_glassgrass_path"
        )
        with self.assertRaises(WorldRuleError) as ctx:
            w.start_dialogue("char_no_dlg")
        self.assertIn("无话可说", str(ctx.exception))

    def test_select_option_no_active_dialogue(self) -> None:
        w = _world_at_chen()
        with self.assertRaises(WorldRuleError) as ctx:
            w.select_option(1)
        self.assertIn("没有在和任何人对话", str(ctx.exception))

    def test_select_option_index_zero(self) -> None:
        w = _world_at_chen()
        w.start_dialogue("character_elder_chen")
        with self.assertRaises(WorldRuleError) as ctx:
            w.select_option(0)
        self.assertIn("无效", str(ctx.exception))

    def test_select_option_index_out_of_range(self) -> None:
        w = _world_at_chen()
        w.start_dialogue("character_elder_chen")
        with self.assertRaises(WorldRuleError) as ctx:
            w.select_option(99)
        self.assertIn("无效", str(ctx.exception))

    def test_end_dialogue_no_active(self) -> None:
        w = _world_at_chen()
        with self.assertRaises(WorldRuleError) as ctx:
            w.end_dialogue()
        self.assertIn("没有在和任何人对话", str(ctx.exception))


class WorldStateInvarianceTests(unittest.TestCase):
    """D. Dialogue operations must not change game state."""

    def setUp(self) -> None:
        self.w = _world_at_chen()
        self.w.start_dialogue("character_elder_chen")
        self.hp = self.w.player.hp
        self.atk = self.w.player.attack
        self.dfn = self.w.player.defense
        self.lvl = self.w.player.level
        self.exp = self.w.player.experience

    def _assert_unchanged(self) -> None:
        self.assertEqual(self.w.player.hp, self.hp)
        self.assertEqual(self.w.player.attack, self.atk)
        self.assertEqual(self.w.player.defense, self.dfn)
        self.assertEqual(self.w.player.level, self.lvl)
        self.assertEqual(self.w.player.experience, self.exp)

    def test_select_option_preserves_player_stats(self) -> None:
        self.w.select_option(1)
        self._assert_unchanged()

    def test_select_option_preserves_inventory(self) -> None:
        inv_before = [s.item_id for s in self.w.player.inventory.stacks]
        self.w.select_option(1)
        self.assertEqual([s.item_id for s in self.w.player.inventory.stacks], inv_before)

    def test_select_option_preserves_equipped(self) -> None:
        hand = self.w.equipped.hand
        body = self.w.equipped.body
        self.w.select_option(1)
        self.assertEqual(self.w.equipped.hand, hand)
        self.assertEqual(self.w.equipped.body, body)

    def test_select_option_preserves_quest_states(self) -> None:
        qs_before = dict(self.w.quest_states)
        self.w.select_option(1)
        self.assertEqual(dict(self.w.quest_states), qs_before)

    def test_select_option_preserves_room_items(self) -> None:
        items_before = {
            rid: [s.item_id for s in r.item_stacks] for rid, r in self.w.rooms.items()
        }
        self.w.select_option(1)
        for rid, r in self.w.rooms.items():
            self.assertEqual([s.item_id for s in r.item_stacks], items_before[rid])

    def test_select_option_preserves_monster_hp(self) -> None:
        hp_before = {mid: m.hp for mid, m in self.w.monsters.items()}
        self.w.select_option(1)
        for mid, m in self.w.monsters.items():
            self.assertEqual(m.hp, hp_before[mid])

    def test_end_dialogue_preserves_player_stats(self) -> None:
        self.w.end_dialogue()
        self._assert_unchanged()

    def test_end_dialogue_preserves_room_state(self) -> None:
        items_before = {
            rid: [s.item_id for s in r.item_stacks] for rid, r in self.w.rooms.items()
        }
        self.w.end_dialogue()
        for rid, r in self.w.rooms.items():
            self.assertEqual([s.item_id for s in r.item_stacks], items_before[rid])


class SaveLoadDialogueTests(unittest.TestCase):
    """E. Save/load tests for dialogue state."""

    def setUp(self) -> None:
        self.pack = load_content_pack(DEMO_PATH)
        self.world = _world_at_chen()
        self.world.start_dialogue("character_elder_chen")
        with tempfile.TemporaryDirectory() as td:
            self.save_dir = Path(td)

    def _service(self) -> SaveLoadService:
        return SaveLoadService(self.pack, self.save_dir)

    def test_save_includes_active_dialogue(self) -> None:
        data = _serialize_world(self.world)
        self.assertIsNotNone(data["active_dialogue"])
        self.assertEqual(
            data["active_dialogue"]["dialogue_id"], "dialogue_elder_chen"
        )

    def test_save_null_when_no_dialogue(self) -> None:
        self.world.active_dialogue = None
        data = _serialize_world(self.world)
        self.assertIsNone(data["active_dialogue"])

    def test_load_restores_active_dialogue(self) -> None:
        svc = self._service()
        svc.save(self.world)
        loaded = svc.load()
        self.assertIsNotNone(loaded.active_dialogue)
        self.assertEqual(
            loaded.active_dialogue.dialogue_id, "dialogue_elder_chen"
        )

    def test_load_rejects_nonexistent_dialogue(self) -> None:
        svc = self._service()
        svc.save(self.world)
        txt = svc.save_path.read_text("utf-8")
        txt = txt.replace("dialogue_elder_chen", "dialogue_bogus")
        svc.save_path.write_text(txt, "utf-8")
        with self.assertRaises(SaveLoadError) as ctx:
            svc.load()
        self.assertIn("dialogue_bogus", str(ctx.exception))

    def test_load_rejects_nonexistent_node(self) -> None:
        svc = self._service()
        svc.save(self.world)
        txt = svc.save_path.read_text("utf-8")
        txt = txt.replace("node_greeting", "node_bogus")
        svc.save_path.write_text(txt, "utf-8")
        with self.assertRaises(SaveLoadError) as ctx:
            svc.load()
        self.assertIn("node_bogus", str(ctx.exception))

    def test_load_rejects_terminal_node_via_custom_pack(self) -> None:
        """Load rejects a save whose active_dialogue points to a terminal node."""
        with tempfile.TemporaryDirectory() as td:
            pack_path = Path(td) / "pack"
            shutil.copytree(DEMO_PATH, pack_path)
            dlg = [{
                "id": "d_term",
                "character_id": "character_elder_chen",
                "start_node_id": "n1",
                "nodes": [
                    {"id": "n1", "text": "Hello", "options": [
                        {"id": "o1", "text": "Go", "next_node_id": "n2", "effects": []}
                    ]},
                    {"id": "n2", "text": "Goodbye.", "options": []},
                ]
            }]
            (pack_path / "dialogues.json").write_text(
                json.dumps(dlg, ensure_ascii=False), "utf-8"
            )
            pack = load_content_pack(pack_path)
            # Build a manual JSON save pointing to terminal node n2
            save_data = {
                "save_format_version": SAVE_FORMAT_VERSION,
                "content_pack": {"id": pack.id, "version": pack.version},
                "player": {
                    "id": "player_local", "name": "test",
                    "room_id": "room_glassgrass_path",
                    "max_hp": 20, "hp": 20, "attack": 5, "defense": 1,
                    "level": 1, "experience": 0, "coins": 20,
                    "inventory_stacks": [],
                },
                "equipped": {"hand": None, "body": None},
                "rooms": {
                    rid: {"item_stacks": [{"item_id": s.item_id, "quantity": s.quantity} for s in r.item_stacks],
                          "monster_ids": list(r.monster_ids)}
                    for rid, r in pack.rooms.items()
                },
                "monsters": {
                    mid: {"hp": m.max_hp}
                    for mid, m in pack.monsters.items()
                },
                "quest_states": {},
                "flags": {},
                "active_dialogue": {
                    "dialogue_id": "d_term",
                    "current_node_id": "n2",
                },
            }
            svc2 = SaveLoadService(pack, Path(td))
            svc2.save_path.write_text(
                json.dumps(save_data, ensure_ascii=False), "utf-8"
            )
            with self.assertRaises(SaveLoadError) as ctx:
                svc2.load()
            self.assertIn("终端节点", str(ctx.exception))



    def test_load_rejects_missing_active_dialogue_field(self) -> None:
        svc = self._service()
        svc.save(self.world)
        txt = svc.save_path.read_text("utf-8")
        data = json.loads(txt)
        del data["active_dialogue"]
        svc.save_path.write_text(json.dumps(data), "utf-8")
        with self.assertRaises(SaveLoadError) as ctx:
            svc.load()
        self.assertIn("active_dialogue", str(ctx.exception))

    def test_load_rejects_missing_dialogue_id(self) -> None:
        svc = self._service()
        svc.save(self.world)
        txt = svc.save_path.read_text("utf-8")
        data = json.loads(txt)
        data["active_dialogue"] = {"current_node_id": "node_greeting"}
        svc.save_path.write_text(json.dumps(data), "utf-8")
        with self.assertRaises(SaveLoadError) as ctx:
            svc.load()
        self.assertIn("dialogue_id", str(ctx.exception))

    def test_load_rejects_unknown_dialogue_field(self) -> None:
        svc = self._service()
        svc.save(self.world)
        txt = svc.save_path.read_text("utf-8")
        data = json.loads(txt)
        data["active_dialogue"]["bogus"] = True
        svc.save_path.write_text(json.dumps(data), "utf-8")
        with self.assertRaises(SaveLoadError) as ctx:
            svc.load()
        self.assertIn("bogus", str(ctx.exception))

    def test_v4_save_rejected(self) -> None:
        svc = self._service()
        svc.save(self.world)
        txt = svc.save_path.read_text("utf-8")
        txt = txt.replace(
            f'"save_format_version": {SAVE_FORMAT_VERSION}',
            '"save_format_version": 4',
        )
        svc.save_path.write_text(txt, "utf-8")
        with self.assertRaises(SaveLoadError) as ctx:
            svc.load()
        self.assertIn("格式版本", str(ctx.exception))

    def test_save_load_round_trip_preserves_position(self) -> None:
        svc = self._service()
        # Advance to introduce node
        self.world.select_option(1)
        node_before = self.world.active_dialogue.current_node_id
        svc.save(self.world)
        loaded = svc.load()
        self.assertEqual(
            loaded.active_dialogue.current_node_id, node_before
        )

    def test_save_load_round_trip_preserves_dialogue_reward_item(self) -> None:
        svc = self._service()
        self.world.select_option(1)
        self.world.select_option(1)
        self.world.select_option(2)
        svc.save(self.world)

        loaded = svc.load()

        self.assertIn("item_chen_token", [s.item_id for s in loaded.player.inventory.stacks])
        self.assertIsNone(loaded.active_dialogue)

class SaveTimeValidationTests(unittest.TestCase):
    """Tests that invalid active_dialogue is rejected at save time."""

    def setUp(self) -> None:
        self.pack = load_content_pack(DEMO_PATH)
        with tempfile.TemporaryDirectory() as td:
            self.save_dir = Path(td)

    def _service(self) -> SaveLoadService:
        return SaveLoadService(self.pack, self.save_dir)

    def test_save_rejects_terminal_node_pointer(self) -> None:
        """Saving with active_dialogue pointing to a terminal node fails."""
        w = _world_at_chen()
        w.start_dialogue("character_elder_chen")
        # Manually set to a terminal state
        from lore2mud.engine.models import DialogueState
        w.active_dialogue = DialogueState(
            dialogue_id="dialogue_elder_chen",
            current_node_id="node_area",  # has options, so OK
        )
        svc = self._service()
        svc.save(w)  # should succeed
        # Now force a terminal-like state: add a dialogue with empty options
        from lore2mud.content.models import DialogueDefinition, DialogueNode
        w.dialogue_defs["d_term"] = DialogueDefinition(
            "d_term", "character_elder_chen", "n1",
            {"n1": DialogueNode("n1", "Terminal.", ())}
        )
        w.active_dialogue = DialogueState("d_term", "n1")
        with self.assertRaises(SaveLoadError) as ctx:
            svc.save(w)
        self.assertIn("终端节点", str(ctx.exception))

    def test_save_rejects_dialogue_not_in_room(self) -> None:
        """Saving with active_dialogue character not in player room fails."""
        w = _world_at_chen()
        w.start_dialogue("character_elder_chen")
        svc = self._service()
        svc.save(w)  # OK
        # Move player away (dialogue should be cleared by move,
        # but manually set it to simulate a bug)
        from lore2mud.engine.models import DialogueState
        w.move("east")  # clears active_dialogue
        w.active_dialogue = DialogueState(
            dialogue_id="dialogue_elder_chen",
            current_node_id="node_greeting",
        )
        with self.assertRaises(SaveLoadError) as ctx:
            svc.save(w)
        self.assertIn("不一致", str(ctx.exception))

    def test_save_failure_preserves_original_file(self) -> None:
        """Failed save does not overwrite the existing save file."""
        w = _world_at_chen()
        w.start_dialogue("character_elder_chen")
        svc = self._service()
        svc.save(w)  # Create initial valid save
        original_content = svc.save_path.read_text("utf-8")
        # Now make the World invalid and try to save
        from lore2mud.engine.models import DialogueState
        w.move("east")
        w.active_dialogue = DialogueState(
            dialogue_id="dialogue_elder_chen",
            current_node_id="node_greeting",
        )
        with self.assertRaises(SaveLoadError):
            svc.save(w)
        # Verify the original save file is unchanged
        current_content = svc.save_path.read_text("utf-8")
        self.assertEqual(original_content, current_content)


class FailureInvarianceTests(unittest.TestCase):
    """Failed operations must not change World state."""

    def setUp(self) -> None:
        self.w = _world_at_chen()
        self.hp = self.w.player.hp
        self.atk = self.w.player.attack
        self.dfn = self.w.player.defense
        self.inv = [s.item_id for s in self.w.player.inventory.stacks]
        self.eq_hand = self.w.equipped.hand
        self.eq_body = self.w.equipped.body
        self.quests = dict(self.w.quest_states)

    def _assert_state_unchanged(self) -> None:
        self.assertEqual(self.w.player.hp, self.hp)
        self.assertEqual(self.w.player.attack, self.atk)
        self.assertEqual(self.w.player.defense, self.dfn)
        self.assertEqual([s.item_id for s in self.w.player.inventory.stacks], self.inv)
        self.assertEqual(self.w.equipped.hand, self.eq_hand)
        self.assertEqual(self.w.equipped.body, self.eq_body)
        self.assertEqual(dict(self.w.quest_states), self.quests)

    def test_start_dialogue_unknown_char_unchanged(self) -> None:
        with self.assertRaises(WorldRuleError):
            self.w.start_dialogue("nobody")
        self._assert_state_unchanged()
        self.assertIsNone(self.w.active_dialogue)

    def test_start_dialogue_wrong_room_unchanged(self) -> None:
        """Player in room_ember_wharf, chen in room_glassgrass_path."""
        w2 = _demo_world()  # player in room_ember_wharf, not room_glassgrass_path
        hp2 = w2.player.hp
        atk2 = w2.player.attack
        dfn2 = w2.player.defense
        with self.assertRaises(WorldRuleError):
            w2.start_dialogue("character_elder_chen")
        self.assertEqual(w2.player.hp, hp2)
        self.assertEqual(w2.player.attack, atk2)
        self.assertEqual(w2.player.defense, dfn2)
        self.assertIsNone(w2.active_dialogue)

    def test_select_option_no_dialogue_unchanged(self) -> None:
        with self.assertRaises(WorldRuleError):
            self.w.select_option(1)
        self._assert_state_unchanged()

    def test_select_option_out_of_range_unchanged(self) -> None:
        self.w.start_dialogue("character_elder_chen")
        before = self.w.active_dialogue.current_node_id
        with self.assertRaises(WorldRuleError):
            self.w.select_option(99)
        self._assert_state_unchanged()
        self.assertIsNotNone(self.w.active_dialogue)
        self.assertEqual(self.w.active_dialogue.current_node_id, before)

    def test_select_option_zero_unchanged(self) -> None:
        self.w.start_dialogue("character_elder_chen")
        before = self.w.active_dialogue.current_node_id
        with self.assertRaises(WorldRuleError):
            self.w.select_option(0)
        self._assert_state_unchanged()
        self.assertEqual(self.w.active_dialogue.current_node_id, before)

    def test_end_dialogue_no_active_unchanged(self) -> None:
        with self.assertRaises(WorldRuleError):
            self.w.end_dialogue()
        self._assert_state_unchanged()

class CommandIntegrationTests(unittest.TestCase):
    """F. Command integration tests for dialogue."""

    def setUp(self) -> None:
        self.pack = load_content_pack(DEMO_PATH)
        self.world = _world_at_chen()
        self.cmd = CommandProcessor(self.world)

    def test_talk_command(self) -> None:
        r = self.cmd.execute("talk character_elder_chen")
        self.assertIn("老陈", r.text)
        self.assertIn("荒地", r.text)
        self.assertIn("1.", r.text)

    def test_talk_no_argument(self) -> None:
        r = self.cmd.execute("talk")
        self.assertIn("用法", r.text)

    def test_bare_number_in_dialogue(self) -> None:
        self.cmd.execute("talk character_elder_chen")
        r = self.cmd.execute("1")
        self.assertIn("陈伯", r.text)

    def test_reward_option_renders_item_line(self) -> None:
        self.cmd.execute("talk character_elder_chen")
        self.cmd.execute("1")
        self.cmd.execute("1")

        result = self.cmd.execute("2")

        self.assertIn("你获得了 旧铜牌。", result.text)
        self.assertIn("对话结束", result.text)
        self.assertIn("item_chen_token", [s.item_id for s in self.world.player.inventory.stacks])

    def test_bye_in_dialogue(self) -> None:
        self.cmd.execute("talk character_elder_chen")
        r = self.cmd.execute("bye")
        self.assertIn("结束", r.text)
        self.assertIsNone(self.world.active_dialogue)

    def test_bare_number_outside_dialogue(self) -> None:
        r = self.cmd.execute("1")
        self.assertIn("未知指令", r.text)

    def test_bye_outside_dialogue(self) -> None:
        r = self.cmd.execute("bye")
        self.assertIn("未知指令", r.text)

    def test_look_shows_characters(self) -> None:
        r = self.cmd.execute("look")
        self.assertIn("老陈", r.text)
        self.assertIn("character_elder_chen", r.text)

    def test_go_during_dialogue_ends_it(self) -> None:
        self.cmd.execute("talk character_elder_chen")
        self.assertIsNotNone(self.world.active_dialogue)
        self.cmd.execute("go east")
        self.assertIsNone(self.world.active_dialogue)

    def test_help_includes_dialogue_commands(self) -> None:
        r = self.cmd.execute("help")
        self.assertIn("talk", r.text)
        self.assertIn("bye", r.text)

    def test_look_during_dialogue_keeps_it(self) -> None:
        self.cmd.execute("talk character_elder_chen")
        self.cmd.execute("look")
        self.assertIsNotNone(self.world.active_dialogue)

    def test_bare_zero_in_dialogue(self) -> None:
        self.cmd.execute("talk character_elder_chen")
        r = self.cmd.execute("0")
        self.assertIn("未知指令", r.text)

    def test_bare_negative_in_dialogue(self) -> None:
        self.cmd.execute("talk character_elder_chen")
        r = self.cmd.execute("-1")
        self.assertIn("未知指令", r.text)

    def test_bare_leading_zero_in_dialogue(self) -> None:
        self.cmd.execute("talk character_elder_chen")
        r = self.cmd.execute("01")
        self.assertIn("未知指令", r.text)

    def test_go_failed_preserves_dialogue(self) -> None:
        self.cmd.execute("talk character_elder_chen")
        self.assertIsNotNone(self.world.active_dialogue)
        r = self.cmd.execute("go north")  # no north exit
        self.assertIn("不能", r.text)
        self.assertIsNotNone(self.world.active_dialogue)

    def test_100000_boundary_returns_unknown(self) -> None:
        """6-digit '100000' exceeds 5-digit regex → unknown command."""
        self.cmd.execute("talk character_elder_chen")
        self.assertIsNotNone(self.world.active_dialogue)
        node_before = self.world.active_dialogue.current_node_id
        r = self.cmd.execute("100000")
        self.assertIn("未知指令", r.text)
        self.assertIsNotNone(self.world.active_dialogue)
        self.assertEqual(self.world.active_dialogue.current_node_id, node_before)

    def test_out_of_range_returns_invalid(self) -> None:
        """'99' in dialogue with3 options → invalid option, state unchanged."""
        self.cmd.execute("talk character_elder_chen")
        self.assertIsNotNone(self.world.active_dialogue)
        node_before = self.world.active_dialogue.current_node_id
        r = self.cmd.execute("99")
        self.assertIn("无效", r.text)
        self.assertIsNotNone(self.world.active_dialogue)
        self.assertEqual(self.world.active_dialogue.current_node_id, node_before)


if __name__ == "__main__":
    unittest.main()
