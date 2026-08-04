# Lore2MUD V2 Development Model

## Product Authority

The user is the product owner, source-rights authority, creative director, and first
player. The user approves product boundaries, creative choices, milestone exits,
push, main movement, and release. Codex supplies analysis and delivery evidence; it
does not silently replace product decisions.

## Codex Roles

One task may hold one or more roles, but approval roles remain independent:

| Role | Responsibility |
|---|---|
| Product | Convert owner direction into outcomes, non-goals, scenarios, and metrics. |
| Architect | Define contracts, dependencies, compatibility, and security boundaries. |
| Engine lead | Own sequencing, integration risk, and shared runtime quality. |
| Implementation | Deliver one bounded workstream and its local verification. |
| Controller | Maintain worktree boundaries, compose accepted candidates, and route gates. |
| Independent acceptance | Read-only findings-first review of an exact commit/range; return GO or REVISE. |

The controller selects an available model and reasoning level for each responsibility
domain according to task complexity, stability, and risk. Record the selection when
the tool exposes it, the assigned responsibility, produced artifacts, verification,
and any rework. Model output is not correctness evidence. Shared contracts,
persistence, state transactions, security boundaries, and independent acceptance
should use the most reliable available reasoning; incomplete, contradictory,
out-of-scope, or unverifiable work is reassigned rather than integrated.

## Required Passes

- **TECH PASS**: contracts are internally consistent; tests and quality gates pass;
  compatibility, determinism, and failure invariance are demonstrated.
- **PRODUCT PASS**: the product owner confirms the workflow, language, creative
  boundary, success metric, and player experience solve the intended problem.
- **SECURITY PASS**: untrusted-input, rights, private-data, package, capability,
  dependency, artifact, and release boundaries are checked.

Passing one does not imply either of the others. Implementation and controller
contexts cannot self-approve. Independent acceptance may grant the requested TECH or
SECURITY gate only; PRODUCT PASS remains the product owner's decision.

## Workstream Lifecycle

1. Start from a verified commit and restate the one authorized outcome, changed-path
   boundary, non-goals, risks, and gate plan.
2. Use an isolated worktree and branch. Shared `main` is read-only while workstreams
   are active.
3. Implement and verify only the declared scope. Commit a coherent candidate locally.
4. Run a fresh independent read-only review of the exact commit or range. Findings
   lead with P0-P3; the result is exactly GO or REVISE.
5. The controller may compose only accepted inputs, then requests any required
   combined TECH, PRODUCT, and SECURITY passes.
6. Stop at the authorized gate. A branch commit, push, main update, and release are
   four distinct actions and four distinct authorization decisions.

No task may infer permission to push, move `main`, publish a release, access private
material, or begin the next milestone from a local commit or GO.

## Startup Reading Order

A fresh task reads, in order:

1. `AGENTS.md`
2. `PRODUCT.md`
3. `PROJECT_STATE.md`
4. `NEXT_TASK.md`
5. the code and documents relevant to the one task

Read the `CHANGELOG.md` Unreleased section or specific `DECISIONS.md` entries only
when the task needs that history. `PROJECT_MEMORY.md`, full decision history, and the
full changelog are references, not mandatory startup reading.

## Evidence And Handoffs

- `PROJECT_STATE.md` contains current facts, not a diary.
- `NEXT_TASK.md` contains exactly one executable next action.
- `PROJECT_MEMORY.md` is a compact durable-contract snapshot.
- `DECISIONS.md` is append-only rationale; supersede through a new decision.
- `CHANGELOG.md` records only changes that exist.
- Reports identify baseline, exact SHA/range, paths, commands, results, Git status,
  residual risks, and the next gate.

Documentation must distinguish implemented V1 behavior, accepted V2 direction, and
future V2 contracts. Historical handoffs route investigation but never replace live
Git, code, test, rights, or acceptance evidence.

## Public And Private Work

Public workstreams may use generic fixtures and original samples only. Private source,
canon, derived adaptation content, images, and reports remain in owner-controlled
external workspaces unless a task has exact access authorization. Public commits may
define generic contracts for private workflows but cannot contain private facts,
names, paths, hashes that reveal content, or derived assets.
