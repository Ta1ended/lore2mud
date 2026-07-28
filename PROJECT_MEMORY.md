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
- 功能状态：消耗品 + 装备(hand+body) + 对话系统 已完成
- Public code contains only the generic engine, tools, schemas, tests, docs, and
  original demo.
- The private novel corpus and split chapters are outside the repository under:
  `D:\MUD game kaifa\小说\processing\`
- The preprocessing pipeline is complete and verified; original source
  reconstruction matched in character count and SHA-256.
- The game engine has versioned local save/load (v5), deterministic quest flow,
  consumable items, hand+body equipment, and branching NPC dialogue.
- No Agent should start background work automatically when the project is resumed.

## Verified facts

- Full project suite: 314 tests passed (2026-07-28).
- Repository safety check: passed.
- Compile check and CLI save/load smoke test: passed.
- CLI validate smoke test: passed.
- CLI play smoke test with quests, consumables, equipment, and dialogue: passed.
- Quest system: auto-accept, completion, reward-once, save round-trip: passed.
- Consumable system: heal_amount field, use command, full HP/dead/non-usable
  rejection, heal_amount: null rejection, save round-trip: passed.
- Equipment hand: attack_bonus, equip/unequip, effective_attack, save v3: passed.
- Equipment body: defense_bonus, effective_defense, player_defense, save v4,
  World state invariance, save v4 illegal matrix: passed.
- Dialogue system: talk command, bare integer selection, bye, terminal node
  auto-end, character lookup, World state invariance, save v5 round-trip,
  v4 save rejection: passed.
- Schema: 9 allOf rules including hand→no defense, body→no attack: passed.
- Content pack version: 0.2.4; save format version: 5.
- git diff --check: clean.
- Private split: manifest v2, explicit GBK decoding, stable sequential IDs, volume
  labels, duplicate source chapter labels allowed.
- Private split reconstruction matched the decoded source in character count and
  SHA-256.
- The raw private source is read-only and must never be committed or copied into
  the public repository.

## Resume rule

The only active task is the one in `NEXT_TASK.md`. Do not start other features
or background processing.

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
