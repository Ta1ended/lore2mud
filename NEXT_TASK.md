# Next Task

_Last updated: 2026-07-28_

## Start here

- Task: Add a standalone content-pack validation CLI (`lore2mud validate`).
- Why now: save/load is complete; the next step before quest implementation is a
  way to validate content packs without starting the game.

## Inputs

- `PROJECT_MEMORY.md`
- `AGENTS.md`
- `src/lore2mud/content/loader.py`
- `examples/original_demo/`
- `DEC-0001` and `DEC-0003`

## Steps

1. Add a `validate` subcommand to the CLI that loads a content pack and reports
   all validation issues without starting the game loop.
2. Return exit code 0 on success, 1 on validation errors.
3. Test with the demo pack and with intentionally malformed packs.
4. Run the full suite, repository safety check, and compile check.

## Acceptance criteria

- `lore2mud validate --content examples/original_demo` prints "内容包校验通过" and
  exits 0.
- Malformed packs print all issues and exit 1.
- No game loop is started.

## If blocked

- Keep validation behind a standard-library CLI and deliver only the documented
  behavior; do not introduce a database or network.

## Queue

1. Extract and review a private sample of the first 20-50 chapters.
2. Implement one original, deterministic quest flow.
3. Add one usable consumable item.
