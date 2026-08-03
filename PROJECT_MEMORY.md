# Project Memory

_Compact durable snapshot, updated 2026-08-03_

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

- Gate 0 commit `1a5a8857579ebf840de4e39e414b52592baea6ba` is the accepted public
  V2 reset baseline (DEC-0086). Verify live refs operationally; do not infer them from
  this snapshot.
- V2-0 target `d13dd0590f47f6477b476cfbdab2715b8f4aba7a` received independent
  TECH GO with no P0-P3 findings after the ContentPack P3 was closed. GitHub Actions
  runs `30822377956` and `30822378186` succeeded, and the product owner explicitly
  gave PRODUCT PASS on 2026-08-03 (DEC-0088).
- V2-0 direction is complete. This seal does not self-approve or record post-seal
  publication/Actions; exact seal review and live refs are controller-verified
  operational state. V2-1 is routed but not started, and a fresh task must verify
  live `main` before any implementation.
- Primary-checkout `uv.lock` is intentionally untracked: 14,471 bytes, SHA-256
  `3b47a6e779ce74c7b91e899c93f00f353d99986ee2168d5ab8f1275e35de73fc`.
  Do not create it in isolated worktrees or include it in a commit.

## V1 Runtime Contract

- `load_content_pack()` validates JSON and returns a shallow-frozen `ContentPack`:
  dataclass fields cannot be reassigned, but its collection mappings remain mutable.
- `World.from_content_pack()` creates the authoritative mutable runtime.
- `CommandProcessor` parses/renders CLI commands but delegates rules to `World`.
- `SaveLoadService` owns strict save v9 I/O and supported v7/v8 read gates.
- Web `PlayerSession` validates structured actions, calls `World`/`CommandProcessor`,
  and builds event/snapshot dictionaries; it is the V2 session precursor.
- `CampaignSpec v1` is pipeline authoring IR. It is not `campaign.json`, a content
  pack, or a runtime input. No CampaignSpec-to-runtime materializer exists.
- Forge currently runs inspection and registry-adaptation stages only.

## V2 Direction

- V2-0 accepted these contracts as direction; they are not implemented runtime or
  authoring APIs unless current code and acceptance evidence explicitly say so.
- Authoring Plane: source and decisions -> `GameBlueprint v1` -> `GameProject v1` ->
  validation/simulation/trace/rights gates -> `GamePackage v2`.
- Runtime Plane: package + `GameIntent` -> `GameSession` -> `GameEvent` values +
  `GameView` -> `TurnResult`.
- `World` remains a compatibility facade during migration. CLI and Web must share the
  session/application layer before capability modularization.
- `CapabilityDescriptor v1` declares safety, namespaced state, intents, predicates,
  effects, events, views, validation, and migrations from a static engine catalog.
- Python SDK and structured CLI come first. MCP is a later adapter.
- No dynamic code/plugin execution initially. Executable/process/shell/unrestricted
  network capability remains forbidden.

## Development Contract

- Every implementation, architecture, and acceptance task/subagent explicitly uses
  `gpt-5.6-sol` with reasoning `xhigh` or higher. Stop and report if unavailable.
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
