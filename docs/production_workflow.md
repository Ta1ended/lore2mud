# Lore2MUD Production Workflow

## Purpose

This workflow turns product-owner direction into bounded, evidence-backed changes.
Lore2MUD is an Agent-callable engine; the developer Agent is the direct user, the
owner/creator decides what should exist, and the player receives the finished game.

## Start A Task

Read `AGENTS.md`, `PRODUCT.md`, `PROJECT_STATE.md`, `NEXT_TASK.md`, then the relevant
code/tests/docs. Read only task-relevant history. Verify the live branch, baseline,
status, ancestry when relevant, and exact next gate.

Before edits, report:

- current data flow and authority;
- one authorized outcome and its acceptance criteria;
- exact changed-path boundary and explicit non-goals;
- compatibility, product, rights, and security risks;
- focused and full verification plan.

If the required `gpt-5.6-sol` model at `xhigh` or higher is unavailable for an
implementation, architecture, or acceptance task/subagent, stop and report. Never
silently downgrade.

## Deliver A Workstream

1. Create or use an isolated worktree and branch at the verified baseline. Shared
   `main` stays read-only.
2. Implement one coherent slice using existing project patterns. Keep clients thin,
   state transitions authoritative, and failed operations mutation-free.
3. Add focused failure/invariance coverage and update every affected data contract.
4. Run focused checks, then the risk-appropriate full matrix. Keep caches, saves,
   artifacts, and dependency environments outside the checkout.
5. Update current handoffs once, after evidence exists. Append decisions; do not edit
   history to manufacture consistency.
6. Audit changed paths, commit locally, and stop at the authorized gate.

## Three Passes

### TECH PASS

Fresh read-only review of an exact commit/range. It checks scope, implementation,
contracts, compatibility, determinism, tests, quality, and evidence. Findings are
ordered P0-P3 and end with GO or REVISE. The implementation context cannot grant it.

### PRODUCT PASS

The product owner confirms the workflow, language, creative boundary, success metric,
and player experience meet the intended outcome. Green tests do not grant this pass.

### SECURITY PASS

Review untrusted inputs, private-data and rights boundaries, capabilities, package
contents, dependency/artifact provenance, client exposure, save paths, and release
conditions. A generic safety scan is evidence, not the whole pass.

Each milestone states which passes are required. No pass implies another.

## Controller And Integration

The controller owns workstream boundaries, dependency order, conflict resolution,
candidate composition, and gate routing. It integrates only accepted inputs and does
not add new product scope during a seal.

These are distinct authorization points:

1. local branch commit;
2. push branch/ref;
3. update local or remote `main`;
4. publish a release.

A GO, merge candidate, or local `main` state authorizes none of the later points by
itself. Recheck live refs and security evidence immediately before publish/release.

## Default Technical Matrix

Choose focused tests for the slice and run the full matrix for shared/runtime,
integration, or release-sensitive changes:

```powershell
python -m unittest discover -s tests -v
python -m pytest -q
python -m ruff check .
python -m pyright
python -m compileall -q src pipeline scripts tests
python -m lore2mud validate --content examples/original_demo
python scripts/check_repo_safety.py --history
git fsck --full --no-dangling
git diff --check
```

Also run direct Draft 2020-12 validation, external CLI/Web/save flows, deterministic
golden checks, packaging, or artifact byte/hash comparison when the change touches
those contracts. Treat a missing optional test dependency as a harness issue until
reproduced in the declared environment.

## V2 Contract Discipline

- Authoring outputs do not become runtime inputs without an explicit materializer and
  package validation.
- `CampaignSpec` remains authoring IR; it is not a `GamePackage`.
- SDK and structured CLI are the first Agent surfaces. MCP is a later adapter.
- `World` stays a compatibility facade while `GameSession` becomes the shared CLI/Web
  application boundary.
- Capability packages are static data selected from an engine catalog. Dynamic code
  and plugin execution are forbidden initially.
- Preserve V1 public content and supported save compatibility unless a separately
  approved migration says otherwise.

## Handoff And Resume

At a durable checkpoint, reconcile `PROJECT_STATE.md`, `PROJECT_MEMORY.md`,
`NEXT_TASK.md`, `CHANGELOG.md`, and any new append-only decision. Current snapshots
must not carry completed tasks, old publish claims, or acceptance the task cannot grant.

A fresh session should resume from the concise startup order without replaying the
full history. Historical records are routing aids; live repository evidence decides.
