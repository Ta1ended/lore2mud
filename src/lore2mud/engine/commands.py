"""Parse player intent and render deterministic text responses."""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from typing import Protocol

from lore2mud.application.contracts import (
    AcceptedQuestEvent,
    AttackIntent,
    BuyIntent,
    CampaignActionEventData,
    CampaignActionIntent,
    CharacterFocusView,
    ChooseDialogueIntent,
    CombatEventData,
    DialogueEndEventData,
    DialogueEventData,
    DialogueView,
    DropIntent,
    EndDialogueIntent,
    EquipIntent,
    EquipmentEventData,
    EquipmentSlot,
    ExamineIntent,
    ExamineTargetKind,
    ExitView,
    FlagChangeEvent,
    GameIntent,
    GameView,
    GrantedExperienceEvent,
    GrantedItemEvent,
    ItemFocusView,
    ItemTransferEventData,
    LoadIntent,
    MonsterFocusView,
    MoveEventData,
    MoveIntent,
    PersistenceEventData,
    QuestCompletionEvent,
    QuestKind,
    QuestTargetView,
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
    ViewIntent,
    ViewKind,
)
from lore2mud.application.session import GameSession
from lore2mud.engine.world import World


class _SaveService(Protocol):
    def save(self, world: World, slot: str | None = None) -> str: ...

    def load(self, slot: str | None = None) -> World: ...


_BARE_SELECTION = re.compile(r'^[1-9][0-9]{0,4}$')

# Numeric style patterns for quantity parsing
_UNSIGNED_INT = re.compile(r'^[0-9]+$')
_SIGNED_INT = re.compile(r'^[+-][0-9]+$')
_DECIMAL_OR_EXPONENT = re.compile(
    r'^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$'
)
_HEX = re.compile(r'^[+-]?0[xX][0-9a-fA-F]+$')
_BINARY = re.compile(r'^[+-]?0[bB][01]+$')
_OCTAL = re.compile(r'^[+-]?0[oO][0-7]+$')
_SPECIAL = re.compile(r'^[+-]?(?:inf|infinity|nan)$', re.IGNORECASE)


def _classify_quantity_token(token: str) -> tuple[str, int | None]:
    """Classify a tail token for quantity parsing.

    Returns:
        ("valid", n)    -- legal unsigned positive integer
        ("invalid", None) -- looks numeric but not a legal quantity
        ("name", None)    -- not numeric, treat as item name part
    """
    if not token:
        return ("name", None)

    # Unsigned pure digit string
    if _UNSIGNED_INT.match(token):
        n = int(token)
        return ("valid", n) if n > 0 else ("invalid", None)

    # Various numeric styles that are NOT valid quantities
    if (_SIGNED_INT.match(token)
            or _DECIMAL_OR_EXPONENT.match(token)
            or _HEX.match(token)
            or _BINARY.match(token)
            or _OCTAL.match(token)
            or _SPECIAL.match(token)):
        return ("invalid", None)

    # Ordinary name
    return ("name", None)


def _parse_quantity(
    arguments: list[str],
    usage: str,
) -> tuple[str, int, str | None]:
    """Parse tail quantity from arguments.

    Returns (query, quantity, error).
    error non-empty means return it directly.
    """
    if not arguments:
        return ("", 1, f"用法：{usage}")

    last = arguments[-1]
    kind, val = _classify_quantity_token(last)

    if kind == "valid":
        assert val is not None
        rest = arguments[:-1]
        if not rest:
            return ("", val, f"用法：{usage}")
        return (" ".join(rest), val, None)

    if kind == "invalid":
        return (" ".join(arguments), 1, "数量必须为正整数。")

    # kind == "name": no quantity suffix, default to 1
    return (" ".join(arguments), 1, None)


@dataclass(frozen=True, slots=True)
class CommandResult:
    text: str
    should_quit: bool = False
    turn_result: TurnResult | None = None


@dataclass(frozen=True, slots=True)
class CommandSpec:
    """One authoritative route and help contract."""

    name: str
    syntax: str
    summary: str
    parameters: str
    context: str
    allowed_when_dead: bool
    handler_name: str | None
    aliases: tuple[str, ...] = ()


COMMAND_SPECS = (
    CommandSpec(
        "look", "look", "查看当前房间", "无。",
        "只读显示当前房间摘要；活动对话保持不变。", True, "_command_look",
    ),
    CommandSpec(
        "examine",
        "examine [room|here|<目标ID或名称>|item <物品ID或名称>|"
        "monster <怪物ID或名称>|character <角色ID或名称>]",
        "查看当前可见目标或房间摘要",
        "无参数、room 或 here 查看当前房间；可用类型限定消除歧义。",
        "仅可见当前房间物品、背包物品、当前房间怪物和角色；只读且不结束对话。",
        True,
        "_examine",
    ),
    CommandSpec(
        "inspect", "inspect <物品ID或名称>", "兼容的物品专用查看",
        "一个可含空格的物品稳定 ID 或名称。",
        "仅查看当前房间或背包物品；只读且不结束对话。", True, "_inspect",
    ),
    CommandSpec(
        "go", "go <方向>", "沿当前房间出口移动",
        "一个方向，例如 north。", "方向必须是当前房间出口。", False, "_go",
    ),
    CommandSpec(
        "take", "take <物品ID或名称> [数量]", "拾取当前房间物品",
        "物品查询可含空格；数量省略时为 1，必须是正整数。",
        "目标必须在当前房间，背包必须可容纳。", False, "_take",
    ),
    CommandSpec(
        "drop", "drop <物品ID或名称> [数量]", "放下背包物品",
        "物品查询可含空格；数量省略时为 1，必须是正整数。",
        "目标必须在背包且未装备。", False, "_drop",
    ),
    CommandSpec(
        "use", "use <物品ID或名称> [数量]", "使用消耗品",
        "物品查询可含空格；数量省略时为 1，必须是正整数。",
        "目标必须是背包中的未装备消耗品，且角色必须有生命损失。", False, "_use",
    ),
    CommandSpec(
        "equip", "equip <物品ID或名称>", "装备物品",
        "一个可含空格的物品稳定 ID 或名称。",
        "目标必须是背包中数量为 1 的 hand 或 body 装备。", False, "_equip",
    ),
    CommandSpec(
        "unequip", "unequip [hand|body]", "卸下装备",
        "可选槽位为 hand 或 body；省略时为 hand。",
        "指定槽位必须已有装备。", False, "_unequip",
    ),
    CommandSpec(
        "inventory", "inventory", "查看背包", "无。",
        "只读；别名 inv、i。", True, "_command_inventory", ("inv", "i"),
    ),
    CommandSpec(
        "actions", "actions", "查看当前场景动作", "无。",
        "只读显示 World 当前投影出的 campaign 动作。", True, "_campaign_actions",
    ),
    CommandSpec(
        "act", "act <动作ID>", "执行当前场景动作",
        "一个当前可用动作的稳定 ID。",
        "动作必须出现在 World 的当前投影中；完整效果列表原子执行。", False, "_act",
    ),
    CommandSpec(
        "objectives", "objectives", "查看分阶段目标", "无。",
        "只读显示已激活、进行、完成或失败的 campaign 目标。", True, "_objectives",
    ),
    CommandSpec(
        "knowledge", "knowledge", "查看玩家知识", "无。",
        "只读显示玩家已获知的内容，不显示 unknown 条目。", True, "_knowledge",
    ),
    CommandSpec(
        "journal", "journal", "查看叙事日志", "无。",
        "只读显示当前条件允许的故事、目标与知识日志。", True, "_journal",
    ),
    CommandSpec(
        "quests", "quests", "查看已接取任务", "无。",
        "只读显示当前任务状态。", True, "_command_quests",
    ),
    CommandSpec(
        "status", "status", "查看角色状态", "无。",
        "只读显示属性、金币和 flags。", True, "_command_status",
    ),
    CommandSpec(
        "shop", "shop", "查看当前房间商店", "无。",
        "当前房间必须有商店；只读且不结束对话。", True, "_shop",
    ),
    CommandSpec(
        "buy", "buy <物品ID或名称> [数量]", "从当前商店购买",
        "物品查询可含空格；数量省略时为 1，必须是正整数。",
        "当前房间必须有商店，并满足目录、金币、容量和栈上限规则。", False, "_buy",
    ),
    CommandSpec(
        "sell", "sell <物品ID或名称> [数量]", "向当前商店出售",
        "物品查询可含空格；数量省略时为 1，必须是正整数。",
        "当前房间必须有商店，目标必须在背包、可售且未装备。", False, "_sell",
    ),
    CommandSpec(
        "attack", "attack <怪物ID或名称>", "攻击当前房间怪物",
        "一个可含空格的怪物稳定 ID 或名称。",
        "目标必须是当前房间仍存活的怪物。", False, "_attack",
    ),
    CommandSpec(
        "talk", "talk <角色ID或名称>", "与当前房间角色对话",
        "一个可含空格的角色稳定 ID 或名称。",
        "目标必须在当前房间且拥有对话；切换目标会结束旧对话。", False, "_talk",
    ),
    CommandSpec(
        "<数字>", "<数字>", "选择活动对话选项", "1 至 99999 的十进制整数。",
        "仅在活动对话中可用；带其他参数不会被解析为选项。", False, None,
    ),
    CommandSpec(
        "bye", "bye", "结束活动对话", "无。",
        "仅在活动对话中可用。", False, "_bye",
    ),
    CommandSpec(
        "save", "save [槽位]", "保存游戏", "可选安全槽位名；省略时为 default。",
        "需要可用的存档服务。", True, "_save",
    ),
    CommandSpec(
        "load", "load [槽位]", "读取存档", "可选安全槽位名；省略时为 default。",
        "需要可用的存档服务及有效存档；成功后替换整个 World。", True, "_load",
    ),
    CommandSpec(
        "recover", "recover", "恢复倒下的角色", "无。",
        "仅在角色倒下时可用。", True, "_recover",
    ),
    CommandSpec(
        "help", "help [command]", "查看总帮助或单条指令帮助",
        "可选一个指令名或别名。", "只读。", True, "_help",
    ),
    CommandSpec(
        "quit", "quit", "退出游戏", "无。", "别名 exit。",
        True, "_quit", ("exit",),
    ),
)


_SELECTION_SPEC = next(spec for spec in COMMAND_SPECS if spec.name == "<数字>")


def _build_command_map() -> dict[str, CommandSpec]:
    routes: dict[str, CommandSpec] = {}
    for spec in COMMAND_SPECS:
        if spec.handler_name is None:
            continue
        for token in (spec.name, *spec.aliases):
            normalized = token.casefold()
            if normalized in routes:
                raise RuntimeError(f"重复命令路由：{token}")
            routes[normalized] = spec
    return routes


_COMMAND_BY_TOKEN = _build_command_map()
_HELP_BY_TOKEN = dict(_COMMAND_BY_TOKEN)
_HELP_BY_TOKEN[_SELECTION_SPEC.name] = _SELECTION_SPEC
_DEAD_ALLOWED = frozenset(
    token
    for token, spec in _COMMAND_BY_TOKEN.items()
    if spec.allowed_when_dead
)


def _render_help_index() -> str:
    lines = ["可用指令："]
    lines.extend(f"  {spec.syntax} — {spec.summary}" for spec in COMMAND_SPECS)
    lines.append("使用 help <command> 查看语法、参数和限制。")
    return "\n".join(lines)


HELP_TEXT = _render_help_index()


class CommandProcessor:
    def __init__(
        self,
        world: World | None = None,
        save_service: _SaveService | None = None,
        *,
        session: GameSession | None = None,
    ) -> None:
        if session is None:
            if world is None:
                raise TypeError("world or session is required")
            self._session = GameSession(world, save_service)
        else:
            if world is not None or save_service is not None:
                raise TypeError("session cannot be combined with world or save_service")
            self._session = session
        self._last_turn_result: TurnResult | None = None

    @classmethod
    def from_session(cls, session: GameSession) -> "CommandProcessor":
        return cls(session=session)

    @property
    def world(self) -> World:
        """Return the current compatibility World for existing integrations."""
        return self._session.world

    @property
    def session(self) -> GameSession:
        return self._session

    @property
    def last_turn_result(self) -> TurnResult | None:
        return self._last_turn_result

    def execute(self, raw_command: str) -> CommandResult:
        self._last_turn_result = None
        if type(raw_command) is not str:
            return self._error("命令必须是字符串。")
        try:
            parts = shlex.split(raw_command.strip())
        except ValueError as exc:
            return self._error(f"无法解析指令：{exc}")
        if not parts:
            return self._error("请输入指令；使用 help 查看帮助。")

        command = parts[0].casefold()
        arguments = parts[1:]
        view = self._session.view()

        # Preserve DEC-0020 ordering: death gates before dialogue routing
        # and before unknown-command feedback.
        if not view.player.alive and command not in _DEAD_ALLOWED:
            from lore2mud.engine.world import _DEAD_ERROR

            return self._error(_DEAD_ERROR, RejectionCode.INADMISSIBLE_INTENT)

        if len(parts) == 1 and _BARE_SELECTION.fullmatch(parts[0]):
            if view.dialogue is not None:
                return self._select_option(int(parts[0]))
            return self._error(f"未知指令：{parts[0]}。使用 help 查看帮助。")

        if command == "bye" and view.dialogue is None:
            return self._error(f"未知指令：{parts[0]}。使用 help 查看帮助。")

        spec = _COMMAND_BY_TOKEN.get(command)
        if spec is None or spec.handler_name is None:
            return self._error(f"未知指令：{parts[0]}。使用 help 查看帮助。")
        handler = getattr(self, spec.handler_name)
        return handler(arguments)

    def _submit(self, intent: GameIntent) -> TurnResult:
        result = self._session.submit(intent)
        self._last_turn_result = result
        return result

    def _error(
        self,
        text: str,
        code: RejectionCode = RejectionCode.MALFORMED_INTENT,
    ) -> CommandResult:
        result = self._session.reject(code, text)
        self._last_turn_result = result
        return CommandResult(text, turn_result=result)

    @staticmethod
    def _rejected(result: TurnResult, *, prefix: str = "") -> CommandResult:
        assert result.status is TurnStatus.REJECTED
        assert result.rejection is not None
        return CommandResult(
            f"{prefix}{result.rejection.message}",
            turn_result=result,
        )

    def _command_look(self, arguments: list[str]) -> CommandResult:
        if arguments:
            return self._error("用法：look")
        result = self._submit(ViewIntent(ViewKind.LOOK))
        return CommandResult(self._look(result.view), turn_result=result)

    @staticmethod
    def _look(view: GameView) -> str:
        room = view.room
        lines = [f"{room.name} [{room.id}]", room.description]
        exits = "、".join(
            CommandProcessor._render_exit(exit_view) for exit_view in room.exits
        ) if room.exits else "无"
        lines.append(f"出口：{exits}")

        if room.items:
            items = "、".join(
                f"{item.name} ×{item.quantity}" if item.quantity > 1 else item.name
                for item in room.items
            )
            lines.append(f"物品：{items}")

        if room.monsters:
            monsters = "、".join(
                f"{monster.name} ({monster.id})" for monster in room.monsters
            )
            lines.append(f"怪物：{monsters}")

        if room.characters:
            characters = "、".join(
                f"{character.name} ({character.id})"
                for character in room.characters
            )
            lines.append(f"角色：{characters}")

        if view.shop is not None:
            lines.append(f"商店：{view.shop.name} ({view.shop.id})")

        if view.campaign.scenes:
            lines.append(
                "场景："
                + "、".join(
                    f"{scene.name} ({scene.id})" for scene in view.campaign.scenes
                )
            )
        if view.campaign.interactables:
            lines.append(
                "交互："
                + "、".join(
                    f"{interactable.name} ({interactable.id})"
                    for interactable in view.campaign.interactables
                )
            )

        lines.extend(room.quest_hints)
        return "\n".join(lines)

    @staticmethod
    def _render_exit(exit_view: ExitView) -> str:
        if exit_view.required_item_id is None:
            return exit_view.direction
        possession = "未持有" if exit_view.locked else "已持有"
        return (
            f"{exit_view.direction}（需要：{exit_view.required_item_name} "
            f"({exit_view.required_item_id})，{possession}）"
        )

    def _go(self, arguments: list[str]) -> CommandResult:
        if len(arguments) != 1 or not arguments[0].strip():
            return self._error("用法：go <方向>")
        result = self._submit(MoveIntent(arguments[0]))
        if result.status is TurnStatus.REJECTED:
            return self._rejected(result)
        payload = result.events[0].payload
        assert isinstance(payload, MoveEventData)
        lines = [f"你来到 {payload.room_name}。"]
        lines.extend(self._render_quest_outcomes(payload.quest_outcomes))
        lines.append(self._look(result.view))
        return CommandResult("\n".join(lines), turn_result=result)

    def _take(self, arguments: list[str]) -> CommandResult:
        query, quantity, error = _parse_quantity(
            arguments, "take <物品ID或名称> [数量]"
        )
        if error:
            return self._error(error)
        result = self._submit(TakeIntent(query, quantity))
        if result.status is TurnStatus.REJECTED:
            return self._rejected(result)
        payload = result.events[0].payload
        assert isinstance(payload, ItemTransferEventData)
        if payload.quantity > 1:
            lines = [f"你拾取了 {payload.item_name} ×{payload.quantity}。"]
        else:
            lines = [f"你拾取了 {payload.item_name}。"]
        lines.extend(self._render_quest_outcomes(payload.quest_outcomes))
        return CommandResult("\n".join(lines), turn_result=result)

    def _drop(self, arguments: list[str]) -> CommandResult:
        query, quantity, error = _parse_quantity(
            arguments, "drop <物品ID或名称> [数量]"
        )
        if error:
            return self._error(error)
        result = self._submit(DropIntent(query, quantity))
        if result.status is TurnStatus.REJECTED:
            return self._rejected(result)
        payload = result.events[0].payload
        assert isinstance(payload, ItemTransferEventData)
        item_text = (
            f"{payload.item_name} ×{payload.quantity}"
            if payload.quantity > 1
            else payload.item_name
        )
        return CommandResult(f"你放下了 {item_text}。", turn_result=result)

    def _examine(self, arguments: list[str]) -> CommandResult:
        usage = f"用法：{_COMMAND_BY_TOKEN['examine'].syntax}"
        if not arguments:
            return self._command_look([])

        selector = arguments[0].casefold()
        if selector in {"room", "here"}:
            if len(arguments) != 1:
                return self._error(usage)
            return self._command_look([])

        target_kind = None
        query_arguments = arguments
        if selector in {"item", "monster", "character"}:
            target_kind = ExamineTargetKind(selector)
            query_arguments = arguments[1:]
            if not query_arguments or not " ".join(query_arguments).strip():
                labels = {
                    "item": "物品ID或名称",
                    "monster": "怪物ID或名称",
                    "character": "角色ID或名称",
                }
                return self._error(
                    f"用法：examine {selector} <{labels[selector]}>"
                )

        query = " ".join(query_arguments).strip()
        if not query:
            return self._error(usage)
        result = self._submit(ExamineIntent(query, target_kind))
        if result.status is TurnStatus.REJECTED:
            return self._rejected(result)
        return CommandResult(self._render_focus(result.view), turn_result=result)

    @staticmethod
    def _render_focus(view: GameView) -> str:
        focus = view.focus
        if isinstance(focus, ItemFocusView):
            return f"{focus.name} [{focus.id}]\n{focus.description}"
        if isinstance(focus, MonsterFocusView):
            return (
                f"{focus.name} [{focus.id}]\n"
                f"{focus.description}\n"
                f"生命：{focus.hp}/{focus.max_hp}"
            )
        if isinstance(focus, CharacterFocusView):
            return f"{focus.name} [{focus.id}]\n{focus.description}"
        raise AssertionError("accepted examine result did not include focus")

    def _inspect(self, arguments: list[str]) -> CommandResult:
        query = " ".join(arguments).strip()
        if not query:
            return self._error("用法：inspect <物品ID或名称>")
        result = self._submit(ExamineIntent(query, ExamineTargetKind.ITEM))
        if result.status is TurnStatus.REJECTED:
            return self._rejected(result)
        return CommandResult(self._render_focus(result.view), turn_result=result)

    def _use(self, arguments: list[str]) -> CommandResult:
        query, quantity, error = _parse_quantity(
            arguments, "use <物品ID或名称> [数量]"
        )
        if error:
            return self._error(error)
        result = self._submit(UseIntent(query, quantity))
        if result.status is TurnStatus.REJECTED:
            return self._rejected(result)
        payload = result.events[0].payload
        assert isinstance(payload, UseEventData)
        if payload.quantity > 1:
            text = (
                f"你使用了 {payload.quantity} 个 {payload.item_name}，"
                f"恢复了 {payload.healed_amount} 点生命。"
            )
        else:
            text = (
                f"你使用了 {payload.item_name}，"
                f"恢复了 {payload.healed_amount} 点生命。"
            )
        return CommandResult(text, turn_result=result)

    def _equip(self, arguments: list[str]) -> CommandResult:
        query = " ".join(arguments).strip()
        if not query:
            return self._error("用法：equip <物品ID或名称>")
        result = self._submit(EquipIntent(query))
        if result.status is TurnStatus.REJECTED:
            return self._rejected(result)
        payload = result.events[0].payload
        assert isinstance(payload, EquipmentEventData)
        return CommandResult(f"你装备了 {payload.item_name}。", turn_result=result)

    def _unequip(self, arguments: list[str]) -> CommandResult:
        if not arguments:
            slot = EquipmentSlot.HAND
        elif len(arguments) == 1 and arguments[0].casefold() in {"hand", "body"}:
            slot = EquipmentSlot(arguments[0].casefold())
        else:
            return self._error("用法：unequip [hand|body]")
        result = self._submit(UnequipIntent(slot))
        if result.status is TurnStatus.REJECTED:
            return self._rejected(result)
        payload = result.events[0].payload
        assert isinstance(payload, EquipmentEventData)
        return CommandResult(f"你卸下了 {payload.item_name}。", turn_result=result)

    @staticmethod
    def _inventory(view: GameView) -> str:
        if not view.inventory:
            return "背包是空的。"
        lines = ["背包："]
        for item in view.inventory:
            if item.quantity > 1:
                lines.append(f"- {item.name} ({item.id}) ×{item.quantity}")
            else:
                lines.append(f"- {item.name} ({item.id})")
        return "\n".join(lines)

    def _command_inventory(self, arguments: list[str]) -> CommandResult:
        if arguments:
            return self._error("用法：inventory")
        result = self._submit(ViewIntent(ViewKind.INVENTORY))
        return CommandResult(self._inventory(result.view), turn_result=result)

    def _campaign_actions(self, arguments: list[str]) -> CommandResult:
        if arguments:
            return self._error("用法：actions")
        result = self._submit(ViewIntent(ViewKind.CAMPAIGN_ACTIONS))
        actions = result.view.campaign.actions
        if not actions:
            return CommandResult("当前没有可用的场景动作。", turn_result=result)
        interactables = {
            value.id: value for value in result.view.campaign.interactables
        }
        return CommandResult(
            "\n".join(
                f"- {action.label} ({action.id})"
                f" @ {interactables[action.interactable_id].name} "
                f"({action.interactable_id})"
                for action in actions
            ),
            turn_result=result,
        )

    def _act(self, arguments: list[str]) -> CommandResult:
        if len(arguments) != 1 or not arguments[0].strip():
            return self._error("用法：act <动作ID>")
        result = self._submit(CampaignActionIntent(arguments[0]))
        if result.status is TurnStatus.REJECTED:
            return self._rejected(result)
        payload = result.events[0].payload
        assert isinstance(payload, CampaignActionEventData)
        return CommandResult(payload.result_text, turn_result=result)

    def _objectives(self, arguments: list[str]) -> CommandResult:
        if arguments:
            return self._error("用法：objectives")
        result = self._submit(ViewIntent(ViewKind.OBJECTIVES))
        entries = result.view.campaign.objectives
        if not entries:
            return CommandResult("尚无可见目标。", turn_result=result)
        return CommandResult(
            "\n".join(
                f"[{entry.status.value if entry.status is not None else ''}] "
                f"{entry.title}\n  {entry.text}"
                for entry in entries
            ),
            turn_result=result,
        )

    def _knowledge(self, arguments: list[str]) -> CommandResult:
        if arguments:
            return self._error("用法：knowledge")
        result = self._submit(ViewIntent(ViewKind.KNOWLEDGE))
        entries = result.view.campaign.knowledge
        if not entries:
            return CommandResult("尚无已知条目。", turn_result=result)
        return CommandResult(
            "\n".join(
                f"[{entry.status.value if entry.status is not None else ''}] "
                f"{entry.title}\n  {entry.text}"
                for entry in entries
            ),
            turn_result=result,
        )

    def _journal(self, arguments: list[str]) -> CommandResult:
        if arguments:
            return self._error("用法：journal")
        result = self._submit(ViewIntent(ViewKind.JOURNAL))
        entries = result.view.campaign.journal
        if not entries:
            return CommandResult("叙事日志为空。", turn_result=result)
        return CommandResult(
            "\n".join(
                f"[{entry.category.value}] {entry.title}"
                + (f" ({entry.status.value})" if entry.status else "")
                + f"\n  {entry.text}"
                for entry in entries
            ),
            turn_result=result,
        )

    @staticmethod
    def _quests(view: GameView) -> str:
        if not view.quests:
            return "当前没有已接取的任务。"
        lines: list[str] = []
        for quest in view.quests:
            status = "已完成" if quest.completed else "进行中"
            lines.append(f"[{status}] {quest.name}")
            lines.append(
                f"  目标：{CommandProcessor._quest_target_text(quest.target)}"
            )
            reward = f"  奖励：{quest.reward_experience} 经验"
            if quest.completed:
                reward += "（已领取）"
            lines.append(reward)
        return "\n".join(lines)

    def _command_quests(self, arguments: list[str]) -> CommandResult:
        if arguments:
            return self._error("用法：quests")
        result = self._submit(ViewIntent(ViewKind.QUESTS))
        return CommandResult(self._quests(result.view), turn_result=result)

    @staticmethod
    def _quest_target_text(target: QuestTargetView) -> str:
        kind = target.kind
        name = target.name
        if kind is QuestKind.MONSTER_DEFEATED:
            return f"击败 {name}"
        if kind is QuestKind.REACH_ROOM:
            return f"到达 {name}"
        if kind is QuestKind.COLLECT_ITEM:
            required = target.required
            current = target.current
            return f"收集 {name} ×{required}（当前 {current}/{required}）"
        raise AssertionError(f"未知任务目标：{target!r}")

    @staticmethod
    def _status(view: GameView) -> str:
        player = view.player
        attack_bonus = player.attack - player.base_attack
        defense_bonus = player.defense - player.base_defense
        attack_text = (
            f"{player.attack}（{player.base_attack} 基础 + {attack_bonus}）"
            if attack_bonus
            else str(player.attack)
        )
        defense_text = (
            f"{player.defense}（{player.base_defense} 基础 + {defense_bonus}）"
            if defense_bonus
            else str(player.defense)
        )
        flags_text = "、".join(
            f"{flag.id}={'true' if flag.value else 'false'}"
            for flag in view.flags
        ) or "无"
        return (
            f"{player.name} [{player.id}]\n"
            f"等级：{player.level}  经验：{player.experience}/"
            f"{player.experience_to_next_level}\n"
            f"生命：{player.hp}/{player.max_hp}  "
            f"攻击：{attack_text}  防御：{defense_text}\n"
            f"金币：{player.coins}\n"
            f"flags：{flags_text}"
        )

    def _command_status(self, arguments: list[str]) -> CommandResult:
        if arguments:
            return self._error("用法：status")
        result = self._submit(ViewIntent(ViewKind.STATUS))
        return CommandResult(self._status(result.view), turn_result=result)

    def _shop(self, arguments: list[str]) -> CommandResult:
        if arguments:
            return self._error("用法：shop")
        result = self._submit(ViewIntent(ViewKind.SHOP))
        if result.status is TurnStatus.REJECTED:
            return self._rejected(result)
        shop = result.view.shop
        assert shop is not None
        lines = [f"{shop.name} [{shop.id}]", f"金币：{result.view.player.coins}"]
        for listing in shop.catalog:
            lines.append(
                f"- {listing.item_name} ({listing.item_id}) "
                f"买入：{listing.buy_price} 金币，"
                f"卖出：{listing.sell_price} 金币"
            )
        return CommandResult("\n".join(lines), turn_result=result)

    def _buy(self, arguments: list[str]) -> CommandResult:
        query, quantity, error = _parse_quantity(
            arguments, "buy <物品ID或名称> [数量]"
        )
        if error:
            return self._error(error)
        result = self._submit(BuyIntent(query, quantity))
        if result.status is TurnStatus.REJECTED:
            return self._rejected(result)
        payload = result.events[0].payload
        assert isinstance(payload, TradeEventData)
        item_text = (
            f"{payload.item_name} ×{payload.quantity}"
            if payload.quantity > 1
            else payload.item_name
        )
        lines = [
            f"你购买了 {item_text}，花费 {payload.total_price} 金币。"
            f"余额：{payload.coins}。"
        ]
        lines.extend(self._render_quest_outcomes(payload.quest_outcomes))
        return CommandResult("\n".join(lines), turn_result=result)

    def _sell(self, arguments: list[str]) -> CommandResult:
        query, quantity, error = _parse_quantity(
            arguments, "sell <物品ID或名称> [数量]"
        )
        if error:
            return self._error(error)
        result = self._submit(SellIntent(query, quantity))
        if result.status is TurnStatus.REJECTED:
            return self._rejected(result)
        payload = result.events[0].payload
        assert isinstance(payload, TradeEventData)
        item_text = (
            f"{payload.item_name} ×{payload.quantity}"
            if payload.quantity > 1
            else payload.item_name
        )
        return CommandResult(
            f"你出售了 {item_text}，获得 {payload.total_price} 金币。"
            f"余额：{payload.coins}。",
            turn_result=result,
        )

    def _attack(self, arguments: list[str]) -> CommandResult:
        query = " ".join(arguments).strip()
        if not query:
            return self._error("用法：attack <怪物ID或名称>")
        result = self._submit(AttackIntent(query))
        if result.status is TurnStatus.REJECTED:
            return self._rejected(result)
        payload = result.events[0].payload
        assert isinstance(payload, CombatEventData)
        lines = [
            f"你对 {payload.monster_name} 造成 "
            f"{payload.damage_to_monster} 点伤害。"
        ]
        if payload.monster_defeated:
            lines.append(
                f"{payload.monster_name} 被击败，你获得 "
                f"{payload.experience_reward} 点经验。"
            )
            if payload.loot_item is not None:
                loot = payload.loot_item
                item_text = (
                    f"{loot.item_name} ×{loot.quantity}"
                    if loot.quantity > 1
                    else loot.item_name
                )
                lines.append(f"{item_text} 掉落在当前房间。")
        else:
            lines.append(
                f"{payload.monster_name} 反击，造成 "
                f"{payload.damage_to_player} 点伤害。"
            )
        for gain in payload.combat_level_gains:
            lines.append(f"你升到了 {gain.new_level} 级！")
        lines.extend(self._render_quest_outcomes(payload.quest_outcomes))
        if payload.player_defeated:
            lines.append(
                "你倒下了。使用 recover 回到起始房间并恢复，"
                "或使用 load 读取存档。"
            )
        return CommandResult("\n".join(lines), turn_result=result)

    def _talk(self, arguments: list[str]) -> CommandResult:
        query = " ".join(arguments).strip()
        if not query:
            return self._error("用法：talk <角色ID或名称>")
        result = self._submit(TalkIntent(query))
        if result.status is TurnStatus.REJECTED:
            return self._rejected(result)
        payload = result.events[0].payload
        assert isinstance(payload, DialogueEventData)
        return CommandResult(
            self._render_talk(payload, result.view.dialogue),
            turn_result=result,
        )

    def _select_option(self, index: int) -> CommandResult:
        result = self._submit(ChooseDialogueIntent(index))
        if result.status is TurnStatus.REJECTED:
            return self._rejected(result)
        payload = result.events[0].payload
        assert isinstance(payload, DialogueEventData)
        return CommandResult(
            self._render_talk(payload, result.view.dialogue),
            turn_result=result,
        )

    def _bye(self, arguments: list[str]) -> CommandResult:
        if arguments:
            return self._error("用法：bye")
        result = self._submit(EndDialogueIntent())
        if result.status is TurnStatus.REJECTED:
            return self._rejected(result)
        payload = result.events[0].payload
        assert isinstance(payload, DialogueEndEventData)
        return CommandResult(
            f"你与{payload.character_name}的对话结束了。",
            turn_result=result,
        )

    @staticmethod
    def _render_talk(
        outcome: DialogueEventData,
        dialogue: DialogueView | None,
    ) -> str:
        lines: list[str] = []
        for effect in outcome.effect_outcomes:
            if isinstance(effect, GrantedItemEvent):
                item_text = (
                    f"{effect.item_name} ×{effect.quantity}"
                    if effect.quantity > 1
                    else effect.item_name
                )
                lines.append(f"你获得了 {item_text}。")
                lines.extend(
                    CommandProcessor._render_quest_outcomes(
                        effect.quest_outcomes
                    )
                )
            elif isinstance(effect, GrantedExperienceEvent):
                lines.append(f"你获得了 {effect.amount} 点经验。")
                for gain in effect.level_gains:
                    lines.append(f"你升到了 {gain.new_level} 级！")
            elif isinstance(effect, AcceptedQuestEvent):
                lines.append(f"你接取了任务：{effect.quest_name}。")
                lines.extend(
                    CommandProcessor._render_quest_outcomes(
                        effect.quest_outcomes
                    )
                )
            elif isinstance(effect, FlagChangeEvent):
                value = "true" if effect.new_value else "false"
                if effect.changed:
                    lines.append(f"标记 {effect.flag_id} 已设为 {value}。")
                else:
                    lines.append(f"标记 {effect.flag_id} 保持 {value}。")
        if dialogue is not None:
            lines.append(f"[{dialogue.character_name}] {dialogue.text}")
            for option in dialogue.options:
                lines.append(f"  {option.index}. {option.text}")
        elif outcome.node_text is not None:
            lines.append(f"[{outcome.character_name}] {outcome.node_text}")
        if outcome.ended:
            lines.append("对话结束了。")
        return "\n".join(lines)

    @staticmethod
    def _render_quest_outcomes(
        outcomes: tuple[QuestCompletionEvent, ...],
    ) -> list[str]:
        lines: list[str] = []
        for outcome in outcomes:
            lines.append(
                f"任务完成：{outcome.quest_name}！"
                f"获得 {outcome.reward_experience} 经验。"
            )
            for gain in outcome.level_gains:
                lines.append(f"你升到了 {gain.new_level} 级！")
        return lines

    def _save(self, arguments: list[str]) -> CommandResult:
        if len(arguments) > 1:
            return self._error("用法：save [槽位]")
        slot = arguments[0] if arguments else None
        result = self._submit(SaveIntent(slot))
        if result.status is TurnStatus.REJECTED:
            return self._rejected(result, prefix="存档失败：")
        payload = result.events[0].payload
        assert isinstance(payload, PersistenceEventData)
        destination = (
            "default" if payload.slot == "default" else f"{payload.slot}.json"
        )
        return CommandResult(f"存档成功：{destination}", turn_result=result)

    def _load(self, arguments: list[str]) -> CommandResult:
        if len(arguments) > 1:
            return self._error("用法：load [槽位]")
        slot = arguments[0] if arguments else None
        result = self._submit(LoadIntent(slot))
        if result.status is TurnStatus.REJECTED:
            return self._rejected(result, prefix="读档失败：")
        return CommandResult(
            f"读档成功。\n{self._look(result.view)}",
            turn_result=result,
        )

    def _recover(self, arguments: list[str]) -> CommandResult:
        if arguments:
            return self._error("用法：recover")
        result = self._submit(RecoverIntent())
        if result.status is TurnStatus.REJECTED:
            return self._rejected(result)
        payload = result.events[0].payload
        assert isinstance(payload, RecoveryEventData)
        return CommandResult(
            f"你已恢复，在 {payload.room_name} 醒来。"
            f"生命：{payload.hp}/{payload.max_hp}",
            turn_result=result,
        )

    def _help(self, arguments: list[str]) -> CommandResult:
        if len(arguments) > 1:
            return CommandResult("用法：help [command]")
        if not arguments:
            return CommandResult(HELP_TEXT)

        query = arguments[0].casefold()
        if _BARE_SELECTION.fullmatch(query):
            spec = _SELECTION_SPEC
        else:
            spec = _HELP_BY_TOKEN.get(query)
        if spec is None:
            return CommandResult(
                f"没有该指令的帮助：{arguments[0]}。使用 help 查看全部指令。"
            )

        lines = [f"指令：{spec.name}", f"语法：{spec.syntax}"]
        if spec.aliases:
            lines.append(f"别名：{', '.join(spec.aliases)}")
        lines.extend((
            f"参数：{spec.parameters}",
            f"上下文限制：{spec.context}",
            "死亡限制：倒下时可用。" if spec.allowed_when_dead else
            "死亡限制：倒下时不可用；请先 recover 或 load。",
        ))
        return CommandResult("\n".join(lines))

    @staticmethod
    def _quit(arguments: list[str]) -> CommandResult:
        if arguments:
            return CommandResult("用法：quit")
        return CommandResult("游戏结束。", should_quit=True)
