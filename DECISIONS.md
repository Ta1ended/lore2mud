# Decisions

## DEC-0001: Standard-library Python starter

- Date: 2026-07-27
- Status: Accepted
- Context: The starter must be easy for a local Agent to inspect, install and test on
  Python 3.11+ without a large framework surface.
- Decision: Use a `src` layout, `pyproject.toml`, standard-library runtime and
  `unittest`; keep setuptools only as the build backend.
- Consequences: Installation and CI remain small, while advanced JSON Schema,
  database and network features require later explicit decisions.
- Evidence: `pyproject.toml`, `src/lore2mud/`, `tests/`.
- Supersedes: None.

## DEC-0002: Canon facts remain outside game rules

- Date: 2026-07-27
- Status: Accepted
- Context: Public code must not bundle third-party novels or confuse source facts with
  invented balance values.
- Decision: Store canon facts in an ignored private layer; game entities may only
  point to them through optional `canon_ref` and `source_chapters`, with adaptation
  choices documented separately.
- Consequences: The engine runs without novel data, and future extraction tools need
  an explicit canon provider and review flow.
- Evidence: `src/lore2mud/content/models.py`,
  `docs/content_pack_format.md`, `.gitignore`.
- Supersedes: None.

## DEC-0003: Deterministic authoritative vertical slice

- Date: 2026-07-27
- Status: Accepted
- Context: The first playable version needs stable scenario tests and a clear location
  for all state changes.
- Decision: Keep mutable state in `World`, let commands submit intent, and implement
  deterministic combat and progression in separate domain services.
- Consequences: Tests are repeatable and future clients can reuse the same rules;
  randomness and multiplayer concurrency are intentionally deferred.
- Evidence: `src/lore2mud/engine/world.py`, `src/lore2mud/combat/`,
  `src/lore2mud/progression/`, `tests/test_commands.py`.
- Supersedes: None.

## DEC-0004: Versioned private preprocessing pipeline

- Date: 2026-07-27
- Status: Accepted
- Context: The private source uses a legacy Chinese encoding, has volume headings,
  and repeats some original chapter numbers.
- Decision: Decode with an explicit encoding, use chapter occurrence order for stable
  IDs, track volume labels as metadata, and verify reconstruction before any model
  extraction.
- Consequences: Original chapter labels remain display/source metadata; private
  processing can be repeated safely without overwriting chapters.
- Evidence: `pipeline/split_novel.py`, `pipeline/build_manifest.py`,
  `tests/test_pipeline.py`, private external processing report.
- Supersedes: None.

## DEC-0005: Pause and resume through repository handoff files

- Date: 2026-07-27
- Status: Accepted
- Context: Long-running corpus work and Agent sessions must be stoppable without
  losing the next action or accidentally continuing expensive processing.
- Decision: Treat `PROJECT_STATE.md`, `NEXT_TASK.md`, `DECISIONS.md`,
  `CHANGELOG.md`, and `PROJECT_MEMORY.md` as the restart contract. A paused project
  has no implicit background work; resumption starts only from the single task in
  `NEXT_TASK.md`.
- Consequences: A fresh session can resume from files and repository evidence, while
  novel scans and model calls never restart automatically.
- Evidence: `PROJECT_MEMORY.md`, `PROJECT_STATE.md`, `NEXT_TASK.md`.
- Supersedes: None.

## DEC-0006: Versioned local save with atomic writes and strict validation

- Date: 2026-07-28
- Status: Accepted
- Context: The playable loop loses all mutable state on exit. Persistence is needed
  before adding more game systems.
- Decision: Implement a `SaveLoadService` that serializes all mutable World state
  (player, room placements, monster HP) to a versioned JSON file. Use a temp file
  plus `os.replace()` for atomic writes. Validate untrusted saves strictly: format
  version, content-pack identity, key-set equality, reference integrity, duplicate
  detection, numeric ranges, and bool-as-int rejection. Keep serialization in a
  dedicated service layer, not in `CommandProcessor`.
- Consequences: Players can save and load across sessions. Content-pack upgrades
  cleanly reject incompatible saves. Future multi-slot support can reuse the service.
- Evidence: `src/lore2mud/engine/save.py`, `tests/test_save.py`,
  `src/lore2mud/engine/commands.py`, `src/lore2mud/cli.py`.
- Supersedes: None.

## DEC-0007: Validate CLI with backward-compatible subcommands

- Date: 2026-07-28
- Status: Accepted (revised)
- Context: Content packs need validation without starting the game loop. The
  existing CLI uses `lore2mud --content <dir>` with `--player-name` and
  `--save-dir`. Breaking this would disrupt documented workflows. Additionally,
  `parse_known_args` silently ignores unknown flags, which is unacceptable.
- Decision: Pre-scan argv for a recognised subcommand. If none is found, inject
  `"play"` at the front of argv, then use `parse_args` (not `parse_known_args`)
  so unknown flags always fail. The `validate` subcommand calls
  `validate_content_pack()` (the public validation entry point). Catch
  `OSError` separately and use the unified `[ERROR] 内容包校验失败:` format.
  Fix `_read_json()` to catch `UnicodeDecodeError`.
- Consequences: Old commands (`--content`, `--player-name`, `--save-dir`) all
  keep working. Unknown flags are always rejected. The public validation API is
  used rather than the internal loader. Error output is uniform.
- Evidence: `src/lore2mud/cli.py`, `tests/test_cli_validate.py`,
  `src/lore2mud/content/loader.py`.
- Supersedes: None.

## DEC-0008: Deterministic quest flow with auto-accept

- Date: 2026-07-28
- Status: Accepted
- Context: The engine needs a quest system before implementing items, equipment,
  or dialogue. The demo world has one room, one monster, and one item — ideal for
  a single vertical-slice quest.
- Decision: (a) Auto-accept quests when the player enters the trigger room (no
  explicit `accept` command). (b) Let `World.attack()` evaluate quest conditions
  and grant rewards — `CommandProcessor` only renders outcomes. (c) Limit each
  `target_monster_id` to one quest (enforced by the content loader) to avoid
  ambiguity about which quest completes first. (d) Upgrade save format to version
  2 with a required `quest_states` field; cleanly reject version 1 saves.
- Consequences: Quest state is authoritative in `World`, serializable, and
  validated on load. Adding more quests requires only content JSON changes. The
  one-target-one-quest constraint simplifies completion logic but will need
  revisiting if shared-target quests are ever needed.
- Evidence: `src/lore2mud/engine/world.py`, `src/lore2mud/engine/save.py`,
  `src/lore2mud/engine/commands.py`, `tests/test_quest.py`.
- Supersedes: None.

## DEC-0009: Consumable items with single heal_amount field

- Date: 2026-07-28
- Status: Accepted
- Context: The quest system is complete; the next step before equipment is a
  simple item with a deterministic on-use effect (heal HP). The design must avoid
  illegal field combinations and keep the `World` domain layer as the single
  authority for state changes.
- Decision: (a) Use a single optional `heal_amount: int | None` field on
  `ItemDefinition` and `Item` instead of a `consumable` boolean plus separate
  heal value — `None` means unusable, positive int means heal-and-consume.
  (b) Implement `World.use(item_query)` returning a structured `UseOutcome`
  (item_id, item_name, healed_amount); text rendering stays in `CommandProcessor`.
  (c) Reject use at full HP (no consume) and at HP=0 (no implicit revive).
  (d) Content pack version bumps to 0.2.1; old 0.2.0 saves are cleanly rejected
  by the existing version check in `SaveLoadService`. (e) Save format stays at
  version 2 — item properties are reconstructed from the content pack on load,
  so no new serialization fields are needed.
- Consequences: Items are simpler to define (one optional field). The version bump
  breaks backward compatibility with 0.2.0 saves, which is acceptable and
  documented. Future equipment can extend the same pattern with additional optional
  fields on `ItemDefinition`.
- Evidence: `src/lore2mud/content/models.py`, `src/lore2mud/engine/world.py`,
  `src/lore2mud/engine/save.py`, `src/lore2mud/engine/commands.py`,
  `examples/original_demo/items.json`, `tests/test_consumable.py`.
- Supersedes: None.

## DEC-0010: Equipment system with effective_attack and save v3

- Date: 2026-07-28
- Status: Accepted
- Context: The consumable system is complete; the next step is equippable items
  that modify player stats. The design must avoid mutating base stats, support
  clean save/load round-trips, and maintain backward-compatible version checks.
- Decision: (a) `player.attack` stores base/leveled attack; never modified by
  equipment. (b) `World.effective_attack` dynamically computes
  `player.attack + hand attack_bonus`. (c) `equip`/`unequip` only modify
  `equipped.hand`, never touching `player.attack`. (d) Combat uses
  `effective_attack` via `player_attack` parameter on `resolve_combat_round`.
  (e) Save format upgraded to v3 with required `equipped` field; v2 explicitly
  rejected. (f) Equipment items stay in inventory (simplest model). (g) Content
  pack version bumps to 0.2.2; old 0.2.1 saves rejected. (h) Loader rejects
  illegal combos: slot+heal_amount, attack_bonus without slot, slot without
  attack_bonus. (i) `World.use()` rejects equipped items at domain layer.
- Consequences: Base stats are preserved across equip/unequip cycles. Save
  round-trips are clean because attack includes no equipment bonus. The v3 bump
  breaks backward compatibility with 0.2.1 saves, which is acceptable and
  documented. Future body/head slots can extend `EquippedItems` with the same
  pattern.
- Evidence: `src/lore2mud/engine/world.py`, `src/lore2mud/engine/save.py`,
  `src/lore2mud/engine/commands.py`, `src/lore2mud/combat/service.py`,
  `src/lore2mud/inventory/models.py`, `tests/test_equipment.py`.

 ## DEC-0011: Body equipment slot with defense_bonus and save v4

 - Date: 2026-07-28
 - Status: Accepted
 - Context: The hand equipment slot is complete; extending to body validates the
 multi-slot design and adds defensive capabilities.
 - Decision: (a) Add `defense_bonus: int` field to `ItemDefinition` and `Item`.
 (b) `EquippedItems` gets `body: str | None`. (c) `World.effective_defense`
 dynamically computes `player.defense + body defense_bonus`. (d) `equip` routes
 by `item.slot` ("hand" or "body") with strict tagged-variant validation before
 any state change — heal_amount is None, slot matches, bonus ≥ 1, no conflicting
 bonus. (e) `unequip` accepts optional slot parameter; bare `unequip` defaults
 to hand for backward compatibility. (f) `resolve_combat_round` gains
 `player_defense` parameter; counter damage uses it while writing to real
 `Player.hp`. (g) Save format upgraded to v4 with required `equipped.hand` and
 `equipped.body` keys; v3 explicitly rejected. (h) Loader rejects all illegal
 combos: mixed bonuses, slot+heal, wrong slot bonus, null values. (i) Content
 pack version bumps to 0.2.3.
 - Consequences: `player.attack` and `player.defense` remain base values (含升级，
 不含装备). Equip/unequip are symmetric for both slots. The v4 bump breaks
 backward compatibility with 0.2.2 saves. Future slots (head, ring) follow the
 same pattern.
 - Evidence: `src/lore2mud/engine/world.py`, `src/lore2mud/engine/save.py`,
   `src/lore2mud/engine/commands.py`, `src/lore2mud/combat/service.py`,
   `src/lore2mud/content/loader.py`, `tests/test_equipment.py`.

 ## DEC-0012: Dialogue system with stateful World.active_dialogue

 - Date: 2026-07-28
 - Status: Accepted
 - Context: Equipment and combat are complete; the engine needs narrative depth
   through NPC dialogue before adding more complex content. The design must
   follow the existing pattern of World-as-authority and CommandProcessor-as-
   renderer.
 - Decision: (a) Content models: `DialogueDefinition` with nested `DialogueNode`
   and `DialogueOption` in `dialogues.json`. `CharacterDefinition.room_id` is
   the sole location source (no `Room.character_ids`). (b) Runtime state:
   `World.active_dialogue: DialogueState | None` holds the current position.
   `World.characters` and `World.dialogue_defs` hold content-derived runtime
   objects. (c) Domain API: `World.start_dialogue()`, `World.select_option()`,
   `World.end_dialogue()` return structured outcomes (`TalkOutcome`,
   `DialogueEndOutcome`). Terminal nodes auto-end; ending options set `ended=True`
   with `None` for `node_id`/`node_text`. (d) Commands: `talk <character>`,
   bare integer `[1-9][0-9]*` selection (only when `active_dialogue` is not
   None), `bye` (only when in dialogue). `look` displays characters. (e) Save
   format v5 with required `active_dialogue` field; strictly rejects invalid
   references, terminal node pointers, and room mismatches. (f) Content pack
   version 0.2.4. (g) Dialogue operations produce no numeric side effects.
 - Consequences: Dialogue adds narrative layer without touching combat, inventory,
   or progression. The strict save validation prevents impossible states. Future
   dialogue effects (items, quests) can extend the pattern by adding optional
   fields to nodes.
 - Evidence: `src/lore2mud/content/models.py`, `src/lore2mud/content/loader.py`,
   `src/lore2mud/engine/models.py`, `src/lore2mud/engine/world.py`,
   `src/lore2mud/engine/commands.py`, `src/lore2mud/engine/save.py`,
   `examples/original_demo/dialogues.json`, `tests/test_dialogue.py`.

## DEC-0013: Safe named local save slots without changing save v5

- Date: 2026-07-28
- Status: Accepted
- Context: The single default save file prevents players from preserving distinct
  local progress points. Accepting arbitrary file names would allow path traversal
  and Windows device-name hazards.
- Decision: Keep parameterless `SaveLoadService.save()` / `.load()` and
  `default.json` exactly compatible. Accept one optional slot name through
  `save [slot]` / `load [slot]`, map it only to `<save-dir>/<slot>.json`, and
  validate before any serialization, reading, or `World` replacement. Names are
  1–32 lowercase ASCII letters, digits, `-`, or `_`, start with a letter or digit,
  and exclude Windows reserved device names. Save JSON remains format v5.
- Consequences: Slots are independent and cannot escape the save directory.
  Existing callers and default saves remain valid. A failed slot validation does
  not write a file or replace the active world.
- Evidence: `src/lore2mud/engine/save.py`, `src/lore2mud/engine/commands.py`,
  `tests/test_save_slots.py`, `tests/test_save.py`.
- Supersedes: None.

## DEC-0014: Normalize save-write I/O failures at the service boundary

- Date: 2026-07-28
- Status: Accepted
- Context: The completed GPT-5.6-sol public-repository audit of `2ecead1` found
  that filesystem `OSError` from `_atomic_write()` escaped `SaveLoadService.save()`.
  `CommandProcessor` only handles `SaveLoadError`, so an ordinary disk or permission
  failure could terminate the game loop instead of returning a save failure.
- Decision: Keep `_atomic_write()` responsible for atomic replacement and temporary
  file cleanup. At `SaveLoadService.save()`, catch only `OSError`, re-raise a
  `SaveLoadError` with `raise ... from exc`, and leave non-I/O errors unchanged.
  Do not change slot validation, content-pack data, or save format v5.
- Consequences: Both default and named saves render write failures through the
  existing CLI error path while retaining the original cause for diagnostics.
  Existing save files and the active `World` remain unchanged on a write failure.
- Evidence: `src/lore2mud/engine/save.py`, `tests/test_save_slots.py`,
  `tests/test_save.py`, GPT-5.6-sol audit report supplied on 2026-07-28.
- Supersedes: None.

## DEC-0015: Drop only unequipped inventory items into the current room

- Date: 2026-07-28
- Status: Accepted
- Context: A playable MUD needs a reversible way to move items out of the
  backpack. Allowing a hand/body-equipped item to be dropped directly would
  silently change effective combat attributes and make the state transition
  harder to understand.
- Decision: Add `World.drop()` and `drop <物品ID或名称>`. Resolve only from the
  player's inventory using existing stable-ID and unique-display-name rules;
  reject a missing, ambiguous, or equipped item before mutation. On success,
  remove the ID from the inventory and append it to the current room. The player
  must explicitly `unequip` before dropping an equipped item.
- Consequences: The command reuses existing room/inventory save-v5 placement and
  uniqueness rules, so it needs no format or content-pack change. Dropping a
  gate item can deliberately remove access until the player takes it again.
- Evidence: `src/lore2mud/engine/world.py`, `src/lore2mud/engine/commands.py`,
  `tests/test_drop.py`, `examples/original_demo/README.md`.
- Supersedes: None.

## DEC-0016: Deterministic single-item monster loot reuses save v5 placement

- Date: 2026-07-28
- Status: Accepted
- Context: The public original demo needs a small combat-to-item gameplay loop
  without introducing randomized tables, automatic inventory changes, or a new
  save format.
- Decision: Add optional `MonsterDefinition.loot_item_id` and runtime
  `Monster.loot_item_id`. The loader requires a real, initially unplaced item
  ID with no duplicate monster owner and no conflict with a dialogue reward.
  `World.attack()` preflights that the loot is still unplaced, then puts it in
  the current room only when the monster is defeated and returns `LootOutcome`.
  Consumables are allowed. Save/load continues to use existing room and
  inventory item placement, and rejects a loaded state where a living monster's
  loot is already placed.
- Consequences: Loot is deterministic, visible to `look`, and collected through
  the existing `take` command. It cannot be farmed by repeated attacks. The
  original demo content pack becomes 0.2.7; its older 0.2.6 saves are rejected
  by the existing content-pack version check, while save JSON remains v5.
- Evidence: `src/lore2mud/content/loader.py`,
  `src/lore2mud/engine/world.py`, `src/lore2mud/engine/save.py`,
  `tests/test_loot.py`, `examples/original_demo/`.
- Supersedes: None.

## DEC-0017: Gate private fact-layer activation behind core readiness

- Date: 2026-07-28
- Status: Accepted
- Context: The project goal includes a personal playable adaptation, but the
  current phase is public-engine development and the private novel corpus must
  not be read, copied, scanned, or committed by this workflow.
- Decision: Treat public regression results as evidence only for the generic
  engine and original demo. Before scaling public playable content, first run a
  read-only core-stability readiness audit with explicit public acceptance
  gates. Private novel facts, canon, summaries, and derived adaptations remain
  inaccessible until the project owner later grants a new, explicit, scoped
  authorization.
- Consequences: The next task may evaluate public engine readiness but cannot
  inspect private material. A GO for public content scaling is not permission to
  enter the private fact layer.
- Evidence: Project owner direction on 2026-07-28; `PROJECT_STATE.md`;
  `NEXT_TASK.md`.
- Supersedes: None.

## DEC-0018: Conditional public-content GO; defer private facts until engine completion

- Date: 2026-07-28
- Status: Accepted
- Context: A read-only public core readiness audit at
  `d81310c08ada7d2950dbfbcd1c431d42773c056e` passed the full 415-test suite,
  248 focused tests, compile, original-demo validation, history safety scan,
  Git integrity checks, and a real public CLI loop. The project owner then
  clarified that the novel fact layer should wait until the engine development
  phase is complete.
- Decision: Record `CONDITIONAL GO` only for another small, fully original
  public content slice using existing engine contracts. Do not treat the audit
  as an engine-completion certificate. Defer every private novel fact, canon,
  summary, and derived adaptation until a future public-engine-complete
  milestone is explicitly established and the owner supplies a new, scoped
  authorization.
- Consequences: The next slice may increase the public demo's playable scale
  without new private inputs. A future fact-layer phase must start with its own
  authorization and boundary audit; it cannot be inferred from this GO.
- Evidence: `PROJECT_STATE.md`, `PROJECT_MEMORY.md`, `NEXT_TASK.md`,
  `tests/`, `scripts/check_repo_safety.py`, and public original demo evidence
  verified on 2026-07-28.
- Supersedes: DEC-0017's readiness-only activation wording.
