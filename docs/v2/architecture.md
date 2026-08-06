# Lore2MUD V2 Target Architecture

_Status: V2-1 runtime contracts implemented in a local candidate; later V2 contracts
remain architecture direction and no publication is implied_

## Two Planes

Lore2MUD V2 separates changeable, review-heavy authoring from deterministic play.

```text
Authoring Plane
source + creator decisions
  -> GameBlueprint v1
  -> GameProject v1
  -> validation / isolated simulation with an unsealed preview build
  -> diagnostics / trace / rights / product / security gates
  -> seal (V2-4)
  -> GamePackage v2

Deterministic Runtime Plane
package-bound runtime input + GameIntent
  -> GameSession
  -> TurnResult { status, GameEvent[], GameView, diagnostics }
  -> CLI / Web / future clients
```

The Authoring Plane may call deterministic tools and model-assisted developer Agents.
It cannot write live game state. The Runtime Plane does not call a model to decide a
turn and does not execute authored code. V2-2 preview builds are unsealed,
non-distributable simulation inputs. V2-4 is responsible for sealing canonical bytes
as a distributable `GamePackage v2`.

## Authoring Contracts

### GameBlueprint v1

Portable creator intent: product identity, audience, play-length target, story and
adaptation boundaries, required game loops, acceptance scenarios, capability needs,
asset needs, provenance requirements, rights assertions, and deterministic inputs.
It says what must be built without prescribing engine internals.

### GameProject v1

A normalized build workspace: approved blueprint, imported source references,
creator decisions, generated and reviewed material, stable IDs, capability
requirements, assets, trace records, validation state, and build lock. Resolved
capability configuration begins in V2-3. Mutable work lives here; a project is not
directly playable or distributable.

### Preview Build

An unsealed runtime candidate derived from a `GameProject` for validation, isolated
simulation, and local proofing. It is non-distributable, cannot be treated as release
evidence, and cannot mutate the source project or any live player session. A later
change may produce a different preview without creating or replacing a sealed package.
Before V2-3, preview construction uses one engine-defined V1 compatibility profile that
is not package-selectable and is not a `CapabilityDescriptor` catalog. Any declared V2
capability requirement blocks preview construction and simulation with a stable
authoring diagnostic; it is never ignored or resolved early.

### AuthoringDiagnostic v1

A machine-readable authoring result shared by the Python SDK and structured CLI. Each
diagnostic records its stage, stable code, severity, artifact ID, JSON Pointer,
optional authorized source span, message, and remediation hint. Public or player-safe
exports omit raw private excerpts, absolute private paths, private source hashes, and
identifiers that reveal private content.

### SimulationReport v1

A deterministic evidence record for one isolated simulation: authoring-input and
preview/runtime-input hashes, engine version, seed and clock inputs, initial and final
authoritative-state hashes, each `GameIntent`, accepted/rejected status, event types,
view hashes, win/loss conditions, a replayable witness trace, and save/load checkpoint
equivalence. Reports are evidence artifacts, not semantic package content, and do not
by themselves prove PLAT-1 or a sealed release. V2-2 may define deterministic report
fingerprints, but V2-4 owns canonical package and evidence-manifest identity.

### Read-Only Proofing Projection

An authoring projection of stable story, scene, reference, diagnostic, and reachability
relationships. Graph coordinates, pane state, zoom, selection, folding, caches, and
other presentation metadata are workspace concerns. In V2-2 they cannot affect
normalized preview inputs or report fingerprints; V2-4 later defines canonical package
and evidence-manifest identity, and V2-5 enforces the exclusion in the workbench.

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
Python, import a module by path, or provide executable hooks. V2-2 projects may record
syntactically valid capability requirement IDs, but catalog lookup, version resolution,
dependency/conflict checks, namespace ownership, safety enforcement, and migration
dispatch begin in V2-3. Because V2-2 preview builds use only the fixed V1 compatibility
profile, any declared V2 capability requirement blocks preview construction rather than
being ignored or resolved early.

## Runtime Contracts

The V2-1 candidate implements this section in `src/lore2mud/application/`:
`contracts.py` defines frozen typed values, `session.py` coordinates one turn around
authoritative `World`, and `projection.py` builds the detached player-safe view. The
current compatibility profile stores immutable seed/clock inputs and a session-owned
event sequence; V1 gameplay does not yet consume RNG or clock values.

- `GameSession`: owns one package-bound deterministic state, clock/seed inputs,
  event sequence, and save boundary.
- `GameIntent`: typed request for an existing engine action. It is not a plugin
  payload and never carries a direct state patch or executable behavior.
- `GameEvent`: immutable ordered transition fact produced by an accepted action. It
  is neither an event bus nor a separate event-sourced authority; `World` remains the
  V1 compatibility authority.
- `GameView`: complete player-safe projection for the current turn; hidden state and
  unavailable actions are absent. General machine-readable admissible-intent
  descriptors are a V2-2 authoring/tooling surface, not a V2-1 requirement.
- `TurnResult`: accepted/rejected contract status, ordered `GameEvent` values,
  resulting `GameView`, and minimal typed runtime diagnostics for SDK, CLI, and Web.

Given the same package, initial state, clock, seed, and intent sequence, the session
must produce the same statuses, events, views, and saved state. A malformed,
inadmissible, or otherwise contract-rejected intent produces no transition events and
leaves gameplay state, RNG position, clock, event sequence, and save-visible metadata
unchanged. An accepted action may still produce an unsuccessful in-world outcome when
existing `World` semantics require it.

## Compatibility Strategy

`World` remains the compatibility authority during migration. The V2-1 adapters
translate typed intents to existing `World` operations and translate typed outcomes
to events/views. CLI and Web now use the shared `GameSession` application layer;
`CommandProcessor` and Web `PlayerSession` retain their compatibility names and
transport parsing/rendering roles. V1 public content and supported saves remain
regression fixtures.

New capabilities must not accumulate new branches in `World`. V2-3 moves capability
state, predicates, effects, views, and migrations behind declared modules. Legacy
behavior may remain behind the facade until a compatibility exit is separately
approved.

## Authoring-To-Runtime Boundary

Existing `NarrativeModel v1` and `CampaignSpec v1` are useful authoring inputs.
`CampaignSpec` is not runtime content and cannot be passed to `GameSession`. A future
explicit materializer may translate validated authoring artifacts into a
`GameProject`, after which normal package validation and sealing still apply.

V2-2 may derive an unsealed preview build from a project and run it only in an
isolated session. V2-4 owns canonical package identity and promotion to a sealed
`GamePackage v2`; a sealed build is never regenerated in place.

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
- Reject a malformed or inadmissible intent before authoritative state mutation;
  report typed diagnostics without changing RNG, clock, event sequence, or save state.
- Keep hidden data out of `GameView`, CLI output, Web payloads, and Agent-visible
  reports unless explicitly authorized.
- Use stable IDs, canonical serialization, content hashes, bounded inputs, and
  explicit migrations.
- Only deterministic, source-controlled engine code mutates authoritative runtime
  state. Authoring and proofing operate on artifacts or isolated session copies.
- No framework migration, database-first authority, runtime model call, dynamic code,
  plugin execution, package-provided script, or implicit network access is authorized
  by the V2-0 through V2-5 roadmap.
- Preserve the public/private boundary described in [PRODUCT.md](../../PRODUCT.md).
