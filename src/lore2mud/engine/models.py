"""Mutable runtime models owned by the authoritative game world."""

from __future__ import annotations

from dataclasses import dataclass, field

from lore2mud.inventory.models import Inventory


@dataclass(slots=True)
class Room:
    id: str
    name: str
    description: str
    exits: dict[str, str] = field(default_factory=dict)
    item_ids: list[str] = field(default_factory=list)
    monster_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Monster:
    id: str
    name: str
    description: str
    max_hp: int
    attack: int
    defense: int
    experience_reward: int
    hp: int | None = None

    def __post_init__(self) -> None:
        if self.hp is None:
            self.hp = self.max_hp

    @property
    def is_alive(self) -> bool:
        return bool(self.hp and self.hp > 0)


@dataclass(slots=True)
class Player:
    id: str
    name: str
    room_id: str
    max_hp: int = 20
    attack: int = 5
    defense: int = 1
    level: int = 1
    experience: int = 0
    hp: int | None = None
    inventory: Inventory = field(default_factory=Inventory)

    def __post_init__(self) -> None:
        if self.hp is None:
            self.hp = self.max_hp

    @property
    def is_alive(self) -> bool:
        return bool(self.hp and self.hp > 0)
