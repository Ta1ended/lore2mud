# Next Task

_Last updated: 2026-07-28_

## Start here
- Task: Add a second equipment slot (body) with one original armor item and a
  deterministic defense_bonus.
- Why now: the hand slot is complete and verified; extending to body validates the
  multi-slot design.

## Inputs
- `PROJECT_MEMORY.md`
- `AGENTS.md`
- `src/lore2mud/engine/world.py`
- `src/lore2mud/engine/commands.py`
- `src/lore2mud/inventory/models.py`
- `examples/original_demo/`
- `DEC-0003`, `DEC-0008`, `DEC-0009`, `DEC-0010`

## Steps
1. Extend `EquippedItems` with `body: str | None`.
2. Add `defense_bonus: int` field to `ItemDefinition` and `Item`.
3. Add `World.effective_defense` property.
4. Add body-slot validation in loader and save.
5. Add one armor item to the demo content pack.
6. Test: equip body, effective_defense, combat uses it, save round-trip.

## Acceptance criteria
- `equip <item>` places a valid body item and applies defense_bonus.
- `unequip` reverses the bonus.
- `effective_defense` used in combat damage calculation.
- All tests and safety checks pass.

## If blocked
- Keep effects behind the World domain layer; do not add randomness or network.

## Queue
1. Extract and review a private sample of the first 20-50 chapters.
2. Implement one original, deterministic quest flow (第二个任务).
