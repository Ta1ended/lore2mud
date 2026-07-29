"""Focused M5 contracts for immutable fixed-catalog shops and coins."""

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
    CollectItemQuestDefinition,
    ShopDefinition,
    ShopListingDefinition,
)
from lore2mud.engine.commands import CommandProcessor
from lore2mud.engine.models import QuestState
from lore2mud.engine.save import SaveLoadService, _serialize_world
from lore2mud.engine.world import BuyOutcome, SellOutcome, ShopOutcome, World, WorldRuleError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = PROJECT_ROOT / "examples" / "original_demo"


def _world_at_shop() -> World:
    world = World.from_content_pack(load_content_pack(DEMO_PATH))
    world.move("east")
    return world


def _mutable_state(world: World) -> tuple[object, ...]:
    return (
        world.player.room_id,
        world.player.coins,
        world.player.level,
        world.player.experience,
        tuple((stack.item_id, stack.quantity) for stack in world.player.inventory.stacks),
        tuple(
            (quest_id, state.completed)
            for quest_id, state in sorted(world.quest_states.items())
        ),
        tuple(sorted(world.flags.items())),
        world.equipped.hand,
        world.equipped.body,
        world.active_dialogue,
    )


class ShopContentTests(unittest.TestCase):
    def _with_pack(self, mutate: object, *, should_fail: bool = True) -> object:
        with tempfile.TemporaryDirectory() as td:
            pack_path = Path(td) / "pack"
            shutil.copytree(DEMO_PATH, pack_path)
            mutate(pack_path)  # type: ignore[operator]
            if should_fail:
                with self.assertRaises(ContentValidationError):
                    load_content_pack(pack_path)
                return None
            return load_content_pack(pack_path)

    def test_frozen_shop_definitions_and_player_coins_load(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        shop = pack.shops["shop_chen_travel_goods"]
        listing = shop.catalog[0]
        self.assertEqual(pack.player.coins, 20)
        self.assertEqual((shop.room_id, listing.item_id, listing.buy_price, listing.sell_price), (
            "room_glassgrass_path", "item_linglu_pill", 4, 2
        ))
        with self.assertRaises(FrozenInstanceError):
            shop.name = "changed"  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            listing.buy_price = 99  # type: ignore[misc]

    def test_shops_file_is_required_and_empty_array_is_valid(self) -> None:
        self._with_pack(lambda root: (root / "shops.json").unlink())
        pack = self._with_pack(
            lambda root: (root / "shops.json").write_text("[]", "utf-8"),
            should_fail=False,
        )
        self.assertEqual(pack.shops, {})  # type: ignore[attr-defined]

    def test_shop_loader_rejects_exact_shape_references_duplicates_and_prices(self) -> None:
        mutations = (
            lambda shops: shops[0].update(extra=True),
            lambda shops: shops[0].update(room_id="room_missing"),
            lambda shops: shops[0]["catalog"][0].update(item_id="item_missing"),
            lambda shops: shops[0].update(catalog=[]),
            lambda shops: shops[0].update(
                catalog=shops[0]["catalog"] * 2
            ),
            lambda shops: shops.append(dict(shops[0], id="shop_other")),
            lambda shops: shops[0]["catalog"][0].update(buy_price=True),
            lambda shops: shops[0]["catalog"][0].update(sell_price=0),
            lambda shops: shops[0]["catalog"][0].update(buy_price=2, sell_price=3),
            lambda shops: shops[0]["catalog"][0].update(item_id="item_chen_token"),
        )
        for mutate_shops in mutations:
            with self.subTest(mutation=mutate_shops):
                self._with_pack(
                    lambda root, mutate_shops=mutate_shops: (
                        (lambda shops: (
                            mutate_shops(shops),
                            (root / "shops.json").write_text(
                                json.dumps(shops, ensure_ascii=False), "utf-8"
                            ),
                        ))(json.loads((root / "shops.json").read_text("utf-8")))
                    )
                )

    def test_pack_coins_are_required_nonnegative_integers(self) -> None:
        for value in (None, -1, True, "20"):
            with self.subTest(value=value):
                def mutate(root: Path, value: object = value) -> None:
                    data = json.loads((root / "pack.json").read_text("utf-8"))
                    if value is None:
                        del data["player"]["coins"]
                    else:
                        data["player"]["coins"] = value
                    (root / "pack.json").write_text(
                        json.dumps(data, ensure_ascii=False), "utf-8"
                    )

                self._with_pack(mutate)


class ShopWorldTests(unittest.TestCase):
    def test_shop_view_is_read_only_and_catalog_order_is_preserved(self) -> None:
        world = _world_at_shop()
        before = _mutable_state(world)

        outcome = world.shop()

        self.assertIsInstance(outcome, ShopOutcome)
        self.assertEqual(outcome.shop_id, "shop_chen_travel_goods")
        self.assertEqual(tuple(listing.item_id for listing in outcome.catalog), ("item_linglu_pill",))
        self.assertEqual(outcome.coins, 20)
        self.assertEqual(_mutable_state(world), before)

    def test_default_and_multiple_buy_sell_keep_catalog_immutable(self) -> None:
        world = _world_at_shop()
        catalog_before = world.shop_defs["shop_chen_travel_goods"].catalog

        first = world.buy("item_linglu_pill")
        second = world.buy("灵露丸", 2)
        third = world.sell("item_linglu_pill")
        fourth = world.sell("灵露丸", 2)

        self.assertIsInstance(first, BuyOutcome)
        self.assertIsInstance(third, SellOutcome)
        self.assertEqual((first.quantity, first.total_price, first.coins), (1, 4, 16))
        self.assertEqual((second.quantity, second.total_price, second.coins), (2, 8, 8))
        self.assertEqual((third.quantity, third.total_price, third.coins), (1, 2, 10))
        self.assertEqual((fourth.quantity, fourth.total_price, fourth.coins), (2, 4, 14))
        self.assertIsNone(world.player.inventory.find_stack("item_linglu_pill"))
        self.assertEqual(world.shop_defs["shop_chen_travel_goods"].catalog, catalog_before)

    def test_buy_sell_failures_leave_the_world_unchanged(self) -> None:
        no_shop = World.from_content_pack(load_content_pack(DEMO_PATH))
        before = _mutable_state(no_shop)
        with self.assertRaises(WorldRuleError):
            no_shop.buy("item_linglu_pill")
        self.assertEqual(_mutable_state(no_shop), before)

        cases: list[tuple[str, object]] = []
        insufficient = _world_at_shop()
        insufficient.player.coins = 0
        cases.append(("insufficient", insufficient))
        full = _world_at_shop()
        full.player.inventory.capacity = 0
        cases.append(("full", full))
        overflow = _world_at_shop()
        overflow.player.inventory.add_stack("item_linglu_pill", 5)
        cases.append(("overflow", overflow))
        unavailable = _world_at_shop()
        cases.append(("unavailable", unavailable))

        for label, world in cases:
            with self.subTest(label=label):
                before = _mutable_state(world)  # type: ignore[arg-type]
                with self.assertRaises(WorldRuleError):
                    if label == "unavailable":
                        world.buy("item_spark_lantern")  # type: ignore[union-attr]
                    elif label == "overflow":
                        world.buy("item_linglu_pill")  # type: ignore[union-attr]
                    else:
                        world.buy("item_linglu_pill")  # type: ignore[union-attr]
                self.assertEqual(_mutable_state(world), before)  # type: ignore[arg-type]

        seller = _world_at_shop()
        before = _mutable_state(seller)
        with self.assertRaises(WorldRuleError):
            seller.sell("item_linglu_pill")
        self.assertEqual(_mutable_state(seller), before)

    def test_new_stack_buy_above_stack_limit_rejects_before_mutation(self) -> None:
        world = _world_at_shop()
        world.player.coins = 26
        before = _mutable_state(world)

        with self.assertRaisesRegex(WorldRuleError, r"超过栈上限 \(5\)"):
            world.buy("item_linglu_pill", 6)
        self.assertEqual(_mutable_state(world), before)
        self.assertIsNone(world.player.inventory.find_stack("item_linglu_pill"))

        result = CommandProcessor(world).execute("buy item_linglu_pill 6")
        self.assertIn("超过栈上限 (5)", result.text)
        self.assertEqual(_mutable_state(world), before)

    def test_equipped_sell_and_nonstackable_duplicate_generation_are_rejected(self) -> None:
        equipped = World.from_content_pack(load_content_pack(DEMO_PATH))
        equipped.take("item_crystal_blade")
        equipped.move("east")
        equipped.shop_defs = {
            "shop_equipment": ShopDefinition(
                id="shop_equipment",
                name="装备商",
                room_id="room_glassgrass_path",
                catalog=(ShopListingDefinition("item_crystal_blade", 4, 2),),
            )
        }
        equipped.equip("item_crystal_blade")
        before = _mutable_state(equipped)
        with self.assertRaises(WorldRuleError):
            equipped.sell("item_crystal_blade")
        self.assertEqual(_mutable_state(equipped), before)

        unique = _world_at_shop()
        unique.shop_defs = {
            "shop_token": ShopDefinition(
                id="shop_token",
                name="铜牌商",
                room_id="room_glassgrass_path",
                catalog=(ShopListingDefinition("item_chen_token", 4, 2),),
            )
        }
        unique.buy("item_chen_token")
        before = _mutable_state(unique)
        with self.assertRaises(WorldRuleError):
            unique.buy("item_chen_token")
        self.assertEqual(_mutable_state(unique), before)

    def test_buy_settles_collect_tasks_and_reward_failure_rolls_back_coins_and_item(self) -> None:
        world = _world_at_shop()
        quest = CollectItemQuestDefinition(
            id="quest_buy_pill",
            name="商店购药",
            description="从商店购买一枚灵露丸。",
            trigger_room_id="room_ember_wharf",
            target_item_id="item_linglu_pill",
            required_quantity=1,
            reward_experience=5,
        )
        world.quest_defs[quest.id] = quest
        world.quest_states[quest.id] = QuestState(quest.id)
        outcome = world.buy("item_linglu_pill")
        self.assertEqual(tuple(item.quest_id for item in outcome.quest_outcomes), (quest.id,))
        self.assertTrue(world.quest_states[quest.id].completed)

        rollback = _world_at_shop()
        rollback.quest_defs[quest.id] = quest
        rollback.quest_states[quest.id] = QuestState(quest.id)
        before = _mutable_state(rollback)
        with patch(
            "lore2mud.engine.world.grant_experience",
            side_effect=RuntimeError("quest reward failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "quest reward failure"):
                rollback.buy("item_linglu_pill")
        self.assertEqual(_mutable_state(rollback), before)

    def test_selling_does_not_revoke_completed_collect_task_or_end_dialogue(self) -> None:
        world = _world_at_shop()
        quest = CollectItemQuestDefinition(
            id="quest_sell_pill",
            name="售后任务",
            description="完成后出售物品。",
            trigger_room_id="room_ember_wharf",
            target_item_id="item_linglu_pill",
            required_quantity=1,
            reward_experience=0,
        )
        world.quest_defs[quest.id] = quest
        world.quest_states[quest.id] = QuestState(quest.id)
        world.start_dialogue("character_elder_chen")
        dialogue_before = world.active_dialogue
        world.buy("item_linglu_pill")
        self.assertTrue(world.quest_states[quest.id].completed)
        self.assertEqual(world.active_dialogue, dialogue_before)
        world.player.coins = 0
        with self.assertRaises(WorldRuleError):
            world.buy("item_linglu_pill")
        self.assertEqual(world.active_dialogue, dialogue_before)
        world.sell("item_linglu_pill")
        self.assertTrue(world.quest_states[quest.id].completed)
        self.assertEqual(world.active_dialogue, dialogue_before)

    def test_dead_player_may_view_shop_but_cannot_trade(self) -> None:
        world = _world_at_shop()
        world.player.hp = 0
        commands = CommandProcessor(world)
        before = _mutable_state(world)
        self.assertIn("陈伯的行囊", commands.execute("shop").text)
        self.assertIn("倒下了", commands.execute("buy item_linglu_pill").text)
        self.assertIn("倒下了", commands.execute("sell item_linglu_pill").text)
        self.assertEqual(_mutable_state(world), before)


class ShopCommandAndSaveTests(unittest.TestCase):
    def test_commands_look_help_status_and_fixed_catalog_survive_load(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack)
        world.move("east")
        commands = CommandProcessor(world)
        self.assertIn("shop", commands.execute("help").text)
        self.assertIn("陈伯的行囊", commands.execute("look").text)
        self.assertIn("shop_chen_travel_goods", commands.execute("look").text)
        self.assertIn("金币：20", commands.execute("shop").text)
        self.assertIn("flags：无", commands.execute("status").text)
        self.assertIn("购买了 灵露丸", commands.execute("buy 灵露丸").text)
        self.assertIn("出售了 灵露丸", commands.execute("sell 灵露丸").text)

        with tempfile.TemporaryDirectory() as td:
            service = SaveLoadService(pack, Path(td))
            service.save(world)
            data = json.loads(service.save_path.read_text("utf-8"))
            self.assertNotIn("shops", data)
            loaded = service.load()
            self.assertEqual(loaded.shop().shop_id, "shop_chen_travel_goods")
            self.assertEqual(loaded.player.coins, world.player.coins)


if __name__ == "__main__":
    unittest.main()
