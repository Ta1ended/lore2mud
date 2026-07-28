"""Tests for save/load service."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from lore2mud.content.loader import load_content_pack
from lore2mud.engine.commands import CommandProcessor
from lore2mud.engine.save import (
    SAVE_FORMAT_VERSION,
    SaveLoadError,
    SaveLoadService,
    _atomic_write,
    _serialize_world,
    _validate_and_build_world,
)
from lore2mud.engine.world import World

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = PROJECT_ROOT / "examples" / "original_demo"


class SaveRoundTripTests(unittest.TestCase):
    """Verify exact state preservation after save+load."""

    def setUp(self) -> None:
        self.pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(self.pack, player_name="测试旅人")
        self.tmpdir = tempfile.mkdtemp()
        self.service = SaveLoadService(self.pack, Path(self.tmpdir))

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_round_trip_fresh_world(self) -> None:
        """New world → save → load → identical state."""
        self.service.save(self.world)
        loaded = self.service.load()

        self.assertEqual(loaded.pack_id, self.world.pack_id)
        self.assertEqual(loaded.pack_version, self.world.pack_version)
        self.assertEqual(loaded.player.name, self.world.player.name)
        self.assertEqual(loaded.player.room_id, self.world.player.room_id)
        self.assertEqual(loaded.player.hp, self.world.player.hp)
        self.assertEqual(loaded.player.max_hp, self.world.player.max_hp)
        self.assertEqual(loaded.player.attack, self.world.player.attack)
        self.assertEqual(loaded.player.defense, self.world.player.defense)
        self.assertEqual(loaded.player.level, self.world.player.level)
        self.assertEqual(loaded.player.experience, self.world.player.experience)
        self.assertEqual(
            loaded.player.inventory.item_ids,
            self.world.player.inventory.item_ids,
        )

    def test_round_trip_after_actions(self) -> None:
        """Pick up item, take damage, then save+load."""
        self.world.take("item_spark_lantern")
        self.world.move("east")
        self.world.move("east")
        outcome = self.world.attack("monster_ash_mite")

        # Player took damage
        self.assertEqual(self.world.player.hp, 18)

        self.service.save(self.world)
        loaded = self.service.load()

        self.assertEqual(loaded.player.hp, 18)
        self.assertEqual(loaded.player.level, 1)
        self.assertEqual(loaded.player.inventory.item_ids, ["item_spark_lantern"])
        # Item removed from room
        self.assertNotIn(
            "item_spark_lantern",
            loaded.rooms["room_ember_wharf"].item_ids,
        )

    def test_round_trip_after_level_up(self) -> None:
        """Pick up item, go to observatory, defeat monster, level up, save+load."""
        self.world.take("item_spark_lantern")
        self.world.move("east")
        self.world.move("east")
        # First attack
        self.world.attack("monster_ash_mite")
        # Second attack defeats monster
        outcome = self.world.attack("monster_ash_mite")

        self.assertTrue(outcome.combat.monster_defeated)
        self.assertEqual(self.world.player.level, 2)
        self.assertEqual(self.world.player.experience, 17)
        # Level up restores HP to max
        self.assertEqual(self.world.player.hp, self.world.player.max_hp)
        # Monster removed from room
        self.assertNotIn(
            "monster_ash_mite",
            self.world.rooms["room_silent_observatory"].monster_ids,
        )

        self.service.save(self.world)
        loaded = self.service.load()

        self.assertEqual(loaded.player.level, 2)
        self.assertEqual(loaded.player.experience, 17)
        self.assertEqual(loaded.player.hp, loaded.player.max_hp)
        self.assertEqual(loaded.player.max_hp, self.world.player.max_hp)
        self.assertEqual(loaded.player.attack, self.world.player.attack)
        self.assertEqual(loaded.player.defense, self.world.player.defense)
        self.assertEqual(
            loaded.player.inventory.item_ids, ["item_spark_lantern"]
        )
        self.assertNotIn(
            "monster_ash_mite",
            loaded.rooms["room_silent_observatory"].monster_ids,
        )
        self.assertEqual(loaded.monsters["monster_ash_mite"].hp, 0)

    def test_load_creates_new_world_object(self) -> None:
        """Load returns a new World, not the same object."""
        self.service.save(self.world)
        loaded = self.service.load()
        self.assertIsNot(loaded, self.world)

    def test_round_trip_quest_completed(self) -> None:
        """Quest completed state survives save+load."""
        self.world.move("east")
        self.world.move("east")
        self.world.attack("monster_ash_mite")  # first hit
        self.world.attack("monster_ash_mite")  # defeats + quest completes

        self.assertIn("quest_clear_ash_mite", self.world.quest_states)
        self.assertTrue(
            self.world.quest_states["quest_clear_ash_mite"].completed
        )

        self.service.save(self.world)
        loaded = self.service.load()

        self.assertIn("quest_clear_ash_mite", loaded.quest_states)
        self.assertTrue(loaded.quest_states["quest_clear_ash_mite"].completed)


class SaveIncludesAllMutableStateTests(unittest.TestCase):
    """Verify the serialized data contains all required fields."""

    def setUp(self) -> None:
        self.pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(self.pack, player_name="测试旅人")

    def test_save_includes_all_player_fields(self) -> None:
        data = _serialize_world(self.world)
        player = data["player"]
        self.assertEqual(player["id"], "player_local")
        self.assertEqual(player["name"], "测试旅人")
        self.assertEqual(player["room_id"], "room_ember_wharf")
        self.assertEqual(player["max_hp"], 20)
        self.assertEqual(player["hp"], 20)
        self.assertEqual(player["attack"], 5)
        self.assertEqual(player["defense"], 1)
        self.assertEqual(player["level"], 1)
        self.assertEqual(player["experience"], 0)
        self.assertEqual(player["inventory_item_ids"], [])

    def test_save_includes_all_rooms(self) -> None:
        data = _serialize_world(self.world)
        room_ids = set(data["rooms"].keys())
        pack_room_ids = set(self.pack.rooms.keys())
        self.assertEqual(room_ids, pack_room_ids)

    def test_save_includes_all_monsters(self) -> None:
        data = _serialize_world(self.world)
        monster_ids = set(data["monsters"].keys())
        pack_monster_ids = set(self.pack.monsters.keys())
        self.assertEqual(monster_ids, pack_monster_ids)

    def test_save_includes_content_pack_identity(self) -> None:
        data = _serialize_world(self.world)
        self.assertEqual(data["content_pack"]["id"], "original_demo")
        self.assertEqual(data["content_pack"]["version"], "0.2.4")
        self.assertEqual(data["save_format_version"], SAVE_FORMAT_VERSION)

    def test_save_includes_equipped_field(self) -> None:
        data = _serialize_world(self.world)
        self.assertIn("equipped", data)
        self.assertIsInstance(data["equipped"], dict)
        self.assertIn("hand", data["equipped"])
        self.assertIsNone(data["equipped"]["hand"])


class SaveLoadServiceTests(unittest.TestCase):
    """Test SaveLoadService behavior."""

    def setUp(self) -> None:
        self.pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(self.pack)
        self.tmpdir = tempfile.mkdtemp()
        self.service = SaveLoadService(self.pack, Path(self.tmpdir))

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_save_creates_file(self) -> None:
        self.service.save(self.world)
        self.assertTrue(self.service.save_path.is_file())

    def test_save_dir_created_automatically(self) -> None:
        nested = Path(self.tmpdir) / "deep" / "nested"
        service = SaveLoadService(self.pack, nested)
        service.save(self.world)
        self.assertTrue(service.save_path.is_file())

    def test_load_nonexistent_raises(self) -> None:
        with self.assertRaises(SaveLoadError):
            self.service.load()

    def test_load_malformed_json_raises(self) -> None:
        self.service.save_path.write_text("not json {{{", encoding="utf-8")
        with self.assertRaises(SaveLoadError) as ctx:
            self.service.load()
        self.assertIn("JSON", str(ctx.exception))

    def test_load_non_dict_raises(self) -> None:
        self.service.save_path.write_text('"hello"', encoding="utf-8")
        with self.assertRaises(SaveLoadError):
            self.service.load()

    def test_load_preserves_current_world_on_failure(self) -> None:
        """Failed load must not change the caller's world."""
        original_room = self.world.player.room_id
        self.service.save_path.write_text("bad json", encoding="utf-8")
        with self.assertRaises(SaveLoadError):
            self.service.load()
        # Original world unchanged
        self.assertEqual(self.world.player.room_id, original_room)


class ValidationTests(unittest.TestCase):
    """Test strict validation of untrusted save data."""

    def setUp(self) -> None:
        self.pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(self.pack)
        self.tmpdir = tempfile.mkdtemp()
        self.service = SaveLoadService(self.pack, Path(self.tmpdir))
        self.valid_data = _serialize_world(self.world)

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _save_and_load(self, data: dict) -> World:
        """Write data and try to load it."""
        _atomic_write(self.service.save_path, data)
        return self.service.load()

    def test_save_format_version_mismatch_raises(self) -> None:
        self.valid_data["save_format_version"] = 99
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("格式版本", str(ctx.exception))

    def test_content_pack_id_mismatch_raises(self) -> None:
        self.valid_data["content_pack"]["id"] = "wrong_pack"
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("ID", str(ctx.exception))

    def test_content_pack_version_mismatch_raises(self) -> None:
        self.valid_data["content_pack"]["version"] = "9.9.9"
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("版本", str(ctx.exception))

    def test_top_level_unknown_field_raises(self) -> None:
        self.valid_data["unexpected"] = True
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("未知字段", str(ctx.exception))

    def test_content_pack_unknown_field_raises(self) -> None:
        self.valid_data["content_pack"]["unexpected"] = True
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("未知字段", str(ctx.exception))

    def test_player_unknown_field_raises(self) -> None:
        self.valid_data["player"]["unexpected"] = True
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("未知字段", str(ctx.exception))

    def test_missing_player_field_raises(self) -> None:
        del self.valid_data["player"]
        with self.assertRaises(SaveLoadError):
            self._save_and_load(self.valid_data)

    def test_invalid_player_id_raises(self) -> None:
        self.valid_data["player"]["id"] = "wrong_id"
        with self.assertRaises(SaveLoadError):
            self._save_and_load(self.valid_data)

    def test_missing_rooms_raises(self) -> None:
        del self.valid_data["rooms"]
        with self.assertRaises(SaveLoadError):
            self._save_and_load(self.valid_data)

    def test_missing_monsters_raises(self) -> None:
        del self.valid_data["monsters"]
        with self.assertRaises(SaveLoadError):
            self._save_and_load(self.valid_data)

    def test_extra_room_raises(self) -> None:
        self.valid_data["rooms"]["fake_room"] = {
            "item_ids": [],
            "monster_ids": [],
        }
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("多余", str(ctx.exception))

    def test_missing_room_raises(self) -> None:
        del self.valid_data["rooms"]["room_ember_wharf"]
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("缺少", str(ctx.exception))

    def test_extra_monster_raises(self) -> None:
        self.valid_data["monsters"]["fake_monster"] = {"hp": 10}
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("多余", str(ctx.exception))

    def test_missing_monster_raises(self) -> None:
        del self.valid_data["monsters"]["monster_ash_mite"]
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("缺少", str(ctx.exception))

    def test_room_unknown_field_raises(self) -> None:
        self.valid_data["rooms"]["room_ember_wharf"]["unexpected"] = True
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("未知字段", str(ctx.exception))

    def test_monster_unknown_field_raises(self) -> None:
        self.valid_data["monsters"]["monster_ash_mite"]["unexpected"] = True
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("未知字段", str(ctx.exception))

    def test_duplicate_item_in_rooms_raises(self) -> None:
        """Same item in two rooms must be rejected."""
        self.valid_data["rooms"]["room_ember_wharf"]["item_ids"] = [
            "item_spark_lantern"
        ]
        self.valid_data["rooms"]["room_glassgrass_path"]["item_ids"] = [
            "item_spark_lantern"
        ]
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("重复", str(ctx.exception))

    def test_duplicate_monster_in_rooms_raises(self) -> None:
        """Same monster in two rooms must be rejected."""
        self.valid_data["rooms"]["room_ember_wharf"]["monster_ids"] = [
            "monster_ash_mite"
        ]
        self.valid_data["rooms"]["room_glassgrass_path"]["monster_ids"] = [
            "monster_ash_mite"
        ]
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("重复", str(ctx.exception))

    def test_item_in_both_room_and_inventory_raises(self) -> None:
        self.valid_data["rooms"]["room_ember_wharf"]["item_ids"] = [
            "item_spark_lantern"
        ]
        self.valid_data["player"]["inventory_item_ids"] = ["item_spark_lantern"]
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("同时出现", str(ctx.exception))

    def test_inventory_over_capacity_raises(self) -> None:
        """Inventory exceeding pack capacity must be rejected."""
        # Pack has inventory_capacity=10
        fake_items = [f"fake_item_{i}" for i in range(11)]
        # Need to add these to pack items too
        self.valid_data["player"]["inventory_item_ids"] = fake_items
        with self.assertRaises(SaveLoadError):
            self._save_and_load(self.valid_data)

    def test_player_hp_exceeds_max_raises(self) -> None:
        self.valid_data["player"]["hp"] = 999
        self.valid_data["player"]["max_hp"] = 20
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("hp", str(ctx.exception))

    def test_player_hp_negative_raises(self) -> None:
        self.valid_data["player"]["hp"] = -1
        with self.assertRaises(SaveLoadError):
            self._save_and_load(self.valid_data)

    def test_player_level_zero_raises(self) -> None:
        self.valid_data["player"]["level"] = 0
        with self.assertRaises(SaveLoadError):
            self._save_and_load(self.valid_data)

    def test_player_experience_negative_raises(self) -> None:
        self.valid_data["player"]["experience"] = -1
        with self.assertRaises(SaveLoadError):
            self._save_and_load(self.valid_data)

    def test_bool_as_int_raises(self) -> None:
        """bool is not int."""
        self.valid_data["player"]["hp"] = True
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("整数", str(ctx.exception))

    def test_monster_hp_out_of_range_raises(self) -> None:
        self.valid_data["monsters"]["monster_ash_mite"]["hp"] = 999
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("hp", str(ctx.exception))

    def test_invalid_room_reference_in_player_raises(self) -> None:
        self.valid_data["player"]["room_id"] = "nonexistent_room"
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("不存在", str(ctx.exception))

    def test_invalid_item_reference_raises(self) -> None:
        self.valid_data["rooms"]["room_ember_wharf"]["item_ids"] = [
            "nonexistent_item"
        ]
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("不存在", str(ctx.exception))

    def test_invalid_monster_reference_raises(self) -> None:
        self.valid_data["rooms"]["room_ember_wharf"]["monster_ids"] = [
            "nonexistent_monster"
        ]
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("不存在", str(ctx.exception))

    def test_duplicate_inventory_item_raises(self) -> None:
        self.valid_data["player"]["inventory_item_ids"] = [
            "item_spark_lantern",
            "item_spark_lantern",
        ]
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("重复", str(ctx.exception))

    def test_missing_item_ids_in_room_raises(self) -> None:
        del self.valid_data["rooms"]["room_ember_wharf"]["item_ids"]
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("item_ids", str(ctx.exception))

    def test_missing_monster_ids_in_room_raises(self) -> None:
        del self.valid_data["rooms"]["room_ember_wharf"]["monster_ids"]
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("monster_ids", str(ctx.exception))

    def test_save_format_version_true_rejected(self) -> None:
        self.valid_data["save_format_version"] = True
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("格式版本", str(ctx.exception))

    def test_save_format_version_false_rejected(self) -> None:
        self.valid_data["save_format_version"] = False
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("格式版本", str(ctx.exception))

    def test_version_1_save_rejected(self) -> None:
        """Version 1 saves (no quest_states) must be cleanly rejected."""
        self.valid_data["save_format_version"] = 1
        del self.valid_data["quest_states"]
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("格式版本", str(ctx.exception))

    def test_version_2_save_rejected(self) -> None:
        """Version 2 saves (no equipped) must be cleanly rejected."""
        self.valid_data["save_format_version"] = 2
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("格式版本", str(ctx.exception))

    def test_missing_quest_states_raises(self) -> None:
        del self.valid_data["quest_states"]
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("quest_states", str(ctx.exception))

    def test_quest_states_not_dict_raises(self) -> None:
        self.valid_data["quest_states"] = "bad"
        with self.assertRaises(SaveLoadError):
            self._save_and_load(self.valid_data)

    def test_unknown_quest_id_raises(self) -> None:
        self.valid_data["quest_states"]["fake_quest"] = {"completed": False}
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("fake_quest", str(ctx.exception))

    def test_quest_state_not_dict_raises(self) -> None:
        self.valid_data["quest_states"]["quest_clear_ash_mite"] = "bad"
        with self.assertRaises(SaveLoadError):
            self._save_and_load(self.valid_data)

    def test_quest_completed_not_bool_raises(self) -> None:
        self.valid_data["quest_states"]["quest_clear_ash_mite"] = {"completed": 1}
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("布尔值", str(ctx.exception))

    def test_quest_unknown_field_raises(self) -> None:
        self.valid_data["quest_states"]["quest_clear_ash_mite"] = {
            "completed": False,
            "extra": True,
        }
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("未知字段", str(ctx.exception))

    def test_missing_equipped_raises(self) -> None:
        del self.valid_data["equipped"]
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("equipped", str(ctx.exception))

    def test_equipped_not_dict_raises(self) -> None:
        self.valid_data["equipped"] = "bad"
        with self.assertRaises(SaveLoadError):
            self._save_and_load(self.valid_data)

    def test_equipped_unknown_slot_raises(self) -> None:
        self.valid_data["equipped"]["head"] = "item_crystal_blade"
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("未知字段", str(ctx.exception))

    def test_equipped_hand_not_in_inventory_raises(self) -> None:
        self.valid_data["equipped"]["hand"] = "item_crystal_blade"
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("背包", str(ctx.exception))

    def test_equipped_hand_not_in_content_pack_raises(self) -> None:
        self.valid_data["equipped"]["hand"] = "nonexistent_item"
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("不存在", str(ctx.exception))

    def test_equipped_missing_hand_key_raises(self) -> None:
        """equipped dict without 'hand' key must be rejected."""
        self.valid_data["equipped"] = {}
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("hand", str(ctx.exception))

    def test_equipped_hand_type_error_raises(self) -> None:
        """equipped.hand must be string or null, not int."""
        self.valid_data["equipped"]["hand"] = 123
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("字符串", str(ctx.exception))

    def test_equipped_hand_normal_item_raises(self) -> None:
        """equipped.hand referencing a normal item (no slot) must be rejected."""
        self.valid_data["equipped"]["hand"] = "item_spark_lantern"
        self.valid_data["player"]["inventory_item_ids"] = ["item_spark_lantern"]
        # Remove from room to avoid dual-placement validation.
        self.valid_data["rooms"]["room_ember_wharf"]["item_ids"] = [
            i for i in self.valid_data["rooms"]["room_ember_wharf"]["item_ids"]
            if i != "item_spark_lantern"
        ]
        with self.assertRaises(SaveLoadError) as ctx:
            self._save_and_load(self.valid_data)
        self.assertIn("slot", str(ctx.exception))


class AtomicWriteTests(unittest.TestCase):
    """Test atomic write behavior."""

    def test_atomic_write_creates_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "test.json"
            _atomic_write(path, {"key": "value"})
            self.assertTrue(path.is_file())
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["key"], "value")

    def test_atomic_write_no_temp_leftover(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "test.json"
            _atomic_write(path, {"key": "value"})
            files = list(Path(td).iterdir())
            self.assertEqual(len(files), 1)  # Only the target file

    def test_atomic_write_failure_preserves_existing(self) -> None:
        """If write fails, existing file should be untouched."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "test.json"
            path.write_text('{"original": true}', encoding="utf-8")

            # Try to write something that will fail during json.dump
            class Unserializable:
                pass

            with self.assertRaises(TypeError):
                _atomic_write(path, {"data": Unserializable()})

            # Original file should be unchanged
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(data["original"])

    def test_atomic_write_failure_no_temp_leftover(self) -> None:
        """Failed write should not leave temp files."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "test.json"

            class Unserializable:
                pass

            with self.assertRaises(TypeError):
                _atomic_write(path, {"data": Unserializable()})

            files = list(Path(td).iterdir())
            self.assertEqual(len(files), 0)


class CommandIntegrationTests(unittest.TestCase):
    """Test save/load commands through CommandProcessor."""

    def setUp(self) -> None:
        self.pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(self.pack, player_name="测试旅人")
        self.tmpdir = tempfile.mkdtemp()
        self.service = SaveLoadService(self.pack, Path(self.tmpdir))
        self.commands = CommandProcessor(self.world, save_service=self.service)

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_save_command(self) -> None:
        result = self.commands.execute("save")
        self.assertIn("存档成功", result.text)
        self.assertTrue(self.service.save_path.is_file())

    def test_load_command_without_save_fails(self) -> None:
        result = self.commands.execute("load")
        self.assertIn("读档失败", result.text)
        self.assertIn("不存在", result.text)

    def test_save_then_load_restores_state(self) -> None:
        self.commands.execute("take item_spark_lantern")
        self.commands.execute("go east")
        self.commands.execute("go east")
        self.commands.execute("attack monster_ash_mite")

        self.commands.execute("save")

        # Create a fresh processor to simulate restart
        fresh_world = World.from_content_pack(self.pack, player_name="测试旅人")
        fresh_commands = CommandProcessor(fresh_world, save_service=self.service)

        result = fresh_commands.execute("load")
        self.assertIn("读档成功", result.text)

        # Verify state restored
        self.assertEqual(fresh_commands.world.player.hp, 18)
        self.assertIn(
            "item_spark_lantern",
            fresh_commands.world.player.inventory.item_ids,
        )

    def test_save_load_full_level_up_scenario(self) -> None:
        """Pick up item, go to observatory, defeat monster, level up, save, load."""
        self.commands.execute("take item_spark_lantern")
        self.commands.execute("go east")
        self.commands.execute("go east")
        self.commands.execute("attack monster_ash_mite")
        self.commands.execute("attack monster_ash_mite")

        # Verify pre-save state
        self.assertEqual(self.world.player.level, 2)
        self.assertEqual(self.world.player.experience, 17)
        self.assertEqual(self.world.player.hp, self.world.player.max_hp)
        self.assertNotIn(
            "monster_ash_mite",
            self.world.rooms["room_silent_observatory"].monster_ids,
        )

        self.commands.execute("save")

        # Simulate restart
        fresh_world = World.from_content_pack(self.pack, player_name="测试旅人")
        fresh_commands = CommandProcessor(fresh_world, save_service=self.service)
        result = fresh_commands.execute("load")
        self.assertIn("读档成功", result.text)

        w = fresh_commands.world
        self.assertEqual(w.player.level, 2)
        self.assertEqual(w.player.experience, 17)
        self.assertEqual(w.player.hp, w.player.max_hp)
        self.assertEqual(w.player.max_hp, self.world.player.max_hp)
        self.assertEqual(w.player.attack, self.world.player.attack)
        self.assertEqual(w.player.defense, self.world.player.defense)
        self.assertEqual(w.player.inventory.item_ids, ["item_spark_lantern"])
        self.assertNotIn("item_spark_lantern", w.rooms["room_ember_wharf"].item_ids)
        self.assertNotIn(
            "monster_ash_mite", w.rooms["room_silent_observatory"].monster_ids
        )
        self.assertEqual(w.monsters["monster_ash_mite"].hp, 0)

    def test_load_failure_preserves_command_processor_world(self) -> None:
        """Failed load must not change CommandProcessor.world."""
        self.service.save_path.write_text("bad json", encoding="utf-8")
        original_room = self.world.player.room_id
        original_hp = self.world.player.hp

        result = self.commands.execute("load")
        self.assertIn("读档失败", result.text)

        # World unchanged
        self.assertIs(self.commands.world, self.world)
        self.assertEqual(self.commands.world.player.room_id, original_room)
        self.assertEqual(self.commands.world.player.hp, original_hp)

    def test_unknown_save_field_preserves_command_processor_world(self) -> None:
        """A structurally invalid save must not replace the active World."""
        invalid_data = _serialize_world(self.world)
        invalid_data["unexpected"] = True
        _atomic_write(self.service.save_path, invalid_data)

        result = self.commands.execute("load")

        self.assertIn("读档失败", result.text)
        self.assertIs(self.commands.world, self.world)

    def test_help_includes_save_load(self) -> None:
        result = self.commands.execute("help")
        self.assertIn("save", result.text)
        self.assertIn("load", result.text)

    def test_no_save_service_returns_error(self) -> None:
        commands = CommandProcessor(self.world, save_service=None)
        result = commands.execute("save")
        self.assertIn("不可用", result.text)
        result = commands.execute("load")
        self.assertIn("不可用", result.text)


if __name__ == "__main__":
    unittest.main()
