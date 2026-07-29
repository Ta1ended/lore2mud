"""Validated, immutable content definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias


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
class ExitDefinition:
    """One normalized room exit, optionally gated by an inventory item."""

    target_room_id: str
    required_item_id: str | None = None


@dataclass(frozen=True, slots=True)
class ItemStackDefinition:
    """Immutable stack reference used in content definitions."""
    item_id: str
    quantity: int = 1


@dataclass(frozen=True, slots=True)
class RoomDefinition:
    id: str
    name: str
    description: str
    exits: dict[str, ExitDefinition]
    item_stacks: tuple[ItemStackDefinition, ...] = ()
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
    stack_limit: int = 1
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
    loot_item: ItemStackDefinition | None = None
    metadata: ContentMetadata = field(default_factory=ContentMetadata)


@dataclass(frozen=True, slots=True)
class CharacterDefinition:
    id: str
    name: str
    description: str
    room_id: str
    metadata: ContentMetadata = field(default_factory=ContentMetadata)


@dataclass(frozen=True, slots=True)
class MonsterDefeatedQuestDefinition:
    """A quest completed when one specific monster has been defeated."""

    id: str
    name: str
    description: str
    trigger_room_id: str
    target_monster_id: str
    reward_experience: int
    kind: Literal["monster_defeated"] = field(
        init=False, default="monster_defeated"
    )
    metadata: ContentMetadata = field(default_factory=ContentMetadata)


@dataclass(frozen=True, slots=True)
class ReachRoomQuestDefinition:
    """A quest completed when the player reaches one specific room."""

    id: str
    name: str
    description: str
    trigger_room_id: str
    target_room_id: str
    reward_experience: int
    kind: Literal["reach_room"] = field(init=False, default="reach_room")
    metadata: ContentMetadata = field(default_factory=ContentMetadata)


@dataclass(frozen=True, slots=True)
class CollectItemQuestDefinition:
    """A quest completed when the inventory holds a required item quantity."""

    id: str
    name: str
    description: str
    trigger_room_id: str
    target_item_id: str
    required_quantity: int
    reward_experience: int
    kind: Literal["collect_item"] = field(init=False, default="collect_item")
    metadata: ContentMetadata = field(default_factory=ContentMetadata)


QuestDefinition: TypeAlias = (
    MonsterDefeatedQuestDefinition
    | ReachRoomQuestDefinition
    | CollectItemQuestDefinition
)


@dataclass(frozen=True, slots=True)
class DialogueOption:
    id: str
    text: str
    next_node_id: str | None = None
    grant_item: ItemStackDefinition | None = None


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
