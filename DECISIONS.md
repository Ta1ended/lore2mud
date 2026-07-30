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

## DEC-0019: Deterministic defeat recovery with unified death gate

- Date: 2026-07-28
- Status: Accepted
- Context: Player death (HP=0) left the game in an unrecoverable state — only
  `load` could restore playability. Individual methods had inconsistent death
  checks with different error messages, and `attack()`/`use()` had their own
  `is_alive` guards that could drift from the unified rule.
- Decision: (a) Add `_require_alive()` private method on `World` that ALL
  mutating public methods call first, before any validation or resolution.
  Replace the old per-method `is_alive` checks in `attack()` and `use()` with
  the single gate. (b) Add `World.recover()` returning `RecoverOutcome`
  (start_room_id, room_name, hp, max_hp); it rejects alive players and
  atomically sets room_id=start_room_id, hp=max_hp, active_dialogue=None.
  (c) Add `start_room_id: str` field to `World`, sourced from
  `ContentPack.start_room_id` in both constructor sites
  (`World.from_content_pack()` and `save.py _validate_and_build_world()`).
  NOT serialized in save JSON — reconstructed from ContentPack on load.
  (d) CommandProcessor adds a second gate after bare-selection/bye routing
  but before normal dispatch, using `_DEAD_ALLOWED` frozenset (look, inspect,
  status, inventory, quests, help, save, load, recover, quit, exit).
  (e) Combat failure text updated to mention recover/load options.
- Consequences: Death is recoverable without save/load. The unified gate
  eliminates inconsistent error messages. `recover` is a game rule in World,
  not a CLI concern. Future death-related mechanics (e.g. penalties, respawn
  timers) can extend `recover()` without touching the gate. save format
  remains v5 — `start_room_id` is reconstructed, not stored.
- Evidence: `src/lore2mud/engine/world.py`, `src/lore2mud/engine/commands.py`,
  `src/lore2mud/engine/save.py`, `tests/test_recover.py`.
- Supersedes: None.

## DEC-0020: Death gate must precede dialogue routing in CommandProcessor

- Date: 2026-07-28
- Status: Accepted
- Context: DEC-0019 placed the command-layer death gate AFTER the bare integer
  dialogue selection and `bye` routing in `CommandProcessor.execute()`. This
  means a dead player with an active dialogue could invoke `_select_option` or
  `_bye` before the death gate fires. The existing tests did not catch this
  because `_make_dead_world()` never sets `active_dialogue`.
- Decision: Move the death gate (`if not self.world.player.is_alive`) to BEFORE
  the bare-selection/bye routing block. Do NOT add `bye` to `_DEAD_ALLOWED`.
  Dead players with active dialogues receive `_DEAD_ERROR` for any non-allowed
  command, including bare numbers and `bye`. `World._require_alive()` remains
  unchanged as the domain-layer second defense.
- Consequences: Dead players can never invoke `_select_option` or `_bye`, even
  when `active_dialogue` is set. The death gate is the first routing decision
  after command parsing. New tests cover dead+active_dialogue+number,
  dead+active_dialogue+bye, and dead+no_dialogue+number scenarios with mock
  verification that routing methods are not called.
- Evidence: `src/lore2mud/engine/commands.py`, `tests/test_recover.py`.
- Supersedes: DEC-0019's placement of the death gate after dialogue routing.

## DEC-0021: M1 independent acceptance — GO

- Date: 2026-07-28
- Status: Accepted
- Context: M1 (death/recovery) was implemented by Hermes agent across two commits
  (`6a50fdf` initial, `c329546` gate-ordering fix). GPT-5.6-sol performed an
  independent verification of `c329546` covering code correctness, test coverage,
  and real CLI behavior.
- Decision: Record M1 as independently accepted. Evidence: 59 recover tests,
  474 full unittest, compileall, original_demo content validation,
  `check_repo_safety.py --history`, `git diff --check`, and real CLI smoke
  (defeat → move rejected → dead save → recover → 20/20 → resume). Git state:
  main, ahead 2 / behind 0, clean, not pushed.
- Consequences: M1 is complete. The project may proceed to M2 (typed stacks)
  proposal. The engine is still in development; this does not certify engine
  feature-completeness.
- Evidence: `c329546`, `tests/test_recover.py`, `src/lore2mud/engine/commands.py`.
- Supersedes: None.

## DEC-0022: Typed item stacks, save v6, and M2 data contracts

- Date: 2026-07-29
- Status: Accepted
- Context: M1 introduced basic item IDs as flat lists. M2 requires items with
  quantities to support stackable consumables, room loot drops, and dialogue
  rewards. The save format must encode quantities, and the content schema must
  declare stack limits.
- Decision:
  (a) Content layer uses frozen `ItemStackDefinition(item_id, quantity)`.
  Runtime uses mutable `ItemStack(item_id, quantity)`. No shared instances.
  (b) `ItemDefinition.stack_limit` (default 1) governs max quantity per stack.
  Equipment items must have `stack_limit == 1`.
  (c) Room `item_ids` → `item_stacks: list[ItemStack]`.
  Inventory `item_ids` → `stacks: list[ItemStack]`. Capacity = stack slots.
  (d) `Monster.loot_item: ItemStackDefinition | None` replaces `loot_item_id`.
  `DialogueOption.grant_item: ItemStackDefinition | None` replaces `grant_item_id`.
  (e) `stack_limit > 1` items may exist in multiple containers simultaneously.
  `stack_limit == 1` items remain globally unique across rooms, inventory,
  loot sources, and dialogue grants.
  (f) `take/drop/use` accept optional suffix quantity (default 1).
  `_parse_quantity` uses ASCII regex classification rejecting 0, signed, float,
  hex, binary, octal, inf/nan.
  (g) Loot preflight in `World.attack()` checks before combat; failure rejects
  the entire attack.
  (h) Save format v6: `inventory_stacks` and `item_stacks` as arrays of
  `{item_id, quantity}` objects. v5 explicitly rejected.
  (i) Content pack version 0.3.0.
- Consequences: All item containers use typed stacks. Old flat ID lists are
  fully removed from runtime and save format. Equipment remains slot-based
  with item_id string reference (stack_limit=1 guarantees quantity=1).
- Evidence: `src/lore2mud/content/models.py`, `src/lore2mud/inventory/models.py`,
  `src/lore2mud/engine/world.py`, `src/lore2mud/engine/save.py`,
  `src/lore2mud/engine/commands.py`, `src/lore2mud/content/loader.py`,
  `tests/test_item_stacks.py`, `schemas/`.
- Supersedes: None.

## DEC-0023: M2 independent acceptance — GO

- Date: 2026-07-29
- Status: Accepted
- Context: M2 typed stacks was implemented by Hermes agent in `3161d52`, with
  contract and handoff synchronization in `1ee0b30`. GPT-5.6-sol independently
  reviewed the implementation and acceptance evidence.
- Decision: Record M2 as independently accepted, GO. Evidence: 530 full unittest
  cases, 56 `tests.test_item_stacks` cases, compileall, original_demo validation,
  `check_repo_safety.py --history`, `git diff --check`, and the real CLI flow for
  quantity pickup, injured `use` ×2 restoring to 20/20, combat loot, drop, and
  save/load. The pre-documentation-closure Git baseline was `main` at `1ee0b30`,
  clean and synchronized with origin/main and remote main at ahead/behind 0/0.
- Consequences: M2 is complete, while the public engine remains in development.
  The sole next action is a read-only M3 proposal for GPT-5.6-sol review; no M3
  implementation is authorized by this decision.
- Evidence: `3161d52`, `1ee0b30`, `tests/test_item_stacks.py`,
  `docs/engine_completion_milestones.md`.
- Supersedes: None.

## DEC-0024: Current executor switches from Hermes to Codex

- Date: 2026-07-29
- Status: Accepted
- Context: The project needs one explicit current execution path after M2
  acceptance, while retaining the historical fact that Hermes agent implemented
  M1 and M2.
- Decision: GPT-5.6-sol is the advisor for scope and architecture review and the
  independent acceptor. Codex is the sole executor for approved slices, including
  code, tests, documentation, handoff files, and local commits. The project owner
  manually transfers advisor prompts and Codex completion reports between the two
  conversations. Local commits do not automatically push.
- Consequences: This switch applies prospectively only. M1/M2 historical
  implementation records remain attributed to Hermes agent; Codex cannot self-
  certify independent acceptance.
- Evidence: `AGENTS.md`, `docs/production_workflow.md`, `PROJECT_MEMORY.md`,
  `PROJECT_STATE.md`, `NEXT_TASK.md`.
- Supersedes: None.

## DEC-0025: M3 typed quest conditions and authoritative settlement

- Date: 2026-07-29
- Status: Implemented locally; GPT-5.6-sol independent acceptance pending.
- Context: The approved M3 slice generalizes the historical single monster task
  without changing save v6 or beginning M4 typed dialogue effects. The system must
  keep a precise content contract, deterministic multi-task results, and no
  duplicate reward path across movement, inventory, combat, dialogue, or load.
- Decision: (a) `QuestDefinition` is a frozen tagged union with exactly
  `monster_defeated.target_monster_id`, `reach_room.target_room_id`, and
  `collect_item.target_item_id + required_quantity`; loader and schema reject
  mixed branch fields. (b) `required_quantity` is an integer from 1 through the
  referenced item's `stack_limit`; collect completion means inventory quantity is
  at least that value. (c) `World` exclusively accepts tasks, checks conditions,
  commits rewards, marks `QuestState.completed`, and emits `quest_outcomes` /
  task `level_gains`. (d) Multiple eligible tasks settle in lexical quest-ID order.
  (e) Movement, pickup, terminal combat, and successful dialogue item grants run
  their primary mutation and task settlement in one local-memory transaction;
  any failure restores the entire action. (f) `World.move()` retains `Room` as its
  return value; `move_with_outcome()` is the additive CLI path. (g) `completed`
  is a one-time reward fact: `drop`, `use`, and load do not revoke or replay it.
  (h) save v6 and the `QuestState` shape remain unchanged; load restores saved
  states only, without reacceptance, recheck, or reward. (i) original_demo is
  content pack 0.4.0, so 0.3.0 saves are rejected by the existing pack-version
  check.
- Consequences: New task kinds require an explicit future content/schema/World
  slice. M4 typed dialogue effects remain out of scope; the existing typed item
  grant only invokes the unified M3 settlement path after its own validation.
- Evidence: `src/lore2mud/content/models.py`, `src/lore2mud/content/loader.py`,
  `schemas/quest.schema.json`, `src/lore2mud/engine/world.py`,
  `src/lore2mud/engine/commands.py`, `tests/test_quest.py`,
  `examples/original_demo/`.
- Supersedes: DEC-0008's historical single-monster-task shape only; M1/M2 history
  and save v6 contracts remain intact.

## DEC-0026: M3 independent acceptance — GO

- Date: 2026-07-29
- Status: Accepted
- Context: Codex implemented the approved M3 typed-quest slice in `dca629b`.
  GPT-5.6-sol's first independent review found one P2 handoff inconsistency in
  `PROJECT_STATE.md`; Codex corrected only that record in `5527faa`.
- Decision: Record M3 as independently accepted GO by GPT-5.6-sol. The focused
  re-review found no remaining findings. Accepted evidence is 540 full unittest
  cases, 31 `tests.test_quest` cases, 56 preserved `tests.test_item_stacks`
  regressions, compileall, original-demo validation, history safety scanning,
  `git diff --check`, and the external-save-directory CLI flow.
- Consequences: M3 is complete. The public engine remains in development; M4 or
  any other feature implementation requires explicit future authorization. This
  decision does not change M1/M2 historical attribution to Hermes agent or their
  own acceptance evidence.
- Evidence: `dca629b`, `5527faa`, `tests/test_quest.py`,
  `docs/engine_completion_milestones.md`, `PROJECT_STATE.md`.
- Supersedes: Only the independent-acceptance-pending status in DEC-0025.

## DEC-0027: Integrated M4 typed dialogue effects and M5 fixed coin shops

- Date: 2026-07-29
- Status: Implemented locally; GPT-5.6-sol independent acceptance pending.
- Context: The project owner approved one bounded public-engine slice that combines
  M4 and M5 without beginning M6–M8, adding no dependencies and no mutable shop
  stock.
- Decision: (a) Replace `DialogueOption.grant_item` with the ordered frozen
  `grant_item` / `grant_experience` / `accept_quest` / `set_flag` effect union.
  Explicit duplicate quest acceptance fails the complete option; flags are
  World-owned stable-ID-to-bool state with missing and `false` kept distinct.
  (b) Keep one authoritative World transaction for whole-list preflight, effect
  execution, quest settlement, progression, flags, and dialogue advancement.
  (c) Introduce frozen, unlimited fixed-price shop catalogs with coins, no
  serialized stock, and fixed `shop` / `buy` / `sell` behavior. (d) Upgrade the
  public demo to content 0.6.0 and saves to v7 with `player.coins` and top-level
  `flags`.
- Consequences: `shops.json` is required even when empty. v6 saves and 0.4.0 demo
  saves are rejected without migration. M6–M8 remain unstarted. Local evidence is
  568 full tests, focused M4/M5 suites, compileall, content validation, history
  safety, and external-save-directory CLI/rejection flows; it is not a Sol GO.
- Evidence: `src/lore2mud/content/models.py`, `src/lore2mud/content/loader.py`,
  `src/lore2mud/engine/world.py`, `src/lore2mud/engine/save.py`,
  `src/lore2mud/engine/commands.py`, `tests/test_dialogue_effects.py`,
  `tests/test_shop.py`, `docs/engine_completion_milestones.md`.
- Supersedes: The M3-only dialogue item-grant contract in DEC-0025 for current
  behavior; DEC-0025 and DEC-0026 remain historical M3 evidence.

## DEC-0028: M4+M5 independent acceptance — GO

- Date: 2026-07-29
- Status: Accepted
- Context: Codex implemented the approved integrated M4/M5 slice in `cc1b1ce`.
  GPT-5.6-sol's first review found one M5 P1: `World.buy()` could create a new
  empty inventory stack above its `stack_limit`, yielding a v7 save that strict
  load rejects. Codex corrected that path in `59ca3cd`.
- Decision: Record M4 typed dialogue effects and M5 fixed coin shops as
  independently accepted GO by GPT-5.6-sol. The focused re-review found no
  findings and closed the M5 P1. Accepted evidence is 25 focused M4/M5 tests,
  569 full unittest cases, compileall, original-demo validation, history safety,
  `git diff --check`, and external-save-directory CLI buy-rejection/save/load
  coverage. M4 effects do not replay; v6 and old content-pack saves remain
  rejected.
- Consequences: M4 and M5 are complete. The public engine remains in development;
  M6 or any other feature work requires explicit future project-owner
  authorization. This decision does not change M1/M2 Hermes history or the
  independent acceptance records for M1–M3.
- Evidence: `cc1b1ce`, `59ca3cd`, `tests/test_dialogue_effects.py`,
  `tests/test_shop.py`, `docs/engine_completion_milestones.md`,
  `PROJECT_STATE.md`.
- Supersedes: Only the independent-acceptance-pending status in DEC-0027.

## DEC-0029: M6 typed visible examine and authoritative command help

- Date: 2026-07-29
- Status: Implemented locally; GPT-5.6-sol independent acceptance pending.
- Context: The project owner explicitly authorized M6 after a read-only design
  review identified three drift risks: help versus real routes and death gates,
  exact `examine` reserved-word/numeric behavior, and cross-type ambiguity
  fixtures accidentally leaking into the public demo.
- Decision: (a) `World.examine()` is the visibility and ambiguity authority and
  returns a frozen `ExamineItemOutcome` / `ExamineMonsterOutcome` /
  `ExamineCharacterOutcome` union. It searches only current-room items, backpack
  items, current-room monsters, and current-room characters; unique exact IDs
  precede unique names, while cross-type duplicate names or IDs require an
  explicit type. (b) `examine`, `examine room`, and `examine here` reuse the
  current room summary; `item`, `monster`, and `character` are case-insensitive
  first-argument selectors. Reserved room words with extra arguments and empty
  typed targets return fixed usage text. (c) `inspect` remains the item-only
  compatibility API and output. (d) A frozen `CommandSpec` registry owns literal
  routes, aliases, summary/detail help, and death permission metadata. The death
  allowlist is derived from it while DEC-0020 ordering remains unchanged.
  (e) Bare integers retain the historical dialogue-only route; `examine 1`
  always treats `1` as a target and preserves any active dialogue. (f) All
  examine/help operations and failures are read-only. Cross-type duplicate-name
  and duplicate-ID fixtures exist only in test memory.
- Consequences: M6 changes no JSON contract, Schema, dependency, content-pack
  data/version, or save data/version; original_demo remains 0.6.0 and saves
  remain v7. The local implementation is not M6 GO until GPT-5.6-sol independently
  reviews it. M7 remains unstarted and unauthorized.
- Evidence: `src/lore2mud/engine/world.py`,
  `src/lore2mud/engine/commands.py`, `tests/test_examine_help.py`,
  `tests/test_inspect.py`, `docs/architecture.md`,
  `docs/engine_completion_milestones.md`.
- Supersedes: The M6-planning-only state; DEC-0020 death-gate ordering and the
  legacy inspect contract remain in force.

## DEC-0030: M6 independent acceptance — GO

- Date: 2026-07-29
- Status: Accepted
- Context: Codex implemented the project-owner-authorized M6 public-engine slice
  in `53a071f`. The independent review checked the visibility boundary, typed
  ambiguity behavior, exact error/help text, registry-to-route consistency, death
  and dialogue ordering, read-only invariance, and external CLI/save behavior.
- Decision: Record M6 `examine`, `help [command]`, and the centralized
  `CommandSpec` registry as independently accepted GO by GPT-5.6-sol, with no
  findings. Accepted evidence is 22 M6 tests, 187 focused
  M6/inspect/commands/recover/dialogue regressions, 591 full unittest cases,
  compileall, original-demo validation, history safety, `git diff --check`, the
  verified 11-file scope relative to `f0acd3f`, and an external-save-directory
  CLI/save v7 flow.
- Consequences: M6 is complete and its contracts in DEC-0029 remain in force.
  M6 changes no Schema, dependency, content-pack data/version, or save data/version;
  original_demo remains 0.6.0 and saves remain v7. M7 is unstarted and needs a
  separate explicit project-owner authorization. This decision does not authorize
  push; direct remote state must be checked again before publishing.
- Evidence: `53a071f`, `tests/test_examine_help.py`, `tests/test_inspect.py`,
  `src/lore2mud/engine/world.py`, `src/lore2mud/engine/commands.py`,
  `docs/engine_completion_milestones.md`, `PROJECT_STATE.md`.
- Supersedes: Only the independent-acceptance-pending status in DEC-0029; the
  DEC-0029 contracts, DEC-0020 death-gate ordering, and legacy `inspect` contract
  remain in force.

## DEC-0031: M7.1 second original encounter and content-pack 0.7.0

- Date: 2026-07-29
- Status: Implemented locally; GPT-5.6-sol independent acceptance pending.
- Context: After M6 was independently accepted, the project owner explicitly
  authorized entry into M7. The roadmap's first required M7 content-expansion
  slice is one second original encounter, not completion of the whole 8-room/
  4-monster milestone.
- Decision: Add only `room_shattered_signal_spur`, `monster_spark_hound`, and
  `quest_clear_spark_hound`. The silent observatory's east exit and the spur's west
  exit are reciprocal. Entering the observatory accepts the existing-kind
  `monster_defeated` quest; defeating the hound reuses existing deterministic combat
  and World-owned quest settlement. Bump original_demo from 0.6.0 to 0.7.0; keep
  save format v7, with old 0.6.0 content-pack saves rejected by the existing
  identity/version check.
- Consequences: No engine, Schema, command, dependency, item, loot, dialogue, shop,
  or save-format contract changes. The demo is now four rooms, two monsters, and
  five quests, so M7 remains incomplete and is not GO. No M7.2 or push is authorized
  until independent acceptance and a separate project-owner authorization.
- Evidence: `examples/original_demo/pack.json`, `rooms.json`, `monsters.json`,
  `quests.json`, `tests/test_m7_second_encounter.py`, `tests/test_loot.py`,
  `docs/engine_completion_milestones.md`, `PROJECT_STATE.md`.
- Supersedes: Only the M7 planning-only status in the milestone roadmap; M1–M6
  contracts and their independent acceptance records remain in force.

## DEC-0032: M7.1 independent acceptance — GO

- Date: 2026-07-30
- Status: Accepted
- Context: Codex implemented the project-owner-authorized M7.1 second original
  encounter in `9786325`. GPT-5.6-sol then independently reviewed the completed
  slice relative to `086cda8`.
- Decision: Record M7.1 as independently accepted GO by GPT-5.6-sol with no
  findings. The acceptance covers one 22-file `+333/-55` commit; no `src/`,
  `schemas/`, dependency-file, or private-material path changed. It accepts the
  public fourth room, second monster, second monster-defeated quest, content-pack
  0.7.0, and unchanged save v7 contract.
- Consequences: M7.1 is complete, but M7 remains in progress at 4/8 rooms, 2/4
  monsters, and five quests; this is not M7 GO or public-engine completion. M7.2
  still requires explicit project-owner authorization, followed first by a read-only
  implementation proposal. This decision does not authorize push.
- Evidence: 19 M7/loot focused tests; 595 full unittest cases; compileall;
  `lore2mud validate --content examples/original_demo`; `check_repo_safety.py
  --history`; baseline `git diff --check`; and a real CLI flow that accepted the
  new task, defeated both monsters, entered the new room, completed
  `quest_clear_spark_hound`, and save/loaded. The v7/0.7.0 save confirmed the
  player remained in the new room, the hound was HP 0 and removed, and the task was
  complete. Direct remote `main` remained `f0acd3f`; no push occurred.
- Supersedes: Only the independent-acceptance-pending status in DEC-0031. DEC-0031
  content, save, and boundary contracts remain in force.

## DEC-0033: M7.2 content-scale completion and content-pack 0.8.0

- Date: 2026-07-30
- Status: Implemented locally; GPT-5.6-sol independent acceptance pending.
- Context: After M7.1 was independently accepted, the project owner authorized a
  larger but still content-only M7.2 slice to reach the M7 room and monster scale
  target without mixing in an engine or data-contract change.
- Decision: Add exactly four public original rooms—`room_broken_rail_junction`,
  `room_mist_condenser_well`, `room_lens_archive`, and
  `room_afterglow_beacon_platform`—plus `monster_mist_crawler`,
  `monster_prism_sentinel`, `quest_clear_mist_crawler`, and
  `quest_clear_prism_sentinel`. The new exits are reciprocal, the two quests are
  accepted on entering the junction, and each has its own unique monster target.
  Bump original_demo from 0.7.0 to 0.8.0; keep save format v7, with old 0.7.0
  content-pack saves rejected by the existing identity/version check.
- Consequences: No engine, Schema, command, dependency, item, loot, dialogue, shop,
  or save-format contract changes. The demo now has eight rooms, four monsters, and
  seven quests, so the M7 content-scale conditions are locally met. This is not M7
  GO or public-engine completion until GPT-5.6-sol independently accepts M7.2. This
  decision does not authorize M8 or push.
- Evidence: `examples/original_demo/pack.json`, `rooms.json`, `monsters.json`, and
  `quests.json`; `tests/test_m7_content_scale.py`; `tests/test_m7_second_encounter.py`;
  `tests/test_loot.py`; and the M7 handoff records. Local evidence is 8 M7 scenario
  tests, 15 loot regressions, 599 full unittest cases, compileall, content validation,
  history safety, diff checking, and an external CLI/save v7 path through both new
  branches.
- Supersedes: Only the M7.2 awaiting-authorization status in `NEXT_TASK.md` and
  related current snapshots. M7.1's GO record and all M1–M6 contracts remain in
  force.

## DEC-0034: M7.2 and M7 independent acceptance — GO

- Date: 2026-07-30
- Status: Accepted
- Context: Codex completed the project-owner-authorized M7.2 public-content scale
  slice in `147633e`. GPT-5.6-sol independently reviewed it relative to the M7.1
  acceptance-record baseline `5497859` and supplied an M7.2 GO plus overall M7 GO
  conclusion with no findings.
- Decision: Record M7.2 and the complete M7 milestone as independently accepted GO
  by GPT-5.6-sol. The acceptance covers one 22-file content, test, and public-doc
  commit; `src/`, Schema, dependency files, and private-material paths are all 0.
  The public demo reaches 8/8 rooms, 4/4 monsters, and 7 quests while retaining
  content-pack 0.8.0 and save v7.
- Consequences: M7 is complete. This does not declare the public engine complete:
  M8 is unstarted and requires a separate project-owner authorization. No engine,
  Schema, command, item, loot, dialogue, shop, dependency, or save-format contract
  changed. This decision does not authorize push.
- Evidence: 23 M7/loot focused tests; 599 full unittest cases; graph and unique-
  target audits; compileall; `lore2mud validate --content examples/original_demo`;
  `check_repo_safety.py --history`; `git diff --check`; real CLI/save; and defeat
  recovery all passed. The v7/0.8.0 save confirmed the player in a new room, both
  new monsters HP=0 and removed, and `quest_clear_mist_crawler` plus
  `quest_clear_prism_sentinel` completed. At acceptance direct remote `main` was
  `f0acd3f` and no push occurred. This session's local `origin/main` remains
  `f0acd3f`, but its direct CLI remote lookup could not refresh because of a network
  connection failure; GitHub Desktop Fetch must confirm no incoming commits before
  any later publishing decision.
- Supersedes: Only DEC-0033's independent-acceptance-pending status and related
  current handoff snapshots. DEC-0033's content, 0.8.0/v7, and boundary contracts,
  DEC-0032's M7.1 record, and all M1–M6 decisions remain in force.

## DEC-0035: M8 public-engine audit baseline — independent acceptance pending

- Date: 2026-07-30
- Status: Codex read-only audit complete; GPT-5.6-sol independent acceptance pending.
- Context: After the project owner confirmed the M7 documentation push, the next
  roadmap stage is M8's public-engine completion audit. The audit was run against
  `f486e12`, which is now present on local `main`, `origin/main`, and the directly
  queried remote `main`.
- Decision: Enter M8 through a read-only evidence baseline. Do not alter engine,
  Schema, dependencies, original content, or save contracts until GPT-5.6-sol
  reviews the evidence and identifies any required bounded correction.
- Consequences: M8 is in audit preparation, not GO; the public engine remains
  uncompleted until independent acceptance. The private novel fact layer remains
  outside this roadmap and is not authorized.
- Evidence: 599 full unittest cases; compileall; `lore2mud validate --content
  examples/original_demo`; `check_repo_safety.py --history`; `git diff --check`;
  `git fsck --full --no-dangling`; and a real CLI/save flow through both new M7.2
  branches. A fresh real CLI flow reached the beacon without defeating prior
  monsters, proved prism-sentinel death, `recover`, and v7 save/load back at the
  start room. No repository files changed during the audit.
- Supersedes: Only the M8-unstarted current handoff status after DEC-0034. DEC-0034
  and all prior milestone contracts and independent acceptance records remain in
  force.

## DEC-0036: M8 independent acceptance — GO; M1–M8 public-engine scope complete

- Date: 2026-07-30
- Status: GPT-5.6-sol focused re-review GO; the Git-snapshot P2 is closed and there
  are no new findings.
- Context: The technical audit baseline is `f486e12`, its audit record is
  `6510e2d`, and `6502a72` corrected the handoff's stale Git snapshot without
  changing engine, content, Schema, dependencies, or private-material boundaries.
- Decision: Record M8 as independently accepted GO and close the M1–M8 public-engine
  roadmap scope. "Complete" applies only to that public-engine roadmap, not to a new
  feature roadmap, M9, publishing work, or the private novel fact layer.
- Consequences: No new implementation is authorized by this record. Any M9 slice,
  other feature work, or private fact-layer access requires a separate, explicit,
  scoped project-owner authorization. This decision does not authorize an automatic
  push.
- Evidence: 599 full unittest cases, compileall, original-demo validation,
  `check_repo_safety.py --history`, `git diff --check`, and
  `git fsck --full --no-dangling` passed. The previously accepted 216 focused,
  375 save-matrix, and 35 content/CLI/safety-matrix checks plus real CLI evidence
  remain valid. At acceptance, local `HEAD` and `origin/main` are both `6502a72`,
  the worktree is clean, and ahead/behind is 0/0; GitHub Desktop push is reflected
  in the local tracking branch, while the command-line direct remote query timed out.
- Supersedes: Only DEC-0035's independent-acceptance-pending current status and the
  related M8 P2 handoff condition. The `f486e12` audit baseline, `6510e2d` audit
  record, `6502a72` correction, all prior milestone contracts, and all historical
  acceptance evidence remain in force.

## DEC-0037: Phase 1.0 fact-candidate document validation contract

- Date: 2026-07-30
- Status: Implemented locally; GPT-5.6-sol independent acceptance pending.
- Context: After M1–M8 public-engine completion (DEC-0036) and a Phase 0
  readiness audit (NO-GO), Phase 0.1 revised the fact-candidate contract.
  The project owner authorized Phase 1.0: implement the v1 document envelope,
  frozen dataclass models, standard-library validator, JSON Schema, tests, and
  public documentation using only fictional test fixtures.
- Decision: (a) Implement `pipeline/fact_candidates.py` as a single module in
  `pipeline/`, not in `src/lore2mud/`. (b) v1 is a document envelope with
  `format_version`, `source_chapter`, `extracted_by`, and `candidates[]`.
  (c) Each candidate has `candidate_id` (stable ID, document-unique),
  `entity_type` (6-way enum), `proposed_entity_id` (optional proposal, not
  authoritative), `display_name`, `aliases` (NFKC+casefold+strip dedup within
  candidate only, originals preserved), and `claims[]`. (d) Each claim has
  `claim_id` (stable ID, candidate-unique), `predicate` (stable ID), `value`
  (5-branch tagged union: text/relation/numeric/boolean/enum), `source_chapters`
  (exactly `[document.source_chapter]`), `source_support` (explicit|inferred),
  `certainty` (certain|uncertain), and `inference_basis` (required when inferred,
  null otherwise). (e) relation value uses `candidate_ref` referencing same-document
  `candidate_id`; numeric rejects bool/NaN/±Inf; boolean rejects int 0/1; enum
  uses stable ID. (f) JSON Schema (draft 2020-12) expresses structural constraints;
  Python adds semantic checks the schema cannot express. (g) v1 excludes confidence,
  timestamps, review status, conflict references, canon promotion, and entity
  registry. (h) 119 focused tests and 718 full tests pass.
- Consequences: The public fact-candidate format is defined and validated.
  Manifest cross-file checking, review decisions, canon writing, model
  integration, and entity ID registry remain for future slices. This does not
  authorize reading private material.
- Evidence: `pipeline/fact_candidates.py`, `schemas/fact_candidate.schema.json`,
  `tests/test_fact_candidates.py`, `tests/fixtures/fact_candidates/`,
  `docs/fact_candidate_format.md`, `docs/novel_pipeline.md`.
- Supersedes: None.

## DEC-0038: Phase 1.0 focus fix — harden fact candidate validation

- Date: 2026-07-30
- Status: Implemented locally; GPT-5.6-sol focused re-review pending.
- Context: Phase 1.0 independent acceptance was NO-GO with two P1 and one P2.
  P1-1: `entity_type`, `source_support`, `certainty` leaked `TypeError` on
  unhashable JSON types (list, dict) because `not in frozenset` was called before
  `isinstance(str)` check, including in construction conditions. P1-2:
  `NumericValue.number` was `float`, causing `float()` conversion of ints
  (precision loss for 2^53+1) and `OverflowError` for 10^400. P2: Schema used
  only `minLength` for non-blank strings and lacked `if/then/else` for the
  `source_support` → `inference_basis` conditional.
- Decision: (a) Add `isinstance(v, str)` guard before all `not in` / `in`
  frozenset checks for `entity_type`, `source_support`, `certainty` — both in
  the error-reporting path and the construction-condition path. (b) Change
  `NumericValue.number` type to `int | float`; pass int values through without
  `float()` conversion; apply `math.isfinite` only to `isinstance(num, float)`.
  (c) Add `non_blank_string` def with `\S` pattern to Schema; use `$ref` for
  `extracted_by`, `display_name`, alias items, text value, and `then` branch
  of `inference_basis`. Add `if/then/else` on claim for
  `source_support=inferred` → non-blank `inference_basis`, else `null`.
  (d) Add 12 new test methods: P1-1 matrix (1 method, 24 subTests),
  P1-2 precision (5 methods), P2 Schema structure (6 methods). Total focused: 131.
- Consequences: The `entity_type`/`source_support`/`certainty` type-check paths
  no longer leak `TypeError` on unhashable JSON types. Numeric `int` values are
  preserved exactly without `float()` conversion, closing the `OverflowError` for
  large ints. Schema now expresses the inference_basis conditional and rejects
  pure-whitespace strings. 730 full tests continue to pass.
- Evidence: `pipeline/fact_candidates.py`, `schemas/fact_candidate.schema.json`,
  `tests/test_fact_candidates.py`.
- Supersedes: None.

## DEC-0039: Phase 1.0 independent acceptance — GO; DEC-0038 findings closed

- Date: 2026-07-30
- Status: Accepted
- Context: Phase 1.0 initial implementation (`e2b8136`) was independently reviewed
  as NO-GO with two P1 and one P2 findings (DEC-0037 pending → DEC-0038 fix).
  The focus fix (`3442d2d`) closed all three findings. GPT-5.6-sol performed a
  focused re-review of the fix relative to `e2b8136`.
- Decision: Record Phase 1.0 fact-candidate document validation contract as
  independently accepted GO by GPT-5.6-sol. All DEC-0038 findings are closed:
  P1-1 enum TypeError paths sealed, P1-2 numeric int precision preserved,
  P2 Schema if/then/else and \S pattern added. No remaining blocking findings.
  Accepted evidence: 131 focused `tests.test_fact_candidates` (1 method/24
  subTests enum matrix, 5 numeric precision, 6 Schema structure, plus original
  119), 730 full unittest, compileall, original-demo validation,
  `check_repo_safety.py --history`, `git diff --check`, and 9-file scope relative
  to `e2b8136`. Local HEAD=`3442d2d`, `origin/main`=`afdb235`, ahead/behind=2/0,
  worktree clean, not pushed. Direct remote query was not refreshed this session.
- Consequences: Phase 1.0 is complete. No new implementation is authorized.
  Phase 1.1 (manifest cross-file checking), review decisions, canon writing,
  model integration, or any other work requires a separate, explicit, scoped
  project-owner authorization. This does not authorize push.
- Evidence: `pipeline/fact_candidates.py`, `schemas/fact_candidate.schema.json`,
  `tests/test_fact_candidates.py`, `docs/fact_candidate_format.md`.
- Supersedes: Only DEC-0037's independent-acceptance-pending status.

## DEC-0040: Clarify Phase 1.0 acceptance handoff and supersession

- Date: 2026-07-30
- Status: Accepted
- Context: DEC-0039 records that all DEC-0038 findings are closed, while its
  supersession field names only DEC-0037. The documentation seal also needs to
  distinguish the acceptance-time Git snapshot from later documentation commits.
- Decision: Treat DEC-0039 as closing both DEC-0037's independent-acceptance-
  pending status and DEC-0038's focused-re-review-pending status. Record
  `3442d2d` only as the acceptance snapshot before its documentation seal; all
  current Git and remote state must be established by live checks.
- Consequences: No implementation contract, test result, or private-material
  boundary changes. Handoff records remain historically precise without
  presenting a stale snapshot as current state.
- Evidence: `DEC-0039`, `CHANGELOG.md`, `NEXT_TASK.md`, `PROJECT_MEMORY.md`,
  `PROJECT_STATE.md`.
- Supersedes: DEC-0038's focused-re-review-pending status.

## DEC-0041: Phase 1.1 manifest validation and candidate source binding

- Date: 2026-07-30
- Status: Implemented locally; independent acceptance pending.
- Context: Phase 1.0 established the fact-candidate document contract. Phase 1.1
  adds manifest v2 structural validation and binds validated fact-candidate documents
  to manifest chapters by source_chapter existence.
- Decision: (a) New `pipeline/chapter_manifests.py` with frozen `ChapterManifestEntry`
  (12 fields) and `ChapterManifest` dataclasses. (b) `validate_chapter_manifest()`
  checks: format_version=2, source_encoding enum or null, chapter_count equals array
  length, chapter_id consecutive from chapter_000001, path equals `<chapter_id>.txt`
  with no separators/traversal, sha256 64-lowercase-hex, chain adjacency for
  previous_id/next_id, primary path requires non-blank label/non-null offset≥0/
  line≥1 with monotonic increase, scan path requires all 5 null. All unknown fields
  rejected. (c) `validate_fact_candidate_sources()` checks each
  `FactCandidateDocument.source_chapter` exists in manifest chapter_ids; returns
  ordered tuple; empty sequence valid; non-document elements rejected. (d) New
  `schemas/chapter_manifest.schema.json` (draft 2020-12). (e) 73 focused tests
  including build_manifest integration (primary, scan, empty). (f) Not modified:
  `pipeline/build_manifest.py`, `src/`, existing schemas, original_demo, save.
- Consequences: Manifest v2 is now structurally validated. Fact-candidate documents
  can be bound to verified chapters. Review decisions, canon writing, entity
  resolution, and file-content verification remain for future slices.
- Evidence: `pipeline/chapter_manifests.py`, `schemas/chapter_manifest.schema.json`,
  `tests/test_chapter_manifests.py`, `tests/fixtures/chapter_manifests/`,
  `docs/chapter_manifest_format.md`.
- Supersedes: None.

## DEC-0042: Phase 1.1 focus fix — close P1 missing-field bypass and P2 Schema conditions

- Date: 2026-07-30
- Status: Implemented locally; independent acceptance pending.
- Context: Phase 1.1 independent acceptance was NO-GO with two findings. P1: the
  validator accepted missing keys (`source_encoding`, scan null fields,
  `previous_id`/`next_id`) by treating `.get()` as default null. P2: Schema lacked
  `if/then/else` on `source_encoding` to differentiate primary/scan entry shapes.
- Decision: (a) Add explicit `"key" not in data`/`raw_entry` checks for
  `source_encoding` root field, five scan-null fields, and `previous_id`/`next_id`;
  all missing keys now produce `ChapterManifestValidationError`. (b) Restructure
  Schema with root `if/then/else`: `source_encoding=null`→`scan_entry` (5 fields
  must be null), else→`primary_entry` (typed constraints). Add `previous_id`/`next_id`
  `oneOf` constraints. (c) Add 8 missing-field tests + 5 new Schema structure tests.
  Total focused: 236. (d) `build_manifest` primary/scan paths remain compatible.
- Consequences: All 12 entry fields and the root `source_encoding` now require
  explicit key presence. Schema now fully distinguishes primary and scan entry
  shapes. 816 full tests continue to pass. Pending focused re-review.
- Evidence: `pipeline/chapter_manifests.py`, `schemas/chapter_manifest.schema.json`,
  `tests/test_chapter_manifests.py`.
- Supersedes: None.

## DEC-0043: Phase 1.1 Schema allOf/additionalProperties fix

- Date: 2026-07-30
- Status: Implemented locally; independent acceptance pending.
- Context: Schema `entry_base` had `additionalProperties:false` with `required` listing
  all 12 fields, but `properties` only defined 7. The 5 conditional fields
  (source_chapter_label, source_title, volume_label, source_offset, source_line)
  were only defined in `primary_entry`/`scan_entry` `allOf` branches, causing
  JSON Schema draft 2020-12 to reject them as additional properties.
- Decision: Add the 5 conditional fields to `entry_base.properties` with `{}`
  (unconstrained); keep `primary_entry`/`scan_entry` `allOf` branches for type
  refinements. Add `test_entry_base_properties_has_all_12_fields` asserting
  the complete property set.
- Consequences: Schema now structurally accepts all 12 fields at the base level
  while `allOf` branches refine types per primary/scan path. 237 focused,
  816 full tests pass. Pending focused re-review.
- Evidence: `schemas/chapter_manifest.schema.json`,
  `tests/test_chapter_manifests.py`.
- Supersedes: None.

## DEC-0044: Phase 1.1 documentation fix — Changelog structure and test evidence

- Date: 2026-07-30
- Status: Implemented locally; independent acceptance pending.
- Context: The CHANGELOG `[Unreleased]` section had a garbled structure (literal
  `n### Fixed`, truncated fact-candidate Schema Added entry, Phase 1.1 fix entries
  embedded in other bullets). Test counts in handoff files showed 816 but the
  current full unittest suite has 817 tests.
- Decision: (a) Rewrite the `[Unreleased]` `### Added`/`### Fixed` sections with
  clean structure: Phase 1.1 additions first, Phase 1.0 additions next, all fixes
  consolidated under one `### Fixed` heading. (b) Update PROJECT_MEMORY.md,
  PROJECT_STATE.md, NEXT_TASK.md test counts from 816 to 817. (c) Remove
  duplicate "Pending" lines in PROJECT_MEMORY.md. (d) Record that DEC-0043's
  816 count was a pre-correction snapshot. No code, Schema, test, or fixture
  changes.
- Consequences: Documentation now accurately reflects the current state. 817 full
  tests confirmed. Pending GPT-5.6-sol final re-review.
- Evidence: `CHANGELOG.md`, `PROJECT_MEMORY.md`, `PROJECT_STATE.md`,
  `NEXT_TASK.md`.
- Supersedes: None.

## DEC-0045: Phase 1.1 Changelog structure merge

- Date: 2026-07-30
- Status: Implemented locally; independent acceptance pending.
- Context: The `[Unreleased]` section had duplicate `### Added`, `### Fixed`,
  `### Changed`, and `### Verified` headings from historical incremental appends.
  DEC-0044 claimed "all fixes under one ### Fixed" but the file was inconsistent.
- Decision: Merge all entries under unique category headings in the fixed order
  Added → Fixed → Changed → Verified. No entries deleted or rewritten; only
  structure and heading deduplication changed. 73 Added bullets, 7 Fixed, 46
  Changed, 15 Verified all preserved.
- Consequences: CHANGELOG `[Unreleased]` is now structurally clean. No code,
  Schema, test, or fixture changes. Pending GPT-5.6-sol final re-review.
- Evidence: `CHANGELOG.md`.
- Supersedes: None.

## DEC-0046: Phase 1.1 Changelog count correction

- Date: 2026-07-30
- Status: Implemented locally; independent acceptance pending.
- Context: DEC-0045 recorded Changelog counts as "73 Added, 7 Fixed, 46 Changed,
  15 Verified". After the merge of (previous unreleased) sub-headings and full
  verification, the actual [Unreleased] counts are 99 Added, 7 Fixed, 20 Changed,
  15 Verified (total 141 bullets). No entries were deleted or rewritten; the
  discrepancy was a counting error in DEC-0045.
- Decision: Append DEC-0046 with corrected counts. No CHANGELOG, code, Schema,
  test, or fixture changes.
- Consequences: Documentation now accurately reflects the merged Changelog
  structure. 237 focused, 817 full tests unchanged. Pending GPT-5.6-sol final
  re-review (DEC-0041 through DEC-0046).
- Evidence: `CHANGELOG.md`, `DECISIONS.md`.
- Supersedes: Only DEC-0045's count numbers; the merge decision and scope
  remain unchanged.

## DEC-0047: Phase 1.1 independent acceptance — GO

- Date: 2026-07-30
- Status: Accepted
- Context: Phase 1.1 manifest validation and candidate source binding was
  implemented (`c69eeee`) and underwent four focus-fix rounds for P1/P2 findings
  (DEC-0042/0043/0044/0045/0046). GPT-5.6-sol performed final independent review
  and confirmed all findings closed.
- Decision: Record Phase 1.1 as independently accepted GO by GPT-5.6-sol.
  Applicable commits: `c69eeee` (initial), `2781e7c` (P1/P2 field presence +
  Schema conditions), `ecfca89` (Schema allOf/additionalProperties),
  `e350ee5` (Changelog structure + test counts), `ca34d7b` (section merge),
  `ec6bc62` (count correction), `56edcb2` (NEXT_TASK DEC range).
  Accepted evidence: 237 focused tests, 817 full unittest, compileall,
  original-demo validation, `check_repo_safety.py --history`,
  `git fsck --full --no-dangling`, `git diff --check`, Schema primary/scan
  path semantic verification, and build_manifest integration all passing.
  Local HEAD=`56edcb2`, `origin/main`=`1585a98`, ahead/behind=7/0, worktree
  clean, not pushed. Direct remote query not refreshed this session; must
  recheck before publishing.
- Consequences: Phase 1.1 is complete. No new implementation is authorized.
  Phase 1.2 (review decisions, canon writing, entity resolution, model
  integration, or any other work) requires a separate, explicit, scoped
  project-owner authorization. This does not authorize push.
- Evidence: `pipeline/chapter_manifests.py`, `schemas/chapter_manifest.schema.json`,
  `tests/test_chapter_manifests.py`, `docs/chapter_manifest_format.md`,
  `docs/fact_candidate_format.md`.
- Supersedes: Only DEC-0041's independent-acceptance-pending status.

## DEC-0048: Phase 1.2 fact-review document validation and claim-level review states

- Date: 2026-07-30
- Status: Implemented locally; independent acceptance pending.
- Context: After Phase 1.1 GO, the project owner authorized Phase 1.2: a
  fact-review document format encoding human review decisions (accepted,
  rejected, superseded, conflicted) on fact-candidate claims, with binding
  validation against FactCandidateDocument instances.
- Decision: (a) New `pipeline/fact_reviews.py` with frozen `ReviewDecision`
  (candidate_id, claim_id, state, reason, superseded_by_claim_id) and
  `FactReviewDocument`. (b) `validate_fact_review_document()` checks:
  format_version=1, review_id stable ID, source_chapter chapter_NNNNNN,
  reviewed_by non-blank, decisions non-empty, (candidate_id,claim_id) unique,
  state four-way enum, superseded_by_claim_id conditional (required non-blank
  when superseded, null otherwise). (c) `validate_fact_review_bindings()`
  checks source_chapter match, candidate/claim existence, supersede same-
  candidate non-self. (d) New Schema with `if/then/else` for superseded
  conditional. (e) 43 focused tests. (f) Not modified: `src/`, existing
  `pipeline/fact_candidates.py`, `pipeline/chapter_manifests.py`,
  `build_manifest.py`, existing schemas, original_demo, save.
- Consequences: Fact-review format is defined and validated. Cross-document
  conflicts, entity resolution, canon writing, and model integration remain for
  future slices. Pending GPT-5.6-sol independent acceptance.
- Evidence: `pipeline/fact_reviews.py`, `schemas/fact_review.schema.json`,
  `tests/test_fact_reviews.py`, `tests/fixtures/fact_reviews/`,
  `docs/fact_review_format.md`.
- Supersedes: None.

## DEC-0049: Phase 1.2 review binding documentation and test evidence

- Date: 2026-07-30
- Status: Implemented locally; independent acceptance pending.
- Context: Independent review found two P2 issues. P2-1: NEXT_TASK.md stated
  "full test pending" but 860 full tests had been verified. P2-2: fact-review
  documentation did not clarify that binding requires an explicit, pre-validated
  FactCandidateDocument, that source_chapter is not a global unique key, and
  that auto-discovery/file-matching/persistence are out of v1 scope.
- Decision: (a) Update NEXT_TASK.md, PROJECT_MEMORY.md, PROJECT_STATE.md with
  43/280/860 test evidence. (b) Expand Binding section in
  docs/fact_review_format.md with caller responsibility and boundary constraints.
  (c) Update docs/fact_candidate_format.md Review binding section to cross-
  reference the same boundary. No code, Schema, test, fixture, or CHANGELOG
  changes.
- Consequences: Documentation now accurately describes the binding boundary
  and test evidence. Pending GPT-5.6-sol focused re-review.
- Evidence: `docs/fact_review_format.md`, `docs/fact_candidate_format.md`,
  `NEXT_TASK.md`, `PROJECT_MEMORY.md`, `PROJECT_STATE.md`.
- Supersedes: None.

## DEC-0050: Phase 1.2 Markdown and DEC range fix

- Date: 2026-07-30
- Status: Implemented locally; independent acceptance pending.
- Context: docs/fact_candidate_format.md Review binding heading had leading `|`
  and trailing `|` from patch artifact. Handoff files referenced only DEC-0048,
  omitting DEC-0049.
- Decision: Remove stray pipe characters from Markdown. Update handoff files
  to reference DEC-0048 through DEC-0050. No code, Schema, test, fixture,
  or CHANGELOG changes.
- Consequences: Markdown is clean. Handoff DEC ranges are consistent.
  Pending GPT-5.6-sol final re-review.
- Evidence: `docs/fact_candidate_format.md`, `NEXT_TASK.md`,
  `PROJECT_MEMORY.md`, `PROJECT_STATE.md`.
- Supersedes: None.

## DEC-0051: Phase 1.2 independent acceptance — GO

- Date: 2026-07-30
- Status: Accepted
- Context: Phase 1.2 fact-review document validation was implemented (`80fd916`)
  with two P2 documentation corrections (DEC-0049, DEC-0050). GPT-5.6-sol
  performed final independent review and confirmed all findings closed.
- Decision: Record Phase 1.2 as independently accepted GO by GPT-5.6-sol.
  Applicable commits: `80fd916` (initial), `ceae065` (binding boundaries),
  `e742d20` (Markdown/DEC range). Accepted evidence: 43 fact-review focused,
  280 Phase 1.2+1.1+1.0 regression, 860 full unittest, compileall,
  original-demo validation, `check_repo_safety.py --history`,
  `git fsck --full --no-dangling`, `git diff --check` all passing.
  Local HEAD=`e742d20`, `origin/main`=`a55c7d8`, ahead/behind=3/0, worktree
  clean, not pushed. Direct remote query not refreshed this session; must
  recheck before publishing.
- Consequences: Phase 1.2 is complete. No new implementation is authorized.
  Phase 1.3 (entity resolution, canon writing, model integration, or any
  other work) requires a separate, explicit, scoped project-owner authorization.
  This does not authorize push.
- Evidence: `pipeline/fact_reviews.py`, `schemas/fact_review.schema.json`,
  `tests/test_fact_reviews.py`, `docs/fact_review_format.md`.
- Supersedes: Only DEC-0048's independent-acceptance-pending status.

## DEC-0052: L2W-1 canon draft promotion from reviewed facts

- Date: 2026-07-30
- Status: Implemented locally; independent acceptance pending.
- Context: After Phase 1.2 GO, the project owner authorized L2W-1: promote
  validated, reviewed, single-chapter fact data into a deterministic canon draft
  via an explicit PromotionPlan.
- Decision: (a) New `pipeline/canon.py` with `PromotionPlan`, `CanonDraft`,
  `CanonEntity`, `CanonClaim` frozen dataclasses, canonical value tagged union
  (text/relation/numeric/boolean/enum) using entity_ref instead of candidate_ref.
  (b) `validate_canon_promotion_plan()` for input structure. (c) `build_canon_draft()`
  for promotion closure (direct ∪ relation entities), source_chapter/plan/review
  consistency, relation rewriting, and self-validation. (d) `validate_canon_draft_document()`
  for output revalidation (entity_ref non-dangling, source_chapter match, etc.).
  (e) Deterministic CLI with atomic write (flush+fsync+os.replace). (f) Two new
  JSON Schema files. (g) 35 focused tests, 895 full tests.
- Consequences: Canon draft format is defined and validated. Cross-chapter
  merging, formal canon registry, and game adaptation remain for future slices.
  Pending GPT-5.6-sol independent acceptance.
- Evidence: `pipeline/canon.py`, `schemas/canon_promotion_plan.schema.json`,
  `schemas/canon_draft.schema.json`, `tests/test_canon.py`,
  `docs/canon_draft_format.md`.
- Supersedes: None.

## DEC-0053: L2W-1 acceptance rework — P1/P2 findings closed

- Date: 2026-07-30
- Status: Implemented locally; independent acceptance pending.
- Context: GPT-5.6-sol independent acceptance REVISE identified five P1 findings
  and four P2 documentation/tests issues. This decision records the fix commit.
- Fixes:
  (a) P1-1: build_canon_draft() now calls validate_fact_candidate_sources()
      and validate_fact_review_bindings() before computing closure.
  (b) P1-2: validate_canon_draft_document() uses two-pass: collect entity_ids
      first, then validate claims with full entity_id set.
  (c) P1-3: CLI rejects output path equal to any input path (normcase + samefile).
  (d) P1-4: tempfile.mkstemp replaces fixed .<output>.tmp path; _cleanup_tmp
      only removes the specific temp file created by this invocation.
  (e) P1-5: added stable-ID checks for source_candidate_id, numeric.unit,
      enum.enum_value in Python validator; Schema now has inference_basis
      if/then/else conditional.
  (f) P2: real relation-only entity test, CHANGELOG correction,
      production_workflow title fix, dead code removal, Schema structure tests.
- Evidence: 50 focused tests, 910 full tests, compileall, validate, safety, diff.
- Pending GPT-5.6-sol focused re-review.
- Supersedes: None.

## DEC-0054: L2W-1 independent acceptance — GO

- Date: 2026-07-30
- Status: Accepted
- Context: L2W-1 canon draft promotion from reviewed facts. Initial
  implementation at `2941641`. Acceptance rework at `1f01207` closed all
  P1-1 through P1-5 and related P2 findings.
- Decision: GPT-5.6-sol independently accepted L2W-1 GO with no remaining
  findings. 50 focused tests, 910 full tests, compileall, validate, safety,
  diff, fsck, and three CLI smokes all pass.
- Consequences: L2W-1 scope is complete. Cross-chapter merging, formal canon
  registry, and game adaptation remain for future slices.
- Supersedes: None. Does not authorize L2W-2 or any subsequent work.

## DEC-0055: L2W-2 micro content pack compilation from canon draft

- Date: 2026-07-30
- Status: Implemented locally; independent acceptance pending.
- Context: After L2W-1 GO, the project owner authorized L2W-2: compile a
  fixed micro-vignette content pack (1 room, 1 character, 1 plain item,
  1 no-effects dialogue, 1 auto-accepted collect_item quest) from a
  CanonDraft + explicit AdaptationPlan.
- Decision: (a) New `pipeline/adaptation.py` with frozen data models,
  `validate_adaptation_plan()` (structural), `compile_micro_pack()`
  (binding + coverage + cross-object references), `write_micro_pack()`
  (staged write + loader validate + manifest revalidate + atomic publish),
  and CLI `main()`. (b) `MicroContentPack` uses `tuple[CompiledDocument,...]`
  for deep immutability. (c) Text fields copied verbatim from plan. (d) Item
  output excludes heal/slot/bonus fields. (e) Quest auto-accepted via
  trigger_room. (f) Dialogue effects=[]. (g) adaptation_manifest.json sidecar.
  (h) Atomic publish rejects any existing output path. (i) 44 focused tests.
- Consequences: L2W-2 scope is complete. Pending GPT-5.6-sol independent
  acceptance.
- Evidence: `pipeline/adaptation.py`, `schemas/adaptation_plan.schema.json`,
  `schemas/adaptation_manifest.schema.json`, `tests/test_adaptation.py`,
  `tests/fixtures/adaptation/`, `docs/adaptation_plan_format.md`.
- Supersedes: None.

## DEC-0056: L2W-2 second rework — P1 findings closed

- Date: 2026-07-30
- Status: Implemented locally; independent acceptance pending.
- Context: GPT-5.6-sol second focused REVISE identified six P1 findings and
  P2 documentation/fixture gaps. This decision records the fix commit at
  `47a7c8a`.
- Fixes:
  (a) P1-1 Manifest: type-safe kind checks, cross-set game_id/CER uniqueness,
      binding∩omission disjoint, deterministic ordering in return value.
  (b) P1-2 MicroContentPack: restored approved dict/tuple semantic model
      (not bytes). JSON serialization moved to writer.
  (c) P1-3 Atomic write: document pre-validation before temp dir creation,
      second lexists right before os.replace, writer-level tests.
  (d) P1-4 Schema: stable ID for dialogue node/option/next ID. CLI explicit
      exception list (no bare `except Exception`).
  (e) P1-5 Tests: 58 tests (restored + new), >44. Nodes sorted by ID,
      options order preserved, 2+ omission/claim_ref determinism tests.
  (f) P2: Golden fixtures (valid_plan.json + expected_output/9 files),
      handoff sync, DEC-0056.
- Evidence: 58 focused tests, 968 full tests.
- Pending GPT-5.6-sol third focused re-review.
- Supersedes: None.

## DEC-0057: L2W-2 third rework — final P1 findings closed

- Date: 2026-07-30
- Status: Implemented locally; independent acceptance pending.
- Context: GPT-5.6-sol third focused REVISE identified remaining P1 findings.
- Fixes:
  (a) P1-1 Writer: flush+fsync restored (open/write/flush/fsync per file).
  (b) P1-2 Golden fixtures: mini_canon_draft.json + valid_plan.json are now a
      consistent pair; expected_output/9 files regenerated from them. Golden
      test loads both, compiles, compares 9 files byte-for-byte.
  (c) P1-3 Schema: start_node_id, node.id, option.id, next_node_id all use
      stable_id $ref. Schema structure tests assert exact $ref.
  (d) P1-4 MCP types: pack must be dict, 7 entity tuples must each contain
      dicts. Type error tests added.
  (e) P1-5 Tests: 72 tests (1 skipped symlink). Subprocess generate+validate.
      Writer-level traversal/extra/missing path tests.
  (f) P2: DEC-0057 appended. All handoff numbers synced.
- Evidence: 72 focused tests (1 skipped), 982 full tests. HEAD=`*current*`.
- Pending GPT-5.6-sol final focused re-review.
- Supersedes: None.
