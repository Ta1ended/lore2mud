"""Deterministic application coordinator around the authoritative V1 ``World``."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, fields, is_dataclass, replace
from random import Random
import re
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Literal, Protocol, TypeAlias, cast

if TYPE_CHECKING:
    from lore2mud.capabilities.runtime import CapabilityRuntimeHost

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
    EndingView,
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
    MoveExitEvent,
    MoveIntent,
    MoveItemStackEvent,
    MoveRoomEvent,
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
    is_declared_game_intent,
)
from lore2mud.application.projection import (
    character_focus,
    item_focus,
    monster_focus,
    project_game_view,
)
from lore2mud.capabilities.contracts import CapabilityEventData, CapabilityIntent
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


class _CapabilityHost(Protocol):
    def snapshot(self) -> object: ...

    def restore(self, snapshot: object) -> None: ...

    def prepare_turn(
        self,
        intent: GameIntent | CapabilityIntent,
        *,
        before_view: GameView,
        after_view: GameView,
        event: _EventDraft | None,
        determinism: DeterminismContext,
        event_sequence: int,
    ) -> object: ...

    def project_view(
        self,
        view: GameView,
        prepared: object | None = None,
    ) -> tuple[object, ...] | None: ...

    def prepared_events(self, prepared: object) -> tuple[CapabilityEventData, ...]: ...

    def commit(self, prepared: object) -> None: ...


class _IntentValidationError(ValueError):
    pass


_EventDraft: TypeAlias = tuple[GameEventKind, GameEventPayload]
_RngState: TypeAlias = tuple[int, tuple[int, ...], float | None]
_DeterminismState: TypeAlias = tuple[int, int]
_STABLE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_MISSING = object()


def _is_capability_intent(value: object) -> bool:
    return type(value) is CapabilityIntent


def _capability_rejection_code(exc: Exception) -> RejectionCode | None:
    value = getattr(exc, "rejection_code", None)
    if value == RejectionCode.CAPABILITY_INTENT_INVALID.value:
        return RejectionCode.CAPABILITY_INTENT_INVALID
    if value == RejectionCode.CAPABILITY_INTENT_INADMISSIBLE.value:
        return RejectionCode.CAPABILITY_INTENT_INADMISSIBLE
    return None


def _capability_rejection_message(code: RejectionCode) -> str:
    if code is RejectionCode.CAPABILITY_INTENT_INADMISSIBLE:
        return "Capability intent is not currently admissible."
    return "Capability intent is invalid."


@dataclass(frozen=True, slots=True)
class _WorldSnapshot:
    backup: World
    references: tuple[tuple[object, object], ...]


@dataclass(frozen=True, slots=True)
class _SaveFileSnapshot:
    path: Path
    existed: bool
    data: bytes


def _capture_world(world: World) -> _WorldSnapshot:
    memo: dict[int, object] = {}
    backup = deepcopy(world, memo)
    references: list[tuple[object, object]] = []
    _collect_snapshot_references(world, memo, set(), references)
    return _WorldSnapshot(backup, tuple(references))


def _collect_snapshot_references(
    value: object,
    memo: dict[int, object],
    visited: set[int],
    references: list[tuple[object, object]],
) -> None:
    identity = id(value)
    if identity in visited:
        return
    visited.add(identity)

    copied = memo.get(identity, _MISSING)
    if copied is not _MISSING:
        references.append((value, copied))

    if is_dataclass(value) and not isinstance(value, type):
        for definition in fields(value):
            _collect_snapshot_references(
                getattr(value, definition.name),
                memo,
                visited,
                references,
            )
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _collect_snapshot_references(key, memo, visited, references)
            _collect_snapshot_references(item, memo, visited, references)
        return
    if isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            _collect_snapshot_references(item, memo, visited, references)


def _restore_world(snapshot: _WorldSnapshot) -> None:
    restore_memo = {
        id(backup): original for original, backup in snapshot.references
    }
    for original, backup in snapshot.references:
        if is_dataclass(original) and not isinstance(original, type):
            values = tuple(
                (
                    definition.name,
                    deepcopy(getattr(backup, definition.name), restore_memo),
                )
                for definition in fields(original)
            )
            for name, value in values:
                object.__setattr__(original, name, value)
            continue
        if isinstance(original, dict):
            assert isinstance(backup, dict)
            values = tuple(
                (
                    deepcopy(key, restore_memo),
                    deepcopy(value, restore_memo),
                )
                for key, value in backup.items()
            )
            original.clear()
            original.update(values)
            continue
        if isinstance(original, list):
            assert isinstance(backup, list)
            original[:] = [deepcopy(value, restore_memo) for value in backup]
            continue
        if isinstance(original, set):
            assert isinstance(backup, set)
            values = {deepcopy(value, restore_memo) for value in backup}
            original.clear()
            original.update(values)


def _capture_save_file(
    service: SaveService | None,
    slot: str | None,
) -> _SaveFileSnapshot | None:
    if service is None:
        return None
    try:
        if slot is None:
            path = getattr(service, "save_path", None)
        else:
            slot_path = getattr(service, "slot_path", None)
            if not callable(slot_path):
                return None
            path = slot_path(slot)
        if not isinstance(path, Path):
            return None
        if not path.is_file():
            return _SaveFileSnapshot(path, False, b"")
        return _SaveFileSnapshot(path, True, path.read_bytes())
    except (OSError, SaveLoadError, TypeError, ValueError):
        return None


def _restore_save_file(snapshot: _SaveFileSnapshot | None) -> None:
    if snapshot is None:
        return
    try:
        if snapshot.existed:
            snapshot.path.parent.mkdir(parents=True, exist_ok=True)
            snapshot.path.write_bytes(snapshot.data)
        elif snapshot.path.exists():
            snapshot.path.unlink()
    except OSError as exc:
        raise SaveLoadError("save rollback failed") from exc


class GameSession:
    """Own one World and coordinate one deterministic application turn at a time."""

    def __init__(
        self,
        world: World,
        save_service: SaveService | None = None,
        *,
        determinism: DeterminismContext | None = None,
        capability_host: "CapabilityRuntimeHost | None" = None,
    ) -> None:
        context = DeterminismContext() if determinism is None else determinism
        self._validate_context(context)
        self._world = world
        self._save_service = save_service
        self._determinism = context
        self._rng = Random(self._determinism.seed)
        self._event_sequence = 0
        self._capability_host = capability_host
        self._lock = RLock()

    @classmethod
    def from_content_pack(
        cls,
        pack: ContentPack,
        save_service: SaveService | None = None,
        *,
        player_name: str = "旅人",
        determinism: DeterminismContext | None = None,
        capability_host: "CapabilityRuntimeHost | None" = None,
    ) -> GameSession:
        return cls(
            World.from_content_pack(pack, player_name=player_name),
            save_service,
            determinism=determinism,
            capability_host=capability_host,
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

    @property
    def capability_host(self) -> "CapabilityRuntimeHost | None":
        return self._capability_host

    def view(self) -> GameView:
        with self._lock:
            return project_game_view(
                self._world,
                capability_host=self._capability_host,
                capability_determinism=self._determinism,
                capability_event_sequence=self._event_sequence,
            )

    def reject(self, code: RejectionCode, message: str) -> TurnResult:
        """Create a transport-parse rejection without touching authority."""
        with self._lock:
            return TurnResult(
                status=TurnStatus.REJECTED,
                events=(),
                view=project_game_view(
                    self._world,
                    capability_host=self._capability_host,
                    capability_determinism=self._determinism,
                    capability_event_sequence=self._event_sequence,
                ),
                rejection=RejectionDiagnostic(code, message),
            )

    def submit(self, intent: GameIntent | CapabilityIntent) -> TurnResult:
        """Validate and execute exactly one intent against the authoritative World."""
        with self._lock:
            capability_intent = _is_capability_intent(intent)
            if not capability_intent:
                try:
                    validate_game_intent(intent)
                except _IntentValidationError as exc:
                    return TurnResult(
                        TurnStatus.REJECTED,
                        (),
                        project_game_view(
                            self._world,
                            capability_host=self._capability_host,
                            capability_determinism=self._determinism,
                            capability_event_sequence=self._event_sequence,
                        ),
                        RejectionDiagnostic(RejectionCode.MALFORMED_INTENT, str(exc)),
                    )
            elif self._capability_host is None:
                return TurnResult(
                    TurnStatus.REJECTED,
                    (),
                    project_game_view(self._world),
                    RejectionDiagnostic(
                        RejectionCode.CAPABILITY_INTENT_INVALID,
                        _capability_rejection_message(
                            RejectionCode.CAPABILITY_INTENT_INVALID
                        ),
                    ),
                )

            original_world = self._world
            snapshot = _capture_world(original_world)
            rng_state = self._rng.getstate()
            determinism = self._determinism
            determinism_state = (determinism.seed, determinism.clock)
            sequence = self._event_sequence
            capability_snapshot: object = _MISSING
            save_file_snapshot: _SaveFileSnapshot | None = None
            try:
                if self._capability_host is not None:
                    capability_snapshot = self._capability_host.snapshot()
                before_view = project_game_view(
                    original_world,
                    capability_host=self._capability_host,
                    capability_determinism=determinism,
                    capability_event_sequence=sequence,
                )
                turn_world = original_world
                if isinstance(intent, LoadIntent):
                    turn_world = self._require_save_service().load(intent.slot)
                if capability_intent:
                    draft, focus = None, None
                else:
                    draft, focus = self._execute(
                        cast(GameIntent, intent),
                        world=turn_world,
                    )
                base_view = project_game_view(turn_world, focus=focus)
                prepared: object = _MISSING
                if self._capability_host is not None:
                    prepared = self._capability_host.prepare_turn(
                        intent,
                        before_view=before_view,
                        after_view=base_view,
                        event=draft,
                        determinism=determinism,
                        event_sequence=sequence,
                    )
                    capability_events = self._capability_host.prepared_events(prepared)
                    final_sequence = (
                        sequence
                        + (1 if draft is not None else 0)
                        + len(capability_events)
                    )
                    view = project_game_view(
                        turn_world,
                        focus=focus,
                        capability_host=self._capability_host,
                        capability_prepared=prepared,
                        capability_determinism=determinism,
                        capability_event_sequence=final_sequence,
                    )
                else:
                    view = base_view
                    capability_events = ()
                    final_sequence = sequence + (1 if draft is not None else 0)
                events = self._build_events(draft, capability_events, view, sequence)
                newly_completed_endings = _newly_completed_endings(
                    before_view,
                    view,
                    intent,
                )

                # Persistence is the final fallible operation. Everything after this
                # point is an assignment into already validated prepared state.
                if isinstance(intent, SaveIntent):
                    service = self._require_save_service()
                    save_file_snapshot = _capture_save_file(service, intent.slot)
                    service.save(turn_world, intent.slot)

                if isinstance(intent, LoadIntent):
                    self._world = turn_world
                if self._capability_host is not None:
                    self._capability_host.commit(prepared)
                self._event_sequence = final_sequence
                return TurnResult(
                    TurnStatus.ACCEPTED,
                    events,
                    view,
                    newly_completed_endings=newly_completed_endings,
                )
            except WorldRuleError as exc:
                try:
                    message = str(exc)
                finally:
                    self._restore(
                        original_world,
                        snapshot,
                        rng_state,
                        determinism,
                        determinism_state,
                        sequence,
                        capability_snapshot,
                        save_file_snapshot,
                    )
                return TurnResult(
                    TurnStatus.REJECTED,
                    (),
                    project_game_view(
                        self._world,
                        capability_host=self._capability_host,
                        capability_determinism=self._determinism,
                        capability_event_sequence=self._event_sequence,
                    ),
                    RejectionDiagnostic(RejectionCode.INADMISSIBLE_INTENT, message),
                )
            except SaveLoadError as exc:
                try:
                    message = _persistence_rejection_message(
                        cast(GameIntent, intent),
                        exc,
                    )
                finally:
                    self._restore(
                        original_world,
                        snapshot,
                        rng_state,
                        determinism,
                        determinism_state,
                        sequence,
                        capability_snapshot,
                        save_file_snapshot,
                    )
                return TurnResult(
                    TurnStatus.REJECTED,
                    (),
                    project_game_view(
                        self._world,
                        capability_host=self._capability_host,
                        capability_determinism=self._determinism,
                        capability_event_sequence=self._event_sequence,
                    ),
                    RejectionDiagnostic(
                        RejectionCode.PERSISTENCE_ERROR,
                        message,
                    ),
                )
            except Exception as exc:
                rejection_code = _capability_rejection_code(exc)
                self._restore(
                    original_world,
                    snapshot,
                    rng_state,
                    determinism,
                    determinism_state,
                    sequence,
                    capability_snapshot,
                    save_file_snapshot,
                )
                if rejection_code is not None:
                    return TurnResult(
                        TurnStatus.REJECTED,
                        (),
                        project_game_view(
                            self._world,
                            capability_host=self._capability_host,
                            capability_determinism=self._determinism,
                            capability_event_sequence=self._event_sequence,
                        ),
                        RejectionDiagnostic(
                            rejection_code,
                            _capability_rejection_message(rejection_code),
                        ),
                    )
                raise

    @staticmethod
    def _build_events(
        draft: _EventDraft | None,
        capability_events: tuple[CapabilityEventData, ...],
        view: GameView,
        sequence: int,
    ) -> tuple[GameEvent, ...]:
        events: list[GameEvent] = []
        next_sequence = sequence
        if draft is not None:
            kind, payload = draft
            payload = _player_safe_event_payload(payload, view)
            next_sequence += 1
            events.append(GameEvent(next_sequence, kind, payload))
        for payload in capability_events:
            next_sequence += 1
            events.append(
                GameEvent(
                    next_sequence,
                    GameEventKind.CAPABILITY,
                    payload,
                )
            )
        return tuple(events)

    def _execute(
        self,
        intent: GameIntent,
        *,
        world: World | None = None,
    ) -> tuple[_EventDraft | None, FocusView | None]:
        world = self._world if world is None else world
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
            return (
                GameEventKind.SAVE,
                PersistenceEventData(intent.slot or "default"),
            ), None
        if isinstance(intent, LoadIntent):
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
        snapshot: _WorldSnapshot,
        rng_state: _RngState,
        determinism: DeterminismContext,
        determinism_state: _DeterminismState,
        sequence: int,
        capability_snapshot: object = _MISSING,
        save_file_snapshot: _SaveFileSnapshot | None = None,
    ) -> None:
        _restore_world(snapshot)
        self._world = original_world
        self._rng.setstate(rng_state)
        seed, clock = determinism_state
        object.__setattr__(determinism, "seed", seed)
        object.__setattr__(determinism, "clock", clock)
        self._determinism = determinism
        self._event_sequence = sequence
        if (
            self._capability_host is not None
            and capability_snapshot is not _MISSING
        ):
            self._capability_host.restore(capability_snapshot)
        _restore_save_file(save_file_snapshot)

    @staticmethod
    def _validate_context(context: DeterminismContext) -> None:
        if (
            type(context) is not DeterminismContext
            or type(context.seed) is not int
            or type(context.clock) is not int
        ):
            raise ValueError("determinism seed and clock must be integers")


def validate_game_intent(intent: object) -> None:
    """Validate one exact V2-1 intent without invoking subclass behavior."""
    if not is_declared_game_intent(intent):
        raise _IntentValidationError("intent 必须是已声明的 GameIntent 子类型。")
    if isinstance(intent, ViewIntent):
        if type(intent.kind) is not ViewKind:
            raise _IntentValidationError("view kind 无效。")
        return
    if isinstance(intent, ExamineIntent):
        _validate_text(intent.target, "target")
        if intent.target_kind is not None and type(
            intent.target_kind
        ) is not ExamineTargetKind:
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
        if type(intent.slot) is not EquipmentSlot:
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
    if type(value) is not str:
        raise _IntentValidationError(f"{field} 必须是非空字符串。")
    normalized = value.strip()
    if not normalized:
        raise _IntentValidationError(f"{field} 必须是非空字符串。")
    if len(normalized) > maximum:
        raise _IntentValidationError(f"{field} 过长。")


def _validate_positive_int(value: object, field: str) -> None:
    if type(value) is not int or value < 1:
        raise _IntentValidationError(f"{field} 必须是正整数。")


def _persistence_rejection_message(
    intent: GameIntent,
    error: SaveLoadError,
) -> str:
    detail = str(error)
    if detail.startswith("存档服务不可用"):
        return "存档服务不可用。"
    if detail.startswith("存档槽位"):
        return "存档槽位无效。"
    if detail.startswith("存档文件不存在"):
        return "存档文件不存在。"
    if type(intent) is SaveIntent:
        return "写入存档失败。"
    if type(intent) is LoadIntent:
        return "读取存档失败。"
    return "存档操作失败。"


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
    room = outcome.room
    return MoveEventData(
        room_id=room.id,
        room_name=room.name,
        room=MoveRoomEvent(
            id=room.id,
            name=room.name,
            description=room.description,
            exits=tuple(
                MoveExitEvent(
                    direction=direction,
                    target_room_id=exit_definition.target_room_id,
                    required_item_id=exit_definition.required_item_id,
                )
                for direction, exit_definition in room.exits.items()
            ),
            item_stacks=tuple(
                MoveItemStackEvent(stack.item_id, stack.quantity)
                for stack in room.item_stacks
            ),
            monster_ids=tuple(room.monster_ids),
        ),
        quest_outcomes=_quest_outcomes(outcome.quest_outcomes),
        level_gains=_level_gains(outcome.level_gains),
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


def _player_safe_event_payload(
    payload: GameEventPayload,
    view: GameView,
) -> GameEventPayload:
    if isinstance(payload, DialogueEventData):
        dialogue = view.dialogue
        if dialogue is None or dialogue.dialogue_id != payload.dialogue_id:
            return replace(payload, options=())
        return replace(
            payload,
            options=tuple(
                DialogueOptionEvent(option.id, option.text)
                for option in dialogue.options
            ),
        )
    return payload


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
    # Raw effect outcomes can contain authoritative state omitted from GameView.
    return CampaignActionEventData(
        outcome.action_id,
        outcome.label,
        outcome.result_text,
        (),
    )


def _newly_completed_endings(
    before_view: GameView,
    after_view: GameView,
    intent: GameIntent | CapabilityIntent,
) -> tuple[EndingView, ...]:
    """Report only a newly reached terminal state, never a restored save."""
    if isinstance(intent, (LoadIntent, SaveIntent, ViewIntent)):
        return ()
    before_ids = {
        ending.id for ending in before_view.campaign.completion.endings
    }
    return tuple(
        ending
        for ending in after_view.campaign.completion.endings
        if ending.id not in before_ids
    )


def _recovery_event(outcome: RecoverOutcome) -> RecoveryEventData:
    return RecoveryEventData(
        outcome.start_room_id,
        outcome.room_name,
        outcome.hp,
        outcome.max_hp,
    )
