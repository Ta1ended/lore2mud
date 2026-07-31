# Registry Inspection Format v1 (L2W-5)

## Overview

L2W-5 creates a deterministic, read-only review artifact from a validated
`CanonRegistry v1`. A human-authored plan selects exact registry entity IDs. The
compiler copies those entities and their complete provenance without searching
names, resolving conflicts, inferring identity, or changing the registry.

```text
CanonRegistry v1 + RegistryInspectionPlan v1
        -> compile_registry_inspection()
        -> RegistryInspectionReport v1
        -> write_registry_inspection_report() -> one JSON file
```

The report is intended for review before an adaptation plan is written. It is a
source-preserving subset, not a new canon authority and not a mutable registry.
Real reports derived from private canon remain private and must not be committed.

## RegistryInspectionPlan v1

The root fields are:

| Field | Meaning |
|---|---|
| `format_version` | Must be `1`. |
| `inspection_id` | Stable ID for this inspection request and report. |
| `source_registry_id` | Must exactly match the input registry ID. |
| `source_registry_version` | Must exactly match the input registry version. |
| `entity_refs` | One or more unique, exact registry entity IDs. |

Example:

```json
{
  "format_version": 1,
  "inspection_id": "inspection_mira_review",
  "source_registry_id": "fixture_registry",
  "source_registry_version": 1,
  "entity_refs": ["canon_mira"]
}
```

The plan cannot select by canonical name or alias. Unknown IDs, duplicates,
unstable IDs, and registry identity/version mismatches fail before output.

## RegistryInspectionReport v1

The report repeats the plan identity and contains:

- `selected_entity_refs`: the canonical sorted selection;
- `entities`: exactly those registry entities, sorted by `entity_id`;
- `sources`: exactly the complete source records referenced by the selected
  entities' claims.

Every selected entity preserves its `entity_type`, `canonical_name`, `aliases`,
`members`, `claims`, and `merge_reason`. Candidate provenance remains present as
each member's `source_candidate_id`; it is not converted into a separate or
inferred candidate list. Claims retain the composite identity
`(promotion_id, source_entity_id, source_claim_id)` and all value, chapter,
support, certainty, inference, and review fields.

Conflicting claims remain separate. Relation values may point to registry entity
IDs outside `selected_entity_refs`; the report preserves that reference without
silently expanding the selection. The source registry identified by the report
remains authoritative for resolving that target.

## Source subset rule

`sources` is derived only from selected claims, not from member rows. Each claim
promotion must have exactly one source record, and its sole `source_chapters`
entry must match that record's chapter. Duplicate promotions and chapters fail.
An entity with no claims therefore produces an empty `sources` array even though
its complete member provenance is still copied.

The standalone report validator requires the source promotion set to equal the
promotion set used by all report claims. During compilation, the selected entity
objects and source records are copied directly from a fully revalidated
CanonRegistry, which proves field preservation against the actual input.

## Determinism and validation

The Python validators reject unknown fields, bool-as-int versions, malformed
stable IDs, normalized duplicate aliases, duplicate member/candidate/claim
provenance, invalid tagged claim values, inference inconsistencies, and incomplete
selection or source coverage. Draft 2020-12 Schemas provide the structural
contracts; Python performs the cross-object set and provenance checks.

Canonical order is:

| Collection | Order |
|---|---|
| selected entity refs and entities | registry entity ID |
| sources | chapter ID, then promotion ID |
| aliases | NFKC + casefold key |
| members | promotion ID, then source entity ID |
| claims | promotion ID, source entity ID, source claim ID |

JSON uses UTF-8, `sort_keys=True`, two-space indentation, and one trailing LF.

## Atomic writer and CLI

The writer revalidates the complete report before creating a temporary file beside
the destination. It writes, flushes, fsyncs, and publishes with `os.replace`.
An unrelated existing output is atomically replaced; a failed publish preserves
that output and removes only the invocation-owned temporary file.

The CLI rejects the registry, plan, and output when any two point to the same file,
including direct paths, hardlinks, and symlinks. Input bytes are never modified.

```powershell
python -m pipeline.registry_inspection `
  --canon-registry tests/fixtures/canon_registry/expected_registry.json `
  --inspection-plan tests/fixtures/registry_inspection/valid_plan.json `
  --output C:\Temp\mira_inspection.json
```

## Deliberate limits

- exact stable-ID selection only; no name, alias, fuzzy, full-text, or semantic search;
- no entity merge, claim deduplication, conflict resolution, or inference;
- no mutable storage, registry update, cross-registry query, or indexing;
- no content-pack adaptation, game-state change, multi-room output, or save change;
- no private novel, summary, canon, or derived report may enter the public repository;
- no model or LLM integration and no new dependency.
