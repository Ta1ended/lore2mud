"""Validated, immutable content definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class CanonReference:
    """Optional pointer to facts stored outside the game-rules content pack."""

    entity_id: str
    source_chapters: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ContentMetadata:
    canon_ref: CanonReference | None = None
    adaptation_notes: str | None = None


@dataclass(frozen=True, slots=True)
class RoomDefinition:
    id: str
    name: str
    description: str
    exits: dict[str, str]
    item_ids: tuple[str, ...] = ()
    monster_ids: tuple[str, ...] = ()
    metadata: ContentMetadata = field(default_factory=ContentMetadata)


@dataclass(frozen=True, slots=True)
class ItemDefinition:
    id: str
    name: str
    description: str
    heal_amount: int | None = None
    slot: str | None = None
    attack_bonus: int = 0
    defense_bonus: int = 0
    metadata: ContentMetadata = field(default_factory=ContentMetadata)


@dataclass(frozen=True, slots=True)
class MonsterDefinition:
    id: str
    name: str
    description: str
    room_id: str
    max_hp: int
    attack: int
    defense: int
    experience_reward: int
    metadata: ContentMetadata = field(default_factory=ContentMetadata)


@dataclass(frozen=True, slots=True)
class CharacterDefinition:
    id: str
    name: str
    description: str
    room_id: str
    metadata: ContentMetadata = field(default_factory=ContentMetadata)


@dataclass(frozen=True, slots=True)
class QuestDefinition:
    id: str
    name: str
    description: str
    trigger_room_id: str
    target_monster_id: str
    reward_experience: int
    metadata: ContentMetadata = field(default_factory=ContentMetadata)


@dataclass(frozen=True, slots=True)
class DialogueOption:
    id: str
    text: str
    next_node_id: str | None = None


@dataclass(frozen=True, slots=True)
class DialogueNode:
    id: str
    text: str
    options: tuple[DialogueOption, ...] = ()


@dataclass(frozen=True, slots=True)
class DialogueDefinition:
    id: str
    character_id: str
    start_node_id: str
    nodes: dict[str, DialogueNode]
    metadata: ContentMetadata = field(default_factory=ContentMetadata)


@dataclass(frozen=True, slots=True)
class PlayerDefaults:
    max_hp: int = 20
    attack: int = 5
    defense: int = 1
    inventory_capacity: int = 20


@dataclass(frozen=True, slots=True)
class ContentPack:
    id: str
    name: str
    version: str
    start_room_id: str
    player: PlayerDefaults
    rooms: dict[str, RoomDefinition]
    items: dict[str, ItemDefinition]
    monsters: dict[str, MonsterDefinition]
    characters: dict[str, CharacterDefinition]
    quests: dict[str, QuestDefinition]
    dialogues: dict[str, DialogueDefinition] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)
