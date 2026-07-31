"""Parse player intent and render deterministic text responses."""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from typing import Protocol

from lore2mud.content.models import (
    CollectItemQuestDefinition,
    MonsterDefeatedQuestDefinition,
    ReachRoomQuestDefinition,
)
from lore2mud.engine.world import (
    AcceptQuestEffectOutcome,
    ExamineCharacterOutcome,
    ExamineItemOutcome,
    ExamineMonsterOutcome,
    GrantExperienceEffectOutcome,
    GrantItemEffectOutcome,
    QuestOutcome,
    SetFlagEffectOutcome,
    World,
    WorldRuleError,
)


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
        world: World,
        save_service: _SaveService | None = None,
    ) -> None:
        self.world = world
        self._save_service = save_service

    def execute(self, raw_command: str) -> CommandResult:
        try:
            parts = shlex.split(raw_command.strip())
        except ValueError as exc:
            return CommandResult(f"无法解析指令：{exc}")
        if not parts:
            return CommandResult("请输入指令；使用 help 查看帮助。")

        command = parts[0].casefold()
        arguments = parts[1:]
        try:
            # Preserve DEC-0020 ordering: death gates before dialogue routing
            # and before unknown-command feedback. The allowlist is derived
            # from the same registry that owns routes and help.
            if not self.world.player.is_alive:
                if command not in _DEAD_ALLOWED:
                    from lore2mud.engine.world import _DEAD_ERROR
                    return CommandResult(_DEAD_ERROR)

            if len(parts) == 1 and _BARE_SELECTION.fullmatch(parts[0]):
                if self.world.active_dialogue is not None:
                    return self._select_option(int(parts[0]))
                return CommandResult(
                    f"未知指令：{parts[0]}。使用 help 查看帮助。"
                )

            if command == "bye" and self.world.active_dialogue is None:
                return CommandResult(
                    f"未知指令：{parts[0]}。使用 help 查看帮助。"
                )

            spec = _COMMAND_BY_TOKEN.get(command)
            if spec is None or spec.handler_name is None:
                return CommandResult(f"未知指令：{parts[0]}。使用 help 查看帮助。")
            handler = getattr(self, spec.handler_name)
            return handler(arguments)
        except WorldRuleError as exc:
            return CommandResult(str(exc))

    def _command_look(self, arguments: list[str]) -> CommandResult:
        if arguments:
            return CommandResult("用法：look")
        return CommandResult(self._look())

    def _look(self) -> str:
        room = self.world.current_room
        lines = [f"{room.name} [{room.id}]", room.description]
        exits = "、".join(
            self._render_exit(direction)
            for direction in sorted(room.exits)
        ) if room.exits else "无"
        lines.append(f"出口：{exits}")

        if room.item_stacks:
            items = "、".join(
                f"{self.world.items[s.item_id].name} ×{s.quantity}"
                if s.quantity > 1
                else f"{self.world.items[s.item_id].name}"
                for s in room.item_stacks
            )
            lines.append(f"物品：{items}")
        if room.monster_ids:
            monsters = "、".join(
                f"{self.world.monsters[monster_id].name} ({monster_id})"
                for monster_id in room.monster_ids
            )
            lines.append(f"怪物：{monsters}")

        room_characters = [
            c for c in self.world.characters.values()
            if c.room_id == self.world.player.room_id
        ]
        if room_characters:
            chars = "、".join(
                f"{c.name} ({c.id})" for c in room_characters
            )
            lines.append(f"角色：{chars}")

        shop = self.world._shop_in_current_room()
        if shop is not None:
            lines.append(f"商店：{shop.name} ({shop.id})")

        hints = self._active_quest_hints()
        if hints:
            lines.append(hints)

        return "\n".join(lines)

    def _render_exit(self, direction: str) -> str:
        """Render one exit's read-only gate status for ``look``."""
        exit_def = self.world.current_room.exits[direction]
        required_item_id = exit_def.required_item_id
        if required_item_id is None:
            return direction

        item = self.world.items[required_item_id]
        possession = (
            "已持有"
            if self.world.player.inventory.has_item(required_item_id)
            else "未持有"
        )
        return f"{direction}（需要：{item.name} ({required_item_id})，{possession}）"

    def _active_quest_hints(self) -> str:
        """Return a hint line for incomplete quests triggered in this room."""
        room_id = self.world.player.room_id
        hints: list[str] = []
        for quest_id in sorted(self.world.quest_states):
            qs = self.world.quest_states[quest_id]
            if qs.completed:
                continue
            qdef = self.world.quest_defs.get(qs.quest_id)
            if qdef is None:
                continue
            if qdef.trigger_room_id == room_id:
                hints.append(
                    f"任务提示：{qdef.name} — {qdef.description}"
                )
        return "\n".join(hints)

    def _go(self, arguments: list[str]) -> CommandResult:
        if len(arguments) != 1 or not arguments[0].strip():
            return CommandResult("用法：go <方向>")
        outcome = self.world.move_with_outcome(arguments[0])
        lines = [f"你来到 {outcome.room.name}。"]
        lines.extend(self._render_quest_outcomes(outcome.quest_outcomes))
        lines.append(self._look())
        return CommandResult("\n".join(lines))

    def _take(self, arguments: list[str]) -> CommandResult:
        query, quantity, error = _parse_quantity(
            arguments, "take <物品ID或名称> [数量]"
        )
        if error:
            return CommandResult(error)
        outcome = self.world.take(query, quantity)
        if outcome.quantity > 1:
            lines = [f"你拾取了 {outcome.item_name} ×{outcome.quantity}。"]
        else:
            lines = [f"你拾取了 {outcome.item_name}。"]
        lines.extend(self._render_quest_outcomes(outcome.quest_outcomes))
        return CommandResult("\n".join(lines))

    def _drop(self, arguments: list[str]) -> CommandResult:
        query, quantity, error = _parse_quantity(
            arguments, "drop <物品ID或名称> [数量]"
        )
        if error:
            return CommandResult(error)
        outcome = self.world.drop(query, quantity)
        if outcome.quantity > 1:
            return CommandResult(
                f"你放下了 {outcome.item_name} ×{outcome.quantity}。"
            )
        return CommandResult(f"你放下了 {outcome.item_name}。")

    def _examine(self, arguments: list[str]) -> CommandResult:
        usage = f"用法：{_COMMAND_BY_TOKEN['examine'].syntax}"
        if not arguments:
            return CommandResult(self._look())

        selector = arguments[0].casefold()
        if selector in {"room", "here"}:
            if len(arguments) != 1:
                return CommandResult(usage)
            return CommandResult(self._look())

        target_type = None
        query_arguments = arguments
        if selector in {"item", "monster", "character"}:
            target_type = selector
            query_arguments = arguments[1:]
            if not query_arguments or not " ".join(query_arguments).strip():
                labels = {
                    "item": "物品ID或名称",
                    "monster": "怪物ID或名称",
                    "character": "角色ID或名称",
                }
                return CommandResult(
                    f"用法：examine {selector} <{labels[selector]}>"
                )

        query = " ".join(query_arguments).strip()
        if not query:
            return CommandResult(usage)
        outcome = self.world.examine(query, target_type)  # type: ignore[arg-type]
        return CommandResult(self._render_examine(outcome))

    @staticmethod
    def _render_examine(outcome: object) -> str:
        if isinstance(outcome, ExamineItemOutcome):
            return (
                f"{outcome.item_name} [{outcome.item_id}]\n"
                f"{outcome.description}"
            )
        if isinstance(outcome, ExamineMonsterOutcome):
            return (
                f"{outcome.monster_name} [{outcome.monster_id}]\n"
                f"{outcome.description}\n"
                f"生命：{outcome.hp}/{outcome.max_hp}"
            )
        if isinstance(outcome, ExamineCharacterOutcome):
            return (
                f"{outcome.character_name} [{outcome.character_id}]\n"
                f"{outcome.description}"
            )
        raise AssertionError(f"未知 examine 结果：{outcome!r}")

    def _inspect(self, arguments: list[str]) -> CommandResult:
        query = " ".join(arguments).strip()
        if not query:
            return CommandResult("用法：inspect <物品ID或名称>")
        outcome = self.world.inspect_item(query)
        return CommandResult(
            f"{outcome.item_name} [{outcome.item_id}]\n{outcome.description}"
        )

    def _use(self, arguments: list[str]) -> CommandResult:
        query, quantity, error = _parse_quantity(
            arguments, "use <物品ID或名称> [数量]"
        )
        if error:
            return CommandResult(error)
        outcome = self.world.use(query, quantity)
        if outcome.quantity > 1:
            return CommandResult(
                f"你使用了 {outcome.quantity} 个 {outcome.item_name}，"
                f"恢复了 {outcome.healed_amount} 点生命。"
            )
        return CommandResult(
            f"你使用了 {outcome.item_name}，恢复了 {outcome.healed_amount} 点生命。"
        )

    def _equip(self, arguments: list[str]) -> CommandResult:
        query = " ".join(arguments).strip()
        if not query:
            return CommandResult("用法：equip <物品ID或名称>")
        outcome = self.world.equip(query)
        return CommandResult(f"你装备了 {outcome.item_name}。")

    def _unequip(self, arguments: list[str]) -> CommandResult:
        if not arguments:
            slot = "hand"
        elif len(arguments) == 1:
            slot = arguments[0].casefold()
            if slot not in ("hand", "body"):
                return CommandResult("用法：unequip [hand|body]")
        else:
            return CommandResult("用法：unequip [hand|body]")
        outcome = self.world.unequip(slot)
        return CommandResult(f"你卸下了 {outcome.item_name}。")

    def _inventory(self) -> str:
        stacks = self.world.player.inventory.stacks
        if not stacks:
            return "背包是空的。"
        lines = ["背包："]
        for s in stacks:
            item = self.world.items[s.item_id]
            if s.quantity > 1:
                lines.append(f"- {item.name} ({s.item_id}) ×{s.quantity}")
            else:
                lines.append(f"- {item.name} ({s.item_id})")
        return "\n".join(lines)

    def _command_inventory(self, arguments: list[str]) -> CommandResult:
        if arguments:
            return CommandResult("用法：inventory")
        return CommandResult(self._inventory())

    def _quests(self) -> str:
        if not self.world.quest_states:
            return "当前没有已接取的任务。"
        lines: list[str] = []
        for quest_id in sorted(self.world.quest_states):
            qs = self.world.quest_states[quest_id]
            qdef = self.world.quest_defs.get(qs.quest_id)
            if qdef is None:
                continue
            status = "已完成" if qs.completed else "进行中"
            lines.append(f"[{status}] {qdef.name}")
            lines.append(f"  目标：{self._quest_target_text(qdef)}")
            if qs.completed:
                lines.append(f"  奖励：{qdef.reward_experience} 经验（已领取）")
            else:
                lines.append(f"  奖励：{qdef.reward_experience} 经验")
        return "\n".join(lines)

    def _command_quests(self, arguments: list[str]) -> CommandResult:
        if arguments:
            return CommandResult("用法：quests")
        return CommandResult(self._quests())

    def _quest_target_text(self, qdef: object) -> str:
        if isinstance(qdef, MonsterDefeatedQuestDefinition):
            return f"击败 {self.world.monsters[qdef.target_monster_id].name}"
        if isinstance(qdef, ReachRoomQuestDefinition):
            return f"到达 {self.world.rooms[qdef.target_room_id].name}"
        if isinstance(qdef, CollectItemQuestDefinition):
            item = self.world.items[qdef.target_item_id]
            stack = self.world.player.inventory.find_stack(qdef.target_item_id)
            current = stack.quantity if stack is not None else 0
            return (
                f"收集 {item.name} ×{qdef.required_quantity}"
                f"（当前 {current}/{qdef.required_quantity}）"
            )
        raise AssertionError(f"未知任务定义：{qdef!r}")

    def _status(self) -> str:
        player = self.world.player
        ea = self.world.effective_attack
        ed = self.world.effective_defense
        atk_bonus = ea - player.attack
        def_bonus = ed - player.defense
        attack_str = (
            f"{ea}（{player.attack} 基础 + {atk_bonus}）" if atk_bonus else str(ea)
        )
        defense_str = (
            f"{ed}（{player.defense} 基础 + {def_bonus}）" if def_bonus else str(ed)
        )
        flags_text = "、".join(
            f"{flag_id}={'true' if value else 'false'}"
            for flag_id, value in sorted(self.world.flags.items())
        ) or "无"
        return (
            f"{player.name} [{player.id}]\n"
            f"等级：{player.level}  经验：{player.experience}/"
            f"{player.level * 10}\n"
            f"生命：{player.hp}/{player.max_hp}  "
            f"攻击：{attack_str}  防御：{defense_str}\n"
            f"金币：{player.coins}\n"
            f"flags：{flags_text}"
        )

    def _command_status(self, arguments: list[str]) -> CommandResult:
        if arguments:
            return CommandResult("用法：status")
        return CommandResult(self._status())

    def _shop(self, arguments: list[str]) -> CommandResult:
        if arguments:
            return CommandResult("用法：shop")
        outcome = self.world.shop()
        lines = [
            f"{outcome.shop_name} [{outcome.shop_id}]",
            f"金币：{outcome.coins}",
        ]
        for listing in outcome.catalog:
            item = self.world.items[listing.item_id]
            lines.append(
                f"- {item.name} ({item.id}) 买入：{listing.buy_price} "
                f"金币，卖出：{listing.sell_price} 金币"
            )
        return CommandResult("\n".join(lines))

    def _buy(self, arguments: list[str]) -> CommandResult:
        query, quantity, error = _parse_quantity(
            arguments, "buy <物品ID或名称> [数量]"
        )
        if error:
            return CommandResult(error)
        outcome = self.world.buy(query, quantity)
        item_text = (
            f"{outcome.item_name} ×{outcome.quantity}"
            if outcome.quantity > 1
            else outcome.item_name
        )
        lines = [
            f"你购买了 {item_text}，花费 {outcome.total_price} 金币。"
            f"余额：{outcome.coins}。"
        ]
        lines.extend(self._render_quest_outcomes(outcome.quest_outcomes))
        return CommandResult("\n".join(lines))

    def _sell(self, arguments: list[str]) -> CommandResult:
        query, quantity, error = _parse_quantity(
            arguments, "sell <物品ID或名称> [数量]"
        )
        if error:
            return CommandResult(error)
        outcome = self.world.sell(query, quantity)
        item_text = (
            f"{outcome.item_name} ×{outcome.quantity}"
            if outcome.quantity > 1
            else outcome.item_name
        )
        return CommandResult(
            f"你出售了 {item_text}，获得 {outcome.total_price} 金币。"
            f"余额：{outcome.coins}。"
        )

    def _attack(self, arguments: list[str]) -> CommandResult:
        query = " ".join(arguments).strip()
        if not query:
            return CommandResult("用法：attack <怪物ID或名称>")
        outcome = self.world.attack(query)
        combat = outcome.combat
        lines = [
            f"你对 {combat.monster_name} 造成 {combat.damage_to_monster} 点伤害。"
        ]
        if combat.monster_defeated:
            lines.append(
                f"{combat.monster_name} 被击败，你获得 "
                f"{combat.experience_reward} 点经验。"
            )
            if outcome.loot_item is not None:
                li = outcome.loot_item
                if li.quantity > 1:
                    lines.append(
                        f"{li.item_name} ×{li.quantity} "
                        f"掉落在当前房间。"
                    )
                else:
                    lines.append(
                        f"{li.item_name} 掉落在当前房间。"
                    )
        else:
            lines.append(
                f"{combat.monster_name} 反击，造成 "
                f"{combat.damage_to_player} 点伤害。"
            )
        for gain in outcome.combat_level_gains:
            lines.append(f"你升到了 {gain.new_level} 级！")
        lines.extend(self._render_quest_outcomes(outcome.quest_outcomes))
        if combat.player_defeated:
            lines.append(
                "你倒下了。使用 recover 回到起始房间并恢复，"
                "或使用 load 读取存档。"
            )
        return CommandResult("\n".join(lines))

    def _talk(self, arguments: list[str]) -> CommandResult:
        query = " ".join(arguments).strip()
        if not query:
            return CommandResult("用法：talk <角色ID或名称>")
        outcome = self.world.start_dialogue(query)
        return CommandResult(self._render_talk(outcome))

    def _select_option(self, index: int) -> CommandResult:
        outcome = self.world.select_option(index)
        return CommandResult(self._render_talk(outcome))

    def _bye(self, arguments: list[str]) -> CommandResult:
        if arguments:
            return CommandResult("用法：bye")
        outcome = self.world.end_dialogue()
        return CommandResult(
            f"你与{outcome.character_name}的对话结束了。"
        )

    @staticmethod
    def _render_talk(outcome: object) -> str:
        lines: list[str] = []
        for effect_outcome in getattr(outcome, "effect_outcomes", ()):
            if isinstance(effect_outcome, GrantItemEffectOutcome):
                if effect_outcome.quantity > 1:
                    lines.append(
                        f"你获得了 {effect_outcome.item_name} "
                        f"×{effect_outcome.quantity}。"
                    )
                else:
                    lines.append(f"你获得了 {effect_outcome.item_name}。")
                lines.extend(
                    CommandProcessor._render_quest_outcomes(
                        effect_outcome.quest_outcomes
                    )
                )
            elif isinstance(effect_outcome, GrantExperienceEffectOutcome):
                lines.append(f"你获得了 {effect_outcome.amount} 点经验。")
                for gain in effect_outcome.level_gains:
                    lines.append(f"你升到了 {gain.new_level} 级！")
            elif isinstance(effect_outcome, AcceptQuestEffectOutcome):
                lines.append(f"你接取了任务：{effect_outcome.quest_name}。")
                lines.extend(
                    CommandProcessor._render_quest_outcomes(
                        effect_outcome.quest_outcomes
                    )
                )
            elif isinstance(effect_outcome, SetFlagEffectOutcome):
                value = "true" if effect_outcome.new_value else "false"
                if effect_outcome.changed:
                    lines.append(
                        f"标记 {effect_outcome.flag_id} 已设为 {value}。"
                    )
                else:
                    lines.append(
                        f"标记 {effect_outcome.flag_id} 保持 {value}。"
                    )
        node_text = getattr(outcome, "node_text", None)
        if node_text is not None:
            char_name = getattr(outcome, "character_name", "")
            lines.append(f"[{char_name}] {node_text}")
        options = getattr(outcome, "options", ())
        if options:
            for i, opt in enumerate(options, 1):
                lines.append(f"  {i}. {opt.text}")
        ended = getattr(outcome, "ended", False)
        if ended:
            lines.append("对话结束了。")
        return "\n".join(lines)

    @staticmethod
    def _render_quest_outcomes(
        outcomes: tuple[QuestOutcome, ...],
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
            return CommandResult("用法：save [槽位]")
        if self._save_service is None:
            return CommandResult("存档服务不可用。")
        from lore2mud.engine.save import SaveLoadError

        try:
            slot = arguments[0] if arguments else None
            msg = self._save_service.save(self.world, slot)
            return CommandResult(msg)
        except SaveLoadError as exc:
            return CommandResult(f"存档失败：{exc}")

    def _load(self, arguments: list[str]) -> CommandResult:
        if len(arguments) > 1:
            return CommandResult("用法：load [槽位]")
        if self._save_service is None:
            return CommandResult("存档服务不可用。")
        from lore2mud.engine.save import SaveLoadError

        try:
            slot = arguments[0] if arguments else None
            new_world = self._save_service.load(slot)
            self.world = new_world
            return CommandResult(
                f"读档成功。\n{self._look()}"
            )
        except SaveLoadError as exc:
            return CommandResult(f"读档失败：{exc}")

    def _recover(self, arguments: list[str]) -> CommandResult:
        if arguments:
            return CommandResult("用法：recover")
        outcome = self.world.recover()
        return CommandResult(
            f"你已恢复，在 {outcome.room_name} 醒来。"
            f"生命：{outcome.hp}/{outcome.max_hp}"
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
