"""Tests for content-defined exits that require a held item."""

from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from lore2mud.content.loader import ContentValidationError, load_content_pack
from lore2mud.content.models import ExitDefinition
from lore2mud.engine.commands import CommandProcessor
from lore2mud.engine.save import SAVE_FORMAT_VERSION, SaveLoadService, _serialize_world
from lore2mud.engine.world import World, WorldRuleError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = PROJECT_ROOT / "examples" / "original_demo"


def _demo_world() -> World:
    return World.from_content_pack(load_content_pack(DEMO_PATH), player_name="测试旅人")


def _grant_demo_token(world: World) -> None:
    world.move("east")
    world.start_dialogue("character_elder_chen")
    world.select_option(1)
    world.select_option(1)
    world.select_option(2)
    assert "item_chen_token" in [s.item_id for s in world.player.inventory.stacks]


def _runtime_snapshot(world: World) -> dict[str, object]:
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
        "inventory": [s.item_id for s in world.player.inventory.stacks],
        "equipped": (world.equipped.hand, world.equipped.body),
        "quests": copy.deepcopy(world.quest_states),
        "active_dialogue": copy.deepcopy(world.active_dialogue),
        "rooms": {
            room_id: ([s.item_id for s in room.item_stacks], list(room.monster_ids))
            for room_id, room in world.rooms.items()
        },
        "monsters": {monster_id: monster.hp for monster_id, monster in world.monsters.items()},
    }


class ExitContentLoadingTests(unittest.TestCase):
    """Both legacy and structured exits normalize to ExitDefinition."""

    def _mutate_rooms(self, mutate: object) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        pack_path = Path(temp_dir.name) / "pack"
        shutil.copytree(DEMO_PATH, pack_path)
        rooms_path = pack_path / "rooms.json"
        rooms = json.loads(rooms_path.read_text(encoding="utf-8"))
        mutate(rooms)
        rooms_path.write_text(
            json.dumps(rooms, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return pack_path

    def test_legacy_string_exit_is_normalized(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        exit_def = pack.rooms["room_ember_wharf"].exits["east"]
        self.assertEqual(exit_def, ExitDefinition("room_glassgrass_path"))

    def test_structured_exit_is_normalized(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        exit_def = pack.rooms["room_glassgrass_path"].exits["west"]
        self.assertEqual(
            exit_def,
            ExitDefinition("room_ember_wharf", "item_chen_token"),
        )

    def test_structured_exit_may_omit_required_item(self) -> None:
        def mutate(rooms: list[dict]) -> None:
            rooms[1]["exits"]["west"] = {
                "target_room_id": "room_ember_wharf"
            }

        pack = load_content_pack(self._mutate_rooms(mutate))
        self.assertEqual(
            pack.rooms["room_glassgrass_path"].exits["west"],
            ExitDefinition("room_ember_wharf", None),
        )

    def test_exit_object_unknown_field_is_rejected(self) -> None:
        def mutate(rooms: list[dict]) -> None:
            rooms[1]["exits"]["west"]["extra"] = True

        with self.assertRaises(ContentValidationError) as caught:
            load_content_pack(self._mutate_rooms(mutate))
        self.assertIn("未知字段", str(caught.exception))

    def test_exit_object_missing_target_is_rejected(self) -> None:
        def mutate(rooms: list[dict]) -> None:
            del rooms[1]["exits"]["west"]["target_room_id"]

        with self.assertRaises(ContentValidationError) as caught:
            load_content_pack(self._mutate_rooms(mutate))
        self.assertIn("target_room_id", str(caught.exception))

    def test_required_item_must_be_nonempty_stable_id(self) -> None:
        for bad_value in (None, "", 12, "Item Bad"):
            with self.subTest(bad_value=bad_value):
                def mutate(rooms: list[dict], value: object = bad_value) -> None:
                    rooms[1]["exits"]["west"]["required_item_id"] = value

                with self.assertRaises(ContentValidationError) as caught:
                    load_content_pack(self._mutate_rooms(mutate))
                self.assertIn("required_item_id", str(caught.exception))

    def test_exit_target_must_be_nonempty_stable_id(self) -> None:
        for bad_value in ("", "Room Bad"):
            with self.subTest(bad_value=bad_value):
                def mutate(rooms: list[dict], value: str = bad_value) -> None:
                    rooms[1]["exits"]["west"]["target_room_id"] = value

                with self.assertRaises(ContentValidationError) as caught:
                    load_content_pack(self._mutate_rooms(mutate))
                self.assertIn("target_room_id", str(caught.exception))

    def test_dangling_exit_target_and_required_item_are_rejected(self) -> None:
        def mutate(rooms: list[dict]) -> None:
            rooms[1]["exits"]["west"] = {
                "target_room_id": "room_missing",
                "required_item_id": "item_missing",
            }

        with self.assertRaises(ContentValidationError) as caught:
            load_content_pack(self._mutate_rooms(mutate))
        issues = str(caught.exception)
        self.assertIn("room_missing", issues)
        self.assertIn("item_missing", issues)

    def test_casefold_duplicate_direction_is_rejected(self) -> None:
        def mutate(rooms: list[dict]) -> None:
            rooms[1]["exits"]["WEST"] = "room_silent_observatory"

        with self.assertRaises(ContentValidationError) as caught:
            load_content_pack(self._mutate_rooms(mutate))
        self.assertIn("重复方向", str(caught.exception))

    def test_required_item_may_be_a_consumable_or_room_item(self) -> None:
        def mutate(rooms: list[dict]) -> None:
            rooms[1]["exits"]["west"]["required_item_id"] = "item_linglu_pill"

        pack = load_content_pack(self._mutate_rooms(mutate))
        self.assertEqual(
            pack.rooms["room_glassgrass_path"].exits["west"].required_item_id,
            "item_linglu_pill",
        )

    def test_exit_errors_are_aggregated(self) -> None:
        def mutate(rooms: list[dict]) -> None:
            rooms[1]["exits"]["west"] = {
                "target_room_id": "Room Bad",
                "required_item_id": None,
                "extra": "bad",
            }

        with self.assertRaises(ContentValidationError) as caught:
            load_content_pack(self._mutate_rooms(mutate))
        issues = str(caught.exception)
        self.assertIn("未知字段", issues)
        self.assertIn("稳定 ID", issues)
        self.assertIn("required_item_id", issues)


class LockedExitWorldTests(unittest.TestCase):
    def test_missing_item_rejects_without_changing_any_world_state(self) -> None:
        world = _demo_world()
        world.move("east")
        world.start_dialogue("character_elder_chen")
        snapshot = {
            "room": world.player.room_id,
            "player_stats": (
                world.player.hp,
                world.player.max_hp,
                world.player.attack,
                world.player.defense,
                world.player.level,
                world.player.experience,
            ),
            "inventory": [s.item_id for s in world.player.inventory.stacks],
            "equipped": (world.equipped.hand, world.equipped.body),
            "quests": copy.deepcopy(world.quest_states),
            "active_dialogue": copy.deepcopy(world.active_dialogue),
            "rooms": {
                room_id: ([s.item_id for s in room.item_stacks], list(room.monster_ids))
                for room_id, room in world.rooms.items()
            },
            "monsters": {monster_id: monster.hp for monster_id, monster in world.monsters.items()},
        }

        with self.assertRaises(WorldRuleError) as caught:
            world.move("west")

        self.assertIn("旧铜牌", str(caught.exception))
        self.assertIn("item_chen_token", str(caught.exception))
        self.assertEqual(world.player.room_id, snapshot["room"])
        self.assertEqual(
            (
                world.player.hp,
                world.player.max_hp,
                world.player.attack,
                world.player.defense,
                world.player.level,
                world.player.experience,
            ),
            snapshot["player_stats"],
        )
        self.assertEqual([s.item_id for s in world.player.inventory.stacks], snapshot["inventory"])
        self.assertEqual(
            (world.equipped.hand, world.equipped.body), snapshot["equipped"]
        )
        self.assertEqual(world.quest_states, snapshot["quests"])
        self.assertEqual(world.active_dialogue, snapshot["active_dialogue"])
        self.assertEqual(
            {
                room_id: ([s.item_id for s in room.item_stacks], list(room.monster_ids))
                for room_id, room in world.rooms.items()
            },
            snapshot["rooms"],
        )
        self.assertEqual(
            {monster_id: monster.hp for monster_id, monster in world.monsters.items()},
            snapshot["monsters"],
        )

    def test_holding_token_allows_exit_without_consuming_it(self) -> None:
        world = _demo_world()
        _grant_demo_token(world)

        room = world.move("west")

        self.assertEqual(room.id, "room_ember_wharf")
        self.assertIn("item_chen_token", [s.item_id for s in world.player.inventory.stacks])

    def test_ordinary_exit_remains_usable_without_token(self) -> None:
        world = _demo_world()
        world.move("east")
        room = world.move("east")
        self.assertEqual(room.id, "room_silent_observatory")


class LockedExitCommandAndSaveTests(unittest.TestCase):
    def _grant_token_via_commands(self, commands: CommandProcessor) -> None:
        commands.execute("go east")
        commands.execute("talk character_elder_chen")
        commands.execute("1")
        commands.execute("1")
        result = commands.execute("2")
        self.assertIn("旧铜牌", result.text)

    def test_cli_reports_missing_token_and_allows_token_holder(self) -> None:
        commands = CommandProcessor(_demo_world())
        commands.execute("go east")
        blocked = commands.execute("go west")
        self.assertIn("旧铜牌", blocked.text)
        self.assertIn("item_chen_token", blocked.text)

        commands = CommandProcessor(_demo_world())
        self._grant_token_via_commands(commands)
        moved = commands.execute("go west")
        self.assertIn("余烬渡台", moved.text)
        self.assertIn("item_chen_token", [s.item_id for s in commands.world.player.inventory.stacks])

    def test_look_keeps_ordinary_exits_bare(self) -> None:
        result = CommandProcessor(_demo_world()).execute("look")
        self.assertIn("出口：east", result.text)
        self.assertNotIn("需要：", result.text)

    def test_look_shows_missing_gate_item_without_changing_world_state(self) -> None:
        world = _demo_world()
        world.move("east")
        world.start_dialogue("character_elder_chen")
        commands = CommandProcessor(world)
        snapshot = _runtime_snapshot(world)

        result = commands.execute("look")

        self.assertIn("west", result.text)
        self.assertIn("旧铜牌", result.text)
        self.assertIn("item_chen_token", result.text)
        self.assertIn("未持有", result.text)
        self.assertEqual(_runtime_snapshot(world), snapshot)

    def test_look_shows_held_gate_item_after_real_dialogue_without_mutation(self) -> None:
        commands = CommandProcessor(_demo_world())
        self._grant_token_via_commands(commands)
        snapshot = _runtime_snapshot(commands.world)

        result = commands.execute("look")

        self.assertIn("west", result.text)
        self.assertIn("旧铜牌", result.text)
        self.assertIn("item_chen_token", result.text)
        self.assertIn("已持有", result.text)
        self.assertEqual(_runtime_snapshot(commands.world), snapshot)

    def test_save_v5_preserves_inventory_gate_without_serializing_exit_state(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        with tempfile.TemporaryDirectory() as temp_dir:
            service = SaveLoadService(pack, Path(temp_dir))

            without_token = _demo_world()
            without_token.move("east")
            service.save(without_token)
            serialized = json.loads(service.save_path.read_text(encoding="utf-8"))
            self.assertEqual(serialized["save_format_version"], SAVE_FORMAT_VERSION)
            self.assertTrue(all("exits" not in room for room in serialized["rooms"].values()))
            loaded_without = service.load()
            with self.assertRaises(WorldRuleError):
                loaded_without.move("west")

            with_token = _demo_world()
            _grant_demo_token(with_token)
            service.save(with_token)
            loaded_with = service.load()
            self.assertIn("item_chen_token", [s.item_id for s in loaded_with.player.inventory.stacks])
            looked = CommandProcessor(loaded_with).execute("look")
            self.assertIn("已持有", looked.text)
            self.assertEqual(loaded_with.move("west").id, "room_ember_wharf")

    def test_serialization_has_no_exit_state(self) -> None:
        data = _serialize_world(_demo_world())
        self.assertTrue(all("exits" not in room for room in data["rooms"].values()))


if __name__ == "__main__":
    unittest.main()
