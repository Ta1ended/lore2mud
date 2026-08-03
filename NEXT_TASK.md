# Next Task

_Last updated: 2026-08-03_

## Single Next Action

**V2-1: design and implement a transport-neutral GameSession contract that wraps the
existing World without splitting gameplay systems.**

This task is routed but not started. Before editing, a fresh V2-1 task must inspect
live `main` and use actual Git history to locate and resolve the full SHA of the V2-0
seal commit (expected subject: `docs: seal v2 product and architecture reset`). It
must then verify from live controller/remote evidence that this exact seal SHA received
a fresh independent seal GO and that post-main Actions are green. DEC-0088 records the
earlier V2-0 TECH and PRODUCT gates; it does not by itself prove seal review or
publication. If any exact evidence is absent or live `main` differs from the verified
seal state, stop and report instead of working from a stale baseline. After those
checks, state the concrete changed-path boundary, data flow, risks, non-goals, and gate
plan before editing.

## Scope

- Introduce the smallest typed, transport-neutral session/application boundary around
  the existing authoritative `World`.
- Define deterministic intent, result, event, and player-safe view values only as
  needed by that boundary; invalid intents must reject before durable mutation.
- Route CLI and Web turn behavior through the shared session layer while preserving
  their transport-specific parsing and rendering.
- Preserve V1 public content, save v9 plus supported v7/v8 reads, runtime campaign
  behavior, deterministic outcomes, and existing client-visible behavior.
- Add focused contract, failure-invariance, CLI, Web, content, and save regressions,
  then run the repository's required full TECH and safety matrix.

## Non-Goals

- Do not implement `CapabilityDescriptor`, capability modularization, or capability
  state migration.
- Do not add a Python SDK, structured SDK surface, MCP adapter, dynamic plugin system,
  generated code, or new dependency/framework.
- Do not create a new Demo or access, adapt, inspect, or publish private material.
- Do not perform a wholesale `World` decomposition, rewrite gameplay systems, change
  content/save versions, begin V2-2, push, move `main`, release, or publish.

## Acceptance And Gates

- CLI and Web share one application/session layer; neither gains new gameplay rules,
  and `World` remains the authoritative compatibility implementation.
- The same content, state, clock/seed inputs, and intent sequence produce equivalent
  results, events, views, and saved state across transports.
- Existing public content and supported saves do not regress; failed intents leave
  authoritative state unchanged.
- Every implementation, architecture, and acceptance task/subagent must explicitly
  use `gpt-5.6-sol` with reasoning `xhigh` or higher. Stop if unavailable; never
  silently downgrade.
- Implementation cannot self-approve. Obtain a fresh findings-first independent TECH
  decision for the exact commit/range, then keep PRODUCT and SECURITY decisions
  separate and owner-controlled. Commit, push, `main` movement, and release remain
  separate controller gates.
