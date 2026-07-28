# Next Task

_Last updated: 2026-07-28_

## Start here
- Task: Implement dialogue effects (items, quest triggers from dialogue nodes).
- Why now: dialogue system is complete; adding effects gives NPCs gameplay
  relevance beyond text.

## Inputs
- `PROJECT_MEMORY.md`
- `AGENTS.md`
- `src/lore2mud/engine/world.py`
- `src/lore2mud/engine/commands.py`
- `src/lore2mud/content/loader.py`
- `examples/original_demo/`
- `DEC-0012`

## Steps
1. Define optional effect fields on DialogueNode (grant_item, trigger_quest).
2. Implement effect evaluation in World.select_option.
3. Add effect-related tests.
4. Update content pack format documentation.

## Acceptance criteria
- Dialogue can grant items to player inventory.
- Dialogue can trigger quest auto-accept.
- All effects are deterministic and validated by content loader.
- All tests and safety checks pass.

## If blocked
- Keep effects behind the World domain layer; do not add randomness or network.

## Completed milestones
1. Consumable items (heal_amount). ✅
2. Equipment hand+body (attack_bonus, defense_bonus). ✅
3. Deterministic quest flow. ✅
4. Branching NPC dialogue system. ✅

## Queue
1. Extract and review a private sample of the first 20-50 chapters.
2. Implement dialogue effects (items, quest triggers).
3. Multi-type quest system.
