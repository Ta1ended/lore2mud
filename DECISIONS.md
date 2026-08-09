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

## DEC-0088: Accept V2-0 direction and route the V2-1 runtime boundary

- Date: 2026-08-03
- Status: V2-0 TECH and PRODUCT gates complete; exact seal review/publication remains
  a separate live controller boundary.
- Context: The first independent TECH review of the V2 Product & Architecture Reset
  found one P3: the documentation overstated `ContentPack` immutability. Repair commit
  `d13dd0590f47f6477b476cfbdab2715b8f4aba7a` corrected the code map and durable
  snapshot to say that the frozen dataclass prevents field reassignment while its
  collection mappings remain mutable.
- Decision: Accept the V2-0 product and architecture direction after independent TECH
  GO and the user/product owner's explicit PRODUCT PASS. Route exactly one
  not-yet-started next task: V2-1, to design and implement a transport-neutral
  `GameSession` contract that wraps the existing `World` without splitting gameplay
  systems. V2 contract names remain accepted direction, not shipped APIs. Every
  implementation, architecture, and acceptance task/subagent must explicitly use
  `gpt-5.6-sol` with reasoning `xhigh` or higher, stop if unavailable, and never
  silently downgrade or self-approve.
- Evidence: The independent re-review resolved exact target `d13dd05`, reproduced the
  prior ContentPack P3, verified the correction, reported P0-P3 all none, and returned
  `GO` on 2026-08-03. Repair-branch GitHub Actions tests run `30822377956` and quality
  run `30822378186` completed successfully on 2026-08-03. The user/product owner then
  replied `PRODUCT PASS` on 2026-08-03. The seal changes only `PROJECT_STATE.md`,
  `PROJECT_MEMORY.md`, `NEXT_TASK.md`, `DECISIONS.md`, and `CHANGELOG.md`; focused
  local verification compares all other tracked paths byte-for-byte with `d13dd05`
  and checks stale claims, paths/links, privacy, model floor, history safety, fsck,
  diff cleanliness, and `uv.lock` absence.
- Consequences: V2-0 is complete and V2-1 is routed but not started. A fresh task must
  verify live `main` contains the exact accepted seal before implementation. This
  decision does not claim independent review or publication of the seal or post-seal
  live-main Actions; the controller verifies those states operationally. V2-1
  excludes Capability work, SDK, MCP, plugins, a new Demo,
  private-material access, and wholesale `World` decomposition. Public/private,
  rights, V1 compatibility, and the intentionally untracked primary-checkout
  `uv.lock` boundaries remain unchanged.
- Supersedes: DEC-0087's TECH/PRODUCT-pending status only. It does not supersede the
  accepted V2 direction, prior historical evidence, or any Git/publication gate.

## DEC-0089: Keep human-facing project handoffs bilingual

- Date: 2026-08-03
- Status: Accepted.
- Context: The product owner needs to understand current project status and the one
  routed next task without depending on English-only operational handoffs. Full
  duplication of long historical or technical records would add maintenance noise
  without improving the main human review path.
- Decision: Maintain `PROJECT_STATE.md` and `NEXT_TASK.md` as mirrored bilingual
  human-facing documents, with Chinese first and English second. Every update must keep
  status, task scope, non-goals, gates, identifiers, dates, and boundaries semantically
  synchronized. Keep other historical and technical documents single-language unless
  the product owner specifically requests otherwise.
- Rationale: Two compact synchronized handoffs make occasional owner review practical
  while preserving one authoritative project state and one actionable next task.
- Scope: This policy applies to ongoing maintenance of `PROJECT_STATE.md` and
  `NEXT_TASK.md`; `AGENTS.md` carries the durable maintenance rule. This decision does
  not require translating earlier decisions, changelog history, product architecture,
  code maps, roadmaps, code, tests, workflows, or private material.
- Consequences: Documentation changes affecting either handoff must update and verify
  both language sections together. Technical acceptance still depends on live Git,
  code, tests, artifacts, and fresh independent review rather than translation alone.
- Evidence: The bilingual snapshot records synchronized live refs at
  `077b8eb568f193b0b3ccab47410bec35dc4c2a9c`, completed V2-0 gates and green branch/
  live-main runs; the bilingual next-task handoff routes only the not-yet-started V2-1
  `GameSession` boundary with matching scope, non-goals, and gates.
- Supersedes: None.

## DEC-0090: Make the public README bilingual

- Date: 2026-08-03
- Status: Accepted.
- Context: The V2-0 reset replaced the earlier Chinese README with a concise English
  project entry. The product owner identified that the GitHub landing page had become
  English-only and explicitly authorized continuing with a bilingual correction.
- Decision: Maintain `README.md` as a mirrored bilingual public entry, with Chinese
  first and English second. Keep product identity, current-versus-target status,
  commands, links, repository flow, public/private boundaries, and development gates
  semantically synchronized in both sections.
- Rationale: The repository landing page serves both the product owner and developer
  Agents. Chinese-first presentation restores direct owner readability, while the
  English section preserves a broadly usable technical entry.
- Scope: Translate and synchronize the existing concise V2 README. Keep `PRODUCT.md`,
  `CODE_MAP.md`, `docs/v2/`, historical records, code, tests, examples, and private
  material outside this translation requirement unless separately authorized.
- Consequences: Future README changes must update both language sections together.
  README commands and links remain executable repository contracts and must be checked
  during documentation acceptance. This decision authorizes no runtime work, V2-1,
  private access, release, force-push, or history rewrite.
- Evidence: The bilingual candidate preserves the same public entry structure in both
  languages and retains the current commands, relative links, V1/V2 boundary, rights
  boundary, repository flows, and verification matrix.
- Supersedes: DEC-0089 only where it previously left `README.md` outside the default
  bilingual set; the bilingual handoff policy remains unchanged.

## DEC-0091: Refine milestone ownership with adopted reference patterns

- Date: 2026-08-04
- Status: Planning direction authorized; revised local planning candidate verified.
- Context: The product owner supplied a synthesized set of patterns from comparable
  projects and authorized a planning-only update. The current V2 direction already
  contained most safety boundaries, but the short roadmap did not assign diagnostics,
  preview simulation, capability resolution, sealing, workbench hashing, and narrative
  constraints precisely enough to prevent later scope leakage. Review also found a
  lifecycle ambiguity: V2-2 must build and simulate before V2-4, while `GamePackage v2`
  was described only as sealed.
- Decision: Keep V2-1 limited to the transport-neutral runtime boundary with the fixed
  flow `CLI/Web parsing -> GameIntent -> GameSession -> TurnResult -> transport
  rendering`. Contract-rejected intents emit no transition events and preserve all
  authoritative session state, while accepted actions may retain deterministic
  unsuccessful in-world outcomes from existing `World` rules. Assign machine-readable
  authoring diagnostics, isolated unsealed preview builds, simulation evidence,
  SDK/structured-CLI parity, bounded player-safe admissible-intent descriptors, and
  read-only proofing to V2-2. V2-2 may record capability requirement IDs but cannot
  resolve them. Before V2-3, V2-2 preview builds use only one engine-defined V1
  compatibility profile; any declared V2 capability requirement blocks preview build
  and simulation with a stable diagnostic. Assign engine-shipped catalog resolution,
  exact versions, namespaces, dependencies/conflicts, safety levels, and explicit
  migration contracts to V2-3.
  Assign canonical sealed `GamePackage v2` and evidence-manifest identity, end-to-end
  adaptation traces, stable story/scene/resume anchors, and explicit anchor migrations
  to V2-4. V2-2 owns only deterministic preview/report fingerprints; V2-5 enforces the
  V2-4 identity boundary for workbench metadata and parity, reusing the V2-2
  SDK/application services instead of creating alternate rules.
- Narrative and trust rule: Deterministic branching and progressive disclosure are
  allowed only within owner-approved `GameBlueprint` constraints. Capabilities,
  runtime logic, and model output cannot invent source facts, broaden rights or
  adaptation scope, expose private material, or bypass approved disclosure
  constraints. Only deterministic source-controlled engine code mutates authoritative
  runtime state; authoring and proofing use artifacts or isolated session copies.
- Rejected alternatives: This roadmap does not authorize migration to Evennia,
  Ranvier, CoffeeMud, or another MUD framework; database-first authority; an event-bus
  or event-sourced V2-1 rewrite; package-provided/generated executable code; dynamic
  plugins; runtime model adjudication; a workbench-only compiler/runtime; multiplayer
  scope; or treating preview/report/UI metadata as sealed package identity.
- Privacy and identity: Public diagnostics, simulation reports, proofing exports,
  player views, and sealed metadata omit raw private excerpts, absolute private paths,
  private source hashes, and identifiers that reveal private content. V2-2 report
  fingerprints are reproducibility evidence only. V2-4 owns canonical semantic package
  and evidence-manifest identity. V2-5 workspace layout and presentation metadata remain
  outside both identities and cannot introduce a second hashing contract.
- Evidence: Live `main` and `origin/main` were verified at
  `564530d87aea17da26544b7793701e0dca0fe57d` before the isolated planning workstream.
  `PRODUCT.md`, `docs/v2/architecture.md`, `docs/v2/roadmap.md`,
  `docs/v2/reference_patterns.md`, and bilingual `NEXT_TASK.md` encode the refined
  lifecycle and milestone boundaries without implementing a V2 API. Local planning
  verification passed on 2026-08-04: strict UTF-8/no-BOM/final-newline checks, relative
  links, bilingual single-action parity, unique milestone ownership, exact changed-path
  scope, `git diff --check`, repository history safety, `git fsck --full --no-dangling`,
  protected implementation-tree identity, the preserved `uv.lock` boundary, and a
  public-plan leakage scan. An initial independent read-only review returned `REVISE`
  for two P2 planning contradictions: unresolved capability requirements in V2-2
  previews and joint ownership of semantic identity. This revision assigns a fixed V1
  compatibility profile to V2-2 and splits identity ownership across V2-2 fingerprints,
  V2-4 package/evidence identities, and V2-5 enforcement. The focused P2 correction
  checks, relative-link validation, protected-path audit, repository history safety, and
  Git integrity checks then passed again. No implementation test was run or claimed.
- Consequences: V2-1 remains the single routed next implementation task and does not
  gain Capability, SDK, structured CLI, diagnostics, simulation-report, migration,
  sealing, workbench, MCP, new content/save version, or private-material scope.
  Publication remains separately gated by a fresh independent TECH review and
  product-owner review. No implementation, push, `main` movement, release, or V2-2
  start is authorized.
- Supersedes: DEC-0087 only where it assigned the static capability catalog to V2-2 or
  left milestone ownership ambiguous. It does not supersede the accepted product
  direction, safety boundaries, PLAT-1, DEC-0088's V2-1 routing, or later bilingual
  maintenance decisions.

## DEC-0092: Implement the V2-1 public runtime boundary without moving World authority

- Date: 2026-08-04
- Status: Local implementation candidate; controller verification and exact-commit
  independent TECH decision are required before advancement.
- Context: Live public `main` was verified at
  `564530d87aea17da26544b7793701e0dca0fe57d` with successful GitHub Actions tests
  `30846680303` and quality `30846680343`. The accepted planning candidate
  `1d4b26d9127d4229893911cf260cf3c2f4b0ce3a` refined V2-1 as the narrow flow
  `CLI/Web parsing -> GameIntent -> GameSession -> TurnResult -> transport rendering`.
  V1 previously split application behavior across `CommandProcessor`, Web
  `PlayerSession`, and direct `World` calls.
- Decision: Add `src/lore2mud/application/` with frozen typed intent, event, view,
  determinism, rejection, and turn-result values; one locked `GameSession` around the
  authoritative compatibility `World`; and one detached player-safe projection.
  Contract rejection restores canonical persistable state, RNG position, immutable
  clock input, event sequence, and original `World` identity before returning no
  transition event. CLI and Web keep parsing/rendering and compatibility names, but
  submit typed requests through the shared session. Concrete player affordances are
  projected from isolated V1 rule probes; no public general admissible-intent catalog
  is introduced. Save/content/schema versions and `World` gameplay systems remain
  unchanged.
- Decision: Replace the repository-wide fixed `gpt-5.6-sol`/`xhigh` floor with
  controller-selected available models and reasoning levels based on responsibility,
  complexity, stability, and risk. Record selections when exposed, verify every
  output through code/tests/Git evidence, prefer reliable reasoning for high-risk
  shared boundaries, and reassign unverifiable work. Independent acceptance remains
  fresh, read-only, exact-target, findings-first, and separate from implementation.
- Evidence: Product/Specification and Architect/Engine Lead completed read-only scope
  and compatibility reviews. Focused contract, cross-transport, CLI, Web, save,
  dialogue, gameplay, runtime-campaign, and Windows packaging regressions pass after
  closing stale client-test and zipapp-index coverage. Full verification passed 1402
  unittest tests with 11 conditional skips, serial pytest at 1391 passed / 11 skipped,
  and xdist pytest at 1391 passed / 11 skipped. The first xdist startup hit a
  pre-collection `WinError 5` in the user pytest temp root; an explicit
  repository-external TEMP/TMP and `--basetemp` rerun passed. Ruff, Pyright,
  compileall, original-demo validation, history safety, fsck, and working/staged diff
  checks passed. This controller evidence does not grant TECH GO.
- Consequences: `World` remains authoritative; `GameEvent` is a result fact rather than
  an event bus or second state authority. V2-1 does not gain Capability, SDK,
  structured CLI, MCP, `SimulationReport`, proofing, migration, plugin, new Demo,
  new content/save version, or private-material scope. Shared `main` stays unmoved and
  there is no push or release. After a fresh independent TECH GO on the exact final
  candidate, the only next owner gate is PRODUCT PASS; TECH GO does not imply it.
- Supersedes: DEC-0087 and DEC-0088 only where they imposed a fixed model/reasoning
  floor, and DEC-0088/DEC-0091 handoff text only where it said V2-1 was not started.
  It does not supersede the accepted product direction, PLAT-1, public/private and
  rights boundaries, Git gates, or later milestone ownership.

## DEC-0093: Reject executable primitive subclasses before the V2-1 snapshot boundary

- Date: 2026-08-04
- Status: Local acceptance-repair candidate; a fresh exact-commit independent TECH
  decision is still required before advancement.
- Context: Two independent read-only reviews of the local V2-1 candidate returned
  `REVISE`. The first found undeclared Intent subclasses, public persistence-path
  leakage, and stale transport-flow documentation. After those findings were fixed,
  the second demonstrated that exact Intent objects could still contain `str` or `int`
  subclasses whose overridden operations mutated authoritative state during validation,
  before `GameSession.submit()` captured its rollback snapshot. It also found that the
  verification counts recorded by DEC-0092 and the current handoff were stale.
- Decision: Validate every public V2-1 request as an exact declared Intent with exact
  `DeterminismContext`, `str`, `int`, and Enum leaf types before invoking any value
  method or operator. Reuse that validator for Web Intent serialization, reject Web
  primitive/container subclasses during parsing, and reject non-exact CLI command
  strings before `strip()` or `shlex` processing. These checks are contract rejection,
  so they emit no transition event and leave canonical World bytes, identity, RNG,
  clock, event sequence, and save-visible metadata unchanged.
- Evidence: Malicious `str` and `int` regression values attempt state mutation from
  overridden `strip()` and comparison operations across `GameSession`, CLI, Web
  parsing, and Web serialization; all are rejected before their behavior runs. The
  focused application/CLI/Web matrix passed 47 tests. Full verification passed 1408
  unittest tests with 11 conditional skips, serial pytest at 1397 passed / 11 skipped,
  and xdist pytest at 1397 passed / 11 skipped with explicit repository-external
  TEMP/TMP and `--basetemp`. Ruff, Pyright, compileall, original-demo validation,
  history safety, fsck, and the working diff check passed. This evidence does not grant
  TECH GO.
- Consequences: DEC-0092 remains the historical implementation decision, but its
  pre-repair test counts and validation detail are superseded by this record. No
  dependency, Schema, content/save version, `World` authority, client responsibility,
  private-data boundary, publish state, or V2-2 scope changes. Shared `main` remains
  unmoved, with no push or release.
- Supersedes: DEC-0092 only for the corrected validation boundary and current test
  evidence. It does not rewrite the earlier review history or supersede any product,
  public/private, rights, Git, acceptance, or milestone gate.

## DEC-0094: Complete rejection rollback after exception diagnostic normalization

- Date: 2026-08-04
- Status: Local acceptance-repair candidate; a new exact-commit independent TECH
  decision is required before advancement.
- Context: Fresh independent read-only acceptance of exact target
  `cebb1af7c0c794d441ae05fc888cf1af2ff5876d` returned `REVISE`. A side-effectful
  `SaveLoadError.__str__()` or `WorldRuleError.__str__()` ran after the existing
  `_restore()` call, so a rejected turn could return zero events and a pre-mutation
  `GameView` while leaving the authoritative World changed. The same review found that
  `docs/architecture.md` still described direct `CommandProcessor -> World` routing and
  that four current-candidate line counts in `CODE_MAP.md` were stale.
- Decision: Normalize rule and persistence rejection messages inside `try` blocks,
  execute the final World/RNG/event-sequence restore in `finally`, and only then project
  the rejection view and construct `TurnResult`. If exception formatting itself raises,
  restoration still completes before the unexpected error is re-raised. Add regression
  coverage for side-effectful rule and persistence exception formatting. Update the V1
  architecture narrative to the shipped V2-1 flow and refresh current source line counts.
- Evidence: The new regression first reproduced canonical World byte drift and a coin
  change from 20 to 97 on the rejected save path, then passed after the ordering fix;
  the equivalent `WorldRuleError` path also passes. The focused application/CLI/Web
  matrix passes 48 tests. Full verification passes 1409 unittest tests with 11
  conditional skips, serial pytest at 1398 passed / 11 skipped, and xdist pytest at
  1398 passed / 11 skipped with explicit repository-external TEMP/TMP and `--basetemp`.
  Ruff, Pyright, compileall, original-demo validation, history safety, fsck, and diff
  checks pass. This controller evidence does not grant TECH GO.
- Consequences: Rejected turns now restore after every operation that can invoke an
  exception object's behavior, and returned views match restored authority. No
  dependency, Schema, content/save version, `World` authority, client responsibility,
  private-data boundary, publish state, or V2-2 scope changes. Shared `main` remains
  unmoved, with no push or release.
- Supersedes: DEC-0093 only for the completed exception-formatting rollback boundary,
  refreshed documentation evidence, and current verification counts. It does not
  rewrite prior review history or supersede product, public/private, rights, Git,
  acceptance, or milestone gates.

## DEC-0095: Render current CLI dialogue actions from the player-safe view

- Date: 2026-08-04
- Status: Local acceptance-repair candidate; another fresh exact-commit independent
  TECH decision is required before advancement.
- Context: Fresh independent reacceptance of exact target
  `5d59f0ca83f64fe7a89f65feb3b6d9ed4b943ab9` returned `REVISE` for one P2. The
  application projection correctly omitted dialogue choices whose effects were no
  longer admissible, but `CommandProcessor._render_talk()` numbered every option from
  `DialogueEventData`. After the public Demo's one-time Elder Chen reward was claimed,
  Web/GameView exposed only `opt_back3` while CLI still displayed `opt_bye4`; selecting
  it immediately produced a rule rejection.
- Decision: Keep dialogue events as ordered transition facts, but render the CLI's
  current dialogue text and numbered actionable choices from
  `TurnResult.view.dialogue`. Preserve projected option indices so CLI selection maps
  to the same typed `ChooseDialogueIntent` as Web, without duplicating effect or quest
  rules in the client. When dialogue has ended, retain the event's completion text.
- Evidence: A public original-Demo regression claims `opt_bye4`, re-enters
  `node_observatory`, confirms that the event still records both condition-visible
  options, confirms that `GameView` contains only `opt_back3`, and verifies that CLI
  output omits the unavailable second choice. The focused application/CLI/Web/dialogue
  matrix passes 66 tests. Full verification passes 1410 unittest tests with 11
  conditional skips, serial pytest at 1399 passed / 11 skipped, and xdist pytest at
  1399 passed / 11 skipped with repository-external TEMP/TMP and `--basetemp`. Ruff,
  Pyright, compileall, original-demo validation, history safety, fsck, and diff checks
  pass. This evidence does not grant TECH GO.
- Consequences: CLI and Web now render the same actionable dialogue surface from the
  shared player-safe projection. `GameEvent` remains non-authoritative and is not used
  as a second action catalog. No dependency, Schema, content/save version, `World`
  authority, private-data boundary, publish state, or V2-2 scope changes. Shared `main`
  remains unmoved, with no push or release.
- Supersedes: DEC-0094 only for current CLI dialogue rendering and verification counts.
  It does not rewrite prior review history or supersede product, public/private,
  rights, Git, acceptance, or milestone gates.

## DEC-0096: Restore determinism-context identity and values on rejected turns

- Date: 2026-08-04
- Status: Local acceptance-repair candidate; a fresh exact-commit independent TECH
  decision is required before advancement.
- Context: Fresh independent reacceptance of exact target
  `5c3cb1715252f3e3455f3ec7d77c71c7715c8a78` returned `REVISE` for one P1. The
  rejection snapshot restored World, RNG, and event sequence, but did not restore the
  frozen `DeterminismContext`. A side-effectful `SaveLoadError.__str__()` used
  `object.__setattr__()` to change `clock` from 31 to 999; the turn returned rejected
  with no events and unchanged World/view while the public determinism context drifted.
- Decision: Snapshot the original `DeterminismContext` object plus exact `seed` and
  `clock` values with every authoritative turn snapshot. Every restore path writes the
  original values back onto that same frozen object with `object.__setattr__()` and
  reattaches the original identity before returning or re-raising. Extend the malicious
  rule/persistence exception-formatting regression to mutate World, seed, and clock and
  assert context identity plus value invariance.
- Evidence: The focused application/CLI/Web/dialogue matrix passes 66 tests. Full
  verification passes 1410 unittest tests with 11 conditional skips, serial pytest at
  1399 passed / 11 skipped, and xdist pytest at 1399 passed / 11 skipped with explicit
  repository-external TEMP/TMP and `--basetemp`. Ruff, Pyright, compileall,
  original-demo validation, history safety, fsck, and diff checks pass. This controller
  evidence does not grant TECH GO.
- Consequences: Contract rejection now preserves canonical World state, World identity,
  RNG position, determinism-context identity and values, event sequence, save-visible
  metadata, and returned-view consistency even under side-effectful exception
  formatting. No dependency, Schema, content/save version, `World` authority,
  private-data boundary, publish state, or V2-2 scope changes. Shared `main` remains
  unmoved, with no push or release.
- Supersedes: DEC-0095 only for the completed determinism rollback boundary and current
  implementation evidence. It does not rewrite prior review history or supersede
  product, public/private, rights, Git, acceptance, or milestone gates.

## DEC-0097: Preserve V1 Web snapshot shape and authored entity order

- Date: 2026-08-04
- Status: Local acceptance-repair candidate; a fresh exact-commit independent TECH
  decision is required before advancement.
- Context: Fresh independent reacceptance of exact target
  `6e7d0ea9360910c14522ba41f77c5925da8ea7d3` returned `REVISE` for one P2 and one P3.
  The compatibility Web `snapshot` reused the player-safe serializer, which correctly
  omitted unavailable V2 actions but also removed V1 fields whose values were `null`.
  Separately, `GameView` sorted room items by stable ID, changing the public Demo's
  authored CLI/Web presentation order.
- Decision: Keep the new player-safe `view` omission rule unchanged, then explicitly
  restore only the V1 nullable compatibility keys in `snapshot`: exit requirement
  identifiers/names, item healing/equipment fields, equipment slots, dialogue/shop,
  and journal status. Preserve authored room item, monster, and character order in the
  shared projection; this order is deterministic content input and remains identical
  across CLI and Web. Add exact public-Demo regressions for the legacy keys and item
  order in both transports.
- Evidence: The finding-specific command/Web/application/transport matrix passes 33
  tests. Full verification passes 1410 unittest tests with 11 conditional skips,
  serial pytest at 1399 passed / 11 skipped, and xdist pytest at 1399 passed / 11
  skipped with explicit repository-external TEMP/TMP and `--basetemp`. The first
  resumed unittest attempt lacked an explicit worktree `PYTHONPATH`, loaded stale
  modules from the primary checkout's editable install, and failed; the corrected
  worktree-bound rerun supplies the valid evidence. Ruff, Pyright, compileall,
  original-demo validation, history safety, fsck, and diff checks pass. This controller
  evidence does not grant TECH GO.
- Consequences: Existing Web consumers can continue testing legacy field presence,
  and V1 CLI/Web presentation retains content-authored order. New unavailable actions
  remain absent rather than appearing as `null`. No dependency, Schema, content/save
  version, `World` authority, private-data boundary, publish state, or V2-2 scope
  changes. Shared `main` remains unmoved, with no push or release.
- Supersedes: DEC-0096 only for the two completed compatibility repairs and current
  verification evidence. It does not rewrite prior review history or supersede
  product, public/private, rights, Git, acceptance, or milestone gates.

## DEC-0098: Preserve complete V1 event payloads and campaign action order

- Date: 2026-08-04
- Status: Local acceptance-repair candidate; a fresh exact-commit independent TECH
  decision is required before advancement.
- Context: Fresh independent reacceptance of exact target
  `731459742cdbda9a32bc87956cb0a15e033d5100` returned `REVISE` for one P2 and one P3.
  The Web adapter preserved the legacy top-level `event` but compressed move room data,
  omitted runtime-campaign effect outcomes, and removed explicit nulls from dialogue
  event data. Separately, the application projection re-sorted authoritative campaign
  actions by ID instead of retaining each interactable's declared `action_ids` order.
  The target commit also carried a future 2026-08-05 timestamp relative to the
  2026-08-04 controller date.
- Decision: Extend the immutable typed event contract with a complete move-room fact,
  typed campaign effect values, and ordered effect outcomes. The Web compatibility
  renderer reconstructs the old `event.data` shape with explicit nulls from those
  facts, while the new event JSON stays typed. Consume
  `World.available_campaign_actions()` in its authoritative order without a second ID
  sort. Add exact move/dialogue/campaign JSON and CLI/Web/GameView ordering regressions.
  Amend the local repair commit with 2026-08-04 author and committer dates so the
  reviewed target has no future audit timestamp.
- Evidence: The finding-specific Web/application/runtime-campaign/transport matrix
  passes 49 tests. Full verification passes 1414 unittest tests with 11 conditional
  skips, serial pytest at 1403 passed / 11 skipped, and xdist pytest at 1403 passed /
  11 skipped with explicit repository-external TEMP/TMP and `--basetemp`. Ruff,
  Pyright, compileall, original-demo validation, history safety, fsck, and diff checks
  pass. This controller evidence does not grant TECH GO.
- Consequences: Legacy Web consumers again receive the complete V1 move, dialogue, and
  campaign event payloads; `GameEvent` remains an immutable ordered fact rather than a
  raw outcome or event bus. Campaign actions retain content-authored order in
  GameView, CLI, and Web. No dependency, Schema, content/save version, `World`
  authority, private-data boundary, publish state, or V2-2 scope changes. Shared
  `main` remains unmoved, with no push or release.
- Supersedes: DEC-0097 only for the completed event-payload and campaign-order repairs,
  corrected local audit timestamp, and current verification evidence. It does not
  rewrite prior review history or supersede product, public/private, rights, Git,
  acceptance, or milestone gates.

## DEC-0099: Restore rejected turns on the existing World object graph

- Date: 2026-08-04
- Status: Local acceptance-repair candidate; a fresh exact-commit independent TECH
  decision is required before advancement.
- Context: Fresh independent reacceptance of exact target
  `d11f6ed0b445436d0ed61f5eebad9f1921709d7d` by a read-only
  `gpt-5.6-sol`/`xhigh` task returned `REVISE` for one P2. Rejection rollback restored
  the top-level `World` identity and canonical bytes by assigning deep-copied fields,
  but callers holding pre-turn `player`, inventory, room, collection, or item-stack
  aliases could still observe illegal rejected-turn mutations on detached old objects.
- Decision: Capture the pre-turn `World` with the deepcopy identity mapping, retain the
  corresponding original references, and recursively restore existing dataclass,
  dict, list, and set objects in place. Root and nested fields are rebound to their
  original references while container contents and mutable values are restored from
  the isolated backup. Add a persistence-failure regression that mutates player coins,
  inventory capacity, flags, a room item stack, and its containing list, then asserts
  identity and value invariance through every retained alias.
- Evidence: The exact alias regression module passes 11 tests; the application, CLI,
  Web, command, and runtime-campaign cross-matrix passes 55 tests. Full verification
  passes 1414 unittest tests with 11 conditional skips, serial pytest at 1403 passed /
  11 skipped, and xdist pytest at 1403 passed / 11 skipped with explicit repository-
  external TEMP/TMP and `--basetemp`. Ruff, Pyright, compileall, and original-demo
  validation pass. Repository history safety, fsck, diff checks, and a fresh exact-
  commit independent decision remain required after the coherent repair commit. This
  controller evidence does not grant TECH GO.
- Consequences: Contract rejection now preserves the observable identity and values of
  the existing compatibility `World` object graph as well as canonical state, RNG,
  clock, determinism context, event sequence, and save-visible metadata. No dependency,
  Schema, content/save version, `World` authority, client responsibility, private-data
  boundary, publish state, or V2-2 scope changes. Shared `main` remains unmoved, with
  no push or release.
- Supersedes: DEC-0098 only for the completed nested-alias rollback repair and current
  verification evidence. It does not rewrite prior review history or supersede product,
  public/private, rights, Git, acceptance, or milestone gates.

## DEC-0100: Seal V2-1 TECH GO and PRODUCT PASS locally

- Date: 2026-08-04
- Status: Local product seal; publication remains separately gated.
- Context: Fresh independent read-only acceptance of exact product candidate
  `d642a9d5e3ab9d9628d0f5cb8fa04a38d74de8d5` returned `GO` with no P0-P3 findings.
  The product owner then explicitly granted `PRODUCT PASS` on 2026-08-04. The accepted
  product bytes remain those of `d642a9d`; this follow-up changes handoff and decision
  documentation only.
- Decision: Record both gates against the exact product candidate and freeze V2-1
  locally. Route the sole next gate to separate explicit push/publication authorization.
  PRODUCT PASS does not authorize push, `main` movement, SECURITY PASS, release, or
  V2-2, and a documentation seal must not be presented as a newly accepted product
  candidate.
- Evidence: Independent acceptance reproduced and closed the nested-alias rollback
  defect, passed 270 focused tests plus the named compatibility probes, 1414 unittest
  tests with 11 skips, serial and xdist pytest at 1403 passed / 11 skipped, all static,
  validation, safety, fsck, diff, CLI, Web, save-v9, and v7/v8 read gates, and ended on
  a clean exact target. The human product owner supplied the required PRODUCT PASS in
  the controller task after that report.
- Consequences: V2-1 is technically and product accepted at `d642a9d` but remains local.
  A later publication controller must recheck live remote ancestry and Actions, receive
  explicit push authorization, and push only the workstream branch. No private-data,
  dependency, Schema, content/save version, runtime authority, or V2-2 scope changes.
- Supersedes: DEC-0099 only for gate status and next-task routing. It does not rewrite
  prior findings, acceptance evidence, product boundaries, rights constraints, or Git
  safety requirements.

## DEC-0101: Harden and publish the V2-1 public runtime boundary

- Date: 2026-08-05
- Status: Published V2-1 product candidate; V2-2 remains separately gated.
- Context: A read-only security scope review of the previously published handoff head
  `d5135451f5f765ee98c2507a29e2f17e3bb59d47` found that public Web event channels
  could re-expose campaign authority state and unavailable dialogue options already
  omitted by `GameView`. It also found unbounded content/save JSON reads whose UTF-8,
  integer, or recursion failures could escape typed application rejection, plus a test
  constraint that excluded the fixed pytest release. Because these repairs changed
  runtime/public-contract bytes, the earlier TECH and PRODUCT decisions could not be
  transferred to the new candidate.
- Decision: Adopt one internal bounded UTF-8 JSON reader with per-file limits of
  8 MiB, depth 64, 200,000 nodes, 1,000,000 characters per string, and 64 decimal
  integer digits. Content loading maps its typed failures to `ContentValidationError`;
  save loading maps them to `SaveLoadError`, so `GameSession` returns a transactional
  `PERSISTENCE_ERROR`. Rebuild dialogue-event options from the final same-turn
  `GameView` and omit raw campaign effect outcomes from public events, including the
  compatibility Web event channel. Require `pytest>=9.0.3,<10`, make unittest subtest
  labels xdist-serializable, and verify the new module in Windows delivery. Preserve
  `World` authority, save v9/v7/v8 compatibility, Schemas, content versions, and all
  V2-1 scope exclusions.
- Evidence: Controller focused serial and xdist matrices each passed 435 tests with
  6 conditional skips and 308 subtests. The corrected full unittest run passed 1418
  tests with 11 skips; serial and xdist pytest each passed 1407 tests with 11 skips and
  554 subtests. Ruff, Pyright, compileall, public-Demo validation, pip consistency,
  repository-history safety, fsck, and diff checks passed. Fresh non-implementing TECH
  acceptance returned empty P0-P3 and `GO`; fresh non-implementing SECURITY acceptance
  returned empty P0-P3 and `GO` after 290 focused tests, 208 subtests, exact/over JSON
  boundary probes, whole-response leakage checks, and transaction-invariance checks.
  The product owner explicitly granted `PRODUCT PASS` for exact candidate
  `c8ee518ef39f938ece374cbd3f7c9bca06de2408` on 2026-08-05. The candidate was then
  fast-forward pushed only to `workstream/v2-1-game-session`; GitHub Actions tests
  `30967325238` and quality `30967325246` completed successfully. Live `main` remained
  `564530d87aea17da26544b7793701e0dca0fe57d`.
- Consequences: V2-1 is complete and published on the workstream branch at accepted
  product bytes `c8ee518`. The following handoff seal is documentation-only and does
  not create a new product candidate. There is no `main` movement, merge, release, or
  V2-2 work. The sole next gate is explicit product-owner authorization to begin V2-2
  and select its accepted starting branch/baseline. Private material remains outside
  the public repository.
- Supersedes: DEC-0100 only for the current accepted product SHA, SECURITY gate,
  publication state, and next-task routing. It preserves DEC-0100 as historical
  evidence and does not rewrite prior findings, rights constraints, or milestone
  boundaries.

## DEC-0102: Implement V2-2 as one fixed-profile authoring and evidence service

- Date: 2026-08-05
- Status: Local V2-2 product candidate; fresh exact-commit independent TECH
  acceptance is pending.
- Context: The product owner authorized V2-2 implementation in an isolated worktree
  without push, `main` movement, merge, release, or V2-3 scope. Live GitHub `main`
  remained `564530d87aea17da26544b7793701e0dca0fe57d`; it did not contain the accepted
  V2-1 documentation head, so the candidate branch starts from exact green head
  `eb972903a0b959f09a647a1727a6ed66f2d098f7`, whose accepted V2-1 product ancestor is
  `c8ee518ef39f938ece374cbd3f7c9bca06de2408`. DEC-0091 assigns deterministic
  preview/report fingerprints and player-safe authoring evidence to V2-2 while
  reserving capability resolution for V2-3, package/evidence identity for V2-4, and
  workbench behavior for V2-5.
- Decision: Add one `src/lore2mud/authoring/` boundary for frozen blueprint, project,
  diagnostic, preview, simulation, descriptor, proofing, and result contracts;
  canonical serialization; bounded project capture; a shared `AuthoringService`;
  `AgentAuthoringSDK`; and structured `author` CLI commands. Projects may record only
  syntactically valid capability requirement IDs. Any non-empty set returns stable
  `capability_requirement_unsupported_v2_2` diagnostics before preview construction or
  simulation. The only profile is the engine-defined
  `lore2mud.v1.compatibility.fixed` profile, and preview/report loaders require the
  current engine version.
- Decision: Preview bytes are explicitly unsealed, non-distributable, and not release
  evidence. Their fingerprints and report fingerprints prove reproducibility only;
  they are not `GamePackage v2`, package identity, evidence-manifest identity, or a
  publication gate. Workspace/proofing metadata is serialized with the editable
  project but excluded from the build lock, semantic project bytes, preview identity,
  and simulation report identity.
- Decision: Capture each allowlisted V1 content document with the shared bounded JSON
  limits before the legacy loader receives an immutable temporary snapshot. Run every
  simulation, replay, state hash, and checkpoint in fresh temporary content/save
  roots through `GameSession`, typed `GameIntent`, and `SaveLoadService`; never accept
  a caller's active session or mutate `World` directly. Proofing reads only a detached
  player-safe `GameView`, exports only known public trace endpoints, and rejects hard
  node, edge, text, or descriptor limits without truncation.
- Evidence: The focused contract, privacy, preview, simulation, proofing, SDK/CLI,
  real subprocess parity, and Windows packaging matrix passed 68 tests plus 43
  subtests; the real PyInstaller author workflow passed one test plus three subtests.
  Full unittest passed 1470 tests with 11 conditional skips. Serial and xdist pytest
  each passed 1459 tests with 11 conditional skips and 601 subtests. Ruff, Pyright,
  compileall, public-Demo validation, pip consistency, history safety, fsck, and
  whitespace checks passed. The exact post-commit baseline range check remains part of
  candidate freezing. This controller evidence does not grant TECH GO.
- Consequences: V2-2 adds no dependency, capability catalog, semver, namespace,
  dependency/conflict resolver, migration, package seal, evidence manifest, workbench,
  MCP surface, alternate compiler/runtime, content/save version, runtime campaign
  change, or `World` decomposition. `CampaignSpec v1` remains authoring IR and is not
  a preview input. The sole next gate is a fresh non-implementing read-only TECH
  decision on the exact coherent candidate. A `GO` still requires a documentation-only
  seal and then human PRODUCT PASS; it does not authorize push, `main`, release,
  publication, SECURITY PASS, or V2-3.
- Supersedes: DEC-0101 only for the completed authorization-to-start-V2-2 routing. It
  preserves the accepted V2-1 product/publication record and every private-data,
  rights, Git, product, security, and later-milestone boundary.

## DEC-0103: Normalize untrusted typed SDK inputs before V2-2 authoring work

- Date: 2026-08-05
- Status: Local V2-2 acceptance-repair candidate; a fresh exact-commit independent
  TECH decision is required.
- Context: Fresh read-only acceptance of exact candidate
  `b33c0886c4f8b4bae658edef194fe24877d78344` returned `REVISE` with one P2. A caller
  could manually construct a frozen `GameProject` or `SimulationReport` whose nested
  values were not valid contract data. Project serialization then parsed embedded
  content bytes or accessed nested fields before domain validation, so SDK operations
  could raise raw `JSONDecodeError` or `AttributeError` instead of returning an
  `AuthoringResult`. The capability gate also ran before typed-project validation, so
  4,097 invalid requirement IDs produced 4,097 diagnostics despite the result Schema's
  4,096-item bound. The structured CLI document path remained bounded and structured.
- Decision: Reuse the shared bounded UTF-8 JSON limits for in-memory canonical content
  bytes. Normalize exact typed blueprint, project, simulation-request, and report values
  through their document loaders before preview, simulation, replay, or proofing work;
  translate decode, recursion, shape, and nested-type failures into stable domain
  rejection diagnostics. Validate a project before deriving capability diagnostics,
  cap the diagnostic projection at 4,096 entries, and never materialize preview runtime
  state for an invalid project or unsupported capability set.
- Evidence: Direct SDK regressions now return one serializable rejection envelope for
  malformed embedded JSON, over-limit embedded bytes, invalid nested blueprint/request/
  report values, and all project-consuming operations. A 4,097-requirement typed value
  is rejected as `preview_project_invalid` before capability diagnostics. The corrected
  focused authoring and Windows packaging matrix passed 72 tests plus 43 subtests.
  Full unittest passed 1474 tests with 11 conditional skips. Serial and xdist pytest
  each passed 1463 tests with 11 conditional skips and 601 subtests. Ruff and standard
  Pyright, compileall, public-Demo validation, and dependency consistency passed. The
  repository-history safety, fsck, and working-tree diff checks also passed. The exact
  post-commit range check remains a candidate-freezing gate rather than TECH approval.
- Consequences: The SDK and structured CLI retain one implementation and stable result
  model; no alternate compiler/runtime, dependency, V1 content/save version, runtime
  campaign, `World`, capability-resolution, package-sealing, workbench, or later-V2
  scope is introduced. During repair, live GitHub `main` advanced from `564530d` to the
  green README-only commit `bf3f8b93d40a04b21107bc9b7c9f828a7f000539`; it remains
  divergent from and does not contain `eb972903`, so the exact V2-2 baseline and scope
  do not change. The only next gate is fresh read-only TECH acceptance of the new exact
  coherent candidate.
- Supersedes: DEC-0102 only for the typed-input rejection order, current verification
  counts, prior exact candidate, and pending-review handoff. It preserves the V2-2
  product contract, non-goals, public/private boundary, and all separate product,
  security, publication, Git, and later-milestone gates.

## DEC-0104: Bound cyclic in-memory authoring documents before SDK validation

- Date: 2026-08-05
- Status: Local V2-2 acceptance-repair candidate; a fresh exact-commit independent
  TECH decision is required.
- Context: Fresh read-only acceptance of exact candidate
  `845c04cc4a3ad3134b7cc39b025cda91ae389a25` independently closed the DEC-0103 P2 but
  returned `REVISE` with one new P2. `validate_unicode_scalars()` iterated direct Python
  list, tuple, and dict values without cycle detection or traversal limits. A dict or
  list containing itself therefore kept the public SDK `validate_blueprint_document()`
  and `validate_project_document()` entry points busy instead of returning the promised
  bounded `AuthoringResult`. The structured CLI JSON-byte path was unaffected.
- Decision: Traverse direct in-memory authoring documents iteratively under the shared
  depth-64, 200,000-node, and 1,000,000-character string limits. Track container
  identities on the active traversal path so cycles reject while repeated references
  to a shared acyclic value remain valid for later domain validation. Map traversal
  failures through the existing stable single `blueprint_invalid` or `project_invalid`
  result envelopes; add no public diagnostic code or alternate validation policy.
- Evidence: Regressions cover self-referential dict and list values across both SDK
  document entry points, require one serializable diagnostic, and validate each result
  against `AuthoringResult v1`. Direct probes now terminate in microseconds rather than
  watchdog timeouts. The corrected focused authoring and Windows packaging matrix
  passed 73 tests plus 47 subtests. Full unittest passed 1475 tests with 11 conditional
  skips; serial and xdist pytest each passed 1464 tests with 11 conditional skips and
  605 subtests. Ruff, standard Pyright, compileall, public-Demo validation, dependency
  consistency, history safety, fsck, and working-tree diff checks passed. The exact
  post-commit baseline range check remains a candidate-freezing gate, not TECH approval.
- Consequences: Direct SDK documents now share a bounded termination guarantee with the
  rest of the authoring boundary. No dependency, Schema, content/save version, runtime
  campaign, `World`, preview identity, simulation behavior, capability resolution,
  package sealing, workbench, or later-V2 scope changes. The only next gate is fresh
  read-only TECH acceptance of the amended single exact candidate.
- Supersedes: DEC-0103 only for in-memory document traversal, current verification
  counts, exact prior candidate, and pending-review routing. It preserves DEC-0103's
  typed normalization order and every V2-2 scope, privacy, compatibility, product,
  security, publication, Git, and later-milestone boundary.

## DEC-0105: Apply shared bounded JSON rules to typed simulation requests

- Date: 2026-08-05
- Status: Local V2-2 acceptance-repair candidate; a fresh exact-commit independent
  TECH decision is required.
- Context: Fresh read-only acceptance of exact candidate
  `1ea39acc195581461c56ad56ee98dcaa1ab0ce77` independently closed the earlier typed-
  input and cyclic-document findings but returned `REVISE` with one P2. A directly
  constructed `SimulationRequest` exceeding the shared string, byte, depth, or node
  limits raised `AuthoringDocumentTraversalError` from the Python SDK, while the same
  over-8-MiB request through the structured CLI returned a Schema-valid
  `authoring_input_too_large` rejection. No preview or session state was mutated.
- Decision: Preflight typed in-memory values iteratively for cycles, depth, and node
  count, stream their canonical JSON encoding under the shared 8-MiB byte cap, and
  round-trip the bytes through the existing bounded reader so string and integer rules
  cannot diverge. Normalize bounded-reader failures at the simulation boundary to one
  serialization-stage `authoring_input_<stable-code>` diagnostic before preview or
  isolated session construction. Keep the existing Unicode rejection and domain
  request validation contracts unchanged.
- Evidence: Regressions cover a 1,000,001-character string, an encoded request over
  8 MiB, depth and node limits plus one, and a 65-digit integer. They require one
  Schema-valid SDK rejection with `too_complex`, `too_large`, or `invalid_json` as
  appropriate, and prove exact SDK/CLI equivalence for the over-8-MiB request. The
  corrected focused authoring and Windows packaging matrix passed 75 tests plus 52
  subtests. Full unittest passed 1477 tests with 11 conditional skips; serial and xdist
  pytest each passed 1466 tests with 11 conditional skips and 610 subtests. Ruff,
  standard Pyright, compileall, public-Demo validation, dependency consistency,
  history safety, fsck, and whitespace checks passed. The exact post-commit baseline
  range check remains a candidate-freezing gate, not TECH approval.
- Consequences: The Python SDK and structured CLI now share the same bounded typed-
  request rejection semantics without a second parser or runtime. No dependency,
  Schema, content/save version, runtime campaign, `World`, preview/report identity,
  capability resolution, package sealing, workbench, or later-V2 scope changes. The
  only next gate is fresh read-only TECH acceptance of the amended single exact
  candidate.
- Supersedes: DEC-0104 only for typed simulation-request resource normalization,
  verification counts, exact prior candidate, and pending-review routing. It preserves
  DEC-0104's cycle guarantee and every V2-2 scope, privacy, compatibility, product,
  security, publication, Git, and later-milestone boundary.

## DEC-0106: Reject typed simulation resource failures before preview work

- Date: 2026-08-05
- Status: Local V2-2 acceptance-repair candidate; a fresh exact-commit independent
  TECH decision is required.
- Context: Fresh read-only acceptance of exact candidate
  `e7054d7c14a6e77f92874becdad6a9e451b72705` verified the DEC-0105 diagnostic and SDK/CLI
  byte equivalence but found one P2 in the rejection order. `simulate_project()` built a
  preview before validating an over-limit typed request, and `simulate_preview()` loaded
  and materialized the preview before the same validation. A capability-blocked project
  could therefore mask the required resource diagnostic. An independent spy observed
  `build_preview=1`, preview materialization twice, and `session=0` for an over-8-MiB
  request.
- Decision: Reuse the existing typed-request canonical normalization helper as a
  resource-only preflight before project preview construction and before preview loading.
  Resource failures (cycle/depth/node/byte/string/integer/Unicode) return the existing
  single serialization-stage `authoring_input_*` envelope and take precedence over
  capability diagnostics. Shape and domain validation remain in the existing post-preview
  request validation path, so unrelated semantic ordering does not change.
- Evidence: Regression spies cover SDK `simulate()` and direct `simulate_preview()` and
  assert zero `build_preview`, preview-load/materializer, and `GameSession` calls for all
  five resource-limit cases; a capability-blocked project returns
  `authoring_input_too_complex` before the capability diagnostic. The corrected focused
  authoring and Windows packaging matrix passed 75 tests plus 52 subtests; simulation and
  end-to-end matrices passed 18 tests plus 17 subtests. Full unittest passed 1477 tests
  with 11 conditional skips; serial and xdist pytest each passed 1466 tests with 11
  conditional skips and 610 subtests. Ruff, standard Pyright, compileall, public-Demo
  validation, dependency consistency, history safety, fsck, and working-tree/baseline
  whitespace checks passed. The exact post-commit range check remains a candidate-
  freezing step, not TECH approval.
- Consequences: Over-limit typed requests cannot construct or load preview state and
  cannot be hidden by capability rejection, while valid requests retain the same
  deterministic simulation/report behavior. No dependency, Schema, content/save version,
  runtime campaign, `World`, preview/report identity, capability catalog, package seal,
  workbench, or later-V2 scope changes.
- Supersedes: DEC-0105 only for resource-rejection ordering, current verification counts,
  exact prior candidate, and pending-review routing. It preserves DEC-0105's bounded
  normalization semantics and every V2-2 scope, privacy, compatibility, product, security,
  publication, Git, and later-milestone boundary.

## DEC-0107: Apply bounded canonical parity to typed authoring artifacts

- Date: 2026-08-05
- Status: Locally verified V2-2 acceptance-repair candidate; a fresh exact-commit
  independent TECH decision is required.
- Context: Fresh read-only acceptance of exact candidate
  `cb974cb9ae2f4736e52f1f519e4aa8947c54be07` independently verified the DEC-0106
  request-resource ordering repair but returned `REVISE` with one P2 and one P3. A
  directly constructed `GameBlueprint` with a 65-digit default seed passed the typed SDK
  project constructor, while the equivalent structured-CLI JSON was rejected as
  `authoring_input_invalid_json`. The resulting typed project could then validate,
  preview, simulate, replay, and proof despite containing a value that could not cross
  the bounded CLI transport. The changelog also stopped its decision range at DEC-0105
  and therefore omitted the DEC-0106 repair.
- Decision: Normalize every exact typed `GameBlueprint`, `GameProject`, and
  `SimulationReport` through canonical JSON and the shared bounded reader before its
  domain loader. Map bounded-reader failures at the shared service boundary to one
  serialization-stage `authoring_input_<stable-code>` rejection with public artifact ID
  `blueprint`, `project`, or `report`. Define Blueprint default seed and clock as signed
  64-bit integers in both Schema and loader. In `simulate_project()`, retain DEC-0106's
  request-resource preflight first, then normalize the project before any preview work.
  Preserve DEC-0104's direct cyclic-document `blueprint_invalid`/`project_invalid`
  contract and all existing domain diagnostics.
- Evidence: The repair-focused authoring and Windows packaging matrix passes 80 tests
  plus 61 subtests. Real subprocess regressions prove SDK/CLI-equivalent canonical
  rejection bytes for a 65-digit typed blueprint, all five project-consuming operations,
  and a 65-digit typed report. Signed-64 boundary regressions cover Schema and loader.
  Spies prove a project resource rejection precedes preview construction and that a
  request resource rejection still precedes project validation. Full unittest passes
  1,482 tests with 11 conditional skips; serial and xdist pytest each pass 1,471 tests
  with 11 conditional skips and 619 subtests. Ruff, standard Pyright, compileall, public-
  Demo validation, dependency consistency, history safety, fsck, and working-tree
  whitespace checks pass. The exact post-commit range check remains candidate-freezing
  evidence, not TECH approval.
- Consequences: Typed SDK values can no longer create or consume authoring artifacts that
  the structured CLI cannot read under the shared resource contract. No dependency,
  content/save version, runtime campaign, `World`, preview/report identity, capability
  resolution, package seal, workbench, or later-V2 scope changes. The only next gate is
  to amend the single exact candidate, complete its exact-range check, and submit it to
  a fresh non-implementing read-only TECH acceptance task.
- Supersedes: DEC-0106 only for typed blueprint/project/report resource parity, Blueprint
  integer bounds, current verification counts, exact prior candidate, and pending-review
  routing. It preserves DEC-0106 request-first ordering and every V2-2 scope, privacy,
  compatibility, product, security, publication, Git, and later-milestone boundary.

## DEC-0108: Normalize unsupported typed scalars into bounded rejections

- Date: 2026-08-05
- Status: Locally verified V2-2 acceptance-repair candidate; a fresh exact-commit
  independent TECH decision is required.
- Context: Fresh read-only acceptance of exact candidate
  `e1f3a806b987209f7ed9435384739c9e6865d513` independently verified the DEC-0107
  bounded canonical parity repair and all broad gates, but returned `REVISE` with one
  P2. A directly constructed typed `GameProject` containing `bytes` in workspace
  metadata, or a typed `SimulationReport` containing `bytes` as `player_name`, escaped
  raw `TypeError` from `JSONEncoder.iterencode()` through SDK validate, preview,
  simulate, replay, and proof paths instead of returning a stable `AuthoringResult`.
- Decision: Treat JSON encoder `TypeError` during the shared bounded canonical round
  trip as `BoundedJsonError(INVALID_JSON)`. Existing service boundaries then return the
  existing serialization-stage `authoring_input_invalid_json` rejection with public
  artifact ID `project` or `report`. Add an exact regression covering all five typed
  project operations and typed-report replay, including canonical result serialization.
  Do not add a diagnostic code, Schema revision, alternate serializer, or runtime path.
- Evidence: The exact Reviewer 12 reproduction now returns six stable bounded rejection
  envelopes. The repaired authoring and Windows packaging matrix passes 81 tests plus
  61 subtests. Full unittest passes 1,483 tests with 11 conditional skips; serial and
  xdist pytest each pass 1,472 tests with 11 conditional skips and 619 subtests. Ruff,
  standard Pyright, compileall, public-Demo validation, dependency consistency, history
  safety, fsck, and working-tree whitespace checks pass. The primary checkout's
  untracked `uv.lock` remains 14,471 bytes with its authorized SHA-256. The exact
  post-commit range check remains candidate-freezing evidence, not TECH approval.
- Consequences: Unsupported typed Python scalars can no longer escape public SDK
  operations as raw encoder exceptions. Existing resource precedence, domain
  diagnostics, canonical bytes, fingerprints, Schemas, content/save compatibility,
  `World`, and later-V2 boundaries do not change. The only next gate is to amend the
  single exact candidate and submit it to fresh non-implementing Reviewer 13.
- Supersedes: DEC-0107 only for unsupported typed scalar normalization, current
  verification counts, exact prior candidate, and pending-review routing. It preserves
  DEC-0107 bounded canonical parity, DEC-0106 request-first ordering, and every V2-2
  scope, privacy, compatibility, product, security, publication, Git, and later-
  milestone boundary.

## DEC-0109: Seal V2-2 independent TECH GO locally

- Date: 2026-08-05
- Status: V2-2 independent TECH GO recorded; human PRODUCT PASS remains pending.
- Context: Fresh, non-implementing Reviewer 13 performed strict read-only acceptance of
  exact product candidate `ec60cb0169678ba8d7ef1256a2f2d7cad27d1b60`, tree
  `f7c12fda17257f7a6b539bbbfce97da18452a961`, whose exact parent is accepted V2-1
  documentation head `eb972903a0b959f09a647a1727a6ed66f2d098f7`. The review returned
  P0/P1/P2/P3 all empty and final verdict `GO`, independently reproducing closure of
  DEC-0108's unsupported typed-scalar P2.
- Decision: Freeze the exact V2-2 product bytes at `ec60cb0169678ba8d7ef1256a2f2d7cad27d1b60`.
  Create one documentation-only seal updating `DECISIONS.md`, `CHANGELOG.md`,
  `PROJECT_STATE.md`, and `NEXT_TASK.md`; do not rerun full TECH acceptance because the
  accepted product bytes do not change. Route the sole next gate to the human product
  owner for explicit `PRODUCT PASS` on the exact product candidate.
- Evidence: Reviewer 13 confirmed exact SHA/branch/tree/parent, one-commit ancestry, and
  a clean worktree. Its independent adversarial probe returned one canonical
  serialization-stage `authoring_input_invalid_json` for every malformed typed project
  or report path with zero preview/materialization/`GameSession`/replay/proofing calls.
  Independent focused authoring and Windows tests passed 81 tests; full unittest passed
  1,483 with 11 conditional skips; full pytest passed 1,472 plus 619 subtests with the
  same 11 conditional skips. Ruff, Pyright, compileall, public-Demo validation, history
  safety, fsck, diff checks, and final clean status passed. Controller xdist independently
  passed the same 1,472/11/619 matrix. The 11 skips are two POSIX-only and nine Windows
  symlink-privilege cases, not passes.
- Consequences: V2-2 has TECH `GO` only. There is no PRODUCT PASS, SECURITY PASS,
  publication, push, merge, `main` movement, release, distribution authorization, or
  V2-3 authorization. The preview/report fingerprints remain reproducibility evidence,
  not package/evidence identity or a release seal.
- Supersedes: DEC-0108 only for pending independent acceptance and next-gate routing.
  DEC-0108's implementation, verification, scope, privacy, compatibility, publication,
  Git, and later-milestone boundaries remain in force.

## DEC-0110: Record V2-2 PRODUCT PASS and authorize workstream publication

- Date: 2026-08-05
- Status: V2-2 TECH GO and PRODUCT PASS complete; authorized workstream push in scope;
  SECURITY PASS remains pending.
- Context: After reviewing the completed V2-2 handoff, the product owner explicitly
  replied `PRODUCT PASS` and requested a remote push. The product decision applies to
  exact product candidate `ec60cb0169678ba8d7ef1256a2f2d7cad27d1b60`, not to the
  documentation-seal commit, preview/report fingerprints, or any future package or
  evidence identity.
- Decision: Record the human PRODUCT PASS and authorize a normal non-force push of the
  current `workstream/v2-2-agent-authoring` branch to
  `origin/workstream/v2-2-agent-authoring`. This authorization does not permit moving or
  merging `main`, release creation, SECURITY PASS, V2-3 work, or publication of private
  material. Preserve the frozen product bytes and include only documentation seals after
  the accepted product commit.
- Evidence: Pre-push live `git ls-remote` found remote `main` at
  `bf3f8b93d40a04b21107bc9b7c9f828a7f000539`, V2-1 workstream at
  `eb972903a0b959f09a647a1727a6ed66f2d098f7`, and no existing remote V2-2 workstream.
  The local branch was clean at documentation seal
  `1006d969ebd2d97fb97dff7ac09bd8d7cb53e39c`; the accepted product commit remained its
  ancestor, and the primary checkout's untracked `uv.lock` retained its authorized byte
  length and SHA-256.
- Consequences: The remote operation creates the V2-2 workstream without force-pushing
  or altering `main`. The sole next quality gate is an independently authorized
  SECURITY PASS for the exact product candidate. Publication to the workstream does not
  itself grant release, distribution, main integration, or later-milestone authority.
- Supersedes: DEC-0109 only for PRODUCT PASS status, workstream-push authorization, and
  next-gate routing. DEC-0109's exact TECH verdict and all product-byte, privacy,
  compatibility, security, release, Git, and later-milestone boundaries remain in force.

## DEC-0111: Repair the post-publication POSIX CLI test transport without changing product bytes

- Date: 2026-08-05
- Status: Verification-only repair independently accepted; V2-2 product SHA, TECH GO,
  and PRODUCT PASS unchanged; normal workstream fast-forward remains authorized;
  SECURITY PASS remains pending.
- Context: The first normal publication created remote
  `workstream/v2-2-agent-authoring` at documentation head
  `8eb549ead9118caf6677bf03e6bd837bed11c62c` without moving `main`. GitHub Actions tests
  `31043215852` and quality `31043215795` then failed on every Ubuntu Python job because
  `tests/test_authoring_end_to_end.py` passed a lone UTF-16 surrogate directly through
  POSIX subprocess argv. Python raised `UnicodeEncodeError` before the product CLI,
  parser, or shared authoring service started. Static analysis and the Windows candidate
  job succeeded.
- Decision: Keep exact PRODUCT PASS candidate
  `ec60cb0169678ba8d7ef1256a2f2d7cad27d1b60` frozen. For ordinary arguments, retain the
  real `python -m lore2mud author` subprocess. Only when a test argument cannot be UTF-8
  encoded, serialize the exact argv as ASCII JSON and rehydrate it inside an independent
  Python child process before calling the same `lore2mud.cli.main(argv)` entry point.
  Treat commit `2dc9475e12087fcca97e15c85c5a4b56220d00de` as a verification-only candidate,
  not a new product candidate or product decision.
- Evidence: Controller verification passed the exact surrogate regression, the 81-test
  plus 61-subtest authoring/Windows matrix, full unittest at 1,483 with 11 conditional
  skips, and serial/xdist pytest at 1,472 passed, 11 skipped, and 619 subtests. Ruff,
  Pyright, compileall, public-Demo validation, `pip check`, history safety, fsck, and diff
  checks passed. A product-path comparison against `ec60cb0` found no changes. Fresh,
  non-implementing Reviewer 14 independently confirmed exact SHA/parent/clean status,
  one changed test file, the ordinary and surrogate subprocess paths, canonical SDK/CLI
  rejection equivalence, 81 focused tests plus 61 subtests, static/Git gates, P0-P3 all
  empty, and final verdict `GO`.
- Consequences: A documentation-only seal may record this verdict, after which the
  controller may normally fast-forward only
  `origin/workstream/v2-2-agent-authoring` and must verify exact-head tests and quality
  Actions before closing publication. No new PRODUCT PASS is required because product
  bytes did not change. No force push, `main` movement/merge, release, SECURITY PASS,
  private-material access, or V2-3 work is authorized.
- Supersedes: DEC-0110 only for its statement that every post-product commit must be
  documentation-only; the narrow verification-harness repair above is the sole
  exception. DEC-0110's exact product decision, publication scope, privacy, security,
  release, Git, and later-milestone boundaries remain in force.

## DEC-0112: Record V2-2 SECURITY PASS locally

- Date: 2026-08-05
- Status: V2-2 TECH GO, PRODUCT PASS, and SECURITY PASS complete for the exact product
  candidate; publication of this documentation-only security seal remains unauthorized.
- Context: After the accepted product and verification-only repair were published to
  `origin/workstream/v2-2-agent-authoring` at
  `2ae85937cf284147a9a415cf350ef79e1695121b`, the security gate authority explicitly
  replied `SECURITY PASS`. The decision applies to exact product candidate
  `ec60cb0169678ba8d7ef1256a2f2d7cad27d1b60`, not to a documentation head, preview or
  report fingerprint, package/evidence identity, or future release artifact.
- Decision: Record the explicit SECURITY PASS without changing product, test, Schema,
  workflow, dependency, packaging, or runtime bytes. Do not infer or invent a separate
  P0-P3 report, additional security test run, release approval, `main` integration,
  distribution approval, or V2-3 authorization from the one-line gate decision. Refresh
  `README.md` in the same documentation-only seal so the GitHub front page describes the
  current V1 runtime and accepted V2-1/V2-2 workstreams without claiming release or
  `main` integration.
- Evidence: Exact product candidate `ec60cb0` already has fresh independent TECH `GO`
  from Reviewer 13 and human PRODUCT PASS. Verification-only candidate `2dc9475e` has
  fresh Reviewer 14 `GO`. Final published documentation head `2ae85937` passed GitHub
  Actions tests `31046078308` and quality `31046078333`, both bound to that exact SHA;
  live post-publication verification kept remote `main` at `bf3f8b93`. The security gate
  authority's explicit `SECURITY PASS` is the security decision evidence.
- Consequences: V2-2 is locally complete across TECH, PRODUCT, and SECURITY gates, while
  product bytes remain frozen at `ec60cb0`. The sole next gate is explicit authorization
  to normally fast-forward the documentation-only SECURITY PASS seal to the matching
  remote workstream. Until then, do not push this seal, move or merge `main`, release,
  distribute previews/reports, or begin V2-3.
- Supersedes: DEC-0111 only for pending SECURITY status and next-gate routing. DEC-0111's
  exact product/verification evidence and all privacy, compatibility, Git, publication,
  release, and later-milestone boundaries remain in force.

## DEC-0113: Authorize publication of the V2-2 security and README documentation seal

- Date: 2026-08-05
- Status: Normal workstream publication authorized; `main`, release, and V2-3 remain
  unauthorized.
- Context: After the local documentation-only seal recorded SECURITY PASS and refreshed
  the bilingual GitHub README, the product owner explicitly requested that the controller
  push it. The authorization applies only to the existing
  `origin/workstream/v2-2-agent-authoring` ref.
- Decision: Amend the still-unpublished documentation seal to record this authorization,
  then normally fast-forward the matching remote workstream without force. Recheck live
  remote refs before the push and verify exact-head GitHub Actions tests and quality after
  publication. Do not move or merge `main`, create a release, publish preview/report
  artifacts, or begin V2-3.
- Evidence: The pre-publication live check found remote `main` at
  `bf3f8b93d40a04b21107bc9b7c9f828a7f000539`, remote V2-2 workstream at
  `2ae85937cf284147a9a415cf350ef79e1695121b`, and the local documentation seal one commit
  ahead. Its changed paths are exactly `README.md`, `CHANGELOG.md`, `DECISIONS.md`,
  `PROJECT_STATE.md`, and `NEXT_TASK.md`; product and test paths are byte-identical to the
  published head. The primary checkout's untracked `uv.lock` retains 14,471 bytes and its
  authorized SHA-256.
- Consequences: After a successful fast-forward and green exact-head Actions, stop. The
  sole next gate becomes explicit human authorization to begin V2-3. That future gate
  does not itself authorize `main` integration, release, or distribution.
- Supersedes: DEC-0112 only for documentation-seal publication authority and next-gate
  routing. DEC-0112's exact SECURITY PASS, product freeze, evidence limits, privacy,
  release, Git, and later-milestone boundaries remain in force.

## DEC-0114: Pause V2-3 after the Authoring checkpoint

- Date: 2026-08-06
- Status: Accepted local checkpoint; no product, publication, or independent TECH verdict.
- Context: The resumed `workstream/v2-3-capability-modules` tree was dirty at HEAD
  `94f9617f7ca1303fc9190e0f200998595087eff6`, with the capability authoring lane incomplete.
  The user requested that development pause at the next recoverable checkpoint.
- Decision: Treat preview, mixed simulation/replay/checkpoint, proofing, SDK/structured-CLI,
  and generic Web host integration as the completed Authoring checkpoint. Preserve the exact
  V2-2 empty-requirement lane, keep the candidate uncommitted, and stop before the full gate
  matrix, candidate commit, or independent acceptance. Record the single resume task in the
  bilingual handoff files.
- Evidence: The focused capability/authoring/Web matrix passed `169 tests` and `480 subtests`
  on 2026-08-06; targeted Ruff/Pyright and `git diff --check` passed. Real public-safe
  `reference_counter` SDK/CLI/Web and checkpoint/replay/proofing paths are covered by focused
  tests. A fresh resume `git ls-remote` attempt timed out and is explicitly not treated as live
  remote evidence.
- Consequences: The worktree remains dirty and no candidate SHA exists. On resume, recheck live
  refs/PR/Actions and protected paths, run the full validation matrix, create one coherent
  candidate, and request fresh read-only TECH acceptance. No push, `main` movement, release,
  private-material access, or V2-4/V2-5 work is authorized by this checkpoint.
- Supersedes: None.

## DEC-0115: 修复 V2-3 capability player-view 基数边界 / Repair the V2-3 capability player-view cardinality boundary

- 日期 / Date: 2026-08-07
- 状态 / Status: `1495407` 的独立 TECH 验收结论为 `REVISE`；修复已本地验证，替代候选提交与新的独立 TECH
  验收仍待完成。 / Independent TECH acceptance of `1495407` returned `REVISE`; the repair has local verification,
  while the replacement candidate commit and a new independent TECH acceptance remain pending.
- 背景 / Context: `CapabilityRuntimeHost._validate_admissible_intents()` 验证 identity、parameters、predicates
  和 duplicate，但没有限制 player-view 的 intent 数量。公开
  `schemas/capability_player_view_entry.schema.json` 将 `admissible_intents` 限为最多 1,024 项。独立验收
  复现了 catalog-valid synthetic capability 投影 1,025 个各自有效的 intent：`GameSession.view()` 接受该输出，
  但 Draft 2020-12 schema 拒绝序列化 entry。 / `CapabilityRuntimeHost._validate_admissible_intents()` checked
  identity, parameters, predicates, and duplicates but did not cap the player-view intent count. Public
  `schemas/capability_player_view_entry.schema.json` caps `admissible_intents` at 1,024. Independent acceptance
  reproduced a catalog-valid synthetic capability with 1,025 individually valid intents: `GameSession.view()` accepted
  the output while the Draft 2020-12 schema rejected the serialized entry.
- 决定 / Decision: 在通用 runtime 的 public projection 验证阶段强制 1,024 项上限，并添加 1,024/1,025
  边界回归。超过上限的 projection 在 public view 输出前以 `CapabilityRuntimeError` 拒绝；测试证明 capability
  state 与 event sequence 不变。 / Enforce the 1,024-item limit in generic runtime public-projection validation
  and add 1,024/1,025 boundary regression coverage. An over-limit projection raises `CapabilityRuntimeError` before
  public view output; the test proves capability state and the event sequence remain unchanged.
- 证据 / Evidence: 改动仅在 `src/lore2mud/capabilities/runtime.py` 与 `tests/test_capability_runtime.py`；修复
  边界测试 `13 passed`。当前矩阵为 `unittest` `1566 OK (skipped=12)`、serial pytest
  `1554 passed, 12 skipped`、xdist pytest `1554 passed, 12 skipped, 924 subtests passed`，并且 Ruff、Pyright、
  compileall、公开 Demo validation、`pip check`、history safety、fsck 与 diff checks 均通过。12 个 skip 是本机
  PyInstaller toolchain 和 Windows symlink 权限缺失。 / Only `src/lore2mud/capabilities/runtime.py` and
  `tests/test_capability_runtime.py` change for the repair; the boundary test passed `13`. The current matrix is
  `unittest` `1566 OK (skipped=12)`, serial pytest `1554 passed, 12 skipped`, and xdist pytest
  `1554 passed, 12 skipped, 924 subtests passed`; Ruff, Pyright, compileall, public Demo validation, `pip check`,
  history safety, fsck, and diff checks all pass. The 12 skips are local absence of the PyInstaller toolchain and
  Windows symlink privilege.
- 后果 / Consequences: 不改变 `World`、`src/lore2mud/engine/save.py` 或 `pipeline/forge.py`；旧候选的
  `REVISE` 不得被视为替代候选的放行。修复必须创建新的精确候选 SHA，并仅由未参与旧实现或旧验收的新任务做
  findings-first、read-only TECH acceptance。 / `World`, `src/lore2mud/engine/save.py`, and `pipeline/forge.py`
  remain unchanged; the old candidate's `REVISE` cannot approve its replacement. The repair must become a new exact
  candidate SHA and receive findings-first, read-only TECH acceptance from a new task that did not implement or
  review the old candidate.
- 取代 / Supersedes: 仅取代 DEC-0114 中“下一个步骤是创建候选并首次验收”的状态路由；DEC-0114 的 V2-3
  scope、privacy、Git、compatibility 与 later-milestone 边界继续有效。 / Supersedes DEC-0114 only for its
  state routing that the next step was initial candidate creation and acceptance; DEC-0114's V2-3 scope, privacy,
  Git, compatibility, and later-milestone boundaries remain in force.

## DEC-0116: 记录 V2-3 TECH GO 并封存文档 / Record V2-3 TECH GO and seal the handoff documentation

- 日期 / Date: 2026-08-07
- 状态 / Status: V2-3 exact candidate TECH `GO` complete; documentation-only handoff seal complete locally.
  PRODUCT PASS、SECURITY PASS、workstream publication、`main` movement、release and later milestones remain pending
  separate authorization. / V2-3 exact-candidate TECH `GO` is complete and this documentation-only handoff seal is
  complete locally. PRODUCT PASS, SECURITY PASS, workstream publication, `main` movement, release, and later milestones
  remain pending separate authorization.
- 背景 / Context: Fresh, non-implementing, read-only acceptance reviewed
  `aa56770ccbefa77ab405ef5739dab769e6536592` against authorized baseline
  `c37969f6b6958e66474738f88a53b9d5c2f50d99`. It independently reproduced the repaired public boundary: 1,024 intents
  project successfully, while 1,025 raises `CapabilityRuntimeError` with unchanged capability state and event sequence `0`.
- 决定 / Decision: Freeze the V2-3 technical candidate at `aa56770`; record P0-P3 all empty and final `GO` in the
  four bilingual handoff files; stop implementation and complete the active Goal after this documentation-only commit.
  Do not add product bytes, rerun a replacement product review, push, move `main`, release, access private material,
  or enter V2-4/V2-5. / Freeze the V2-3 technical candidate at `aa56770`; record P0-P3 empty and final `GO` in the four
  bilingual handoff files; stop implementation and complete the active Goal after this documentation-only commit.
  Do not add product bytes, rerun a replacement product review, push, move `main`, release, access private material,
  or enter V2-4/V2-5.
- 证据 / Evidence: The fresh reviewer reported P0/P1/P2/P3 all empty; focused groups passed `96` and `58` tests,
  full unittest passed `1566` with `12` skips, and serial pytest passed `1554` with `12` skips. Public Demo validation,
  compileall, repository-safety history scan, fsck, and baseline diff checks passed. The reviewer lacked Ruff, Pyright,
  and xdist; those were recorded as tool gaps, while Controller reran them from repository-external tools. No protected
  `World`, save-core, `pipeline/forge.py`, or private-material paths changed.
- 后果 / Consequences: The V2-3 technical handoff is complete, but this is not a product, security, publication, main,
  or release decision. The next task is to wait for explicit independent authorization; preserve the clean frozen tree.
- 取代 / Supersedes: DEC-0115 only for its pending acceptance and state routing; DEC-0115's cardinality repair,
  verification evidence, privacy boundary, and Git/later-milestone limits remain in force.

## DEC-0117: 记录 V2-3 文档封存发布与 main 合并 / Record V2-3 documentation-seal publication and main integration

- 日期 / Date: 2026-08-07
- 状态 / Status: V2-3 documentation seal published and merged to `main` under explicit user authorization;
  PRODUCT PASS, SECURITY PASS, release, and distribution remain separate pending gates. / V2-3 documentation seal 已在
  用户明确授权下发布并合并到 `main`；PRODUCT PASS、SECURITY PASS、release 与分发仍是独立的待决门禁。
- 背景 / Context: The frozen V2-3 product candidate is `aa56770ccbefa77ab405ef5739dab769e6536592`, and the
  documentation-only handoff seal is `26fe8428d39f366e068ba7986975322e72d0f355`. The product owner explicitly
  authorized both a normal push and a `main` merge on 2026-08-07.
- 决定 / Decision: Record the completed non-force fast-forward publication of the seal head to
  `origin/workstream/v2-3-capability-modules` and `origin/main`. At publication completion both live refs pointed exactly
  to `26fe8428d39f366e068ba7986975322e72d0f355`; this follow-up commit only records the fact in the handoff documents and
  does not change product or test bytes. / 记录该封存头已无强制推送地正常快进发布到两个远端 ref；发布完成时两者均精确指向
  `26fe8428d39f366e068ba7986975322e72d0f355`。本后续提交只记录事实，不改变产品或测试字节。
- 证据 / Evidence: GitHub Actions for exact `26fe842` completed successfully: tests runs `31156995926` and
  `31156931379`, quality runs `31156995982` and `31156931281`. Before publication, the final local xdist matrix was
  `1564 passed, 2 skipped, 927 subtests passed`; the focused PyInstaller packaging matrix was `17 passed, 12 subtests
  passed`, and manual Windows symbolic-link creation succeeded. The two full-suite skips are POSIX-only symlink tests;
  they are not product failures.
- 后果 / Consequences: V2-3 product bytes remain frozen at `aa56770`; the published documentation seal does not itself
  grant PRODUCT PASS, SECURITY PASS, release, distribution, private-material access, or V2-4/V2-5 authorization. The next
  routed gate is the independent PRODUCT/SECURITY decision plus any separately authorized release action. / V2-3 产品字节
  继续冻结于 `aa56770`；本发布不授予 PRODUCT PASS、SECURITY PASS、release、分发、私有材料访问或 V2-4/V2-5 权限。下一门禁
  是独立 PRODUCT/SECURITY 决定及另行授权的 release 动作。
- 取代 / Supersedes: DEC-0116 only for publication and `main` state routing. DEC-0116's TECH `GO`, product-byte freeze,
  privacy, compatibility, release, and later-milestone boundaries remain in force.

## DEC-0118: 完成 V2-4A 本地验收并冻结候选 / Complete V2-4A local acceptance and freeze the candidate

- 日期 / Date: 2026-08-08
- 状态 / Status: V2-4A exact local product candidate has TECH `GO`, PRODUCT `PRODUCT PASS`, and SECURITY `GO`.
  Publication, `main` movement, release, distribution, and later-milestone work remain unapproved. / 精确 V2-4A
  本地产品候选已获得 TECH `GO`、PRODUCT `PRODUCT PASS` 和 SECURITY `GO`；发布、`main` 移动、release、分发和
  后续里程碑仍未获授权。
- 背景 / Context: The authorized V2-4A workstream began from `36ff77fb5daa3407a79b0b2359a03a49a63003a0` and produced
  candidate `badc9a20816a9515b24c98199ca37323a02c1b00` on
  `workstream/v2-4a-provenance-rights-20260807-r2`. It provides public-safe source/rights/decision/transformation
  tracing, deterministic package and evidence identity, explicit anchor migration, and shared AuthoringService/SDK/CLI/Web
  validation without changing `World`, save core, V1 content-pack contracts, or client game rules. The final privacy repair
  anonymizes private-connected element labels as well as IDs before public sealing.
- 决定 / Decision: Freeze `badc9a2` as the V2-4A local product candidate; record all three independent gate decisions
  and update the bilingual handoffs. Preserve candidate bytes, keep `main` read-only, and stop this Goal after the
  documentation-only local seal. Do not push, merge, release, distribute, access private material, reseal an existing
  candidate in place, or enter V2-5. / 将 `badc9a2` 冻结为 V2-4A 本地产品候选；记录三项独立门禁并更新双语交接。
  保持候选字节不变、`main` 只读，并在 documentation-only 本地封存后停止本 Goal。不得 push、合并、release、分发、
  访问私人材料、原地重封已有候选或进入 V2-5。
- 证据 / Evidence: Focused V2-4 contracts passed `56`; the public-safe 30–60 minute story-arc smoke passed `1`;
  full pytest passed `1619` with `3` conditional skips and full unittest passed `1622` with `3` conditional skips.
  Ruff, Pyright, compileall, public Demo validation, `pip check`, `git diff --check`, history safety, and
  `git fsck --full --no-dangling` passed. Fresh TECH found P0-P3 empty and returned `GO`; fresh PRODUCT found P0-P3
  empty and returned `PRODUCT PASS`; fresh SECURITY found P0-P3 empty and returned `GO`. Live `origin/main` and
  `origin/workstream/v2-3-capability-modules` were both rechecked at `36ff77`; the main checkout's user-owned untracked
  `uv.lock` stayed outside this candidate.
- 后果 / Consequences: V2-4A contracts are locally accepted but not published. The next task must be selected by a new
  product decision, rather than inferred from this candidate or any gate. The separate housekeeping branch remains
  independent; no merge or scope transfer is implied. / V2-4A contracts 已在本地验收但尚未发布。下一任务必须由新的产品
  决定选择，不能由本候选或任何门禁推断。独立 housekeeping 分支仍保持独立；本记录不暗示合并或范围转移。
- 取代 / Supersedes: The V2-3 routing in DEC-0117 only as the current-task pointer. DEC-0117 remains the historical
  record of V2-3 publication; its publication and release boundaries are unchanged.

## DEC-0119: 发布 V2-4A 文档封存并纯快进整合 main / Publish the V2-4A documentation seal and fast-forward main

- 日期 / Date: 2026-08-09
- 状态 / Status: V2-4A documentation seal is published and fast-forward integrated into `main` under explicit
  product-owner authorization. Release, content distribution, private-material access, and V2-5 remain separate,
  unauthorized gates. / V2-4A documentation seal 已在产品所有者明确授权下发布并纯快进整合到 `main`；release、
  内容分发、私人材料访问与 V2-5 仍是独立且未授权的门禁。
- 背景 / Context: The frozen V2-4A product candidate is
  `badc9a20816a9515b24c98199ca37323a02c1b00`; its documentation-only acceptance seal is
  `c7e3280083ebc77a2b453f9bc057df302b00202a` on
  `workstream/v2-4a-provenance-rights-20260807-r2`. The product owner explicitly authorized closing the private
  playtest service and continuing V2-4 through normal push and `main` integration on August 9, 2026.
- 决定 / Decision: Record the completed non-force publication of `c7e3280` to
  `origin/workstream/v2-4a-provenance-rights-20260807-r2` and the pure fast-forward of `origin/main` from `36ff77f`
  to the same SHA. At publication completion, a fresh `git ls-remote` showed both live refs exactly at `c7e3280`.
  This follow-up commit changes only the five public handoff/decision documents and leaves product, Schema, source,
  and test bytes unchanged. / 记录 `c7e3280` 已无强制推送地发布到工作分支，并将 `origin/main` 从 `36ff77f`
  纯快进到同一 SHA；发布完成时实时远端查询确认两个 ref 均精确位于 `c7e3280`。本后续提交仅修改五份公共
  交接/决策文档，不改变产品、Schema、源码或测试字节。
- 证据 / Evidence: Before publication, full pytest passed `1619` with `3` conditional skips. A bare host
  `python -m unittest discover` first imported the editable package from the main checkout and failed during candidate
  test collection; after explicitly selecting the candidate `src`, the complete unittest matrix passed `1622` with
  `3` conditional skips. Ruff, Pyright, compileall, public Demo validation, `pip check`, history safety,
  `git fsck --full --no-dangling`, and range `git diff --check` passed. Both worktrees were clean except for the
  preserved main-checkout `uv.lock` at 14,471 bytes and SHA-256
  `3b47a6e779ce74c7b91e899c93f00f353d99986ee2168d5ab8f1275e35de73fc`.
- 后果 / Consequences: V2-4A contracts are now available on public `main`, while frozen product identity remains
  `badc9a2`. The next routed V2-4 work is a new public-safe V2-4B / PLAT-1 presentation slice that localizes stable
  IDs before player display and projects an explicit completion/ending result in CLI/Web, using synthetic fixtures
  rather than private story material. It requires its own implementation verification and fresh independent TECH
  acceptance; no automatic push, `main` movement, release, distribution, or V2-5 follows. / V2-4A contracts 现已进入
  公共 `main`，冻结产品身份仍为 `badc9a2`。下一项 V2-4 工作路由为新的公开安全 V2-4B / PLAT-1 表现层切片：
  在玩家显示前本地化稳定 ID，并在 CLI/Web 投影明确的通关/结局结果；仅使用合成 fixture，不访问私有故事材料。
  该切片需要自己的实现验证与全新独立 TECH 验收，不自动授权 push、`main` 移动、release、分发或 V2-5。
- 取代 / Supersedes: DEC-0118 only for publication, `main`, and next-task routing. DEC-0118's exact product freeze,
  TECH/PRODUCT/SECURITY decisions, privacy guarantees, compatibility boundaries, and release limits remain in force.
