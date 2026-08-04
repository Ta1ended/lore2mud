# Lore2MUD V2 Reference Patterns

_Status: adopted planning guidance, not implemented API_

## Purpose And Evidence Boundary

This document maps patterns synthesized from product-owner-supplied external-project
research into the Lore2MUD roadmap. The source project list and primary evidence were
not supplied to this repository, so these are adopted design patterns, not claims that
Lore2MUD independently verified or copied a particular project.

The owning contracts remain [PRODUCT.md](../../PRODUCT.md),
[architecture.md](architecture.md), and [roadmap.md](roadmap.md). This document explains
why a pattern is adopted, deferred, or rejected and prevents later tasks from moving it
into the wrong milestone.

## Cross-Cutting Invariants

- Agent or model output may create authoring artifacts or submit a typed `GameIntent`.
  Only deterministic, source-controlled engine code mutates authoritative runtime
  state.
- Authoring, validation, simulation, proofing, and workbench operations produce
  artifacts/reports or use isolated session copies. They cannot patch a live session.
- Packages remain data-only. No package may provide code, import paths, hooks, scripts,
  native modules, subprocess access, unrestricted network access, or dynamic plugins.
- Player-safe projections omit hidden state, unavailable actions, private source,
  privileged diagnostics, and identifiers that reveal private content.
- Stable IDs and canonical semantic bytes define identity. Presentation metadata does
  not silently change project/package identity.
- The V2-0 through V2-5 roadmap does not authorize migration to Evennia, Ranvier,
  CoffeeMud, or another external MUD framework; multiplayer and database-first content
  authority are outside V2 Alpha scope.

## Adopted Patterns By Milestone

| Pattern | Owning milestone | Adoption rule |
|---|---|---|
| Transport-neutral application boundary | V2-1 | CLI/Web parse and render; `GameSession` alone coordinates authoritative turns. |
| Typed intent, ordered events, complete safe view | V2-1 | Intent is not extensibility; events are not a bus; hidden/unavailable data is absent. |
| Contract-rejection invariance | V2-1 | Rejected intents emit no transition events and preserve canonical authoritative state. |
| Stable machine-readable diagnostics | V2-2 | SDK and CLI share stage/code/severity/location/message/hint semantics. |
| Isolated deterministic simulation evidence | V2-2 | Preview builds and reports cannot mutate projects, candidates, or live sessions. |
| Player-safe admissible-intent descriptors | V2-2 | Tooling may expose bounded descriptors without hidden IDs or private conditions. |
| Read-only proofing projection | V2-2 | Semantic relationships are stable; graph/UI layout is nonsemantic workspace data. |
| Engine-shipped static capability catalog | V2-3 | Projects/packages declare requirements; the engine resolves exact safe versions. |
| Namespaced capability state and pre-session rejection | V2-3 | Invalid dependencies, conflicts, safety, namespace, or migration sets fail before state creation. |
| End-to-end adaptation trace chain | V2-4 | Source, rights, decisions, transformations, project elements, and sealed elements remain linked. |
| Canonical sealed identity and stable anchors | V2-4 | Sealed bytes are never replaced in place; incremental anchors migrate explicitly. |
| One compiler/runtime toolchain for the workbench | V2-5 | The UI consumes SDK/application services and cannot introduce alternate rules. |
| Semantic/UI hash separation | V2-4 and V2-5 | V2-4 defines package identity; V2-5 keeps presentation/workspace state outside it. |

## Interpretation Rules

### Contract Rejection Versus In-World Failure

A malformed, inadmissible, or otherwise contract-rejected `GameIntent` causes no
authoritative transition. An accepted engine action may still produce a deterministic
unsuccessful in-world result when existing gameplay rules require it. V2-1 must not
rewrite those V1 semantics merely to make every unsuccessful action a rejected intent.

### Preview Versus Sealed Package

V2-2 preview builds are unsealed, non-distributable inputs for isolated validation and
simulation. They are not release evidence and are not `GamePackage v2`. V2-4 owns
canonical package identity, sealing, provenance/rights closure, and promotion to a
distributable `GamePackage v2`.

### Narrative Choice Authority

Deterministic branching and progressive disclosure are allowed only when authorized by
the approved `GameBlueprint`. Capabilities, runtime logic, or model output may not
invent source facts, broaden rights/adaptation scope, expose private material, or
override owner-approved narrative constraints. The engine must not impose a global ban
on creator-approved alternate paths, endings, prerequisites, or disclosure order.

### Hash And Identity Boundary

- Semantic project/package identity includes runtime-affecting data, declared
  capabilities, shipped assets, canonical rules/configuration, and required rights or
  compatibility policy.
- Evidence identity may separately bind diagnostics, traces, reports, simulations, and
  release approvals.
- Workspace identity may include graph coordinates, panes, folding, zoom, selection,
  caches, and editor preferences. These values never affect semantic package hashes.

### Privacy-Safe Diagnostics And Trace

Authorized authoring workspaces may use source spans or private references internally.
Public diagnostics, simulation reports, proofing exports, player views, and sealed
package metadata omit raw private excerpts, absolute private paths, private source
hashes, and identifiers that reveal private content unless an exact owner-approved
export policy says otherwise.

## Deferred Research

- Storylet scheduling, fact-consumption semantics, and adaptive narrative selection are
  research references for V2-4 only. They do not authorize a storylet runtime,
  scheduler, or new dependency.
- Capability migrations are part of the V2-3 contract design. An initial implementation
  may reject unsupported versions instead of migrating them and does not imply a new
  save version.
- Controlled engine-owned I/O remains denied by default. Any later allowlist requires a
  separate security and product decision.
- Multiplayer runtime, collaborative authoring, and database-first content authority
  are outside V2 Alpha and require a later roadmap decision.

## Explicitly Rejected Alternatives

- Replatforming onto Evennia, Ranvier, CoffeeMud, or another MUD framework during the
  V2-0 through V2-5 roadmap.
- Package-provided or generated Python, import hooks, script languages, native modules,
  Git submodules, or dynamic plugin loading.
- Runtime model adjudication, model-written state patches, or model access to live
  authoritative state.
- An event bus or event-sourced rewrite inside V2-1.
- A workbench-only compiler, validator, simulation engine, package format, or bypass of
  validate/simulate/seal gates.
- Treating preview builds, proofing layouts, or simulation reports as sealed package
  identity or release evidence.
