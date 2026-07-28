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
    defense_bonus: int = 0
    stack_limit: int = 1


@dataclass(slots=True)
class ItemStack:
    """Mutable runtime stack used in Room and Inventory."""
    item_id: str
    quantity: int = 1


@dataclass(slots=True)
class EquippedItems:
    hand: str | None = None
    body: str | None = None


@dataclass(slots=True)
class Inventory:
    capacity: int = 20
    stacks: list[ItemStack] = field(default_factory=list)

    @property
    def stack_count(self) -> int:
        return len(self.stacks)

    def find_stack(self, item_id: str) -> ItemStack | None:
        for s in self.stacks:
            if s.item_id == item_id:
                return s
        return None

    def has_item(self, item_id: str) -> bool:
        return self.find_stack(item_id) is not None

    def can_add_stack(
        self, item_id: str, quantity: int, stack_limit: int
    ) -> bool:
        existing = self.find_stack(item_id)
        if existing is not None:
            return existing.quantity + quantity <= stack_limit
        return self.stack_count < self.capacity

    def add_stack(self, item_id: str, quantity: int) -> None:
        existing = self.find_stack(item_id)
        if existing is not None:
            existing.quantity += quantity
        else:
            if self.stack_count >= self.capacity:
                raise ValueError("inventory is full")
            self.stacks.append(ItemStack(item_id=item_id, quantity=quantity))

    def remove_stack(self, item_id: str, quantity: int) -> None:
        existing = self.find_stack(item_id)
        if existing is None:
            raise ValueError(f"item {item_id} not in inventory")
        if existing.quantity < quantity:
            raise ValueError(
                f"insufficient quantity: have {existing.quantity}, need {quantity}"
            )
        if existing.quantity == quantity:
            self.stacks.remove(existing)
        else:
            existing.quantity -= quantity

    @property
    def all_item_ids(self) -> set[str]:
        return {s.item_id for s in self.stacks}
