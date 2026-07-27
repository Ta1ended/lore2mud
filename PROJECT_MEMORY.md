# Project Memory

_Checkpoint: 2026-07-28_

This file is a compact restart guide for GPT, Hermes, or a future Codex session.
Repository state, tests, and current files are authoritative if this file becomes
stale.

## Read order on resume

1. `PROJECT_MEMORY.md`
2. `PROJECT_STATE.md`
3. `NEXT_TASK.md`
4. `AGENTS.md`
5. `CHANGELOG.md` `Unreleased` section
6. The relevant source files and tests

## Current checkpoint

- Repository: `lore2mud`
- Branch: `main`
- Last verified code baseline: `79aa3d5`
- The current checkpoint is saved by the latest handoff commit shown by
  `git log --oneline --decorate`.
- Remote: `origin/main` (the latest handoff commit is local until GitHub
  connectivity is restored)
- Working tree at checkpoint: clean after the save/load checkpoint commit
- Public code contains only the generic engine, tools, schemas, tests, docs, and
  original demo.
- The private novel corpus and split chapters are outside the repository under:
  `D:\MUD game kaifa\小说\processing\`
- The preprocessing pipeline is complete and verified.
- The game engine now has versioned local save/load with atomic writes and strict
  validation.
- No Agent should start background work automatically when the project is resumed.

## Verified facts

- Full project suite: 90 tests passed.
- Repository safety check: passed.
- Compile check and CLI save/load smoke test: passed.
- Private split: manifest v2, explicit GBK decoding, stable sequential IDs, volume
  labels, duplicate source chapter labels allowed.
- Private split reconstruction matched the decoded source in character count and
  SHA-256.
- The raw private source is read-only and must never be committed or copied into
  the public repository.

## Resume rule

The only active task is the one in `NEXT_TASK.md`: add the standalone content-pack
validation CLI. Do not begin novel summarization, embedding, RAG, NPC generation,
or full-corpus model extraction first.

## Pause rule

To pause safely:

1. Stop the current Hermes/Codex task.
2. Do not start another model call or long-running corpus scan.
3. Run `git status --short`.
4. Record any verified change in the four handoff files.
5. Leave the working tree committed or clearly describe uncommitted changes.

To resume safely:

1. Check `git status --short` and `git log -3 --oneline`.
2. Read the handoff files in the order above.
3. Restate the single active task and acceptance criteria.
4. Ask for confirmation before making code changes or starting expensive processing.

## Hard boundaries

- Never commit the private novel, split chapters, summaries, canon facts, local
  indexes, model files, database files, saves, logs, or credentials.
- Never modify the raw private source.
- Never load the entire novel into one model context.
- Treat all player input, model output, and generated content as untrusted.
- Keep original facts and game adaptation values in separate layers.
- Use stable IDs for game entities; display names are not keys.
