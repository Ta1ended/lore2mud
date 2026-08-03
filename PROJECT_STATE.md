# Project State

_Last updated: 2026-08-03_

## Objective

Deliver an Agent-callable novel-to-text-game engine whose Authoring Plane produces
validated, traceable packages for a deterministic Runtime Plane, while preserving V1
compatibility and strict public/private and rights boundaries.

## Current Status

Gate 0 commit `1a5a8857579ebf840de4e39e414b52592baea6ba` is the accepted public
V2 reset baseline (DEC-0086); live refs must still be verified operationally by each
new task. V2-0 target `d13dd0590f47f6477b476cfbdab2715b8f4aba7a` received
independent TECH GO and the user/product owner's explicit PRODUCT PASS on 2026-08-03.
This isolated branch records that acceptance in a documentation-only seal. The seal
does not self-approve or record its own controller publication or post-seal Actions;
those live states require operational verification. V2-1 is the single routed next
task and has not started.

## Completed

- Gate 0 public runtime/content baseline is accepted and present on `main` (DEC-0086).
- V1 provides strict public content loading, authoritative `World` gameplay, CLI and
  local Web clients, save v9, runtime campaign support, deterministic authoring
  compilers, Forge, packaging, and repository safety checks.
- V2-0 product and architecture direction, roles, milestone order, PLAT-1, and safety
  posture are accepted through separate TECH and PRODUCT gates (DEC-0087, DEC-0088).
- `CODE_MAP.md` records the real V1 data flows, central modules, current gaps, and
  where V2 changes belong.

## In Progress

- No V2 implementation is in progress. Focused review and publication of the exact
  documentation seal are separate controller actions verified from live evidence.

## Blockers

- A fresh V2-1 task must verify live `main` contains the exact accepted seal before
  it starts. This seal does not itself authorize edits, ref movement, push, or release.
- No product or architecture blocker is currently known for the routed V2-1 scope.

## Verification

- Gate 0 independent acceptance - GO (2026-08-03; DEC-0086).
- Gate 0 branch and post-main unittest/pytest, Ruff, Pyright, compileall, public
  content, safety, fsck, and diff gates - green (2026-08-03; DEC-0086).
- V2-0 local matrix - 1,390 unittest tests passed with 12 conditional skips;
  pytest reported 1,378 passed and 12 skipped (2026-08-03).
- V2-0 local quality and boundary gates - Ruff, Pyright, compileall, original-demo
  validation, history safety, fsck, staged/working diff checks, relative-link check,
  exact 13-path audit, protected-tree byte audit, stale-claim/privacy/model-floor
  searches, and `uv.lock` absence all passed (2026-08-03).
- V2-0 independent TECH re-review of exact target `d13dd05` - GO with no P0-P3
  findings after reproducing and closing the prior ContentPack P3 (2026-08-03).
- Repair-branch GitHub Actions tests run `30822377956` and quality run `30822378186`
  completed successfully (2026-08-03).
- V2-0 user/product owner PRODUCT PASS - explicit pass (2026-08-03).
- This seal's focused local documentation verification is recorded in DEC-0088; it
  does not substitute for a fresh focused independent review of the exact seal.

## Key Paths

- `AGENTS.md` - mandatory task, model, gate, architecture, and safety rules.
- `PRODUCT.md` - product users, modes, contracts, PLAT-1, metrics, and non-goals.
- `CODE_MAP.md` - current symbols, data flows, risks, and future ownership.
- `docs/v2/architecture.md` - target Authoring/Runtime Plane contracts.
- `docs/v2/development_model.md` - Codex roles and separated passes/gates.
- `docs/v2/roadmap.md` - approved V2-0 through V2-5 sequence.
- `NEXT_TASK.md` - the single routed next task.

## Risks And Unknowns

- V2 contract names are direction only until code, compatibility tests, and independent
  acceptance implement them.
- `World`, loader, save, command, Web, and campaign modules are large and coupled;
  V2 must introduce boundaries incrementally rather than rewrite them wholesale.
- `CampaignSpec v1` has no runtime materializer and is not a runtime input.
- MCP, dynamic plugins, generated code, and unrestricted host/network access are not
  authorized. SDK and structured CLI precede any MCP adapter.
- Private source, canon, adaptations, images, and reports remain outside public Git;
  no V2 milestone changes that boundary without explicit owner authorization.
- The primary checkout retains an intentionally untracked `uv.lock` of 14,471 bytes,
  SHA-256 `3b47a6e779ce74c7b91e899c93f00f353d99986ee2168d5ab8f1275e35de73fc`.
  It is absent from this isolated worktree and must not be created or committed here.
