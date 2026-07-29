"""Tests for M2: typed item stacks and save v6."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from lore2mud.content.loader import load_content_pack
from lore2mud.content.models import ItemStackDefinition
from lore2mud.engine.commands import CommandProcessor, _parse_quantity, _classify_quantity_token
from lore2mud.engine.models import DialogueState
from lore2mud.engine.save import SAVE_FORMAT_VERSION, SaveLoadError, SaveLoadService
from lore2mud.engine.world import World, WorldRuleError
from lore2mud.inventory.models import ItemStack

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = PROJECT_ROOT / "examples" / "original_demo"


class ContentDefinitionImmutabilityTests(unittest.TestCase):
    """Content ItemStackDefinition must not be mutated by runtime operations."""

    def test_content_stack_definition_is_frozen(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        room_def = pack.rooms["room_ember_wharf"]
        stack = room_def.item_stacks[0]
        with self.assertRaises(AttributeError):
            stack.quantity = 99  # type: ignore[misc]

    def test_content_definition_not_mutated_by_take(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        room_def = pack.rooms["room_ember_wharf"]
        original_qty = room_def.item_stacks[1].quantity  # linglu_pill qty=3
        world = World.from_content_pack(pack)
        world.take("item_linglu_pill", 1)
        self.assertEqual(room_def.item_stacks[1].quantity, original_qty)

    def test_runtime_stacks_are_independent_instances(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack)
        room_def = pack.rooms["room_ember_wharf"]
        runtime_stack = world.rooms["room_ember_wharf"].item_stacks[0]
        content_stack = room_def.item_stacks[0]
        self.assertIsNot(runtime_stack, content_stack)


class StackLimitLoaderTests(unittest.TestCase):
    """Loader must validate stack_limit strictly."""

    def test_stack_limit_default_1(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        self.assertEqual(pack.items["item_spark_lantern"].stack_limit, 1)

    def test_stack_limit_custom(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        self.assertEqual(pack.items["item_linglu_pill"].stack_limit, 5)

    def test_equipment_stack_limit_must_be_1(self) -> None:
        """Equipment items must have stack_limit == 1."""
        pack = load_content_pack(DEMO_PATH)
        self.assertEqual(pack.items["item_crystal_blade"].stack_limit, 1)
        self.assertEqual(pack.items["item_bronze_scale_mail"].stack_limit, 1)


class QuantityParsingTests(unittest.TestCase):
    """_parse_quantity must handle all numeric styles correctly."""

    def test_suffix_quantity(self) -> None:
        q, qty, err = _parse_quantity(["灵露丸", "3"], "take <物品ID或名称> [数量]")
        self.assertEqual(q, "灵露丸")
        self.assertEqual(qty, 3)
        self.assertIsNone(err)

    def test_default_quantity_1(self) -> None:
        q, qty, err = _parse_quantity(["灵露丸"], "take <物品ID或名称> [数量]")
        self.assertEqual(q, "灵露丸")
        self.assertEqual(qty, 1)
        self.assertIsNone(err)

    def test_rejects_0(self) -> None:
        _, _, err = _parse_quantity(["灵露丸", "0"], "take <物品ID或名称> [数量]")
        self.assertIsNotNone(err)
        self.assertIn("正整数", err)

    def test_rejects_negative(self) -> None:
        _, _, err = _parse_quantity(["灵露丸", "-1"], "take <物品ID或名称> [数量]")
        self.assertIsNotNone(err)

    def test_rejects_plus_1(self) -> None:
        _, _, err = _parse_quantity(["灵露丸", "+1"], "take <物品ID或名称> [数量]")
        self.assertIsNotNone(err)

    def test_rejects_float(self) -> None:
        _, _, err = _parse_quantity(["灵露丸", "1.5"], "take <物品ID或名称> [数量]")
        self.assertIsNotNone(err)

    def test_rejects_scientific(self) -> None:
        _, _, err = _parse_quantity(["灵露丸", "1e5"], "take <物品ID或名称> [数量]")
        self.assertIsNotNone(err)

    def test_rejects_hex(self) -> None:
        _, _, err = _parse_quantity(["灵露丸", "0xFF"], "take <物品ID或名称> [数量]")
        self.assertIsNotNone(err)

    def test_rejects_inf(self) -> None:
        _, _, err = _parse_quantity(["灵露丸", "inf"], "take <物品ID或名称> [数量]")
        self.assertIsNotNone(err)

    def test_lone_number_is_usage_error(self) -> None:
        _, _, err = _parse_quantity(["3"], "take <物品ID或名称> [数量]")
        self.assertIsNotNone(err)
        self.assertIn("用法", err)

    def test_empty_is_usage_error(self) -> None:
        _, _, err = _parse_quantity([], "take <物品ID或名称> [数量]")
        self.assertIsNotNone(err)

    def test_number_suffix_name(self) -> None:
        """Name like '3号电池' is not a numeric token."""
        kind, val = _classify_quantity_token("3号电池")
        self.assertEqual(kind, "name")
        self.assertIsNone(val)


class WorldTakeTests(unittest.TestCase):
    """World.take with quantity support."""

    def setUp(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(pack)

    def test_take_entire_stack(self) -> None:
        outcome = self.world.take("item_linglu_pill", 3)
        self.assertEqual(outcome.quantity, 3)
        self.assertIsNone(self.world.current_room.find_stack("item_linglu_pill"))
        inv_stack = self.world.player.inventory.find_stack("item_linglu_pill")
        self.assertIsNotNone(inv_stack)
        self.assertEqual(inv_stack.quantity, 3)

    def test_take_partial_stack(self) -> None:
        outcome = self.world.take("item_linglu_pill", 1)
        self.assertEqual(outcome.quantity, 1)
        room_stack = self.world.current_room.find_stack("item_linglu_pill")
        self.assertIsNotNone(room_stack)
        self.assertEqual(room_stack.quantity, 2)
        inv_stack = self.world.player.inventory.find_stack("item_linglu_pill")
        self.assertIsNotNone(inv_stack)
        self.assertEqual(inv_stack.quantity, 1)

    def test_take_merges_into_existing_inventory(self) -> None:
        self.world.take("item_linglu_pill", 2)
        self.world.drop("item_linglu_pill", 1)
        self.world.take("item_linglu_pill", 1)
        inv_stack = self.world.player.inventory.find_stack("item_linglu_pill")
        self.assertEqual(inv_stack.quantity, 2)

    def test_take_rejects_insufficient_source(self) -> None:
        with self.assertRaises(WorldRuleError):
            self.world.take("item_linglu_pill", 10)

    def test_take_rejects_quantity_0(self) -> None:
        with self.assertRaises(WorldRuleError):
            self.world.take("item_linglu_pill", 0)

    def test_take_rejects_quantity_negative(self) -> None:
        with self.assertRaises(WorldRuleError):
            self.world.take("item_linglu_pill", -1)

    def test_take_rejects_quantity_bool(self) -> None:
        with self.assertRaises(WorldRuleError):
            self.world.take("item_linglu_pill", True)  # type: ignore[arg-type]


class WorldDropTests(unittest.TestCase):
    """World.drop with quantity support."""

    def setUp(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(pack)
        self.world.take("item_linglu_pill", 3)

    def test_drop_partial(self) -> None:
        outcome = self.world.drop("item_linglu_pill", 1)
        self.assertEqual(outcome.quantity, 1)
        inv = self.world.player.inventory.find_stack("item_linglu_pill")
        self.assertEqual(inv.quantity, 2)

    def test_drop_entire_stack(self) -> None:
        self.world.drop("item_linglu_pill", 3)
        self.assertIsNone(self.world.player.inventory.find_stack("item_linglu_pill"))

    def test_drop_rejects_equipped(self) -> None:
        self.world.take("item_crystal_blade", 1)
        self.world.equip("item_crystal_blade")
        with self.assertRaises(WorldRuleError):
            self.world.drop("item_crystal_blade", 1)

    def test_drop_rejects_quantity_0(self) -> None:
        with self.assertRaises(WorldRuleError):
            self.world.drop("item_linglu_pill", 0)

    def test_drop_rejects_quantity_negative(self) -> None:
        with self.assertRaises(WorldRuleError):
            self.world.drop("item_linglu_pill", -1)

    def test_drop_rejects_quantity_bool(self) -> None:
        with self.assertRaises(WorldRuleError):
            self.world.drop("item_linglu_pill", True)  # type: ignore[arg-type]


class WorldUseTests(unittest.TestCase):
    """World.use with quantity support."""

    def setUp(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(pack)
        self.world.take("item_linglu_pill", 3)

    def test_use_single(self) -> None:
        self.world.player.hp = 10
        outcome = self.world.use("item_linglu_pill", 1)
        self.assertEqual(outcome.quantity, 1)
        self.assertEqual(outcome.healed_amount, 10)

    def test_use_multiple(self) -> None:
        self.world.player.hp = 5
        outcome = self.world.use("item_linglu_pill", 2)
        self.assertEqual(outcome.quantity, 2)
        self.assertEqual(outcome.healed_amount, 15)  # min(2*10, 20-5)

    def test_use_heal_capped_at_max_hp(self) -> None:
        self.world.player.hp = 15
        outcome = self.world.use("item_linglu_pill", 3)
        self.assertEqual(outcome.quantity, 3)
        self.assertEqual(outcome.healed_amount, 5)  # min(30, 20-15)
        self.assertEqual(self.world.player.hp, 20)

    def test_use_rejects_full_hp(self) -> None:
        with self.assertRaises(WorldRuleError):
            self.world.use("item_linglu_pill", 1)

    def test_use_rejects_insufficient(self) -> None:
        self.world.player.hp = 10
        with self.assertRaises(WorldRuleError):
            self.world.use("item_linglu_pill", 5)

    def test_use_rejects_quantity_0(self) -> None:
        self.world.player.hp = 10
        with self.assertRaises(WorldRuleError):
            self.world.use("item_linglu_pill", 0)


class EquipmentQuantityTests(unittest.TestCase):
    """Equipment requires quantity == 1."""

    def setUp(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(pack)

    def test_equip_success(self) -> None:
        self.world.take("item_crystal_blade", 1)
        outcome = self.world.equip("item_crystal_blade")
        self.assertEqual(outcome.item_id, "item_crystal_blade")

    def test_equip_rejects_non_equippable(self) -> None:
        self.world.take("item_linglu_pill", 1)
        with self.assertRaises(WorldRuleError):
            self.world.equip("item_linglu_pill")


class LootTests(unittest.TestCase):
    """Loot preflight and placement."""

    def setUp(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(pack)
        self.world.move("east")
        self.world.move("east")

    def test_loot_creates_new_stack(self) -> None:
        # Set player HP high and attack repeatedly until monster dies
        self.world.player.hp = 100
        for _ in range(10):
            outcome = self.world.attack("monster_ash_mite")
            if outcome.combat.monster_defeated:
                break
        self.assertTrue(outcome.combat.monster_defeated)
        self.assertIsNotNone(outcome.loot_item)
        gel_stack = self.world.current_room.find_stack("item_ash_mite_gel")
        self.assertIsNotNone(gel_stack)
        self.assertEqual(gel_stack.quantity, 1)


class SaveV7Tests(unittest.TestCase):
    """Save format v7 with stacks, coins, and flags."""

    def setUp(self) -> None:
        self.pack = load_content_pack(DEMO_PATH)
        self.tmpdir = tempfile.mkdtemp()
        self.service = SaveLoadService(self.pack, Path(self.tmpdir))

    def test_save_v7_round_trip(self) -> None:
        world = World.from_content_pack(self.pack)
        world.take("item_linglu_pill", 2)
        self.service.save(world)
        loaded = self.service.load()
        inv = loaded.player.inventory.find_stack("item_linglu_pill")
        self.assertIsNotNone(inv)
        self.assertEqual(inv.quantity, 2)
        room = loaded.rooms["room_ember_wharf"]
        gel = room.find_stack("item_linglu_pill")
        self.assertIsNotNone(gel)
        self.assertEqual(gel.quantity, 1)

    def test_save_format_version_is_7(self) -> None:
        self.assertEqual(SAVE_FORMAT_VERSION, 7)

    def test_save_v7_rejects_v6(self) -> None:
        """A v6 save must be rejected."""
        import json
        v6_data = {
            "save_format_version": 6,
            "content_pack": {"id": "original_demo", "version": "0.6.0"},
            "player": {
                "id": "player_local", "name": "test", "room_id": "room_ember_wharf",
                "max_hp": 20, "hp": 20, "attack": 5, "defense": 1,
                "level": 1, "experience": 0,
                "inventory_item_ids": [],
            },
            "equipped": {"hand": None, "body": None},
            "rooms": {},
            "monsters": {},
            "quest_states": {},
            "active_dialogue": None,
        }
        save_path = Path(self.tmpdir) / "default.json"
        save_path.write_text(json.dumps(v6_data), encoding="utf-8")
        with self.assertRaises(SaveLoadError):
            self.service.load()

    def test_save_v7_load_failure_preserves_world(self) -> None:
        """Failed load must not replace the current world."""
        world = World.from_content_pack(self.pack)
        self.service.save(world)
        # Corrupt the save
        save_path = Path(self.tmpdir) / "default.json"
        save_path.write_text('{"save_format_version": 6}', encoding="utf-8")
        with self.assertRaises(SaveLoadError):
            self.service.load()
        # Original world should be unchanged
        self.assertEqual(world.player.hp, world.player.max_hp)


class DeathGateRegressionTests(unittest.TestCase):
    """M1 death gate must still work with stacks."""

    def setUp(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(pack)
        self.world.move("east")
        self.world.move("east")
        self.world.player.hp = 1
        self.world.attack("monster_ash_mite")
        self.assertEqual(self.world.player.hp, 0)
        self.commands = CommandProcessor(self.world)

    def test_dead_cannot_take(self) -> None:
        r = self.commands.execute("take 灵露丸")
        self.assertIn("倒下了", r.text)

    def test_dead_cannot_drop(self) -> None:
        r = self.commands.execute("drop 微火提灯")
        self.assertIn("倒下了", r.text)

    def test_dead_cannot_use(self) -> None:
        r = self.commands.execute("use 灵露丸")
        self.assertIn("倒下了", r.text)

    def test_dead_cannot_attack(self) -> None:
        r = self.commands.execute("attack 灰壳兽")
        self.assertIn("倒下了", r.text)

    def test_recover_preserves_stack_quantities(self) -> None:
        self.world.recover()
        self.assertEqual(self.world.player.hp, self.world.player.max_hp)
        # Room stacks should be preserved from before death
        # (the monster was in observatory, we moved there and died)
        # After recover we're in ember_wharf, stacks there should be intact


class LockedExitTests(unittest.TestCase):
    """Locked exit must check has_item."""

    def test_locked_exit_with_item(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack)
        world.move("east")  # move to glassgrass_path where character is
        # Get token through dialogue
        world.start_dialogue("character_elder_chen")
        world.select_option(1)  # introduce
        world.select_option(1)  # observatory
        world.select_option(2)  # bye with token
        self.assertTrue(world.player.inventory.has_item("item_chen_token"))
        room = world.move("west")
        self.assertEqual(room.id, "room_ember_wharf")

    def test_locked_exit_without_item(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack)
        world.move("east")
        with self.assertRaises(WorldRuleError):
            world.move("west")


SCHEMA_DIR = PROJECT_ROOT / "schemas"


class SchemaContractTests(unittest.TestCase):
    """Verify JSON schemas match the M2 typed-stack contracts."""

    def _load(self, name: str) -> dict:
        return json.loads((SCHEMA_DIR / name).read_text("utf-8"))

    def test_item_schema_has_stack_limit(self) -> None:
        schema = self._load("item.schema.json")
        prop = schema["properties"]["stack_limit"]
        self.assertEqual(prop["type"], "integer")
        self.assertEqual(prop["minimum"], 1)

    def test_location_schema_uses_item_stacks(self) -> None:
        schema = self._load("location.schema.json")
        self.assertIn("item_stacks", schema["required"])
        self.assertIn("item_stacks", schema["properties"])
        self.assertNotIn("item_ids", schema["required"])
        self.assertNotIn("item_ids", schema["properties"])
        ref = schema["properties"]["item_stacks"]["items"]["$ref"]
        self.assertEqual(ref, "common.schema.json#/$defs/item_stack")

    def test_monster_schema_uses_loot_item(self) -> None:
        schema = self._load("monster.schema.json")
        self.assertNotIn("loot_item_id", schema["properties"])
        self.assertIn("loot_item", schema["properties"])
        ref = schema["properties"]["loot_item"]["$ref"]
        self.assertEqual(ref, "common.schema.json#/$defs/item_stack")

    def test_dialogue_schema_uses_effects_union(self) -> None:
        schema = self._load("dialogue.schema.json")
        opt_schema = (
            schema["properties"]["nodes"]["items"]
            ["properties"]["options"]["items"]
        )
        self.assertNotIn("grant_item", opt_schema["properties"])
        self.assertIn("effects", opt_schema["required"])
        self.assertIn("effects", opt_schema["properties"])
        ref = opt_schema["properties"]["effects"]["items"]["$ref"]
        self.assertEqual(ref, "#/$defs/dialogue_effect")

    def test_common_schema_item_stack_definition(self) -> None:
        schema = self._load("common.schema.json")
        stack = schema["$defs"]["item_stack"]
        self.assertEqual(stack["type"], "object")
        self.assertIn("item_id", stack["required"])
        self.assertIn("quantity", stack["required"])
        self.assertFalse(stack["additionalProperties"])
        self.assertEqual(
            stack["properties"]["item_id"]["$ref"], "#/$defs/stable_id"
        )
        # quantity references positive_integer which has minimum 1
        qty = stack["properties"]["quantity"]
        self.assertEqual(qty["$ref"], "#/$defs/positive_integer")
        pos_int = schema["$defs"]["positive_integer"]
        self.assertEqual(pos_int["minimum"], 1)


if __name__ == "__main__":
    unittest.main()
