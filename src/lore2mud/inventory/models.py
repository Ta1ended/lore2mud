"""Items and player inventory."""
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass(frozen=True, slots=True)
class Item:
    id: str
    name: str
    description: str
    heal_amount: int | None = None
    slot: str | None = None
    attack_bonus: int = 0


@dataclass(slots=True)
class EquippedItems:
    hand: str | None = None


@dataclass(slots=True)
class Inventory:
    capacity: int = 20
    item_ids: list[str] = field(default_factory=list)

    @property
    def can_add(self) -> bool:
        return len(self.item_ids) < self.capacity

    def add(self, item_id: str) -> None:
        if not self.can_add:
            raise ValueError("inventory is full")
        self.item_ids.append(item_id)
