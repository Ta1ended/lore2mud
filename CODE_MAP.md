# Lore2MUD Current Code Map

_Baseline: public `main` `1a5a8857579ebf840de4e39e414b52592baea6ba`, 2026-08-03_

This map describes the current V1 implementation. Names defined in the V2 target
documents do not exist yet unless this file says otherwise.

## Runtime Data Flow

```text
content directory
  -> src/lore2mud/content/loader.py::load_content_pack()
  -> src/lore2mud/content/models.py::ContentPack
  -> src/lore2mud/engine/world.py::World.from_content_pack()
  -> World (authoritative mutable state and rules)
  -> src/lore2mud/engine/commands.py::CommandProcessor.execute()
  -> CommandResult text
```

`load_content_pack()` reads the multi-file JSON pack, performs schema-like type and
cross-reference validation, and returns an immutable `ContentPack`. `World` copies
those definitions into mutable rooms, actors, inventory, narrative state, quests,
and optional runtime `campaign.json` state. `CommandProcessor` owns text command
routing and rendering but delegates rule decisions to `World`.

`SaveLoadService` in `src/lore2mud/engine/save.py` serializes and validates the
current `World`, writes save v9 atomically, and reconstructs a replacement `World`
against the same `ContentPack`. Save compatibility is therefore coupled to both the
runtime model and content-pack version.

## Client Composition

### CLI

`src/lore2mud/cli.py` loads a `ContentPack`, creates `World`, `SaveLoadService`, and
`CommandProcessor`, then runs a text loop. The `validate` path calls the same loader.
The CLI is thin at startup, but `CommandProcessor` contains client-specific parsing,
help, and result rendering.

### Web

`src/lore2mud/web/server.py` loads the content pack and hosts one local
`src/lore2mud/web/app.py::PlayerSession`. `PlayerSession.dispatch()` validates a
structured Web action, calls `World` directly or falls back to `CommandProcessor`,
then builds event dictionaries and a full snapshot.

`PlayerSession` is the closest current precursor to `GameSession`, `GameIntent`,
`GameEvent`, `GameView`, and `TurnResult`, but it is Web-owned, dictionary-shaped,
and duplicates application behavior and projection logic. V2-1 moves that contract
below both clients rather than renaming the Web class.

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
canonical authoring artifacts with provenance. There is currently no materializer
from `CampaignSpec` to a runtime `ContentPack` or runtime `campaign.json`.
**CampaignSpec is not a runtime input.** The similarly named runtime campaign is an
optional structure loaded from a content pack; the two contracts must not be
conflated.

`pipeline/forge.py` currently orchestrates only `inspection` and `adaptation` stages
over a controlled workspace. It provides useful patterns for fingerprints, immutable
outputs, resume, locks, validation, and rollback, but it is not the V2 build system
and does not run NarrativeModel or CampaignSpec stages today.

## Central Modules And Risks

Line counts at the baseline are orientation, not quality scores:

| File | Lines | Current responsibility | V2 risk |
|---|---:|---|---|
| `src/lore2mud/content/loader.py` | 2633 | Parse, validate, cross-link every content file. | Every format addition expands one monolithic loader. |
| `pipeline/campaign.py` | 2380 | Campaign plan/spec types, validation, compilation, CLI, writer. | Authoring contract and implementation are tightly colocated. |
| `src/lore2mud/engine/world.py` | 2141 | State, projection, predicates, transactions, and nearly all gameplay effects. | New capabilities require central edits and widen regression scope. |
| `pipeline/forge.py` | 1409 | Workspace lifecycle for inspection/adaptation. | Useful infrastructure is specialized to the V1 two-stage flow. |
| `src/lore2mud/engine/save.py` | 1110 | Save schema, validation, migration gates, atomic I/O, reconstruction. | Capability state additions couple directly to save core. |
| `src/lore2mud/engine/commands.py` | 978 | Command registry, parsing, execution adapters, help, rendering. | Runtime behavior is exposed through a text-first application boundary. |
| `src/lore2mud/web/app.py` | 555 | Web action validation, dispatch, events, snapshots. | Duplicates routing and projection outside a shared session layer. |
| `src/lore2mud/content/models.py` | 470 | Frozen content definitions, including `ContentPack`. | One aggregate carries all optional gameplay domains. |

The first V2 goal is not a wholesale rewrite. It is to introduce stable boundaries
around these modules while keeping them as compatibility implementations.

## Where Future Changes Go

| Change | Target ownership |
|---|---|
| Shared CLI/Web turn semantics | V2 application/session layer introduced in V2-1. |
| Creator intent and game requirements | `GameBlueprint v1` authoring contract. |
| Normalized build workspace and trace | `GameProject v1` authoring contract. |
| Runtime distribution | `GamePackage v2`, not `CampaignSpec`. |
| New gameplay domain | Capability module with `CapabilityDescriptor v1`, namespaced state, predicates, effects, views, and migrations. |
| Backward-compatible V1 behavior | `World` compatibility facade and explicit adapters. |
| Save evolution | Session/package state contract plus capability migrations; keep legacy loading isolated. |
| New client | Consume `GameIntent` and `TurnResult`; do not call `World` rules directly. |
| Agent integration | Python SDK and structured CLI first; MCP adapter only after contracts stabilize. |
| Novel provenance and rights | Authoring Plane manifests and traced/sealed promotion gates. |

## Navigation

- `src/lore2mud/content/models.py` - `ContentPack` and frozen V1 definitions.
- `src/lore2mud/content/loader.py` - public content entry and validation authority.
- `src/lore2mud/engine/world.py` - current runtime authority and future facade.
- `src/lore2mud/engine/commands.py` - current text command boundary.
- `src/lore2mud/engine/save.py` - save v9 and legacy compatibility.
- `src/lore2mud/web/app.py` - `PlayerSession` precursor.
- `src/lore2mud/cli.py` / `src/lore2mud/web/server.py` - current clients.
- `pipeline/narrative_model.py` / `pipeline/campaign.py` - authoring IR compilers.
- `pipeline/forge.py` - current resumable authoring workbench.
- `schemas/` / `docs/*_format.md` - V1 data contracts.
- `tests/` - current behavior and compatibility evidence.
