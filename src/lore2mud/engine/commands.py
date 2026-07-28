"""Parse player intent and render deterministic text responses."""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass

from lore2mud.engine.world import World, WorldRuleError

HELP_TEXT = """可用指令：
  look                  查看当前房间
  inspect <物品ID或名称> 查看当前房间或背包中的物品详情
  go <方向>             移动，例如 go north
  take <物品ID或名称>   拾取物品
  use <物品ID或名称>    使用消耗品
  equip <物品ID或名称>  装备物品
  unequip [hand|body]   卸下装备（默认 hand）
  inventory             查看背包
  quests                查看任务
  status                查看角色状态
  attack <怪物ID或名称> 攻击怪物
  talk <角色ID或名称>   与角色对话
  <数字>                选择对话选项（对话中）
  bye                   结束当前对话（对话中）
  save [槽位]           保存游戏（默认 default）
  load [槽位]           读取存档（默认 default）
  help                  查看帮助
  quit                  退出游戏"""

_BARE_SELECTION = re.compile(r'^[1-9][0-9]{0,4}$')


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

        if room.item_ids:
            items = "、".join(
                f"{self.world.items[item_id].name} ({item_id})"
                for item_id in room.item_ids
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

        # Show active quest hints (read-only, no state change).
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
            if required_item_id in self.world.player.inventory.item_ids
            else "未持有"
        )
        return f"{direction}（需要：{item.name} ({required_item_id})，{possession}）"

    def _active_quest_hints(self) -> str:
        """Return a hint line for incomplete quests triggered in this room."""
        room_id = self.world.player.room_id
        hints: list[str] = []
        for qs in self.world.quest_states.values():
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
        room = self.world.move(arguments[0])
        return CommandResult(f"你来到 {room.name}。\n{self._look()}")

    def _take(self, arguments: list[str]) -> CommandResult:
        if not arguments:
            return CommandResult("用法：take <物品ID或名称>")
        item = self.world.take(" ".join(arguments))
        return CommandResult(f"你拾取了 {item.name} ({item.id})。")

    def _inspect(self, arguments: list[str]) -> CommandResult:
        if not arguments:
            return CommandResult("用法：inspect <物品ID或名称>")
        outcome = self.world.inspect_item(" ".join(arguments))
        return CommandResult(
            f"{outcome.item_name} [{outcome.item_id}]\n{outcome.description}"
        )

    def _use(self, arguments: list[str]) -> CommandResult:
        if not arguments:
            return CommandResult("用法：use <物品ID或名称>")
        outcome = self.world.use(" ".join(arguments))
        return CommandResult(
            f"你服下 {outcome.item_name}，恢复了 {outcome.healed_amount} 点生命。"
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
        item_ids = self.world.player.inventory.item_ids
        if not item_ids:
            return "背包是空的。"
        lines = ["背包："]
        lines.extend(
            f"- {self.world.items[item_id].name} ({item_id})"
            for item_id in item_ids
        )
        return "\n".join(lines)

    def _quests(self) -> str:
        if not self.world.quest_states:
            return "当前没有已接取的任务。"
        lines: list[str] = []
        for qs in self.world.quest_states.values():
            qdef = self.world.quest_defs.get(qs.quest_id)
            if qdef is None:
                continue
            status = "已完成" if qs.completed else "进行中"
            lines.append(f"[{status}] {qdef.name}")
            lines.append(f"  目标：击败 {self.world.monsters[qdef.target_monster_id].name}")
            if qs.completed:
                lines.append(f"  奖励：{qdef.reward_experience} 经验（已领取）")
            else:
                lines.append(f"  奖励：{qdef.reward_experience} 经验")
        return "\n".join(lines)

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
        else:
            lines.append(
                f"{combat.monster_name} 反击，造成 "
                f"{combat.damage_to_player} 点伤害。"
            )
        if outcome.quest_outcome is not None:
            qo = outcome.quest_outcome
            lines.append(
                f"任务完成：{qo.quest_name}！获得 {qo.reward_experience} 经验。"
            )
        for gain in outcome.level_gains:
            lines.append(f"你升到了 {gain.new_level} 级！")
        if combat.player_defeated:
            lines.append("你倒下了。")
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
    def _render_talk(outcome: "TalkOutcome") -> str:
        lines: list[str] = []
        if outcome.granted_item is not None:
            lines.append(
                f"你获得了 {outcome.granted_item.item_name} "
                f"({outcome.granted_item.item_id})。"
            )
        if outcome.node_text is not None:
            lines.append(f"[{outcome.character_name}] {outcome.node_text}")
        if outcome.options:
            for i, opt in enumerate(outcome.options, 1):
                lines.append(f"  {i}. {opt.text}")
        if outcome.ended:
            lines.append("对话结束了。")
        return "\n".join(lines)

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
