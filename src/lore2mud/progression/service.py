"""Deterministic progression rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class ProgressingPlayer(Protocol):
    level: int
    experience: int
    max_hp: int
    hp: int | None
    attack: int
    defense: int


@dataclass(frozen=True, slots=True)
class LevelGain:
    new_level: int
    max_hp_gain: int
    attack_gain: int
    defense_gain: int


def experience_to_next_level(level: int) -> int:
    if level < 1:
        raise ValueError("level must be positive")
    return level * 10


def grant_experience(
    player: ProgressingPlayer,
    amount: int,
) -> list[LevelGain]:
    if amount < 0:
        raise ValueError("experience amount cannot be negative")
    player.experience += amount
    gains: list[LevelGain] = []

    while player.experience >= experience_to_next_level(player.level):
        threshold = experience_to_next_level(player.level)
        player.experience -= threshold
        player.level += 1
        player.max_hp += 5
        player.attack += 2
        player.defense += 1
        player.hp = player.max_hp
        gains.append(
            LevelGain(
                new_level=player.level,
                max_hp_gain=5,
                attack_gain=2,
                defense_gain=1,
            )
        )
    return gains
