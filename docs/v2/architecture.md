# Lore2MUD V2 Target Architecture

_Status: architecture direction, not implemented API_

## Two Planes

Lore2MUD V2 separates changeable, review-heavy authoring from deterministic play.

```text
Authoring Plane
source + creator decisions
  -> GameBlueprint v1
  -> GameProject v1
  -> validation / simulation / trace / rights gates
  -> GamePackage v2

Deterministic Runtime Plane
GamePackage v2 + GameIntent
  -> GameSession
  -> GameEvent[]
  -> GameView
  -> TurnResult
  -> CLI / Web / future clients
```

The Authoring Plane may call deterministic tools and model-assisted developer Agents.
It cannot write live game state. The Runtime Plane does not call a model to decide a
turn and does not execute authored code.

## Authoring Contracts

### GameBlueprint v1

Portable creator intent: product identity, audience, play-length target, story and
adaptation boundaries, required game loops, acceptance scenarios, capability needs,
asset needs, provenance requirements, rights assertions, and deterministic inputs.
It says what must be built without prescribing engine internals.

### GameProject v1

A normalized build workspace: approved blueprint, imported source references,
creator decisions, generated and reviewed material, stable IDs, capability
configuration, assets, trace records, validation state, and build lock. Mutable work
lives here; a project is not directly playable or distributable.

### GamePackage v2

The sealed runtime artifact: canonical game data, declared capability versions,
initial namespaced state, assets and hashes, compatibility metadata, and no private
source text unless the owner explicitly authorized it for that package. Packages are
data, never executable plugins.

### CapabilityDescriptor v1

The static contract for a gameplay capability:

- stable ID and semantic version;
- safety level and compatibility requirements;
- owned state namespace and initialization schema;
- accepted intent shapes;
- predicates, deterministic effects, events, and player-view projections;
- validation rules and explicit state migrations;
- declared dependencies and conflicts.

The descriptor is selected from an engine-shipped catalog. A package cannot inject
Python, import a module by path, or provide executable hooks.

## Runtime Contracts

- `GameSession`: owns one package-bound deterministic state, clock/seed inputs,
  event sequence, and save boundary.
- `GameIntent`: typed request from a player or client. It expresses intent, never a
  direct state patch.
- `GameEvent`: immutable ordered fact produced by accepted transitions. Events are
  internal/audit data and are filtered before player display.
- `GameView`: complete player-safe projection for the current turn; hidden state and
  unavailable actions are absent.
- `TurnResult`: accepted/rejected status, ordered `GameEvent` values, resulting
  `GameView`, and typed diagnostics suitable for SDK, CLI, and Web.

Given the same package, initial state, clock, seed, and intent sequence, the session
must produce the same events, views, and saved state.

## Compatibility Strategy

`World` remains a compatibility facade during migration. V2 adapters initially
translate typed intents to existing `World` operations and translate typed outcomes
to events/views. New clients call `GameSession`; they do not call `World` directly.
CLI and Web move to the shared application layer in V2-1 while V1 public content and
supported saves remain regression fixtures.

New capabilities must not accumulate new branches in `World`. V2-3 moves capability
state, predicates, effects, views, and migrations behind declared modules. Legacy
behavior may remain behind the facade until a compatibility exit is separately
approved.

## Authoring-To-Runtime Boundary

Existing `NarrativeModel v1` and `CampaignSpec v1` are useful authoring inputs.
`CampaignSpec` is not runtime content and cannot be passed to `GameSession`. A future
explicit materializer may translate validated authoring artifacts into a
`GameProject`, after which normal package validation and sealing still apply.

The current runtime `campaign.json` belongs to the V1 `ContentPack` contract. Similar
names do not imply compatibility with the pipeline `CampaignSpec`.

## Capability Safety Levels

| Level | Meaning | Initial policy |
|---|---|---|
| `L0 projection` | Read-only predicates and player-safe views. | Allowed from the static catalog. |
| `L1 deterministic` | Typed, namespaced gameplay state transitions with no host I/O. | Allowed after contract validation. |
| `L2 controlled I/O` | Explicit engine-owned services such as approved asset or storage access. | Denied by default; later allowlist only. |
| `L3 executable` | Dynamic code, native/plugin loading, process, shell, or unrestricted network access. | Forbidden. |

Safety level is part of the sealed package policy and cannot be raised at session
load time.

## Interfaces And Delivery Order

The first programmable surfaces are a typed Python SDK and structured CLI with JSON
input/output and stable exit/error contracts. The Web client consumes the same
application layer. MCP comes later as a thin adapter after the SDK and CLI contracts
have acceptance evidence; MCP is not the core product boundary.

## Invariants

- Validate structure, references, rights policy, capability policy, and assets before
  session creation.
- Reject a failed intent before durable state mutation; report typed diagnostics.
- Keep hidden data out of `GameView`, CLI output, Web payloads, and Agent-visible
  reports unless explicitly authorized.
- Use stable IDs, canonical serialization, content hashes, bounded inputs, and
  explicit migrations.
- No runtime model call, dynamic code, plugin execution, or implicit network access.
- Preserve the public/private boundary described in [PRODUCT.md](../../PRODUCT.md).
