"""Tests for the equipment system — content loading, equip/unequip,
effective_attack, combat integration, save round-trip, and edge cases."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from lore2mud.content.loader import ContentValidationError, load_content_pack
from lore2mud.engine.commands import CommandProcessor
from lore2mud.engine.save import SAVE_FORMAT_VERSION, SaveLoadError, SaveLoadService
from lore2mud.engine.world import World, WorldRuleError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = PROJECT_ROOT / "examples" / "original_demo"


# -- Content loading tests ---------------------------------------------------


class EquipmentContentLoadingTests(unittest.TestCase):
    """Equipment items must be validated during content pack loading."""

    def test_demo_loads_with_blade(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        self.assertIn("item_crystal_blade", pack.items)
        blade = pack.items["item_crystal_blade"]
        self.assertEqual(blade.slot, "hand")
        self.assertEqual(blade.attack_bonus, 3)

    def test_slot_hand_attack_bonus_zero_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            bp = Path(td) / "bad"
            shutil.copytree(DEMO_PATH, bp)
            items = json.loads((bp / "items.json").read_text("utf-8"))
            items[2]["attack_bonus"] = 0
            (bp / "items.json").write_text(
                json.dumps(items, ensure_ascii=False, indent=2), "utf-8"
            )
            with self.assertRaises(ContentValidationError) as ctx:
                load_content_pack(bp)
            self.assertIn("attack_bonus", str(ctx.exception))

    def test_slot_null_attack_bonus_rejected(self) -> None:
        """attack_bonus >= 1 without slot must be rejected."""
        with tempfile.TemporaryDirectory() as td:
            bp = Path(td) / "bad"
            shutil.copytree(DEMO_PATH, bp)
            items = json.loads((bp / "items.json").read_text("utf-8"))
            del items[2]["slot"]
            (bp / "items.json").write_text(
                json.dumps(items, ensure_ascii=False, indent=2), "utf-8"
            )
            with self.assertRaises(ContentValidationError) as ctx:
                load_content_pack(bp)
            self.assertIn("slot", str(ctx.exception))

    def test_slot_and_heal_amount_rejected(self) -> None:
        """Cannot have both slot and heal_amount."""
        with tempfile.TemporaryDirectory() as td:
            bp = Path(td) / "bad"
            shutil.copytree(DEMO_PATH, bp)
            items = json.loads((bp / "items.json").read_text("utf-8"))
            items[2]["heal_amount"] = 5
            (bp / "items.json").write_text(
                json.dumps(items, ensure_ascii=False, indent=2), "utf-8"
            )
            with self.assertRaises(ContentValidationError) as ctx:
                load_content_pack(bp)
            self.assertIn("slot", str(ctx.exception))
            self.assertIn("heal_amount", str(ctx.exception))

    def test_invalid_slot_value_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            bp = Path(td) / "bad"
            shutil.copytree(DEMO_PATH, bp)
            items = json.loads((bp / "items.json").read_text("utf-8"))
            items[2]["slot"] = "head"
            (bp / "items.json").write_text(
                json.dumps(items, ensure_ascii=False, indent=2), "utf-8"
            )
            with self.assertRaises(ContentValidationError) as ctx:
                load_content_pack(bp)
            self.assertIn("hand", str(ctx.exception))

    def test_slot_null_explicitly_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            bp = Path(td) / "bad"
            shutil.copytree(DEMO_PATH, bp)
            items = json.loads((bp / "items.json").read_text("utf-8"))
            items[2]["slot"] = None
            (bp / "items.json").write_text(
                json.dumps(items, ensure_ascii=False, indent=2), "utf-8"
            )
            with self.assertRaises(ContentValidationError) as ctx:
                load_content_pack(bp)
            self.assertIn("slot", str(ctx.exception))

    def test_attack_bonus_zero_no_slot_accepted(self) -> None:
        """字段缺省时普通物品默认为不可装备。"""
        pack = load_content_pack(DEMO_PATH)
        lantern = pack.items["item_spark_lantern"]
        self.assertEqual(lantern.attack_bonus, 0)
        self.assertIsNone(lantern.slot)

    def test_attack_bonus_without_slot_rejected(self) -> None:
        """attack_bonus >= 1 without slot must be rejected."""
        with tempfile.TemporaryDirectory() as td:
            bp = Path(td) / "bad"
            shutil.copytree(DEMO_PATH, bp)
            items = json.loads((bp / "items.json").read_text("utf-8"))
            items[2].pop("slot")
            (bp / "items.json").write_text(
                json.dumps(items, ensure_ascii=False, indent=2), "utf-8"
            )
            with self.assertRaises(ContentValidationError) as ctx:
                load_content_pack(bp)
            self.assertIn("slot", str(ctx.exception))


# -- Equip/unequip tests -----------------------------------------------------


class EquipUnequipTests(unittest.TestCase):
    """Equipping and unequipping items modify effective_attack correctly."""

    def setUp(self) -> None:
        self.pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(self.pack, player_name="测试旅人")
        self.commands = CommandProcessor(self.world)
        self.commands.execute("take item_crystal_blade")

    def test_equip_increases_effective_attack(self) -> None:
        self.assertEqual(self.world.effective_attack, 5)
        result = self.commands.execute("equip item_crystal_blade")
        self.assertIn("装备了", result.text)
        self.assertEqual(self.world.effective_attack, 8)

    def test_status_shows_effective_attack(self) -> None:
        self.commands.execute("equip item_crystal_blade")
        result = self.commands.execute("status")
        self.assertIn("8", result.text)
        self.assertIn("5 基础", result.text)
        self.assertIn("+ 3", result.text)

    def test_unequip_restores_base_attack(self) -> None:
        self.commands.execute("equip item_crystal_blade")
        self.assertEqual(self.world.effective_attack, 8)
        result = self.commands.execute("unequip")
        self.assertIn("卸下了", result.text)
        self.assertEqual(self.world.effective_attack, 5)

    def test_equip_unequip_equip_cycle(self) -> None:
        self.commands.execute("equip item_crystal_blade")
        self.commands.execute("unequip")
        self.commands.execute("equip item_crystal_blade")
        self.assertEqual(self.world.effective_attack, 8)

    def test_equip_by_display_name(self) -> None:
        result = self.commands.execute("equip 晶刃")
        self.assertIn("装备了", result.text)
        self.assertEqual(self.world.effective_attack, 8)


# -- Failure path tests ------------------------------------------------------


class EquipmentFailureTests(unittest.TestCase):
    """All failure paths leave state unchanged."""

    def setUp(self) -> None:
        self.pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(self.pack, player_name="测试旅人")
        self.commands = CommandProcessor(self.world)
        self.commands.execute("take item_crystal_blade")

    def test_equip_not_in_inventory(self) -> None:
        ea_before = self.world.effective_attack
        result = self.commands.execute("equip nonexistent")
        self.assertIn("没有", result.text)
        self.assertEqual(self.world.effective_attack, ea_before)

    def test_equip_non_equippable(self) -> None:
        self.commands.execute("take item_spark_lantern")
        ea_before = self.world.effective_attack
        result = self.commands.execute("equip item_spark_lantern")
        self.assertIn("无法装备", result.text)
        self.assertEqual(self.world.effective_attack, ea_before)

    def test_equip_consumable_rejected(self) -> None:
        self.commands.execute("take item_linglu_pill")
        ea_before = self.world.effective_attack
        result = self.commands.execute("equip item_linglu_pill")
        self.assertIn("无法装备", result.text)
        self.assertEqual(self.world.effective_attack, ea_before)

    def test_equip_already_equipped(self) -> None:
        self.commands.execute("equip item_crystal_blade")
        ea_before = self.world.effective_attack
        inv_before = [s.item_id for s in self.world.player.inventory.stacks]
        result = self.commands.execute("equip item_crystal_blade")
        self.assertIn("已经装备了", result.text)
        self.assertEqual(self.world.effective_attack, ea_before)
        self.assertEqual([s.item_id for s in self.world.player.inventory.stacks], inv_before)

    def test_equip_second_hand_item_rejected(self) -> None:
        """When hand is occupied, equipping another item is rejected."""
        self.commands.execute("equip item_crystal_blade")
        # Add a second equippable item.
        self.world.items["item_fake_sword"] = type(self.world.items["item_crystal_blade"])(
            id="item_fake_sword", name="假剑", description="测试",
            slot="hand", attack_bonus=1,
        )
        from lore2mud.inventory.models import ItemStack
        self.world.player.inventory.stacks.append(ItemStack(item_id="item_fake_sword", quantity=1))
        ea_before = self.world.effective_attack
        result = self.commands.execute("equip item_fake_sword")
        self.assertIn("已经装备了", result.text)
        self.assertEqual(self.world.effective_attack, ea_before)
        self.assertEqual(self.world.equipped.hand, "item_crystal_blade")

    def test_unequip_empty_slot(self) -> None:
        result = self.commands.execute("unequip")
        self.assertIn("没有", result.text)

    def test_use_equipped_item_rejected(self) -> None:
        self.commands.execute("take item_linglu_pill")
        self.commands.execute("equip item_crystal_blade")
        # Damage the player first so use would be valid if not equipped.
        self.commands.execute("go east")
        self.commands.execute("go east")
        self.commands.execute("attack monster_ash_mite")
        self.assertLess(self.world.player.hp, self.world.player.max_hp)
        # The blade is equipped, so use is rejected at domain layer.
        result = self.commands.execute("use item_crystal_blade")
        self.assertIn("正在装备中", result.text)
        self.assertEqual(self.world.effective_attack, 8)

    def test_use_equipped_blade_rejected(self) -> None:
        """Directly test that use rejects an equipped item."""
        self.commands.execute("equip item_crystal_blade")
        result = self.commands.execute("use item_crystal_blade")
        self.assertIn("正在装备中", result.text)
        self.assertEqual(self.world.effective_attack, 8)

    def test_equip_empty_args(self) -> None:
        result = self.commands.execute("equip")
        self.assertIn("用法", result.text)

    def test_unequip_with_args_rejected(self) -> None:
        result = self.commands.execute("unequip extra")
        self.assertIn("用法", result.text)


# -- World.use() direct test --------------------------------------------------


class WorldUseEquipRejectTest(unittest.TestCase):
    """Directly call World.use() to verify equipped rejection at domain layer."""
    def test_use_equipped_at_domain_layer(self) -> None:
        """Directly test World.use() rejects equipped items at domain layer."""
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack)
        world.take("item_crystal_blade")
        world.take("item_linglu_pill")
        world.move("east")
        world.move("east")
        world.attack("monster_ash_mite")
        world.equip("item_crystal_blade")
        with self.assertRaises(WorldRuleError) as ctx:
            world.use("item_crystal_blade")
        self.assertIn("正在装备中", str(ctx.exception))
        # unequip and try with pill
        world.unequip()
        result = world.use("item_linglu_pill")
        self.assertGreater(result.healed_amount, 0)


# -- Combat integration tests -------------------------------------------------


class EquipmentCombatTests(unittest.TestCase):
    """Equipment affects combat damage calculation."""

    def setUp(self) -> None:
        self.pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(self.pack, player_name="测试旅人")
        self.commands = CommandProcessor(self.world)
        self.commands.execute("take item_crystal_blade")
        self.commands.execute("equip item_crystal_blade")
        self.commands.execute("go east")
        self.commands.execute("go east")

    def test_equipped_attack_increases_damage(self) -> None:
        """With blade equipped, damage should be 8-1=7."""
        result = self.commands.execute("attack monster_ash_mite")
        self.assertIn("7 点伤害", result.text)

    def test_player_takes_counter_damage(self) -> None:
        """Player should take 3-1=2 damage from monster反击."""
        self.commands.execute("attack monster_ash_mite")
        self.assertEqual(self.world.player.hp, 18)


# -- Upgrade while equipped tests ---------------------------------------------


class EquipmentUpgradeTests(unittest.TestCase):
    """Equipment and level-up interaction."""

    def setUp(self) -> None:
        self.pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(self.pack, player_name="测试旅人")
        self.commands = CommandProcessor(self.world)
        self.commands.execute("take item_crystal_blade")
        self.commands.execute("equip item_crystal_blade")

    def test_level_up_with_equipment(self) -> None:
        """Level up while equipped: effective_attack = new_base + bonus."""
        self.commands.execute("go east")
        self.commands.execute("go east")
        # Two attacks to defeat monster (7 damage each vs 8 HP)
        self.commands.execute("attack monster_ash_mite")
        self.commands.execute("attack monster_ash_mite")
        # Player should be level 2 with base attack 7, blade +3 = 10
        self.assertEqual(self.world.player.level, 2)
        self.assertEqual(self.world.player.attack, 7)
        self.assertEqual(self.world.effective_attack, 10)

    def test_unequip_after_level_up(self) -> None:
        """After leveling up, unequip shows base attack = 7."""
        self.commands.execute("go east")
        self.commands.execute("go east")
        self.commands.execute("attack monster_ash_mite")
        self.commands.execute("attack monster_ash_mite")
        self.commands.execute("unequip")
        self.assertEqual(self.world.player.attack, 7)
        self.assertEqual(self.world.effective_attack, 7)


# -- Save round-trip tests ---------------------------------------------------


class EquipmentSaveRoundTripTests(unittest.TestCase):
    """Equipment state survives save/load."""

    def setUp(self) -> None:
        self.pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(self.pack, player_name="测试旅人")
        self.tmpdir = tempfile.mkdtemp()
        self.service = SaveLoadService(self.pack, Path(self.tmpdir))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_save_stores_base_attack(self) -> None:
        """Save file stores base attack (5), not effective attack (8)."""
        from lore2mud.engine.save import _serialize_world
        self.world.take("item_crystal_blade")
        self.world.equip("item_crystal_blade")
        data = _serialize_world(self.world)
        self.assertEqual(data["player"]["attack"], 5)

    def test_save_stores_equipped_hand(self) -> None:
        from lore2mud.engine.save import _serialize_world
        self.world.take("item_crystal_blade")
        self.world.equip("item_crystal_blade")
        data = _serialize_world(self.world)
        self.assertEqual(data["equipped"]["hand"], "item_crystal_blade")

    def test_equip_survives_save_load(self) -> None:
        self.world.take("item_crystal_blade")
        self.world.equip("item_crystal_blade")
        self.service.save(self.world)
        loaded = self.service.load()
        self.assertEqual(loaded.equipped.hand, "item_crystal_blade")
        self.assertEqual(loaded.effective_attack, 8)
        self.assertEqual(loaded.player.attack, 5)

    def test_unequip_survives_save_load(self) -> None:
        self.world.take("item_crystal_blade")
        self.world.equip("item_crystal_blade")
        self.world.unequip()
        self.service.save(self.world)
        loaded = self.service.load()
        self.assertIsNone(loaded.equipped.hand)
        self.assertEqual(loaded.effective_attack, 5)

    def test_old_v2_save_rejected(self) -> None:
        """v2 saves (no equipped field) must be rejected."""
        self.service.save(self.world)
        txt = self.service.save_path.read_text("utf-8")
        txt = txt.replace('"version": "0.2.4"', '"version": "0.2.3"')
        txt = txt.replace(f'"save_format_version": {SAVE_FORMAT_VERSION}',
                          '"save_format_version": 2')
        self.service.save_path.write_text(txt, "utf-8")
        with self.assertRaises(SaveLoadError) as ctx:
            self.service.load()
        self.assertIn("格式版本", str(ctx.exception))

    def test_missing_equipped_rejected(self) -> None:
        self.service.save(self.world)
        data = json.loads(self.service.save_path.read_text("utf-8"))
        del data["equipped"]
        self.service.save_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), "utf-8"
        )
        with self.assertRaises(SaveLoadError) as ctx:
            self.service.load()
        self.assertIn("equipped", str(ctx.exception))

    def test_equipped_unknown_slot_rejected(self) -> None:
        self.service.save(self.world)
        data = json.loads(self.service.save_path.read_text("utf-8"))
        data["equipped"]["head"] = "item_crystal_blade"
        self.service.save_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), "utf-8"
        )
        with self.assertRaises(SaveLoadError) as ctx:
            self.service.load()
        self.assertIn("未知字段", str(ctx.exception))


# -- Command integration tests ------------------------------------------------
# -- Command integration tests ------------------------------------------------


class EquipmentCommandTests(unittest.TestCase):
    """equip/unequip command rendering."""

    def test_help_includes_equip(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack)
        commands = CommandProcessor(world)
        result = commands.execute("help")
        self.assertIn("equip", result.text)
        self.assertIn("unequip", result.text)

    def test_unequip_default_hand(self) -> None:
        """Bare 'unequip' defaults to hand slot."""
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack)
        cmds = CommandProcessor(world)
        cmds.execute("take item_crystal_blade")
        cmds.execute("equip item_crystal_blade")
        result = cmds.execute("unequip")
        self.assertIn("晶刃", result.text)
        self.assertIsNone(world.equipped.hand)

    def test_unequip_explicit_body(self) -> None:
        """'unequip body' unequips body slot."""
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack)
        cmds = CommandProcessor(world)
        cmds.execute("take item_bronze_scale_mail")
        cmds.execute("equip item_bronze_scale_mail")
        result = cmds.execute("unequip body")
        self.assertIn("铜鳞甲", result.text)
        self.assertIsNone(world.equipped.body)

    def test_unequip_unknown_slot(self) -> None:
        """'unequip head' reports unknown slot."""
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack)
        cmds = CommandProcessor(world)
        result = cmds.execute("unequip head")
        self.assertIn("用法", result.text)

    def test_unequip_extra_args(self) -> None:
        """'unequip body extra' reports usage."""
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack)
        cmds = CommandProcessor(world)
        result = cmds.execute("unequip body extra")
        self.assertIn("用法", result.text)


# -- Body equip/unequip tests -------------------------------------------------


class BodyEquipTests(unittest.TestCase):
    """Body slot equip, unequip, and dual-slot behavior."""

    def setUp(self) -> None:
        self.pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(self.pack, player_name="测试旅人")
        self.commands = CommandProcessor(self.world)
        self.commands.execute("take item_crystal_blade")
        self.commands.execute("take item_bronze_scale_mail")

    def test_equip_body_increases_defense(self) -> None:
        self.assertEqual(self.world.effective_defense, 1)
        result = self.commands.execute("equip item_bronze_scale_mail")
        self.assertIn("装备了", result.text)
        self.assertEqual(self.world.effective_defense, 4)

    def test_status_shows_defense(self) -> None:
        self.commands.execute("equip item_bronze_scale_mail")
        result = self.commands.execute("status")
        self.assertIn("4", result.text)
        self.assertIn("1 基础", result.text)
        self.assertIn("+ 3", result.text)

    def test_unequip_body_restores_defense(self) -> None:
        self.commands.execute("equip item_bronze_scale_mail")
        self.assertEqual(self.world.effective_defense, 4)
        result = self.commands.execute("unequip body")
        self.assertIn("铜鳞甲", result.text)
        self.assertEqual(self.world.effective_defense, 1)

    def test_hand_and_body_simultaneously(self) -> None:
        """Both hand and body can be equipped at the same time."""
        self.commands.execute("equip item_crystal_blade")
        self.commands.execute("equip item_bronze_scale_mail")
        self.assertEqual(self.world.effective_attack, 8)
        self.assertEqual(self.world.effective_defense, 4)
        self.assertEqual(self.world.equipped.hand, "item_crystal_blade")
        self.assertEqual(self.world.equipped.body, "item_bronze_scale_mail")

    def test_body_occupied_rejects_second(self) -> None:
        """Equipping another body item when body is occupied is rejected."""
        self.commands.execute("equip item_bronze_scale_mail")
        # Create a second body item.
        self.world.items["item_fake_armor"] = type(
            self.world.items["item_bronze_scale_mail"]
        )(
            id="item_fake_armor", name="假甲", description="测试",
            slot="body", defense_bonus=1,
        )
        from lore2mud.inventory.models import ItemStack
        self.world.player.inventory.stacks.append(ItemStack(item_id="item_fake_armor", quantity=1))
        result = self.commands.execute("equip item_fake_armor")
        self.assertIn("已经装备了", result.text)
        self.assertEqual(self.world.equipped.body, "item_bronze_scale_mail")


# -- Use double-slot rejection tests ------------------------------------------


class UseDoubleSlotRejectionTests(unittest.TestCase):
    """World.use() rejects items in either equipped slot."""

    def setUp(self) -> None:
        self.pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(self.pack)
        self.world.take("item_crystal_blade")
        self.world.take("item_bronze_scale_mail")
        self.world.take("item_linglu_pill")
        self.world.move("east")
        self.world.move("east")
        self.world.attack("monster_ash_mite")

    def test_use_hand_equipped_rejected(self) -> None:
        self.world.equip("item_crystal_blade")
        with self.assertRaises(WorldRuleError) as ctx:
            self.world.use("item_crystal_blade")
        self.assertIn("正在装备中", str(ctx.exception))

    def test_use_body_equipped_rejected(self) -> None:
        self.world.equip("item_bronze_scale_mail")
        with self.assertRaises(WorldRuleError) as ctx:
            self.world.use("item_bronze_scale_mail")
        self.assertIn("正在装备中", str(ctx.exception))


# -- Combat with defense tests -----------------------------------------------


class BodyCombatTests(unittest.TestCase):
    """Equipment defense affects combat counter damage."""

    def test_counter_damage_with_body_armor(self) -> None:
        """Monster attack=3, player defense=1+3=4. Damage = max(1,3-4) = 1."""
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack)
        world.take("item_bronze_scale_mail")
        world.equip("item_bronze_scale_mail")
        world.move("east")
        world.move("east")
        self.assertEqual(world.effective_defense, 4)
        world.attack("monster_ash_mite")
        # Monster attack=3, defense=4 → max(1, 3-4) = 1
        self.assertEqual(world.player.hp, 19)

    def test_counter_damage_without_armor(self) -> None:
        """Without armor: defense=1, damage = max(1,3-1) = 2."""
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack)
        world.move("east")
        world.move("east")
        self.assertEqual(world.effective_defense, 1)
        world.attack("monster_ash_mite")
        self.assertEqual(world.player.hp, 18)

    def test_direct_world_attack_defense(self) -> None:
        """Directly call World.attack() to verify effective_defense."""
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack)
        world.take("item_bronze_scale_mail")
        world.equip("item_bronze_scale_mail")
        world.move("east")
        world.move("east")
        outcome = world.attack("monster_ash_mite")
        self.assertEqual(outcome.combat.damage_to_player, 1)


# -- Upgrade with body tests --------------------------------------------------


class BodyUpgradeTests(unittest.TestCase):
    """Body armor and level-up interaction."""

    def test_level_up_with_body(self) -> None:
        """Level up while body equipped: defense=2, effective=5."""
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack)
        world.take("item_crystal_blade")
        world.take("item_bronze_scale_mail")
        world.equip("item_crystal_blade")
        world.equip("item_bronze_scale_mail")
        world.move("east")
        world.move("east")
        world.attack("monster_ash_mite")
        world.attack("monster_ash_mite")
        self.assertEqual(world.player.level, 2)
        self.assertEqual(world.player.defense, 2)
        self.assertEqual(world.effective_defense, 5)

    def test_unequip_body_after_upgrade(self) -> None:
        """After upgrade, unequip body shows base defense=2."""
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack)
        world.take("item_crystal_blade")
        world.take("item_bronze_scale_mail")
        world.equip("item_crystal_blade")
        world.equip("item_bronze_scale_mail")
        world.move("east")
        world.move("east")
        world.attack("monster_ash_mite")
        world.attack("monster_ash_mite")
        world.unequip("body")
        self.assertEqual(world.player.defense, 2)
        self.assertEqual(world.effective_defense, 2)


# -- Body save round-trip tests -----------------------------------------------


class BodySaveRoundTripTests(unittest.TestCase):
    """Body equipment state survives save/load."""

    def setUp(self) -> None:
        self.pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(self.pack, player_name="测试旅人")
        self.tmpdir = tempfile.mkdtemp()
        self.service = SaveLoadService(self.pack, Path(self.tmpdir))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_both_slots_survive_save_load(self) -> None:
        self.world.take("item_crystal_blade")
        self.world.take("item_bronze_scale_mail")
        self.world.equip("item_crystal_blade")
        self.world.equip("item_bronze_scale_mail")
        self.service.save(self.world)
        loaded = self.service.load()
        self.assertEqual(loaded.equipped.hand, "item_crystal_blade")
        self.assertEqual(loaded.equipped.body, "item_bronze_scale_mail")
        self.assertEqual(loaded.effective_attack, 8)
        self.assertEqual(loaded.effective_defense, 4)

    def test_save_stores_base_stats(self) -> None:
        """Save stores base defense (1), not effective defense (4)."""
        from lore2mud.engine.save import _serialize_world
        self.world.take("item_bronze_scale_mail")
        self.world.equip("item_bronze_scale_mail")
        data = _serialize_world(self.world)
        self.assertEqual(data["player"]["defense"], 1)
        self.assertEqual(data["equipped"]["body"], "item_bronze_scale_mail")

    def test_v3_save_rejected(self) -> None:
        """v3 saves (no body key) must be rejected."""
        self.service.save(self.world)
        txt = self.service.save_path.read_text("utf-8")
        txt = txt.replace('"save_format_version": 8', '"save_format_version": 4')
        self.service.save_path.write_text(txt, "utf-8")
        with self.assertRaises(SaveLoadError) as ctx:
            self.service.load()
        self.assertIn("格式版本", str(ctx.exception))

    def test_missing_body_key_rejected(self) -> None:
        self.service.save(self.world)
        data = json.loads(self.service.save_path.read_text("utf-8"))
        del data["equipped"]["body"]
        self.service.save_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), "utf-8"
        )
        with self.assertRaises(SaveLoadError) as ctx:
            self.service.load()
        self.assertIn("body", str(ctx.exception))


# -- Schema and loader formal tests -------------------------------------------


class SchemaAndLoaderFormalTests(unittest.TestCase):
    """Schema and loader combo rules must be formally verified."""

    def test_explicit_attack_bonus_zero_without_slot_rejected(self) -> None:
        """显式 attack_bonus: 0 且无 slot 必须被 loader 拒绝。"""
        with tempfile.TemporaryDirectory() as td:
            bp = Path(td) / "bad"
            shutil.copytree(DEMO_PATH, bp)
            items = [
                {
                    "id": "item_test_zero",
                    "name": "零攻加成",
                    "description": "测试。",
                    "attack_bonus": 0,
                },
            ]
            (bp / "items.json").write_text(
                json.dumps(items, ensure_ascii=False, indent=2), "utf-8"
            )
            with self.assertRaises(ContentValidationError) as ctx:
                load_content_pack(bp)
            self.assertIn("attack_bonus", str(ctx.exception))

    def test_item_schema_combo_rules(self) -> None:
        """Read item.schema.json and assert combo constraints without
        jsonschema dependency."""
        schema_path = PROJECT_ROOT / "schemas" / "item.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        props = schema["properties"]

        # attack_bonus and defense_bonus minimum must be 1.
        self.assertEqual(props["attack_bonus"]["minimum"], 1)
        self.assertEqual(props["defense_bonus"]["minimum"], 1)

        # slot enum must include hand and body.
        self.assertIn("hand", props["slot"]["enum"])
        self.assertIn("body", props["slot"]["enum"])

        # allOf must exist with combo rules.
        all_of = schema.get("allOf", [])
        self.assertGreaterEqual(len(all_of), 7)

        # Rule 0: slot requires either attack_bonus or defense_bonus.
        self.assertIn("slot", all_of[0]["if"]["required"])
        self.assertIn("anyOf", all_of[0]["then"])

        # Rule 1: attack_bonus requires slot.
        self.assertIn("attack_bonus", all_of[1]["if"]["required"])
        self.assertIn("slot", all_of[1]["then"]["required"])

        # Rule 2: defense_bonus requires slot.
        self.assertIn("defense_bonus", all_of[2]["if"]["required"])
        self.assertIn("slot", all_of[2]["then"]["required"])

        # Rule 3: heal_amount excludes slot.
        self.assertIn("heal_amount", all_of[3]["if"]["required"])
        self.assertEqual(all_of[3]["then"]["not"]["required"], ["slot"])

        # Rule 4: slot excludes heal_amount.
        self.assertIn("slot", all_of[4]["if"]["required"])
        self.assertEqual(all_of[4]["then"]["not"]["required"], ["heal_amount"])

        # Rule 5: attack_bonus excludes defense_bonus.
        self.assertIn("attack_bonus", all_of[5]["if"]["required"])
        self.assertEqual(all_of[5]["then"]["not"]["required"], ["defense_bonus"])

        # Rule 6: defense_bonus excludes attack_bonus.
        self.assertIn("defense_bonus", all_of[6]["if"]["required"])
        self.assertEqual(all_of[6]["then"]["not"]["required"], ["attack_bonus"])

        # Rule 7: hand slot excludes defense_bonus.
        self.assertEqual(all_of[7]["if"]["properties"]["slot"]["const"], "hand")
        self.assertEqual(all_of[7]["then"]["not"]["required"], ["defense_bonus"])

        # Rule 8: body slot excludes attack_bonus.
        self.assertEqual(all_of[8]["if"]["properties"]["slot"]["const"], "body")
        self.assertEqual(all_of[8]["then"]["not"]["required"], ["attack_bonus"])


# -- Body loader illegal combo tests -----------------------------------------


class BodyLoaderIllegalComboTests(unittest.TestCase):
    """Body slot loader rejects all illegal field combinations."""

    def _make_pack(self, items):
        with tempfile.TemporaryDirectory() as td:
            bp = Path(td) / "bad"
            shutil.copytree(DEMO_PATH, bp)
            (bp / "items.json").write_text(
                json.dumps(items, ensure_ascii=False, indent=2), "utf-8"
            )
            with self.assertRaises(ContentValidationError) as ctx:
                load_content_pack(bp)
            return str(ctx.exception)

    def test_body_with_attack_bonus_rejected(self) -> None:
        err = self._make_pack([{
            "id": "item_bad", "name": "坏", "description": "T",
            "slot": "body", "attack_bonus": 3,
        }])
        self.assertIn("attack_bonus", err)

    def test_body_with_heal_amount_rejected(self) -> None:
        err = self._make_pack([{
            "id": "item_bad", "name": "坏", "description": "T",
            "slot": "body", "heal_amount": 5,
        }])
        self.assertIn("heal_amount", err)

    def test_body_with_zero_defense_rejected(self) -> None:
        err = self._make_pack([{
            "id": "item_bad", "name": "坏", "description": "T",
            "slot": "body", "defense_bonus": 0,
        }])
        self.assertIn("defense_bonus", err)

    def test_hand_with_defense_bonus_rejected(self) -> None:
        err = self._make_pack([{
            "id": "item_bad", "name": "坏", "description": "T",
            "slot": "hand", "defense_bonus": 3,
        }])
        self.assertIn("defense_bonus", err)

    def test_explicit_null_slot_rejected(self) -> None:
        err = self._make_pack([{
            "id": "item_bad", "name": "坏", "description": "T",
            "slot": None,
        }])
        self.assertIn("slot", err)

    def test_explicit_null_defense_bonus_rejected(self) -> None:
        err = self._make_pack([{
            "id": "item_bad", "name": "坏", "description": "T",
            "defense_bonus": None,
        }])
        self.assertIn("defense_bonus", err)


# -- World state invariance tests ---------------------------------------------


class WorldStateInvarianceTests(unittest.TestCase):
    """Failed equip/unequip must not change World state."""

    def setUp(self) -> None:
        self.pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(self.pack)
        # Pre-populate inventory so room state is stable.
        self.world.take("item_spark_lantern")
        self.world.take("item_linglu_pill")
        self.world.take("item_crystal_blade")
        self.world.take("item_bronze_scale_mail")

    def _snapshot(self):
        return (
            self.world.effective_attack,
            self.world.effective_defense,
            self.world.player.attack,
            self.world.player.defense,
            self.world.player.hp,
            [s.item_id for s in self.world.player.inventory.stacks],
            self.world.equipped.hand,
            self.world.equipped.body,
        )

    def test_equip_non_equippable_no_change(self) -> None:
        before = self._snapshot()
        with self.assertRaises(WorldRuleError):
            self.world.equip("item_spark_lantern")
        self.assertEqual(self._snapshot(), before)

    def test_equip_consumable_no_change(self) -> None:
        before = self._snapshot()
        with self.assertRaises(WorldRuleError):
            self.world.equip("item_linglu_pill")
        self.assertEqual(self._snapshot(), before)

    def test_equip_occupied_hand_no_change(self) -> None:
        self.world.equip("item_crystal_blade")
        before = self._snapshot()
        with self.assertRaises(WorldRuleError):
            self.world.equip("item_spark_lantern")
        self.assertEqual(self._snapshot(), before)

    def test_unequip_empty_body_no_change(self) -> None:
        before = self._snapshot()
        with self.assertRaises(WorldRuleError):
            self.world.unequip("body")
        self.assertEqual(self._snapshot(), before)

    def test_unequip_unknown_slot_no_change(self) -> None:
        before = self._snapshot()
        with self.assertRaises(WorldRuleError):
            self.world.unequip("head")
        self.assertEqual(self._snapshot(), before)


# -- Save v4 illegal matrix tests ---------------------------------------------


class SaveV4IllegalMatrixTests(unittest.TestCase):
    """Save v4 rejects all illegal equipped configurations."""

    def setUp(self) -> None:
        self.pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(self.pack)
        self.tmpdir = tempfile.mkdtemp()
        self.service = SaveLoadService(self.pack, Path(self.tmpdir))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _load_with_tamper(self, mutate):
        self.service.save(self.world)
        data = json.loads(self.service.save_path.read_text("utf-8"))
        mutate(data)
        self.service.save_path.write_text(
            json.dumps(data, ensure_ascii=False), "utf-8"
        )
        return self.service.load()

    def test_body_not_in_inventory_rejected(self) -> None:
        with self.assertRaises(SaveLoadError) as ctx:
            self._load_with_tamper(
                lambda d: d.__setitem__("equipped", {"hand": None, "body": "item_bronze_scale_mail"})
            )
        self.assertIn("背包", str(ctx.exception))

    def test_body_wrong_slot_rejected(self) -> None:
        """hand item (crystal_blade, slot=hand) in body slot → slot mismatch."""
        self.world.take("item_crystal_blade")
        with self.assertRaises(SaveLoadError) as ctx:
            self._load_with_tamper(
                lambda d: d.__setitem__("equipped", {"hand": None, "body": "item_crystal_blade"})
            )
        self.assertIn("slot", str(ctx.exception))

    def test_body_normal_item_rejected(self) -> None:
        """Normal item (spark_lantern, slot=None) in body slot → slot mismatch."""
        self.world.take("item_spark_lantern")
        with self.assertRaises(SaveLoadError) as ctx:
            self._load_with_tamper(
                lambda d: d.__setitem__("equipped", {"hand": None, "body": "item_spark_lantern"})
            )
        self.assertIn("slot", str(ctx.exception))

    def test_hand_normal_item_rejected(self) -> None:
        """Normal item (spark_lantern, slot=None) in hand slot → slot mismatch."""
        self.world.take("item_spark_lantern")
        with self.assertRaises(SaveLoadError) as ctx:
            self._load_with_tamper(
                lambda d: d.__setitem__("equipped", {"hand": "item_spark_lantern", "body": None})
            )
        self.assertIn("slot", str(ctx.exception))

    def test_body_consumable_slot_mismatch(self) -> None:
        """Consumable (linglu_pill, slot=None) in body slot → slot mismatch."""
        self.world.take("item_linglu_pill")
        with self.assertRaises(SaveLoadError) as ctx:
            self._load_with_tamper(
                lambda d: d.__setitem__("equipped", {"hand": None, "body": "item_linglu_pill"})
            )
        self.assertIn("slot", str(ctx.exception))

    def test_missing_hand_key_rejected(self) -> None:
        with self.assertRaises(SaveLoadError) as ctx:
            self._load_with_tamper(lambda d: d.__setitem__("equipped", {"body": None}))
        self.assertIn("hand", str(ctx.exception))

    def test_missing_body_key_rejected(self) -> None:
        with self.assertRaises(SaveLoadError) as ctx:
            self._load_with_tamper(lambda d: d.__setitem__("equipped", {"hand": None}))
        self.assertIn("body", str(ctx.exception))

    def test_v3_save_rejected(self) -> None:
        self.service.save(self.world)
        txt = self.service.save_path.read_text("utf-8")
        txt = txt.replace('"save_format_version": 8', '"save_format_version": 4')
        self.service.save_path.write_text(txt, "utf-8")
        with self.assertRaises(SaveLoadError) as ctx:
            self.service.load()
        self.assertIn("格式版本", str(ctx.exception))

if __name__ == "__main__":
    unittest.main()
