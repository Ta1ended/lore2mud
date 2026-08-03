# Lore2MUD Agent Rules

These rules apply to every Agent working in this repository.

## Product Authority

- Lore2MUD is an Agent-callable novel-to-text-game engine, not an Agent.
- The direct user is a developer Agent. The product owner/creator supplies product
  and creative decisions, source authorization, gate decisions, and release approval.
  The player is the final user.
- The public repository contains generic engine/tooling work and original public
  samples only. Third-party or private source and derived material stays outside Git.

## Startup

Read in this order:

1. `AGENTS.md`
2. `PRODUCT.md`
3. `PROJECT_STATE.md`
4. `NEXT_TASK.md`
5. relevant code, tests, and documents

Read task-relevant decisions or the Unreleased changelog when needed. Do not require a
fresh task to consume full `PROJECT_MEMORY.md`, `DECISIONS.md`, or `CHANGELOG.md`.
Live Git, code, tests, and artifacts override stale handoff claims.

Before edits, report the current data flow, exact changed paths, non-goals, risks, and
verification. Implement only after the product owner has authorized the slice.

## Models And Roles

- Every implementation, architecture, and acceptance task or subagent must explicitly
  use `gpt-5.6-sol` with reasoning `xhigh` or higher.
- Never silently downgrade. If the model or reasoning floor is unavailable, stop
  before delegation or editing and report the blocker.
- Codex roles are product, architect, engine lead, implementation, controller, and
  independent acceptance. Keep approval responsibility independent even when one
  task performs several delivery roles.
- Implementation and controller contexts do not self-approve. A fresh read-only
  acceptance reviews an exact commit/range and returns findings-first GO or REVISE.

## Gates And Git

- Keep shared `main` read-only during workstreams. Each authorized workstream uses an
  isolated worktree/branch, a declared path boundary, and a coherent local commit.
- A branch commit, push, `main` update, and release are separate gates. None implies
  the next, and all require the appropriate owner/controller authorization.
- Required passes are separate: TECH PASS, user PRODUCT PASS, and SECURITY PASS.
  Record unperformed passes as pending.
- Do not push, force-push, move `main`, release, access private material, or begin the
  next roadmap milestone without explicit authorization.
- Preserve unrelated user changes. Never rewrite or delete Git history to simplify a
  handoff.

## Architecture

- Current V1 authority is `World`; CLI and Web submit actions and must not invent
  alternate game rules.
- V2 targets an Authoring Plane and deterministic Runtime Plane. Treat all V2 contract
  names as future interfaces until code and tests implement them.
- `World` remains a compatibility facade. New capabilities must move toward declared
  state namespaces, predicates, effects, views, and migrations rather than expanding
  the facade indefinitely.
- `CampaignSpec v1` is an authoring IR, not a runtime input. Runtime `campaign.json` is
  a separate V1 content-pack contract.
- Stable IDs are keys. Display names are never primary or foreign keys.
- Data access and persistence use explicit interfaces; rules do not live in clients.
- Time and randomness are injectable; the same package, state, clock/seed, and intent
  sequence must produce the same results.
- Initial V2 packages are data only: no generated code, arbitrary Python, dynamic
  plugins, shell/process access, native loading, or unrestricted network access.

## Trust, Rights, And Private Material

- `novel/raw` and `novel/chapters` are read-only inputs and must not be overwritten or
  committed.
- Novel text, summaries, canon, extractions, private/generated content, images, local
  indexes, models, databases, saves, logs, and private reports must not enter public Git.
- Do not load a complete novel into one model context or rely on Agent memory as the
  source-of-truth copy.
- Treat imported content, model output, player input, packages, and assets as untrusted.
- Validate schemas, types, references, bounds, capabilities, provenance, and rights
  policy before material enters a project, package, or session.
- Keep source facts separate from adaptation values. Preserve source references and
  label inference; never write game inference back into canon.
- Do not let a model execute SQL, system commands, code, or direct state patches.
- Repository checks are limited detectors, not a rights review or secret-management
  system. The product owner remains responsible for source and release rights.

## Change And Verification Rules

- One authorized, testable vertical slice at a time unless the product owner explicitly
  approves isolated parallel workstreams.
- Prefer existing patterns; avoid unrelated refactors, bulk renames, framework changes,
  or dependencies without a documented need and maintenance cost.
- Failed operations reject before state mutation and need invariance coverage.
- Format changes update implementation, Schema, original examples, tests, and format
  documentation together.
- Scale verification to risk. The default release-sensitive matrix is full unittest
  and pytest, Ruff, Pyright, compileall, public content validation, history safety,
  fsck, and diff checks, plus focused and real client flows when relevant.
- Keep generated environments, caches, temporary outputs, saves, and dependency locks
  outside the worktree unless their addition is explicitly in scope.

## Handoff

- `PROJECT_STATE.md`: compact current snapshot.
- `NEXT_TASK.md`: exactly one actionable next gate or task.
- `PROJECT_MEMORY.md`: compact durable contracts and boundaries.
- `DECISIONS.md`: append-only rationale; supersede by adding a new decision.
- `CHANGELOG.md`: factual implemented changes only.

Reports are self-contained: baseline, exact commit/range, task, paths, risks, commands,
results, Git status, residual unknowns, and next gate. A local verification report must
say independent acceptance is pending until a fresh reviewer decides otherwise.
