"""Tests for deterministic single-item monster loot."""

from __future__ import annotations

import copy
from dataclasses import replace
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from lore2mud.content.loader import ContentValidationError, load_content_pack
from lore2mud.engine.commands import CommandProcessor
from lore2mud.engine.save import SaveLoadError, SaveLoadService
from lore2mud.engine.world import LootOutcome, World, WorldRuleError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = PROJECT_ROOT / "examples" / "original_demo"


def _copy_demo_pack(temp_dir: str) -> Path:
    pack_path = Path(temp_dir) / "pack"
    shutil.copytree(DEMO_PATH, pack_path)
    return pack_path


def _runtime_snapshot(world: World) -> dict[str, object]:
    """Capture mutable state for failed-attack invariance checks."""
    return {
        "room": world.player.room_id,
        "player": (
            world.player.hp,
            world.player.level,
            world.player.experience,
            list(world.player.inventory.item_ids),
        ),
        "equipped": (world.equipped.hand, world.equipped.body),
        "quests": copy.deepcopy(world.quest_states),
        "active_dialogue": copy.deepcopy(world.active_dialogue),
        "rooms": {
            room_id: (list(room.item_ids), list(room.monster_ids))
            for room_id, room in world.rooms.items()
        },
        "monsters": {
            monster_id: (monster.hp, monster.loot_item_id)
            for monster_id, monster in world.monsters.items()
        },
    }


class MonsterLootContentTests(unittest.TestCase):
    def test_demo_declares_one_hidden_consumable_loot_item(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        monster = pack.monsters["monster_ash_mite"]

        self.assertEqual(monster.loot_item_id, "item_ash_mite_gel")
        self.assertEqual(pack.items["item_ash_mite_gel"].heal_amount, 6)
        self.assertFalse(
            any(
                "item_ash_mite_gel" in room.item_ids
                for room in pack.rooms.values()
            )
        )

    def test_loot_field_is_optional(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pack_path = _copy_demo_pack(temp_dir)
            monsters = json.loads((pack_path / "monsters.json").read_text("utf-8"))
            del monsters[0]["loot_item_id"]
            (pack_path / "monsters.json").write_text(
                json.dumps(monsters, ensure_ascii=False), "utf-8"
            )

            pack = load_content_pack(pack_path)

        self.assertIsNone(pack.monsters["monster_ash_mite"].loot_item_id)

    def test_null_loot_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pack_path = _copy_demo_pack(temp_dir)
            monsters = json.loads((pack_path / "monsters.json").read_text("utf-8"))
            monsters[0]["loot_item_id"] = None
            (pack_path / "monsters.json").write_text(
                json.dumps(monsters, ensure_ascii=False), "utf-8"
            )

            with self.assertRaises(ContentValidationError) as caught:
                load_content_pack(pack_path)

        self.assertIn("loot_item_id", str(caught.exception))

    def test_missing_loot_item_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pack_path = _copy_demo_pack(temp_dir)
            monsters = json.loads((pack_path / "monsters.json").read_text("utf-8"))
            monsters[0]["loot_item_id"] = "item_missing_loot"
            (pack_path / "monsters.json").write_text(
                json.dumps(monsters, ensure_ascii=False), "utf-8"
            )

            with self.assertRaises(ContentValidationError) as caught:
                load_content_pack(pack_path)

        self.assertIn("item_missing_loot", str(caught.exception))

    def test_room_placed_loot_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pack_path = _copy_demo_pack(temp_dir)
            monsters = json.loads((pack_path / "monsters.json").read_text("utf-8"))
            monsters[0]["loot_item_id"] = "item_spark_lantern"
            (pack_path / "monsters.json").write_text(
                json.dumps(monsters, ensure_ascii=False), "utf-8"
            )

            with self.assertRaises(ContentValidationError) as caught:
                load_content_pack(pack_path)

        self.assertIn("已放置在房间", str(caught.exception))

    def test_dialogue_reward_cannot_also_be_loot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pack_path = _copy_demo_pack(temp_dir)
            monsters = json.loads((pack_path / "monsters.json").read_text("utf-8"))
            monsters[0]["loot_item_id"] = "item_chen_token"
            (pack_path / "monsters.json").write_text(
                json.dumps(monsters, ensure_ascii=False), "utf-8"
            )

            with self.assertRaises(ContentValidationError) as caught:
                load_content_pack(pack_path)

        self.assertIn("同时作为怪物战利品和对话奖励", str(caught.exception))

    def test_multiple_monsters_cannot_share_loot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pack_path = _copy_demo_pack(temp_dir)
            monsters = json.loads((pack_path / "monsters.json").read_text("utf-8"))
            copied = dict(monsters[0])
            copied["id"] = "monster_ash_mite_copy"
            copied["name"] = "灰壳兽复制体"
            monsters.append(copied)
            (pack_path / "monsters.json").write_text(
                json.dumps(monsters, ensure_ascii=False), "utf-8"
            )
            rooms = json.loads((pack_path / "rooms.json").read_text("utf-8"))
            observatory = next(
                room for room in rooms
                if room["id"] == "room_silent_observatory"
            )
            observatory["monster_ids"].append("monster_ash_mite_copy")
            (pack_path / "rooms.json").write_text(
                json.dumps(rooms, ensure_ascii=False), "utf-8"
            )

            with self.assertRaises(ContentValidationError) as caught:
                load_content_pack(pack_path)

        self.assertIn("多个怪物作为战利品", str(caught.exception))

    def test_schema_documents_optional_loot_item_id(self) -> None:
        schema = json.loads(
            (PROJECT_ROOT / "schemas" / "monster.schema.json").read_text("utf-8")
        )

        self.assertNotIn("loot_item_id", schema["required"])
        self.assertEqual(
            schema["properties"]["loot_item_id"]["$ref"],
            "common.schema.json#/$defs/stable_id",
        )


class MonsterLootWorldTests(unittest.TestCase):
    def setUp(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(pack, player_name="测试旅人")
        self.world.move("east")
        self.world.move("east")

    def _defeat_ash_mite(self):
        first = self.world.attack("monster_ash_mite")
        second = self.world.attack("monster_ash_mite")
        return first, second

    def test_first_defeat_places_typed_loot_once(self) -> None:
        first, second = self._defeat_ash_mite()

        self.assertFalse(first.combat.monster_defeated)
        self.assertIsNone(first.loot_item)
        self.assertTrue(second.combat.monster_defeated)
        self.assertIsInstance(second.loot_item, LootOutcome)
        self.assertEqual(second.loot_item.item_id, "item_ash_mite_gel")
        self.assertEqual(second.loot_item.item_name, "灰壳凝胶")
        self.assertEqual(
            self.world.current_room.item_ids.count("item_ash_mite_gel"), 1
        )
        self.assertNotIn("item_ash_mite_gel", self.world.player.inventory.item_ids)

    def test_defeated_monster_cannot_duplicate_loot(self) -> None:
        self._defeat_ash_mite()

        with self.assertRaisesRegex(WorldRuleError, "这里没有可攻击"):
            self.world.attack("monster_ash_mite")

        self.assertEqual(
            self.world.current_room.item_ids.count("item_ash_mite_gel"), 1
        )

    def test_monster_without_loot_defeats_without_placing_an_item(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        no_loot_mite = replace(
            pack.monsters["monster_ash_mite"], loot_item_id=None
        )
        no_loot_pack = replace(
            pack,
            monsters={"monster_ash_mite": no_loot_mite},
        )
        world = World.from_content_pack(no_loot_pack)
        world.move("east")
        world.move("east")

        world.attack("monster_ash_mite")
        outcome = world.attack("monster_ash_mite")

        self.assertTrue(outcome.combat.monster_defeated)
        self.assertIsNone(outcome.loot_item)
        self.assertNotIn("item_ash_mite_gel", world.current_room.item_ids)

    def test_preplaced_loot_rejects_before_combat_without_mutation(self) -> None:
        self.world.current_room.item_ids.append("item_ash_mite_gel")
        before = _runtime_snapshot(self.world)

        with self.assertRaisesRegex(WorldRuleError, "战利品已在世界中"):
            self.world.attack("monster_ash_mite")

        self.assertEqual(_runtime_snapshot(self.world), before)


class MonsterLootCommandAndSaveTests(unittest.TestCase):
    def test_attack_renders_loot_then_player_can_take_it(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack, player_name="测试旅人")
        commands = CommandProcessor(world)
        commands.execute("go east")
        commands.execute("go east")
        commands.execute("attack monster_ash_mite")

        result = commands.execute("attack monster_ash_mite")

        self.assertIn("灰壳凝胶 (item_ash_mite_gel) 掉落在当前房间。", result.text)
        self.assertIn("item_ash_mite_gel", commands.execute("look").text)
        self.assertIn("拾取了 灰壳凝胶", commands.execute("take item_ash_mite_gel").text)

    def test_uncollected_loot_survives_save_load(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack, player_name="测试旅人")
        world.move("east")
        world.move("east")
        world.attack("monster_ash_mite")
        world.attack("monster_ash_mite")

        with tempfile.TemporaryDirectory() as temp_dir:
            service = SaveLoadService(pack, Path(temp_dir))
            service.save(world)
            loaded = service.load()

        self.assertIn("item_ash_mite_gel", loaded.current_room.item_ids)
        self.assertEqual(
            loaded.monsters["monster_ash_mite"].loot_item_id,
            "item_ash_mite_gel",
        )
        loaded.take("item_ash_mite_gel")
        self.assertIn("item_ash_mite_gel", loaded.player.inventory.item_ids)

    def test_load_rejects_alive_monster_with_already_placed_loot(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack, player_name="测试旅人")

        with tempfile.TemporaryDirectory() as temp_dir:
            service = SaveLoadService(pack, Path(temp_dir))
            service.save(world)
            save_data = json.loads(service.save_path.read_text("utf-8"))
            save_data["rooms"]["room_silent_observatory"]["item_ids"].append(
                "item_ash_mite_gel"
            )
            service.save_path.write_text(
                json.dumps(save_data, ensure_ascii=False), "utf-8"
            )

            with self.assertRaises(SaveLoadError) as caught:
                service.load()

        self.assertIn("存活怪物", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
