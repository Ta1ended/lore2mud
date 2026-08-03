# Project State

_Last updated: 2026-08-03_

## Objective

Deliver an Agent-callable novel-to-text-game engine whose Authoring Plane produces
validated, traceable packages for a deterministic Runtime Plane, while preserving V1
compatibility and strict public/private and rights boundaries.

## Current Status

Public `main` and `origin/main` are synchronized at
`1a5a8857579ebf840de4e39e414b52592baea6ba`. Gate 0 recovered the public baseline,
received fresh independent GO, and passed its branch and post-main test/quality gates.
V2-0 is now an isolated documentation-only reset candidate on
`workstream/v2-product-architecture-reset`; implementation cannot approve it.

## Completed

- Gate 0 public runtime/content baseline is accepted and present on `main` (DEC-0086).
- V1 provides strict public content loading, authoritative `World` gameplay, CLI and
  local Web clients, save v9, runtime campaign support, deterministic authoring
  compilers, Forge, packaging, and repository safety checks.
- The accepted V2 direction, roles, milestone order, PLAT-1, and safety posture are
  recorded in `PRODUCT.md` and `docs/v2/` (DEC-0087).
- `CODE_MAP.md` records the real V1 data flows, central modules, current gaps, and
  where V2 changes belong.

## In Progress

- The V2-0 documentation candidate is pending a fresh independent read-only TECH
  review of its exact commit and the user's PRODUCT PASS.

## Blockers

- V2-1 is blocked on both V2-0 gates and a subsequent docs-only controller seal.
- No implementation blocker is currently known.

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
- V2-0 independent TECH PASS - pending.
- V2-0 user PRODUCT PASS - pending.

## Key Paths

- `AGENTS.md` - mandatory task, model, gate, architecture, and safety rules.
- `PRODUCT.md` - product users, modes, contracts, PLAT-1, metrics, and non-goals.
- `CODE_MAP.md` - current symbols, data flows, risks, and future ownership.
- `docs/v2/architecture.md` - target Authoring/Runtime Plane contracts.
- `docs/v2/development_model.md` - Codex roles and separated passes/gates.
- `docs/v2/roadmap.md` - approved V2-0 through V2-5 sequence.
- `NEXT_TASK.md` - the only authorized continuation.

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
