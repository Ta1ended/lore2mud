# Registry Adaptation Format v1 (L2W-4)

## Overview

L2W-4 is a deliberately small bridge from a validated `CanonRegistry v1` to the
same playable profile as L2W-2: one room, one character, one plain item, one
game-only collect quest, and one game-only dialogue. It does not replace or
change the `CanonDraft + AdaptationPlan v1` compiler. The registry route is a
separate module and a separate plan/manifest contract.

```text
CanonRegistry v1 + RegistryAdaptationPlan v1
        -> compile_registry_micro_pack()
        -> write_registry_micro_pack() -> 9 JSON files
        -> load_content_pack() -> World.from_content_pack()
```

The plan is human-authored. Every game-facing string, number, and ID comes from
the plan verbatim. Registry claims are used only to validate explicit coverage
and to carry provenance; the compiler never resolves a conflict, infers a value,
rewrites claim text, or generates game text.

## RegistryAdaptationPlan v1

The root fields are:

| Field | Meaning |
|---|---|
| `format_version` | Must be `1`. |
| `adaptation_id` | Stable plan ID. |
| `source_registry_id` | Exact input registry ID. |
| `source_registry_version` | Exact input registry version. |
| `pack` | L2W-2-compatible pack/player profile. |
| `room`, `character`, `item` | One explicit registry entity binding each. |
| `quest`, `dialogue` | Game-only L2W-2 profile entries. |
| `omissions` | Explicit registry entity IDs outside this slice. |

Each adapted entity has this shape:

```json
{
  "registry_entity_ref": "canon_lyra",
  "game_id": "character_lyra",
  "name": "Lyra",
  "description": "Game text written by the plan.",
  "registry_claim_refs": [
    {
      "promotion_id": "promo_ch001",
      "source_entity_id": "source_lyra_early",
      "source_claim_id": "claim_role"
    }
  ],
  "adaptation_notes": "Why this binding is in the micro slice."
}
```

The three fields in a claim reference are a composite identity. A bare
`source_claim_id` is never sufficient because different promotions may reuse the
same local claim ID. Every claim on each selected registry entity must appear
exactly once in its binding. Every other registry entity must appear exactly
once in `omissions`. Selected claims must span at least two promotions for this
multi-chapter slice.

The compiler enforces these type bindings:

| Plan entry | Registry entity type |
|---|---|
| `room` | `location` |
| `character` | `character` |
| `item` | `item` |

There is exactly one distinct game ID for each of the five output entities.
`pack.start_room_id`, `dialogue.character_id`, and
`quest.target_item_id` must point to the corresponding plan IDs. The quest is
`collect_item` with quantity `1`; dialogue options must have `effects: []`.

## Provenance manifest

The output sidecar is named `registry_adaptation_manifest.json`. It contains:

- `source_registry_id` and `source_registry_version`;
- every complete registry source record (promotion, chapter, hash, extractor,
  review, and reviewer);
- three sorted bindings with composite `registry_claim_refs`;
- `source_chapters` for each binding;
- explicit omissions and the two game-only entries.

`source_chapters` is derived from the selected registry claims. The manifest
validator independently maps each claim reference's `promotion_id` through the
complete source list and requires the declared chapter set to match exactly.
For example, a character with one selected claim from each of chapters 1 and 2
must expose both chapters, even when the game description is one sentence.
Conflicting claims remain visible as separate composite references in the
manifest; no value is chosen or merged.

The three content entities carry:

```json
"canon_ref": {
  "entity_id": "canon_lyra",
  "source_chapters": ["chapter_000001", "chapter_000002"]
}
```

Game-only quests and dialogues intentionally have no `canon_ref`.

## Output and atomic writer

The writer emits exactly these files with deterministic UTF-8 JSON (`sort_keys`,
two-space indentation, one trailing LF):

```text
pack.json
rooms.json
items.json
characters.json
quests.json
dialogues.json
monsters.json
shops.json
registry_adaptation_manifest.json
```

`pack.json.extensions.canon_provider` is:

```json
{
  "kind": "registry_adaptation_manifest",
  "format_version": 1,
  "path": "registry_adaptation_manifest.json"
}
```

Documents and the manifest are prevalidated before a staging directory is
created. The writer then writes, flushes, and fsyncs all nine files, loads the
staged pack through the existing content loader, revalidates the staged
manifest, checks the destination a second time, and publishes with
`os.replace`. Existing outputs are never overwritten. A failure removes only
the invocation-owned staging directory.

## CLI

```powershell
python -m pipeline.registry_adaptation `
  --canon-registry tests/fixtures/registry_adaptation/canon_registry.json `
  --adaptation-plan tests/fixtures/registry_adaptation/valid_plan.json `
  --output-dir C:\Temp\registry_micro_demo
```

The generated directory can be checked with:

```powershell
python -m lore2mud validate --content C:\Temp\registry_micro_demo
```

## Deliberate limits

- one room, one character, one item, one collect quest, and one dialogue only;
- no monsters, shops, equipment, consumables, dialogue effects, or save changes;
- no semantic conflict resolution, inference, mutable registry/query layer, or
  multi-room expansion;
- no private novel input, private canon, summaries, or generated private content;
- no changes to `src/`, the original demo, the existing L2W-2 compiler, or
  dependencies.
