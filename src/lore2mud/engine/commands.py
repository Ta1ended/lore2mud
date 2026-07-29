"""Parse player intent and render deterministic text responses."""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass

from lore2mud.content.models import (
    CollectItemQuestDefinition,
    MonsterDefeatedQuestDefinition,
    ReachRoomQuestDefinition,
)
from lore2mud.engine.world import QuestOutcome, World, WorldRuleError

HELP_TEXT = """可用指令：
  look                        查看当前房间
  inspect <物品ID或名称>       查看当前房间或背包中的物品详情
  go <方向>                   移动，例如 go north
  take <物品ID或名称> [数量]   拾取物品（数量可选，默认 1）
  drop <物品ID或名称> [数量]   放下背包中的未装备物品
  use <物品ID或名称> [数量]    使用消耗品
  equip <物品ID或名称>         装备物品
  unequip [hand|body]          卸下装备（默认 hand）
  inventory                    查看背包
  quests                       查看任务
  status                       查看角色状态
  attack <怪物ID或名称>         攻击怪物
  talk <角色ID或名称>           与角色对话
  <数字>                       选择对话选项（对话中）
  bye                          结束当前对话（对话中）
  save [槽位]                  保存游戏（默认 default）
  load [槽位]                  读取存档（默认 default）
  recover                      恢复倒下的角色
  help                         查看帮助
  quit                         退出游戏"""

_BARE_SELECTION = re.compile(r'^[1-9][0-9]{0,4}$')

_DEAD_ALLOWED = frozenset({
    "look", "inspect", "status", "inventory", "inv", "i",
    "quests", "help", "save", "load", "recover",
    "quit", "exit",
})

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
) -> tuple[str, int, str | None]:
    """Parse tail quantity from arguments.

    Returns (query, quantity, error).
    error non-empty means return it directly.
    """
    if not arguments:
        return ("", 1, "用法：take <物品ID或名称> [数量]")

    last = arguments[-1]
    kind, val = _classify_quantity_token(last)

    if kind == "valid":
        assert val is not None
        rest = arguments[:-1]
        if not rest:
            return ("", val, "用法：take <物品ID或名称> [数量]")
        return (" ".join(rest), val, None)

    if kind == "invalid":
        return (" ".join(arguments), 1, "数量必须为正整数。")

    # kind == "name": no quantity suffix, default to 1
    return (" ".join(arguments), 1, None)


@dataclass(frozen=True, slots=True)
class CommandResult:
    text: str
    should_quit: bool = False


class CommandProcessor:
    def __init__(
        self,
        world: World,
        save_service: object | None = None,
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
            # Death gate: only allow read-only and recovery commands.
            if not self.world.player.is_alive:
                if command not in _DEAD_ALLOWED:
                    from lore2mud.engine.world import _DEAD_ERROR
                    return CommandResult(_DEAD_ERROR)

            # Bare integer selection in active dialogue
            if self.world.active_dialogue is not None and len(parts) == 1:
                if _BARE_SELECTION.fullmatch(parts[0]):
                    return self._select_option(int(parts[0]))
                if command == "bye":
                    return self._bye()

            if command == "look":
                return CommandResult(self._look())
            if command == "inspect":
                return self._inspect(arguments)
            if command == "go":
                return self._go(arguments)
            if command == "take":
                return self._take(arguments)
            if command == "drop":
                return self._drop(arguments)
            if command == "use":
                return self._use(arguments)
            if command == "equip":
                return self._equip(arguments)
            if command == "unequip":
                return self._unequip(arguments)
            if command in {"inventory", "inv", "i"}:
                return CommandResult(self._inventory())
            if command == "quests":
                return CommandResult(self._quests())
            if command == "status":
                return CommandResult(self._status())
            if command == "attack":
                return self._attack(arguments)
            if command == "talk":
                return self._talk(arguments)
            if command == "save":
                return self._save(arguments)
            if command == "load":
                return self._load(arguments)
            if command == "recover":
                return self._recover(arguments)
            if command == "help":
                return CommandResult(HELP_TEXT)
            if command in {"quit", "exit"}:
                return CommandResult("游戏结束。", should_quit=True)
            return CommandResult(f"未知指令：{parts[0]}。使用 help 查看帮助。")
        except WorldRuleError as exc:
            return CommandResult(str(exc))

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
        if len(arguments) != 1:
            return CommandResult("用法：go <方向>")
        outcome = self.world.move_with_outcome(arguments[0])
        lines = [f"你来到 {outcome.room.name}。"]
        lines.extend(self._render_quest_outcomes(outcome.quest_outcomes))
        lines.append(self._look())
        return CommandResult("\n".join(lines))

    def _take(self, arguments: list[str]) -> CommandResult:
        query, quantity, error = _parse_quantity(arguments)
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
        query, quantity, error = _parse_quantity(arguments)
        if error:
            return CommandResult(error)
        outcome = self.world.drop(query, quantity)
        if outcome.quantity > 1:
            return CommandResult(
                f"你放下了 {outcome.item_name} ×{outcome.quantity}。"
            )
        return CommandResult(f"你放下了 {outcome.item_name}。")

    def _inspect(self, arguments: list[str]) -> CommandResult:
        if not arguments:
            return CommandResult("用法：inspect <物品ID或名称>")
        outcome = self.world.inspect_item(" ".join(arguments))
        return CommandResult(
            f"{outcome.item_name} [{outcome.item_id}]\n{outcome.description}"
        )

    def _use(self, arguments: list[str]) -> CommandResult:
        query, quantity, error = _parse_quantity(arguments)
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
        if not arguments:
            return CommandResult("用法：equip <物品ID或名称>")
        outcome = self.world.equip(" ".join(arguments))
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
        return (
            f"{player.name} [{player.id}]\n"
            f"等级：{player.level}  经验：{player.experience}/"
            f"{player.level * 10}\n"
            f"生命：{player.hp}/{player.max_hp}  "
            f"攻击：{attack_str}  防御：{defense_str}"
        )

    def _attack(self, arguments: list[str]) -> CommandResult:
        if not arguments:
            return CommandResult("用法：attack <怪物ID或名称>")
        outcome = self.world.attack(" ".join(arguments))
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
        if not arguments:
            return CommandResult("用法：talk <角色ID或名称>")
        outcome = self.world.start_dialogue(" ".join(arguments))
        return CommandResult(self._render_talk(outcome))

    def _select_option(self, index: int) -> CommandResult:
        outcome = self.world.select_option(index)
        return CommandResult(self._render_talk(outcome))

    def _bye(self) -> CommandResult:
        outcome = self.world.end_dialogue()
        return CommandResult(
            f"你与{outcome.character_name}的对话结束了。"
        )

    @staticmethod
    def _render_talk(outcome: object) -> str:
        lines: list[str] = []
        granted = getattr(outcome, "granted_item", None)
        if granted is not None:
            if granted.quantity > 1:
                lines.append(
                    f"你获得了 {granted.item_name} ×{granted.quantity}。"
                )
            else:
                lines.append(
                    f"你获得了 {granted.item_name}。"
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
        lines.extend(
            CommandProcessor._render_quest_outcomes(
                getattr(outcome, "quest_outcomes", ())
            )
        )
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
        try:
            from lore2mud.engine.save import SaveLoadError
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
        try:
            from lore2mud.engine.save import SaveLoadError
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
