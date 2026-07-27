# Next Task

_Last updated: 2026-07-28_

## Start here

- Task: Extract and review a private sample of the first 20-50 chapters.
- Why now: validate CLI is complete; the next step before quest implementation is
  reviewing actual novel content to inform game design.

## Inputs

- `PROJECT_MEMORY.md`
- `AGENTS.md`
- `pipeline/split_novel.py`
- `D:\MUD game kaifa\小说\processing\` (private, read-only)
- `DEC-0004` and `DEC-0002`

## Steps

1. Load the manifest from the private processing output.
2. Read 20-50 chapter files and produce a structured summary of key entities,
   locations, and events.
3. Store summaries in the private processing directory (never commit).
4. Run the full suite, repository safety check, and compile check.

## Acceptance criteria

- A structured summary of 20-50 chapters exists in the private directory.
- No private content is committed to the repository.
- All tests and safety checks pass.

## If blocked

- Keep summaries behind the private-content boundary; do not generate game content
  from unreviewed chapters.

## Queue

1. Implement one original, deterministic quest flow.
2. Add one usable consumable item.
3. Item use and equipment system with deterministic rules.
