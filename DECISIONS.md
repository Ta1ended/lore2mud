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

## DEC-0073: NarrativeModel v1 all-omission accounting correction - re-review pending

- Date: 2026-08-01
- Status: First independent acceptance returned REVISE/P2; local correction pending fresh re-review.
- Context: The original v1 documentation and decision require every scoped registry
  claim to be accounted for by a proposition use or a reasoned omission. The first
  clean reviewer constructed a plan that omitted every fixture claim with a non-blank
  reason and converted the affected propositions to `unknown`. It was otherwise
  valid but the parser and both Schemas rejected its empty `claim_uses` array.
- Decision: `scope.claim_uses` remains a required array but may be empty. The
  compiler remains responsible for binding the selected entities to the registry and
  rejects a claim unless it appears exactly as a use or a reasoned omission. Plan and
  model Schemas, parser, format documentation, and regressions all use this same
  contract.
- Evidence: The correction adds public plan/compiler/model/Schema coverage for an
  all-omission fixture-derived plan. It passes 42 focused tests with 2 Windows
  symlink permission skips, 1298 full unittest cases, and 1289 pytest cases with
  9 conditional skips per full suite. Ruff, Pyright, compileall, original-demo
  validation, history safety, fsck, and a repository-external standard golden plus
  all-omission CLI run pass. A fresh clean GPT-5.6-sol reviewer must inspect the
  final range before GO.
- Consequences: This correction neither generates canon nor relaxes foreign/missing
  provenance rejection. It does not authorize integration, `main` changes, push,
  release, private-material access, campaign compilation, Forge v2, or a review
  workbench.
- Supersedes: The empty-`claim_uses` restriction implied by the initial DEC-0072
  implementation only; DEC-0072's explicit complete-accounting rationale remains.

## DEC-0076: Public runtime campaign foundation v1

- Date: 2026-08-02
- Status: Implementation complete in an isolated worktree; fresh independent read-only review pending.
- Context: The 1-58 chapter playable prototype needs a reusable runtime layer that can carry
  multi-location campaigns, staged scenes, objectives, player-scoped knowledge, and atomic
  actions without turning dialogue into an untyped action soup or adding client-side rules.
- Decision: Add optional strict `campaign.json` v1 over the existing bounded declarative
  condition AST. World remains the single authority for dynamic projections (locations,
  exits, actors, dialogue text/options, scenes, interactables, actions, objectives,
  knowledge, journal) and for ordered atomic effects with full preflight and rollback.
  New saves write v9 and strictly preserve actor position/presence/enabled/incapacitated
  plus campaign scene/objective/knowledge state without replaying effects; v8 remains
  read-compatible only for packs without campaign, v7 only for packs with neither
  narrative state nor campaign. Two fictional cross-genre fixtures cover a magical staged
  event and an urban investigation with knowledge correction; no novel-specific names or
  content enter the public repository.
- Evidence: 382 focused/regression tests; 1333 full unittest and 1323 pytest pass with
  10 platform/symlink skips; compileall and diff checks pass. Ruff, Pyright, content
  validation for original_demo and both campaign fixtures, Draft 2020-12 schema checks,
  history safety, fsck, and desktop/390/320 browser interaction plus save/load now pass;
  a fresh read-only reviewer is still required before GO.
- Consequences: Campaign definitions remain optional and original_demo stays a 0.10.0
  pack in this slice; new saves are v9. This does not authorize campaign compilation from
  private canon, Forge v2, runtime LLM, scripting, or integration to `main`; it does not
  authorize reading chapters 59+ or publishing private material.
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

## DEC-0058: L2W-2 independent acceptance — GO

- Date: 2026-07-30
- Status: Accepted
- Context: L2W-2 micro content pack compilation from CanonDraft + AdaptationPlan.
  Initial implementation `e05c946`. Three rework rounds (`2cc6696`, `389c0b0`,
  `f7a977a`) closed all P1/P2 findings.
- Decision: GPT-5.6-sol independently accepted L2W-2 GO with no remaining code
  findings. 72 focused tests (1 skipped), 982 full tests (1 skipped).
  Evidence: code contracts verified, golden fixtures byte-identical, atomic
  write with fsync, MicroContentPack type safety, Schema stable IDs, real
  subprocess CLI, and loader validation all pass.
- Acceptance commit: `f7a977a2ced3e1a90bbd0cabb76803ff8bd93897`.
- Consequences: L2W-2 scope is complete. Cross-chapter merging, formal canon
  registry, and general game adaptation remain for future slices.
- Supersedes: DEC-0057's "已同步" claim was premature; this decision confirms
  the correct handling off numbers and clean Git state.
- Does not authorize: L2W-3, push, or any new feature work.

## DEC-0059: Codex-only GPT-5.6-sol development workflow

- Date: 2026-07-31
- Status: Active
- Context: Hermes is no longer available as an executor. The project owner directed
  Codex to run the development workflow end to end using GPT-5.6-sol.
- Decision: Codex is the sole active development Agent for planning, implementation,
  testing, handoff, and review tasks. All lore2mud development tasks select
  GPT-5.6-sol; if unavailable, implementation stops rather than silently switching
  models. The project owner approves slice scope and push but no longer transfers
  prompts between advisor and executor Agents. When independent acceptance is
  required, a fresh Codex review task or clean context performs a read-only review
  of the real baseline, commit, tests, safety checks, and gameplay evidence. An
  implementation context cannot self-declare GO from its own completion report.
- Consequences: `AGENTS.md` and `docs/production_workflow.md` now describe one
  Codex workflow with stage separation instead of Agent separation. Existing
  Hermes and Codex attribution in historical commits and decisions remains unchanged.
  Local commits still require explicit project-owner authorization before push.
- Supersedes: The active advisor/Hermes/manual-transfer workflow in DEC-0037 and
  later workflow references; it does not supersede their historical implementation
  or acceptance evidence.

## DEC-0060: L2W-3 explicit multi-chapter canon registry assembly

- Date: 2026-07-31
- Status: Implemented locally; independent acceptance pending.
- Context: After L2W-2 independent acceptance, the project owner authorized Codex
  to choose and implement the next bounded slice. A stable multi-chapter identity
  layer is required before broader adaptation can consume facts from several
  CanonDraft documents without guessing or overwriting provenance.
- Decision: (a) L2W-3 consumes at least two validated CanonDraft v1 inputs with
  unique promotion and chapter IDs plus a human-authored RegistryPlan v1.
  (b) The plan maps every `(promotion_id, source_entity_id)` exactly once, requires
  explicit registry names/aliases and `merge_reason`, permits at most one member
  per promotion in each registry entity, and cannot combine different entity types.
  (c) CanonRegistry v1 preserves every source name, alias, candidate,
  claim, review field, and chapter binding; claim identity is the composite
  `(promotion_id, source_entity_id, source_claim_id)`. Repeated and conflicting
  claims coexist without automatic deduplication or resolution. (d) Relation values
  are rewritten through the exact member mapping to registry entity IDs.
  (e) Sources, entities, aliases, members, claims, and JSON keys have canonical
  deterministic ordering. (f) The CLI rejects input/output aliases and writes one
  revalidated UTF-8 registry through same-directory tempfile + flush + fsync +
  `os.replace`, preserving an old output on failure. (g) No private corpus,
  engine, content-pack, save, dependency, or model integration is in scope.
- Evidence: baseline `b22bee33cacb154a2efc7e4eef0e3182ccc8319c` to current
  implementation HEAD; 80 focused tests and 1062 full tests (1 skipped) pass,
  together with compileall, original-demo validation, history safety,
  `git fsck --full --no-dangling`, `git diff --check`, golden output, and a real
  `python -m pipeline.canon_registry` subprocess flow.
- Consequences: explicit cross-chapter identity assembly and a formal immutable
  registry snapshot exist. Semantic conflict resolution, mutable registry storage,
  registry queries, broader game adaptation, L2W-4, private processing, and push
  remain outside this decision.
- Independent acceptance: Pending a fresh Codex GPT-5.6-sol read-only review.
- Supersedes: None.

## DEC-0061: L2W-3 independent-acceptance rework

- Date: 2026-07-31
- Status: Implemented locally; second independent acceptance pending.
- Context: A fresh GPT-5.6-sol read-only review of implementation commit
  `a89fdc6d819b976b80b82a74e575ff851ba86448` returned REVISE with one P1 and
  three P2 findings. Registry relation validation only required an existing target
  ID, members could reuse `(promotion_id, source_candidate_id)`, determinism tests
  bypassed the writer's exact bytes, and input/output link aliases lacked tests.
- Decision: (a) `validate_canon_registry_document()` requires each relation target
  to contain exactly one member from the relation claim's source promotion.
  (b) Registry members must be globally unique by both
  `(promotion_id, source_entity_id)` and `(promotion_id, source_candidate_id)`.
  (c) Writer, in-process CLI, and subprocess CLI tests compare output directly with
  the golden fixture bytes. (d) CLI alias tests cover hardlinks and cover symlinks
  when the runtime grants link-creation permission, while asserting source bytes
  remain unchanged. (e) The format document states these provenance constraints;
  no Schema change is needed because they are cross-object semantic checks.
- Evidence: 84 focused tests pass with one Windows symlink permission skip; 1066
  full tests pass with two skips. Compileall, original-demo validation, Draft
  2020-12 Schema + fixture validation, history safety, `git fsck --full
  --no-dangling`, `git diff --check`, and a repository-external real CLI whose
  output equals the golden bytes all pass.
- Consequences: All four first-review findings are closed locally, but L2W-3 is not
  GO until a new GPT-5.6-sol task or clean context independently re-reviews the
  correction. L2W-4, private processing, engine/content/save changes, and push are
  still outside this rework.
- Supersedes: None; refines DEC-0060 validation and acceptance evidence.

## DEC-0062: L2W-3 independent acceptance — GO

- Date: 2026-07-31
- Status: Accepted
- Context: A new GPT-5.6-sol Codex task with no implementation context performed a
  read-only re-review of acceptance correction `1c9a20bfade5bdb292ca3a801f00279cf0450e30`
  relative to initial implementation `a89fdc6d819b976b80b82a74e575ff851ba86448`.
- Decision: L2W-3 is accepted GO with no findings. The prior P1 relation-target
  traceability gap and three P2 candidate-provenance, golden-byte, and link-alias
  gaps are closed. The review independently confirmed semantic counterexamples,
  forward relations, full provenance correspondence, writer/in-process/subprocess
  golden bytes, all three hardlink input classes, and the complete one-commit scope.
- Evidence: 84 focused tests (1 Windows symlink permission skip), 1066 full tests
  (2 skips), compileall, original-demo validation, two Draft 2020-12 Schemas and
  fixtures, history safety, `git fsck --full --no-dangling`, `git diff --check`,
  and repository-external CLI all pass. Golden output is 6245 bytes with SHA-256
  `1f41c14cafec915e8e16bdc9a3c467aa64edd445ef1b6e66508790c2453bcfc6`.
  Scope is one 8-file commit (`+231/-66`), with no private material, `src/`, Schema,
  original-demo, save, content, or dependency changes. Acceptance snapshot:
  clean worktree, `origin/main=a89fdc6d`, ahead 1, not pushed.
- Residual risk: This Windows host cannot create symlinks (`WinError 1314`), so that
  path is statically reviewed and conditionally skipped. Cross-object provenance is
  intentionally enforced by Python rather than JSON Schema. Generic path-swap TOCTOU
  remains outside the trusted local CLI contract.
- Consequences: L2W-3 is complete. The project owner requested an immediate pause;
  no L2W-4 implementation starts in this session. The next bounded candidate is a
  registry-backed micro adaptation that keeps L2W-2's one-room profile.
- Supersedes: DEC-0061's pending acceptance status; it does not alter DEC-0060's
  implemented contract or historical first-review evidence.

## DEC-0063: L2W-4 registry-backed micro adaptation

- Date: 2026-07-31
- Status: Implemented locally; independent acceptance pending.
- Context: After L2W-3 independent GO, the project owner restored the autonomous
  Goal and authorized Codex to choose the next bounded public-safe slice. The
  first registry consumer must preserve L2W-2's one-room gameplay profile while
  making every cross-chapter claim choice explicit.
- Decision: (a) A separate `pipeline.registry_adaptation` module consumes a
  validated `CanonRegistry v1` and a strict `RegistryAdaptationPlan v1`.
  (b) The plan binds exactly one location, character, and item, lists every
  selected claim by the composite `(promotion_id, source_entity_id,
  source_claim_id)`, and explicitly omits every other registry entity. Selected
  claims must span at least two promotions; registry IDs and versions must match.
  (c) Game text and numbers are copied verbatim from the plan. The compiler does
  not infer, rewrite, merge, or resolve conflicting claims. It derives
  `canon_ref.source_chapters` and manifest binding chapters from selected claims.
  (d) Output remains one room, one character, one plain item, one game-only
  collect-item quest, one game-only dialogue, and empty monsters/shops; no
  `src/`, original demo, save, dependency, or private-material changes are in
  scope. (e) The sidecar is
  `registry_adaptation_manifest.json`; it records complete registry sources,
  registry ID/version, composite refs, chapters, omissions, and game-only
  entries. The writer validates before staging, fsyncs all nine files, loads the
  staged pack, revalidates the manifest, checks the destination again, and uses
  same-directory atomic replace without overwriting an existing output.
- Evidence: 39 focused tests (1 Windows symlink permission skip), 1105 full
  unittest cases (3 skips), compileall, both Schema JSON parses, fictional
  fixture/golden validation, original-demo validation, `check_repo_safety.py
  --history`, `git fsck --full --no-dangling`, `git diff --check`, and an
  external-temp-directory CLI plus `lore2mud validate`; external manifest output
  is 2840 bytes with SHA-256
  `4d09e4126364e3f6e3967780ae30688204e9e7030a13c3a196052cfe5f31fe7c`.
- Implementation commit: `1fb95bf8fce42428188d6d9d06b1a68397f8d999`, relative to
  baseline `a19707521ed0dcc162abf2448254c086a1bf58af`. After the commit,
  `origin/main` remains `a89fdc6d819b976b80b82a74e575ff851ba86448` and the local
  branch is ahead by 3; a direct GitHub `main` query was reset by the network.
- Consequences: L2W-2's existing `CanonDraft + AdaptationPlan v1` route remains
  unchanged. This slice deliberately does not add semantic conflict resolution,
  mutable registry/query, multi-room expansion, or private processing. A fresh
  GPT-5.6-sol Codex task or clean context must independently review the real
  implementation commit before the slice can be called GO. Local commits are not
  pushed automatically.
- Supersedes: None.

## DEC-0064: L2W-4 independent acceptance - GO

- Date: 2026-07-31
- Status: Accepted
- Context: A fresh GPT-5.6-sol Codex task performed a read-only review of
  implementation commit `1fb95bf8fce42428188d6d9d06b1a68397f8d999`
  relative to baseline `a19707521ed0dcc162abf2448254c086a1bf58af`.
- Decision: L2W-4 is accepted GO with no P0-P3 findings. The review independently
  confirmed the frozen plan and manifest contracts, exact entity/claim/omission
  coverage, composite provenance, registry identity and version checks, derived
  chapters, deterministic nine-file output, staged loader validation, atomic
  writer behavior, and the unchanged one-room gameplay profile.
- Evidence: 39 focused tests passed with one Windows symlink permission skip;
  72 unchanged L2W-2 regression tests passed with one skip; 1105 full unittest
  cases passed with three skips. Compileall, both Draft 2020-12 Schemas, the
  fictional plan and golden fixture, original-demo validation, history safety,
  `git fsck --full --no-dangling`, working-tree and implementation-range
  `git diff --check`, repository-external CLI compilation, loader validation,
  and a real World pickup/quest playthrough all passed. All nine output files
  matched golden bytes; the manifest is 2840 bytes with SHA-256
  `4d09e4126364e3f6e3967780ae30688204e9e7030a13c3a196052cfe5f31fe7c`.
- Acceptance snapshot: clean worktree at
  `77f1fa795bd3f7c0ba6b565a57809459db31ee0d`; tracking
  `origin/main=a89fdc6d819b976b80b82a74e575ff851ba86448`, ahead/behind
  `4/0`, not pushed. A direct `git ls-remote --heads origin main` timed out, so
  no live GitHub state is claimed.
- Residual risk: This Windows host cannot create symlinks, so that conditional
  alias test remains skipped and its `lexists` path was statically reviewed. The
  narrow check-to-replace TOCTOU window remains inside the trusted local CLI
  assumption.
- Consequences: L2W-4 is complete. Semantic conflict resolution, mutable registry
  storage, multi-room adaptation, private-material processing, release, and push
  remain outside this acceptance. The next public-safe slice may add a bounded,
  read-only registry inspection artifact without changing canon or game state.
- Supersedes: Only DEC-0063's independent-acceptance-pending status; it does not
  change the implemented L2W-4 contract.

## DEC-0065: L2W-5 explicit read-only registry inspection report

- Date: 2026-07-31
- Status: Implemented locally; independent acceptance pending.
- Context: After L2W-4 independent GO, the autonomous GPT-5.6-sol Goal selected
  the smallest public-safe follow-up needed before larger adaptation planning:
  reviewers need a deterministic way to isolate exact registry entities without
  name search, semantic inference, or a mutable query layer.
- Decision: (a) `pipeline.registry_inspection` consumes a fully validated
  `CanonRegistry v1` and a strict `RegistryInspectionPlan v1`. The plan matches
  registry ID/version and selects one or more unique stable entity IDs. (b) The
  `RegistryInspectionReport v1` contains exactly that sorted entity set and copies
  every entity field, member, source candidate ID, and composite claim source
  without rewriting or resolving conflicts. Relation targets may remain outside
  the selected set. (c) The report source array contains exactly the complete
  source records used by selected claims; an entity with no claims has an empty
  source subset while retaining its members. (d) Python validators enforce exact
  selection/source coverage, nested CanonRegistry contracts, NFKC alias rules,
  member/candidate/claim provenance uniqueness, claim/source chapter binding, and
  canonical order. Two Draft 2020-12 Schemas provide strict structural contracts.
  (e) The CLI rejects registry, plan, and output path aliases, including hardlinks
  and symlinks when available. Its single-file writer revalidates before creating
  a same-directory tempfile, then writes, flushes, fsyncs, and atomically replaces;
  failure preserves an existing unrelated output and cleans its own tempfile.
- Evidence: 49 L2W-5 focused tests pass with one Windows symlink permission skip;
  172 L2W-3/L2W-4/L2W-5 focused and regression tests pass with three skips; 1154
  full unittest cases pass with four skips. Compileall, both Schemas under
  `Draft202012Validator`, original-demo validation, history safety,
  `git fsck --full --no-dangling`, whitespace checks, and a repository-external
  subprocess CLI all pass. The fictional golden report copies one cross-chapter
  character, two members, four claims, two source records, conflicting role claims,
  and unselected relation targets. It is 4144 bytes with SHA-256
  `f943f6f487bcca607d854023c32b0a663ede25069700f707637420a5857eebb5`;
  registry and plan input hashes remain unchanged.
- Implementation baseline: `9f09d9691a236919648cea294c31fcdf0f105ff9`.
  The implementation and handoff are one local commit containing this decision;
  use live `git rev-parse HEAD` for its commit ID.
- Consequences: L2W-5 does not modify CanonRegistry v1, L2W-2, L2W-4, `src/`,
  original_demo, save, dependencies, or private material. Fuzzy/full-text/semantic
  search, mutable storage, conflict resolution, adaptation, multi-room output,
  private processing, release, and push remain outside scope. A fresh GPT-5.6-sol
  Codex task or clean context must independently review the implementation before
  GO. The local commit makes GitHub `main` lag by more than five commits under the
  current tracking snapshot, so development pauses for project-owner push.
- Supersedes: None.

## DEC-0066: L2W-5 independent acceptance - GO

- Date: 2026-07-31
- Status: Accepted.
- Context: A fresh GPT-5.6-sol Codex task independently reviewed the read-only,
  single-commit range `9f09d9691a236919648cea294c31fcdf0f105ff9..`
  `13be791bc0a116f6596267b5d914a8a63e511f1f` (17 files, `+2455/-39`).
- Decision: Accept L2W-5 GO with no P0-P3 findings. Exact stable-ID selection,
  complete entity/member/candidate/claim preservation, exact claim-source subsets,
  conflicts, external relation targets, strict Schemas, deterministic writer, and
  repository-external CLI bytes satisfy the bounded read-only contract.
- Evidence: 49 focused tests passed with one Windows symlink permission skip;
  172 L2W-3/L2W-4/L2W-5 regression tests passed with three skips; 1154 full
  unittest cases passed with four skips. Compileall, original-demo validation,
  Schema/fixture checks, history safety, `git fsck --full --no-dangling`, diff
  checks, and repository-external CLI/golden bytes passed. The CLI output is
  4144 bytes with SHA-256
  `f943f6f487bcca607d854023c32b0a663ede25069700f707637420a5857eebb5`.
- Acceptance snapshot: `HEAD=origin/main=GitHub main=13be791bc0a116f6596267b5d914a8a63e511f1f`,
  clean worktree. No push, release, or private-material access occurred in review.
- Consequences: L2W-5 is complete. This GO does not authorize fuzzy search,
  mutable registry state, conflict resolution, private processing, or release.
- Supersedes: DEC-0065's independent-acceptance-pending status only.

## DEC-0067: Project-owner-authorized isolated five-domain parallel sprint

- Date: 2026-07-31
- Status: Implemented and integrated; final acceptance recorded in DEC-0068.
- Context: After L2W-5 GO, the project owner explicitly authorized four or more
  concurrent GPT-5.6-sol Goal tasks. The former single-slice and five-commit lag
  rules were too restrictive for this bounded experiment.
- Decision: Use isolated worktrees and branches for Core, Forge, Player, Quality,
  and Ship, with one controller owning boundaries, integration order, conflict
  handling, final candidate, and handoff. Keep shared `main` read-only. Workers
  commit only their responsibility domain and report cross-domain interfaces to the
  controller. Neither local commits nor GO automatically modify `main`, push, or release.
- Integrated scope: Core upgrades the original demo to 0.9.0 with nine rooms,
  eight items, four monsters, two characters, eight quests and a confirmable ending.
  Forge adds resumable `init/status/check/run/rerun` orchestration with fingerprints,
  immutable artifacts, locking and recovery. Player adds a standard-library
  loopback Web session/UI with structured actions. Quality adds Ruff, Pyright,
  pytest/xdist and multi-version CI. Ship adds PyInstaller primary and zipapp
  fallback Windows candidates, diagnostics, manifests and cold-start checks.
- Repair history: `8207228` received REVISE for unguarded oversized
  `Content-Length` conversion, a Forge POSIX junction mock omission, and possible
  Windows TCP reset during early POST rejection; `a27b363` closed all three. The
  next review found browser recovery unreachable after defeat and a 320px
  dead-state overflow; `a172a82` closed both without expanding scope.
- Consequences: An explicitly authorized isolated sprint is an exception to the
  default one-slice and lag-count hard-stop rules. Once an integrated candidate
  exists, no scope is added until acceptance and the publish gate finish. Private
  novel material remains outside every responsibility domain.
- Supersedes: The absolute single-slice and five-commit hard-stop rules for
  explicitly authorized isolated parallel sprints only; default sequential
  development and no-automatic-push rules remain in force.

## DEC-0068: Five-domain parallel integration candidate - GO

- Date: 2026-07-31
- Status: Accepted.
- Context: The integration branch contains all five domains and both repair rounds.
  A fresh GPT-5.6-sol Codex task independently rechecked final repair range
  `a27b363..a172a82` after the earlier full cross-platform pass.
- Decision: Accept code candidate
  `a172a82a0c70812b8ff5429de3ec4b309ad75cd5` GO with no P0-P3 findings.
  Browser recovery and narrow layout are fixed; all earlier protocol, Forge,
  packaging and platform findings remain closed. No third full acceptance cycle is
  required unless candidate code or remote ancestry changes.
- Cross-platform evidence: Linux Python 3.11 and 3.12 serial plus 3.13 xdist each
  passed `1248 / 3 skipped`; Windows pytest serial and xdist each passed
  `1243 / 8 skipped`; Windows unittest ran 1251 cases with `OK / 8 skipped`.
  Final Web focused tests passed 35/35; Web plus packaging ran 48 cases with
  47 passed and one expected toolchain skip. Ruff, Pyright, Node syntax,
  compileall, validation, current/history safety, fsck, and diff checks passed.
  At 320x720 the defeated view had `scrollWidth=clientWidth=305`; recovery restored
  `room_ember_wharf` and HP `20/20` with no console warnings/errors.
- Delivery evidence: repository-external PyInstaller candidate is 8,804,173 bytes,
  72 manifest files, SHA-256
  `a11458b491dd862618cada085df895b9db8bb42e73c992eb3a2d75acb9807c75`.
  Zipapp fallback is 75,672 bytes, 13 manifest files, SHA-256
  `41c85e35cd750a5cdb964bd9010ac8634d11699f5dc0f40159e377f687a176bc`.
  Both record exact `source_commit=a172a82a0c70812b8ff5429de3ec4b309ad75cd5`
  and passed repository-external Web/console cold starts.
- Git snapshot: the integration worktree was clean at `a172a82`; local
  `main=origin/main=GitHub main=13be791bc0a116f6596267b5d914a8a63e511f1f`,
  so the integration branch was ahead/behind `13/0`. It was not merged, pushed,
  or released during acceptance.
- Residual risk: Windows symlink permission branches remain conditionally skipped.
  The ignored integration-worktree `dist/windows` is an old `8207228` build and is
  not a release candidate.
- Consequences: The branch is ready for fast-forward and push after explicit owner
  authorization and a fresh remote check. A following documentation-only seal does
  not change the artifact source commit.
- Supersedes: DEC-0067's final-acceptance-pending state and all REVISE findings
  listed there; it does not authorize automatic push or release.

## DEC-0069: Frozen Windows CLI output is explicitly UTF-8

- Date: 2026-07-31
- Status: Implemented locally; independent acceptance pending.
- Context: After `6761e0850a367308a29f9b8189cb08715fb0cb03` reached GitHub
  `main`, Actions `quality` run `30642616305` succeeded. Separate `tests` run
  `30642616101` passed all three Python unittest jobs but failed
  `windows-candidate`. The pinned PyInstaller
  executable built and started successfully; its diagnostic `validate` call then
  raised `UnicodeEncodeError` at `src/lore2mud/cli.py:69` while printing Chinese
  through redirected `cp1252` stdout. The verifier already supplied
  `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8`, but the isolated frozen runtime did
  not use those environment settings.
- Decision: `lore2mud.cli.main()` reconfigures stdout and stderr to UTF-8 before
  argparse or command output only for a PyInstaller frozen process or when the
  official launcher supplies `LORE2MUD_UTF8_IO=1`. Streams without `reconfigure`
  remain unchanged, and ordinary embedded/test calls do not mutate their host
  streams. The bundled PowerShell launcher supplies that signal and aligns console
  input, console output, and pipeline output to UTF-8 so a fixed executable does
  not merely replace the crash with mojibake. A regression invokes real validation
  with `cp1252` `TextIOWrapper` streams under a simulated frozen runtime and asserts
  UTF-8 Chinese output. No content, save, Web protocol, dependency, or private-
  material contract changes.
- Evidence: The pre-fix local `cp1252` reproduction raised the same traceback at
  `cli.py:69`; the corrected frozen-runtime reproduction exits 0 and decodes the
  success line as UTF-8. The final 25-test CLI suite proves both the frozen UTF-8
  path and ordinary host-stream preservation. After installing the pinned
  toolchain, the real PyInstaller 6.21.0 resource and repository-external
  diagnostic/console/Web cold-start test passed. The full unittest suite passed
  1254 tests with 7 existing conditional skips; xdist pytest passed 1247 with the
  same 7 skips using a fresh repository-local `--basetemp` after the host's default
  pytest temp root returned `WinError 5` before collection. Ruff, Pyright,
  compileall, original-demo validation, history safety,
  `git fsck --full --no-dangling`, and `git diff --check` also passed.
- Git snapshot: local `HEAD=origin/main=GitHub main=6761e0850a367308a29f9b8189cb08715fb0cb03`.
  The implementation and handoff are an uncommitted working-tree diff; no push or
  release occurred in this task.
- Consequences: DEC-0068 remains the historical integration acceptance, but its
  Windows delivery evidence is not sufficient for the published runner locale.
  This narrow correction requires fresh clean-context independent acceptance
  before a local commit or project-owner-authorized push. The next remote run must
  be checked directly; local success is not proof that GitHub Actions is green.
- Supersedes: Only the immediate direct-push next action recorded after DEC-0068;
  it does not supersede the accepted Core, Forge, Player, Quality, or Ship scope.

## DEC-0070: Windows UTF-8 CI hotfix - GO

- Date: 2026-08-01
- Status: Accepted.
- Context: A fresh GPT-5.6-sol Codex review independently inspected the complete
  eight-file working-tree diff against published baseline
  `6761e0850a367308a29f9b8189cb08715fb0cb03`. The review also queried GitHub
  Actions directly: `tests` run `30642616101` has three successful Python jobs
  and only `windows-candidate` failed, specifically at `Test Windows packaging`;
  `quality` run `30642616305` succeeded at the same source commit.
- Decision: Accept the DEC-0069 hotfix GO with no P0-P3 findings. The frozen
  runtime guard fixes the failing PyInstaller path, the launcher signal covers the
  zipapp path, streams without `reconfigure` remain supported, and an ordinary
  embedded call preserves its host encoding. The scope remains limited to CLI
  delivery encoding, the official launcher, regression tests, and handoff records.
- Evidence: The combined CLI and Windows packaging suite passed all 38 tests and
  built a real pinned PyInstaller 6.21.0 executable. Repository-external
  diagnostic, console, and Web/API cold starts passed for PyInstaller and zipapp
  candidates. Full unittest passed 1254 tests with 7 conditional skips; focused
  pytest passed 38 tests; full xdist pytest passed 1247 tests with the same 7
  skips. Ruff passed, Pyright reported 0 errors, and compileall, original-demo
  validation, history safety, `git fsck --full --no-dangling`, and
  `git diff --check` passed.
- Git snapshot: Before the local hotfix commit, local `HEAD`, tracking
  `origin/main`, and direct GitHub `main` all resolved to
  `6761e0850a367308a29f9b8189cb08715fb0cb03`; ahead/behind was 0/0 and the
  reviewed diff contained only the three implementation/test paths plus five
  synchronized handoff files. No push or release occurred during acceptance.
- Consequences: The reviewed diff may be recorded as one local commit on `main`
  and is then ready for the project owner to push after a fresh remote ancestry
  check. The pushed commit still requires new GitHub `quality` and `tests` runs;
  local GO is not remote CI success and does not authorize release or new scope.
- Supersedes: DEC-0069's independent-acceptance-pending state only.

## DEC-0071: GEN-1 generic narrative state and conditions - re-review pending

- Date: 2026-08-01
- Status: Local REVISE corrections verified; fresh independent acceptance pending.
- Context: The isolated branch `codex/gen1-narrative-conditions` starts from
  `e6070bd7ba31e0a5e45dfdf4e213b51e9f3f0ca1`; its initial implementation is
  `9e2d30130baf716cda0d9f52a638f10950d04cd2`. It adds a generic narrative
  state/condition foundation without reading or writing any private material.
  The first fresh review returned three P2 findings: present `int.minimum` and
  `int.maximum` accepted JSON `null`, Windows delivery guidance still described
  0.9.0/v7, and required continuity files were stale.
- Decision: (a) An absent integer bound remains optional, but a present bound
  must be a non-bool integer; explicit `null` is rejected by the loader and is
  covered for both `minimum` and `maximum`. (b) The Windows candidate document
  names `content-0.10.0`, save v8, and v7's narrow compatibility only for packs
  without narrative state. (c) All five continuity files record the corrected
  local state; the changelog, state, task, memory, and decision records preserve
  that independent re-review is pending. (d) The underlying GEN-1 contract remains
  typed bool/int/enum state, a strict bounded condition AST, World-authoritative
  dialogue projection, and save v8 for stateful packs; it does not add scripts,
  `eval`, LLM integration, runtime authority outside World, or private content.
- Evidence: The correction passes 17 focused GEN-1 tests, 13 Windows packaging
  tests including a real PyInstaller cold start, 1272 full unittest cases, and
  1265 pytest cases, each suite with 7 conditional skips. Ruff, Pyright,
  compileall, original-demo validation, `check_repo_safety.py --history`, and
  `git fsck --full --no-dangling` pass.
  `jsonschema` is not installed and is not added for meta-validation; JSON
  parsing, strict loader contracts, and runtime coverage provide the local gate.
- Consequences: This is not a GO. A new clean GPT-5.6-sol read-only review must
  inspect `e6070bd..HEAD`, the exact null-bound rejection, packaging guidance,
  handoff synchronization, and named evidence before integration. No change to
  `main`, push, release, or another feature is authorized by this record.
- Supersedes: No prior decision; it records the GEN-1 implementation and closes
  only the first review's local correction work.

## DEC-0072: NarrativeModel v1 deterministic public compiler - recovered integration record

- Date: 2026-08-01
- Status: Individual independent acceptance now GO; final integration acceptance pending.
- Context: The original `workstream/narrative-model-v1` decision was omitted by
  the handoff-file merge even though the public implementation and its correction
  were merged. This record restores the v1 scope without changing the historical
  DEC-0073 correction record.
- Decision: `pipeline.narrative_model` compiles a validated CanonRegistry and an
  explicit human NarrativePlan into a deterministic NarrativeModel. Plans scope
  exact entity IDs and account for every scoped claim as a proposition use or a
  reasoned omission. The model retains exact composite provenance and only the
  named claim-promotion source records. Perspectives, proposition states,
  contiguous phases, DAG beats, disclosure states, canonical serialization,
  atomic writing, and path-alias rejection are structurally validated. The
  compiler neither generates canon nor resolves conflicts; all fixtures remain
  fictional and public.
- Evidence: The initial implementation received a REVISE for rejecting valid
  all-omission plans. DEC-0073 corrected that contract, and a new clean
  GPT-5.6-sol review accepted `8ddc89c1a458e282dbea54b7419ba1db9b8207d8` GO
  with no P0-P3 findings after focused, full, Schema, external CLI, quality, and
  repository-safety gates.
- Consequences: This decision does not authorize runtime integration, canon
  generation, private-material access, campaign compilation, Forge v2, a review
  workbench, push, or release.
- Supersedes: The missing handoff record only; DEC-0073 remains the correction
  decision and DEC-0074 records the combined final gate.

## DEC-0074: Public narrative foundations integration candidate - final acceptance pending

- Date: 2026-08-01
- Status: Both isolated slices independently accepted GO; final clean integration acceptance pending.
- Context: The project owner authorized local-only completion of the already
  reviewed public GEN-1 and NarrativeModel v1 slices, but not a push, release,
  private-material access, or a new product lane.
- Decision: Merge GEN-1 `e7cba52fcfdf0c04458fca5fb9b516ebc762f4bc` and
  NarrativeModel v1 `8ddc89c1a458e282dbea54b7419ba1db9b8207d8` on baseline
  `e6070bd7ba31e0a5e45dfdf4e213b51e9f3f0ca1` into public candidate
  `dcd9bb0b21eb667061e2694a462f63e252636545`. Keep the runtime/save/Web changes
  of GEN-1 and the standalone public compiler of NarrativeModel v1 separate in
  scope, while testing their combined repository state before local `main` moves.
- Evidence: GEN-1's clean re-review found no P0-P3 findings and passed 17 focused,
  13 Windows packaging, 1272 unittest, and 1265 pytest cases plus the named
  quality/safety gates. NarrativeModel's clean re-review found no P0-P3 findings
  and passed 44 focused, 1298 unittest, and 1288 pytest cases plus Schema and
  repository-external CLI coverage. The controller must rerun combined gates and
  obtain a distinct clean read-only decision before claiming final GO.
- Consequences: Until that decision, this candidate cannot update `main`, be
  pushed, released, or expanded into RegistryCampaignPlan, Forge v2, a review
  workbench, or private content.
- Supersedes: The individual-acceptance-pending states in DEC-0071 and DEC-0073
  only; it does not supersede their technical contracts.

## DEC-0075: Public narrative foundations final integration acceptance

- Date: 2026-08-01
- Status: Accepted locally; continuity seal fast-forwarded to local `main`, not pushed or released.
- Context: GEN-1 and NarrativeModel v1 had each passed an isolated clean review,
  but their merged repository state still required its own independent decision.
- Decision: The clean read-only review accepts public candidate
  `dcd9bb0b21eb667061e2694a462f63e252636545` GO with no P0-P3 findings. Its
  parents are exactly GEN-1 `e7cba52fcfdf0c04458fca5fb9b516ebc762f4bc` and
  NarrativeModel v1 `8ddc89c1a458e282dbea54b7419ba1db9b8207d8`; baseline
  `e6070bd7ba31e0a5e45dfdf4e213b51e9f3f0ca1` is an ancestor. The authorized
  local closeout is a continuity-only commit followed by a fast-forward from
  local `main`; it does not query or change any remote.
- Evidence: The independent reviewer found no P0-P3 issues in the v8/v7 save
  boundary, World-authoritative dialogue filtering, Windows package resources,
  exact NarrativeModel use/omission accounting including all-omission plans,
  canonical writer, CLI alias rejection, or continuity records. It verified 72
  focused/package tests with 2 symlink-permission skips, 1316 unittest tests
  with 9 platform/permission skips, and 1307 pytest tests with 9 corresponding
  skips. Ruff, Pyright, compileall, original-demo validation, repository-external
  golden CLI bytes, history safety, fsck, and diff checks passed.
- Consequences: The project owner may refresh remote state and perform a normal
  push only after confirming ancestry. This acceptance does not authorize a
  release, force push, private-material access, or any subsequent lane.
- Supersedes: DEC-0074's final-integration-pending state only.

## DEC-0077: CampaignSpec v1 deterministic campaign IR - independent acceptance pending

- Date: 2026-08-02
- Status: Local implementation and verification complete; fresh independent acceptance pending.
- Context: The accepted NarrativeModel v1 remains a standalone narrative artifact.
  A downstream private Demo requires a public-safe, genre-neutral boundary that can
  represent a multi-location, multi-actor, multi-scene, multi-objective campaign
  before runtime content, saves, Web, and Forge are expanded.
- Decision: Add `RegistryCampaignPlan v1` and `CampaignSpec v1` as a pure
  deterministic compiler in `pipeline.campaign`. A plan must bind the exact
  canonical NarrativeModel SHA-256 and account for every model entity,
  perspective, proposition, and beat as an exact use or one reasoned omission.
  Campaign bindings validate a reachable directed location graph, source-ordered
  scene DAG with physically traversable locations, objective DAGs whose mutual
  exclusions cannot make prerequisite closure impossible, exact disclosure
  projection, totally ordered knowledge tracks, and explicit adaptation-only
  correction records. The spec embeds the validated NarrativeModel snapshot and
  is written as canonical UTF-8 JSON through the existing atomic alias-resistant
  pattern. Both public fixtures are wholly original and cover different genres.
- Evidence: On baseline `812a00fe4412f4fc7068ac2e188c5c26d0a03157`,
  41 focused campaign tests passed with 2 Windows symlink-permission skips;
  1357 full unittest tests passed with 12 skips; full pytest reported
  1345 passed / 12 skipped. Ruff, both Pyright checks, compileall, Draft 2020-12
  meta-validation and all four plan/spec fixture instances, original-demo
  validation, repository-external golden CLI bytes, history safety, fsck, and
  whitespace checks passed.
- Consequences: This is not an independent GO. A fresh GPT-5.6-sol/max read-only
  task must inspect `812a00f..HEAD` and return GO/REVISE before integration.
  The slice does not generate runtime content, modify `src/`, save, Web, Forge,
  packaging or dependencies, access private material, change shared `main`, or
  authorize push/release.
- Supersedes: The stale post-DEC-0075 pause boundary in current handoff files only;
  it does not supersede NarrativeModel, GEN-1, or their acceptance decisions.

## DEC-0078: CampaignSpec v1 independent-review corrections - re-review pending

- Date: 2026-08-02
- Status: Local REVISE corrections verified; fresh independent acceptance pending.
- Context: A fresh GPT-5.6-sol/max read-only review of
  `812a00fe4412f4fc7068ac2e188c5c26d0a03157..8f3e53452ccf12ce6e6b262f64f85fcd0011d76b`
  returned REVISE. It found two P2 semantic gaps: an `apply_knowledge` completion
  needed only an existing knowledge/correction ID and could therefore complete an
  objective from an unrelated or later scene; and `start_location_ref` could differ
  from the sole player's starting location, so root reachability did not prove the
  player's first required scene was reachable. It also found a P3 README omission
  for the campaign compiler CLI and format link.
- Decision: The sole player's `starting_location_ref` is required to be non-null
  and exactly equal to authoritative `start_location_ref`. Completion resolution is
  uniform across all four kinds: the target location must host, the actor must
  participate in, the scene must be, or the knowledge transition must occur in a
  scene listed by the containing objective and in that objective's exact phase.
  Existing scene DAG, source-order, and directed-travel checks remain authoritative.
  Both plan and spec share this semantic validator and Schema definitions; the
  README exposes the exact `python -m pipeline.campaign` arguments and links the
  format guide. No runtime, save, Web, Forge, packaging, dependency, or private
  material scope is added.
- Evidence: Public mutation regressions cover later and earlier phase knowledge,
  unrelated same-graph locations and actors, an earlier completion scene, and a
  market-root/crown-player/no-return route whose first scene remains at the base.
  Plan, self-contained spec, and typed compile entry points reject the relevant
  mutations. Local verification passed 45 focused campaign tests with 2 Windows
  symlink-permission skips, 1361 unittest tests with 12 skips, and 1349 pytest tests
  with 12 skips. Ruff, both Pyright entry points, compileall, Draft 2020-12 Schema
  meta-validation and fixtures, original-demo validation from the candidate source
  path, repository-external golden CLI bytes, history safety, fsck, and whitespace
  checks passed.
- Consequences: This correction is not a GO. A new GPT-5.6-sol/max read-only task
  must review `812a00f..HEAD` findings-first and return explicit GO/REVISE before
  any integration. It does not authorize modifying shared `main`, push, release,
  private-material access, or the next public runtime slice.
- Supersedes: DEC-0077's claim that first independent acceptance was merely pending;
  it does not supersede the CampaignSpec v1 contract or any prior accepted slice.

## DEC-0079: CampaignSpec completion targets are isolated across every possible scene

- Date: 2026-08-02
- Status: Local second-review correction verified; fresh independent acceptance pending.
- Context: A fresh read-only re-review of the DEC-0078 candidate reproduced one
  remaining P2. Completion validation accepted a target when at least one matching
  scene was objective-owned and in-phase, even if the same location or actor also
  appeared in an earlier or later scene. Adding an excluded branch scene to the
  current objective also allowed that branch's knowledge transition to complete
  both mutually exclusive objectives.
- Decision: Validation now computes every scene in which the typed completion can
  resolve. All such scenes must belong to the containing objective and match its
  exact phase. None may be owned by a mutually exclusive objective. Mutual
  exclusion does not globally prohibit shared setup scenes; a shared scene remains
  valid when neither branch completion can fire there. Plan validation,
  self-contained CampaignSpec validation, and typed compilation use the same rule.
- Evidence: Regressions reproduce the shared-location earlier scene, shared-actor
  later scene, and excluded-branch knowledge transition, plus the allowed shared
  non-completion setup scene. Forty-eight focused campaign tests passed with two
  Windows symlink-privilege skips; 1364 full unittest tests passed with 12 skips;
  pytest reported 1352 passed and 12 skipped. Ruff, default and pipeline/test
  Pyright checks, compileall, original-demo validation, repository-external golden
  CLI coverage, history safety, fsck, and whitespace checks passed.
- Consequences: This correction is not a GO. A new GPT-5.6-sol/max read-only task
  must review `812a00f..HEAD` and return explicit GO or REVISE before integration.
  Shared `main`, remotes, private material, runtime, save, Web, Forge, packaging,
  and dependencies remain outside this correction.
- Supersedes: DEC-0078's completion-resolution rule and re-review-pending evidence
  only; it does not supersede the CampaignSpec v1 contract or earlier decisions.

## DEC-0080: Runtime and CampaignSpec individual gates accepted for public integration

- Date: 2026-08-02
- Status: Both isolated slices accepted GO; combined integration verification pending.
- Context: A new read-only continuation context reviewed the exact public candidates
  before performing any integration or implementation edits. Runtime Campaign
  Foundation v1 was reviewed at
  `261541866533016f6215453b083b1110af212f97`; CampaignSpec v1 was reviewed at
  `15f47ca5dc2781d3cbcdbfcfa2e98807b3db333a` after both correction rounds.
- Decision: Accept both isolated candidates GO with no P0-P3 findings and combine
  them, in dependency order, on `coord/demo-1-58-public-integration`. Shared
  `main` remains unchanged until the exact combined candidate passes its full
  controller gates and a separate clean read-only integration decision.
- Evidence: Runtime passed 17 focused tests, 1333 full unittest tests with 10
  skips, and 1323 pytest tests with 10 skips. CampaignSpec passed 48 focused
  tests with 2 Windows symlink-permission skips, 1364 full unittest tests with
  12 skips, and 1352 pytest tests with 12 skips. Both candidates passed Ruff,
  Pyright, compileall, original-demo validation, history safety, fsck, and diff
  checks; Runtime also passed both cross-genre content validations, while
  CampaignSpec passed its Draft 2020-12 Schema, golden-byte, and external CLI
  coverage.
- Consequences: Individual GO authorizes only the isolated public integration
  candidate. It does not authorize a fast-forward of local `main`, push,
  release, force push, or placement of any private material in Git.
- Supersedes: DEC-0076's runtime acceptance-pending status and DEC-0079's
  CampaignSpec re-review-pending status only.

## DEC-0081: Combined Runtime and CampaignSpec controller verification complete

- Date: 2026-08-02
- Status: Controller verification complete; fresh independent integration acceptance pending.
- Context: The accepted Runtime and CampaignSpec candidates were merged in
  dependency order on `coord/demo-1-58-public-integration`. Combined code commit
  `1a9fcf607806b7f66e04545c1878bdd7ac16047b` has parents
  `91e525838d20d783fdf0f0eb7fce37d58131b052` and
  `15f47ca5dc2781d3cbcdbfcfa2e98807b3db333a`; accepted Runtime commit
  `261541866533016f6215453b083b1110af212f97` is an ancestor.
- Decision: Freeze the exact integrated code tree and this documentation-only
  evidence seal for a separate clean read-only review of `812a00f..HEAD`. Passing
  controller gates does not let the integrating context self-declare GO.
- Evidence: Sixty-five focused Runtime/CampaignSpec tests passed with two Windows
  symlink-permission skips. Full unittest passed 1381 tests with 12 skips; serial
  and xdist pytest each reported 1369 passed and 12 skipped. Ruff, configured
  Pyright, explicit CampaignSpec/test Pyright, and compileall passed. Direct Draft
  2020-12 validation covered both campaign-plan/spec Schemas, four plan/spec
  instances, the runtime campaign Schema, and two runtime instances. Original
  demo and both runtime campaign fixtures validated. Repository-external golden
  CLI outputs matched SHA-256 `71d9b7445d8649cc179bca757cc1931be66fab89dec6d2c9e42ad0de956fabaf`
  and `e0923fece619a8943eeaa55ce7b6c320154be5d82a68771d2c8f9939a276f9bb`.
  A repository-external Forge workspace completed init/status/run/check, skipped
  current stages on resume, and produced a deterministic immutable inspection
  rerun. Zipapp and pinned PyInstaller 6.21.0 Windows candidates both passed
  repository-external Web and console cold starts; their artifact SHA-256 values
  are `aa7a25ced70b41c92d8e39fa547296b94197c3ab04bd354a5d50d7eb5a42f608`
  and `68020fc96be68106b577f376c64a2ec34ab66086522ae9a1ed83653b98096431`.
  History safety, `git fsck --full --no-dangling`, range/worktree diff checks,
  and a clean integration worktree passed. Local `main` and local `origin/main`
  remained `812a00fe4412f4fc7068ac2e188c5c26d0a03157`; a post-gate live GitHub refresh
  failed after a connection reset and must be repeated before any fast-forward.
- Consequences: A fresh context must return findings-first P0-P3 and explicit
  `GO` or `REVISE` for the exact sealed HEAD. Until GO, local `main` must not move;
  no push, release, force push, private-material access, or new public scope is
  authorized. The Windows artifacts and controller reports remain outside Git.
- Supersedes: DEC-0080's combined-controller-verification-pending state only; it
  does not supersede the requirement for a separate integration acceptance.

## DEC-0082: Runtime campaign loader and Schema parity correction is controller-verified

- Date: 2026-08-02
- Status: P2 correction verified; fresh independent re-review pending.
- Context: The fresh read-only review of seal `7f1ceff` returned `REVISE` for
  one P2. `schemas/campaign.schema.json` requires every
  `dialogue_views[].nodes` array to contain at least one item, while the runtime
  loader and official `lore2mud validate` CLI accepted an empty array.
- Decision: Code commit `22a05d181bc7fc5a9eda96c39ef6e6f9e2e052bf` adds the
  same non-empty validation already used by base dialogue definitions and a
  focused regression that requires Draft 2020-12, `load_content_pack()`, and the
  real validation CLI all to reject the exact malformed public fixture copy.
  No Schema, runtime projection, save, Web, CampaignSpec, dependency, or content
  contract was otherwise changed.
- Evidence: Sixty-six focused Runtime/CampaignSpec tests passed with two Windows
  symlink-permission skips. Full unittest passed 1382 tests with 12 skips; serial
  and xdist pytest each reported 1370 passed and 12 skipped. Ruff, configured and
  explicit Pyright, compileall, direct Schema validation, three public content
  validations, both repository-external CampaignSpec goldens, the full external
  Forge lifecycle, history safety, fsck, and range/worktree diff checks passed.
  New repository-external zipapp and PyInstaller 6.21.0 candidates passed Web and
  console cold starts at SHA-256
  `4e011c22a67a4db774e26353ce7c09b4568fa6a39571254bd793c0c4de163a6e`
  and `cfde8f6a87c22b5a6fde2d1a00ab501fdd5e4897d319f72d3f817f403aabf269`.
- Consequences: This controller result is not independent GO. A fresh clean
  read-only task must reproduce the old P2, review the exact new seal, and return
  findings-first `GO` or `REVISE` before local `main` moves. No push, release,
  force push, private-material access, or new public scope is authorized.
- Supersedes: DEC-0081's controller-evidence counts and first-seal-pending state;
  it does not supersede the accepted Runtime or CampaignSpec contracts.

## DEC-0083: Current-state handoff drift is corrected without changing the accepted code tree

- Date: 2026-08-02
- Status: Documentation correction verified; fresh focused independent re-review pending.
- Context: The independent re-review of seal
  `e1e09941a368c04b2e6f08f4b2a53e137307016f` reproduced the original
  loader/Schema P2 as closed and found no additional code, test, packaging,
  safety, or history issue. It returned `REVISE` for one P2 in the mandatory
  resume record: later current sections of `PROJECT_STATE.md` still described
  the CampaignSpec merge, combined gates, and isolated Runtime/CampaignSpec GO
  decisions as incomplete, contradicting the accurate top-level record and
  DEC-0080 through DEC-0082.
- Decision: Synchronize the current `In progress`, `Blockers`, and
  `Risks and unknowns` bullets with the accepted isolated candidates and the
  completed combined technical gates. Update the compact restart files and
  changelog to record that only a focused review of this documentation seal
  remains. Do not modify the integrated code, Schema, fixtures, tests, packaging,
  dependencies, or private boundary.
- Evidence: The working diff is limited to `PROJECT_STATE.md`,
  `PROJECT_MEMORY.md`, `NEXT_TASK.md`, `CHANGELOG.md`, and this append-only
  decision. Searches find none of the three superseded current-state claims.
  `git diff --check`, `python scripts/check_repo_safety.py --history`, and
  `git fsck --full --no-dangling` pass. The source, pipeline, Schema, test,
  example, and packaging trees are byte-unchanged from code commit
  `22a05d181bc7fc5a9eda96c39ef6e6f9e2e052bf`.
- Consequences: A fresh clean task must review the exact new documentation seal,
  verify this P2 is closed, and return findings-first `GO` or `REVISE`. Local
  `main` remains at `812a00f` until GO and a fresh live-remote ancestry check.
  No push, release, force push, private-material access, or new public scope is
  authorized.
- Supersedes: Only the stale current-state bullets and DEC-0082's expectation
  that the next review would be a full technical re-review. It does not supersede
  the technical evidence or the requirement for independent acceptance.

## DEC-0084: Accepted public campaign integration is synchronized to local main

- Date: 2026-08-02
- Status: Accepted locally; current continuity seal pending focused read-only review.
- Context: A fresh focused read-only review inspected documentation correction
  `97a1ab314cd0b45f3728d707674f462547164216`, reproduced the earlier handoff-only
  P2 as closed, confirmed that the accepted code tree remains commit `22a05d1`,
  and returned `GO` with no P0-P3 findings.
- Decision: Record the resulting linear local-main synchronization and update the
  current handoff cache. Remove the current absolute location of the external
  private processing workspace from public tracked files while retaining the
  generic never-commit boundary. Do not rewrite reachable history.
- Evidence: The independent report is stored outside the repository at
  `.codex-test-tmp/acceptance-reports/integration-independent-rereview-97a1ab3.md`.
  The `main` reflog records a fast-forward from `812a00f` to `97a1ab3` at
  2026-08-02 20:42 Asia/Shanghai. A current read-only `git ls-remote` resolves
  GitHub `main` to `812a00f`; local `origin/main` matches it. The working tree is
  clean except for the preserved 14,471-byte untracked `uv.lock`, SHA-256
  `3b47a6e779ce74c7b91e899c93f00f353d99986ee2168d5ab8f1275e35de73fc`.
- Consequences: Local `main` is ahead of the remote and remains unpublished. The
  current continuity seal changes handoff documentation only and needs a fresh
  focused review. Older reachable commits retain path-only private-workspace
  metadata; controller scans found no non-trivial private artifact blob or private
  content. Push, release, force-push, history rewrite, private-material access,
  and a new public slice remain unauthorized.
- Supersedes: DEC-0083's focused-review-pending and local-main-at-`812a00f` states
  only. It does not supersede the accepted technical evidence or publish gate.

## DEC-0085: Content-defined drop protection closes the public beacon-key risk

- Date: 2026-08-03
- Status: Implementation and local verification complete; fresh independent read-only
  acceptance pending.
- Context: A public playtest reported that dropping `item_beacon_core` at the beacon
  platform could strand progression. The current `0aa9302` baseline could in fact
  return west/east, retake the core, and finish, but that recovery depended on route
  discovery and DEC-0015 allowed every unequipped item to be dropped. The same playtest
  also found three monster-task descriptions inconsistent with free movement and the
  optional Elder Chen token route too deeply hidden. Private content-pack development
  is stopped; this decision is limited to the public engine and `original_demo`.
- Decision: Add strict optional `droppable` boolean metadata to item Schema, loader,
  immutable content definitions, runtime items, World construction, and save/load
  reconstruction. Omission defaults to `true`; `World.drop()` rejects a false value
  before any state mutation. Mark only `item_beacon_core` false and give the platform
  an explicit key warning. Rewrite the four public monster-quest descriptions to match
  existing free movement, add a natural Glassgrass Path conversation hint, and append
  a direct Elder Chen warning question while preserving opening option indices 1-3 and
  the original reward route. Keep content pack 0.10.0 and save v9 unchanged.
- Evidence: 141 focused tests, 1390 full unittest tests with 12 skips, and 1378 full
  pytest passes with 12 skips. Compileall, original-demo validation, Ruff, Pyright,
  Draft 2020-12 validation of 36 public instances, history safety, fsck, and diff
  checks pass. Repository-external CLI saves prove the README ending, the rejected
  core drop with unchanged placement followed by beacon restoration, and the direct
  optional-token route plus west return.
- Consequences: Existing content packs retain prior drop behavior without edits.
  Protected items cannot be intentionally placed on the floor, but no monster-gated
  movement, combat system, campaign/narrative feature, save migration, dependency, or
  private-content access is introduced. A new clean GPT-5.6-sol task must still return
  GO or REVISE before this slice is accepted or published.
- Supersedes: DEC-0015's statement that every gate item may be deliberately dropped,
  only for items whose content explicitly sets `droppable=false`; all other DEC-0015
  behavior remains unchanged.

## DEC-0086: Gate 0 recovery and publication establish the V2 baseline

- Date: 2026-08-03
- Status: Accepted and published to `main`.
- Context: DEC-0085 closed the public beacon-key and discovery risks but still needed
  independent acceptance, a CI dependency repair, truthful save-compatibility
  documentation, post-main verification, and an explicit publish gate before the
  project could reset product direction.
- Decision: Record Gate 0 as independently accepted GO and use
  `1a5a8857579ebf840de4e39e414b52592baea6ba` as the public V2 reset baseline. The
  controller completed the authorized main/publish sequence; local `main`, local
  `origin/main`, and a live GitHub `refs/heads/main` query resolve to that commit.
  Preserve the primary checkout's intentionally untracked `uv.lock` boundary without
  copying it into isolated worktrees or Git.
- Evidence: The accepted range includes the public original-demo repair, CI schema
  validation dependencies, and the final save-compatibility correction. Independent
  review returned GO; branch and post-main unittest/pytest, Ruff, Pyright, compileall,
  original-demo validation, Draft 2020-12 validation, history safety, fsck, and diff
  gates were green. On 2026-08-03 the primary checkout was clean except for
  `uv.lock`, exactly 14,471 bytes with SHA-256
  `3b47a6e779ce74c7b91e899c93f00f353d99986ee2168d5ab8f1275e35de73fc`; the isolated
  V2 reset worktree did not contain that file.
- Consequences: Gate 0 is complete and no longer the active task. It authorizes the
  isolated V2-0 documentation reset only; it does not grant V2-0 TECH/PRODUCT passes,
  private-material access, another push/main move, a release, or V2-1 implementation.
- Supersedes: DEC-0085's independent-acceptance-pending state and older current
  handoff/publish claims only. It does not supersede V1 runtime compatibility or the
  public/private boundary.

## DEC-0087: V2 product direction and development model

- Date: 2026-08-03
- Status: Direction accepted; documentation candidate TECH and PRODUCT passes pending.
- Context: V1 has a capable public text-game runtime and deterministic authoring IRs,
  but the product entry described a local MUD project, application behavior was split
  across CLI/Web/World, `CampaignSpec` had no runtime materializer, central modules
  accumulated responsibilities, and historical handoffs obscured the one current
  product path.
- Decision: Define Lore2MUD as an Agent-callable novel-to-text-game engine, not an
  Agent. The developer Agent is the direct user, the product owner/creator supplies
  decisions and rights authorization, and the player is the final user. Adopt
  prototype/traced/sealed modes; an Authoring Plane producing `GameBlueprint v1`,
  `GameProject v1`, and `GamePackage v2`; and a deterministic Runtime Plane centered
  on `GameSession`, `GameIntent`, `GameEvent`, `GameView`, and `TurnResult`.
  `CapabilityDescriptor v1` uses a static catalog, safety levels, namespaced state,
  predicates/effects/views/migrations, and no dynamic code/plugin execution initially.
  Keep `World` as a compatibility facade, ship SDK and structured CLI before MCP, and
  keep `CampaignSpec` as authoring IR rather than runtime input. Adopt the exact
  V2-0..V2-5 roadmap and PLAT-1 recorded in `docs/v2/roadmap.md`.
- Evidence: `PRODUCT.md`, `CODE_MAP.md`, `docs/v2/architecture.md`,
  `docs/v2/development_model.md`, and `docs/v2/roadmap.md` define the product and target
  against live V1 symbols and file sizes. `README.md`, `AGENTS.md`,
  `docs/production_workflow.md`, and the compact handoffs route future tasks through
  TECH PASS, user PRODUCT PASS, and SECURITY PASS. Every implementation,
  architecture, and acceptance task/subagent must explicitly use `gpt-5.6-sol` at
  reasoning `xhigh` or higher, stop if unavailable, and never self-approve. Local
  verification passed 1,390 unittest tests with 12 conditional skips and 1,378 pytest
  tests with 12 skips, plus Ruff, Pyright, compileall, original-demo validation,
  history safety, fsck, staged/working diff checks, relative links, exact changed-path
  and protected-tree byte audits, and stale-claim/privacy/model-floor searches.
- Consequences: V2-0 remains a documentation candidate until fresh independent TECH
  GO and user PRODUCT PASS. After both, the controller may make a docs-only seal and
  route V2-1 Public Runtime Boundary. V2 names are not shipped APIs yet. Shared `main`
  stays read-only during workstreams; branch commit, push, main movement, and release
  remain separate gates. Public/private and rights boundaries remain unchanged.
- Supersedes: Current product framing, startup order, roadmap, and stale active-task
  claims in the prior snapshots. It does not rewrite historical decisions, remove V1
  capabilities, authorize private work, or change code/data/save/package contracts.
