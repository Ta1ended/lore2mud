# Changelog

## [Unreleased]

### Added

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
