# Lore2MUD Current Code Map

_Baseline: V2-1 local candidate based on
`1d4b26d9127d4229893911cf260cf3c2f4b0ce3a`, 2026-08-04_

This map describes the current isolated candidate. `World` remains the authoritative
V1 gameplay implementation; the V2-1 application contracts now exist below both
clients. Later V2 authoring, package, capability, SDK, diagnostics, simulation,
proofing, and MCP contracts remain future work.

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

## Client Composition

### CLI

`src/lore2mud/cli.py` loads a `ContentPack`, creates `SaveLoadService` and
`GameSession`, and starts `CommandProcessor`. `CommandProcessor` retains its existing
constructor, `.world`, help, parser, and text rendering compatibility, but gameplay
handlers submit typed intents and render only from `TurnResult`/`GameView`.

### Web

`src/lore2mud/web/server.py` still hosts one local
`src/lore2mud/web/app.py::PlayerSession`. The class is intentionally not renamed to
`GameSession`: it is now the Web parsing/JSON rendering adapter around the shared
application session. Responses expose `status`, ordered `events`, typed-safe `view`,
and minimal diagnostics while retaining the compatible `ok`, `event`, and `snapshot`
fields. `src/lore2mud/web/static/app.js` consumes projected affordance intents instead
of rebuilding movement, death, item, trade, dialogue, or campaign availability rules.

## Authoring Data Flow

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
| `src/lore2mud/content/loader.py` | 2633 | Parse, validate, cross-link content files. | Format changes remain monolithic. |
| `pipeline/campaign.py` | 2380 | Campaign authoring IR, validation, compiler, CLI. | Authoring types and implementation remain colocated. |
| `src/lore2mud/engine/world.py` | 2141 | Authoritative state and gameplay rules. | Compatibility facade remains large. |
| `pipeline/forge.py` | 1409 | V1 inspection/adaptation workspace lifecycle. | Not yet the V2 workbench. |
| `src/lore2mud/engine/save.py` | 1110 | Save v9, v7/v8 read gates, reconstruction. | State evolution remains coupled to save core. |
| `src/lore2mud/engine/commands.py` | 1094 | CLI parsing and `TurnResult` text rendering. | Legacy routing compatibility remains broad. |
| `src/lore2mud/application/contracts.py` | 750 | Typed V2-1 request/result/view/event values. | Current closed action set is V1-specific. |
| `src/lore2mud/application/session.py` | 749 | Turn coordination and transaction boundary. | Projection rollback uses whole-World copies. |
| `src/lore2mud/web/app.py` | 624 | Web parsing and JSON compatibility rendering. | Legacy and V2 response shapes coexist. |
| `src/lore2mud/application/projection.py` | 531 | Safe projection and concrete affordances. | Affordance probes copy and execute V1 rules. |
| `src/lore2mud/content/models.py` | 470 | Frozen content definitions. | One aggregate spans optional gameplay domains. |

## Where Future Changes Go

| Change | Target ownership |
|---|---|
| Shared CLI/Web turn semantics | Existing V2-1 application/session layer. |
| Creator intent and game requirements | Future `GameBlueprint v1` authoring contract. |
| Normalized build workspace and trace | Future `GameProject v1` authoring contract. |
| Runtime distribution | Future `GamePackage v2`, not `CampaignSpec`. |
| General admissible-intent/tooling descriptions | V2-2, not the V2-1 player view. |
| New gameplay domain | V2-3 capability module with namespaced state and migrations. |
| Backward-compatible V1 behavior | `World` compatibility authority and adapters. |
| Save evolution | Later session/package state contract plus explicit migrations. |
| New client | Consume `GameIntent` and `TurnResult`; do not call `World` rules directly. |
| Agent integration | Python SDK and structured CLI first; MCP only after stabilization. |
| Novel provenance and rights | Authoring-plane manifests and traced/sealed gates. |

## Navigation

- `src/lore2mud/application/` - V2-1 public runtime boundary.
- `src/lore2mud/content/models.py` - `ContentPack` and frozen V1 definitions.
- `src/lore2mud/content/loader.py` - public content validation authority.
- `src/lore2mud/engine/world.py` - gameplay and mutable-state authority.
- `src/lore2mud/engine/commands.py` - CLI parser and renderer adapter.
- `src/lore2mud/engine/save.py` - save v9 and legacy compatibility.
- `src/lore2mud/web/app.py` - Web parser/renderer compatibility adapter.
- `src/lore2mud/cli.py` / `src/lore2mud/web/server.py` - transport entry points.
- `pipeline/narrative_model.py` / `pipeline/campaign.py` - authoring IR compilers.
- `pipeline/forge.py` - current resumable authoring workspace.
- `tests/test_game_session.py` - contract, invariance, and safe-view evidence.
- `tests/test_transport_equivalence.py` - real CLI/Web parity and save evidence.
- `schemas/` / `docs/*_format.md` - V1 data contracts.
