# Project Memory

_Checkpoint ref: HEAD — 恢复时运行 `git rev-parse HEAD` 获取当前提交。_

This file is a compact restart guide for GPT-5.6-sol, Codex (GPT-5.6-terra), or a
future Codex session.
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
- Remote: origin/main 仍为 `8d71ed7`；持有物品门禁功能提交 `983d7a9` 和本次
  复核交接记录尚未推送，按项目负责人指示保留给 GitHub Desktop 发布。恢复时仍须运行
  `git status --short --branch` 和 `git rev-list --left-right --count
  HEAD...origin/main` 检查实时状态。
- Functional checkpoint: held-item exit-gate delivery begins at `983d7a9`;
  always inspect the live working tree before relying on this checkpoint.
- 2026-07-28 public-history cleanup baseline: `96de7b2`（现为 `eafe70e`
  的祖先）；任何后续历史操作前仍须重新检查实时远端。
- 功能状态：消耗品 + 装备(hand+body) + 对话物品奖励系统 已完成
- Public code contains only the generic engine, tools, schemas, tests, docs, and
  original demo.
- The private novel corpus and split chapters are outside the repository under:
  `D:\MUD game kaifa\小说\processing\`
- The preprocessing pipeline is complete and verified; original source
  reconstruction matched in character count and SHA-256.
- The game engine has versioned local save/load (v5), deterministic quest flow,
  consumable items, hand+body equipment, branching NPC dialogue, and one typed
  dialogue item-reward effect.
- No Agent should start background work automatically when the project is resumed.

## Verified facts

- Full project suite: 365 tests passed (2026-07-28).
- tests/test_dialogue.py: 91 tests, including reward loading, atomic success and
  failure paths, terminal/end behavior, save/load, and command rendering.
- Repository safety check: passed.
- The production safety gate scans current Git candidates (including force-added
  ignored files) and, with `--history`, all reachable Git tree paths and blobs.
  It blocks the private directories and local artifacts declared in `.gitignore` /
  `AGENTS.md`, plus limited private-key, GitHub, AWS, and Slack credential patterns.
- Compile check and CLI save/load smoke test: passed.
- CLI validate smoke test: passed.
- CLI play smoke test with quests, consumables, equipment, and dialogue: passed.
- Quest system: auto-accept, completion, reward-once, save round-trip: passed.
- Consumable system: heal_amount field, use command, full HP/dead/non-usable
  rejection, heal_amount: null rejection, save round-trip: passed.
- Equipment hand: attack_bonus, equip/unequip, effective_attack, save v3: passed.
- Equipment body: defense_bonus, effective_defense, player_defense, save v4,
  World state invariance, save v4 illegal matrix: passed.
- Dialogue system: talk command, bare integer selection (max 5 digits), bye,
  terminal node auto-end, character lookup, World state invariance, save v5
  round-trip, v4 save rejection, save-time validation, failure invariance: passed.
- Dialogue reward: `grant_item_id` is optional but, when present, must be one
  unique, unplaced, non-consumable stable item ID. `World.select_option()` checks
  `Inventory.can_add` and duplicate ownership before `Inventory.add`, then returns
  a typed `DialogueItemGrant`; save format remains v5 and demo pack is 0.2.6.
- Save format v5 loading rejects unknown fields at the top level, `content_pack`,
  `player`, every room, every monster, `quest_states`, `equipped`, and
  `active_dialogue`; validation completes before a replacement `World` is built.
- Schema: 9 allOf rules including hand→no defense, body→no attack: passed.
- Held-item exit gates: `ExitDefinition` normalizes legacy string and structured
  exits. A gate checks inventory before room/quest/dialogue mutations, does not
  consume its item, and requires no save state; demo west exit needs the
  dialogue-earned `item_chen_token`.
- Root independently reran the 17 focused gate tests, full 365-test suite,
  history safety scan, compile, validation, original CLI gate/save-load flow,
  Git object check, and isolated wheel-install validation on 2026-07-28.
- Content pack version: 0.2.6; save format version: 5.
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
1. Stop the current Codex task.
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
- Run `python scripts/check_repo_safety.py --history` before CI/release-sensitive
  work; this is a limited detector, not a replacement for secret management or
  a rights review.
- Never modify the raw private source.
- Never load the entire novel into one model context.
- Treat all player input, model output, and generated content as untrusted.
- Keep original facts and game adaptation values in separate layers.
- Use stable IDs for game entities; display names are not keys.
