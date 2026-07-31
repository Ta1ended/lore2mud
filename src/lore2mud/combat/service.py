"""Small, deterministic combat service without hidden randomness."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class Combatant(Protocol):
    name: str
    hp: int | None
    attack: int
    defense: int

    @property
    def is_alive(self) -> bool: ...


class MonsterCombatant(Combatant, Protocol):
    experience_reward: int


@dataclass(frozen=True, slots=True)
class CombatRound:
    monster_name: str
    damage_to_monster: int
    damage_to_player: int
    monster_defeated: bool
    player_defeated: bool
    experience_reward: int


def calculate_damage(attack: int, defense: int) -> int:
    return max(1, attack - defense)


def resolve_combat_round(
    player: Combatant,
    monster: MonsterCombatant,
    *,
    player_attack: int | None = None,
    player_defense: int | None = None,
) -> CombatRound:
    if not player.is_alive:
        raise ValueError("defeated player cannot attack")
    if not monster.is_alive:
        raise ValueError("defeated monster cannot be attacked")
    assert player.hp is not None
    assert monster.hp is not None

    attack_value = player_attack if player_attack is not None else player.attack
    defense_value = player_defense if player_defense is not None else player.defense
    damage_to_monster = calculate_damage(attack_value, monster.defense)
    monster.hp = max(0, monster.hp - damage_to_monster)

    damage_to_player = 0
    if monster.is_alive:
        damage_to_player = calculate_damage(monster.attack, defense_value)
        player.hp = max(0, player.hp - damage_to_player)

    return CombatRound(
        monster_name=monster.name,
        damage_to_monster=damage_to_monster,
        damage_to_player=damage_to_player,
        monster_defeated=not monster.is_alive,
        player_defeated=not player.is_alive,
        experience_reward=(
            monster.experience_reward if not monster.is_alive else 0
        ),
    )
