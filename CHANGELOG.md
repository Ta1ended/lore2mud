# Changelog

## [Unreleased]

### Added

- Added `use <item>` command for consuming usable items from inventory.
- Added `heal_amount: int | None` field to `ItemDefinition` and `Item`; a positive
  integer makes the item usable (heals HP and is consumed), `None` means unusable.
- Added `UseOutcome` dataclass and `World.use()` method with deterministic healing
  logic: `min(heal_amount, max_hp - hp)`, item removed from inventory after use.
- Added boundary checks: full HP rejects use (no consume), HP=0 rejects use
  (no implicit revive).
- Added `item_linglu_pill` (灵露丸, heal_amount=10) to the original demo content
  pack; placed in the starting room alongside `item_spark_lantern`.
- Added 17 new tests covering content loading, normal use, partial heal, failure
  paths (non-usable, not in inventory, full HP, dead player, empty args, display
  name), and save round-trip (heal_amount survives load, used pill gone after
  reload, old version save rejected).
- Added `heal_amount` to `item.schema.json` and `docs/content_pack_format.md`.

### Changed

- Upgraded content pack version to 0.2.1 (breaking change: old 0.2.0 saves are
  rejected by `SaveLoadService` version check).
- Updated `World.from_content_pack()` and `SaveLoadService._validate_and_build_world()`
  to pass `heal_amount` when constructing `Item` objects.
- Updated `test_content_loader.py` item count assertion (1→2) and
  `test_save.py` version assertion (0.2.0→0.2.1).
- Updated `original_demo/README.md` with consumable in the demo flow.

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
