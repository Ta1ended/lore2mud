"""Deterministic application coordinator around the authoritative V1 ``World``."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import fields
from random import Random
import re
from threading import RLock
from typing import Literal, Protocol, TypeAlias

from lore2mud.application.contracts import (
    AcceptedQuestEvent,
    AttackIntent,
    BuyIntent,
    CampaignActionEventData,
    CampaignActionIntent,
    ChooseDialogueIntent,
    CombatEventData,
    DeterminismContext,
    DialogueEffectEvent,
    DialogueEndEventData,
    DialogueEventData,
    DialogueOptionEvent,
    DropIntent,
    EndDialogueIntent,
    EquipIntent,
    EquipmentSlot,
    EquipmentEventData,
    ExamineIntent,
    ExamineTargetKind,
    FlagChangeEvent,
    FocusView,
    GameEvent,
    GameEventKind,
    GameEventPayload,
    GameIntent,
    GameView,
    GrantedExperienceEvent,
    GrantedItemEvent,
    ItemTransferEventData,
    LevelGainEvent,
    LoadIntent,
    LootEvent,
    MoveEventData,
    MoveIntent,
    PersistenceEventData,
    QuestCompletionEvent,
    QuestKind,
    RecoverIntent,
    RecoveryEventData,
    RejectionCode,
    RejectionDiagnostic,
    SaveIntent,
    SellIntent,
    TakeIntent,
    TalkIntent,
    TradeEventData,
    TurnResult,
    TurnStatus,
    UnequipIntent,
    UseEventData,
    UseIntent,
    ViewIntent,
    ViewKind,
)
from lore2mud.application.projection import (
    character_focus,
    item_focus,
    monster_focus,
    project_game_view,
)
from lore2mud.content.models import ContentPack
from lore2mud.engine.save import SaveLoadError
from lore2mud.engine.world import (
    AcceptQuestEffectOutcome,
    AttackOutcome,
    BuyOutcome,
    CampaignActionOutcome,
    DialogueEndOutcome,
    DropOutcome,
    EquipOutcome,
    ExamineCharacterOutcome,
    ExamineItemOutcome,
    ExamineMonsterOutcome,
    GrantExperienceEffectOutcome,
    GrantItemEffectOutcome,
    MoveOutcome,
    QuestOutcome,
    RecoverOutcome,
    SellOutcome,
    SetFlagEffectOutcome,
    TakeOutcome,
    TalkOutcome,
    UnequipOutcome,
    UseOutcome,
    World,
    WorldRuleError,
)
from lore2mud.progression.service import LevelGain


class SaveService(Protocol):
    def save(self, world: World, slot: str | None = None) -> str: ...

    def load(self, slot: str | None = None) -> World: ...


class _IntentValidationError(ValueError):
    pass


_EventDraft: TypeAlias = tuple[GameEventKind, GameEventPayload]
_RngState: TypeAlias = tuple[int, tuple[int, ...], float | None]
_STABLE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class GameSession:
    """Own one World and coordinate one deterministic application turn at a time."""

    def __init__(
        self,
        world: World,
        save_service: SaveService | None = None,
        *,
        determinism: DeterminismContext | None = None,
    ) -> None:
        self._validate_context(determinism or DeterminismContext())
        self._world = world
        self._save_service = save_service
        self._determinism = determinism or DeterminismContext()
        self._rng = Random(self._determinism.seed)
        self._event_sequence = 0
        self._lock = RLock()

    @classmethod
    def from_content_pack(
        cls,
        pack: ContentPack,
        save_service: SaveService | None = None,
        *,
        player_name: str = "旅人",
        determinism: DeterminismContext | None = None,
    ) -> GameSession:
        return cls(
            World.from_content_pack(pack, player_name=player_name),
            save_service,
            determinism=determinism,
        )

    @property
    def world(self) -> World:
        """Return the current compatibility World for legacy integrations."""
        return self._world

    @property
    def determinism(self) -> DeterminismContext:
        return self._determinism

    @property
    def event_sequence(self) -> int:
        return self._event_sequence

    def view(self) -> GameView:
        with self._lock:
            return project_game_view(self._world)

    def reject(self, code: RejectionCode, message: str) -> TurnResult:
        """Create a transport-parse rejection without touching authority."""
        with self._lock:
            return TurnResult(
                status=TurnStatus.REJECTED,
                events=(),
                view=project_game_view(self._world),
                rejection=RejectionDiagnostic(code, message),
            )

    def submit(self, intent: GameIntent) -> TurnResult:
        """Validate and execute exactly one intent against the authoritative World."""
        with self._lock:
            try:
                self._validate_intent(intent)
            except _IntentValidationError as exc:
                return TurnResult(
                    TurnStatus.REJECTED,
                    (),
                    project_game_view(self._world),
                    RejectionDiagnostic(RejectionCode.MALFORMED_INTENT, str(exc)),
                )

            original_world = self._world
            backup = deepcopy(original_world)
            rng_state = self._rng.getstate()
            sequence = self._event_sequence
            try:
                draft, focus = self._execute(intent)
                view = project_game_view(self._world, focus=focus)
            except WorldRuleError as exc:
                self._restore(original_world, backup, rng_state, sequence)
                return TurnResult(
                    TurnStatus.REJECTED,
                    (),
                    project_game_view(self._world),
                    RejectionDiagnostic(RejectionCode.INADMISSIBLE_INTENT, str(exc)),
                )
            except SaveLoadError as exc:
                self._restore(original_world, backup, rng_state, sequence)
                return TurnResult(
                    TurnStatus.REJECTED,
                    (),
                    project_game_view(self._world),
                    RejectionDiagnostic(RejectionCode.PERSISTENCE_ERROR, str(exc)),
                )
            except Exception:
                self._restore(original_world, backup, rng_state, sequence)
                raise

            if draft is None:
                return TurnResult(TurnStatus.ACCEPTED, (), view)

            kind, payload = draft
            next_sequence = self._event_sequence + 1
            event = GameEvent(next_sequence, kind, payload)
            self._event_sequence = next_sequence
            return TurnResult(TurnStatus.ACCEPTED, (event,), view)

    def _execute(
        self,
        intent: GameIntent,
    ) -> tuple[_EventDraft | None, FocusView | None]:
        world = self._world
        if isinstance(intent, ViewIntent):
            if intent.kind is ViewKind.SHOP:
                world.shop()
            return None, None
        if isinstance(intent, ExamineIntent):
            target_kind: Literal["item", "monster", "character"] | None = None
            if intent.target_kind is ExamineTargetKind.ITEM:
                target_kind = "item"
            elif intent.target_kind is ExamineTargetKind.MONSTER:
                target_kind = "monster"
            elif intent.target_kind is ExamineTargetKind.CHARACTER:
                target_kind = "character"
            outcome = world.examine(intent.target, target_kind)
            if isinstance(outcome, ExamineItemOutcome):
                return None, item_focus(
                    outcome.item_id, outcome.item_name, outcome.description
                )
            if isinstance(outcome, ExamineMonsterOutcome):
                return None, monster_focus(
                    outcome.monster_id,
                    outcome.monster_name,
                    outcome.description,
                    outcome.hp,
                    outcome.max_hp,
                )
            assert isinstance(outcome, ExamineCharacterOutcome)
            return None, character_focus(
                outcome.character_id,
                outcome.character_name,
                outcome.description,
            )
        if isinstance(intent, MoveIntent):
            outcome = world.move_with_outcome(intent.direction)
            return (GameEventKind.MOVE, _move_event(outcome)), None
        if isinstance(intent, TakeIntent):
            outcome = world.take(intent.target, intent.quantity)
            return (GameEventKind.TAKE, _take_event(outcome)), None
        if isinstance(intent, DropIntent):
            outcome = world.drop(intent.target, intent.quantity)
            return (GameEventKind.DROP, _drop_event(outcome)), None
        if isinstance(intent, UseIntent):
            outcome = world.use(intent.target, intent.quantity)
            return (GameEventKind.USE, _use_event(outcome)), None
        if isinstance(intent, EquipIntent):
            outcome = world.equip(intent.target)
            return (GameEventKind.EQUIP, _equipment_event(outcome)), None
        if isinstance(intent, UnequipIntent):
            outcome = world.unequip(intent.slot.value)
            return (GameEventKind.UNEQUIP, _equipment_event(outcome)), None
        if isinstance(intent, AttackIntent):
            outcome = world.attack(intent.target)
            return (GameEventKind.ATTACK, _combat_event(outcome)), None
        if isinstance(intent, TalkIntent):
            outcome = world.start_dialogue(intent.target)
            return (GameEventKind.TALK, _dialogue_event(outcome)), None
        if isinstance(intent, ChooseDialogueIntent):
            outcome = world.select_option(intent.index)
            return (GameEventKind.CHOOSE_DIALOGUE, _dialogue_event(outcome)), None
        if isinstance(intent, EndDialogueIntent):
            outcome = world.end_dialogue()
            return (GameEventKind.END_DIALOGUE, _dialogue_end_event(outcome)), None
        if isinstance(intent, BuyIntent):
            outcome = world.buy(intent.target, intent.quantity)
            return (GameEventKind.BUY, _buy_event(outcome)), None
        if isinstance(intent, SellIntent):
            outcome = world.sell(intent.target, intent.quantity)
            return (GameEventKind.SELL, _sell_event(outcome)), None
        if isinstance(intent, CampaignActionIntent):
            outcome = world.execute_campaign_action(intent.action_id)
            return (
                GameEventKind.CAMPAIGN_ACTION,
                _campaign_action_event(outcome),
            ), None
        if isinstance(intent, RecoverIntent):
            outcome = world.recover()
            return (GameEventKind.RECOVER, _recovery_event(outcome)), None
        if isinstance(intent, SaveIntent):
            service = self._require_save_service()
            service.save(world, intent.slot)
            return (
                GameEventKind.SAVE,
                PersistenceEventData(intent.slot or "default"),
            ), None
        if isinstance(intent, LoadIntent):
            service = self._require_save_service()
            self._world = service.load(intent.slot)
            return (
                GameEventKind.LOAD,
                PersistenceEventData(intent.slot or "default"),
            ), None
        raise _IntentValidationError(f"未知 GameIntent 类型：{type(intent).__name__}")

    def _require_save_service(self) -> SaveService:
        if self._save_service is None:
            raise SaveLoadError("存档服务不可用。")
        return self._save_service

    def _restore(
        self,
        original_world: World,
        backup: World,
        rng_state: _RngState,
        sequence: int,
    ) -> None:
        for definition in fields(World):
            setattr(
                original_world,
                definition.name,
                deepcopy(getattr(backup, definition.name)),
            )
        self._world = original_world
        self._rng.setstate(rng_state)
        self._event_sequence = sequence

    @staticmethod
    def _validate_context(context: DeterminismContext) -> None:
        if (
            isinstance(context.seed, bool)
            or not isinstance(context.seed, int)
            or isinstance(context.clock, bool)
            or not isinstance(context.clock, int)
        ):
            raise ValueError("determinism seed and clock must be integers")

    @staticmethod
    def _validate_intent(intent: GameIntent) -> None:
        if not isinstance(intent, GameIntent) or type(intent) is GameIntent:
            raise _IntentValidationError("intent 必须是已声明的 GameIntent 子类型。")
        if isinstance(intent, ViewIntent):
            if not isinstance(intent.kind, ViewKind):
                raise _IntentValidationError("view kind 无效。")
            return
        if isinstance(intent, ExamineIntent):
            _validate_text(intent.target, "target")
            if intent.target_kind is not None and not isinstance(
                intent.target_kind, ExamineTargetKind
            ):
                raise _IntentValidationError("target_kind 无效。")
            return
        if isinstance(intent, MoveIntent):
            _validate_text(intent.direction, "direction", maximum=32)
            return
        if isinstance(intent, (TakeIntent, DropIntent, UseIntent, BuyIntent, SellIntent)):
            _validate_text(intent.target, "target")
            _validate_positive_int(intent.quantity, "quantity")
            return
        if isinstance(intent, (EquipIntent, AttackIntent, TalkIntent)):
            _validate_text(intent.target, "target")
            return
        if isinstance(intent, UnequipIntent):
            if not isinstance(intent.slot, EquipmentSlot):
                raise _IntentValidationError("slot 无效。")
            return
        if isinstance(intent, ChooseDialogueIntent):
            _validate_positive_int(intent.index, "index")
            return
        if isinstance(intent, CampaignActionIntent):
            _validate_text(intent.action_id, "action_id")
            if not _STABLE_ID_PATTERN.fullmatch(intent.action_id):
                raise _IntentValidationError("action_id 必须是稳定 ID。")
            return
        if isinstance(intent, (SaveIntent, LoadIntent)):
            if intent.slot is not None:
                _validate_text(intent.slot, "slot", maximum=32)
            return
        if isinstance(intent, (EndDialogueIntent, RecoverIntent)):
            return
        raise _IntentValidationError(f"未知 GameIntent 类型：{type(intent).__name__}")


def _validate_text(value: object, field: str, *, maximum: int = 200) -> None:
    if not isinstance(value, str) or not value.strip():
        raise _IntentValidationError(f"{field} 必须是非空字符串。")
    if len(value.strip()) > maximum:
        raise _IntentValidationError(f"{field} 过长。")


def _validate_positive_int(value: object, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise _IntentValidationError(f"{field} 必须是正整数。")


def _level_gains(values: tuple[LevelGain, ...]) -> tuple[LevelGainEvent, ...]:
    return tuple(
        LevelGainEvent(
            value.new_level,
            value.max_hp_gain,
            value.attack_gain,
            value.defense_gain,
        )
        for value in values
    )


def _quest_outcomes(values: tuple[QuestOutcome, ...]) -> tuple[QuestCompletionEvent, ...]:
    return tuple(
        QuestCompletionEvent(
            value.quest_id,
            value.quest_name,
            QuestKind(value.kind),
            value.reward_experience,
            _level_gains(value.level_gains),
        )
        for value in values
    )


def _move_event(outcome: MoveOutcome) -> MoveEventData:
    return MoveEventData(
        outcome.room.id,
        outcome.room.name,
        _quest_outcomes(outcome.quest_outcomes),
        _level_gains(outcome.level_gains),
    )


def _take_event(outcome: TakeOutcome) -> ItemTransferEventData:
    return ItemTransferEventData(
        outcome.item_id,
        outcome.item_name,
        outcome.quantity,
        _quest_outcomes(outcome.quest_outcomes),
        _level_gains(outcome.level_gains),
    )


def _drop_event(outcome: DropOutcome) -> ItemTransferEventData:
    return ItemTransferEventData(outcome.item_id, outcome.item_name, outcome.quantity)


def _use_event(outcome: UseOutcome) -> UseEventData:
    return UseEventData(
        outcome.item_id,
        outcome.item_name,
        outcome.quantity,
        outcome.healed_amount,
    )


def _equipment_event(outcome: EquipOutcome | UnequipOutcome) -> EquipmentEventData:
    return EquipmentEventData(
        outcome.item_id,
        outcome.item_name,
        outcome.attack_bonus,
        outcome.defense_bonus,
    )


def _combat_event(outcome: AttackOutcome) -> CombatEventData:
    combat = outcome.combat
    return CombatEventData(
        monster_name=combat.monster_name,
        damage_to_monster=combat.damage_to_monster,
        damage_to_player=combat.damage_to_player,
        monster_defeated=combat.monster_defeated,
        player_defeated=combat.player_defeated,
        experience_reward=combat.experience_reward,
        combat_level_gains=_level_gains(outcome.combat_level_gains),
        quest_outcomes=_quest_outcomes(outcome.quest_outcomes),
        level_gains=_level_gains(outcome.level_gains),
        loot_item=(
            LootEvent(
                outcome.loot_item.item_id,
                outcome.loot_item.item_name,
                outcome.loot_item.quantity,
            )
            if outcome.loot_item is not None
            else None
        ),
    )


def _dialogue_event(outcome: TalkOutcome) -> DialogueEventData:
    effects: list[DialogueEffectEvent] = []
    for effect in outcome.effect_outcomes:
        if isinstance(effect, GrantItemEffectOutcome):
            effects.append(
                GrantedItemEvent(
                    effect.item_id,
                    effect.item_name,
                    effect.quantity,
                    _quest_outcomes(effect.quest_outcomes),
                )
            )
        elif isinstance(effect, GrantExperienceEffectOutcome):
            effects.append(
                GrantedExperienceEvent(effect.amount, _level_gains(effect.level_gains))
            )
        elif isinstance(effect, AcceptQuestEffectOutcome):
            effects.append(
                AcceptedQuestEvent(
                    effect.quest_id,
                    effect.quest_name,
                    _quest_outcomes(effect.quest_outcomes),
                )
            )
        elif isinstance(effect, SetFlagEffectOutcome):
            effects.append(
                FlagChangeEvent(
                    effect.flag_id,
                    effect.old_value,
                    effect.new_value,
                    effect.changed,
                )
            )
        else:
            raise AssertionError(f"未知 dialogue effect outcome：{effect!r}")
    return DialogueEventData(
        character_id=outcome.character_id,
        character_name=outcome.character_name,
        dialogue_id=outcome.dialogue_id,
        node_id=outcome.node_id,
        node_text=outcome.node_text,
        options=tuple(
            DialogueOptionEvent(option.option_id, option.text)
            for option in outcome.options
        ),
        ended=outcome.ended,
        effect_outcomes=tuple(effects),
        quest_outcomes=_quest_outcomes(outcome.quest_outcomes),
        level_gains=_level_gains(outcome.level_gains),
    )


def _dialogue_end_event(outcome: DialogueEndOutcome) -> DialogueEndEventData:
    return DialogueEndEventData(
        outcome.character_id,
        outcome.character_name,
        outcome.dialogue_id,
    )


def _buy_event(outcome: BuyOutcome) -> TradeEventData:
    return TradeEventData(
        outcome.shop_id,
        outcome.shop_name,
        outcome.item_id,
        outcome.item_name,
        outcome.quantity,
        outcome.unit_price,
        outcome.total_price,
        outcome.coins,
        _quest_outcomes(outcome.quest_outcomes),
        _level_gains(outcome.level_gains),
    )


def _sell_event(outcome: SellOutcome) -> TradeEventData:
    return TradeEventData(
        outcome.shop_id,
        outcome.shop_name,
        outcome.item_id,
        outcome.item_name,
        outcome.quantity,
        outcome.unit_price,
        outcome.total_price,
        outcome.coins,
    )


def _campaign_action_event(outcome: CampaignActionOutcome) -> CampaignActionEventData:
    return CampaignActionEventData(
        outcome.action_id,
        outcome.label,
        outcome.result_text,
    )


def _recovery_event(outcome: RecoverOutcome) -> RecoveryEventData:
    return RecoveryEventData(
        outcome.start_room_id,
        outcome.room_name,
        outcome.hp,
        outcome.max_hp,
    )
