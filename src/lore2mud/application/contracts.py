"""Typed, transport-neutral application contracts for one game turn."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias

from lore2mud.capabilities.contracts import (
    CapabilityEventData,
    CapabilityPlayerViewEntry,
)


class TurnStatus(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class RejectionCode(str, Enum):
    MALFORMED_INTENT = "malformed_intent"
    INADMISSIBLE_INTENT = "inadmissible_intent"
    PERSISTENCE_ERROR = "persistence_error"
    CAPABILITY_INTENT_INVALID = "capability_intent_invalid"
    CAPABILITY_INTENT_INADMISSIBLE = "capability_intent_inadmissible"


class ViewKind(str, Enum):
    LOOK = "look"
    INVENTORY = "inventory"
    CAMPAIGN_ACTIONS = "campaign_actions"
    OBJECTIVES = "objectives"
    KNOWLEDGE = "knowledge"
    JOURNAL = "journal"
    QUESTS = "quests"
    STATUS = "status"
    SHOP = "shop"


class ExamineTargetKind(str, Enum):
    ITEM = "item"
    MONSTER = "monster"
    CHARACTER = "character"


class EquipmentSlot(str, Enum):
    HAND = "hand"
    BODY = "body"


class QuestKind(str, Enum):
    MONSTER_DEFEATED = "monster_defeated"
    REACH_ROOM = "reach_room"
    COLLECT_ITEM = "collect_item"


class SceneStatus(str, Enum):
    INACTIVE = "inactive"
    ACTIVE = "active"
    COMPLETED = "completed"


class ObjectiveStatus(str, Enum):
    INACTIVE = "inactive"
    ACTIVE = "active"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class KnowledgeStatus(str, Enum):
    UNKNOWN = "unknown"
    HEARD = "heard"
    SUSPECTED = "suspected"
    CONFIRMED = "confirmed"
    RETRACTED = "retracted"
    CORRECTED = "corrected"


class JournalCategory(str, Enum):
    STORY = "story"
    OBJECTIVE = "objective"
    KNOWLEDGE = "knowledge"


class InteractableKind(str, Enum):
    ACTOR = "actor"
    LOCATION = "location"
    OBJECT = "object"
    RITUAL = "ritual"
    INNER = "inner"


@dataclass(frozen=True, slots=True)
class GameIntent:
    """Closed base type for deterministic requests understood by ``GameSession``."""


@dataclass(frozen=True, slots=True)
class ViewIntent(GameIntent):
    kind: ViewKind


@dataclass(frozen=True, slots=True)
class ExamineIntent(GameIntent):
    target: str
    target_kind: ExamineTargetKind | None = None


@dataclass(frozen=True, slots=True)
class MoveIntent(GameIntent):
    direction: str


@dataclass(frozen=True, slots=True)
class TakeIntent(GameIntent):
    target: str
    quantity: int = 1


@dataclass(frozen=True, slots=True)
class DropIntent(GameIntent):
    target: str
    quantity: int = 1


@dataclass(frozen=True, slots=True)
class UseIntent(GameIntent):
    target: str
    quantity: int = 1


@dataclass(frozen=True, slots=True)
class EquipIntent(GameIntent):
    target: str


@dataclass(frozen=True, slots=True)
class UnequipIntent(GameIntent):
    slot: EquipmentSlot = EquipmentSlot.HAND


@dataclass(frozen=True, slots=True)
class AttackIntent(GameIntent):
    target: str


@dataclass(frozen=True, slots=True)
class TalkIntent(GameIntent):
    target: str


@dataclass(frozen=True, slots=True)
class ChooseDialogueIntent(GameIntent):
    index: int


@dataclass(frozen=True, slots=True)
class EndDialogueIntent(GameIntent):
    pass


@dataclass(frozen=True, slots=True)
class BuyIntent(GameIntent):
    target: str
    quantity: int = 1


@dataclass(frozen=True, slots=True)
class SellIntent(GameIntent):
    target: str
    quantity: int = 1


@dataclass(frozen=True, slots=True)
class CampaignActionIntent(GameIntent):
    action_id: str


@dataclass(frozen=True, slots=True)
class RecoverIntent(GameIntent):
    pass


@dataclass(frozen=True, slots=True)
class SaveIntent(GameIntent):
    slot: str | None = None


@dataclass(frozen=True, slots=True)
class LoadIntent(GameIntent):
    slot: str | None = None


_DECLARED_GAME_INTENT_TYPES: tuple[type[GameIntent], ...] = (
    ViewIntent,
    ExamineIntent,
    MoveIntent,
    TakeIntent,
    DropIntent,
    UseIntent,
    EquipIntent,
    UnequipIntent,
    AttackIntent,
    TalkIntent,
    ChooseDialogueIntent,
    EndDialogueIntent,
    BuyIntent,
    SellIntent,
    CampaignActionIntent,
    RecoverIntent,
    SaveIntent,
    LoadIntent,
)


def is_declared_game_intent(value: object) -> bool:
    """Return whether value has one of the exact V2-1 intent types."""
    return type(value) in _DECLARED_GAME_INTENT_TYPES


ItemAction: TypeAlias = TakeIntent | DropIntent | UseIntent | EquipIntent
ShopAction: TypeAlias = BuyIntent | SellIntent


@dataclass(frozen=True, slots=True)
class DeterminismContext:
    """Injected V1 determinism inputs; current rules do not consume them."""

    seed: int = 0
    clock: int = 0


@dataclass(frozen=True, slots=True)
class RejectionDiagnostic:
    code: RejectionCode
    message: str


@dataclass(frozen=True, slots=True)
class LevelGainEvent:
    new_level: int
    max_hp_gain: int
    attack_gain: int
    defense_gain: int


@dataclass(frozen=True, slots=True)
class QuestCompletionEvent:
    quest_id: str
    quest_name: str
    kind: QuestKind
    reward_experience: int
    level_gains: tuple[LevelGainEvent, ...] = ()


@dataclass(frozen=True, slots=True)
class LootEvent:
    item_id: str
    item_name: str
    quantity: int


@dataclass(frozen=True, slots=True)
class MoveExitEvent:
    direction: str
    target_room_id: str
    required_item_id: str | None


@dataclass(frozen=True, slots=True)
class MoveItemStackEvent:
    item_id: str
    quantity: int


@dataclass(frozen=True, slots=True)
class MoveRoomEvent:
    id: str
    name: str
    description: str
    exits: tuple[MoveExitEvent, ...]
    item_stacks: tuple[MoveItemStackEvent, ...]
    monster_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MoveEventData:
    room_id: str
    room_name: str
    room: MoveRoomEvent
    quest_outcomes: tuple[QuestCompletionEvent, ...] = ()
    level_gains: tuple[LevelGainEvent, ...] = ()


@dataclass(frozen=True, slots=True)
class ItemTransferEventData:
    item_id: str
    item_name: str
    quantity: int
    quest_outcomes: tuple[QuestCompletionEvent, ...] = ()
    level_gains: tuple[LevelGainEvent, ...] = ()


@dataclass(frozen=True, slots=True)
class UseEventData:
    item_id: str
    item_name: str
    quantity: int
    healed_amount: int


@dataclass(frozen=True, slots=True)
class EquipmentEventData:
    item_id: str
    item_name: str
    attack_bonus: int
    defense_bonus: int


@dataclass(frozen=True, slots=True)
class CombatEventData:
    monster_name: str
    damage_to_monster: int
    damage_to_player: int
    monster_defeated: bool
    player_defeated: bool
    experience_reward: int
    combat_level_gains: tuple[LevelGainEvent, ...] = ()
    quest_outcomes: tuple[QuestCompletionEvent, ...] = ()
    level_gains: tuple[LevelGainEvent, ...] = ()
    loot_item: LootEvent | None = None


@dataclass(frozen=True, slots=True)
class DialogueOptionEvent:
    option_id: str
    text: str


@dataclass(frozen=True, slots=True)
class GrantedItemEvent:
    item_id: str
    item_name: str
    quantity: int
    quest_outcomes: tuple[QuestCompletionEvent, ...] = ()


@dataclass(frozen=True, slots=True)
class GrantedExperienceEvent:
    amount: int
    level_gains: tuple[LevelGainEvent, ...] = ()


@dataclass(frozen=True, slots=True)
class AcceptedQuestEvent:
    quest_id: str
    quest_name: str
    quest_outcomes: tuple[QuestCompletionEvent, ...] = ()


@dataclass(frozen=True, slots=True)
class FlagChangeEvent:
    flag_id: str
    old_value: bool | None
    new_value: bool
    changed: bool


DialogueEffectEvent: TypeAlias = (
    GrantedItemEvent
    | GrantedExperienceEvent
    | AcceptedQuestEvent
    | FlagChangeEvent
)


@dataclass(frozen=True, slots=True)
class DialogueEventData:
    character_id: str
    character_name: str
    dialogue_id: str
    node_id: str | None = None
    node_text: str | None = None
    options: tuple[DialogueOptionEvent, ...] = ()
    ended: bool = False
    effect_outcomes: tuple[DialogueEffectEvent, ...] = ()
    quest_outcomes: tuple[QuestCompletionEvent, ...] = ()
    level_gains: tuple[LevelGainEvent, ...] = ()


@dataclass(frozen=True, slots=True)
class DialogueEndEventData:
    character_id: str
    character_name: str
    dialogue_id: str


@dataclass(frozen=True, slots=True)
class TradeEventData:
    shop_id: str
    shop_name: str
    item_id: str
    item_name: str
    quantity: int
    unit_price: int
    total_price: int
    coins: int
    quest_outcomes: tuple[QuestCompletionEvent, ...] = ()
    level_gains: tuple[LevelGainEvent, ...] = ()


@dataclass(frozen=True, slots=True)
class CampaignActionEventData:
    action_id: str
    label: str
    result_text: str
    effect_outcomes: tuple[CampaignEffectEvent, ...] = ()


@dataclass(frozen=True, slots=True)
class CampaignActorStateEvent:
    location_id: str | None
    presence: str
    enabled: bool
    incapacitated: bool


@dataclass(frozen=True, slots=True)
class CampaignSceneStateEvent:
    status: str
    stage_index: int | None


CampaignEffectValue: TypeAlias = (
    str
    | int
    | bool
    | None
    | CampaignActorStateEvent
    | CampaignSceneStateEvent
)


@dataclass(frozen=True, slots=True)
class CampaignEffectEvent:
    kind: str
    target_id: str
    before: CampaignEffectValue
    after: CampaignEffectValue


@dataclass(frozen=True, slots=True)
class RecoveryEventData:
    start_room_id: str
    room_name: str
    hp: int
    max_hp: int


@dataclass(frozen=True, slots=True)
class PersistenceEventData:
    slot: str


GameEventPayload: TypeAlias = (
    MoveEventData
    | ItemTransferEventData
    | UseEventData
    | EquipmentEventData
    | CombatEventData
    | DialogueEventData
    | DialogueEndEventData
    | TradeEventData
    | CampaignActionEventData
    | RecoveryEventData
    | PersistenceEventData
    | CapabilityEventData
)


class GameEventKind(str, Enum):
    MOVE = "move"
    TAKE = "take"
    DROP = "drop"
    USE = "use"
    EQUIP = "equip"
    UNEQUIP = "unequip"
    ATTACK = "attack"
    TALK = "talk"
    CHOOSE_DIALOGUE = "choose_dialogue"
    END_DIALOGUE = "end_dialogue"
    BUY = "buy"
    SELL = "sell"
    CAMPAIGN_ACTION = "campaign_action"
    RECOVER = "recover"
    SAVE = "save"
    LOAD = "load"
    CAPABILITY = "capability"


@dataclass(frozen=True, slots=True)
class GameEvent:
    sequence: int
    kind: GameEventKind
    payload: GameEventPayload


@dataclass(frozen=True, slots=True)
class PackView:
    id: str
    name: str
    version: str


@dataclass(frozen=True, slots=True)
class PlayerView:
    id: str
    name: str
    alive: bool
    hp: int
    max_hp: int
    level: int
    experience: int
    experience_to_next_level: int
    attack: int
    base_attack: int
    defense: int
    base_defense: int
    coins: int
    inventory_capacity: int
    inventory_stack_count: int
    recover: RecoverIntent | None


@dataclass(frozen=True, slots=True)
class ExitView:
    direction: str
    target_room_id: str
    target_room_name: str
    required_item_id: str | None
    required_item_name: str | None
    locked: bool
    move: MoveIntent | None


@dataclass(frozen=True, slots=True)
class ItemView:
    id: str
    name: str
    description: str
    quantity: int
    heal_amount: int | None
    slot: EquipmentSlot | None
    attack_bonus: int
    defense_bonus: int
    equipped: bool
    actions: tuple[ItemAction, ...] = ()


@dataclass(frozen=True, slots=True)
class MonsterView:
    id: str
    name: str
    description: str
    hp: int
    max_hp: int
    attack: int
    defense: int
    attack_intent: AttackIntent | None


@dataclass(frozen=True, slots=True)
class CharacterView:
    id: str
    name: str
    description: str
    talk: TalkIntent | None


@dataclass(frozen=True, slots=True)
class RoomView:
    id: str
    name: str
    description: str
    exits: tuple[ExitView, ...]
    items: tuple[ItemView, ...]
    monsters: tuple[MonsterView, ...]
    characters: tuple[CharacterView, ...]
    quest_hints: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EquippedItemView:
    id: str
    name: str
    attack_bonus: int
    defense_bonus: int
    unequip: UnequipIntent | None


@dataclass(frozen=True, slots=True)
class EquipmentView:
    hand: EquippedItemView | None
    body: EquippedItemView | None


@dataclass(frozen=True, slots=True)
class QuestTargetView:
    kind: QuestKind
    id: str
    name: str
    current: int
    required: int


@dataclass(frozen=True, slots=True)
class QuestView:
    id: str
    name: str
    description: str
    completed: bool
    reward_experience: int
    target: QuestTargetView


@dataclass(frozen=True, slots=True)
class SceneView:
    id: str
    name: str
    status: SceneStatus
    stage_id: str
    description: str


@dataclass(frozen=True, slots=True)
class CampaignActionView:
    id: str
    label: str
    interactable_id: str
    intent: CampaignActionIntent


@dataclass(frozen=True, slots=True)
class InteractableView:
    id: str
    name: str
    kind: InteractableKind
    description: str
    actions: tuple[CampaignActionView, ...]


@dataclass(frozen=True, slots=True)
class JournalEntryView:
    id: str
    category: JournalCategory
    title: str
    text: str
    status: ObjectiveStatus | KnowledgeStatus | None = None


@dataclass(frozen=True, slots=True)
class CampaignView:
    scenes: tuple[SceneView, ...]
    interactables: tuple[InteractableView, ...]
    actions: tuple[CampaignActionView, ...]
    objectives: tuple[JournalEntryView, ...]
    knowledge: tuple[JournalEntryView, ...]
    journal: tuple[JournalEntryView, ...]


@dataclass(frozen=True, slots=True)
class DialogueOptionView:
    index: int
    id: str
    text: str
    intent: ChooseDialogueIntent


@dataclass(frozen=True, slots=True)
class DialogueView:
    dialogue_id: str
    character_id: str
    character_name: str
    node_id: str
    text: str
    options: tuple[DialogueOptionView, ...]
    end: EndDialogueIntent


@dataclass(frozen=True, slots=True)
class ShopListingView:
    item_id: str
    item_name: str
    buy_price: int
    sell_price: int
    actions: tuple[ShopAction, ...]


@dataclass(frozen=True, slots=True)
class ShopView:
    id: str
    name: str
    catalog: tuple[ShopListingView, ...]


@dataclass(frozen=True, slots=True)
class FlagView:
    id: str
    value: bool


@dataclass(frozen=True, slots=True)
class ItemFocusView:
    id: str
    name: str
    description: str


@dataclass(frozen=True, slots=True)
class MonsterFocusView:
    id: str
    name: str
    description: str
    hp: int
    max_hp: int


@dataclass(frozen=True, slots=True)
class CharacterFocusView:
    id: str
    name: str
    description: str


FocusView: TypeAlias = ItemFocusView | MonsterFocusView | CharacterFocusView


@dataclass(frozen=True, slots=True)
class GameView:
    pack: PackView
    player: PlayerView
    room: RoomView
    inventory: tuple[ItemView, ...]
    equipment: EquipmentView
    quests: tuple[QuestView, ...]
    campaign: CampaignView
    dialogue: DialogueView | None
    shop: ShopView | None
    flags: tuple[FlagView, ...]
    focus: FocusView | None = None
    # Capability data is additive; the legacy lane keeps this explicitly absent.
    capabilities: tuple[CapabilityPlayerViewEntry, ...] | None = None


@dataclass(frozen=True, slots=True)
class TurnResult:
    status: TurnStatus
    events: tuple[GameEvent, ...]
    view: GameView
    rejection: RejectionDiagnostic | None = None
