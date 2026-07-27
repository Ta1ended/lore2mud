# Changelog

## [Unreleased]

### Added

- Added equipment system with `slot` and `attack_bonus` fields on `ItemDefinition`
  and `Item`; `slot="hand"` enables equipping via `equip <item>`.
- Added `EquippedItems` model with `hand: str | None` slot.
- Added `World.effective_attack` property: `player.attack + hand attack_bonus`.
- Added `World.equip()` and `World.unequip()` methods that only modify
  `equipped.hand`, never touching `player.attack`.
- Added `EquipOutcome` and `UnequipOutcome` dataclasses.
- Added `equip` and `unequip` commands to `CommandProcessor`.
- Added equipped-rejected check in `World.use()` (before heal_amount check).
- Added `player_attack` keyword argument to `resolve_combat_round` for
  equipment-aware damage calculation.
- Added `item_crystal_blade` (晶刃, slot=hand, attack_bonus=3) to demo content.
- Upgraded save format to version 3 with required `equipped` field; v2 saves
  explicitly rejected.
- Added strict equipped validation: slot must be "hand", item must exist in
  content pack and inventory, must have attack_bonus >= 1, must not have
  heal_amount.
- Added content loader validation for slot/attack_bonus cross-field rules
  (slot requires bonus, bonus requires slot, no slot+heal_amount combo).
- Added 49 new tests across test_equipment.py, test_save.py, test_consumable.py,
  test_commands.py covering content loading, equip/unequip, failure paths, combat
  integration, upgrade interaction, save round-trip, equipped validation, schema
  rules, and CLI equipment smoke.

### Changed

- Upgraded content pack version to 0.2.2 (breaking: old 0.2.1 saves rejected).
- Updated `status` command to display `effective_attack` with base breakdown.
- Updated `resolve_combat_round` to accept optional `player_attack` parameter.
- Updated `World.from_content_pack()` and `SaveLoadService` to reconstruct
  Item with `slot` and `attack_bonus`.
- Updated `test_content_loader.py` item count (2→3) and `test_save.py`
  version (0.2.1→0.2.2) + equipped field assertions.
- Updated demo content pack, README, schemas, and docs.

### Added (previous unreleased)

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
- Added an original three-room demo with one pickup item and one monster.
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
