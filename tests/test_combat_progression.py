from __future__ import annotations

import unittest

from lore2mud.combat.service import calculate_damage, resolve_combat_round
from lore2mud.engine.models import Monster, Player
from lore2mud.progression.service import grant_experience


class CombatTests(unittest.TestCase):
    def test_damage_is_deterministic_and_has_minimum_one(self) -> None:
        self.assertEqual(calculate_damage(5, 2), 3)
        self.assertEqual(calculate_damage(2, 99), 1)

    def test_living_monster_retaliates(self) -> None:
        player = Player(id="player_test", name="测试者", room_id="room_test")
        monster = Monster(
            id="monster_test",
            name="测试怪物",
            description="",
            max_hp=10,
            attack=3,
            defense=1,
            experience_reward=4,
        )
        result = resolve_combat_round(player, monster)
        self.assertEqual(result.damage_to_monster, 4)
        self.assertEqual(result.damage_to_player, 2)
        self.assertFalse(result.monster_defeated)
        self.assertEqual(monster.hp, 6)
        self.assertEqual(player.hp, 18)


class ProgressionTests(unittest.TestCase):
    def test_experience_can_trigger_multiple_levels(self) -> None:
        player = Player(id="player_test", name="测试者", room_id="room_test")
        gains = grant_experience(player, 35)
        self.assertEqual([gain.new_level for gain in gains], [2, 3])
        self.assertEqual(player.level, 3)
        self.assertEqual(player.experience, 5)
        self.assertEqual(player.max_hp, 30)
        self.assertEqual(player.attack, 9)
        self.assertEqual(player.defense, 3)
        self.assertEqual(player.hp, 30)


if __name__ == "__main__":
    unittest.main()
