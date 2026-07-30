# Canon Draft Format v1 (L2W-1)

## Overview

A canon draft is the deterministic output of promoting reviewed fact-candidate
claims into a structured, traceable, and re-validable canon document.  It is
called a *draft* because it contains a single chapter's facts only;
cross-chapter identity mapping belongs to the separate L2W-3 canon registry
stage. Conflict resolution and multi-source semantic deduplication remain
outside CanonDraft v1.

## Input chain

```
ChapterManifest ─┐
FactCandidateDoc ─┤  → build_canon_draft() → CanonDraft
FactReviewDoc    ─┤
PromotionPlan    ─┘
```

## PromotionPlan

A JSON file written by the human reviewer that explicitly maps each
fact-candidate ``candidate_id`` to its stable canon ``entity_id``.

```json
{
  "format_version": 1,
  "promotion_id": "promo_ch001",
  "source_chapter": "chapter_000001",
  "review_id": "review_ch001",
  "entity_mappings": [
    {
      "candidate_id": "character_fog_villager",
      "entity_id": "canon_char_fog_villager",
      "canonical_name": "雾岭老村民",
      "aliases": ["老村民"]
    }
  ]
}
```

### Promotion closure

Only **accepted** claims enter canon.  The promotion closure is:

1. **Direct entities**: candidates with at least one ``accepted`` claim.
2. **Relation entities**: candidates referenced by an ``accepted`` relation claim.

The plan's ``entity_mappings`` must cover exactly this closure — missing and
extra mappings are rejected.

## CanonDraft

```json
{
  "format_version": 1,
  "promotion_id": "promo_ch001",
  "source": {
    "chapter_id": "chapter_000001",
    "chapter_sha256": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
  },
  "extracted_by": "test-extractor/v1",
  "review_id": "review_ch001",
  "reviewed_by": "human-reviewer",
  "entities": [ ... ]
}
```

### CanonEntity

| Field | Type | Source |
|-------|------|--------|
| ``entity_id`` | stable ID | promotion plan |
| ``entity_type`` | enum | copied from ``FactCandidate`` |
| ``canonical_name`` | non-blank string | promotion plan |
| ``aliases`` | array of string | promotion plan, sorted |
| ``source_candidate_id`` | stable ID | original candidate |
| ``claims`` | array of ``CanonClaim`` | accepted claims only |

### CanonClaim

| Field | Type | Preserved from |
|-------|------|----------------|
| ``claim_id`` | stable ID | ``FactCandidate.claim_id`` |
| ``predicate`` | stable ID | original |
| ``value`` | tagged union | original (relation rewritten) |
| ``source_chapters`` | array | original |
| ``source_support`` | ``explicit`` \| ``inferred`` | original |
| ``certainty`` | ``certain`` \| ``uncertain`` | original |
| ``inference_basis`` | string \| null | original |
| ``review_reason`` | non-blank string | from review decision |

### Relation value

Canon uses ``entity_ref`` (referencing a canon ``entity_id``), not
``candidate_ref``.  All ``entity_ref`` values must reference entities
present in the same ``CanonDraft`` — otherwise validation fails.

## Deterministic ordering

| Level | Order |
|-------|-------|
| entities | by ``entity_id`` |
| claims | by ``claim_id`` |
| aliases | by NFKC+casefold+strip key |
| JSON keys | ``sort_keys=True`` |

## Atomic write (CLI)

All reads, structural validation, binding checks, and output validation
complete *before* any file is written.  The CLI uses a temporary file in the
same directory, flushes, fsyncs, and ``os.replace`` for atomic replacement.
On any failure, the temporary file is cleaned up and an existing output file
remains unchanged.

## What v1 does NOT cover

- Cross-chapter entity merging inside a CanonDraft; use
  [Canon Registry Format v1](canon_registry_format.md) for explicit multi-draft
  identity mapping and source-preserving assembly
- Multi-source conflict resolution
- Mutable canon registry storage, incremental versioning, or query APIs
- Canon→game adaptation (HP, attack, quests, items)
- Model or LLM integration
- UI or web interface
