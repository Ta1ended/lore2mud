# Changelog

## [Unreleased]

### Added

- Added body equipment slot with `defense_bonus` field on `ItemDefinition` and `Item`.
- Added `item_bronze_scale_mail` (铜鳞甲, slot=body, defense_bonus=3) to demo content.
- Added `World.effective_defense` property: `player.defense + body defense_bonus`.
- Added `player_defense` keyword argument to `resolve_combat_round`.
- Added body validation in content loader: defense_bonus ≥ 1 required for body slot,
  no attack_bonus or heal_amount allowed.
- Added JSON Schema allOf rules for body/heal/exclusive bonus constraints.
- Added 20 new tests across test_equipment.py covering body equip/unequip,
  dual-slot, combat with defense, upgrade interaction, save round-trip, and
  unequip command variants.
- Upgraded save format to version 4 with required `equipped.hand` and
  `equipped.body` keys; v3 saves explicitly rejected.

### Changed

- `equip` now routes by `item.slot` ("hand" or "body") with strict tagged-variant
  validation before any state change.
- `unequip` accepts optional slot parameter; bare `unequip` defaults to hand.
- `UnequipOutcome` now carries both `attack_bonus` and `defense_bonus`.
- `World.use()` now rejects items in either equipped slot.
- `status` command displays both effective_attack and effective_defense with
  base breakdown.
- `EquipOutcome` and `UnequipOutcome` both carry `attack_bonus` and
  `defense_bonus` (default 0).
- Upgraded content pack version to 0.2.3 (breaking: old 0.2.2 saves rejected).
- Updated `test_content_loader.py` item count (3→4) and `test_save.py`
  version (0.2.2→0.2.3) + equipped field assertions.

### Added (previous unreleased)

- Added equipment system with hand slot, `slot`/`attack_bonus` fields,
  `World.effective_attack`, `equip`/`unequip` commands, save v3, and 49 tests.
- Added consumable system with `heal_amount`, `use` command, save v2, and 17 tests.
- Added `validate` subcommand, `play` subcommand, deterministic quest flow,
  versioned save/load with atomic writes, and all preceding features.

### Changed (previous unreleased)

- Upgraded content pack versions through 0.2.0→0.2.1→0.2.2→0.2.3.

### Verified

- 229 tests passed (2026-07-28).
- Repository safety check passed.
- compileall passed.
- Content pack validation passed.
- git diff --check clean.
