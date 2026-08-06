# Lore2MUD Current Code Map

_Baseline: accepted V2-2 tree integrated by candidate
`c37969f6b6958e66474738f88a53b9d5c2f50d99`, 2026-08-06. V2-3 implementation is
explicitly authorized after planning-Goal review but has not started._

This map describes the accepted V2-2 tree and the exact integration candidate currently
under Draft PR review. `World` remains the authoritative V1 gameplay implementation;
the V2-1 application contracts remain below both player clients, and the V2-2 authoring
service builds fixed-profile previews and isolated evidence over that same runtime.
V2-3 will add an engine-shipped static capability catalog and namespaced runtime through
new `src/lore2mud/capabilities/` ownership. Package sealing, workbench UI, and MCP remain
future work.

## Runtime Data Flow

```text
content directory
  -> src/lore2mud/content/loader.py::load_content_pack()
  -> src/lore2mud/content/models.py::ContentPack
  -> src/lore2mud/application/session.py::GameSession.from_content_pack()
  -> src/lore2mud/engine/world.py::World (authoritative state and rules)

CLI/Web parsing
  -> src/lore2mud/application/contracts.py::GameIntent
  -> GameSession.submit()
  -> World typed outcomes
  -> ordered immutable GameEvent + complete player-safe GameView
  -> TurnResult
  -> CLI/Web rendering
```

`load_content_pack()` validates the multi-file JSON pack and returns a shallow-frozen
`ContentPack`: dataclass fields cannot be reassigned, but collection mappings remain
mutable. `World` copies those definitions into mutable rooms, actors, inventory,
narrative state, quests, and optional runtime `campaign.json` state.

`GameSession` owns one compatibility `World`, immutable determinism inputs, an event
sequence, a save boundary, and a lock around one turn. It validates typed intents,
rolls back authority on contract rejection, translates existing typed `World`
outcomes into immutable event payloads, and creates the current safe projection.
`World` remains the only gameplay authority; events are result facts, not a second
event-sourced state.

`SaveLoadService` in `src/lore2mud/engine/save.py` still serializes and validates the
current `World`, writes save v9 atomically, and reconstructs a replacement `World`
against the same `ContentPack`. V2-1 changes no save or content format.

## Application Contracts

- `src/lore2mud/application/contracts.py`: frozen Enums/dataclasses for the closed
  current intent set, typed event payloads, safe view values, rejection diagnostics,
  determinism context, and `TurnResult`.
- `src/lore2mud/application/session.py`: one deterministic turn, validation,
  transaction snapshot/restore, save/load integration, event ordering, and adapters
  from existing `World` outcomes.
- `src/lore2mud/application/projection.py`: detached `World -> GameView` projection.
  Hidden campaign state and unavailable actions are absent. Concrete V1 UI
  affordances are checked only on isolated `World` copies; no public general
  admissible-intent catalog is introduced.
- `src/lore2mud/application/__init__.py`: public V2-1 runtime exports.

## Authoring Contracts

```text
approved GameBlueprint v1 + public-safe inputs + bounded V1 content snapshot
  -> GameProject v1 normalization and build lock
  -> fixed lore2mud.v1.compatibility.fixed PreviewBuild v1
  -> fresh ContentPack + SaveLoadService + GameSession per evidence run
  -> SimulationReport v1 / read-only ProofingProjection v1
  -> shared AuthoringResult v1
  -> AgentAuthoringSDK / structured author CLI
```

- `src/lore2mud/authoring/contracts.py`: frozen V2-2 blueprint, project,
  diagnostics, preview, request/report, descriptor, proofing, and result values.
- `src/lore2mud/authoring/project.py`: bounded public input capture, typed canonical
  round trips, canonical V1 content snapshots, validation, build locks, and capability
  rejection.
- `src/lore2mud/authoring/preview.py`: current-engine, fixed-profile,
  non-distributable preview construction and validation.
- `src/lore2mud/authoring/simulation.py`: bounded typed project/report entry checks,
  isolated typed-intent simulation, state/view hashes, witness replay, conditions, and
  save/load checkpoint evidence.
- `src/lore2mud/authoring/proofing.py`: bounded read-only nodes, edges, and concrete
  admissible intents derived only from a detached player-safe `GameView`.
- `src/lore2mud/authoring/serialization.py`: canonical JSON, hashes, stable ordering,
  and typed artifact/result documents.
- `src/lore2mud/authoring/service.py`: the single application implementation called
  by `AgentAuthoringSDK` and the structured CLI adapter.

## Client Composition

### CLI

`src/lore2mud/cli.py` loads a `ContentPack`, creates `SaveLoadService` and
`GameSession`, and starts `CommandProcessor`. `CommandProcessor` retains its existing
constructor, `.world`, help, parser, and text rendering compatibility, but gameplay
handlers submit typed intents and render only from `TurnResult`/`GameView`.

The same entry point also owns argument parsing for `author create-project`,
`validate`, `preview`, `simulate`, `replay`, and `proof`. Those commands parse bounded
JSON and present canonical results, while all domain behavior remains in the shared
authoring service.

### Web

`src/lore2mud/web/server.py` still hosts one local
`src/lore2mud/web/app.py::PlayerSession`. The class is intentionally not renamed to
`GameSession`: it is now the Web parsing/JSON rendering adapter around the shared
application session. Responses expose `status`, ordered `events`, typed-safe `view`,
and minimal diagnostics while retaining the compatible `ok`, `event`, and `snapshot`
fields. `src/lore2mud/web/static/app.js` consumes projected affordance intents instead
of rebuilding movement, death, item, trade, dialogue, or campaign availability rules.

## Existing Pipeline Authoring Flow

```text
source chapters / reviewed facts (private when applicable)
  -> public pipeline validators and compilers
  -> CanonRegistry
  -> NarrativeModel v1
  -> RegistryCampaignPlan v1 + NarrativeModel v1
  -> CampaignSpec v1
```

`pipeline/narrative_model.py` and `pipeline/campaign.py` create deterministic,
canonical authoring artifacts with provenance. There is no materializer from
`CampaignSpec` to a runtime `ContentPack` or runtime `campaign.json`.
**CampaignSpec is not a runtime input.** The similarly named runtime campaign is an
optional V1 content-pack structure; the two contracts are not interchangeable.

`pipeline/forge.py` currently orchestrates only `inspection` and `adaptation` stages.
It is not the V2 build system and does not run NarrativeModel or CampaignSpec stages.

## Central Modules And Risks

Line counts are orientation for this candidate, not quality scores:

| File | Lines | Current responsibility | Remaining risk |
|---|---:|---|---|
| `src/lore2mud/content/loader.py` | 2648 | Parse, validate, cross-link content files. | Format changes remain monolithic. |
| `pipeline/campaign.py` | 2380 | Campaign authoring IR, validation, compiler, CLI. | Authoring types and implementation remain colocated. |
| `src/lore2mud/engine/world.py` | 2141 | Authoritative state and gameplay rules. | Compatibility facade remains large. |
| `pipeline/forge.py` | 1409 | V1 inspection/adaptation workspace lifecycle. | Not yet the V2 workbench. |
| `src/lore2mud/engine/save.py` | 1126 | Save v9, v7/v8 read gates, reconstruction. | State evolution remains coupled to save core. |
| `src/lore2mud/engine/commands.py` | 1094 | CLI parsing and `TurnResult` text rendering. | Legacy routing compatibility remains broad. |
| `src/lore2mud/application/contracts.py` | 750 | Typed V2-1 request/result/view/event values. | Current closed action set is V1-specific. |
| `src/lore2mud/authoring/simulation.py` | 958 | Isolated simulation, replay, hashes, and checkpoints. | Evidence is V2-2 reproducibility proof, not release identity. |
| `src/lore2mud/authoring/project.py` | 823 | Blueprint/project normalization and bounded content capture. | Fixed V1 file set only; no V2 capability resolver. |
| `src/lore2mud/application/session.py` | 794 | Turn coordination and transaction boundary. | Rejection snapshots restore the existing World object graph in place. |
| `src/lore2mud/authoring/structured_cli.py` | 696 | Bounded structured transport and atomic output. | Intentionally thin; service parity must remain tested. |
| `src/lore2mud/authoring/serialization.py` | 730 | Canonical authoring documents, bounded in-memory traversal, and typed loaders. | Public JSON shapes must remain aligned with Schemas and result envelopes. |
| `src/lore2mud/web/app.py` | 624 | Web parsing and JSON compatibility rendering. | Legacy and V2 response shapes coexist. |
| `src/lore2mud/application/projection.py` | 531 | Safe projection and concrete affordances. | Affordance probes copy and execute V1 rules. |
| `src/lore2mud/content/models.py` | 470 | Frozen content definitions. | One aggregate spans optional gameplay domains. |
| `src/lore2mud/authoring/contracts.py` | 326 | Frozen V2-2 public authoring values. | V2-3/V2-4 contracts must not be folded into v1 formats. |
| `src/lore2mud/authoring/proofing.py` | 305 | Player-safe proofing and admissible descriptors. | Initial-view projection only; no workbench state. |
| `src/lore2mud/authoring/preview.py` | 315 | Fixed-profile preview construction and loading. | Current engine version only; never distributable. |

## Where Future Changes Go

| Change | Target ownership |
|---|---|
| Shared CLI/Web turn semantics | Existing V2-1 application/session layer. |
| Creator intent and game requirements | Existing V2-2 `GameBlueprint v1` contract. |
| Normalized build workspace and trace | Existing V2-2 `GameProject v1` contract. |
| Runtime distribution | Future `GamePackage v2`, not `CampaignSpec`. |
| General admissible-intent/tooling descriptions | Existing V2-2 proofing projection, not the V2-1 player view. |
| New gameplay domain | V2-3 capability module with namespaced state and migrations. |
| Backward-compatible V1 behavior | `World` compatibility authority and adapters. |
| Save evolution | Later session/package state contract plus explicit migrations. |
| New client | Consume `GameIntent` and `TurnResult`; do not call `World` rules directly. |
| Agent integration | Existing Python SDK and structured CLI; MCP remains later scope. |
| Novel provenance and rights | Authoring-plane manifests and traced/sealed gates. |

## Navigation

- `src/lore2mud/application/` - V2-1 public runtime boundary.
- `src/lore2mud/authoring/` - V2-2 contracts, service, preview, simulation, proofing,
  SDK, structured CLI, and canonical serialization.
- `src/lore2mud/capabilities/` - planned V2-3 ownership for descriptor contracts,
  SemVer, static catalog, deterministic resolution, namespaced runtime, and checkpoints;
  the directory does not exist in the planning candidate.
- `src/lore2mud/content/models.py` - `ContentPack` and frozen V1 definitions.
- `src/lore2mud/content/loader.py` - public content validation authority.
- `src/lore2mud/engine/world.py` - gameplay and mutable-state authority.
- `src/lore2mud/engine/commands.py` - CLI parser and renderer adapter.
- `src/lore2mud/engine/save.py` - save v9 and legacy compatibility.
- `src/lore2mud/web/app.py` - Web parser/renderer compatibility adapter.
- `src/lore2mud/cli.py` / `src/lore2mud/web/server.py` - transport entry points.
- `pipeline/narrative_model.py` / `pipeline/campaign.py` - authoring IR compilers.
- `pipeline/forge.py` - current resumable authoring workspace.
- `docs/v2/authoring_interface.md` - V2-2 formats, identities, limits, and commands.
- `tests/test_authoring_*.py` - V2-2 contracts, determinism, privacy, parity, and
  isolation evidence.
- `tests/test_game_session.py` - contract, invariance, and safe-view evidence.
- `tests/test_transport_equivalence.py` - real CLI/Web parity and save evidence.
- `schemas/` / `docs/*_format.md` - V1 data contracts.
