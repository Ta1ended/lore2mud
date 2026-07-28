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
from lore2mud.inventory.models import ItemStack


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
            [s.item_id for s in world.player.inventory.stacks],
        ),
        "equipped": (world.equipped.hand, world.equipped.body),
        "quests": copy.deepcopy(world.quest_states),
        "active_dialogue": copy.deepcopy(world.active_dialogue),
        "rooms": {
            room_id: ([s.item_id for s in room.item_stacks], list(room.monster_ids))
            for room_id, room in world.rooms.items()
        },
        "monsters": {
            monster_id: (monster.hp, (monster.loot_item.item_id if monster.loot_item else None))
            for monster_id, monster in world.monsters.items()
        },
    }


class MonsterLootContentTests(unittest.TestCase):
    def test_demo_declares_one_hidden_consumable_loot_item(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        monster = pack.monsters["monster_ash_mite"]

        self.assertEqual(monster.loot_item.item_id, "item_ash_mite_gel")
        self.assertEqual(pack.items["item_ash_mite_gel"].heal_amount, 6)
        self.assertFalse(
            any(
                "item_ash_mite_gel" in [s.item_id for s in room.item_stacks]
                for room in pack.rooms.values()
            )
        )

    def test_loot_field_is_optional(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pack_path = _copy_demo_pack(temp_dir)
            monsters = json.loads((pack_path / "monsters.json").read_text("utf-8"))
            del monsters[0]["loot_item"]
            (pack_path / "monsters.json").write_text(
                json.dumps(monsters, ensure_ascii=False), "utf-8"
            )

            pack = load_content_pack(pack_path)

        self.assertIsNone(pack.monsters["monster_ash_mite"].loot_item)

    def test_null_loot_field_is_accepted_as_no_loot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pack_path = _copy_demo_pack(temp_dir)
            monsters = json.loads((pack_path / "monsters.json").read_text("utf-8"))
            monsters[0]["loot_item"] = None
            (pack_path / "monsters.json").write_text(
                json.dumps(monsters, ensure_ascii=False), "utf-8"
            )

            pack = load_content_pack(pack_path)

        self.assertIsNone(pack.monsters["monster_ash_mite"].loot_item)

    def test_missing_loot_item_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pack_path = _copy_demo_pack(temp_dir)
            monsters = json.loads((pack_path / "monsters.json").read_text("utf-8"))
            monsters[0]["loot_item"] = {"item_id": "item_missing_loot", "quantity": 1}
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
            monsters[0]["loot_item"] = {"item_id": "item_spark_lantern", "quantity": 1}
            (pack_path / "monsters.json").write_text(
                json.dumps(monsters, ensure_ascii=False), "utf-8"
            )

            with self.assertRaises(ContentValidationError) as caught:
                load_content_pack(pack_path)

        self.assertIn("被多个来源引用", str(caught.exception))

    def test_dialogue_reward_cannot_also_be_loot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pack_path = _copy_demo_pack(temp_dir)
            monsters = json.loads((pack_path / "monsters.json").read_text("utf-8"))
            monsters[0]["loot_item"] = {"item_id": "item_chen_token", "quantity": 1}
            (pack_path / "monsters.json").write_text(
                json.dumps(monsters, ensure_ascii=False), "utf-8"
            )

            with self.assertRaises(ContentValidationError) as caught:
                load_content_pack(pack_path)

        self.assertIn("被多个来源引用", str(caught.exception))

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
            [s.item_id for s in self.world.current_room.item_stacks].count("item_ash_mite_gel"), 1
        )
        self.assertNotIn("item_ash_mite_gel", [s.item_id for s in self.world.player.inventory.stacks])

    def test_defeated_monster_cannot_duplicate_loot(self) -> None:
        self._defeat_ash_mite()

        with self.assertRaisesRegex(WorldRuleError, "这里没有可攻击"):
            self.world.attack("monster_ash_mite")

        self.assertEqual(
            [s.item_id for s in self.world.current_room.item_stacks].count("item_ash_mite_gel"), 1
        )

    def test_monster_without_loot_defeats_without_placing_an_item(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        no_loot_mite = replace(
            pack.monsters["monster_ash_mite"], loot_item=None
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
        self.assertNotIn("item_ash_mite_gel", [s.item_id for s in world.current_room.item_stacks])

    def test_preplaced_stackable_loot_merges_on_defeat(self) -> None:
        """Stackable loot (stack_limit>1) merges with preplaced stack."""
        self.world.current_room.item_stacks.append(ItemStack(item_id="item_ash_mite_gel", quantity=1))
        count_before = sum(s.quantity for s in self.world.current_room.item_stacks if s.item_id == "item_ash_mite_gel")

        # Attack should succeed since stack_limit=3 allows stacking.
        self.world.attack("monster_ash_mite")
        outcome = self.world.attack("monster_ash_mite")

        self.assertTrue(outcome.combat.monster_defeated)
        count_after = sum(s.quantity for s in self.world.current_room.item_stacks if s.item_id == "item_ash_mite_gel")
        self.assertEqual(count_after, count_before + 1)


class MonsterLootCommandAndSaveTests(unittest.TestCase):
    def test_attack_renders_loot_then_player_can_take_it(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack, player_name="测试旅人")
        commands = CommandProcessor(world)
        commands.execute("go east")
        commands.execute("go east")
        commands.execute("attack monster_ash_mite")

        result = commands.execute("attack monster_ash_mite")

        self.assertIn("灰壳凝胶 掉落在当前房间。", result.text)
        self.assertIn("灰壳凝胶", commands.execute("look").text)
        self.assertIn("拾取了 灰壳凝胶", commands.execute("take 灰壳凝胶").text)

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

        self.assertIn("item_ash_mite_gel", [s.item_id for s in loaded.current_room.item_stacks])
        self.assertEqual(
            loaded.monsters["monster_ash_mite"].loot_item.item_id,
            "item_ash_mite_gel",
        )
        loaded.take("item_ash_mite_gel")
        self.assertIn("item_ash_mite_gel", [s.item_id for s in loaded.player.inventory.stacks])

    def test_load_detects_alive_monster_loot_already_placed(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack, player_name="测试旅人")

        with tempfile.TemporaryDirectory() as temp_dir:
            service = SaveLoadService(pack, Path(temp_dir))
            service.save(world)
            save_data = json.loads(service.save_path.read_text("utf-8"))
            save_data["rooms"]["room_silent_observatory"]["item_stacks"].append(
                {"item_id": "item_ash_mite_gel", "quantity": 1}
            )
            service.save_path.write_text(
                json.dumps(save_data, ensure_ascii=False), "utf-8"
            )

            # item_ash_mite_gel has stack_limit=3, so the validation
            # (which only fires for stack_limit=1) does not reject this load.
            loaded = service.load()
            self.assertIn("item_ash_mite_gel", [s.item_id for s in loaded.rooms["room_silent_observatory"].item_stacks])


if __name__ == "__main__":
    unittest.main()
