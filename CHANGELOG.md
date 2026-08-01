# Changelog

## [Unreleased]

### Changed

- Tightened CampaignSpec v1 cross-object semantics after its first independent
  review returned REVISE. The sole player's non-null starting location must now
  equal the authoritative campaign map root. Every completion kind resolves to
  an objective-owned scene in the exact objective phase, preventing later or
  unrelated knowledge, locations, actors, or scenes from completing an earlier
  objective. Schema descriptions and the format guide state the shared plan/spec
  rule, and README now lists the real `python -m pipeline.campaign` CLI. Local
  corrections are verified but await a fresh independent re-review (DEC-0077).
- Added generic, typed narrative state and bounded declarative dialogue
  conditions to the original public demo. Content packs may define bool, int,
  and enum state in optional `narrative_state.json`; `World` remains the sole
  authority for evaluating options through `available_dialogue_options()`, and
  CLI/Web project only that result. Stateful packs write save v8; v7 remains
  read-compatible only for packs with no narrative-state definitions.
- Explicit `minimum` and `maximum` integer bounds in `narrative_state.json` now
  reject JSON `null`; omitting either field remains the only way to declare no
  bound. Windows candidate guidance now reflects original demo 0.10.0 and save
  v8 compatibility. A clean re-review accepted GEN-1 GO; it is included in the
  local public integration candidate, whose final clean integration acceptance
  also returned GO (DEC-0071, DEC-0074, DEC-0075).
- Frozen CLI entry points, plus zipapps started by the official Windows launcher,
  now reconfigure supported standard output and error streams as UTF-8 before
  parsing commands. The PowerShell launcher uses matching UTF-8 console and
  pipeline encodings so candidates remain usable when redirected by a legacy-
  code-page runner without mutating streams in embedded or test calls
  (DEC-0069, DEC-0070).
- Updated the development contract for project-owner-authorized isolated parallel
  sprints: named responsibility domains use separate worktrees/branches and one
  integration controller while `main` stays read-only. Integration, GO, push, and
  release remain distinct gates (DEC-0067).
- Aligned the README workflow summary with DEC-0059: Codex now owns planning,
  implementation, testing, handoff, local commits, and clean-context acceptance;
  Hermes remains historical attribution only, and local commits are not pushed
  automatically. Added the registry-backed adaptation CLI to the public pipeline
  entry points. Documented the autonomous-Goal stop rule when confirmed GitHub
  lag exceeds five local commits.

### Added

- Added public `RegistryCampaignPlan v1` and `CampaignSpec v1` contracts for a
  deterministic, genre-neutral campaign IR. The compiler binds an explicit
  human plan to the exact canonical NarrativeModel SHA-256, closes use/omission
  accounting for entities, perspectives, propositions, and beats, validates
  directed location and scene traversal, objective DAG/exclusion consistency,
  ordered knowledge transitions and explicit corrections, and emits a
  self-contained canonical artifact through an atomic alias-protected CLI.
  Two wholly original fixture families cover a magic-like civic event and an
  urban investigation knowledge correction. Local implementation verification
  passed 45 focused tests with 2 Windows symlink-permission skips, 1361 full
  unittest tests with 12 skips, and 1349 full pytest tests with 12 skips, plus
  Draft 2020-12 Schema/fixture validation, Ruff, Pyright, compileall,
  original-demo validation, repository-external golden CLI bytes, history
  safety, fsck, and whitespace checks. The first independent review returned
  REVISE; its two P2 semantic findings and P3 README finding are closed locally,
  with fresh independent re-review still pending (DEC-0076, DEC-0077).
- Added deterministic `NarrativeModel v1` compilation from a validated
  CanonRegistry plus an explicit human NarrativePlan. The public pipeline
  validates exact claim use/omission accounting, scoped source snapshots,
  perspectives, proposition states, contiguous phases, DAG beats, disclosures,
  canonical serialization, atomic output, and CLI path-alias protection. Added
  strict plan/model Schemas, public fictional fixtures, golden-byte and CLI
  coverage, and format documentation. The first independent review found that
  all-reasoned-omission plans were incorrectly rejected; the local correction
  permits empty `claim_uses` when every scoped claim is explicitly omitted and
  has since received a clean re-review GO. It is included in the local public
  integration candidate, whose final clean integration acceptance also returned
  GO (DEC-0072, DEC-0073, DEC-0074, DEC-0075).
- Integrated the five-domain public sprint. Core expands `original_demo` to
  content-pack 0.9.0 with nine rooms, eight items, four monsters, two characters,
  eight quests and a confirmable ending. Forge adds resumable
  `init/status/check/run/rerun` workspaces with fingerprints, immutable artifacts,
  locks and recovery. Player adds a loopback standard-library Web UI with structured
  actions. Quality adds Ruff, Pyright, pytest/xdist and multi-version CI. Ship adds
  verified PyInstaller and zipapp Windows candidates with diagnostics, manifests,
  and repository-external cold-start verification (DEC-0067, DEC-0068).
- Added a real `cp1252` stream regression for the frozen Unicode validation-success
  path and a complementary embedded-call host-stream preservation regression.
  A fresh clean-context review accepted the hotfix GO with no P0-P3 findings after
  the pinned PyInstaller 6.21.0 repository-external cold start, 1254 full unittest
  cases with 7 skips, focused pytest with 38 passing tests, and xdist pytest with
  1247 passed / 7 skipped. Ruff, Pyright, compileall, original-demo validation,
  history safety, fsck, and whitespace checks also passed (DEC-0070).
- Added explicit read-only CanonRegistry inspection reports (L2W-5):
  `pipeline/registry_inspection.py` validates strict plan/report v1 contracts,
  selects only exact stable entity IDs, copies complete aliases, members,
  candidate provenance and composite claims, and derives the exact claim-source
  subset without search, inference, conflict resolution, or registry mutation.
  Added two Draft 2020-12 Schemas, a public fictional plan and 4144-byte golden
  report, deterministic atomic/fsync writer, direct/subprocess CLI coverage,
  format and pipeline docs, and 49 focused tests (1 Windows symlink permission
  skip). Verification passed 172 L2W-3/L2W-4/L2W-5 tests (3 skips), 1154 full
  unittest cases (4 skips), compileall, real Schema validation, original-demo
  validation, history safety, fsck, whitespace checks, and a repository-external
  golden-byte CLI. A fresh GPT-5.6-sol task independently accepted the single-commit
  implementation GO with no P0-P3 findings (DEC-0065, DEC-0066).

- Added registry-backed micro adaptation (L2W-4):
  `pipeline/registry_adaptation.py` validates a strict `RegistryAdaptationPlan v1`,
  requires exact registry entity/claim/omission coverage, preserves composite
  `(promotion_id, source_entity_id, source_claim_id)` provenance, derives binding
  chapters, and compiles the unchanged L2W-2 one-room profile without conflict
  resolution or text inference. Added separate plan/manifest draft-2020-12 Schemas,
  a fictional two-source registry and plan, nine-file golden output, format
  documentation, atomic fsync writer, direct/subprocess CLI checks, loader/World
  playthrough, and 39 focused tests (1 platform symlink skip). Local verification
  passed 1105 full unittest cases (3 skips), compileall, Schema/fixture parsing,
  original-demo validation, `check_repo_safety.py --history`, `git fsck`,
  `git diff --check`, and a repository-external CLI whose bytes match the golden
  output. A fresh GPT-5.6-sol task independently reran the focused, L2W-2
  regression, full, Schema, safety, CLI, loader, golden-byte, and World evidence
  and accepted L2W-4 GO with no P0-P3 findings (DEC-0064).

- Added deterministic multi-chapter canon registry assembly (L2W-3):
  `pipeline/canon_registry.py` validates explicit `RegistryPlan v1` identity
  mappings, requires exact coverage of two or more unique CanonDraft sources,
  allows at most one member per source in each registry entity, rejects mixed
  entity types and duplicate `(promotion_id, source_candidate_id)` provenance,
  rewrites relations only to registry entities with a member from the claim's
  source promotion, and emits a
  frozen source-preserving `CanonRegistry v1`. Repeated or conflicting claims
  remain distinct under `(promotion_id, source_entity_id, source_claim_id)`;
  no identity inference or semantic conflict resolution occurs. The CLI writes
  deterministic UTF-8 JSON through a same-directory temporary file with
  flush, fsync, atomic replace, input/output alias rejection, and failure cleanup.
  Added RegistryPlan/CanonRegistry draft-2020-12 Schemas, a public fictional
  golden fixture, format documentation, and 84 focused tests. The first independent
  GPT-5.6-sol review returned REVISE; its four provenance, byte-fixture, and link-alias
  findings are closed locally in DEC-0061. Rework verification passed 1066 full
  tests (2 skipped), compileall, original-demo validation, Schema + fixture checks,
  history safety, fsck, diff checking, and a repository-external module CLI whose
  output matched the golden bytes. A fresh GPT-5.6-sol task independently accepted
  correction `1c9a20bfade5bdb292ca3a801f00279cf0450e30` as GO with no findings
  (DEC-0062); the 6245-byte golden output, provenance mutations, three hardlink
  input classes, full scope, and clean Git snapshot were independently rechecked.
- Added micro content pack compilation (L2W-2): `pipeline/adaptation.py` with
  frozen `AdaptationPlan`, `AdaptationManifest`, and semantic `MicroContentPack`
  dataclass models, `validate_adaptation_plan()`,
  `compile_micro_pack()`, `write_micro_pack()` (atomic, staged),
  `validate_adaptation_manifest_document()`, and deterministic `main()` CLI.
  72 focused tests (1 skipped) and 982 full tests (1 skipped) passed independent
  acceptance. Adaptation plan single-object profile (1 room/character/
  item/quest/dialogue). Item output excludes heal/slot/bonus fields. Quest
  auto-accepted via trigger_room. Dialogue effects=[]. Full provenance via
  adaptation_manifest.json sidecar; golden nine-file output and per-file fsync
  are covered.
- Added `schemas/adaptation_plan.schema.json` and
  `schemas/adaptation_manifest.schema.json` (draft 2020-12).
- Added `docs/adaptation_plan_format.md`.
- Added canon draft promotion (L2W-1): `pipeline/canon.py` with frozen
  `PromotionPlan`, `CanonDraft`, `CanonEntity`, `CanonClaim` dataclass models,
  `validate_canon_promotion_plan()`, `build_canon_draft()`,
  `validate_canon_draft_document()`, and deterministic `main()` CLI.
  Promotion closure: direct entities (≥1 accepted claim) ∪ relation entities
  (accepted relation target). Relation value rewritten from candidate_ref to
  entity_ref. CanonDraft validated before atomic write.
- Added `schemas/canon_promotion_plan.schema.json` and
  `schemas/canon_draft.schema.json` (draft 2020-12).
- Added `tests/test_canon.py` with 50 focused tests.
- Added `docs/canon_draft_format.md`.
- Added v2 chapter manifest validation: `pipeline/chapter_manifests.py` with
  frozen `ChapterManifestEntry` and `ChapterManifest` dataclasses, primary/scan
  conditional validation, consecutive chapter ID enforcement, chain adjacency,
  path safety, SHA-256 format, and monotonic offset/line checks.
- Added `schemas/chapter_manifest.schema.json` (draft 2020-12, `additionalProperties`
  false, `source_encoding` if/then/else conditional, `oneOf` for previous/next).
- Added `validate_fact_candidate_sources()` for binding validated
  `FactCandidateDocument` instances to a `ChapterManifest` by source_chapter
  existence check.
- Added `tests/test_chapter_manifests.py` with 86 focused tests covering fixtures,
  frozen types, build_manifest integration (primary + scan + empty), ID consecutive/
  duplicate/skip, path safety, SHA-256 format, chain adjacency, primary/scan
  conditions, offset/line monotonic, missing-field rejection, source binding,
  and Schema structure assertions.
- Added `tests/fixtures/chapter_manifests/valid_primary.json` and `valid_scan.json`.
- Added `docs/chapter_manifest_format.md`.
- Added v1 fact-review document validation: `pipeline/fact_reviews.py` with
  frozen `ReviewDecision` and `FactReviewDocument` dataclasses, four-state
  (accepted/rejected/superseded/conflicted) with superseded_by_claim_id
  conditional, (candidate_id, claim_id) uniqueness, and
  `validate_fact_review_bindings()` for candidate-document cross-checking.
- Added `schemas/fact_review.schema.json` (draft 2020-12, `if/then/else` for
  state=superseded conditional).
- Added `tests/test_fact_reviews.py` with 43 focused tests.
- Added `tests/fixtures/fact_reviews/valid_review.json`.
- Added `docs/fact_review_format.md`.
- Added v1 fact-candidate document validation contract: `pipeline/fact_candidates.py`
  with frozen dataclass models (`FactCandidateDocument`, `Candidate`, `Claim`,
  five value branches), stable-ID regex, NFKC alias dedup, relation cross-reference,
  and `FactCandidateValidationError`.
- Added `schemas/fact_candidate.schema.json` (draft 2020-12, `additionalProperties`
  false, `oneOf` tagged union, `if/then/else` for inference_basis conditional,
  `\\S` pattern for non-blank strings). Schema expresses structural constraints;
  Python adds semantic checks (dedup, cross-reference, NFKC, bool/int, finite float).
- Added `tests/test_fact_candidates.py` with 131 focused tests covering all value
  branches, unknown fields, missing fields, bool/int, NaN/Inf, alias dedup,
  relation dangling ref, chapter mismatch, inference_basis conditionals, frozen
  return types, issues-order determinism, P1-1 enum TypeError matrix (3 fields ×
  8 bad types), P1-2 numeric int precision (42, 2^53+1, 10^400, float), and
  P2 Schema structure assertions.
- Added `tests/fixtures/fact_candidates/valid_character.json` — a fully fictional
  fixture with two candidates (character + location), four value branches, and a
  relation cross-reference.
- Added `docs/fact_candidate_format.md` documenting the v1 envelope, candidate,
  claim, evidence dimensions, value branches, stable ID rules, and schema/Python
  boundary.


- Added `tests.test_m7_content_scale` for the four-room topology, reciprocal
  exits, unique quest targets, both deterministic branches, CLI rendering, and v7
  save/load after both new encounters. Updated current-content version/count
  assertions and prior-save rejection fixtures for content-pack 0.8.0.
- Added `tests.test_m7_second_encounter` for content counts/references, the
  observation-station-to-spur scenario, CLI quest rendering, and v7 rejection of
  an old 0.6.0 content-pack save. Updated the no-loot test fixture to retain
  valid quest/monster references as the demo grows.
- Added M6 `examine`: no argument, `room`, and `here` render the current room;
  untyped or `item` / `monster` / `character` queries inspect only currently
  visible entities. World returns frozen typed outcomes, resolves exact IDs
  before names, and requires a type qualifier for cross-type ambiguity.
- Added 22 M6 tests covering typed results, room/backpack/current-room visibility,
  hidden rewards, in-memory-only duplicate-name/duplicate-ID ambiguity, reserved
  words, empty and numeric targets, dialogue/death boundaries, stable help/error
  text, registry consistency, and complete failure-state invariance.
- Added the M4 frozen dialogue-effect tagged union: `grant_item`,
  `grant_experience`, `accept_quest`, and `set_flag`. Options require an ordered
  `effects` list; strict loader/schema validation rejects legacy fields, mixed
  branches, invalid values, references, and duplicate targets.
- Added atomic whole-list dialogue effect preflight/execution, World-owned flags,
  typed per-effect outcomes, explicit quest acceptance, and save v7 flags support.
  The original demo adds the ordered elder-Chen effect fixture and the
  `quest_collect_ash_mite_gel` collect task.
- Added the M5 fixed coin shop model, required `shops.json`/shop schema, typed
  `ShopOutcome`/`BuyOutcome`/`SellOutcome`, and `shop`/`buy`/`sell` commands.
  Catalogs are frozen, unlimited content definitions with no mutable stock;
  original_demo starts at 20 coins and sells/buys `item_linglu_pill` for 4/2.
- Added `tests.test_dialogue_effects` and `tests.test_shop` focused contract suites.
- Added the M3 frozen `QuestDefinition` tagged union with exact
  `monster_defeated.target_monster_id`, `reach_room.target_room_id`, and
  `collect_item.target_item_id` plus `required_quantity` branches. Schema and
  loader reject unknown kinds, mixed target fields, invalid references, duplicate
  concrete conditions, and collection quantities outside the target stack limit.
- Added World-owned, stable quest settlement for movement, item pickup, monster
  defeat, and dialogue item grants. `QuestOutcome` collections and task level gains
  are ordered by quest ID; `World.move()` retains its `Room` result and the CLI uses
  additive `move_with_outcome()` results.
- Added local-memory rollback around M3 action plus settlement commits, so a reward
  failure restores the corresponding movement, pickup, combat/loot, or dialogue
  item and state transition.
- Added original-demo `reach_room` and `collect_item` tasks alongside the existing
  monster task, and 31 focused M3 task tests for contracts, ordering, rollback,
  idempotence, dialogue rewards, CLI output, and v6 load behavior.
- Added typed item stacks: frozen `ItemStackDefinition` in content layer,
  mutable `ItemStack` in runtime. `ItemStackDefinition.stack_limit` field (default 1).
  Rooms, inventory, loot, and dialogue rewards use typed stacks.
- Added optional quantity to `take`, `drop`, and `use` commands (suffix syntax:
  `take <item> [qty]`). Default quantity is 1. Numeric style validation rejects
  0, negative, signed, float, hex, binary, octal, inf/nan.
- Added loot preflight in `World.attack()`: combat fails entirely if loot
  cannot be placed (stack overflow or non-stackable duplicate).
- Upgraded save format to version 6 with `inventory_stacks` and `item_stacks`
  fields (list of `{item_id, quantity}` objects). v5 saves rejected by save
  format version check (not by content-pack version check).
- Upgraded content pack to version 0.3.0. Saves referencing content pack
  0.2.7 rejected by content-pack version check (independent of format version).
- Added `docs/engine_completion_milestones.md` M2 status.
- Added 51 new M2 tests in `tests/test_item_stacks.py` covering content
  definition immutability, quantity parsing, take/drop/use with quantities,
  equipment quantity validation, loot preflight, save v6 round-trip, and
  M1 death gate regression.


- Added deterministic defeat recovery: `World.recover()` teleports a dead player
  to the start room with full HP; `_require_alive()` unified death gate covers
  10 mutating World methods; command-layer gate with `_DEAD_ALLOWED` frozenset;
  `RecoverOutcome` typed result; save/load round-trip verified; 55 new tests.
- Added `docs/engine_completion_milestones.md` with M1–M8 roadmap from current
  state to engine feature-complete certification.

- Added optional deterministic `loot_item_id` monster loot with typed
  `LootOutcome`: a valid item is placed in the current room exactly once on the
  monster's first defeat and can then use the existing `take` flow.
- Added strict loot cross-reference validation (existing and initially unplaced
  item, no dialogue-reward conflict, and no duplicate monster owner), plus
  fifteen focused loader, World, CLI, and save/load tests.
- Added the original-demo `item_ash_mite_gel` consumable as the ash mite's loot
  and upgraded that public content pack to 0.2.7; save format remains v5.
- Added `drop <item ID or name>` for moving an unequipped inventory item into
  the current room, with typed `DropOutcome`, stable-ID/unique-name resolution,
  and no save-v5 or content-contract change.
- Added eleven focused drop tests for successful movement, failure invariance,
  equipped hand/body rejection, dialogue preservation, CLI rendering, and
  save/load round trips.
- Added safe named local save slots through `save [slot]` and `load [slot]`.
  Default `default.json` behavior remains compatible; validated slot names cannot
  traverse paths or address Windows reserved device names, and save format remains v5.
- Added nine focused save-slot tests for default compatibility, isolation, invalid
  names, command syntax, world invariance, and named save/load round trips.
- Added focused write-failure tests for `OSError` translation, CLI rendering,
  existing-save preservation, world invariance, and non-I/O error propagation.
- Added read-only `inspect <item ID or name>` with `World.inspect_item()` and
  typed `InspectItemOutcome`.  It exposes only current-room or inventory items,
  preserves all runtime state, and adds no content-pack or save-v5 contract.
- Added nine focused inspection tests for visible/inventory items, inaccessible
  rewards, duplicate names, dialogue invariance, command rendering, and save/load.
- Added read-only `look` rendering for held-item exit gates: gated exits show the
  direction, required item name, stable ID, and held/missing status, while
  ordinary exits remain bare directions.
- Added normalized `ExitDefinition` content contracts and optional
  `required_item_id` gates for room exits, while preserving legacy string exits.
- Added one original demo gate: returning west from 琉草小径 requires the
  dialogue-earned `item_chen_token`; the demo content pack is now 0.2.6 and
  save format remains v5.
- Added focused loading, state-invariance, CLI, and save/load coverage for
  held-item exit gates.
- Added one typed dialogue item-reward effect: `DialogueOption.grant_item_id`,
  `DialogueItemGrant`, and `TalkOutcome.granted_item`.
- Added strict cross-file validation for dialogue rewards and one hidden original
  demo reward item (`item_chen_token`); upgraded the demo content pack to 0.2.5.
- Added a two-layer repository safety gate: current Git candidates (including
  force-added ignored files) plus optional reachable-history path/blob scanning.
- Added limited private-key, GitHub, AWS, and Slack credential-pattern detection;
  this is intentionally not presented as a complete secret scanner.
- Added CI history safety checking and tests for blocked ignored paths, local
  artifacts, credential patterns, and historic blobs.
- Added `docs/production_workflow.md` for the GPT-5.6-sol advisor and Codex
  (GPT-5.6-terra) execution/acceptance workflow.

- Added dialogue system with branching NPC conversations (`dialogues.json`).
- Added `DialogueDefinition`, `DialogueNode`, `DialogueOption` content models.
- Added `Character` and `DialogueState` runtime models.
- Added `World.start_dialogue()`, `World.select_option()`, `World.end_dialogue()`
  domain API.
- Added `TalkOutcome`, `DialogueOptionSummary`, `DialogueEndOutcome` structured
  outcomes.
- Added `talk <character>`, bare integer option selection (ASCII
  `^[1-9][0-9]{0,4}$`, max 5 digits), and `bye` commands.
- Added `look` command displays characters in current room.
- Added `dialogues.json` to required content pack files.
- Added `dialogues` field to `ContentPack` and `DialogueDefinition` validation
  in content loader.
- Added one original NPC (老陈, `character_elder_chen`) with 4-node branching
  dialogue to demo content.
- Added `schemas/dialogue.schema.json` (documentation only, not loaded at
  runtime).
- Added body equipment slot with `defense_bonus` field on `ItemDefinition` and
  `Item`.
- Added `World.effective_defense` property: `player.defense + body defense_bonus`.
- Added `player_defense` keyword argument to `resolve_combat_round`.
- Added body validation in content loader: defense_bonus ≥ 1 required for body slot,
  no attack_bonus or heal_amount allowed.
- Added JSON Schema allOf rules including slot-specific exclusions
  (hand→no defense_bonus, body→no attack_bonus).
- Added 19 new tests covering body loader illegal combos (6), World state
  invariance (5), and save v4 illegal matrix (8).
- Upgraded save format to version 4 with required `equipped.hand` and
  `equipped.body` keys; v3 saves explicitly rejected.
- Upgraded save format to version 5 with required `active_dialogue` field;
  v4 saves explicitly rejected.
- Upgraded content pack version to 0.2.4 (breaking: old 0.2.3 saves rejected).
- Added 77 new tests covering dialogue loading (18), World normal (8),
  World failure (7), state invariance (8), save/load (11), save-time
  validation (3), failure invariance (6), and command integration (16).


- Added equipment system with hand slot, `slot`/`attack_bonus` fields,
  `World.effective_attack`, `equip`/`unequip` commands, save v3, and 49 tests.
- Added consumable system with `heal_amount`, `use` command, save v2, and 17 tests.
- Added `validate` subcommand: `lore2mud validate --content <dir>` validates a
  content pack without starting the game, reports all issues, and exits 0/1.
- Added implicit play fallback for legacy `lore2mud --content <dir>` (no
  subcommand) so existing workflows remain unchanged.
- Added `play` subcommand as the explicit way to start the game.
- Added `UnicodeDecodeError` handling in `_read_json()` so invalid-UTF-8 content
  pack files produce a clean `ContentValidationError` instead of a traceback.
- Added 23 new tests covering validate success/error paths, encoding errors,
  legacy/explicit play with --player-name/--save-dir backward compatibility,
  unknown-argument rejection, OSError unified format, and argparse error handling.
- Added deterministic quest flow: auto-accept in trigger room, monster-defeat
  condition, instant reward via `grant_experience`, `quests` command, quest hints
  in `look`, and quest completion text in `attack` output.
- Added `QuestState` runtime model and `QuestOutcome` carried by `AttackOutcome`.
- Upgraded save format to version 2 with required `quest_states` field; version 1
  saves are cleanly rejected.
- Upgraded content pack version to 0.2.0.
- Added content loader validation for quest `trigger_room_id`, `target_monster_id`,
  `reward_experience`, and duplicate target monster rejection.
- Added 21 new quest tests covering content loading, auto-accept, completion,
  reward-once, non-target monster, quests command, and save round-trip.
- Added versioned local save/load with atomic writes (`save` and `load` commands).
- Added `SaveLoadService` with strict validation of untrusted save data: format
  version, content-pack identity, room/monster key sets, reference integrity,
  duplicate detection (including inventory duplicates), inventory capacity,
  numeric range checks, required room state fields, and bool-as-int rejection.
- Added `pack_version` field to `World`, initialized from `ContentPack.version`.
- Added `--save-dir` CLI argument (default: `saves/`).
- Added 54 new tests covering round-trip state, validation of malformed saves,
  atomic write behavior, and command integration.
- Added an installable Python 3.11+ package with `lore2mud` and
  `python -m lore2mud` command-line entry points.
- Added authoritative rooms, player state, inventory, deterministic combat and
  experience progression.
- Added strict JSON content-pack loading with stable ID, unknown-field and
  cross-file reference validation.
- Added an original three-room demo with pickup items, equipment, and a monster.
- Added conservative novel chapter splitting and deterministic manifest generation.
- Added repository safety scanning, private-content ignore rules and core tests.
- Added Chinese project documentation, Hermes rules, GitHub Actions, Issue config,
  pull request template and MIT license.
- Added compact project handoff files for future Agent sessions.

### Fixed

- Closed all five findings raised during parallel integration acceptance: bounded
  oversized `Content-Length` parsing, portable Forge junction mocks, orderly Windows
  POST rejection, reachable structured browser recovery after defeat, and 320px
  dead-state overflow. Repairs are in `a27b363` and `a172a82` (DEC-0067, DEC-0068).
- Phase 1.0 P1-1: enum fields (`entity_type`, `source_support`, `certainty`) no longer
  leak `TypeError` on unhashable JSON types (list, dict). All JSON-compatible types
  are now caught and reported as `FactCandidateValidationError`.
- Phase 1.0 P1-2: `NumericValue.number` is now `int | float`. Integers are preserved
  exactly (no `float()` conversion), eliminating precision loss for large ints and
  `OverflowError` for huge ints. `math.isfinite` check applies only to floats.
- Phase 1.0 P2: Schema uses `if/then/else` for `source_support` → `inference_basis`
  conditional, and `\\S` pattern for non-blank strings instead of `minLength` alone.
- Phase 1.1 P1: `source_encoding`, scan five null fields, `previous_id`/`next_id`
  now require explicit key presence; missing keys raise
  `ChapterManifestValidationError` instead of silently defaulting.
- Phase 1.1 P2: Schema restructured with root `if/then/else` on `source_encoding`
  (null→scan_entry, encoding→primary_entry), typed `oneOf` constraints for
  previous_id/next_id, and conditional field requirements for primary vs. scan.
- Phase 1.1 Schema P1: entry_base.properties now lists all 12 required fields,
  fixing additionalProperties:false rejection of the 5 conditional fields
  (source_chapter_label, source_title, volume_label, source_offset, source_line).


- Fixed `World.buy()` so an empty inventory stack cannot be created above the
  item's `stack_limit`. The rejection happens before coins, inventory, quests,
  or dialogue state mutate; the M5 regression covers both World and CLI buy ×6
  rejection followed by a valid v7 save/load.

### Changed

- Replaced the active GPT-5.6-sol advisor + Hermes executor handoff with a
  Codex-only GPT-5.6-sol workflow. Codex now owns planning, implementation,
  verification, and handoff; independent acceptance remains a separate fresh
  Codex review task or clean-context pass. Historical Hermes attribution is unchanged.
- Expanded the fully original demo to content-pack 0.8.0 with M7.2: four more
  rooms, the two new monsters `monster_mist_crawler` and `monster_prism_sentinel`,
  and their unique-target `monster_defeated` quests. The demo now reaches eight
  rooms, four monsters, and seven quests. Save format remains v7; saves bound to
  content-pack 0.7.0 are rejected by the existing content-pack version check.
- Expanded the fully original demo to content-pack 0.7.0 with the M7.1 second
  encounter: the fourth room `room_shattered_signal_spur`, the second monster
  `monster_spark_hound`, and its existing-kind `monster_defeated` quest. Save
  format remains v7; saves bound to content-pack 0.6.0 are rejected by the
  existing content-pack version check.
- Replaced separately maintained command routing, summary help, and death
  allowlist metadata with one frozen `CommandSpec` registry. `help [command]`
  now reports syntax, parameters, context restrictions, and death restrictions;
  DEC-0020 death-gate ordering and dialogue-only bare-number behavior remain
  compatible.
- Earlier documented the GPT-5.6-sol advisor + Hermes executor workflow for
  fact-layer slices. DEC-0059 now supersedes that active workflow while preserving
  its historical implementation and acceptance attribution.
- Upgraded the original demo content pack to 0.6.0 and the local save format to v7.
  v6 saves are rejected by format version; 0.4.0 content-pack saves are rejected by
  the content-pack version check.
- Moved command-layer death gate before dialogue routing in `CommandProcessor`
  so that dead players cannot invoke `_select_option` or `_bye` through bare
  numbers or `bye` when `active_dialogue` is set (DEC-0020).


- Existing saves for original-demo content pack 0.2.6 are rejected by the
  existing content-pack version check; save JSON format remains v5.
- `SaveLoadService.save()` now translates filesystem `OSError` into a chained
  `SaveLoadError`, so the `save` command reports a normal failure instead of
  leaking a write exception. Save format v5 and atomic-write behavior are unchanged.
- `World.move()` now checks a required inventory item before changing room,
  quest, or dialogue state; passing a gate does not consume the item.
- Dialogue selection now atomically awards a validated item before advancing or
  ending, and rejects a full inventory or duplicate reward without state changes.
- Tightened save format v5 loading: top-level, `content_pack`, `player`, room, and
  monster objects now reject unknown fields before a replacement `World` is built.
- Replaced the former agent-specific workflow reference with the production workflow and
  documented `dialogues.json` as a required content-pack file.

- `equip` now routes by `item.slot` ("hand" or "body") with strict tagged-variant
  validation before any state change.
- `unequip` accepts optional slot parameter; bare `unequip` defaults to hand.
- `UnequipOutcome` now carries both `attack_bonus` and `defense_bonus`.
- `World.use()` now rejects items in either equipped slot.
- `status` command displays both effective_attack and effective_defense with
  base breakdown.
- Upgraded content pack version to 0.2.3 (breaking: old 0.2.2 saves rejected).


- Extended the novel pipeline with explicit UTF-8/GBK/GB18030 input encoding,
  chapter-only split points, volume metadata, stable occurrence IDs, and manifest v2.
- Added pipeline tests for encoding, duplicate chapter labels, volume propagation,
  metadata fields, strict decoding, and source reconstruction.

### Verified

- GPT-5.6-sol independently accepted five-domain integration candidate `a172a82`
  GO with no P0-P3 findings (DEC-0068). Linux Python 3.11/3.12 serial and 3.13
  xdist each passed 1248 tests with 3 skips; Windows pytest serial/xdist each passed
  1243 with 8 skips, and unittest ran 1251 `OK` with 8 skips. Final Web focused
  tests passed 35/35; Web plus packaging passed 47/48 with one expected toolchain
  skip. Ruff, Pyright, Node syntax, compileall, validation, safety, fsck, diff,
  responsive browser recovery, and both repository-external delivery candidates
  passed. PyInstaller SHA-256 is
  `a11458b491dd862618cada085df895b9db8bb42e73c992eb3a2d75acb9807c75`;
  zipapp SHA-256 is
  `41c85e35cd750a5cdb964bd9010ac8634d11699f5dc0f40159e377f687a176bc`.
- GPT-5.6-sol independently accepted L2W-5 registry inspection GO with no P0-P3
  findings (DEC-0066): 49 focused (1 skip), 172 regression (3 skips), 1154 full
  unittest cases (4 skips), compileall, Schema/fixture checks, original-demo
  validation, history safety, fsck, diff, and 4144-byte external golden CLI passed.
- GPT-5.6-sol independently accepted Phase 1.0 fact-candidate validation as GO
  with no remaining findings (DEC-0039). Initial implementation `e2b8136` (119
  focused, 718 full) was NO-GO; focus fix `3442d2d` closed P1-1 (enum TypeError),
  P1-2 (numeric int precision), P2 (Schema constraints). Accepted evidence: 131
  focused tests, 730 full tests, compileall, original-demo validation, safety
  history scan, and diff check. Local HEAD=`3442d2d`, `origin/main`=`afdb235`,
  ahead/behind=2/0, not pushed.
- GPT-5.6-sol independently accepted Phase 1.1 manifest validation and candidate
  source binding as GO with no remaining findings (DEC-0047). Implementation
  `c69eeee` + 4 focus-fix rounds (`2781e7c`, `ecfca89`, `e350ee5`, `ca34d7b`,
  `ec6bc62`, `56edcb2`) closed all P1/P2 findings. Accepted evidence: 237 focused
  tests, 817 full tests, compileall, original-demo validation, safety history
  scan, git fsck, diff check, Schema primary/scan path verification, and
  build_manifest integration all passing. Local HEAD=`56edcb2`,
  `origin/main`=`1585a98`, ahead/behind=7/0, not pushed.
- GPT-5.6-sol independently accepted Phase 1.2 fact-review validation and
  claim-level review states as GO with no remaining findings (DEC-0051).
  Implementation `80fd916` + 2 P2 doc fixes (`ceae065`, `e742d20`) closed
  all findings. Accepted evidence: 43 fact-review focused, 280 Phase 1.2+1.1+1.0
  regression, 860 full tests, compileall, original-demo validation, safety
  history scan, git fsck, and diff check all passing. Local HEAD=`e742d20`,
  `origin/main`=`a55c7d8`, ahead/behind=3/0, not pushed.
- GPT-5.6-sol independently accepted L2W-1 canon draft promotion as GO with
  no remaining findings (DEC-0054). Initial implementation `2941641`. Focus
  fix `1f01207` closed P1-1 through P1-5 and P2. Accepted evidence: 50 canon
  focused, 910 full tests, compileall, original-demo validation, safety
  history scan, git fsck, and diff check all passing. Local HEAD=`1f01207`,
  `origin/main`=`a52b21c`, ahead/behind=2/0, not pushed.
- GPT-5.6-sol independently accepted L2W-2 micro content pack compilation
  as GO with no remaining code findings (DEC-0058). Initial implementation
  `e05c946`. Three rework rounds (`2cc6696`, `389c0b0`, `f7a977a`) closed
  all P1/P2 findings. Accepted evidence: 72 adaptation focused (1 skipped),
  982 full tests (1 skipped), golden fixture byte identity, flush+fsync,
  MicroContentPack type safety, Schema stable IDs, real subprocess CLI, and
  loader validation all pass. Local HEAD=`f7a977a`, `origin/main`=`b9cee1e`,
  ahead/behind=4/0, not pushed.


- GPT-5.6-sol independently accepted M8 as GO after focused review: the Git-snapshot
  P2 is closed and there are no new findings. This closes the M1–M8 public-engine
  roadmap scope only; it does not authorize M9, other feature work, or private novel
  fact-layer access. The technical baseline is `f486e12`, the audit record is
  `6510e2d`, and the P2 correction is `6502a72`; the acceptance records 599 full
  unittest cases, compileall, content validation, history safety, diff checking,
  Git fsck, and the existing focused/save/CLI evidence as passing.
- Codex completed the read-only M8 public-engine audit baseline on `f486e12`
  after the push was confirmed: 599 full unittest cases, compileall, original-demo
  validation, `check_repo_safety.py --history`, `git diff --check`, and
  `git fsck --full --no-dangling` passed. A real CLI flow completed the M7.2
  branches, saved and loaded v7/0.8.0 state, and a fresh real CLI flow proved
  prism-sentinel death → `recover` → v7 save/load. `main`, `origin/main`, and the
  directly queried remote `main` all point to `f486e12`; M8 independent acceptance
  remains pending.
- GPT-5.6-sol independently accepted M7.2 and the complete M7 milestone as GO with
  no findings (2026-07-30). Relative to `5497859`, `147633e` is one 22-file
  content/test/public-document commit with zero `src/`, Schema, dependency, or
  private-material-path changes. Accepted evidence: 23 M7/loot focused tests, 599
  full unittest cases, topology and unique-target audits, compileall, original-demo
  validation, history safety, `git diff --check`, and real CLI/save plus defeat
  recovery. The v7/0.8.0 save confirmed the player in a new room, both new monsters
  at HP 0 and removed, and both new quests complete; direct remote `main` was
  `f0acd3f` at acceptance and no push occurred.
- Codex locally verified M7.2 before its independent acceptance: 8 M7 scenario tests,
  15 loot regressions, and 599 full unittest cases passed, along with compileall,
  original-demo validation, history safety, and `git diff --check`. An
  external-save-directory CLI flow equipped the starting gear, cleared both prior
  encounters and both new branches, then save/loaded v7/0.8.0 state at the beacon
  with the two new quests complete and both new monsters removed. The later M7.2/M7
  independent acceptance is recorded above.
- GPT-5.6-sol independently accepted M7.1 as GO with no findings (2026-07-30).
  Relative to `086cda8`, `9786325` is one 22-file `+333/-55` commit with zero
  `src/`, `schemas/`, dependency-file, or private-path changes. Accepted evidence
  includes 19 M7/loot focused tests, 595 full unittest cases, compileall,
  original-demo validation, history safety, baseline `git diff --check`, and a real
  CLI/save v7 flow. The saved v7/0.7.0 state places the player in the new room,
  removes the defeated hound at HP 0, and marks `quest_clear_spark_hound` complete.
  Direct remote `main` remained `f0acd3f`; no push occurred. This GO closes M7.1
  only; M7 remains in progress at 4/8 rooms, 2/4 monsters, and five quests.
- Codex locally verified M7.1 (not independent acceptance): 19 M7/loot focused
  tests and 595 full unittest cases passed, along with compileall, original-demo
  validation, history safety, and `git diff --check`. An external-save-directory
  CLI flow reached the new room, defeated both monsters, completed
  `quest_clear_spark_hound`, and save/loaded v7/0.7.0 state. M7 remains in
  progress; the subsequent independent acceptance is recorded above.
- GPT-5.6-sol independently accepted M6 as GO with no findings, using
  `53a071f` as the baseline. Accepted evidence is 22 M6 tests, 187 focused
  M6/inspect/commands/recover/dialogue regressions, and 591 full unittest cases;
  compileall, original-demo validation, history safety, `git diff --check`, the
  11-file scope relative to `f0acd3f`, and an external-save-directory CLI/save v7
  flow also passed. The GO closes M6 only; M7 and push still require separate
  project-owner authorization.
- GPT-5.6-sol independently accepted the integrated M4+M5 slice as GO. The
  focused re-review closed the first-review M5 empty-stack `stack_limit` P1 in
  `59ca3cd` with no findings; accepted evidence is 25 focused M4/M5 tests, 569
  full unittest cases, compileall, original-demo validation, history safety,
  `git diff --check`, and the external-save-directory CLI rejection/save/load
  flow. M4 effects do not replay, and v6/old-content saves remain rejected.
- Codex locally verified the M5 P1 correction (not independent acceptance): 569
  full unittest cases, 12 M4 effect cases, and 13 M5 shop cases passed, along
  with compileall, original-demo validation, history safety, `git diff --check`,
  and an external-save-directory CLI flow that preserves 26 coins and an empty
  inventory after rejected buy ×6, then save/loads successfully.
- Codex completed local M4+M5 verification (not independent acceptance): 568 full
  unittest cases, 12 `tests.test_dialogue_effects` cases, 12 `tests.test_shop`
  cases, the M1–M3 regression suite, compileall, content validation, history safety,
  diff checking, and external-save-directory CLI flows including v6/0.6 and
  v7/0.4 rejection cases.
- GPT-5.6-sol independently accepted the M3 typed quest-condition slice as GO.
  The focused re-review of the M3 implementation and its `5527faa` handoff
  correction closed the single P2 `PROJECT_STATE.md` finding with no remaining
  findings; the accepted evidence is 540 full unittest cases, 31 M3 task cases,
  56 M2 stack regressions, compileall, original-demo validation, history safety,
  `git diff --check`, and the external-save-directory CLI save/load flow.
- Codex completed local M3 verification (not independent acceptance): 540 full
  unittest cases, 31 `tests.test_quest` cases, 56 preserved M2 stack cases,
  compileall, original-demo validation, history safety scan, `git diff --check`,
  and an external-save-directory CLI flow covering all three task kinds, combat
  loot, save, post-save pickup, and load restoration.
- GPT-5.6-sol independently accepted M2 typed stacks as GO. Evidence: 530 full
  unittest cases, 56 `tests.test_item_stacks` cases, compileall, original-demo
  validation, history safety scan, `git diff --check`, and the quantity pickup,
  injured use ×2 restoring to 20/20, combat loot, drop, and save/load CLI flow.


- Validated the private external corpus split without adding its source or chapters
  to the public repository; the original source remained unchanged.

## [0.2.3] - 2026-07-28
- Body equipment slot with defense_bonus and bronze scale mail.

## [0.2.2] - 2026-07-28
- Hand equipment slot with attack_bonus and crystal blade.

## [0.2.1] - 2026-07-28
- Consumable items with heal_amount and linglu pill.

## [0.2.0] - 2026-07-28
- Deterministic quest flow, versioned save v2, content pack versioning.
