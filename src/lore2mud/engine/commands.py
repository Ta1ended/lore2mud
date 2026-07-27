"""Parse player intent and render deterministic text responses."""

from __future__ import annotations

import shlex
from dataclasses import dataclass

from lore2mud.engine.world import World, WorldRuleError


HELP_TEXT = """可用指令：
  look                  查看当前房间
  go <方向>             移动，例如 go north
  take <物品ID或名称>   拾取物品
  inventory             查看背包
  status                查看角色状态
  attack <怪物ID或名称> 攻击怪物
  save                  保存游戏
  load                  读取存档
  help                  查看帮助
  quit                  退出游戏"""


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
            if command == "look":
                return CommandResult(self._look())
            if command == "go":
                return self._go(arguments)
            if command == "take":
                return self._take(arguments)
            if command in {"inventory", "inv", "i"}:
                return CommandResult(self._inventory())
            if command == "status":
                return CommandResult(self._status())
            if command == "attack":
                return self._attack(arguments)
            if command == "save":
                return self._save()
            if command == "load":
                return self._load()
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
        exits = "、".join(sorted(room.exits)) if room.exits else "无"
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
        return "\n".join(lines)

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

    def _status(self) -> str:
        player = self.world.player
        return (
            f"{player.name} [{player.id}]\n"
            f"等级：{player.level}  经验：{player.experience}/"
            f"{player.level * 10}\n"
            f"生命：{player.hp}/{player.max_hp}  "
            f"攻击：{player.attack}  防御：{player.defense}"
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
        for gain in outcome.level_gains:
            lines.append(f"你升到了 {gain.new_level} 级！")
        if combat.player_defeated:
            lines.append("你倒下了。")
        return CommandResult("\n".join(lines))

    def _save(self) -> CommandResult:
        if self._save_service is None:
            return CommandResult("存档服务不可用。")
        try:
            from lore2mud.engine.save import SaveLoadError
            msg = self._save_service.save(self.world)
            return CommandResult(msg)
        except SaveLoadError as exc:
            return CommandResult(f"存档失败：{exc}")

    def _load(self) -> CommandResult:
        if self._save_service is None:
            return CommandResult("存档服务不可用。")
        try:
            from lore2mud.engine.save import SaveLoadError
            new_world = self._save_service.load()
            self.world = new_world
            return CommandResult(
                f"读档成功。\n{self._look()}"
            )
        except SaveLoadError as exc:
            return CommandResult(f"读档失败：{exc}")
