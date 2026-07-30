# Adaptation Plan Format v1 (L2W-2)

## Overview

An AdaptationPlan is a human-written JSON document that maps a single-chapter
CanonDraft into a playable micro content pack (1 room, 1 character, 1 item,
1 dialogue, 1 quest).  It is the only place where game-oriented values
(display text, attributes, IDs) are specified — the compiler never infers
game values from canon lore.

## Input Pipeline

```
CanonDraft (from L2W-1)     ─┐
AdaptationPlan (human-written) ─┤  → compile_micro_pack() → MicroContentPack
                                 │
                                 └  → write_micro_pack() → output-dir (9 files)
```

## AdaptationPlan Structure

```json
{
  "format_version": 1,
  "adaptation_id": "adapt_fog_village",
  "source_promotion_id": "promo_fog_ch001",
  "source_chapter": "chapter_000001",
  "pack": {
    "id": "fog_village_micro",
    "name": "雾岭微场景",
    "version": "0.1.0",
    "start_room_id": "room_fog_village",
    "player": { "max_hp": 20, "attack": 5, "defense": 1, "inventory_capacity": 20, "coins": 0 }
  },
  "room": {
    "canon_entity_ref": "canon_loc_fog_ridge",
    "game_id": "room_fog_village",
    "name": "雾岭小村",
    "description": "一个安静的小山村。",
    "canon_claim_refs": [],
    "adaptation_notes": "唯一房间，无出口。"
  },
  "character": {
    "canon_entity_ref": "canon_char_fog_villager",
    "game_id": "char_old_villager",
    "name": "老村民",
    "description": "一位老人。",
    "canon_claim_refs": ["claim_origin"],
    "adaptation_notes": "叙事 NPC。"
  },
  "item": {
    "canon_entity_ref": "canon_item_herb",
    "game_id": "item_fog_herb",
    "name": "草药",
    "description": "一束干燥草药。",
    "canon_claim_refs": [],
    "adaptation_notes": "普通收集物品。"
  },
  "quest": {
    "game_id": "quest_collect_herb",
    "kind": "collect_item",
    "name": "草药任务",
    "description": "收集草药。",
    "target_item_id": "item_fog_herb",
    "required_quantity": 1,
    "reward_experience": 10,
    "adaptation_notes": "自动接取。"
  },
  "dialogue": {
    "game_id": "dialogue_old_villager",
    "character_id": "char_old_villager",
    "start_node_id": "start",
    "nodes": [
      {
        "id": "start",
        "text": "你好，年轻人。",
        "options": [
          {"id": "opt_leave", "text": "再会。", "next_node_id": null, "effects": []}
        ]
      }
    ],
    "adaptation_notes": "纯叙事交互。"
  },
  "omissions": [
    {"canon_entity_ref": "canon_extra", "reason": "不在微场景范围内。"}
  ]
}
```

## Compilation Rules

### Text Fidelity

All text fields in the plan are copied verbatim into the output. The compiler
never trims, rewrites, appends NPC/item/quest hints, or concatenates text.

### Output Files (9)

| File | Content |
|------|---------|
| `pack.json` | pack metadata + extensions.canon_provider |
| `rooms.json` | 1 room with item_stacks, empty exits/monsters |
| `items.json` | 1 plain item (only id/name/description/stack_limit) |
| `characters.json` | 1 character at the start room |
| `quests.json` | 1 collect_item quest (auto-accepted via trigger_room) |
| `dialogues.json` | 1 dialogue with effects=[] on all options |
| `monsters.json` | `[]` |
| `shops.json` | `[]` |
| `adaptation_manifest.json` | Provenance sidecar |

### Items

Items are plain collectibles — no heal_amount, slot, attack_bonus, or
defense_bonus fields are output.

### Quest

The quest's `trigger_room_id` is always set to `pack.start_room_id`, so the
World auto-accepts it on initialization.  No `accept_quest` effect appears in
dialogue.

### Dialogue

- `nodes` is a JSON array, not an object
- Every option has `effects: []`
- `start_node_id` must reference an existing node
- Option order is preserved (it determines player input 1/2/3)

### Provenance

- `rooms/items/characters` include `canon_ref` and `adaptation_notes`
- `quests/dialogues` omit `canon_ref` entirely and include
  `adaptation_notes` explaining they are game-only designs
- `adaptation_manifest.json` records full provenance including omissions

## AdaptationManifest

The manifest is a provenance sidecar:

```json
{
  "format_version": 1,
  "adaptation_id": "adapt_fog_village",
  "source": {
    "promotion_id": "promo_fog_ch001",
    "chapter_id": "chapter_000001",
    "chapter_sha256": "a1b2c3..."
  },
  "pack": { "id": "fog_village_micro", "version": "0.1.0" },
  "bindings": [
    { "game_kind": "room", "game_id": "room_fog_village",
      "canon_entity_ref": "canon_loc_fog_ridge",
      "canon_claim_refs": [], "adaptation_notes": "..." },
    { "game_kind": "character", "game_id": "char_old_villager",
      "canon_entity_ref": "canon_char_fog_villager",
      "canon_claim_refs": ["claim_origin"], "adaptation_notes": "..." },
    { "game_kind": "item", "game_id": "item_fog_herb",
      "canon_entity_ref": "canon_item_herb",
      "canon_claim_refs": [], "adaptation_notes": "..." }
  ],
  "omissions": [...],
  "game_only": [
    { "game_kind": "quest", "game_id": "quest_collect_herb",
      "adaptation_notes": "自动接取。" },
    { "game_kind": "dialogue", "game_id": "dialogue_old_villager",
      "adaptation_notes": "纯叙事交互。" }
  ]
}
```

## What v1 does NOT cover

- Multiple rooms, characters, items, dialogues, or quests
- Monsters, shops, equipment, consumables
- Dialogue effects (grant_item, accept_quest, etc.)
- Cross-chapter entity merging or conflict resolution
- Formal canon registry
- LLM or model integration
