# Lore2MUD V2 Roadmap

The milestone order is fixed by product direction. A milestone starts only after the
prior exit is evidenced and the product owner authorizes the next scope. Each adopted
pattern belongs to one owning milestone; a later contract must not leak into an
earlier implementation slice.

See [Reference Patterns](reference_patterns.md) for the cross-project lessons adopted,
deferred, or rejected by this roadmap.

## V2-0 Direction Reset

CI green, product definition, architecture RFC, code map, development model.

**Exit:** project entry is clear, current state is consistent, and the product owner
approves the product and architecture boundaries.

## V2-1 Public Runtime Boundary

`GameSession` / `GameIntent` / `GameEvent` / `GameView` / `TurnResult`.

### Adopted Patterns

- Fix the authoritative client flow as:

  ```text
  CLI/Web parsing -> GameIntent -> GameSession -> TurnResult -> transport rendering
  ```

- Keep `World` as the authoritative V1 compatibility implementation. CLI and Web own
  parsing/rendering only and cannot add gameplay rules.
- Treat `GameIntent` as a typed request for an existing action, not a plugin payload,
  direct state patch, or executable extension.
- Treat `GameEvent` as an ordered immutable transition fact, not an event bus or a
  second event-sourced authority.
- Make `GameView` the complete player-safe projection. Hidden state and unavailable
  actions are absent rather than emitted with hidden flags.
- Return one `TurnResult` containing contract status, ordered events, the current
  view, and minimal typed runtime rejection details.
- Distinguish a contract-rejected intent from an accepted action with an unsuccessful
  in-world outcome. Existing `World` gameplay semantics remain authoritative.

### Non-Goals

- No `CapabilityDescriptor`, capability catalog/resolution, SDK, structured CLI, MCP,
  plugin system, generated code, or dependency/framework migration.
- No `SimulationReport`, general admissible-intent authoring interface, proofing model,
  state migration, new save/content version, `World` decomposition, or new Demo.
- No private-material access and no V2-2 implementation.

### Acceptance Evidence

- Identical content/package, authoritative state, clock, seed, and intent sequence
  produce equivalent `status`, ordered events, player-safe view, and saved state in
  CLI and Web flows.
- A malformed, inadmissible, or otherwise contract-rejected intent produces no
  transition events. Canonical durable authoritative state is identical before and
  after rejection, including gameplay state, RNG position, clock, event sequence, and
  save-visible metadata.
- Accepted actions may retain deterministic unsuccessful in-world outcomes where V1
  behavior requires them.
- Existing public content, save v9 writes, supported v7/v8 reads, and client-visible
  behavior do not regress.

**Exit:** CLI and Web share one application/session layer; rejection invariance and
transport equivalence are demonstrated; old content and saves do not regress.

## V2-2 Agent Authoring Interface

`GameBlueprint v1`, `GameProject v1`, `AuthoringDiagnostic v1`, unsealed preview
builds, `SimulationReport v1`, Python SDK, and structured CLI.

### Adopted Patterns

- Return machine-readable diagnostics with stage, stable code, severity, artifact ID,
  JSON Pointer, optional authorized source span, message, and remediation hint.
- Make the Python SDK and structured CLI call the same implementation and return
  semantically equivalent results and diagnostics.
- Produce an unsealed, non-distributable preview build for isolated validation and
  simulation. Preview output is not a `GamePackage v2` and is never release evidence.
- Record `SimulationReport v1` evidence: authoring-input and preview/runtime-input
  hashes, engine version, seed/clock, initial/final authoritative-state hashes, each
  intent and its accepted/rejected status, event types, view hashes, win/loss
  conditions, replayable witness trace, and save/load checkpoint equivalence.
- Expose bounded player-safe admissible-intent descriptors for authoring and
  simulation tools without revealing hidden actions, hidden IDs, private source, or
  privileged conditions.
- Provide a read-only proofing projection. Graph layout, folding, zoom, selection,
  caches, and other UI metadata cannot affect normalized preview inputs or deterministic
  report fingerprints. These V2-2 fingerprints are not package identity or release
  evidence.
- Allow blueprints/projects to record syntactically validated capability requirement
  IDs only. Catalog lookup and semantic capability resolution belong to V2-3.
- Build V2-2 previews only with one engine-defined V1 compatibility profile backed by
  current `World` behavior. The profile is not package-selectable and is not a catalog.
  Any declared V2 capability requirement produces a stable diagnostic and blocks preview
  build and simulation until V2-3; it is never ignored or resolved early.

### Non-Goals

- No static-catalog resolution, capability dependency/conflict evaluation, namespace
  ownership, capability migrations, sealing, distribution, release evidence, or MCP.
- No workbench UI, runtime plugin host, generated executable code, or live-session
  mutation by authoring tools.

### Acceptance Evidence

- A fresh Agent can initialize a project that declares no V2 capability requirements,
  build a preview against the fixed V1 compatibility profile, validate, simulate, and
  explain diagnostics without reading or modifying `src/`.
- A project that declares any V2 capability requirement is rejected with the same
  stable diagnostic by the SDK and structured CLI before preview construction.
- SDK and structured CLI produce equivalent normalized artifacts, diagnostics, exit
  meaning, and simulation evidence for the same inputs.
- Simulation advances only an isolated session copy and cannot mutate the caller's
  project, source artifacts, preview bytes, or live player session.
- Public exports contain no raw private excerpts, absolute private paths, private
  source hashes, or identifiers that reveal private content.

**Exit:** a fresh Agent can build, validate, and simulate a fixed-profile V1-compatible
project through published contracts without reading or modifying `src`; unsupported V2
capability requirements reject deterministically, and preview evidence is reproducible.

## V2-3 Capability Module Architecture

`CapabilityDescriptor`, engine-shipped static catalog, state namespaces,
predicates/effects/events/views, dependency resolution, and explicit migrations.

### Adopted Patterns

- Define stable ID, semantic version, safety level, owned state namespace, initial
  schema, accepted intents, dependencies, conflicts, predicates, deterministic
  effects, events, player-safe views, and explicit migration declarations.
- Resolve package/project requirements deterministically against the engine-shipped
  catalog before session construction. The result is an ordered exact-version plan.
- Reject missing or ambiguous requirements, version conflicts, dependency cycles,
  namespace overlap, illegal safety levels, and migration-incompatible state before
  authoritative mutation.
- Packages select catalog capability IDs/versions only. They cannot contain code,
  import paths, Python hooks, script languages, native modules, Git submodules, or
  dynamically loaded plugins.

### Non-Goals

- No package-provided capabilities, dynamic marketplace, arbitrary host I/O, runtime
  model adjudication, multiplayer scope, or wholesale `World` rewrite.
- Planning an explicit migration contract does not require a save-version bump in the
  first capability slice; unsupported version changes may be rejected instead.

### Acceptance Evidence

- Session construction fails before state creation for every invalid capability set.
- The same catalog and requirement set always produce the same ordered resolution.
- A reference gameplay capability can be added without modifying `World`, save core,
  or client routing.
- Capability behavior is deterministic and confined to its declared namespace and
  safety policy.

**Exit:** the reference capability passes resolution, runtime, save/load, safety, and
client regressions without changes to `World`, save core, or client routing.

## V2-4 Novel Adaptation V2

prototype / traced / sealed modes, provenance and rights manifest, canonical package
identity, and incremental story content.

### Adopted Patterns

- Trace every material story element through:

  ```text
  source reference -> rights assertion -> creator decision -> transformation
  -> GameProject element -> sealed package element
  ```

- Reserve `GamePackage v2` for canonical sealed bytes. A sealed build is never
  regenerated or replaced in place; any change creates a new candidate identity.
- Define canonical package identity and a separate canonical evidence-manifest identity
  when sealing. V2-2 report fingerprints may be admitted as traceable evidence, but
  neither they nor a V2-4A sealed candidate are release evidence or distribution
  authorization; those gates remain external.
- Use opaque stable story, scene, and resume anchors plus explicit anchor migration
  records for incremental content. Anchors must not expose private source paths or
  raw text.
- Permit deterministic branching and progressive disclosure only within the approved
  `GameBlueprint` narrative, adaptation, rights, and player-safe projection
  constraints. Runtime or Agent output cannot invent source facts or bypass
  owner-approved disclosure constraints.
- Keep storylet scheduling and fact-consumption semantics as research references only.

### Non-Goals

- No storylet runtime/scheduler, dynamic canon rewriting, hidden-source disclosure,
  in-place resealing, or automatic migration of unsupported package/save versions.
- No global rule that forbids creator-approved alternate routes, endings, or disclosure
  order.

### Acceptance Evidence

- One public-safe story arc produces a traceable 30-60 minute game whose material
  elements resolve through the complete trace chain.
- Rebuilding identical sealed inputs yields identical package and evidence identities;
  changing a semantic input yields a new candidate.
- Incremental content preserves or explicitly migrates every referenced anchor and
  rejects unresolved migrations before sealing.
- Rights, provenance, and privacy checks pass without exposing private source material.

**Exit:** one public-safe story arc yields a deterministic, traceable, sealed game with
reviewable adaptation decisions and stable incremental anchors.

The V2-4A local contract candidate is specified in
[Novel Adaptation Contracts](novel_adaptation_contracts.md). It is not an exit claim,
publication decision, or authorization to begin V2-5.

## V2-5 Alpha Workbench

Nontechnical workbench, asset/rights status, local proofing and playtest, external
playtests, packaging, and security audit.

### Adopted Patterns

- Provide synchronized text and graph views, referenced diagnostics, local proofing,
  bounded local playtest, and visible asset/rights status.
- Build the workbench as a client of V2-2 SDK/application services. It cannot own a
  second compiler, validator, simulation engine, or runtime rule set.
- Keep graph coordinates, pane state, folding, zoom, selection, caches, and proofing
  presentation metadata outside the V2-4 package and evidence-manifest identities. V2-5
  enforces this existing boundary; it does not define a second identity contract.
- Enforce the V2-4 rule that shipped assets and runtime-affecting data affect package
  identity. Diagnostics, traces, and reports enter the V2-4 evidence manifest only
  through its admission contract; workbench metadata remains workspace-only.
- Require validate, simulate, and seal gates before distribution. The workbench cannot
  directly patch a live `GameSession` or bypass those gates.

### Non-Goals

- No collaborative multiplayer authoring/runtime, database-first content authority,
  dynamic plugin marketplace, or alternate workbench-only package format in V2 Alpha.

### Acceptance Evidence

- Workbench and structured CLI produce equivalent build, validation, simulation, and
  sealing results for the same project inputs.
- UI-only edits leave the V2-4 package and evidence-manifest identities unchanged;
  runtime-affecting edits change package identity under the V2-4 contract.
- Three to five external users or Agents independently complete different-genre
  projects, and players can finish the resulting games.

**Exit:** external creators can complete and prove different-genre projects through one
shared toolchain; packaging and security audits pass.

## PLAT-1 Platform Thread

A fresh Agent, from public-safe material plus an approved `GameBlueprint`, makes no
core changes and creates a deterministic 20-30 minute game with build, validate,
simulate, Web, and save/load evidence.

The technical first path uses the existing public `urban_investigation` family. The
product sample is a new original investigation. Cultivation is the second genre.

PLAT-1 is developed incrementally across V2-1 through V2-5. V2-2 may prove only the
fixed-profile preview build/validate/simulate portion; V2-4 owns sealed package and
evidence-manifest identity; V2-5 owns independent nontechnical workflow evidence and
workbench parity enforcement. No milestone may claim complete platform acceptance
before the full scenario passes independently.
