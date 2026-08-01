# Campaign Spec Format v1

## Overview

`CampaignSpec v1` is a deterministic, reviewable campaign intermediate
representation. A human writes a `RegistryCampaignPlan v1` against one exact,
validated `NarrativeModel v1`; the pure compiler binds every source reference,
checks campaign graphs and accounting, and emits one self-contained canonical
JSON artifact.

```text
NarrativeModel v1 + RegistryCampaignPlan v1
        -> compile_campaign_spec()
        -> CampaignSpec v1
        -> write_campaign_spec() -> one JSON file
```

This pipeline does not emit a content pack or runtime rules. It does not touch
the game runtime, saves, Web Player, player CLI, or Forge. A plan or spec derived
from private material is private derived material and must remain outside the
public repository.

## Exact Source Binding

The plan's `source_narrative_model` has three required fields:

| Field | Meaning |
|---|---|
| `format_version` | True integer `1`. |
| `model_id` | Exact source model stable ID. |
| `narrative_model_sha256` | Lowercase SHA-256 of the canonical source model bytes. |

Canonical source bytes are `narrative_model_to_document(model)` serialized as
UTF-8 with sorted object keys, two-space indentation, no NaN, and one trailing
LF. `narrative_model_sha256()` implements this calculation. Compilation rejects
a different format, ID, or hash, including a changed source snapshot that keeps
all stable IDs.

The output replaces this compact reference with the complete validated
`NarrativeModel` document in `source_narrative_model`. The spec is therefore
self-contained and preserves the source registry snapshot, claim provenance,
perspectives, propositions, phases, beats, and disclosures without mutation.

## Root and Accounting

The common plan/spec body contains:

| Field | Meaning |
|---|---|
| `format_version` | True integer `1`. |
| `campaign_id` | Stable campaign ID. |
| `adaptation_rationale` | Non-blank rationale for the campaign cut. |
| `scope` | Complete source use/omission accounting. |
| `start_location_ref` | Authoritative reachable-map and player-entry root. |
| `locations` | Directed campaign locations and exits. |
| `actors` | Player, character, and adversary roles. |
| `scenes` | Phase-bound scene DAG. |
| `objectives` | Objective DAG, exclusions, and typed completion targets. |
| `knowledge_beats` | Exact projections of source disclosures. |
| `knowledge_corrections` | Explicit adaptation-only corrected transitions. |

`scope` has required use and omission arrays for NarrativeModel entities,
perspectives, propositions, and beats. Every source ID must occur in exactly one
disposition:

- a use ID must be present in an actual campaign binding; or
- an omission must name the exact source ID once and give a non-blank reason.

The declared use sets must exactly equal the union of their concrete bindings.
The compiler rejects missing, foreign, overlapping, duplicate, or invented
accounting. Multiple campaign objects may cite the same source proposition or
entity; its accounting disposition remains one set entry.

## Locations and Actors

A location has a stable ID, name, description, zero or more exact source entity
and proposition refs, non-blank adaptation notes, and directed exits. Every exit
declares a human-facing `direction`, a `name`, and an exact target location. A
location cannot repeat a normalized direction or name. Exit reciprocity is not
implied.

Every location must be reachable from `start_location_ref`. The compiler also
checks campaign progression: when a physical scene depends on an earlier
physical scene, the later location must be reachable from the earlier location
through directed exits. This check follows transitive scene predecessors, so a
null-location or internal scene between the physical scenes does not permit an
impossible traversal.

Exactly one actor is the player, and that actor must have a non-null
`starting_location_ref` equal to `start_location_ref`. Other actor starting
locations remain independently declared. This keeps the map root, player entry,
and first reachable campaign actions under one authority even when exits are
directed and a remote location has no return route.

An actor has a stable ID, kind, name, description, optional exact source entity
ref, starting location ref or null, source proposition refs, and adaptation
notes. Kinds are `player`, `character`, and `adversary`; exactly one actor is the
player. `adversary` records opposed campaign intent and does not imply combat.

## Scenes and Source Beats

Scene kinds are `exploration`, `conversation`, `conflict`, `ritual`, `internal`,
and `revelation`. Each scene declares an exact source phase, a location or null,
one or more participating actors, zero or more exact NarrativeBeat refs,
predecessor scene refs, source proposition refs, and adaptation notes.

Scenes form a DAG. A predecessor cannot be in a later source phase. A source
beat may be bound by only one scene and must have the same phase as that scene.
For every pair of used source beats related by NarrativeModel predecessor
reachability, the containing scenes must have the same strict reachability in
the campaign DAG. Source predecessors may be reasonedly omitted, but used beats
cannot be reordered, collapsed into one unordered scene, or placed on an
impossible directed-map route.

## Objectives

An objective has a stable ID, title, description, phase ref, one or more scene
refs, predecessor objective refs, mutually exclusive objective refs, source
proposition refs, a completion tagged union, and adaptation notes. Every scene
must be bound by at least one objective.

Objective predecessors form a DAG and cannot move backward through source
phases. Mutual exclusion must be symmetric. An objective cannot depend on an
objective it excludes, and no objective may require an ancestry containing two
mutually exclusive objectives.

Completion is one strict branch:

```json
{ "kind": "reach_location", "location_ref": "location_records_office" }
{ "kind": "interact_actor", "actor_ref": "actor_bicycle_courier" }
{ "kind": "complete_scene", "scene_ref": "scene_report" }
{ "kind": "apply_knowledge", "knowledge_ref": "correction_cart_report" }
```

Every completion target must resolve through one of the containing objective's
`scene_refs` in the objective's exact phase. `reach_location` names the location
of such a scene, `interact_actor` names one of its participants,
`complete_scene` names the scene directly, and `apply_knowledge` names a
knowledge beat or correction whose `scene_ref` is that scene. The resolved scene
still obeys the campaign scene DAG, source phase, and directed travel checks.
This prevents a later or unrelated scene from completing an earlier objective.
The tagged target is validated but not executed; it remains an IR boundary for
a separately authorized future runtime compiler.

## Knowledge and Corrections

A knowledge beat binds a campaign actor and scene to one exact source beat,
perspective, proposition, and disclosure state. The state remains one of the
NarrativeModel v1 values: `heard`, `suspected`, `confirmed`, or `retracted`.
The compiler requires the full tuple to match a disclosure in the named source
beat; it never upgrades or reinterprets the source snapshot.

For one `(actor, perspective, proposition)` track, every pair of repeated
updates must be totally ordered by both the source beat DAG and the campaign
scene DAG. Incomparable branch updates are rejected because v1 defines no
branch-join knowledge semantics. Ordered transitions cannot regress from
confirmed to heard/suspected or resume after retraction, and a retraction
requires a reachable earlier non-retracted projection.

NarrativeModel v1 has no `corrected` disclosure state. An adaptation-only
knowledge correction therefore remains a separate object with literal state
`corrected`. It names the earlier heard/suspected knowledge beat, earlier and
later proposition refs, actor, scene, and rationale. A valid correction must
occur later in the scene DAG and must be supported by a reachable source
retraction of the earlier proposition plus confirmation of the later one. The
source model embedded in the spec remains byte-for-byte canonical and unchanged.

## Canonical Order and Schemas

Semantically unordered collections are sorted by stable IDs or normalized route
labels. Scenes and objectives use deterministic topological order with stable-ID
tie breaks; knowledge collections use scene order and their own stable IDs.
Reference arrays are sorted. In v1, array declaration order is never a hidden
choice mechanic: phases, predecessor edges, exit labels, exclusions, and tagged
targets carry all behavioral meaning.

`registry_campaign_plan.schema.json` and `campaign_spec.schema.json` are strict
Draft 2020-12 Schemas. The spec schema reuses the plan's shared definitions and
the adjacent `narrative_model.schema.json`; consumers must register those schema
IDs when validating offline. Python adds cross-object, graph, SHA, and source
binding validation.

## Atomic Writer and CLI

`write_campaign_spec()` revalidates the complete typed artifact before creating
a same-directory temporary file. It writes, flushes, fsyncs, and publishes with
`os.replace`; a failed replace preserves an existing output and removes only the
invocation-owned temporary file.

The module CLI rejects direct paths, hardlinks, symlinks, and Windows reparse
points that make either input or the output alias another supplied path:

```powershell
python -m pipeline.campaign `
  --narrative-model tests/fixtures/campaign/magic_event/narrative_model.json `
  --campaign-plan tests/fixtures/campaign/magic_event/valid_plan.json `
  --output C:\Temp\resonance_campaign_spec.json
```

## Deliberate Limits

- no runtime content pack, game rules, save format, Web, player CLI, or Forge integration;
- no automatic plot, quest text, dialogue, combat, or objective execution;
- no canon generation, identity resolution, conflict resolution, or source rewriting;
- no branch-join knowledge semantics or correction of an unprojected belief;
- no private novel text, summaries, canon, models, or derived campaign artifacts;
- no new dependency.
