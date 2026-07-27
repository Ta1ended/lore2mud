# Next Task

_Last updated: 2026-07-27_

## Start here

- Task: implement a versioned local save/load vertical slice with atomic writes.
- Why now: the current playable loop loses all mutable state on exit, and persistence
  is the next prerequisite before adding more game systems.

## Inputs

- `AGENTS.md`
- `src/lore2mud/engine/world.py`
- `src/lore2mud/cli.py`
- `docs/architecture.md`
- `DEC-0001` and `DEC-0003`

## Steps

1. Specify a minimal save schema for player, room placements, monster health and a
   content-pack identity/version check.
2. Add a repository/service boundary and `save`/`load` CLI behavior without placing
   serialization in `CommandProcessor`.
3. Test round-trip state, malformed saves, mismatched content packs and interrupted
   writes; then run the full suite, safety check and CLI smoke test.

## Acceptance criteria

- A user can save after taking the demo item and damaging the monster, restart the
  process, load the save, and observe exactly the same authoritative state.
- Failed or incompatible loads leave the current world unchanged.
- Writes use a temporary file plus atomic replacement, and saves remain ignored by Git.

## If blocked

- Keep persistence behind a protocol and deliver only the documented save schema plus
  deterministic round-trip tests; do not introduce a database or third-party package.

## Queue

1. Add one usable consumable item.
2. Add a standalone content-pack validation CLI.
3. Implement one original, deterministic quest flow.
