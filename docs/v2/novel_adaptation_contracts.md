# V2-4A Novel Adaptation Contracts

_Status: local V2-4A implementation candidate. This document defines public-safe
contracts only; it does not grant source rights, authorize distribution, or claim any
acceptance gate._

## Scope And Ownership

V2-4A adds four authoring-owned, transport-neutral modules under
`src/lore2mud/authoring/`:

| Module | Owns | Does not own |
|---|---|---|
| `provenance.py` | source references, rights assertions, creator decisions, transformations, trace bindings, public audit projection | source text, source paths, private hashes, rights adjudication |
| `anchors.py` | opaque story/scene/resume anchors, explicit migration records, resolution report | save-version migration, runtime scheduling |
| `packages.py` | pure-data `GamePackage v2`, evidence manifest, canonical bytes, candidate identity, seal input | dynamic code, runtime loading, `World`, save core |
| `web_transport.py` | generic bounded JSON adapter over `AuthoringService` | a Web-specific compiler or authoring rules |

The V1 `World` remains the compatibility authority. V2-4A does not alter runtime
turn rules, V1 content-pack inputs, save formats, capability resolution, or clients.

## Promotion Modes

`ProvenanceManifest v1` has exactly three modes:

| Mode | Contract |
|---|---|
| `prototype` | May hold public-safe source/decision structure before every project element has a trace binding. It is not distributable or sealable. |
| `traced` | Every material project element has one complete source-to-package trace binding. Denied rights are rejected. |
| `sealed` | Extends `traced`: every recorded right is `authorized`, every creator decision is approved, and every transformation is deterministic. Only this mode can seal. |

`sealed` is a technical integrity state, not a release state. V2-4A writes
`GamePackage v2` candidates with `sealed=true`, `distributable=false`, and
`release_evidence=false`. A candidate may be handed to the controlled runtime input
boundary, but it grants neither product approval, security approval, source-rights
authorization beyond the recorded assertions, nor permission to distribute or publish.
Those gates remain external to this contract and are deliberately not represented as
package-provided executable policy.

The material-element chain is fixed:

```text
source reference
  -> rights assertion
  -> creator decision
  -> transformation record
  -> GameProject element
  -> GamePackage v2 element
```

Stable IDs are opaque keys, not display names. Duplicate IDs, missing references,
transform cycles, duplicate transformation outputs, incomplete traced/sealed chains,
and unapproved sealed inputs reject before a candidate is created.

## Public-Safe Provenance

`provenance_manifest.schema.json` describes the typed manifest. The public audit
projection preserves status, trace topology, and deterministic transformation facts,
but anonymizes every `authorized_private` source and associated rights/decision IDs.
It replaces private labels, source kinds, rights scope/authority, and decision
rationale with generic public-safe values before serialization or hashing.

No free-text or package-data field accepts raw source text, excerpts, absolute or relative
paths (including bare filenames, dotfiles, and dot segments), file or network URIs, or
source hashes. `content_files[].name` is the sole filename exception and is restricted to
the engine-owned V1 content-file allowlist. Slash punctuation is rejected unless the complete
value is one of the small, established public display labels (`fixture-extractor/v1`,
`fixture-extractor / v1`, `story/scene`, `story / scene`, `hand/body`, or
`hand / body`); this keeps legacy public labels compatible without admitting arbitrary
path-like text. Backslashes, URI-like `scheme:payload` tokens, format/control
characters, and percent escapes are rejected. Public diagnostics use stable codes and
public artifact IDs only; they do not echo rejected input values.
Validation results also return the public provenance projection, including through
the SDK.

## Package And Evidence Identity

`GamePackage v2` is pure JSON data. It contains a loader-valid canonical V1 content
snapshot (all required V1 files and no unsupported runtime inputs), resolved capability
requirement IDs, at least one material package element, anchors, the evidence-manifest
digest, and the anchor-migration digest. It cannot contain package-provided Python,
scripts, import/module paths, plugins, submodules, native modules, shell or process
fields, or network/host-I/O fields.
The captured V1 snapshot is screened again at sealing time for the same public-safe
pure-data policy; V1 loader acceptance alone is not permission to seal private paths
or executable/host-I/O data.

The following canonical documents use sorted keys, two-space UTF-8 JSON, LF endings,
and exactly one final newline:

| Artifact | Identity bytes exclude |
|---|---|
| `GamePackage v2` | candidate ID, package hash, presentation metadata |
| `EvidenceManifest v1` | evidence candidate ID, manifest hash, presentation metadata |
| `AnchorMigrationReport v1` | no identity fields; its complete migration set and resolutions are canonical |

`SealRequest` accepts typed `SimulationReport v1` or `CapabilitySimulationReport v1`
records, never caller-supplied evidence IDs or source hashes. Each report must belong
to the exact `GameProject`, validate, and replay byte-equivalently before its
fingerprint is projected into the evidence manifest.

`candidate_id` is `package_` plus the first 24 hex characters of the package semantic
SHA-256. `EvidenceManifest` uses the same rule with the `evidence_` prefix. A changed
semantic package field, provenance projection, admitted evidence entry, anchor, or
anchor migration changes the relevant hash. Layout, selection, zoom, folding, caches,
and other `presentation_metadata` values do not change either identity.

The package semantic bytes also bind `seal_mode` and, for an incremental seal, the
immediate predecessor candidate ID, package SHA-256, and complete predecessor-anchor
set SHA-256. Thus an initial and incremental seal of otherwise identical current content
are distinct candidates.

`SealCandidate v1` carries the sealed package, evidence manifest, anonymized
provenance manifest, anchor migration report, migration digest, and a hash over all
four binding digests. Loaders recompute every stored hash and reject tampering. A
sealed package is immutable: any semantic change must create a new candidate.

## Anchors And Incremental Content

`StoryAnchor v1` is an opaque stable ID bound to one project/package element pair and
one of `story`, `scene`, or `resume`. `AnchorMigration v1` explicitly maps a removed
previous anchor to one or more same-kind current anchors and records the creator
decision responsible for the migration.

`SealRequest` has an explicit lineage mode. `initial` starts a new lineage or fork and
must not carry a predecessor or migrations. This stateless contract does not claim that
it is the globally first seal for a project; proving that would require an external
registry. `incremental` must carry one loader-validated predecessor package for the same
project. Its complete predecessor anchor set is derived by the service, never supplied
or narrowed by the caller, and every predecessor anchor must be preserved implicitly or
resolved by an explicit migration.

Sealing validates the predecessor/current sets, migration graph, exact package/project
pairs, complete predecessor-anchor coverage, migration target kinds, and creator-decision binding.
A migration source that is still present in the current package rejects; preservation is
implicit only when its kind and project/package binding are unchanged, and an explicit
migration is reserved for a removed anchor. Unresolved anchors,
cycles, duplicate migration records, unknown decisions, over-limit collections, or a
package/anchor pair mismatch reject before canonical package bytes are produced. Graph
walks are iterative so a valid long migration or transformation chain remains within the
same typed contract rather than leaking a host recursion failure.

## Shared Service Boundary

The Python SDK, structured CLI, and generic Web transport delegate to the same
`AuthoringService` methods:

```text
validate_provenance_document
validate_anchor_migrations_document
seal_document
```

All three use the existing bounded JSON and canonical serialization rules. Invalid
Unicode, cyclic containers, oversized input, malformed records, and policy rejection
produce the same public `AuthoringResult v1` envelope semantics. V2-2's empty
capability-requirements lane remains unchanged; V2-4A neither resolves a new
capability nor changes preview/report behavior.

## Schemas

- `provenance_manifest.schema.json`
- `story_anchor.schema.json`
- `anchor_migration.schema.json`
- `anchor_validation_request.schema.json`
- `anchor_migration_report.schema.json`
- `game_package_v2.schema.json`
- `evidence_manifest.schema.json`
- `seal_request.schema.json`
- `seal_candidate.schema.json`

These schemas are structural gates. The authoring loaders additionally enforce
cross-reference integrity, bounds, public-safe text, canonical hashes, and pure-data
policy before sealing.

## Explicit Exclusions

V2-4A does not implement a Workbench, MCP, a Reference Agent, a new Demo, a storylet
scheduler, canon rewriting, runtime LLM decisions, dynamic plugins, package scripts,
multiplayer, a new save/content version, release, distribution, push, or a `main`
merge. Private novel text, canon, derived adaptation content, images, saves, reports,
paths, and source hashes remain outside this repository.
