"""Tests for the consumable item system — content loading, use command,
edge cases, and save round-trip."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from lore2mud.content.loader import ContentValidationError, load_content_pack
from lore2mud.engine.commands import CommandProcessor
from lore2mud.engine.models import Monster
from lore2mud.engine.save import SaveLoadService, _serialize_world
from lore2mud.engine.world import World, WorldRuleError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = PROJECT_ROOT / "examples" / "original_demo"


# -- Content loading tests ---------------------------------------------------


class ConsumableContentLoadingTests(unittest.TestCase):
    """Consumable items must be validated during content pack loading."""

    def test_demo_loads_with_pill(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        self.assertIn("item_linglu_pill", pack.items)
        pill = pack.items["item_linglu_pill"]
        self.assertEqual(pill.heal_amount, 10)

    def test_spark_lantern_has_no_heal(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        lantern = pack.items["item_spark_lantern"]
        self.assertIsNone(lantern.heal_amount)

    def test_heal_amount_zero_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            bp = Path(td) / "bad"
            shutil.copytree(DEMO_PATH, bp)
            items = json.loads((bp / "items.json").read_text("utf-8"))
            items[1]["heal_amount"] = 0
            (bp / "items.json").write_text(
                json.dumps(items, ensure_ascii=False, indent=2), "utf-8"
            )
            with self.assertRaises(ContentValidationError) as ctx:
                load_content_pack(bp)
            self.assertIn("heal_amount", str(ctx.exception))

    def test_heal_amount_bool_rejected(self) -> None:
        """heal_amount: true must be rejected (bool is not int)."""
        with tempfile.TemporaryDirectory() as td:
            bp = Path(td) / "bad"
            shutil.copytree(DEMO_PATH, bp)
            items = json.loads((bp / "items.json").read_text("utf-8"))
            items[1]["heal_amount"] = True
            (bp / "items.json").write_text(
                json.dumps(items, ensure_ascii=False, indent=2), "utf-8"
            )
            with self.assertRaises(ContentValidationError) as ctx:
                load_content_pack(bp)
            self.assertIn("heal_amount", str(ctx.exception))

    def test_heal_amount_null_rejected(self) -> None:
        """heal_amount: null must be rejected."""
        with tempfile.TemporaryDirectory() as td:
            bp = Path(td) / "bad"
            shutil.copytree(DEMO_PATH, bp)
            items = json.loads((bp / "items.json").read_text("utf-8"))
            items[1]["heal_amount"] = None
            (bp / "items.json").write_text(
                json.dumps(items, ensure_ascii=False, indent=2), "utf-8"
            )
            with self.assertRaises(ContentValidationError) as ctx:
                load_content_pack(bp)
            self.assertIn("heal_amount", str(ctx.exception))


# -- Normal use tests --------------------------------------------------------


class ConsumableUseTests(unittest.TestCase):
    """Using a consumable heals the player and removes the item."""

    def setUp(self) -> None:
        self.pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(self.pack, player_name="测试旅人")
        self.commands = CommandProcessor(self.world)
        # Pick up the pill.
        self.commands.execute("take item_linglu_pill")

    def test_use_heals_and_removes_item(self) -> None:
        # Take damage first.
        self.commands.execute("go east")
        self.commands.execute("go east")
        self.commands.execute("attack monster_ash_mite")
        hp_before = self.world.player.hp
        self.assertLess(hp_before, self.world.player.max_hp)

        result = self.commands.execute("use item_linglu_pill")
        self.assertIn("恢复了", result.text)
        self.assertIn("灵露丸", result.text)
        self.assertNotIn("item_linglu_pill", self.world.player.inventory.item_ids)
        self.assertGreater(self.world.player.hp, hp_before)

    def test_use_partial_heal(self) -> None:
        """When missing HP < heal_amount, only restore the difference."""
        self.commands.execute("go east")
        self.commands.execute("go east")
        self.commands.execute("attack monster_ash_mite")
        # Player HP is 18 (max 20), missing 2. heal_amount=10, actual=2.
        result = self.commands.execute("use item_linglu_pill")
        self.assertIn("恢复了 2 点生命", result.text)
        self.assertEqual(self.world.player.hp, self.world.player.max_hp)

    def test_help_includes_use(self) -> None:
        result = self.commands.execute("help")
        self.assertIn("use", result.text)


# -- Failure path tests ------------------------------------------------------


class ConsumableFailureTests(unittest.TestCase):
    """All failure paths leave HP and inventory unchanged."""

    def setUp(self) -> None:
        self.pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(self.pack, player_name="测试旅人")
        self.commands = CommandProcessor(self.world)
        self.commands.execute("take item_linglu_pill")

    def _assert_state_unchanged(self) -> None:
        """Assert HP and inventory are unchanged."""
        # Inventory should still have the pill.
        self.assertIn("item_linglu_pill", self.world.player.inventory.item_ids)

    def test_use_non_usable_item(self) -> None:
        """item_spark_lantern has no heal_amount — cannot use."""
        self.commands.execute("take item_spark_lantern")
        hp_before = self.world.player.hp
        inv_before = list(self.world.player.inventory.item_ids)
        result = self.commands.execute("use item_spark_lantern")
        self.assertIn("无法使用", result.text)
        self.assertEqual(self.world.player.hp, hp_before)
        self.assertEqual(self.world.player.inventory.item_ids, inv_before)

    def test_use_item_not_in_inventory(self) -> None:
        hp_before = self.world.player.hp
        inv_before = list(self.world.player.inventory.item_ids)
        result = self.commands.execute("use nonexistent")
        self.assertIn("没有", result.text)
        self.assertEqual(self.world.player.hp, hp_before)
        self.assertEqual(self.world.player.inventory.item_ids, inv_before)

    def test_use_at_full_hp(self) -> None:
        hp_before = self.world.player.hp
        result = self.commands.execute("use item_linglu_pill")
        self.assertIn("满血", result.text)
        self.assertEqual(self.world.player.hp, hp_before)
        # Item must NOT be consumed.
        self.assertIn("item_linglu_pill", self.world.player.inventory.item_ids)

    def test_use_empty_args(self) -> None:
        result = self.commands.execute("use")
        self.assertIn("用法", result.text)

    def test_use_by_display_name(self) -> None:
        """Use the item by its display name '灵露丸' instead of ID."""
        # Take damage so use is valid.
        self.commands.execute("go east")
        self.commands.execute("go east")
        self.commands.execute("attack monster_ash_mite")
        hp_before = self.world.player.hp
        self.assertLess(hp_before, self.world.player.max_hp)

        result = self.commands.execute("use 灵露丸")
        self.assertIn("恢复了", result.text)
        self.assertNotIn("item_linglu_pill", self.world.player.inventory.item_ids)
        self.assertGreater(self.world.player.hp, hp_before)

    def test_use_dead_player(self) -> None:
        """HP=0 player cannot use consumable."""
        self.world.player.hp = 0
        inv_before = list(self.world.player.inventory.item_ids)
        result = self.commands.execute("use item_linglu_pill")
        self.assertIn("倒下", result.text)
        self.assertEqual(self.world.player.hp, 0)
        self.assertEqual(self.world.player.inventory.item_ids, inv_before)


# -- Save round-trip tests ---------------------------------------------------


class ConsumableSaveRoundTripTests(unittest.TestCase):
    """Consumable state survives save/load."""

    def setUp(self) -> None:
        self.pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(self.pack, player_name="测试旅人")
        self.tmpdir = tempfile.mkdtemp()
        self.service = SaveLoadService(self.pack, Path(self.tmpdir))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_pill_heal_amount_survives_load(self) -> None:
        """After load, the pill item must retain heal_amount."""
        self.service.save(self.world)
        loaded = self.service.load()
        pill = loaded.items["item_linglu_pill"]
        self.assertEqual(pill.heal_amount, 10)

    def test_use_after_damage_and_reload(self) -> None:
        """Injure → save → load → use: the pill still heals."""
        self.world.take("item_linglu_pill")
        self.world.move("east")
        self.world.move("east")
        self.world.attack("monster_ash_mite")
        self.assertLess(self.world.player.hp, self.world.player.max_hp)

        self.service.save(self.world)
        loaded = self.service.load()
        commands = CommandProcessor(loaded)

        result = commands.execute("use item_linglu_pill")
        self.assertIn("恢复了", result.text)
        self.assertNotIn(
            "item_linglu_pill", loaded.player.inventory.item_ids
        )

    def test_used_pill_gone_after_reload(self) -> None:
        """Use pill → save → load: pill must not reappear."""
        self.world.take("item_linglu_pill")
        self.world.move("east")
        self.world.move("east")
        self.world.attack("monster_ash_mite")
        self.world.use("item_linglu_pill")

        self.service.save(self.world)
        loaded = self.service.load()
        self.assertNotIn("item_linglu_pill", loaded.player.inventory.item_ids)

    def test_old_version_save_rejected(self) -> None:
        """A save from pack version 0.2.6 must be rejected by 0.2.7."""
        self.service.save(self.world)
        # Tamper the version in the save file.
        save_text = self.service.save_path.read_text("utf-8")
        save_text = save_text.replace('"version": "0.2.7"', '"version": "0.2.6"')
        self.service.save_path.write_text(save_text, "utf-8")
        from lore2mud.engine.save import SaveLoadError
        with self.assertRaises(SaveLoadError) as ctx:
            self.service.load()
        self.assertIn("版本", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
