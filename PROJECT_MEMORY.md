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
- 功能状态：消耗品 + 装备(hand+body) 已完成
- Public code contains only the generic engine, tools, schemas, tests, docs, and
  original demo.
- The private novel corpus and split chapters are outside the repository.
- No Agent should start background work automatically when the project is resumed.

## Verified facts

- Full project suite: 229 tests passed (2026-07-28).
- Repository safety check: passed.
- Compile check: passed.
- Content pack validation: passed.
- git diff --check: clean.
- Consumable: heal_amount, use, full HP/dead rejection, save round-trip.
- Equipment hand: attack_bonus, equip/unequip, effective_attack, save v3.
- Equipment body: defense_bonus, effective_defense, player_defense, save v4.
- Content pack version: 0.2.3; save format version: 4.

## Resume rule

The only active task is the one in `NEXT_TASK.md`. Do not start other features.

## Pause rule

To pause safely:
1. Stop the current task.
2. Run `git status --short`.
3. Sync `PROJECT_MEMORY.md` 及四个交接文件。
4. Leave the working tree committed.

To resume safely:
1. Run `git rev-parse HEAD` and `git log -3 --oneline`.
2. Read the handoff files in order.
3. Restate the single active task.

## Hard boundaries
- Never commit the private novel, split chapters, summaries, canon facts, or credentials.
- Never modify the raw private source.
- Never load the entire novel into one model context.
- Treat all player input, model output, and generated content as untrusted.
- Use stable IDs for game entities; display names are not keys.
