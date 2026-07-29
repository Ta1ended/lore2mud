# Changelog

## [Unreleased]

### Changed

- Documented the current execution workflow: GPT-5.6-sol is the scope/architecture
  reviewer and independent acceptor; Codex is the sole executor; the project owner
  manually transfers prompts and completion reports between the two conversations.
- Moved command-layer death gate before dialogue routing in `CommandProcessor`
  so that dead players cannot invoke `_select_option` or `_bye` through bare
  numbers or `bye` when `active_dialogue` is set (DEC-0020).

### Added

- Added typed item stacks: frozen `ItemStackDefinition` in content layer,
  mutable `ItemStack` in runtime. `ItemDefinition.stack_limit` field (default 1).
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

### Verified

- GPT-5.6-sol independently accepted M2 typed stacks as GO. Evidence: 530 full
  unittest cases, 56 `tests.test_item_stacks` cases, compileall, original-demo
  validation, history safety scan, `git diff --check`, and the quantity pickup,
  injured use ×2 restoring to 20/20, combat loot, drop, and save/load CLI flow.

### Added

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

### Changed

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

### Added (previous unreleased)

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

### Changed (previous unreleased)

- Extended the novel pipeline with explicit UTF-8/GBK/GB18030 input encoding,
  chapter-only split points, volume metadata, stable occurrence IDs, and manifest v2.
- Added pipeline tests for encoding, duplicate chapter labels, volume propagation,
  metadata fields, strict decoding, and source reconstruction.

### Verified

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
