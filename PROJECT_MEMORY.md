# Project Memory

_Compact durable snapshot, updated 2026-08-04_

## Resume

Read `AGENTS.md`, `PRODUCT.md`, `PROJECT_STATE.md`, `NEXT_TASK.md`, then only the
code/docs relevant to the active task. Use `DECISIONS.md`, `CHANGELOG.md`, and older
history for targeted evidence, not mandatory startup reading. Live Git and tests win
over this cache.

## Product Contract

- Lore2MUD is an Agent-callable novel-to-text-game engine, not an Agent.
- Direct user: developer Agent. Product authority and creative direction: user/product
  owner. Final user: player.
- Product modes are `prototype`, `traced`, and `sealed`.
- PLAT-1 requires a fresh Agent, public-safe material, and an approved
  `GameBlueprint` to create a deterministic 20-30 minute game without core changes,
  with build/validate/simulate/Web/save evidence.
- Technical first path: existing public `urban_investigation` family. Product sample:
  a new original investigation. Second genre: cultivation.

## Current Repository State

- Live published `main` was verified at
  `564530d87aea17da26544b7793701e0dca0fe57d` before the V2-1 workstream. The local
  candidate branch is based on accepted planning commit
  `1d4b26d9127d4229893911cf260cf3c2f4b0ce3a`; verify live refs operationally rather
  than inferring them from this snapshot.
- V2-0 target `d13dd0590f47f6477b476cfbdab2715b8f4aba7a` received independent
  TECH GO with no P0-P3 findings after the ContentPack P3 was closed. GitHub Actions
  runs `30822377956` and `30822378186` succeeded, and the product owner explicitly
  gave PRODUCT PASS on 2026-08-03 (DEC-0088).
- V2-0 direction is complete. A V2-1 local candidate now implements the shared public
  runtime boundary on `workstream/v2-1-game-session`; it is not published, does not
  move `main`, and gains no PRODUCT or SECURITY pass from local implementation.
- Primary-checkout `uv.lock` is intentionally untracked: 14,471 bytes, SHA-256
  `3b47a6e779ce74c7b91e899c93f00f353d99986ee2168d5ab8f1275e35de73fc`.
  Do not create it in isolated worktrees or include it in a commit.

## V1 Runtime Contract

- `load_content_pack()` validates JSON and returns a shallow-frozen `ContentPack`:
  dataclass fields cannot be reassigned, but its collection mappings remain mutable.
- `World.from_content_pack()` creates the authoritative mutable runtime.
- `GameSession` coordinates typed turns around authoritative `World` and returns
  frozen `TurnResult` values containing ordered events and a complete safe view.
- `CommandProcessor` parses/renders CLI commands over `GameSession` and retains its
  compatibility constructor and dynamic `.world` property.
- `SaveLoadService` owns strict save v9 I/O and supported v7/v8 read gates.
- Web `PlayerSession` keeps its compatibility name but validates/renders around the
  same `GameSession`; browser affordances come from `GameView` instead of duplicated
  gameplay rules.
- `CampaignSpec v1` is pipeline authoring IR. It is not `campaign.json`, a content
  pack, or a runtime input. No CampaignSpec-to-runtime materializer exists.
- Forge currently runs inspection and registry-adaptation stages only.

## V2 Direction

- V2-1 runtime contracts are implemented in `src/lore2mud/application/` only where
  current code and acceptance evidence say so. Later authoring, package, capability,
  SDK, diagnostics, simulation, proofing, and MCP contracts remain future work.
- Authoring Plane: source and decisions -> `GameBlueprint v1` -> `GameProject v1` ->
  validation/simulation/trace/rights gates -> `GamePackage v2`.
- Runtime Plane: package + `GameIntent` -> `GameSession` -> `GameEvent` values +
  `GameView` -> `TurnResult`.
- `World` remains the compatibility authority during migration. CLI and Web share the
  V2-1 session/application layer before capability modularization.
- `CapabilityDescriptor v1` declares safety, namespaced state, intents, predicates,
  effects, events, views, validation, and migrations from a static engine catalog.
- Python SDK and structured CLI come first. MCP is a later adapter.
- No dynamic code/plugin execution initially. Executable/process/shell/unrestricted
  network capability remains forbidden.

## Development Contract

- The controller selects available models and reasoning levels by responsibility and
  risk, records the choice when exposed, and treats code/tests rather than model output
  as correctness evidence.
- Separate TECH PASS, user PRODUCT PASS, and SECURITY PASS. No self-approval.
- Shared `main` is read-only during workstreams. Branch commit, push, main movement,
  and release are distinct owner/controller gates.
- Keep `PROJECT_STATE.md` current, `NEXT_TASK.md` singular, `DECISIONS.md` append-only,
  and `CHANGELOG.md` factual.

## Public, Private, And Rights Boundary

- Public Git contains generic code/tools/contracts and original public samples only.
- Private novel text, chapters, summaries, canon, adaptations, images, indexes,
  databases, saves, logs, and reports remain external and owner-controlled.
- Imported content, player input, model output, packages, and assets are untrusted.
- The engine records provenance and rights assertions; it does not grant rights or
  decide whether an assertion is true.
- Never overwrite raw source, load an entire novel into one context, expose private
  paths/content in public artifacts, or let generated content execute code/SQL/shell.

## Pause

Stop running work, finish or terminate required sessions, check Git status, reconcile
the compact handoff files from evidence, and leave the worktree either coherently
committed or explicitly described. Do not start background work on resume.
