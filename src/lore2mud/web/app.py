"""Web parsing and rendering adapters for the shared application boundary."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
import shlex
from typing import TypeAlias, cast

from lore2mud.application.contracts import (
    AttackIntent,
    BuyIntent,
    CampaignActionEventData,
    CampaignActionIntent,
    ChooseDialogueIntent,
    CombatEventData,
    DeterminismContext,
    DialogueEndEventData,
    DialogueEventData,
    DropIntent,
    EndDialogueIntent,
    EquipIntent,
    EquipmentEventData,
    EquipmentSlot,
    GameEvent,
    GameIntent,
    GameView,
    ItemTransferEventData,
    LoadIntent,
    MoveEventData,
    MoveIntent,
    PersistenceEventData,
    RecoverIntent,
    RecoveryEventData,
    RejectionCode,
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
)
from lore2mud.application.session import GameSession, validate_game_intent
from lore2mud.capabilities.contracts import (
    CanonicalJsonObject,
    CapabilityEventData,
    CapabilityIntent,
    CapabilityPlayerViewEntry,
)
from lore2mud.capabilities.serialization import (
    canonical_json_object,
    capability_value_to_document,
)
from lore2mud.capabilities.runtime import CapabilityRuntimeHost
from lore2mud.content.models import ContentPack
from lore2mud.engine.commands import CommandProcessor
from lore2mud.engine.save import SaveLoadService
from lore2mud.engine.world import World


JsonValue: TypeAlias = (
    str | int | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
)


class PlayerActionError(ValueError):
    """Raised when an untrusted browser action is malformed."""


_ACTION_FIELDS: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "move": (frozenset({"direction"}), frozenset()),
    "take": (frozenset({"target"}), frozenset({"quantity"})),
    "drop": (frozenset({"target"}), frozenset({"quantity"})),
    "use": (frozenset({"target"}), frozenset({"quantity"})),
    "equip": (frozenset({"target"}), frozenset()),
    "unequip": (frozenset({"slot"}), frozenset()),
    "attack": (frozenset({"target"}), frozenset()),
    "talk": (frozenset({"target"}), frozenset()),
    "choose_dialogue": (frozenset({"index"}), frozenset()),
    "end_dialogue": (frozenset(), frozenset()),
    "buy": (frozenset({"target"}), frozenset({"quantity"})),
    "sell": (frozenset({"target"}), frozenset({"quantity"})),
    "save": (frozenset(), frozenset({"slot"})),
    "load": (frozenset(), frozenset({"slot"})),
    "recover": (frozenset(), frozenset()),
    "campaign_action": (frozenset({"action_id"}), frozenset()),
    "capability": (
        frozenset({"capability_id", "action_id", "parameters"}),
        frozenset(),
    ),
    "command": (frozenset({"command"}), frozenset()),
}
_READ_ONLY_COMMANDS = frozenset({
    "help",
    "i",
    "inventory",
    "actions",
    "journal",
    "knowledge",
    "look",
    "objectives",
    "quests",
    "status",
})


class PlayerSession:
    """Keep the legacy Web composition name while delegating turns to GameSession."""

    def __init__(
        self,
        pack: ContentPack,
        save_service: SaveLoadService,
        *,
        player_name: str = "旅人",
        determinism: DeterminismContext | None = None,
        capability_host: CapabilityRuntimeHost | None = None,
    ) -> None:
        self._session = GameSession.from_content_pack(
            pack,
            save_service,
            player_name=player_name,
            determinism=determinism,
            capability_host=capability_host,
        )
        self._commands = CommandProcessor.from_session(self._session)
        self._last_turn_result: TurnResult | None = None

    @property
    def world(self) -> World:
        """Return the current compatibility World for existing integrations."""
        return self._session.world

    @property
    def game_session(self) -> GameSession:
        return self._session

    @property
    def last_turn_result(self) -> TurnResult | None:
        return self._last_turn_result

    def dispatch(self, raw_action: object) -> dict[str, JsonValue]:
        """Parse one Web action, submit one typed turn, and render its result."""
        try:
            action_type, action = self._validate_action(raw_action)
            if action_type == "command":
                return self._dispatch_command(action)
            intent = self._intent(action_type, action)
        except PlayerActionError as exc:
            result = self._session.reject(
                RejectionCode.MALFORMED_INTENT,
                str(exc),
            )
            self._last_turn_result = result
            return self._render_response(
                result,
                legacy_type="error",
                message=str(exc),
                legacy_data={},
            )

        result = self._session.submit(cast(GameIntent, intent))
        self._last_turn_result = result
        if result.status is TurnStatus.REJECTED:
            assert result.rejection is not None
            return self._render_response(
                result,
                legacy_type="error",
                message=result.rejection.message,
                legacy_data={},
            )
        event = result.events[0] if result.events else None
        return self._render_response(
            result,
            legacy_type=event.kind.value if event is not None else action_type,
            message=self._message(action_type, event),
            legacy_data=self._legacy_event_data(event),
        )

    def snapshot(self) -> dict[str, JsonValue]:
        """Return the compatibility JSON snapshot rendered from GameView."""
        return self._legacy_snapshot(self._session.view())

    def _dispatch_command(
        self,
        action: dict[str, object],
    ) -> dict[str, JsonValue]:
        command = self._text(action, "command", maximum=500)
        self._validate_fallback_command(command)
        command_result = self._commands.execute(command)
        turn = command_result.turn_result
        if turn is None:
            turn = TurnResult(TurnStatus.ACCEPTED, (), self._session.view())
        self._last_turn_result = turn
        event_type = "command" if turn.status is TurnStatus.ACCEPTED else "error"
        return self._render_response(
            turn,
            legacy_type=event_type,
            message=command_result.text,
            legacy_data={
                "command": command,
                "should_quit": command_result.should_quit,
            },
        )

    @staticmethod
    def _validate_action(
        raw_action: object,
    ) -> tuple[str, dict[str, object]]:
        if type(raw_action) is not dict:
            raise PlayerActionError("action 必须是 JSON 对象。")
        if not all(type(key) is str for key in raw_action):
            raise PlayerActionError("action 字段名必须是字符串。")
        action = dict(raw_action)
        action_type = action.get("type")
        if type(action_type) is not str or not action_type:
            raise PlayerActionError("action.type 必须是非空字符串。")
        schema = _ACTION_FIELDS.get(action_type)
        if schema is None:
            raise PlayerActionError(f"未知 action 类型：{action_type}。")
        required, optional = schema
        keys = set(action) - {"type"}
        missing = required - keys
        unknown = keys - required - optional
        if missing:
            raise PlayerActionError(
                f"action {action_type} 缺少字段：{', '.join(sorted(missing))}。"
            )
        if unknown:
            raise PlayerActionError(
                f"action {action_type} 包含未知字段：{', '.join(sorted(unknown))}。"
            )
        return action_type, action

    @staticmethod
    def _text(
        action: dict[str, object],
        field: str,
        *,
        maximum: int = 200,
    ) -> str:
        value = action.get(field)
        if type(value) is not str:
            raise PlayerActionError(f"action.{field} 必须是非空字符串。")
        normalized = value.strip()
        if not normalized:
            raise PlayerActionError(f"action.{field} 必须是非空字符串。")
        if len(normalized) > maximum:
            raise PlayerActionError(f"action.{field} 过长。")
        return normalized

    @staticmethod
    def _quantity(action: dict[str, object], field: str = "quantity") -> int:
        value = action.get(field, 1)
        if type(value) is not int or value < 1:
            raise PlayerActionError(f"action.{field} 必须是正整数。")
        return value

    @staticmethod
    def _slot(action: dict[str, object]) -> str | None:
        if "slot" not in action:
            return None
        value = action["slot"]
        if value is None:
            return None
        if type(value) is not str:
            raise PlayerActionError("action.slot 必须是非空字符串或 null。")
        normalized = value.strip()
        if not normalized:
            raise PlayerActionError("action.slot 必须是非空字符串或 null。")
        return normalized

    def _intent(
        self,
        action_type: str,
        action: dict[str, object],
    ) -> GameIntent | CapabilityIntent:
        if action_type == "capability":
            try:
                parameters = canonical_json_object(action["parameters"])
            except (TypeError, ValueError) as exc:
                raise PlayerActionError(
                    "action.parameters must be a bounded canonical JSON object."
                ) from exc
            return CapabilityIntent(
                capability_id=self._text(action, "capability_id"),
                action_id=self._text(action, "action_id"),
                parameters=parameters,
            )
        if action_type == "move":
            return MoveIntent(self._text(action, "direction", maximum=32))
        if action_type == "take":
            return TakeIntent(self._text(action, "target"), self._quantity(action))
        if action_type == "drop":
            return DropIntent(self._text(action, "target"), self._quantity(action))
        if action_type == "use":
            return UseIntent(self._text(action, "target"), self._quantity(action))
        if action_type == "equip":
            return EquipIntent(self._text(action, "target"))
        if action_type == "unequip":
            slot = self._text(action, "slot", maximum=16).casefold()
            try:
                equipment_slot = EquipmentSlot(slot)
            except ValueError as exc:
                raise PlayerActionError("action.slot 必须是 hand 或 body。") from exc
            return UnequipIntent(equipment_slot)
        if action_type == "attack":
            return AttackIntent(self._text(action, "target"))
        if action_type == "talk":
            return TalkIntent(self._text(action, "target"))
        if action_type == "choose_dialogue":
            return ChooseDialogueIntent(self._quantity(action, "index"))
        if action_type == "end_dialogue":
            return EndDialogueIntent()
        if action_type == "buy":
            return BuyIntent(self._text(action, "target"), self._quantity(action))
        if action_type == "sell":
            return SellIntent(self._text(action, "target"), self._quantity(action))
        if action_type == "save":
            return SaveIntent(self._slot(action))
        if action_type == "load":
            return LoadIntent(self._slot(action))
        if action_type == "recover":
            return RecoverIntent()
        if action_type == "campaign_action":
            return CampaignActionIntent(self._text(action, "action_id"))
        raise PlayerActionError(f"未知 action 类型：{action_type}。")

    @staticmethod
    def _validate_fallback_command(command: str) -> None:
        try:
            parts = shlex.split(command)
        except ValueError as exc:
            raise PlayerActionError(f"无法解析指令：{exc}") from exc
        if len(parts) != 1 or parts[0].casefold() not in _READ_ONLY_COMMANDS:
            allowed = ", ".join(sorted(_READ_ONLY_COMMANDS))
            raise PlayerActionError(
                "命令入口仅接受无参数只读指令："
                f"{allowed}。其他行动请使用结构化界面控件。"
            )

    @staticmethod
    def _render_response(
        result: TurnResult,
        *,
        legacy_type: str,
        message: str,
        legacy_data: dict[str, JsonValue],
    ) -> dict[str, JsonValue]:
        diagnostics: list[JsonValue] = []
        if result.rejection is not None:
            diagnostics.append({
                "code": result.rejection.code.value,
                "message": result.rejection.message,
            })
        return {
            "ok": result.status is TurnStatus.ACCEPTED,
            "status": result.status.value,
            "events": [PlayerSession._event_json(event) for event in result.events],
            "view": PlayerSession._json_value(result.view),
            "diagnostics": diagnostics,
            "event": {
                "type": legacy_type,
                "message": message,
                "data": legacy_data,
            },
            "snapshot": PlayerSession._legacy_snapshot(result.view),
        }

    @staticmethod
    def _event_json(event: GameEvent) -> dict[str, JsonValue]:
        return {
            "sequence": event.sequence,
            "type": event.kind.value,
            "data": PlayerSession._json_value(event.payload),
        }

    @staticmethod
    def _legacy_event_data(event: GameEvent | None) -> dict[str, JsonValue]:
        if event is None:
            return {}
        payload = event.payload
        if isinstance(payload, CapabilityEventData):
            return cast(dict[str, JsonValue], PlayerSession._json_value(payload))
        if isinstance(payload, CombatEventData):
            return {
                "combat": {
                    "monster_name": payload.monster_name,
                    "damage_to_monster": payload.damage_to_monster,
                    "damage_to_player": payload.damage_to_player,
                    "monster_defeated": payload.monster_defeated,
                    "player_defeated": payload.player_defeated,
                    "experience_reward": payload.experience_reward,
                },
                "combat_level_gains": PlayerSession._json_value(
                    payload.combat_level_gains
                ),
                "quest_outcomes": PlayerSession._json_value(
                    payload.quest_outcomes
                ),
                "level_gains": PlayerSession._json_value(payload.level_gains),
                "loot_item": PlayerSession._json_value(payload.loot_item),
            }
        if isinstance(payload, MoveEventData):
            return {
                "room": {
                    "id": payload.room.id,
                    "name": payload.room.name,
                    "description": payload.room.description,
                    "exits": {
                        exit_value.direction: {
                            "target_room_id": exit_value.target_room_id,
                            "required_item_id": exit_value.required_item_id,
                        }
                        for exit_value in payload.room.exits
                    },
                    "item_stacks": [
                        {
                            "item_id": stack.item_id,
                            "quantity": stack.quantity,
                        }
                        for stack in payload.room.item_stacks
                    ],
                    "monster_ids": list(payload.room.monster_ids),
                },
                "quest_outcomes": PlayerSession._legacy_json_value(
                    payload.quest_outcomes
                ),
                "level_gains": PlayerSession._legacy_json_value(payload.level_gains),
            }
        value = PlayerSession._legacy_json_value(payload)
        assert isinstance(value, dict)
        return value

    @staticmethod
    def _message(action_type: str, event: GameEvent | None) -> str:
        if event is None:
            return "行动已接受。"
        payload = event.payload
        if isinstance(payload, MoveEventData):
            return f"来到 {payload.room_name}。"
        if isinstance(payload, ItemTransferEventData):
            return (
                f"拾取 {payload.item_name}。"
                if action_type == "take"
                else f"放下 {payload.item_name}。"
            )
        if isinstance(payload, UseEventData):
            return f"使用 {payload.item_name}。"
        if isinstance(payload, EquipmentEventData):
            return (
                f"装备 {payload.item_name}。"
                if action_type == "equip"
                else f"卸下 {payload.item_name}。"
            )
        if isinstance(payload, CombatEventData):
            return (
                f"攻击 {payload.monster_name}，"
                f"造成 {payload.damage_to_monster} 点伤害。"
            )
        if isinstance(payload, DialogueEventData):
            return (
                f"与 {payload.character_name} 对话。"
                if action_type == "talk"
                else "选择了对话回应。"
            )
        if isinstance(payload, DialogueEndEventData):
            return "结束对话。"
        if isinstance(payload, TradeEventData):
            return (
                f"购买 {payload.item_name}。"
                if action_type == "buy"
                else f"出售 {payload.item_name}。"
            )
        if isinstance(payload, RecoveryEventData):
            return f"在 {payload.room_name} 恢复。"
        if isinstance(payload, CampaignActionEventData):
            return payload.result_text
        if isinstance(payload, CapabilityEventData):
            return "Capability action accepted."
        if isinstance(payload, PersistenceEventData):
            return (
                f"已保存到 {payload.slot}。"
                if action_type == "save"
                else f"已读取 {payload.slot}。"
            )
        return "行动已接受。"

    @staticmethod
    def _legacy_snapshot(view: GameView) -> dict[str, JsonValue]:
        value = PlayerSession._json_value(view)
        assert isinstance(value, dict)
        value.pop("focus", None)

        room = value["room"]
        assert isinstance(room, dict)
        exits = room["exits"]
        assert isinstance(exits, list)
        for exit_value in exits:
            assert isinstance(exit_value, dict)
            exit_value.setdefault("required_item_id", None)
            exit_value.setdefault("required_item_name", None)

        for item_values in (room["items"], value["inventory"]):
            assert isinstance(item_values, list)
            for item_value in item_values:
                assert isinstance(item_value, dict)
                item_value.setdefault("heal_amount", None)
                item_value.setdefault("slot", None)

        campaign = value["campaign"]
        assert isinstance(campaign, dict)
        for entry_group in ("objectives", "knowledge", "journal"):
            entries = campaign[entry_group]
            assert isinstance(entries, list)
            for entry in entries:
                assert isinstance(entry, dict)
                entry.setdefault("status", None)

        value["dialogue"] = (
            PlayerSession._json_value(view.dialogue)
            if view.dialogue is not None
            else None
        )
        value["shop"] = (
            PlayerSession._json_value(view.shop)
            if view.shop is not None
            else None
        )
        value["equipment"] = {
            "hand": (
                PlayerSession._json_value(view.equipment.hand)
                if view.equipment.hand is not None
                else None
            ),
            "body": (
                PlayerSession._json_value(view.equipment.body)
                if view.equipment.body is not None
                else None
            ),
        }
        return value

    @staticmethod
    def _json_value(value: object) -> JsonValue:
        if value is None or isinstance(value, (str, int, bool)):
            return value
        if type(value) is CapabilityIntent:
            return PlayerSession._intent_json(value)
        if type(value) is CapabilityEventData:
            return {
                "capability_id": value.capability_id,
                "event_id": value.event_id,
                "payload": PlayerSession._json_value(value.payload),
            }
        if type(value) is CapabilityPlayerViewEntry:
            return {
                "capability_id": value.capability_id,
                "version": str(value.version),
                "view": PlayerSession._json_value(value.view),
                "admissible_intents": [
                    PlayerSession._intent_json(item)
                    for item in value.admissible_intents
                ],
            }
        if type(value) is CanonicalJsonObject:
            return cast(JsonValue, capability_value_to_document(value))
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, GameIntent):
            return PlayerSession._intent_json(value)
        if isinstance(value, (tuple, list)):
            return [PlayerSession._json_value(item) for item in value]
        if isinstance(value, dict):
            return {
                str(key): PlayerSession._json_value(item)
                for key, item in value.items()
            }
        if is_dataclass(value) and not isinstance(value, type):
            result: dict[str, JsonValue] = {}
            for definition in fields(value):
                item = getattr(value, definition.name)
                if item is None:
                    continue
                result[definition.name] = PlayerSession._json_value(item)
            return result
        raise TypeError(f"unsupported JSON projection value: {type(value).__name__}")

    @staticmethod
    def _legacy_json_value(value: object) -> JsonValue:
        if value is None:
            return None
        if type(value) in {
            CapabilityIntent,
            CapabilityEventData,
            CapabilityPlayerViewEntry,
            CanonicalJsonObject,
        }:
            return PlayerSession._json_value(value)
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, (str, int, bool)):
            return value
        if isinstance(value, (tuple, list)):
            return [PlayerSession._legacy_json_value(item) for item in value]
        if isinstance(value, dict):
            return {
                str(key): PlayerSession._legacy_json_value(item)
                for key, item in value.items()
            }
        if is_dataclass(value) and not isinstance(value, type):
            return {
                definition.name: PlayerSession._legacy_json_value(
                    getattr(value, definition.name)
                )
                for definition in fields(value)
            }
        raise TypeError(
            f"unsupported legacy JSON value: {type(value).__name__}"
        )

    @staticmethod
    def _intent_json(
        intent: GameIntent | CapabilityIntent,
    ) -> dict[str, JsonValue]:
        if type(intent) is CapabilityIntent:
            document = capability_value_to_document(intent)
            if type(document) is not dict:
                raise TypeError("invalid CapabilityIntent")
            return {
                "type": "capability",
                **cast(dict[str, JsonValue], document),
            }
        try:
            validate_game_intent(intent)
        except ValueError as exc:
            raise TypeError(f"invalid GameIntent: {exc}") from exc
        if isinstance(intent, MoveIntent):
            return {"type": "move", "direction": intent.direction}
        if isinstance(intent, TakeIntent):
            return {
                "type": "take",
                "target": intent.target,
                "quantity": intent.quantity,
            }
        if isinstance(intent, DropIntent):
            return {
                "type": "drop",
                "target": intent.target,
                "quantity": intent.quantity,
            }
        if isinstance(intent, UseIntent):
            return {
                "type": "use",
                "target": intent.target,
                "quantity": intent.quantity,
            }
        if isinstance(intent, EquipIntent):
            return {"type": "equip", "target": intent.target}
        if isinstance(intent, UnequipIntent):
            return {"type": "unequip", "slot": intent.slot.value}
        if isinstance(intent, AttackIntent):
            return {"type": "attack", "target": intent.target}
        if isinstance(intent, TalkIntent):
            return {"type": "talk", "target": intent.target}
        if isinstance(intent, ChooseDialogueIntent):
            return {"type": "choose_dialogue", "index": intent.index}
        if isinstance(intent, EndDialogueIntent):
            return {"type": "end_dialogue"}
        if isinstance(intent, BuyIntent):
            return {
                "type": "buy",
                "target": intent.target,
                "quantity": intent.quantity,
            }
        if isinstance(intent, SellIntent):
            return {
                "type": "sell",
                "target": intent.target,
                "quantity": intent.quantity,
            }
        if isinstance(intent, CampaignActionIntent):
            return {"type": "campaign_action", "action_id": intent.action_id}
        if isinstance(intent, RecoverIntent):
            return {"type": "recover"}
        if isinstance(intent, SaveIntent):
            return {"type": "save", "slot": intent.slot}
        if isinstance(intent, LoadIntent):
            return {"type": "load", "slot": intent.slot}
        raise TypeError(f"unsupported Web intent: {type(intent).__name__}")
