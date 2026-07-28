"""Tests for the quest system — content loading, gameplay, and commands."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from lore2mud.content.loader import ContentValidationError, load_content_pack
from lore2mud.engine.commands import CommandProcessor
from lore2mud.engine.models import Monster, QuestState
from lore2mud.engine.world import World

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = PROJECT_ROOT / "examples" / "original_demo"


# -- Content loading tests ---------------------------------------------------


class QuestContentLoadingTests(unittest.TestCase):
    """Quest definitions must be validated during content pack loading."""

    def test_demo_loads_with_quest(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        self.assertIn("quest_clear_ash_mite", pack.quests)
        q = pack.quests["quest_clear_ash_mite"]
        self.assertEqual(q.trigger_room_id, "room_ember_wharf")
        self.assertEqual(q.target_monster_id, "monster_ash_mite")
        self.assertEqual(q.reward_experience, 15)

    def test_missing_trigger_room_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            bp = Path(td) / "bad"
            shutil.copytree(DEMO_PATH, bp)
            quests = json.loads((bp / "quests.json").read_text("utf-8"))
            quests[0]["trigger_room_id"] = "room_nonexistent"
            (bp / "quests.json").write_text(
                json.dumps(quests, ensure_ascii=False, indent=2), "utf-8"
            )
            with self.assertRaises(ContentValidationError) as ctx:
                load_content_pack(bp)
            self.assertIn("trigger_room_id", str(ctx.exception))

    def test_missing_target_monster_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            bp = Path(td) / "bad"
            shutil.copytree(DEMO_PATH, bp)
            quests = json.loads((bp / "quests.json").read_text("utf-8"))
            quests[0]["target_monster_id"] = "monster_nonexistent"
            (bp / "quests.json").write_text(
                json.dumps(quests, ensure_ascii=False, indent=2), "utf-8"
            )
            with self.assertRaises(ContentValidationError) as ctx:
                load_content_pack(bp)
            self.assertIn("target_monster_id", str(ctx.exception))

    def test_negative_reward_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            bp = Path(td) / "bad"
            shutil.copytree(DEMO_PATH, bp)
            quests = json.loads((bp / "quests.json").read_text("utf-8"))
            quests[0]["reward_experience"] = -5
            (bp / "quests.json").write_text(
                json.dumps(quests, ensure_ascii=False, indent=2), "utf-8"
            )
            with self.assertRaises(ContentValidationError) as ctx:
                load_content_pack(bp)
            self.assertIn("reward_experience", str(ctx.exception))

    def test_reward_experience_bool_rejected(self) -> None:
        """reward_experience: true must be rejected (bool is not int)."""
        with tempfile.TemporaryDirectory() as td:
            bp = Path(td) / "bad"
            shutil.copytree(DEMO_PATH, bp)
            quests = json.loads((bp / "quests.json").read_text("utf-8"))
            quests[0]["reward_experience"] = True
            (bp / "quests.json").write_text(
                json.dumps(quests, ensure_ascii=False, indent=2), "utf-8"
            )
            with self.assertRaises(ContentValidationError) as ctx:
                load_content_pack(bp)
            self.assertIn("reward_experience", str(ctx.exception))

    def test_unknown_quest_field_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            bp = Path(td) / "bad"
            shutil.copytree(DEMO_PATH, bp)
            quests = json.loads((bp / "quests.json").read_text("utf-8"))
            quests[0]["extra_field"] = True
            (bp / "quests.json").write_text(
                json.dumps(quests, ensure_ascii=False, indent=2), "utf-8"
            )
            with self.assertRaises(ContentValidationError) as ctx:
                load_content_pack(bp)
            self.assertIn("未知字段", str(ctx.exception))

    def test_duplicate_target_monster_rejected(self) -> None:
        """Two quests sharing the same target_monster_id must be rejected."""
        with tempfile.TemporaryDirectory() as td:
            bp = Path(td) / "bad"
            shutil.copytree(DEMO_PATH, bp)
            quests = json.loads((bp / "quests.json").read_text("utf-8"))
            quests.append({
                "id": "quest_clear_ash_mite_copy",
                "name": "清除灰壳兽二号",
                "description": "复制任务。",
                "trigger_room_id": "room_glassgrass_path",
                "target_monster_id": "monster_ash_mite",
                "reward_experience": 10,
            })
            (bp / "quests.json").write_text(
                json.dumps(quests, ensure_ascii=False, indent=2), "utf-8"
            )
            with self.assertRaises(ContentValidationError) as ctx:
                load_content_pack(bp)
            msg = str(ctx.exception)
            self.assertIn("monster_ash_mite", msg)
            self.assertIn("quest_clear_ash_mite", msg)
            self.assertIn("quest_clear_ash_mite_copy", msg)


# -- Auto-accept tests -------------------------------------------------------


class QuestAutoAcceptTests(unittest.TestCase):
    """Quests are auto-accepted based on trigger_room_id."""

    def test_start_room_auto_accepts(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack)
        self.assertIn("quest_clear_ash_mite", world.quest_states)
        self.assertFalse(world.quest_states["quest_clear_ash_mite"].completed)

    def test_move_into_trigger_room_accepts(self) -> None:
        """Moving into a trigger room accepts the quest."""
        pack = load_content_pack(DEMO_PATH)
        # Patch quest to trigger on room_glassgrass_path instead.
        from lore2mud.content.models import QuestDefinition
        q = pack.quests["quest_clear_ash_mite"]
        pack.quests["quest_clear_ash_mite"] = QuestDefinition(
            id=q.id,
            name=q.name,
            description=q.description,
            trigger_room_id="room_glassgrass_path",
            target_monster_id=q.target_monster_id,
            reward_experience=q.reward_experience,
            metadata=q.metadata,
        )
        world = World.from_content_pack(pack)
        self.assertNotIn("quest_clear_ash_mite", world.quest_states)
        world.move("east")  # → room_glassgrass_path (trigger)
        self.assertIn("quest_clear_ash_mite", world.quest_states)
        self.assertFalse(world.quest_states["quest_clear_ash_mite"].completed)

    def test_non_trigger_room_does_not_accept_new(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack)
        del world.quest_states["quest_clear_ash_mite"]
        world.move("east")  # glassgrass — not a trigger room
        self.assertNotIn("quest_clear_ash_mite", world.quest_states)

    def test_look_does_not_change_quest_state(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack)
        del world.quest_states["quest_clear_ash_mite"]
        commands = CommandProcessor(world)
        result = commands.execute("look")
        self.assertIn("余烬渡台", result.text)
        self.assertNotIn("quest_clear_ash_mite", world.quest_states)


# -- Quest completion tests --------------------------------------------------


class QuestCompletionTests(unittest.TestCase):
    """Quest completion via monster defeat."""

    def setUp(self) -> None:
        self.pack = load_content_pack(DEMO_PATH)
        self.world = World.from_content_pack(self.pack)
        self.commands = CommandProcessor(self.world)
        self.commands.execute("go east")
        self.commands.execute("go east")

    def test_defeating_target_completes_quest(self) -> None:
        self.commands.execute("attack monster_ash_mite")
        result = self.commands.execute("attack monster_ash_mite")
        qs = self.world.quest_states["quest_clear_ash_mite"]
        self.assertTrue(qs.completed)
        self.assertIn("任务完成", result.text)
        self.assertIn("清除灰壳兽", result.text)
        self.assertIn("15 经验", result.text)

    def test_quest_grants_reward_experience(self) -> None:
        self.commands.execute("attack monster_ash_mite")
        self.commands.execute("attack monster_ash_mite")
        # Monster 12 + Quest 15 = 27; level 1→2 needs 10; remaining 17
        self.assertEqual(self.world.player.level, 2)
        self.assertEqual(self.world.player.experience, 17)

    def test_reward_only_once(self) -> None:
        """Reset the target monster and defeat it again; quest XP must not
        increase because the quest is already completed."""
        self.commands.execute("attack monster_ash_mite")
        self.commands.execute("attack monster_ash_mite")
        self.assertTrue(self.world.quest_states["quest_clear_ash_mite"].completed)

        xp_after = self.world.player.experience
        level_after = self.world.player.level

        # Respawn the target monster with 0 experience reward.
        self.world.monsters["monster_ash_mite"] = Monster(
            id="monster_ash_mite",
            name="灰壳兽",
            description="重生体",
            max_hp=8,
            attack=3,
            defense=1,
            experience_reward=0,
        )
        self.world.current_room.monster_ids.append("monster_ash_mite")
        self.commands.execute("attack monster_ash_mite")
        self.commands.execute("attack monster_ash_mite")

        # XP must not have increased — quest reward already granted.
        self.assertEqual(self.world.player.experience, xp_after)
        self.assertEqual(self.world.player.level, level_after)

    def test_non_target_monster_does_not_complete(self) -> None:
        self.world.monsters["monster_dummy"] = Monster(
            id="monster_dummy",
            name="假怪物",
            description="测试用",
            max_hp=1,
            attack=1,
            defense=0,
            experience_reward=1,
        )
        self.world.current_room.monster_ids.append("monster_dummy")
        self.commands.execute("attack monster_dummy")
        self.assertFalse(
            self.world.quest_states["quest_clear_ash_mite"].completed
        )


# -- Quest command tests -----------------------------------------------------


class QuestCommandTests(unittest.TestCase):
    """The `quests` command renders quest state correctly."""

    def test_quests_before_completion(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack)
        commands = CommandProcessor(world)
        result = commands.execute("quests")
        self.assertIn("进行中", result.text)
        self.assertIn("清除灰壳兽", result.text)
        self.assertIn("灰壳兽", result.text)
        self.assertIn("15 经验", result.text)
        self.assertNotIn("已领取", result.text)

    def test_quests_after_completion(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack)
        commands = CommandProcessor(world)
        commands.execute("go east")
        commands.execute("go east")
        commands.execute("attack monster_ash_mite")
        commands.execute("attack monster_ash_mite")
        result = commands.execute("quests")
        self.assertIn("已完成", result.text)
        self.assertIn("清除灰壳兽", result.text)
        self.assertIn("已领取", result.text)

    def test_quests_when_none(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack)
        del world.quest_states["quest_clear_ash_mite"]
        commands = CommandProcessor(world)
        result = commands.execute("quests")
        self.assertIn("没有", result.text)

    def test_look_shows_quest_hint(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack)
        commands = CommandProcessor(world)
        result = commands.execute("look")
        self.assertIn("任务提示", result.text)
        self.assertIn("清除灰壳兽", result.text)

    def test_look_hint_disappears_after_completion(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack)
        commands = CommandProcessor(world)
        commands.execute("go east")
        commands.execute("go east")
        commands.execute("attack monster_ash_mite")
        commands.execute("attack monster_ash_mite")
        commands.execute("go west")
        commands.execute("talk character_elder_chen")
        commands.execute("1")
        commands.execute("1")
        commands.execute("2")
        commands.execute("go west")
        result = commands.execute("look")
        self.assertNotIn("任务提示", result.text)

    def test_help_includes_quests(self) -> None:
        pack = load_content_pack(DEMO_PATH)
        world = World.from_content_pack(pack)
        commands = CommandProcessor(world)
        result = commands.execute("help")
        self.assertIn("quests", result.text)


if __name__ == "__main__":
    unittest.main()
