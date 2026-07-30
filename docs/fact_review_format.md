# Fact Review Document Format v1

## Overview

A fact-review document encodes human review decisions on fact-candidate
claims.  Each decision marks a single claim as accepted, rejected,
superseded, or conflicted, with a mandatory reason.

## Root object

```json
{
  "format_version": 1,
  "review_id": "review_character_fog_villager",
  "source_chapter": "chapter_000001",
  "reviewed_by": "human-reviewer",
  "decisions": [ ... ]
}
```

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `format_version` | int | yes | Must be `1`. Bool rejected. |
| `review_id` | string | yes | Stable ID `^[a-z][a-z0-9_]*$`. |
| `source_chapter` | string | yes | `^chapter_[0-9]{6}$`. |
| `reviewed_by` | string | yes | Non-blank. |
| `decisions` | array | yes | Non-empty. |

## Decision

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `candidate_id` | string | yes | Stable ID. |
| `claim_id` | string | yes | Stable ID. |
| `state` | string | yes | `accepted` \| `rejected` \| `superseded` \| `conflicted`. |
| `reason` | string | yes | Non-blank. |
| `superseded_by_claim_id` | string \| null | yes (key must be present) | Non-blank stable ID when `state=superseded`; must be `null` otherwise. |

### Uniqueness

`(candidate_id, claim_id)` must be unique within the review document.

### Partial review

Not all claims in a candidate document need to be reviewed.  Claims not
appearing in the decisions array are considered unreviewed.

## Binding

The binding function accepts exactly one pre-validated
`FactCandidateDocument` (returned by `validate_fact_candidate_document()`).
The caller is responsible for selecting the correct candidate document for
this review.

Key boundary constraints:

- `review.source_chapter` must equal `candidate_document.source_chapter`.
  However, `source_chapter` is **not** a globally unique key for candidate
  documents: the same chapter may have multiple extraction runs, each
  producing a separate `FactCandidateDocument`.  The caller must explicitly
  pass the single document being reviewed.
- Auto-discovery of candidate documents by `source_chapter`, file matching,
  persistence, and cross-document conflict resolution are **not** in v1 scope.

Per-decision checks:

```python
from pipeline.fact_reviews import validate_fact_review_bindings

validate_fact_review_bindings(review, candidate_document)
```
- `review.source_chapter` equals `candidate_document.source_chapter`.
- Every `candidate_id` exists in the candidate document.
- Every `claim_id` belongs to its parent candidate.
- `superseded_by_claim_id` (if set) belongs to the same candidate and is not self-referential.

Returns the review unchanged on success; raises `FactReviewBindingValidationError` on failure.

## What v1 does NOT include

- Cross-document conflict references
- Entity merging / resolution
- Canon writing / promotion
- Review history / timestamps
- Confidence scores
- Model-driven review suggestions

## Schema

`schemas/fact_review.schema.json` (draft 2020-12) with `additionalProperties:false`
and `if/then/else` for the `state=superseded` conditional. Python adds duplicate
pair detection, candidate/claim binding, cross-candidate supersede rejection,
and self-reference checks.
