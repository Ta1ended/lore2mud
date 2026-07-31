# Canon Registry Format v1 (L2W-3)

## Overview

A canon registry is a deterministic, source-preserving view over two or more
validated `CanonDraft v1` documents. It gives chapter-local entities a shared
registry identity without asking code or a model to guess whether two entities
are the same.

L2W-3 deliberately separates two concerns:

- a human-authored `RegistryPlan` decides identity membership, registry names,
  aliases, and the reason for each mapping;
- `pipeline.canon_registry` validates exact coverage, preserves every source
  claim, rewrites relations, and emits a `CanonRegistry` snapshot.

Conflicting or repeated claims are retained independently. L2W-3 does not choose
a winning fact, deduplicate equivalent prose, or modify any source draft.

## Input chain

```text
CanonDraft v1 (chapter A) ─┐
CanonDraft v1 (chapter B) ─┼─> build_canon_registry() ─> CanonRegistry v1
...                         │
RegistryPlan v1 ────────────┘
```

At least two drafts are required. Their `promotion_id` and source `chapter_id`
values must each be unique.

## RegistryPlan v1

```json
{
  "format_version": 1,
  "registry_id": "private_story_registry",
  "registry_version": 1,
  "entities": [
    {
      "entity_id": "canon_mira",
      "canonical_name": "Mira",
      "aliases": ["First Watcher", "Valley Watcher"],
      "members": [
        {
          "promotion_id": "promo_ch001",
          "source_entity_id": "source_mira"
        },
        {
          "promotion_id": "promo_ch002",
          "source_entity_id": "source_mira_later"
        }
      ],
      "merge_reason": "The reviewer identifies both chapter-local entities as the same person."
    }
  ]
}
```

### Exact coverage

The plan must map every entity from every input draft exactly once:

- a missing source entity is rejected;
- a source entity referenced more than once is rejected;
- an unknown `promotion_id` or `source_entity_id` is rejected;
- one registry entity may contain at most one member from each `promotion_id`;
- members with different `entity_type` values cannot be combined.

There is no name-based or alias-based automatic matching. Names are display
metadata; `(promotion_id, source_entity_id)` is the source identity.

### Registry names and aliases

`canonical_name` and `aliases` are explicit registry-level choices. Aliases are
NFKC + casefold + strip checked for duplicates and cannot normalize to the
canonical name. Original source names and aliases are copied into registry
members, so a registry-level naming choice cannot erase source wording.

`merge_reason` is required even for a one-member registry entity. It records why
the reviewer retained or combined that identity; it is not a fact claim.

## CanonRegistry v1

```json
{
  "format_version": 1,
  "registry_id": "private_story_registry",
  "registry_version": 1,
  "sources": [
    {
      "promotion_id": "promo_ch001",
      "chapter_id": "chapter_000001",
      "chapter_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "extracted_by": "extractor/v1",
      "review_id": "review_ch001",
      "reviewed_by": "human-reviewer"
    },
    {
      "promotion_id": "promo_ch002",
      "chapter_id": "chapter_000002",
      "chapter_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "extracted_by": "extractor/v1",
      "review_id": "review_ch002",
      "reviewed_by": "human-reviewer"
    }
  ],
  "entities": [
    {
      "entity_id": "canon_mira",
      "entity_type": "character",
      "canonical_name": "Mira",
      "aliases": ["First Watcher", "Valley Watcher"],
      "members": [
        {
          "promotion_id": "promo_ch001",
          "source_entity_id": "source_mira",
          "source_candidate_id": "candidate_mira",
          "source_canonical_name": "Mira",
          "source_aliases": ["First Watcher"]
        },
        {
          "promotion_id": "promo_ch002",
          "source_entity_id": "source_mira_later",
          "source_candidate_id": "candidate_mira_later",
          "source_canonical_name": "Mira of the Gate",
          "source_aliases": ["Valley Watcher"]
        }
      ],
      "claims": [
        {
          "source": {
            "promotion_id": "promo_ch001",
            "source_entity_id": "source_mira",
            "source_claim_id": "claim_role"
          },
          "predicate": "role",
          "value": {
            "kind": "enum",
            "enum_value": "watcher"
          },
          "source_chapters": ["chapter_000001"],
          "source_support": "explicit",
          "certainty": "certain",
          "inference_basis": null,
          "review_reason": "The chapter states the location directly."
        }
      ],
      "merge_reason": "The reviewer identifies both chapter-local entities as the same person."
    }
  ]
}
```

### Source preservation

Every registry claim retains the composite source key:

```text
(promotion_id, source_entity_id, source_claim_id)
```

This key, rather than `source_claim_id` alone, is unique. Two chapters may both
contain `claim_role`; both claims remain present and independently traceable.
`source_chapters[0]` must equal the chapter declared by the matching registry
source. Registry members also preserve both chapter-local identities. Within one
promotion, `source_entity_id` and `source_candidate_id` must each occur exactly
once across the registry, so a rewritten document cannot attach two source
entities to the same candidate provenance.

### Relation rewriting

A `CanonDraft` relation points to another entity in the same draft. During
assembly, the target `(promotion_id, entity_ref)` is looked up in the exact
RegistryPlan mapping and rewritten to the target registry `entity_id`. A missing
mapping or dangling registry relation is rejected. Because each registry entity
has at most one member from a promotion, the original chapter-local target remains
recoverable from the target registry entity's members. The validator therefore
requires every relation target to contain exactly one member whose `promotion_id`
matches the relation claim's source promotion; an existing registry ID from only
another chapter is not a valid target.

### Conflict behavior

The registry is a lossless reviewed-claim union, not a truth-resolution layer.
When two source claims use the same predicate but different values:

- both claims remain in deterministic source order;
- neither silently replaces the other;
- no new certainty or inference is generated;
- downstream work must make a separate, explicit resolution decision if needed.

## Deterministic ordering

| Collection | Canonical order |
|---|---|
| sources | `(chapter_id, promotion_id)` |
| registry entities | `entity_id` |
| aliases | NFKC + casefold + strip key |
| members | `(promotion_id, source_entity_id)` |
| claims | `(promotion_id, source_entity_id, source_claim_id)` |
| JSON object keys | `sort_keys=True` |

Changing input draft, plan entity, member, or alias order therefore does not
change the output bytes.

## CLI and atomic output

```powershell
python -m pipeline.canon_registry `
  --canon-draft canon_ch001.json `
  --canon-draft canon_ch002.json `
  --registry-plan registry_plan.json `
  --output canon_registry.json
```

`--canon-draft` must be supplied at least twice. The output cannot refer to the
same file as any input. All input and output validation completes before a
temporary file is created. The writer creates that file beside the destination,
writes UTF-8 JSON, flushes and fsyncs it, then uses `os.replace`; failures preserve
an existing output and clean up the invocation's temporary file.

## What v1 does not cover

- automatic entity matching from names or aliases;
- semantic claim deduplication or conflict resolution;
- mutable registry storage, incremental updates, indexing, or general queries;
  L2W-5 provides a separate explicit-ID, read-only
  [inspection report](registry_inspection_format.md) without changing registry v1;
- cross-registry references;
- adaptation of a registry into a multi-room game content pack;
- model or LLM integration;
- reading or committing private novel text.
