# Narrative Model Format v1

## Overview

`NarrativeModel v1` is a deterministic, reviewable intermediate artifact for
organizing a scoped portion of a validated `CanonRegistry v1`. A human writes a
`NarrativePlan v1`; the compiler binds its exact claim references to the input
registry and writes one canonical JSON model.

```text
CanonRegistry v1 + NarrativePlan v1
        -> compile_narrative_model()
        -> NarrativeModel v1
        -> write_narrative_model() -> one JSON file
```

The plan, model, and compiler do not generate canon, infer identity, resolve
conflicts, change a registry, or construct game content. They do not connect to
the runtime, saves, Web Player, or Forge. A real model derived from private
canon is private derived material and must not be committed to the public
repository.

## NarrativePlan v1

The root fields are:

| Field | Meaning |
|---|---|
| `format_version` | True integer `1`. |
| `model_id` | Stable ID for the requested model. |
| `source_registry` | Exact `registry_id` and `registry_version` expected from the input. |
| `scope` | Registry entities plus complete use/omission accounting for their claims. |
| `perspectives` | Explicit narrative viewpoints anchored to scoped entity IDs. |
| `propositions` | Human-authored statements and their exact claim support when applicable. |
| `phases` | Contiguous ordered narrative phases. |
| `beats` | Ordered narrative beats and their dependencies. |

### Scope and provenance

`scope.entity_refs` selects one or more exact registry entity IDs. It is a
scoped subset, so it does not need to cover every registry entity. During
compilation, every claim of every scoped entity must be accounted for exactly
once in one of these ways:

- `claim_uses` contains its composite source identity and it appears in one or
  more proposition `claim_refs`; or
- `claim_omissions` contains the same composite identity with a non-blank human
  reason.

Both arrays are required. `claim_uses` may be empty when every scoped claim is
recorded in `claim_omissions`; compilation still rejects any scoped claim that
is neither used nor reasonedly omitted.

A claim reference is always the full tuple
`(promotion_id, source_entity_id, source_claim_id)`. The compiler rejects a
missing, foreign, or unaccounted claim. It preserves no raw claim value in the
model, so the input `CanonRegistry` remains the authority for claim content.

### Perspectives and propositions

Each perspective has a stable `perspective_id`, a scoped `entity_ref`, and a
human-authored `summary`. Every perspective must be used by at least one beat.

Each proposition has a stable `proposition_id`, `statement`, `status`, exact
`claim_refs`, and a human-authored `rationale`. The supported statuses are:

| Status | Claim rule |
|---|---|
| `canon_supported` | One or more exact claim references. |
| `conflicted` | At least two exact claim references. The compiler does not decide whether they conflict. |
| `adaptation_only` | No claim references. It records an explicit non-canon design choice. |
| `unknown` | No claim references. It records an explicit unresolved question. |

The set of all proposition claim references must exactly equal
`scope.claim_uses`. A referenced claim can support more than one proposition,
but appears only once in the scope accounting set.

### Phases, beats, and disclosures

`phases` have unique stable IDs and true integer `sequence` values contiguous
from `1`. A beat has a stable `beat_id`, one `phase_ref`, zero or more
`predecessor_refs`, at least one perspective and proposition reference, optional
disclosures, and a summary.

The beats must form a DAG. A beat cannot depend on itself, an unknown beat, or a
beat from a later phase. Each phase, perspective, and proposition must appear in
at least one beat. A disclosure is local to its beat: its perspective and
proposition must both be listed by that beat, and the pair may appear only once
within that beat. Its state is one of `heard`, `suspected`, `confirmed`, or
`retracted`.

## NarrativeModel v1

The output copies the plan body in canonical order and replaces the plan's
registry reference with a `source_registry` snapshot containing:

- `registry_id` and `registry_version` from the actual input registry;
- exactly the complete source records for promotions named by scoped claim uses
  and omissions.

The source-promotion set must exactly equal the promotion set of the scoped
claims. This gives a model a stable, reviewable source-record snapshot while the
compiler verifies each individual claim reference against the actual registry.
The standalone model validator checks the model's internal shape, ordering, DAG,
and source-promotion coverage; compilation is the operation that proves claim
membership in a particular `CanonRegistry`.

## Canonical order and validation

Python validators reject unknown fields, bools and floats for integer fields,
malformed stable IDs, duplicate composite claim provenance, conflicting
use/omission entries, missing beat references, unused body elements, cycles, and
non-contiguous phase sequences. Draft 2020-12 JSON Schemas provide the strict
structural contracts; Python validates the cross-object and registry-bound
rules.

Canonical collection order is:

| Collection | Order |
|---|---|
| scoped entity IDs | stable ID |
| claim uses and omissions | promotion ID, source entity ID, source claim ID |
| perspectives and propositions | stable ID |
| phases | sequence, then stable ID |
| beats | deterministic topological order, then phase and stable ID tie-breaks |
| beat ID references | stable ID |
| disclosures | perspective ID, proposition ID, state |
| source records | chapter ID, then promotion ID |

JSON is encoded as UTF-8 with `sort_keys=True`, two-space indentation, and one
trailing LF.

## Atomic writer and CLI

`write_narrative_model()` revalidates the whole typed model before it creates a
same-directory temporary file. It writes, flushes, fsyncs, and publishes with
`os.replace`; a failed publish preserves an unrelated existing output and removes
only the invocation-owned temporary file.

The CLI rejects direct paths, hardlinks, symlinks, and Windows reparse points
that make any registry input, plan input, or output alias another supplied path.
Input bytes are never modified.

```powershell
python -m pipeline.narrative_model `
  --canon-registry tests/fixtures/canon_registry/expected_registry.json `
  --narrative-plan tests/fixtures/narrative_model/valid_plan.json `
  --output C:\Temp\fixture_narrative_model.json
```

## Deliberate limits

- no name, alias, fuzzy, full-text, or semantic entity search;
- no claim deduction, conflict resolution, source rewriting, or registry update;
- no runtime, content-pack, save, Web, Forge, model/LLM, database, or index integration;
- no automatic plot generation or game rules;
- no private novel text, summaries, canon, or derived model may enter the public repository;
- no new dependency.
