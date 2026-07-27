# Next Task

_Last updated: 2026-07-28_

## Start here
- Task: Add one equipment slot (hand) with one original equipment item that
  provides a deterministic attack bonus.
- Why now: consumable items are complete; the next step is a single equippable
  item that modifies one player stat while worn.

## Inputs
- `PROJECT_MEMORY.md`
- `AGENTS.md`
- `src/lore2mud/engine/world.py`
- `src/lore2mud/engine/commands.py`
- `src/lore2mud/inventory/models.py`
- `examples/original_demo/`
- `DEC-0003`, `DEC-0008`, `DEC-0009`

## Steps
1. Add `slot: str | None` and `attack_bonus: int` fields to `ItemDefinition` and `Item`.
2. Add `EquippedItems` model with a single `hand` slot to `inventory/models.py`.
3. Add `equip <item>` and `unequip` commands to `CommandProcessor`.
4. Add `equip`/`unequip` logic to `World` with stat bonus application/removal.
5. Add one equipment item (e.g. `item_crystal_blade`, attack_bonus=3) to the demo.
6. Update save/load to serialize equipped state.
7. Test: equip applies bonus, unequip reverses, equipped item cannot be used as
   consumable, save round-trip preserves equipped state.

## Acceptance criteria
- `equip <item>` places a valid item in the hand slot and applies attack_bonus.
- `unequip` removes the item and reverses the bonus.
- Equipped items cannot be used as consumables.
- All tests and safety checks pass.

## If blocked
- Keep effects behind the World domain layer; do not add randomness or network.

## Queue
1. Extract and review a private sample of the first 20-50 chapters.
2. Implement one original, deterministic quest flow (第二个任务).
