# V2 Authoring Interface

V2-2 adds one public-safe, deterministic authoring path over the accepted V2-1
runtime boundary. V2-4A extends that same service boundary with public-safe
provenance/rights validation, explicit anchor migrations, and sealed package-candidate
identity:

```text
approved GameBlueprint v1 + public-safe V1 content inputs
  -> GameProject v1
  -> validation
  -> fixed-profile unsealed PreviewBuild v1
  -> isolated GameSession simulation
  -> SimulationReport v1 / ProofingProjection v1
  -> provenance / anchor validation (V2-4A)
  -> sealed, non-distributable GamePackage v2 candidate + evidence manifest
  -> Python SDK and structured CLI
```

The implementation lives in `src/lore2mud/authoring/`. The SDK and CLI call the same
`AuthoringService`; the CLI adds only bounded JSON parsing, command routing, atomic
artifact output, and canonical result presentation. `pipeline/forge.py` remains the
V1 inspection/adaptation orchestrator and is not a V2 build system.

## Canonical JSON

Every V2-2 artifact uses UTF-8 JSON with these rules:

- object keys sorted lexicographically;
- two-space indentation;
- JSON non-ASCII text preserved rather than escaped;
- non-finite numbers rejected;
- LF line endings and exactly one final newline;
- contract-defined arrays normalized to stable order before serialization.

Structured file inputs share the bounded JSON limits: 8 MiB encoded bytes, depth
64, 200,000 nodes, 1,000,000 characters per string, and 64 integer digits. Direct
Python document graphs use the same depth, node, and string traversal limits.
Exact typed `GameBlueprint`, `GameProject`, `SimulationRequest`, and `SimulationReport`
values are additionally streamed into canonical JSON under the byte cap and parsed
through the same bounded reader used by the structured CLI before domain loading.

SHA-256 is written as 64 lowercase hexadecimal characters. A fingerprint is the
SHA-256 of the canonical document with its own `fingerprint` field omitted. Preview
and report fingerprints prove reproducibility only. They are not `GamePackage v2`
identity, evidence-manifest identity, sealing, release evidence, or distribution
authorization.

## GameBlueprint v1

Schema: `schemas/game_blueprint.schema.json`.

`GameBlueprint v1` records an approved public product brief: stable blueprint ID,
title, approval decision, audience, genre, tone, bounded play length, adaptation
boundaries, required game loops, acceptance scenarios, asset/provenance/rights
requirements, optional capability requirement IDs, and default seed/clock values.
Default seed and clock values are signed 64-bit integers in both Schema and loader.

Capability requirement IDs are syntax-checked only. V2-2 has no catalog, namespace,
version, dependency, conflict, safety-level, or migration resolver. Any non-empty
`capability_requirement_ids` array blocks preview construction and simulation with:

- stage: `preview`;
- code: `capability_requirement_unsupported_v2_2`;
- JSON Pointer: `/blueprint/capability_requirement_ids/{index}`.

## GameProject v1

Schemas: `schemas/game_project.schema.json` and
`schemas/game_project_inputs.schema.json`.

`GameProject v1` stores only immutable, canonical inputs needed by the fixed V1
preview profile:

- the normalized blueprint and its SHA-256;
- public-safe input descriptors;
- canonical bytes and hashes for the fixed V1 content-file set;
- creator decisions and public trace records;
- a deterministic build-input lock;
- nonsemantic workspace metadata.

Content file names are relative allowlisted names. Each source document is read with
the shared bounded UTF-8 JSON limits and canonicalized before the legacy `ContentPack`
loader sees it. The loader therefore validates only an immutable temporary snapshot,
not the caller's mutable source directory. Absolute paths, mutable `ContentPack`
objects, and source-directory references are not retained. Project creation
revalidates the exact captured snapshot before returning it.

`workspace_metadata` may hold layout, selection, zoom, folding, or cache preferences.
It is serialized with the editable project but excluded from the semantic project
bytes, build lock, preview fingerprint, and simulation report fingerprint.

## AuthoringDiagnostic v1

Schema: `schemas/authoring_diagnostic.schema.json`.

A diagnostic contains `stage`, stable `code`, `severity`, public artifact ID, JSON
Pointer, optional explicitly authorized source span, public message, and remediation.
Diagnostics are sorted by stage, artifact ID, pointer, code, and severity before
transport output. Public diagnostics never include absolute source paths or I/O error
details.

## PreviewBuild v1

Schema: `schemas/preview_build.schema.json`.

A preview contains the validated project/runtime input hashes, engine version,
canonical V1 content bytes, and the engine-defined profile
`lore2mud.v1.compatibility.fixed`. Its invariant flags are:

```json
{
  "kind": "preview",
  "sealed": false,
  "distributable": false,
  "release_evidence": false,
  "identity_scope": "preview_reproducibility_only"
}
```

The profile cannot be selected by a project. Preview loading checks the current
engine version, all hashes, canonical file order, fixed flags, profile ID,
fingerprint, and V1 `ContentPack` validity before constructing runtime state.

## SimulationRequest v1

Schema: `schemas/simulation_request.schema.json`.

A request supplies one signed-64-bit seed and clock, a bounded player name, at most
1,024 typed `GameIntent` values, at most 256 deterministic win/loss conditions, and
unique sorted save/load checkpoint step indices. Conditions inspect only fields
already available in the final player-safe `GameView`.

An over-limit typed request returns one serialization-stage rejection before preview
or session work and before project capability diagnostics can mask that resource
failure. The SDK and CLI use the same stable `authoring_input_too_large`,
`authoring_input_too_complex`, or `authoring_input_invalid_json` diagnostic according
to the shared bounded-reader failure.

## SimulationReport v1

Schema: `schemas/simulation_report.schema.json`.

Simulation always creates fresh content, save-directory, `SaveLoadService`, `World`,
and `GameSession` values from immutable preview bytes. It never receives or mutates a
caller's active session. The report records:

- blueprint, semantic project, preview, and normalized request hashes;
- engine version plus seed, clock, and player name;
- initial/final authoritative save-state and player-view hashes;
- each typed intent, accepted/rejected status, stable rejection code, event types,
  and resulting view hash;
- evaluated win/loss conditions and aggregate outcome;
- a replayable witness trace and fresh-replay result;
- requested save/load checkpoint state/view hashes and equivalence result;
- `simulation_reproducibility_only` identity scope and report fingerprint.

Authoritative state hashes are produced only by submitting typed `SaveIntent` values
to an isolated `GameSession` and hashing the bounded save document. V2-2 does not
import or expose the engine's private save serializer as an authoring API.

Replay rejects reports from another engine version, rebuilds the exact preview from
the supplied project, reconstructs the request from the witness, runs fresh isolated
sessions, and requires the complete normalized report document to match. Typed reports
first complete the same bounded canonical round trip as structured CLI report inputs.

## Admissible Intents And Proofing

Schema: `schemas/proofing_projection.schema.json`.

Admissible-intent descriptors flatten only concrete typed intents already present in
the detached player-safe `GameView`. They never scan `World`, infer unavailable
actions, or expose hidden targets and conditions. Descriptor IDs derive from the
canonical intent document; fields are bounded scalar values. Nodes, edges, labels,
and descriptor collections have hard limits. Oversized projections reject rather
than silently omit gameplay actions.

The proofing projection contains stable public nodes, edges, diagnostics, and the
current admissible descriptors. It is a detached read-only value. Unknown trace
endpoints, hidden runtime values, absolute paths, private source hashes, raw private
text, and presentation metadata are absent.

## AuthoringResult v1

Schema: `schemas/authoring_result.schema.json`.

Every operation returns one canonical envelope containing the operation name,
`success` or `rejected` status, one optional typed artifact, sorted diagnostics, and
exit meaning. Success requires an artifact, no diagnostics, and exit code `0`;
rejection requires no artifact, at least one diagnostic, and exit code `1`.
Diagnostics are bounded to at most 4,096 entries. Inputs that cannot be safely
normalized collapse to a stable single rejection rather than producing an invalid or
partially serialized result.

## Python SDK

`lore2mud.authoring.sdk.AgentAuthoringSDK` exposes:

- `create_project(...)`;
- `validate_blueprint_document(document)`;
- `validate_project_document(document)` and `validate_project(project)`;
- `build_preview(project)`;
- `simulate(project, request)`;
- `replay(project, report)`;
- `proof(project)`.

The SDK contains no second compiler, runtime, or validation policy.
Every typed blueprint, project, request, and report is defensively normalized again at
the shared service boundary. Malformed nested values or canonical content bytes return
an `AuthoringResult` rejection before capability diagnostics, preview materialization,
or isolated session construction. Direct Python document objects are traversed under
the shared depth, node, and string limits; cyclic containers reject before domain
loading. Typed values additionally share the byte and integer limits through a bounded
canonical round trip. Resource failures use public artifact IDs `blueprint`, `project`,
or `report`; simulation request resource checks still run before project normalization.
Raw decode, attribute, recursion, traversal, and bounded-reader failures are not public
SDK results.

## V2-4A Provenance, Anchors, And Sealing

`AuthoringService` remains the only policy boundary for the Python SDK, structured CLI,
and generic Web transport. It adds these operations without adding a second compiler,
runtime, or `World` authority:

- `validate_provenance_document(manifest)` validates opaque IDs, public-safe source
  references, rights assertions, creator decisions, transformations, and the complete
  source-to-project-to-package trace chain.
- `validate_anchor_migrations_document(request)` validates opaque story, scene, and
  resume anchors plus explicit migrations for incremental candidates.
- `seal_document(request)` validates both contracts, replay-verified evidence, pure
  data package elements, and canonical identities before producing one candidate.

Successful sealing produces `sealed=true`, `distributable=false`, and
`release_evidence=false`. It is immutable and suitable only for the controlled runtime
input boundary. It does not grant PRODUCT approval, SECURITY approval, source-rights
permission beyond the recorded assertion, distribution, publishing, or release.
Presentation metadata is retained for the workspace but excluded from package and
evidence identity bytes.

The public synthetic 30-60 minute story-arc smoke and CLI/SDK/Web parity coverage live
in `tests/test_v2_4_provenance_rights.py`; they use no private source material.

## Structured CLI

The corresponding commands are:

```text
python -m lore2mud author create-project --project-id ID --blueprint FILE --content DIR [--project-inputs FILE] [--output FILE]
python -m lore2mud author validate --project FILE [--output FILE]
python -m lore2mud author preview --project FILE [--output FILE]
python -m lore2mud author simulate --project FILE --request FILE [--output FILE]
python -m lore2mud author replay --project FILE --report FILE [--output FILE]
python -m lore2mud author proof --project FILE [--output FILE]
python -m lore2mud author validate-provenance --manifest FILE [--output FILE]
python -m lore2mud author validate-anchors --request FILE [--output FILE]
python -m lore2mud author seal --request FILE [--output FILE]
```

Standard output is one canonical `AuthoringResult v1`. `--output` atomically writes
only a successful artifact and cannot alias an input or the content source directory.
Exit code `0` means success, `1` means a structured domain rejection, and `2` is
reserved for argparse or transport misuse.

## Compatibility And Exclusions

V2-2 changes no V1 content or save format. Saves still write v9 and retain v7/v8 read
conditions. Runtime `campaign.json` remains an optional V1 content-pack input;
`CampaignSpec v1` remains authoring IR and is never accepted as a preview package.
`World` remains the gameplay authority, and simulation submits only typed intents
through `GameSession`.

V2-2 compatibility remains unchanged for the empty capability-requirements lane.
V2-4A adds only provenance/rights closure, anchor migration, canonical package/evidence
identity, and a sealed non-distributable candidate. It does not implement capability
resolution, a workbench or alternate editor/compiler/runtime (V2-5), MCP, dynamic
plugins, runtime model adjudication, dependency changes, release evidence, or
publishing behavior.
