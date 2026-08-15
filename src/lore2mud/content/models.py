"""Validated, immutable content definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias

from lore2mud.narrative.models import (
    NarrativeCondition,
    NarrativeStateDefinition,
)


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
    droppable: bool = True
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
class GrantItemEffect:
    """Award one validated, non-consumable typed item stack."""

    item_id: str
    quantity: int
    kind: Literal["grant_item"] = field(init=False, default="grant_item")


@dataclass(frozen=True, slots=True)
class GrantExperienceEffect:
    """Award deterministic experience through the progression service."""

    amount: int
    kind: Literal["grant_experience"] = field(
        init=False, default="grant_experience"
    )


@dataclass(frozen=True, slots=True)
class AcceptQuestEffect:
    """Explicitly accept one quest, independently of its trigger room."""

    quest_id: str
    kind: Literal["accept_quest"] = field(
        init=False, default="accept_quest"
    )


@dataclass(frozen=True, slots=True)
class SetFlagEffect:
    """Upsert one World-owned boolean flag."""

    flag_id: str
    value: bool
    kind: Literal["set_flag"] = field(init=False, default="set_flag")


DialogueEffect: TypeAlias = (
    GrantItemEffect
    | GrantExperienceEffect
    | AcceptQuestEffect
    | SetFlagEffect
)


@dataclass(frozen=True, slots=True)
class SetNarrativeStateEffect:
    state_id: str
    value: bool | int | str
    kind: Literal["set_narrative_state"] = field(
        init=False, default="set_narrative_state"
    )


@dataclass(frozen=True, slots=True)
class AdjustNarrativeStateEffect:
    state_id: str
    amount: int
    kind: Literal["adjust_narrative_state"] = field(
        init=False, default="adjust_narrative_state"
    )


@dataclass(frozen=True, slots=True)
class RemoveItemEffect:
    item_id: str
    quantity: int
    kind: Literal["remove_item"] = field(init=False, default="remove_item")


@dataclass(frozen=True, slots=True)
class MoveActorEffect:
    actor_id: str
    location_id: str | None = None
    presence: Literal["present", "absent"] | None = None
    enabled: bool | None = None
    incapacitated: bool | None = None
    kind: Literal["move_actor"] = field(init=False, default="move_actor")


@dataclass(frozen=True, slots=True)
class AdvanceSceneEffect:
    scene_id: str
    transition: Literal["activate", "advance", "complete"]
    kind: Literal["advance_scene"] = field(init=False, default="advance_scene")


@dataclass(frozen=True, slots=True)
class AdvanceObjectiveEffect:
    objective_id: str
    transition: Literal["activate", "start", "complete", "fail"]
    kind: Literal["advance_objective"] = field(
        init=False, default="advance_objective"
    )


@dataclass(frozen=True, slots=True)
class RevealKnowledgeEffect:
    knowledge_id: str
    status: Literal["heard", "suspected", "confirmed"]
    kind: Literal["reveal_knowledge"] = field(
        init=False, default="reveal_knowledge"
    )


@dataclass(frozen=True, slots=True)
class RetractKnowledgeEffect:
    knowledge_id: str
    kind: Literal["retract_knowledge"] = field(
        init=False, default="retract_knowledge"
    )


@dataclass(frozen=True, slots=True)
class CorrectKnowledgeEffect:
    knowledge_id: str
    kind: Literal["correct_knowledge"] = field(
        init=False, default="correct_knowledge"
    )


CampaignEffect: TypeAlias = (
    DialogueEffect
    | SetNarrativeStateEffect
    | AdjustNarrativeStateEffect
    | RemoveItemEffect
    | MoveActorEffect
    | AdvanceSceneEffect
    | AdvanceObjectiveEffect
    | RevealKnowledgeEffect
    | RetractKnowledgeEffect
    | CorrectKnowledgeEffect
)


@dataclass(frozen=True, slots=True)
class ConditionalText:
    text: str
    condition: NarrativeCondition | None = None


@dataclass(frozen=True, slots=True)
class LocationViewDefinition:
    location_id: str
    descriptions: tuple[ConditionalText, ...] = ()
    exit_conditions: dict[str, NarrativeCondition] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ActorViewDefinition:
    actor_id: str
    descriptions: tuple[ConditionalText, ...] = ()
    condition: NarrativeCondition | None = None


@dataclass(frozen=True, slots=True)
class DialogueNodeViewDefinition:
    node_id: str
    texts: tuple[ConditionalText, ...]


@dataclass(frozen=True, slots=True)
class DialogueViewDefinition:
    dialogue_id: str
    nodes: dict[str, DialogueNodeViewDefinition]


SceneStatus: TypeAlias = Literal["inactive", "active", "completed"]
ObjectiveStatus: TypeAlias = Literal[
    "inactive", "active", "in_progress", "completed", "failed"
]
KnowledgeStatus: TypeAlias = Literal[
    "unknown", "heard", "suspected", "confirmed", "retracted", "corrected"
]


@dataclass(frozen=True, slots=True)
class SceneStageDefinition:
    id: str
    descriptions: tuple[ConditionalText, ...]
    interactable_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SceneDefinition:
    id: str
    name: str
    location_id: str
    stages: tuple[SceneStageDefinition, ...]
    initial_status: Literal["inactive", "active"] = "inactive"
    condition: NarrativeCondition | None = None


@dataclass(frozen=True, slots=True)
class InteractableDefinition:
    id: str
    name: str
    kind: Literal["actor", "location", "object", "ritual", "inner"]
    action_ids: tuple[str, ...]
    descriptions: tuple[ConditionalText, ...]
    target_id: str | None = None
    location_id: str | None = None
    scene_id: str | None = None
    condition: NarrativeCondition | None = None


@dataclass(frozen=True, slots=True)
class CampaignActionDefinition:
    id: str
    label: str
    result_text: str
    effects: tuple[CampaignEffect, ...]
    condition: NarrativeCondition | None = None


@dataclass(frozen=True, slots=True)
class ObjectiveDefinition:
    id: str
    title: str
    description: str
    initial_status: Literal["inactive", "active"] = "inactive"
    dependency_ids: tuple[str, ...] = ()
    exclusive_with: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class KnowledgeDefinition:
    id: str
    title: str
    texts: dict[str, str]
    initial_status: KnowledgeStatus = "unknown"


@dataclass(frozen=True, slots=True)
class LogEntryDefinition:
    id: str
    category: Literal["story", "objective", "knowledge"]
    texts: tuple[ConditionalText, ...]
    condition: NarrativeCondition | None = None
    title: str | None = None
    terminal: bool = False


@dataclass(frozen=True, slots=True)
class CampaignDefinition:
    location_views: dict[str, LocationViewDefinition] = field(default_factory=dict)
    actor_views: dict[str, ActorViewDefinition] = field(default_factory=dict)
    dialogue_views: dict[str, DialogueViewDefinition] = field(default_factory=dict)
    scenes: dict[str, SceneDefinition] = field(default_factory=dict)
    interactables: dict[str, InteractableDefinition] = field(default_factory=dict)
    actions: dict[str, CampaignActionDefinition] = field(default_factory=dict)
    objectives: dict[str, ObjectiveDefinition] = field(default_factory=dict)
    knowledge: dict[str, KnowledgeDefinition] = field(default_factory=dict)
    log_entries: dict[str, LogEntryDefinition] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DialogueOption:
    id: str
    text: str
    next_node_id: str | None = None
    effects: tuple[DialogueEffect, ...] = ()
    condition: NarrativeCondition | None = None


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
    coins: int = 0


@dataclass(frozen=True, slots=True)
class ShopListingDefinition:
    """One immutable fixed-price item listing in a shop catalog."""

    item_id: str
    buy_price: int
    sell_price: int


@dataclass(frozen=True, slots=True)
class ShopDefinition:
    """An immutable, unlimited-supply catalog located in one room."""

    id: str
    name: str
    room_id: str
    catalog: tuple[ShopListingDefinition, ...]
    metadata: ContentMetadata = field(default_factory=ContentMetadata)


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
    shops: dict[str, ShopDefinition] = field(default_factory=dict)
    narrative_state_defs: dict[str, NarrativeStateDefinition] = field(
        default_factory=dict
    )
    campaign: CampaignDefinition | None = None
    extensions: dict[str, Any] = field(default_factory=dict)
