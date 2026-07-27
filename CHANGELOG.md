# Changelog

## [Unreleased]

### Added

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

### Changed

- Extended the novel pipeline with explicit UTF-8/GBK/GB18030 input encoding,
  chapter-only split points, volume metadata, stable occurrence IDs, and manifest v2.
- Added pipeline tests for encoding, duplicate chapter labels, volume propagation,
  metadata fields, strict decoding, and source reconstruction.

### Verified

- Validated the private external corpus split without adding its source or chapters
  to the public repository; the original source remained unchanged.
