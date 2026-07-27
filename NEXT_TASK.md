# Next Task

_Last updated: 2026-07-27_

## Start here

- Task: implement a versioned local save/load vertical slice with atomic writes,
  using only `examples/original_demo`.
- Why now: the public engine and private preprocessing pipeline are both verified;
  the playable loop still loses all mutable state on exit.

## Inputs

- `PROJECT_MEMORY.md`
- `AGENTS.md`
- `src/lore2mud/engine/world.py`
- `src/lore2mud/engine/commands.py`
- `src/lore2mud/cli.py`
- `docs/architecture.md`
- `DEC-0001`, `DEC-0003`, and the save/load analysis from the current task

## Steps

1. Define a save schema that includes all mutable player combat attributes, room
   placements, monster HP, inventory, content-pack identity/version, and save format.
2. Add a repository/service boundary and explicit `save`/`load` commands; do not put
   serialization logic in `CommandProcessor`.
3. Test round-trip state after pickup, damage, and level-up; malformed/incompatible
   saves; unchanged state after failed loads; atomic replacement and CLI behavior.
4. Run the full suite, repository safety check, compile check, and a CLI smoke test.

## Acceptance criteria

- A user can save after taking an item, damaging a monster, and leveling up, then
  restore the exact player stats, room state, inventory, and monster HP.
- Failed or incompatible loads leave the current World and CommandProcessor state
  unchanged.
- Writes use a same-directory temporary file plus atomic replacement and leave no
  temporary artifact.
- No pipeline code, novel file, or private processing output is modified.

## If blocked

- Keep persistence behind a standard-library service/protocol and deliver only the
  documented save schema plus deterministic tests; do not add a database or network.

## Queue

1. Add a standalone content-pack validation CLI.
2. Extract and review a private sample of the first 20-50 chapters.
3. Implement one original, deterministic quest flow.
