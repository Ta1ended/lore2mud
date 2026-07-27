# Next Task

_Last updated: 2026-07-28_

## Start here

- Task: Add one usable original consumable item.
- Why now: the quest system is complete; the next step before equipment is a
  simple item with a deterministic on-use effect (e.g. heal HP).

## Inputs

- `PROJECT_MEMORY.md`
- `AGENTS.md`
- `src/lore2mud/engine/world.py`
- `src/lore2mud/engine/commands.py`
- `src/lore2mud/inventory/models.py`
- `examples/original_demo/`
- `DEC-0003` and `DEC-0008`

## Steps

1. Define a consumable item in `items.json` with a `use_effect` (e.g. heal).
2. Add a `use <item>` command to `CommandProcessor`.
3. Implement the effect in `World` (deterministic, no randomness).
4. Add the item to a room or as a quest reward.
5. Update save format if item state changes (e.g. consumed flag).
6. Test with the demo pack and with edge cases.
7. Run the full suite, repository safety check, and compile check.

## Acceptance criteria

- `use <item>` command applies a deterministic effect (e.g. restores HP).
- Consumable items are removed from inventory after use.
- Using a non-consumable or不在背包中的物品 reports an error.
- All tests and safety checks pass.

## If blocked

- Keep effects behind the World domain layer; do not add randomness or network.

## Queue

1. Item use and equipment system with deterministic rules.
2. Extract and review a private sample of the first 20-50 chapters.
3. Implement one original, deterministic quest flow (第二个任务).
