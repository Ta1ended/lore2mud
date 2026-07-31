"""Tests for M1: defeat recovery and death gate."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lore2mud.content.loader import load_content_pack
from lore2mud.engine.commands import CommandProcessor
from lore2mud.engine.save import SaveLoadService
from lore2mud.engine.world import RecoverOutcome, World, WorldRuleError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = PROJECT_ROOT / "examples" / "original_demo"


def _make_dead_world() -> World:
    """Create a world where the player is dead (HP=0)."""
    pack = load_content_pack(DEMO_PATH)
    world = World.from_content_pack(pack, player_name="测试旅人")
    # Move to observatory where the monster is
    world.move("east")
    world.move("east")
    # Set HP to 1, then attack to die
    world.player.hp = 1
    world.attack("monster_ash_mite")
    assert world.player.hp == 0
    return world


class RecoverSuccessTests(unittest.TestCase):
    """Test World.recover() when the player is dead."""

    def setUp(self) -> None:
        self.world = _make_dead_world()

    def test_recover_restores_full_hp(self) -> None:
        self.world.recover()
        self.assertEqual(self.world.player.hp, self.world.player.max_hp)

    def test_recover_moves_to_start_room(self) -> None:
        self.world.recover()
        self.assertEqual(self.world.player.room_id, self.world.start_room_id)
        self.assertEqual(self.world.player.room_id, "room_ember_wharf")

    def test_recover_returns_typed_outcome(self) -> None:
        outcome = self.world.recover()
        self.assertIsInstance(outcome, RecoverOutcome)
        self.assertEqual(outcome.start_room_id, "room_ember_wharf")
        self.assertEqual(outcome.room_name, "余烬渡台")
        self.assertEqual(outcome.hp, self.world.player.max_hp)
        self.assertEqual(outcome.max_hp, self.world.player.max_hp)

    def test_recover_preserves_level(self) -> None:
        level_before = self.world.player.level
        self.world.recover()
        self.assertEqual(self.world.player.level, level_before)

    def test_recover_preserves_experience(self) -> None:
        exp_before = self.world.player.experience
        self.world.recover()
        self.assertEqual(self.world.player.experience, exp_before)

    def test_recover_preserves_quests(self) -> None:
        quests_before = {
            k: (v.quest_id, v.completed)
            for k, v in self.world.quest_states.items()
        }
        self.world.recover()
        quests_after = {
            k: (v.quest_id, v.completed)
            for k, v in self.world.quest_states.items()
        }
        self.assertEqual(quests_before, quests_after)

    def test_recover_preserves_inventory(self) -> None:
        inv_before = [s.item_id for s in self.world.player.inventory.stacks]
        self.world.recover()
        self.assertEqual([s.item_id for s in self.world.player.inventory.stacks], inv_before)

    def test_recover_preserves_equipped(self) -> None:
        hand_before = self.world.equipped.hand
        body_before = self.world.equipped.body
        self.world.recover()
        self.assertEqual(self.world.equipped.hand, hand_before)
        self.assertEqual(self.world.equipped.body, body_before)

    def test_recover_preserves_room_items(self) -> None:
        items_before = {
            rid: [s.item_id for s in r.item_stacks] for rid, r in self.world.rooms.items()
        }
        self.world.recover()
        for rid, room in self.world.rooms.items():
            self.assertEqual([s.item_id for s in room.item_stacks], items_before[rid])

    def test_recover_preserves_room_monsters(self) -> None:
        monsters_before = {
            rid: list(r.monster_ids) for rid, r in self.world.rooms.items()
        }
        self.world.recover()
        for rid, room in self.world.rooms.items():
            self.assertEqual(room.monster_ids, monsters_before[rid])

    def test_recover_preserves_monster_hp(self) -> None:
        hp_before = {
            mid: m.hp for mid, m in self.world.monsters.items()
        }
        self.world.recover()
        for mid, monster in self.world.monsters.items():
            self.assertEqual(monster.hp, hp_before[mid])

    def test_recover_clears_active_dialogue(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack, player_name="对话测试")
        # Move to a room with an NPC
        world.move("east")  # room_glassgrass_path has character_elder_chen
        # Start dialogue
        world.start_dialogue("character_elder_chen")
        self.assertIsNotNone(world.active_dialogue)
        # Kill the player
        world.player.hp = 0
        self.assertFalse(world.player.is_alive)
        # Recover should clear dialogue
        world.recover()
        self.assertIsNone(world.active_dialogue)

    def test_recover_then_move_and_attack(self) -> None:
        """After recovery the player can resume normal gameplay."""
        self.world.recover()
        self.world.move("east")
        self.assertEqual(self.world.player.room_id, "room_glassgrass_path")
        self.world.move("east")
        self.world.attack("monster_ash_mite")
        self.assertTrue(self.world.player.hp > 0)


class RecoverFailureTests(unittest.TestCase):
    """Test that alive players cannot recover."""

    def test_full_hp_cannot_recover(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack)
        with self.assertRaises(WorldRuleError) as ctx:
            world.recover()
        self.assertIn("尚未倒下", str(ctx.exception))

    def test_injured_but_alive_cannot_recover(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack)
        world.move("east")
        world.move("east")
        world.attack("monster_ash_mite")  # takes damage
        self.assertTrue(world.player.is_alive)
        with self.assertRaises(WorldRuleError):
            world.recover()

    def test_alive_recover_failure_preserves_room(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack)
        room_before = world.player.room_id
        with self.assertRaises(WorldRuleError):
            world.recover()
        self.assertEqual(world.player.room_id, room_before)

    def test_alive_recover_failure_preserves_hp(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack)
        hp_before = world.player.hp
        with self.assertRaises(WorldRuleError):
            world.recover()
        self.assertEqual(world.player.hp, hp_before)

    def test_alive_recover_failure_preserves_dialogue(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack)
        world.move("east")
        world.start_dialogue("character_elder_chen")
        dlg_before = world.active_dialogue
        with self.assertRaises(WorldRuleError):
            world.recover()
        self.assertEqual(world.active_dialogue, dlg_before)

    def test_alive_recover_failure_preserves_inventory(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack)
        inv_before = [s.item_id for s in world.player.inventory.stacks]
        with self.assertRaises(WorldRuleError):
            world.recover()
        self.assertEqual([s.item_id for s in world.player.inventory.stacks], inv_before)

    def test_alive_recover_failure_preserves_quests(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack)
        qs_before = dict(world.quest_states)
        with self.assertRaises(WorldRuleError):
            world.recover()
        self.assertEqual(dict(world.quest_states), qs_before)


class DeathGateWorldTests(unittest.TestCase):
    """Test that all mutating World methods are gated by _require_alive."""

    def setUp(self) -> None:
        self.world = _make_dead_world()

    def _snapshot(self) -> dict:
        """Capture full mutable state for invariance checks."""
        w = self.world
        return {
            "room_id": w.player.room_id,
            "hp": w.player.hp,
            "level": w.player.level,
            "exp": w.player.experience,
            "inv": [(s.item_id, s.quantity) for s in w.player.inventory.stacks],
            "hand": w.equipped.hand,
            "body": w.equipped.body,
            "dlg": w.active_dialogue,
            "room_items": {
                rid: [(s.item_id, s.quantity) for s in r.item_stacks] for rid, r in w.rooms.items()
            },
            "room_monsters": {
                rid: list(r.monster_ids) for rid, r in w.rooms.items()
            },
            "monster_hp": {mid: m.hp for mid, m in w.monsters.items()},
            "quests": {
                k: (v.quest_id, v.completed)
                for k, v in w.quest_states.items()
            },
        }

    def _assert_unchanged(self, snap: dict) -> None:
        w = self.world
        self.assertEqual(w.player.room_id, snap["room_id"])
        self.assertEqual(w.player.hp, snap["hp"])
        self.assertEqual(w.player.level, snap["level"])
        self.assertEqual(w.player.experience, snap["exp"])
        self.assertEqual([(s.item_id, s.quantity) for s in w.player.inventory.stacks], snap["inv"])
        self.assertEqual(w.equipped.hand, snap["hand"])
        self.assertEqual(w.equipped.body, snap["body"])
        self.assertEqual(w.active_dialogue, snap["dlg"])
        for rid in w.rooms:
            self.assertEqual([(s.item_id, s.quantity) for s in w.rooms[rid].item_stacks], snap["room_items"][rid])
            self.assertEqual(
                w.rooms[rid].monster_ids, snap["room_monsters"][rid]
            )
        for mid in w.monsters:
            self.assertEqual(w.monsters[mid].hp, snap["monster_hp"][mid])
        qs = {
            k: (v.quest_id, v.completed)
            for k, v in w.quest_states.items()
        }
        self.assertEqual(qs, snap["quests"])

    def test_dead_cannot_move(self) -> None:
        snap = self._snapshot()
        with self.assertRaises(WorldRuleError) as ctx:
            self.world.move("west")
        self.assertIn("倒下", str(ctx.exception))
        self._assert_unchanged(snap)

    def test_dead_cannot_take(self) -> None:
        snap = self._snapshot()
        with self.assertRaises(WorldRuleError):
            self.world.take("item_spark_lantern")
        self._assert_unchanged(snap)

    def test_dead_cannot_drop(self) -> None:
        snap = self._snapshot()
        with self.assertRaises(WorldRuleError):
            self.world.drop("nonexistent")
        self._assert_unchanged(snap)

    def test_dead_cannot_use(self) -> None:
        snap = self._snapshot()
        with self.assertRaises(WorldRuleError):
            self.world.use("nonexistent")
        self._assert_unchanged(snap)

    def test_dead_cannot_equip(self) -> None:
        snap = self._snapshot()
        with self.assertRaises(WorldRuleError):
            self.world.equip("nonexistent")
        self._assert_unchanged(snap)

    def test_dead_cannot_unequip(self) -> None:
        snap = self._snapshot()
        with self.assertRaises(WorldRuleError):
            self.world.unequip()
        self._assert_unchanged(snap)

    def test_dead_cannot_attack(self) -> None:
        snap = self._snapshot()
        with self.assertRaises(WorldRuleError):
            self.world.attack("monster_ash_mite")
        self._assert_unchanged(snap)

    def test_dead_cannot_start_dialogue(self) -> None:
        snap = self._snapshot()
        with self.assertRaises(WorldRuleError):
            self.world.start_dialogue("character_elder_chen")
        self._assert_unchanged(snap)

    def test_dead_cannot_select_option(self) -> None:
        snap = self._snapshot()
        with self.assertRaises(WorldRuleError):
            self.world.select_option(1)
        self._assert_unchanged(snap)

    def test_dead_cannot_end_dialogue(self) -> None:
        snap = self._snapshot()
        with self.assertRaises(WorldRuleError):
            self.world.end_dialogue()
        self._assert_unchanged(snap)

    def test_dead_attack_nonexistent_still_dies_first(self) -> None:
        """Death gate fires before monster resolution."""
        with self.assertRaises(WorldRuleError) as ctx:
            self.world.attack("totally_fake_monster")
        self.assertIn("倒下", str(ctx.exception))

    def test_dead_use_nonexistent_still_dies_first(self) -> None:
        """Death gate fires before item resolution."""
        with self.assertRaises(WorldRuleError) as ctx:
            self.world.use("totally_fake_item")
        self.assertIn("倒下", str(ctx.exception))


class DeathGateCommandTests(unittest.TestCase):
    """Test command-layer death gate."""

    def setUp(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(pack, player_name="测试旅人")
        self.commands = CommandProcessor(self.world)
        # Move and die
        self.commands.execute("go east")
        self.commands.execute("go east")
        self.world.player.hp = 1
        self.commands.execute("attack monster_ash_mite")
        assert self.world.player.hp == 0

    def _snapshot(self) -> dict:
        """Capture full mutable state for invariance checks."""
        w = self.world
        return {
            "room_id": w.player.room_id,
            "hp": w.player.hp,
            "level": w.player.level,
            "exp": w.player.experience,
            "inv": [(s.item_id, s.quantity) for s in w.player.inventory.stacks],
            "hand": w.equipped.hand,
            "body": w.equipped.body,
            "dlg": w.active_dialogue,
            "room_items": {
                rid: [(s.item_id, s.quantity) for s in r.item_stacks] for rid, r in w.rooms.items()
            },
            "quests": {
                qid: qs.completed for qid, qs in w.quest_states.items()
            },
        }

    def test_dead_look_still_works(self) -> None:
        result = self.commands.execute("look")
        self.assertIn("静默观测站", result.text)

    def test_dead_inspect_still_works(self) -> None:
        result = self.commands.execute("inspect item_spark_lantern")
        # It may fail if item not in room/inventory, but shouldn't be death-gated
        # The point is it doesn't return the death error
        self.assertNotIn("倒下了。使用 recover", result.text)

    def test_dead_status_still_works(self) -> None:
        result = self.commands.execute("status")
        self.assertIn("生命", result.text)

    def test_dead_inventory_still_works(self) -> None:
        result = self.commands.execute("inventory")
        # Should not be death-gated
        self.assertNotIn("倒下了。使用 recover", result.text)

    def test_dead_quests_still_works(self) -> None:
        result = self.commands.execute("quests")
        self.assertNotIn("倒下了。使用 recover", result.text)

    def test_dead_help_still_works(self) -> None:
        result = self.commands.execute("help")
        self.assertIn("recover", result.text)

    def test_dead_save_still_works(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            service = SaveLoadService(
                load_content_pack(DEMO_PATH), Path(tmpdir)
            )
            cmds = CommandProcessor(self.world, save_service=service)
            result = cmds.execute("save")
            self.assertIn("存档成功", result.text)

    def test_dead_quit_still_works(self) -> None:
        result = self.commands.execute("quit")
        self.assertTrue(result.should_quit)

    def test_dead_go_rejected_by_command_gate(self) -> None:
        result = self.commands.execute("go west")
        self.assertIn("倒下", result.text)

    def test_dead_take_rejected_by_command_gate(self) -> None:
        result = self.commands.execute("take item_spark_lantern")
        self.assertIn("倒下", result.text)

    def test_dead_attack_rejected_by_command_gate(self) -> None:
        result = self.commands.execute("attack monster_ash_mite")
        self.assertIn("倒下", result.text)

    def test_dead_talk_rejected_by_command_gate(self) -> None:
        result = self.commands.execute("talk character_elder_chen")
        self.assertIn("倒下", result.text)

    def test_dead_bare_number_rejected_by_command_gate(self) -> None:
        result = self.commands.execute("1")
        self.assertIn("倒下", result.text)

    def test_dead_bye_rejected_by_command_gate(self) -> None:
        result = self.commands.execute("bye")
        self.assertIn("倒下", result.text)

    def test_dead_bare_number_with_active_dialogue_blocked(self) -> None:
        """Dead + active_dialogue + bare number → _DEAD_ERROR, no _select_option."""
        from lore2mud.engine.models import DialogueState
        from unittest.mock import patch as _patch
        # Set up active dialogue (simulate mid-dialogue death)
        self.world.active_dialogue = DialogueState("dialogue_elder_chen", "node_1")
        before_dialogue = self.world.active_dialogue
        with _patch.object(
            type(self.commands), '_select_option', side_effect=AssertionError("must not call")
        ) as mock_sel:
            result = self.commands.execute("1")
        mock_sel.assert_not_called()
        self.assertIn("倒下了", result.text)
        self.assertEqual(self.world.active_dialogue, before_dialogue)

    def test_dead_bye_with_active_dialogue_blocked(self) -> None:
        """Dead + active_dialogue + bye → _DEAD_ERROR, no _bye."""
        from lore2mud.engine.models import DialogueState
        from unittest.mock import patch as _patch
        self.world.active_dialogue = DialogueState("dialogue_elder_chen", "node_1")
        before_dialogue = self.world.active_dialogue
        with _patch.object(
            type(self.commands), '_bye', side_effect=AssertionError("must not call")
        ) as mock_bye:
            result = self.commands.execute("bye")
        mock_bye.assert_not_called()
        self.assertIn("倒下了", result.text)
        self.assertEqual(self.world.active_dialogue, before_dialogue)

    def test_dead_other_command_with_active_dialogue_blocked(self) -> None:
        """Dead + active_dialogue + disallowed command → state invariant."""
        from lore2mud.engine.models import DialogueState
        self.world.active_dialogue = DialogueState("dialogue_elder_chen", "node_1")
        snapshot = self._snapshot()
        result = self.commands.execute("go west")
        self.assertIn("倒下了", result.text)
        self.assertEqual(self._snapshot(), snapshot)

    def test_dead_bare_number_no_dialogue_returns_dead_error(self) -> None:
        """Dead + no active_dialogue + bare number → _DEAD_ERROR (not unknown command)."""
        self.assertIsNone(self.world.active_dialogue)
        result = self.commands.execute("1")
        self.assertIn("倒下了", result.text)
        self.assertNotIn("未知指令", result.text)

    def test_recover_command_success(self) -> None:
        result = self.commands.execute("recover")
        self.assertIn("余烬渡台", result.text)
        self.assertIn(str(self.world.player.max_hp), result.text)
        self.assertEqual(self.world.player.hp, self.world.player.max_hp)
        self.assertEqual(self.world.player.room_id, "room_ember_wharf")

    def test_recover_command_extra_args(self) -> None:
        result = self.commands.execute("recover extra")
        self.assertIn("用法", result.text)

    def test_combat_defeat_text_mentions_recover(self) -> None:
        """Verify the defeat text includes recover/load hint."""
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack)
        commands = CommandProcessor(world)
        commands.execute("go east")
        commands.execute("go east")
        world.player.hp = 1
        result = commands.execute("attack monster_ash_mite")
        self.assertIn("recover", result.text)
        self.assertIn("load", result.text)


class SaveLoadRecoverTests(unittest.TestCase):
    """Test save/load round-trips with death and recovery."""

    def setUp(self) -> None:
        self.pack = load_content_pack(DEMO_PATH)
        self.tmpdir = tempfile.mkdtemp()
        self.service = SaveLoadService(self.pack, Path(self.tmpdir))

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_dead_save_load_round_trip(self) -> None:
        world = _make_dead_world()
        self.service.save(world)
        loaded = self.service.load()
        self.assertEqual(loaded.player.hp, 0)
        self.assertFalse(loaded.player.is_alive)

    def test_loaded_dead_can_recover(self) -> None:
        world = _make_dead_world()
        self.service.save(world)
        loaded = self.service.load()
        loaded.recover()
        self.assertEqual(loaded.player.hp, loaded.player.max_hp)
        self.assertEqual(loaded.player.room_id, loaded.start_room_id)

    def test_loaded_start_room_id_is_correct(self) -> None:
        world = World.from_content_pack(self.pack)
        self.service.save(world)
        loaded = self.service.load()
        self.assertEqual(loaded.start_room_id, "room_ember_wharf")

    def test_recover_then_save_load_preserves_state(self) -> None:
        world = _make_dead_world()
        world.recover()
        self.service.save(world)
        loaded = self.service.load()
        self.assertEqual(loaded.player.hp, loaded.player.max_hp)
        self.assertEqual(loaded.player.room_id, "room_ember_wharf")
        self.assertIsNone(loaded.active_dialogue)

    def test_save_format_version_unchanged(self) -> None:
        from lore2mud.engine.save import SAVE_FORMAT_VERSION
        self.assertEqual(SAVE_FORMAT_VERSION, 8)

    def test_content_pack_version_is_current(self) -> None:
        self.assertEqual(self.pack.version, "0.10.0")


if __name__ == "__main__":
    unittest.main()
