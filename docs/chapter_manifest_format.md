# Chapter Manifest Format v2

## Overview

A chapter manifest describes the metadata of split novel chapters. It is
produced by `pipeline/build_manifest.py` from either the primary split path
(with full metadata) or the scan-compat path (with limited fields).

## Root object

```json
{
  "format_version": 2,
  "source_encoding": "gbk",
  "chapter_count": 3,
  "chapters": [ ... ]
}
```

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `format_version` | int | yes | Must be exactly `2`. Bool rejected. |
| `source_encoding` | string \| null | yes | `null` for scan-compat; one of `utf-8-sig`, `utf-8`, `gbk`, `gb18030` for primary. |
| `chapter_count` | int | yes | Non-negative. Must equal `chapters` array length. Bool rejected. |
| `chapters` | array | yes | May be empty (scan of empty directory). |

## Chapter entry

Each entry has exactly 12 fields. Unknown fields are rejected.

| Field | Type | Primary | Scan |
|-------|------|---------|------|
| `chapter_id` | string | `^chapter_[0-9]{6}$`, unique, consecutive | same |
| `title` | string | non-blank | non-blank |
| `source_chapter_label` | string \| null | non-blank string | must be null |
| `source_title` | string \| null | string (allows empty) | must be null |
| `volume_label` | string \| null | non-blank or null | must be null |
| `source_offset` | int \| null | non-negative int | must be null |
| `source_line` | int \| null | positive int (≥1) | must be null |
| `path` | string | `<chapter_id>.txt` | same |
| `character_count` | int | non-negative | same |
| `sha256` | string | 64 lowercase hex | same |
| `previous_id` | string \| null | chain adjacency | same |
| `next_id` | string \| null | chain adjacency | same |

### Semantic constraints (Python only)

- `chapter_id` must be consecutive from `chapter_000001`.
- `previous_id` of entry `[i]` must equal `chapters[i-1].chapter_id` (null for first).
- `next_id` of entry `[i]` must equal `chapters[i+1].chapter_id` (null for last).
- In primary path, `source_offset` must strictly increase across entries.
- In primary path, `source_line` must strictly increase across entries.
- `path` must not contain `/`, `\`, `..`, or start with `/`.

## Two paths

`build_manifest` produces two compatible shapes:

1. **Primary path** (`_build_from_chapters`): `source_encoding` is non-null;
   all 5 conditional fields are populated.
2. **Scan path** (`_build_from_scan`): `source_encoding` is null;
   all 5 conditional fields are null.

The validator enforces the correct set based on `source_encoding`.

## Validation

```python
from pipeline.chapter_manifests import validate_chapter_manifest

manifest = validate_chapter_manifest(parsed_json_dict)
# Returns ChapterManifest on success
# Raises ChapterManifestValidationError on failure
```

## Source binding

```python
from pipeline.chapter_manifests import validate_fact_candidate_sources

validated = validate_fact_candidate_sources(manifest, documents)
# Returns tuple[FactCandidateDocument, ...]
# Raises FactCandidateSourceValidationError if any document.source_chapter
# is not in manifest.chapter_ids
```

## Schema

`schemas/chapter_manifest.schema.json` (draft 2020-12) expresses structural
constraints. Python adds: consecutive IDs, chain adjacency, count equality,
monotonic offset/line, and path safety checks.
