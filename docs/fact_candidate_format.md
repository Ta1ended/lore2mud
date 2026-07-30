# Fact Candidate Document Format v1

## Overview

A fact-candidate document is a structured envelope for facts extracted from
a single novel chapter.  Each document contains a flat list of **candidates**
(entities, locations, events, etc.) and each candidate carries one or more
**claims** (individual facts about that entity).

The format is designed so that:

- Every fact is traceable to exactly one source chapter.
- Evidence dimensions are explicit and independent.
- Cross-references within a document use stable IDs, not display names.
- The structure can be validated without reading any private source material.

## Document envelope

```json
{
  "format_version": 1,
  "source_chapter": "chapter_000001",
  "extracted_by": "tool-name/version",
  "candidates": [ ... ]
}
```

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `format_version` | int | yes | Must be exactly `1`. `true`/`false` rejected. |
| `source_chapter` | string | yes | Must match `^chapter_[0-9]{6}$`. |
| `extracted_by` | string | yes | Non-blank after stripping. |
| `candidates` | array | yes | Non-empty. Each element is a candidate object. |

Unknown top-level fields are rejected.

## Candidate

```json
{
  "candidate_id": "character_fog_villager",
  "entity_type": "character",
  "proposed_entity_id": "character_fog_villager",
  "display_name": "雾岭村民",
  "aliases": ["老村民"],
  "claims": [ ... ]
}
```

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `candidate_id` | string | yes | Stable ID: `^[a-z][a-z0-9_]*$`. Unique within the document. |
| `entity_type` | string | yes | One of: `character`, `location`, `organization`, `skill`, `item`, `event`. |
| `proposed_entity_id` | string \| null | yes (key must be present) | If non-null, must match stable ID format. This is a *proposal*, not an authoritative ID. |
| `display_name` | string | yes | Non-blank. |
| `aliases` | array of string | yes (may be empty) | Each element non-blank. Checked for NFKC+casefold+strip duplicates *within this candidate only*. Original values are never modified. |
| `claims` | array | yes | Non-empty. Each element is a claim object. |

### ID generation

`candidate_id` is **not** derived from `display_name`.  The ID generation
strategy is left to the extraction tool.  The validator only checks format
and uniqueness.

## Claim

```json
{
  "claim_id": "claim_fog_villager_origin",
  "predicate": "origin",
  "value": { "kind": "text", "text": "出身于雾岭小村。" },
  "source_chapters": ["chapter_000001"],
  "source_support": "explicit",
  "certainty": "certain",
  "inference_basis": null
}
```

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `claim_id` | string | yes | Stable ID. Unique within the parent candidate. |
| `predicate` | string | yes | Stable ID. Semantic label for the relationship or attribute. |
| `value` | tagged union | yes | See [Value branches](#value-branches). |
| `source_chapters` | array of string | yes | Must be exactly `[document.source_chapter]` — a single-element array matching the document's `source_chapter`. |
| `source_support` | string | yes | `explicit` or `inferred`. |
| `certainty` | string | yes | `certain` or `uncertain`. |
| `inference_basis` | string \| null | yes (key must be present) | Required non-blank string when `source_support` is `inferred`. Must be `null` otherwise. |

### Evidence dimensions

Two independent dimensions describe each claim:

| Dimension | Values | Meaning |
|-----------|--------|---------|
| `source_support` | `explicit` | The fact is directly stated in the source chapter. |
| `source_support` | `inferred` | The fact is inferred from context by the extraction tool. |
| `certainty` | `certain` | The extraction tool considers this certain. |
| `certainty` | `uncertain` | The extraction tool is unsure (e.g. ambiguous pronouns, missing subject). |

**Key distinction:** "extracted by a model" ≠ `inferred`.  A model can
extract `explicit` claims when the source text directly states them.
`inferred` means the source does not directly state the fact.

## Value branches

Each `value` is a tagged union with a `kind` discriminator.  Every branch
rejects unknown fields.

### text

```json
{ "kind": "text", "text": "自由文本。" }
```

| Field | Type | Constraint |
|-------|------|------------|
| `kind` | `"text"` | literal |
| `text` | string | non-blank |

### relation

```json
{ "kind": "relation", "candidate_ref": "character_other" }
```

| Field | Type | Constraint |
|-------|------|------------|
| `kind` | `"relation"` | literal |
| `candidate_ref` | string | Stable ID. Must reference a `candidate_id` in the same document. |

The semantic relationship type is encoded in `Claim.predicate`, not in
the value.

### numeric

```json
{ "kind": "numeric", "number": 42, "unit": "years" }
```

| Field | Type | Constraint |
|-------|------|------------|
| `kind` | `"numeric"` | literal |
| `number` | int or float | Must not be `bool`. Must be finite (no NaN, no ±Inf). |
| `unit` | string \| null | If non-null, must match stable ID format. |

### boolean

```json
{ "kind": "boolean", "flag": true }
```

| Field | Type | Constraint |
|-------|------|------------|
| `kind` | `"boolean"` | literal |
| `flag` | boolean | Must be a true JSON `true`/`false`. Integer `0`/`1` rejected. |

### enum

```json
{ "kind": "enum", "enum_value": "elder" }
```

| Field | Type | Constraint |
|-------|------|------------|
| `kind` | `"enum"` | literal |
| `enum_value` | string | Must match stable ID format. |

## Stable ID format

All IDs (`candidate_id`, `claim_id`, `predicate`, `proposed_entity_id`,
`candidate_ref`, `enum_value`, and non-null `unit`) must match:

```
^[a-z][a-z0-9_]*$
```

Lowercase ASCII letter start, followed by lowercase letters, digits, or
underscores.  No hyphens, no uppercase, no leading digits.

## What v1 does NOT contain

The following are explicitly excluded from v1 and reserved for future
slices:

- `confidence` numeric scores
- `created_at` / `updated_at` timestamps
- `review_status` (pending / approved / rejected / superseded)
- Claim-level accepted / rejected / superseded / conflicted states
- Candidate-level duplicate markers
- Claim-to-claim conflict references
- Canon promotion / writing
- Entity ID central registry

## Validation

```python
from pipeline.fact_candidates import validate_fact_candidate_document

doc = validate_fact_candidate_document(parsed_json_dict)
# Returns FactCandidateDocument on success
# Raises FactCandidateValidationError on failure
```

The validator performs structural checks and bounded semantic checks (ID dedup,
NFKC alias dedup, relation cross-reference, source_chapter equality, bool/int
discrimination, finite float).  It does not read files,
access private data, or validate against a manifest.

## Schema

`schemas/fact_candidate.schema.json` provides a JSON Schema (draft 2020-12)
for editor hints and documentation.  The Python validator adds semantic
checks that the Schema cannot express:

- `candidate_id` / `claim_id` uniqueness within their scope
- NFKC + casefold + strip alias deduplication
- `relation.candidate_ref` cross-reference to existing `candidate_id`
- `source_chapters` equality with `document.source_chapter`
- `bool` rejection for `format_version` and `value.numeric.number`
- `NaN` / `Infinity` rejection for floats

## Source binding

After a `FactCandidateDocument` is validated, its `source_chapter` can be
checked against a validated `ChapterManifest`:

```python
from pipeline.chapter_manifests import validate_fact_candidate_sources

validated = validate_fact_candidate_sources(manifest, [doc1, doc2])
```

This ensures every extraction document references a chapter that exists in
the manifest. Multiple documents per chapter are allowed; no deduplication
or merging is performed.
