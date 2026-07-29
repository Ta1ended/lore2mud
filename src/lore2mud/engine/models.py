"""Mutable runtime models owned by the authoritative game world."""

from __future__ import annotations

from dataclasses import dataclass, field
from lore2mud.content.models import ExitDefinition, ItemStackDefinition
from lore2mud.inventory.models import Inventory, ItemStack


@dataclass(slots=True)
class Room:
    id: str
    name: str
    description: str
    exits: dict[str, ExitDefinition] = field(default_factory=dict)
    item_stacks: list[ItemStack] = field(default_factory=list)
    monster_ids: list[str] = field(default_factory=list)

    def find_stack(self, item_id: str) -> ItemStack | None:
        for s in self.item_stacks:
            if s.item_id == item_id:
                return s
        return None


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
    loot_item: ItemStackDefinition | None = None

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
    coins: int = 0
    hp: int | None = None
    inventory: Inventory = field(default_factory=Inventory)

    def __post_init__(self) -> None:
        if self.hp is None:
            self.hp = self.max_hp

    @property
    def is_alive(self) -> bool:
        return bool(self.hp and self.hp > 0)


@dataclass(slots=True)
class QuestState:
    """Mutable quest state for one accepted quest.

    Presence in World.quest_states means the quest has been accepted.
    ``completed=True`` means the reward has already been granted.
    """

    quest_id: str
    completed: bool = False


@dataclass(slots=True)
class Character:
    """Runtime character in the world."""
    id: str
    name: str
    description: str
    room_id: str


@dataclass(slots=True)
class DialogueState:
    """Mutable dialogue state for one active conversation."""
    dialogue_id: str
    current_node_id: str
