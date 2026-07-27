# Next Task

_Last updated: 2026-07-28_

## Start here
- Task: Implement dialogue system with one NPC and branching responses.
- Why now: equipment and combat are complete; dialogue adds narrative depth.

## Inputs
- `PROJECT_MEMORY.md`
- `AGENTS.md`
- `src/lore2mud/engine/world.py`
- `src/lore2mud/engine/commands.py`
- `src/lore2mud/content/loader.py`
- `examples/original_demo/`
- `DEC-0003`, `DEC-0008`, `DEC-0009`, `DEC-0010`, `DEC-0011`

## Steps
1. Define dialogue node structure in content models.
2. Add `talk <character>` command to CommandProcessor.
3. Implement dialogue traversal in World.
4. Add one NPC with branching dialogue to demo.
5. Test dialogue flow and edge cases.

## Acceptance criteria
- `talk <character>` displays dialogue and accepts player responses.
- Dialogue nodes support branching.
- All tests and safety checks pass.

## If blocked
- Keep effects behind the World domain layer; do not add randomness or network.

## Queue
1. Extract and review a private sample of the first 20-50 chapters.
2. Implement one original, deterministic quest flow (第二个任务).
