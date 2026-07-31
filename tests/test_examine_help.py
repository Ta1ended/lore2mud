"""M6 tests for typed examine, command help, and stable read-only errors."""

from __future__ import annotations

import copy
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import unittest

from lore2mud.content.loader import load_content_pack
from lore2mud.engine.commands import (
    COMMAND_SPECS,
    HELP_TEXT,
    CommandProcessor,
    _COMMAND_BY_TOKEN,
    _DEAD_ALLOWED,
)
from lore2mud.engine.save import SAVE_FORMAT_VERSION
from lore2mud.engine.world import (
    ExamineCharacterOutcome,
    ExamineItemOutcome,
    ExamineMonsterOutcome,
    World,
    WorldRuleError,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = PROJECT_ROOT / "examples" / "original_demo"
EXAMINE_USAGE = (
    "用法：examine [room|here|<目标ID或名称>|item <物品ID或名称>|"
    "monster <怪物ID或名称>|character <角色ID或名称>]"
)
AMBIGUOUS_ERROR = (
    "目标不唯一，请使用类型限定："
    "examine item|monster|character <目标ID或名称>。"
)


def _world() -> World:
    return World.from_content_pack(
        load_content_pack(DEMO_PATH), player_name="测试旅人"
    )


def _mutable_state(world: World) -> tuple[object, ...]:
    """Capture every mutable World branch relevant to save v7."""
    player = world.player
    return (
        (
            player.id,
            player.name,
            player.room_id,
            player.hp,
            player.max_hp,
            player.attack,
            player.defense,
            player.level,
            player.experience,
            player.coins,
        ),
        tuple(
            (stack.item_id, stack.quantity)
            for stack in player.inventory.stacks
        ),
        tuple(
            (
                room_id,
                tuple((stack.item_id, stack.quantity) for stack in room.item_stacks),
                tuple(room.monster_ids),
            )
            for room_id, room in sorted(world.rooms.items())
        ),
        tuple(
            (monster_id, monster.hp)
            for monster_id, monster in sorted(world.monsters.items())
        ),
        tuple(
            (quest_id, state.completed)
            for quest_id, state in sorted(world.quest_states.items())
        ),
        tuple(sorted(world.flags.items())),
        (world.equipped.hand, world.equipped.body),
        copy.deepcopy(world.active_dialogue),
        tuple(
            (character_id, character.room_id)
            for character_id, character in sorted(world.characters.items())
        ),
    )


class ExamineWorldTests(unittest.TestCase):
    def test_item_monster_and_character_return_frozen_typed_outcomes(self) -> None:
        item_world = _world()
        item_before = _mutable_state(item_world)
        item = item_world.examine("微火提灯")
        self.assertIsInstance(item, ExamineItemOutcome)
        self.assertEqual(item.kind, "item")
        self.assertEqual(item.item_id, "item_spark_lantern")
        with self.assertRaises(FrozenInstanceError):
            item.item_name = "不能修改"  # type: ignore[misc]
        self.assertEqual(_mutable_state(item_world), item_before)

        character_world = _world()
        character_world.move("east")
        character_before = _mutable_state(character_world)
        character = character_world.examine("character_elder_chen")
        self.assertIsInstance(character, ExamineCharacterOutcome)
        self.assertEqual(character.kind, "character")
        self.assertEqual(character.character_name, "老陈")
        self.assertEqual(_mutable_state(character_world), character_before)

        monster_world = _world()
        monster_world.move("east")
        monster_world.move("east")
        monster_before = _mutable_state(monster_world)
        monster = monster_world.examine("灰壳兽")
        self.assertIsInstance(monster, ExamineMonsterOutcome)
        self.assertEqual(monster.kind, "monster")
        self.assertEqual((monster.hp, monster.max_hp), (8, 8))
        self.assertEqual(_mutable_state(monster_world), monster_before)

    def test_inventory_item_is_visible_after_pickup(self) -> None:
        world = _world()
        world.take("item_spark_lantern")
        before = _mutable_state(world)
        outcome = world.examine("item_spark_lantern", "item")
        self.assertIsInstance(outcome, ExamineItemOutcome)
        self.assertEqual(_mutable_state(world), before)

    def test_other_rooms_and_unobtained_rewards_are_hidden(self) -> None:
        world = _world()
        before = _mutable_state(world)
        for query in (
            "monster_ash_mite",
            "character_elder_chen",
            "item_chen_token",
            "item_ash_mite_gel",
        ):
            with self.subTest(query=query):
                with self.assertRaisesRegex(
                    WorldRuleError, f"^这里看不到 {query}。$"
                ):
                    world.examine(query)
        self.assertEqual(_mutable_state(world), before)

    def test_explicit_type_has_stable_missing_errors(self) -> None:
        world = _world()
        before = _mutable_state(world)
        cases = (
            ("item_chen_token", "item", "这里或背包中没有 item_chen_token。"),
            ("monster_ash_mite", "monster", "这里没有怪物 monster_ash_mite。"),
            ("character_elder_chen", "character", "这里没有角色 character_elder_chen。"),
        )
        for query, target_type, expected in cases:
            with self.subTest(target_type=target_type):
                with self.assertRaisesRegex(WorldRuleError, f"^{expected}$"):
                    world.examine(query, target_type)  # type: ignore[arg-type]
        self.assertEqual(_mutable_state(world), before)

    def test_cross_type_duplicate_name_requires_type_qualifier(self) -> None:
        world = _world()
        elder = world.characters["character_elder_chen"]
        world.characters[elder.id] = replace(
            elder,
            name="微火提灯",
            room_id=world.player.room_id,
        )
        before = _mutable_state(world)

        with self.assertRaisesRegex(WorldRuleError, f"^{AMBIGUOUS_ERROR}$"):
            world.examine("微火提灯")
        self.assertIsInstance(world.examine("微火提灯", "item"), ExamineItemOutcome)
        self.assertIsInstance(
            world.examine("微火提灯", "character"), ExamineCharacterOutcome
        )
        self.assertEqual(_mutable_state(world), before)

    def test_same_type_duplicate_name_requires_stable_id(self) -> None:
        world = _world()
        blade = world.items["item_crystal_blade"]
        world.items[blade.id] = replace(blade, name="微火提灯")
        before = _mutable_state(world)

        with self.assertRaisesRegex(
            WorldRuleError, "^物品名称不唯一，请使用稳定 ID。$"
        ):
            world.examine("微火提灯")
        self.assertIsInstance(
            world.examine("item_crystal_blade"), ExamineItemOutcome
        )
        self.assertEqual(_mutable_state(world), before)

    def test_cross_type_duplicate_id_requires_type_qualifier(self) -> None:
        """The invalid content shape is constructed only in runtime memory."""
        world = _world()
        elder = world.characters["character_elder_chen"]
        duplicate_id = "item_spark_lantern"
        world.characters[duplicate_id] = replace(
            elder,
            id=duplicate_id,
            name="同号旅人",
            room_id=world.player.room_id,
        )
        before = _mutable_state(world)

        with self.assertRaisesRegex(WorldRuleError, f"^{AMBIGUOUS_ERROR}$"):
            world.examine(duplicate_id)
        self.assertIsInstance(
            world.examine(duplicate_id, "item"), ExamineItemOutcome
        )
        self.assertIsInstance(
            world.examine(duplicate_id, "character"), ExamineCharacterOutcome
        )
        self.assertEqual(_mutable_state(world), before)

    def test_unique_exact_id_wins_over_a_name_match(self) -> None:
        world = _world()
        elder = world.characters["character_elder_chen"]
        world.characters[elder.id] = replace(
            elder,
            name="item_spark_lantern",
            room_id=world.player.room_id,
        )
        outcome = world.examine("item_spark_lantern")
        self.assertIsInstance(outcome, ExamineItemOutcome)

    def test_empty_query_and_invalid_type_are_read_only(self) -> None:
        world = _world()
        before = _mutable_state(world)
        with self.assertRaisesRegex(WorldRuleError, "^查看目标不能为空。$"):
            world.examine("  ")
        with self.assertRaisesRegex(
            WorldRuleError, "^查看目标类型无效：room。$"
        ):
            world.examine("微火提灯", "room")  # type: ignore[arg-type]
        self.assertEqual(_mutable_state(world), before)

    def test_success_and_failure_preserve_active_dialogue(self) -> None:
        world = _world()
        world.move("east")
        world.start_dialogue("character_elder_chen")
        before = _mutable_state(world)
        world.examine("老陈")
        with self.assertRaisesRegex(WorldRuleError, "^这里看不到 不存在。$"):
            world.examine("不存在")
        self.assertEqual(_mutable_state(world), before)


class ExamineCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.world = _world()
        self.commands = CommandProcessor(self.world)

    def test_empty_room_and_here_forms_reuse_look_exactly(self) -> None:
        look = self.commands.execute("look").text
        self.assertEqual(self.commands.execute("examine").text, look)
        self.assertEqual(self.commands.execute("examine room").text, look)
        self.assertEqual(self.commands.execute("examine HERE").text, look)

    def test_item_monster_and_character_rendering(self) -> None:
        item = self.commands.execute("examine item item_spark_lantern").text
        self.assertEqual(
            item,
            "微火提灯 [item_spark_lantern]\n"
            "一盏封着淡蓝火星的小灯，足以照亮近处的路。",
        )

        self.commands.execute("go east")
        character = self.commands.execute("examine 老陈").text
        self.assertIn("老陈 [character_elder_chen]", character)
        self.commands.execute("go east")
        monster = self.commands.execute("examine monster 灰壳兽").text
        self.assertIn("灰壳兽 [monster_ash_mite]", monster)
        self.assertIn("生命：8/8", monster)

    def test_inspect_output_remains_item_only_and_compatible(self) -> None:
        self.assertEqual(
            self.commands.execute("inspect item_spark_lantern").text,
            self.commands.execute("examine item item_spark_lantern").text,
        )
        self.commands.execute("go east")
        self.assertEqual(
            self.commands.execute("inspect character_elder_chen").text,
            "这里或背包中没有 character_elder_chen。",
        )

    def test_reserved_words_empty_queries_and_extra_arguments_have_exact_usage(self) -> None:
        cases = (
            ('examine ""', EXAMINE_USAGE),
            ("examine room extra", EXAMINE_USAGE),
            ("examine here extra", EXAMINE_USAGE),
            ("examine item", "用法：examine item <物品ID或名称>"),
            ('examine monster ""', "用法：examine monster <怪物ID或名称>"),
            ("examine character", "用法：examine character <角色ID或名称>"),
            ('inspect ""', "用法：inspect <物品ID或名称>"),
        )
        before = _mutable_state(self.world)
        for command, expected in cases:
            with self.subTest(command=command):
                self.assertEqual(self.commands.execute(command).text, expected)
        self.assertEqual(_mutable_state(self.world), before)

    def test_numeric_target_does_not_select_dialogue_option(self) -> None:
        self.commands.execute("go east")
        self.commands.execute("talk character_elder_chen")
        before = _mutable_state(self.world)

        self.assertEqual(
            self.commands.execute("examine 1").text,
            "这里看不到 1。",
        )
        self.assertEqual(
            self.commands.execute("examine item 1").text,
            "这里或背包中没有 1。",
        )
        self.assertEqual(_mutable_state(self.world), before)
        self.assertNotIn("未知指令", self.commands.execute("1").text)

    def test_examine_is_available_while_dead_and_preserves_state(self) -> None:
        self.world.player.hp = 0
        before = _mutable_state(self.world)
        self.assertIn(
            "微火提灯",
            self.commands.execute("examine item_spark_lantern").text,
        )
        self.assertIn("examine", self.commands.execute("help examine").text)
        self.assertIn("倒下了", self.commands.execute("attack 不存在").text)
        self.assertEqual(_mutable_state(self.world), before)

    def test_all_examine_and_help_failures_preserve_runtime_state(self) -> None:
        before = _mutable_state(self.world)
        commands = (
            "examine room extra",
            "examine item",
            "examine 不存在",
            "help one two",
            "help 不存在",
            "look extra",
            "inventory extra",
        )
        for command in commands:
            with self.subTest(command=command):
                self.commands.execute(command)
                self.assertEqual(_mutable_state(self.world), before)


class HelpRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.commands = CommandProcessor(_world())

    def test_help_command_has_stable_detailed_contract(self) -> None:
        self.assertEqual(
            self.commands.execute("help examine").text,
            "指令：examine\n"
            "语法：examine [room|here|<目标ID或名称>|item <物品ID或名称>|"
            "monster <怪物ID或名称>|character <角色ID或名称>]\n"
            "参数：无参数、room 或 here 查看当前房间；可用类型限定消除歧义。\n"
            "上下文限制：仅可见当前房间物品、背包物品、当前房间怪物和角色；"
            "只读且不结束对话。\n"
            "死亡限制：倒下时可用。",
        )

    def test_help_accepts_alias_and_numeric_selection(self) -> None:
        inventory = self.commands.execute("help i").text
        self.assertIn("指令：inventory", inventory)
        self.assertIn("别名：inv, i", inventory)
        selection = self.commands.execute("help 1").text
        self.assertIn("指令：<数字>", selection)
        self.assertIn("仅在活动对话中可用", selection)

    def test_help_argument_errors_are_exact_and_read_only(self) -> None:
        world = self.commands.world
        before = _mutable_state(world)
        self.assertEqual(
            self.commands.execute("help examine extra").text,
            "用法：help [command]",
        )
        self.assertEqual(
            self.commands.execute("help missing").text,
            "没有该指令的帮助：missing。使用 help 查看全部指令。",
        )
        self.assertEqual(_mutable_state(world), before)

    def test_route_help_and_death_metadata_are_bidirectionally_consistent(self) -> None:
        literal_specs = tuple(spec for spec in COMMAND_SPECS if spec.handler_name)
        expected_routes = {
            token.casefold(): spec
            for spec in literal_specs
            for token in (spec.name, *spec.aliases)
        }
        self.assertEqual(_COMMAND_BY_TOKEN, expected_routes)
        self.assertEqual(
            _DEAD_ALLOWED,
            frozenset(
                token
                for token, spec in expected_routes.items()
                if spec.allowed_when_dead
            ),
        )
        for spec in COMMAND_SPECS:
            with self.subTest(command=spec.name):
                if spec.handler_name is not None:
                    self.assertTrue(
                        callable(getattr(CommandProcessor, spec.handler_name, None))
                    )
                self.assertIn(spec.syntax, HELP_TEXT)
                detail_query = "1" if spec.name == "<数字>" else spec.name
                detail = self.commands.execute(f"help {detail_query}").text
                self.assertIn(f"语法：{spec.syntax}", detail)
                self.assertIn("参数：", detail)
                self.assertIn("上下文限制：", detail)
                self.assertIn("死亡限制：", detail)

    def test_save_format_and_content_versions_are_current(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        self.assertEqual(SAVE_FORMAT_VERSION, 7)
        self.assertEqual(pack.version, "0.9.0")


if __name__ == "__main__":
    unittest.main()
