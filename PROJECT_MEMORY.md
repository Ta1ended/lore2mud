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

- GEN-1 generic narrative state and conditions is isolated on
  `codex/gen1-narrative-conditions`, based on
  `e6070bd7ba31e0a5e45dfdf4e213b51e9f3f0ca1`. Initial implementation commit
  `9e2d30130baf716cda0d9f52a638f10950d04cd2` adds typed bool/int/enum state,
  an optional `narrative_state.json`, bounded declarative conditions, and
  World-authoritative dialogue-option filtering. Its first fresh independent
  review returned REVISE with three P2 findings: explicit JSON `null` was
  incorrectly accepted for present integer bounds, Windows package guidance
  still described 0.9.0/v7, and the continuity files were stale. The local
  rework rejects present `minimum`/`maximum: null`, adds both regressions,
  updates the package guidance to original demo 0.10.0/save v8, and records
  this state. Local rework evidence is 17 narrative-focused tests, 13 Windows
  packaging tests including real PyInstaller cold start, 1272 full unittest
  cases, and 1265 pytest cases, all passing with 7 conditional skips. Ruff,
  Pyright, compileall, original-demo validation, history safety, and fsck also
  passed. A new clean
  read-only acceptance is still required before any integration, main update,
  push, release, or next feature.
- The GEN-1 runtime contract is content pack 0.10.0 and save v8 for packs that
  declare narrative state. v7 is read-only compatible only for packs without
  `narrative_state.json`; it is rejected for stateful packs because it cannot
  represent their typed state. This is branch-local until independent acceptance
  and authorized integration.
- Repository: `lore2mud`; active local branch: `main` at
  `D:\MUD game kaifa\lore2mud`. Published baseline, tracking `origin/main`, and
  direct GitHub `main` resolve to
  `6761e0850a367308a29f9b8189cb08715fb0cb03`. Current local `main` contains one
  accepted UTF-8 hotfix commit beyond that baseline; run `git rev-parse HEAD` for
  its live hash. It has not been pushed or released.
- GitHub Actions run `30642616101` passed every Python 3.11/3.12/3.13 job but
  failed `windows-candidate` while its PyInstaller executable printed the Chinese
  validation-success line through redirected `cp1252` output. DEC-0069 records the
  narrow delivery-runtime UTF-8 correction in `src/lore2mud/cli.py`, the Windows
  launcher, and two complementary regression tests. A fresh review accepted it GO
  with no P0-P3 findings (DEC-0070). Real frozen and zipapp cold starts, 1254 full
  unittest cases, 38 focused pytest cases, 1247 passing xdist pytest cases, and all
  named static/repository gates passed. The local commit is ready for the project
  owner to push after refreshing the remote; the resulting workflows remain to be
  observed.
- Current execution mode (DEC-0059, DEC-0067): new development is performed by
  GPT-5.6-sol Codex tasks. The default remains one vertical slice, while a project-
  owner-authorized sprint may use isolated parallel responsibility domains and one
  integration controller. Independent acceptance uses a fresh Codex review task or
  clean context. Hermes remains historical attribution only; local commits never
  automatically modify `main`, push, or release.
- M7.2 independent acceptance compares
  `147633e0f139c9bc04919d8f69e75666e511fadc` with baseline
  `549785912418bff56d1521437a51c25718edbc34`; M7.1's independently accepted
  implementation remains `97863258966a499b8eba805cd0ef2e598943eb63`. Recheck live
  Git, `origin/main`, direct remote `main`, and ahead/behind before acting or
  publishing. Local commits do not automatically push.
- GPT-5.6-sol's first M4+M5 independent review was NO-GO because `World.buy()`
  could create a new stack above its `stack_limit`, allowing a save that its own
  v7 loader rejects. Codex corrected that one M5 P1 in `59ca3cd`; GPT-5.6-sol's
  focused re-review found no findings and independently accepted M4+M5 GO on
  2026-07-29. GPT-5.6-sol also independently accepted M6 GO with no findings on
  2026-07-29 (DEC-0030). The project owner then authorized M7.1; Codex implemented
  the second original encounter and GPT-5.6-sol independently accepted M7.1 GO with
  no findings on 2026-07-30 (DEC-0032). The project owner then authorized the larger
  M7.2 content-only scale slice; GPT-5.6-sol independently accepted M7.2 and M7 as
  GO with no findings on 2026-07-30 (DEC-0034). The M8 technical audit baseline is
  `f486e12`, its audit record is `6510e2d`, and `6502a72` corrected the independent-
  review Git-snapshot P2. GPT-5.6-sol then accepted M8 GO with no new findings
  (DEC-0036), closing the M1–M8 public-engine roadmap scope. At acceptance, local
  `HEAD` and `origin/main` are both `6502a72`, the worktree is clean, and
  ahead/behind is 0/0; GitHub Desktop push is reflected locally, while the command-
  line direct remote query timed out. Recheck Git live after every handoff commit
  and before any later publishing decision. M8 GO does not authorize M9, other
  feature work, or private novel fact-layer access.
- Current integrated public-engine contract: content pack 0.9.0; save v7; typed
  `ItemStackDefinition`/`ItemStack`; quantity-aware `take`/`drop`/`use`;
  required ordered dialogue effects; World-owned flags; nonnegative coins; and
  frozen fixed-price, unlimited shop catalogs without serialized stock. v6 and
  old 0.7.0 content saves are rejected without migration.
- M3 was implemented by Codex and independently accepted GO by GPT-5.6-sol on
  2026-07-29 after the focused re-review of `dca629b` and its handoff correction
  `5527faa`. `QuestDefinition` is a frozen three-branch union:
  `monster_defeated.target_monster_id`, `reach_room.target_room_id`, and
  `collect_item.target_item_id + required_quantity`. World owns acceptance,
  condition checking, reward commit, deterministic quest-ID ordering, and local
  rollback; `World.move()` still returns `Room` while `move_with_outcome()` feeds
  CLI task results. M4 effects and M5 trades reuse this authority: effects are
  whole-list preflighted and atomic; explicit duplicate acceptance rejects the
  option; loading v7 restores state only and never replays effects, tasks,
  rewards, or trades.
- M6 adds `World.examine()` with frozen item/monster/character outcomes, current-
  visibility-only resolution, public `examine`, compatible item-only `inspect`,
  and one frozen `CommandSpec` registry for real routes, help, aliases, and death
  permission. Exact-ID resolution precedes names; cross-type duplicate IDs or
  names require an explicit type. `examine` and `help` are read-only, preserve
  active dialogue, and remain available when dead. M6 changes no content or save
  contract and is independently accepted GO.
- M7.1 adds only public content: `room_shattered_signal_spur` east of the silent
  observatory, `monster_spark_hound`, and the observation-station-triggered
  `quest_clear_spark_hound`. It reuses existing movement, deterministic combat,
  typed monster quests, and v7 saves; no engine, Schema, command, item, or loot
  contract changed. The demo is now four rooms, two monsters, and five quests.
  M7.1 is independently accepted, but this is not full M7 completion.
- M7.2 adds only public content: `room_broken_rail_junction`,
  `room_mist_condenser_well`, `room_lens_archive`,
  `room_afterglow_beacon_platform`, `monster_mist_crawler`,
  `monster_prism_sentinel`, and their unique-target monster quests. It reuses the
  same movement, deterministic combat, typed quest, and v7 save contracts; no
  engine, Schema, command, item, loot, or dependency contract changed. The demo is
  now eight rooms, four monsters, and seven quests. The M7 scale conditions and M8
  public-engine audit are independently accepted GO; this completes only the M1–M8
  public-engine roadmap scope and does not authorize subsequent work.
- Phase 1.0 fact-candidate validation implemented by Hermes (2026-07-30):
  `pipeline/fact_candidates.py` with frozen dataclass models (document envelope,
  candidate, claim, 5-branch value tagged union), stable-ID regex, NFKC alias
  dedup, relation cross-reference, `FactCandidateValidationError`. JSON Schema
  at `schemas/fact_candidate.schema.json` (draft 2020-12). Initial verification:
  119 focused and 718 full tests, compileall, content validation, safety scan,
  diff check. Independent acceptance NO-GO (P1-1 enum TypeError, P1-2 numeric
  precision, P2 Schema constraints). Focus fix `3442d2d` (DEC-0038): 131 focused
  and 730 full tests. GPT-5.6-sol independently accepted Phase 1.0 GO with no
  remaining findings (DEC-0039). The acceptance snapshot before its documentation
  seal was HEAD=`3442d2d`, `origin/main`=`afdb235`, ahead/behind=2/0, not pushed.
- Phase 1.1 manifest validation and source binding implemented by Hermes (2026-07-30):
  `pipeline/chapter_manifests.py` with frozen dataclass models (ChapterManifestEntry,
  ChapterManifest), primary/scan conditional validation, consecutive chapter ID,
  chain adjacency, path safety, SHA-256 format, monotonic offset/line. Source binding
  via `validate_fact_candidate_sources()`. JSON Schema at
  `schemas/chapter_manifest.schema.json`. 73 focused tests, 803 full tests pass.
  Pending GPT-5.6-sol independent acceptance (DEC-0041). Phase 1.1 independent
  acceptance NO-GO (P1 missing-field bypass, P2 Schema conditions). Focus fix in
  DEC-0042: 8 missing-field tests + 5 new Schema tests, 236 focused, 817 full tests.
  Schema allOf/additionalProperties P1 fixed in DEC-0043: entry_base.properties
  now lists all 12 fields. 237 focused, 817 full tests. Pending GPT-5.6-sol
  final re-review (DEC-0041 through DEC-0046). GPT-5.6-sol independently
  accepted Phase 1.1 GO with no remaining findings (DEC-0047). 237 focused,
  817 full tests. Local HEAD=`56edcb2`, `origin/main`=`1585a98`.
- Phase 1.2 fact-review validation and claim-level review states implemented
  by Hermes (2026-07-30): `pipeline/fact_reviews.py` with frozen dataclass
  models, four-state decisions, superseded conditional, (candidate_id,claim_id)
  uniqueness, candidate-document binding. 43 focused, 280 Phase 1.2+1.1+1.0
  regression, 860 full tests. GPT-5.6-sol independently accepted Phase 1.2 GO
  with no remaining findings (DEC-0051). Local HEAD=`e742d20`,
  `origin/main`=`a55c7d8`.
- L2W-1 canon draft promotion implemented by Hermes (2026-07-30):
  `pipeline/canon.py` with frozen dataclass models, promotion closure logic,
  CLI with atomic write. 50 focused, 910 full tests. GPT-5.6-sol independently
  accepted GO (DEC-0054).
- L2W-2 micro content pack compilation implemented by Hermes (2026-07-30):
  `pipeline/adaptation.py` with frozen dataclass models, AdaptationPlan
  structural validation, binding + coverage + cross-object compilation,
  staged atomic write with loader validation and manifest re-validate.
  GPT-5.6-sol independently accepted technical commit `f7a977a2` GO (DEC-0058):
  72 focused tests with 1 skipped and 982 full tests with 1 skipped.
- L2W-3 multi-chapter canon registry assembly was implemented by Codex in
  `a89fdc6d819b976b80b82a74e575ff851ba86448` against baseline
  `b22bee33cacb154a2efc7e4eef0e3182ccc8319c` (DEC-0060). The first fresh
  GPT-5.6-sol review returned REVISE: relation targets did not require a member
  from the claim's source promotion, source candidate provenance could be reused,
  byte determinism did not exercise the writer/golden fixture, and link aliases
  lacked tests. DEC-0061 closes all four locally with semantic validation,
  mutation tests, writer/CLI golden-byte comparisons, and hardlink plus conditional
  symlink tests. Rework evidence: 84 focused tests (1 skipped), 1066 full tests
  (2 skipped), compileall, original-demo validation, Schema + fixture validation,
  history safety, fsck, diff checking, and repository-external CLI/golden bytes.
  A second fresh GPT-5.6-sol task independently accepted correction
  `1c9a20bfade5bdb292ca3a801f00279cf0450e30` as GO with no findings (DEC-0062).
  Its acceptance snapshot was one 8-file commit (`+231/-66`) after `a89fdc6d`,
  with a clean worktree and `origin/main` still at `a89fdc6d` (ahead 1, not pushed).
- L2W-4 registry-backed micro adaptation was implemented by Codex in the
  separate `pipeline/registry_adaptation.py` route. It consumes a validated
  `CanonRegistry v1` plus an explicit `RegistryAdaptationPlan v1`, preserves every
  selected composite claim reference, derives chapters, and emits the unchanged
  L2W-2 one-room profile with `registry_adaptation_manifest.json`. The fictional
  two-source fixture covers one location, one cross-chapter character with
  conflicting role claims, and one item; no private corpus was read.
- L2W-4 local evidence is 39 focused tests (1 Windows symlink permission skip),
  1105 full unittest cases (3 skips), compileall, Schema JSON parsing, fixture and
  golden bytes, original-demo validation, history safety, fsck, diff checking,
  repository-external CLI plus `lore2mud validate`, and a World pickup/quest
  completion playthrough. A fresh GPT-5.6-sol Codex task independently reran the
  implementation-range, test, Schema, golden, writer, CLI, loader, World, safety,
  and Git checks and accepted L2W-4 GO with no P0-P3 findings (DEC-0064).
  The implementation commit is `1fb95bf8fce42428188d6d9d06b1a68397f8d999` on top
  of `a19707521ed0dcc162abf2448254c086a1bf58af`; local tracking `origin/main` is
  still `a89fdc6d819b976b80b82a74e575ff851ba86448`; the independent-acceptance
  snapshot was clean at `77f1fa795bd3f7c0ba6b565a57809459db31ee0d`, ahead/behind
  `4/0`. A direct GitHub `main` query timed out and must be retried before publishing.
- L2W-5 explicit read-only registry inspection was implemented by Codex and
  independently accepted GO with no P0-P3 findings (DEC-0065, DEC-0066).
  `pipeline/registry_inspection.py` consumes a validated CanonRegistry
  and an exact-ID `RegistryInspectionPlan v1`, then copies the selected frozen
  entities into a deterministic `RegistryInspectionReport v1`. It retains aliases,
  members, source candidate IDs, every composite claim and conflict, while deriving
  only the source records used by those claims. It performs no name search,
  inference, conflict resolution, registry update, adaptation, or game-state change.
- L2W-5 evidence is 49 focused tests (1 Windows symlink permission skip), 172
  L2W-3/L2W-4/L2W-5 tests (3 skips), and 1154 full unittest cases (4 skips), plus
  compileall, both Draft 2020-12 Schemas under `Draft202012Validator`, original-demo
  validation, history safety, fsck, whitespace checks, and a repository-external
  subprocess CLI. The 4144-byte golden report has SHA-256
  `f943f6f487bcca607d854023c32b0a663ede25069700f707637420a5857eebb5` and exactly
  1 entity, 2 members, 4 claims and 2 source records; input hashes stay unchanged.
  The accepted range is `9f09d9691a236919648cea294c31fcdf0f105ff9..`
  `13be791bc0a116f6596267b5d914a8a63e511f1f`: one commit, 17 files,
  `+2455/-39`. Independent verification repeated the focused/regression/full suites,
  compileall, Schema/fixture checks, original-demo validation, history safety, fsck,
  diff checks, and a repository-external CLI/golden-byte run.
- The project owner then authorized an isolated five-domain parallel sprint
  (DEC-0067). Core expands the fully original demo to 0.9.0 with a confirmable
  ending; Forge adds a resumable conversion workbench; Player adds a standard-
  library loopback Web UI and structured actions; Quality adds Ruff, Pyright,
  pytest/xdist and multi-version CI; Ship adds verified PyInstaller and zipapp
  Windows candidates. The controller integrated all domains in dependency order.
  Two acceptance rounds found and closed protocol, Forge portability, browser
  recovery, and 320px overflow defects. Candidate `a172a82` is independently
  accepted GO with no P0-P3 findings (DEC-0068).
- M1 was implemented by Hermes agent and independently accepted GO by
  GPT-5.6-sol on 2026-07-28 (`c329546`). M2 was implemented by Hermes agent and
  independently accepted GO by GPT-5.6-sol on 2026-07-29 (DEC-0023).
- Codex local P1-correction evidence: 569 full unittest cases, 12
  `tests.test_dialogue_effects` cases, 13 `tests.test_shop` cases, compileall,
  original-demo validation, history safety scan, diff checking, and an
  external-save-directory CLI path that rejects buy ×6 after selling ×3, then
  save/loads the valid zero-stack state with 26 coins. GPT-5.6-sol independently
  accepted this M4+M5 evidence as GO; the first-review P1 is closed. M2's
  historical independent-acceptance evidence remains 530 full cases and 56
  `tests.test_item_stacks` cases with its own CLI flow.
- Public code contains only the generic engine, tools, schemas, tests, docs, and
  original demo. The private corpus remains outside the repository and is not read
  for public-engine work.
- No new implementation should start automatically when the project is resumed;
  the only active action is the publish gate in `NEXT_TASK.md`.

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

- Codex locally verified M7.2 before independent acceptance: content pack 0.8.0
  expands the demo to eight rooms, four monsters, and seven quests, with four new
  rooms, two new monsters, and two unique-target `monster_defeated` quests. Eight
  M7 scenario tests plus 15 loot regressions and 599 full tests passed, together
  with compileall, original-demo validation, history safety, and diff checking. The
  external CLI completed both new branches and save/loaded v7/0.8.0 state with the
  player at the beacon, both new monsters at HP 0 and removed, and both new quests
  complete. This local evidence was subsequently independently accepted.
- GPT-5.6-sol independently accepted M7.2 and the complete M7 milestone as GO with
  no findings (2026-07-30, DEC-0034). Relative to `5497859`, `147633e` is one
  22-file content/test/public-document commit with zero `src/`, Schema, dependency,
  or private-material-path changes. Accepted evidence is 23 M7/loot focused tests,
  599 full unittest cases, topology and unique-target audits, compileall,
  original-demo validation, history safety, and `git diff --check`; real CLI/save
  and defeat recovery also passed. The v7/0.8.0 save confirms the player is in a
  new room, both new monsters are HP 0 and removed, and both new quests are complete.
  The acceptance-time direct remote `main` was `f0acd3f` and no push occurred.
- Codex completed the M8 read-only audit baseline on `f486e12` (2026-07-30): 599
  full unittest cases, compileall, original-demo validation, `check_repo_safety.py
  --history`, `git diff --check`, and `git fsck --full --no-dangling` passed. A real
  CLI flow completed both M7.2 branches and v7/0.8.0 save/load; a fresh CLI flow
  proved prism-sentinel death, the death gate, `recover`, and v7 save/load back at
  the start room. The subsequent M8 audit-record commit is `6510e2d`, and `6502a72`
  corrected its P2 Git snapshot. GPT-5.6-sol then independently accepted M8 GO with
  no new findings (DEC-0036), completing the M1–M8 public-engine roadmap scope only.
- GPT-5.6-sol independently accepted M7.1 as GO with no findings (2026-07-30):
  relative to `086cda8`, `9786325` is one 22-file `+333/-55` commit and leaves
  `src/`, `schemas/`, dependency files, and private-material paths untouched. 19 M7/loot focused and
  595 full tests, compileall, original-demo validation, history safety, and baseline
  diff checking passed. The real CLI completed the second encounter and save/load;
  the v7/0.7.0 save has the player in the new room, the hound at HP 0 and removed,
  and `quest_clear_spark_hound` completed. Direct remote `main` was `f0acd3f` and
  no push occurred. This accepts M7.1 only; M7 remains in progress at four of eight
  rooms and two of four monsters.
- Codex locally verified M7.1 before independent acceptance: 4 new M7 scenario
  tests plus 15 loot regressions and 595 full tests passed, together with
  compileall, original-demo validation, history safety, and diff checking. The
  external CLI completed the second encounter and saved/loaded v7 with pack 0.7.0;
  a 0.6.0 content-pack save is rejected.
- GPT-5.6-sol independently accepted M6 GO with no findings (2026-07-29): 22 M6
  tests, 187 focused inspect/commands/recover/dialogue regressions, and 591 full
  tests passed together with compileall, original-demo validation, history safety,
  diff checking, an 11-file scope check relative to `f0acd3f`, and an
  external-save-directory CLI/save v7 flow. The CLI proved room/item/character/
  monster examine, typed missing errors, detailed help, dialogue-preserving numeric
  target handling, and v7/0.6.0 save/load. Cross-type ambiguity fixtures are test-
  memory-only. This historical M6 record does not accept M7.1.
- GPT-5.6-sol independently accepted M4+M5 as GO (2026-07-29). The first
  review's empty-stack `stack_limit` P1 was fixed in `59ca3cd`; the focused
  re-review found no findings.
- Codex local P1-correction suite: 569 tests passed (2026-07-29); focused suites
  are 12 `tests.test_dialogue_effects` and 13 `tests.test_shop` tests. The new
  test covers World and CLI rejection of an empty-stack buy ×6, with coins and
  all mutable state unchanged.
- M4 coverage proves exact effect shapes, all frozen branches, whole-list order and
  rollback, duplicate explicit acceptance, immediate ready-task settlement,
  flag semantics, typed CLI outcomes, and v7 flag load behavior.
- M5 coverage proves frozen catalog definitions, required/strict shops content,
  exact coins, catalog immutability, buy/sell invariance and rollback, the
  empty-stack stack-limit preflight, death gate, dialogue preservation, and v7
  catalog reconstruction without stock serialization.
- Compileall, original-demo validation, `check_repo_safety.py --history`,
  `git diff --check`, and real external-save-directory CLI flow passed. The CLI
  saved 14 coins/one true flag after effects, traded after saving, then loaded the
  earlier world without replaying effects; independent v6/0.6 and v7/0.4 loads
  were rejected for format and content-pack version respectively.
- M1, M2, and M3 retain their historical GPT-5.6-sol independent GO decisions;
  M4+M5 are also independently accepted GO (DEC-0028), and M6 is independently
  accepted GO (DEC-0030). M7.1 is independently accepted GO (DEC-0032); M7.2 and
  M7 are independently accepted GO (DEC-0034); M8 is independently accepted GO
  (DEC-0036). M1–M8 public-engine scope is complete; there is no active development
  slice until the project owner provides new, explicit authorization.

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
