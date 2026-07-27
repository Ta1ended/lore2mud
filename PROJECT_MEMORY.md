# Project Memory

_Checkpoint ref: HEAD — 恢复时运行 `git rev-parse HEAD` 获取当前提交。_

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
- Remote: origin/main；恢复时运行 `git status --short --branch` 和
  `git rev-list --left-right --count HEAD...origin/main` 检查同步状态。
- Working tree: clean
- 功能状态：消耗品系统 + 装备系统已完成（heal_amount/use + slot/equip/unequip +
  effective_attack/save v3）
- Public code contains only the generic engine, tools, schemas, tests, docs, and
  original demo.
- The private novel corpus and split chapters are outside the repository under:
  `D:\MUD game kaifa\小说\processing\`
- The preprocessing pipeline is complete and verified.
- No Agent should start background work automatically when the project is resumed.

## Verified facts

- Full project suite: 209 tests passed (2026-07-28).
- Repository safety check: passed.
- Compile check and CLI save/load smoke test: passed.
- CLI validate smoke test: passed.
- CLI play smoke test with quests, consumables, and equipment: passed.
- Quest system: auto-accept, completion, reward-once, save round-trip: passed.
- Consumable system: heal_amount field, use command, full HP / dead / non-usable
  rejection, heal_amount: null rejection, save round-trip: passed.
- Equipment system: slot/attack_bonus, equip/unequip, effective_attack, equipped
  validation, combat integration, upgrade interaction, save v3 round-trip: passed.
- Content pack version: 0.2.2 (old 0.2.1 saves cleanly rejected).
- Save format version: 3 (old v2 saves explicitly rejected).
- git diff --check: clean.
- Private split: manifest v2, explicit GBK decoding, stable sequential IDs, volume
  labels, duplicate source chapter labels allowed.
- Private split reconstruction matched the decoded source in character count and
  SHA-256.
- The raw private source is read-only and must never be committed or copied into
  the public repository.

## Resume rule

The only active task is the one in `NEXT_TASK.md`: add a body equipment slot with
one original armor item and one deterministic defense_bonus. Do not implement
dialogue trees, novel extraction, or multiple body items first.

## Pause rule

To pause safely:
1. Stop the current Hermes/Codex task.
2. Do not start another model call or long-running corpus scan.
3. Run `git status --short`.
4. Sync `PROJECT_MEMORY.md` 及四个交接文件（`PROJECT_STATE.md`、
   `NEXT_TASK.md`、`DECISIONS.md`、`CHANGELOG.md`）。
5. Leave the working tree committed or clearly describe uncommitted changes.

To resume safely:
1. Run `git rev-parse HEAD` and `git log -3 --oneline`.
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
