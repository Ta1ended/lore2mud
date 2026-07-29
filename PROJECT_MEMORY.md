# Project Memory

_Checkpoint ref: HEAD — 恢复时运行 `git rev-parse HEAD` 获取当前提交。_

This file is a compact restart guide for GPT-5.6-sol, Codex, the project owner,
or a future agent session.
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

- Repository: `lore2mud`; branch: `main`.
- Current execution mode: GPT-5.6-sol reviews scope and architecture and performs
  independent acceptance; Codex is the sole executor; the project owner manually
  transfers prompts and completion reports between the two conversations.
- Documentation-closure baseline (before this local documentation commit):
  `HEAD`, `origin/main`, and directly queried remote `main` were all
  `1ee0b3053c541c1c2aa4c5e4339ebeaae62d1622`; the worktree was clean and
  ahead/behind was `0/0`. Recheck live Git before acting; local commits do not
  automatically push.
- Current public-engine contract: content pack 0.3.0, save v6, typed
  `ItemStackDefinition`/`ItemStack`, stack-limit validation, quantity-aware
  `take`/`drop`/`use`, typed loot/dialogue rewards, and v5 save rejection.
- M1 was implemented by Hermes agent and independently accepted GO by
  GPT-5.6-sol on 2026-07-28 (`c329546`). M2 was implemented by Hermes agent and
  independently accepted GO by GPT-5.6-sol on 2026-07-29 (DEC-0023).
- Current acceptance evidence: 530 full unittest cases and 56
  `tests.test_item_stacks` cases passed; compileall, original-demo validation,
  history safety scan, `git diff --check`, and the M2 CLI flow passed.
- Public code contains only the generic engine, tools, schemas, tests, docs, and
  original demo. The private corpus remains outside the repository and is not read
  for public-engine work.
- No Agent should start background work automatically when the project is resumed.

## Historical checkpoints (pre-M2; not current)

- Repository: `lore2mud`
- Branch: `main`
- Remote: `drop` 切片开始前，`HEAD`、本地跟踪 `origin/main` 与直接查询的
  `origin` 服务器 `main` 都是
  `1936e913348d3d46278ffaae2cfabf6502020835`；怪物战利品切片开始前，本地 `HEAD` 为
  `7a084e9d2439e00d1b0f9098300219e6d9c4e802`，相对该远端为 ahead/behind `1/0`。
  此前“仍为 `6c13fca`、等待发布”的交接叙述已过期。各切片仅做本地提交，未自动推送；恢复时仍须运行
  `git status --short --branch` 和 `git rev-list --left-right --count
  HEAD...origin/main` 检查实时状态。
- 2026-07-28 公共核心 readiness audit 基线：`HEAD` 为
  `d81310c08ada7d2950dbfbcd1c431d42773c056e`，本地工作树干净，直接远端和
  `origin/main` 都是 `1936e913348d3d46278ffaae2cfabf6502020835`，
  ahead/behind 为 `2/0`。结论为仅对公共原创内容扩展的 `CONDITIONAL GO`；不推送。
- Functional checkpoint: held-item exit gates, read-only `look` gate status,
  read-only visible-item inspection, safe named local save slots, a write-I/O
  error contract, `drop` for unequipped inventory items, deterministic
  single-item monster loot, and deterministic defeat recovery (`World.recover()`
  + `_require_alive()` unified death gate + command-layer gate before dialogue
  routing) are implemented; M1 independently accepted by GPT-5.6-sol on
  2026-07-28 (`c329546`);
  always inspect the live working tree before relying on this checkpoint.
- 2026-07-28 public-history cleanup baseline: `96de7b2`（现为 `eafe70e`
  的祖先）；任何后续历史操作前仍须重新检查实时远端。
- 功能状态：消耗品 + 装备(hand+body) + 对话物品奖励 + 可见物品查看 + 命名存档槽位 +
  写入错误契约 + 丢弃物品 + 确定性怪物战利品 + 死亡/失败处理(M1) 已实现；
  M1 已由 GPT-5.6-sol 独立验收 GO（`c329546`）；公共引擎仍在开发中
- Public code contains only the generic engine, tools, schemas, tests, docs, and
  original demo.
- The private novel corpus and split chapters are outside the repository under:
  `D:\MUD game kaifa\小说\processing\`
- The preprocessing pipeline is complete and verified; original source
  reconstruction matched in character count and SHA-256.
- The game engine has versioned local save/load (v5), deterministic quest flow,
  consumable items, hand+body equipment, item dropping, branching NPC dialogue,
  one typed dialogue item-reward effect, and deterministic defeat recovery.
- No Agent should start background work automatically when the project is resumed.

## Verified current facts

- Full project suite: 530 tests passed (2026-07-29).
- `tests/test_item_stacks.py`: 56 tests passed (2026-07-29), covering typed
  content/runtime stacks, stack limits, optional quantities, equipment constraints,
  loot preflight, save v6, M1 death-gate regression, and schema contracts.
- GPT-5.6-sol independently accepted M2 as GO. Compileall, original-demo
  validation, history safety scan, `git diff --check`, and the M2 CLI flow passed.

## Dated historical verification evidence (not current contracts)

- Focused readiness suite: 248 tests covering content loading, save/load and
  slots, dialogue, locked exits, drop, inspect, loot, and repository safety
  passed (2026-07-28). Compile, original-demo validation, history safety scan,
  and a real public CLI loop also passed.
- `tests/test_recover.py`: 59 tests cover recover success (12), recover
  failure/alive rejection (7), World death gate invariance (12), command-layer
  gate (19), and save/load round-trip (6). M1 independently accepted.
- `tests/test_loot.py`: 15 tests cover optional-field parsing, invalid and
  duplicate references, dialogue conflicts, one-time room placement, attack
  failure invariance, CLI rendering, and save/load validation.
- `tests/test_drop.py`: 11 tests cover ID/name resolution, failure invariance,
  equipped-item rejection, dialogue preservation, CLI text, and save/load.
- `tests/test_save_slots.py`: 12 tests cover default compatibility, isolated named
  saves, invalid/path-like names, Windows device names, command grammar, load
  failure invariance, write-I/O translation, and non-I/O propagation.
- `tests/test_inspect.py`: 9 tests cover room/inventory visibility, hidden reward
  rejection, duplicate-name handling, dialogue invariance, CLI text, and save/load.
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
  a typed `DialogueItemGrant`; save format remains v5.
- Save format v5 loading rejects unknown fields at the top level, `content_pack`,
  `player`, every room, every monster, `quest_states`, `equipped`, and
  `active_dialogue`; validation completes before a replacement `World` is built.
- Schema: 9 allOf rules including hand→no defense, body→no attack: passed.
- Held-item exit gates: `ExitDefinition` normalizes legacy string and structured
  exits. A gate checks inventory before room/quest/dialogue mutations, does not
  consume its item, and requires no save state; demo west exit needs the
  dialogue-earned `item_chen_token`.
- `look` renders each gated exit read-only with its direction, required item name,
  stable ID, and `未持有`/`已持有` status; ordinary exits remain bare directions.
  `World.move()` remains the sole gate-rule authority, and the display adds no
  content or save contract.
- `World.inspect_item()` resolves only the current room plus backpack, returns
  `InspectItemOutcome`, and is fully read-only. It does not expose items elsewhere
  or unawarded dialogue rewards, and does not change any content or save contract.
- `SaveLoadService` now accepts an optional safe slot name. Default calls remain
  `default.json`; named calls are constrained to the save directory and reject
  traversal, extensions, invalid characters, and Windows device names. Save v5
  data and atomic write behavior are unchanged.
- `SaveLoadService.save()` now converts filesystem `OSError` from its write path
  into a chained `SaveLoadError`; `CommandProcessor.save` reports it normally.
  It does not catch non-I/O programming errors, and save v5 data remains unchanged.
- `World.drop()` resolves only items already in the player's inventory and moves a
  valid, unequipped item to the current room. It rejects missing, ambiguous, or
  hand/body-equipped items before mutation; room/inventory placement is already
  covered by save v5 serialization and uniqueness validation.
- `MonsterDefinition.loot_item_id` is optional. It must reference an existing,
  initially unplaced item, cannot duplicate another monster's loot or a dialogue
  reward, and is placed in the current room only when that monster is first
  defeated. `World.attack()` remains the authoritative transition and returns a
  typed `LootOutcome`; save format v5 reuses existing room/inventory placement.
- Under the project owner's temporary GPT-5.6-terra exception, Terra self-audited
  and executed the `drop` and deterministic monster-loot slices.
- Under the project owner's direction, Hermes agent executed the M1 defeat-recovery
  slice and the M1 acceptance-rework fix.
- GPT-5.6-sol independently accepted M1 on 2026-07-28 (`c329546`): 59 recover
  tests, 474 full tests, compileall, content validation, safety scan, real CLI,
  and git status all passed. Conclusion: GO.
- The project owner provided a completed GPT-5.6-sol public-repository audit for
  baseline `2ecead1`, with a `CONDITIONAL GO`. It identified this write-I/O gap;
  the current slice closes it. The audit reported 43 dangling blobs without reading
  their contents; reachable-history scanning does not cover such objects. It also
  did not refresh the live GitHub server state.
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
1. Stop the current agent task.
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
- The completed public core-stability audit is a `CONDITIONAL GO` only for
  scaling fully original public content. It does not certify private novel facts
  or authorize private fact-layer work. The project owner has deferred that
  layer until public engine development is declared feature-complete; it will
  still require new, explicit scoped authorization before any access.
