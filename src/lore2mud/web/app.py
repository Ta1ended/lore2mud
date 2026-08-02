"""Structured player actions and snapshots for the local browser UI."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
import shlex
from threading import RLock
from typing import Any, Callable

from lore2mud.content.models import (
    CollectItemQuestDefinition,
    ContentPack,
    MonsterDefeatedQuestDefinition,
    ReachRoomQuestDefinition,
)
from lore2mud.engine.commands import CommandProcessor
from lore2mud.engine.save import SaveLoadError, SaveLoadService
from lore2mud.engine.world import World, WorldRuleError


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
    """Own one authoritative World and expose a structured player boundary."""

    def __init__(
        self,
        pack: ContentPack,
        save_service: SaveLoadService,
        *,
        player_name: str = "旅人",
    ) -> None:
        self._pack = pack
        self._save_service = save_service
        self._world = World.from_content_pack(pack, player_name=player_name)
        self._commands = CommandProcessor(
            self._world, save_service=self._save_service
        )
        self._lock = RLock()

    @property
    def world(self) -> World:
        """Return the current authoritative World for integration tests."""
        return self._world

    def dispatch(self, raw_action: object) -> dict[str, Any]:
        """Validate and execute one player intent, always returning a snapshot."""
        with self._lock:
            try:
                action_type, action = self._validate_action(raw_action)
                event = self._execute(action_type, action)
                return {
                    "ok": True,
                    "event": event,
                    "snapshot": self._snapshot(),
                }
            except (PlayerActionError, WorldRuleError, SaveLoadError) as exc:
                return {
                    "ok": False,
                    "event": {"type": "error", "message": str(exc), "data": {}},
                    "snapshot": self._snapshot(),
                }

    def snapshot(self) -> dict[str, Any]:
        """Return a read-only JSON-ready view of the authoritative World."""
        with self._lock:
            return self._snapshot()

    @staticmethod
    def _validate_action(raw_action: object) -> tuple[str, dict[str, Any]]:
        if not isinstance(raw_action, dict):
            raise PlayerActionError("action 必须是 JSON 对象。")
        action = dict(raw_action)
        action_type = action.get("type")
        if not isinstance(action_type, str) or not action_type:
            raise PlayerActionError("action.type 必须是非空字符串。")
        fields = _ACTION_FIELDS.get(action_type)
        if fields is None:
            raise PlayerActionError(f"未知 action 类型：{action_type}。")
        required, optional = fields
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
    def _text(action: dict[str, Any], field: str, *, maximum: int = 200) -> str:
        value = action.get(field)
        if not isinstance(value, str) or not value.strip():
            raise PlayerActionError(f"action.{field} 必须是非空字符串。")
        value = value.strip()
        if len(value) > maximum:
            raise PlayerActionError(f"action.{field} 过长。")
        return value

    @staticmethod
    def _quantity(action: dict[str, Any], field: str = "quantity") -> int:
        value = action.get(field, 1)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise PlayerActionError(f"action.{field} 必须是正整数。")
        return value

    @staticmethod
    def _slot(action: dict[str, Any]) -> str | None:
        if "slot" not in action:
            return None
        value = action["slot"]
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise PlayerActionError("action.slot 必须是非空字符串或 null。")
        return value.strip()

    def _execute(self, action_type: str, action: dict[str, Any]) -> dict[str, Any]:
        operations: dict[str, Callable[[], object]] = {
            "move": lambda: self._world.move_with_outcome(
                self._text(action, "direction", maximum=32)
            ),
            "take": lambda: self._world.take(
                self._text(action, "target"), self._quantity(action)
            ),
            "drop": lambda: self._world.drop(
                self._text(action, "target"), self._quantity(action)
            ),
            "use": lambda: self._world.use(
                self._text(action, "target"), self._quantity(action)
            ),
            "equip": lambda: self._world.equip(self._text(action, "target")),
            "unequip": lambda: self._world.unequip(
                self._text(action, "slot", maximum=16)
            ),
            "attack": lambda: self._world.attack(self._text(action, "target")),
            "talk": lambda: self._world.start_dialogue(
                self._text(action, "target")
            ),
            "choose_dialogue": lambda: self._world.select_option(
                self._quantity(action, "index")
            ),
            "end_dialogue": self._world.end_dialogue,
            "buy": lambda: self._world.buy(
                self._text(action, "target"), self._quantity(action)
            ),
            "sell": lambda: self._world.sell(
                self._text(action, "target"), self._quantity(action)
            ),
            "recover": self._world.recover,
            "campaign_action": lambda: self._world.execute_campaign_action(
                self._text(action, "action_id")
            ),
        }

        if action_type == "save":
            slot = self._slot(action)
            self._save_service.save(self._world, slot)
            return self._event(
                "save", {"slot": slot or "default"}, f"已保存到 {slot or 'default'}。"
            )
        if action_type == "load":
            slot = self._slot(action)
            self._replace_world(self._save_service.load(slot))
            return self._event(
                "load", {"slot": slot or "default"}, f"已读取 {slot or 'default'}。"
            )
        if action_type == "command":
            command = self._text(action, "command", maximum=500)
            self._validate_fallback_command(command)
            result = self._commands.execute(command)
            return self._event(
                "command",
                {"command": command, "should_quit": result.should_quit},
                result.text,
            )

        outcome = operations[action_type]()
        return self._event(
            action_type,
            self._json_value(outcome),
            self._message(action_type, outcome),
        )

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

    def _replace_world(self, world: World) -> None:
        self._world = world
        self._commands = CommandProcessor(
            self._world, save_service=self._save_service
        )

    @staticmethod
    def _json_value(value: object) -> Any:
        if is_dataclass(value) and not isinstance(value, type):
            return asdict(value)
        return value

    @staticmethod
    def _event(action_type: str, data: Any, message: str) -> dict[str, Any]:
        return {"type": action_type, "message": message, "data": data}

    @staticmethod
    def _message(action_type: str, outcome: object) -> str:
        labels = {
            "move": lambda: f"来到 {outcome.room.name}。",  # type: ignore[attr-defined]
            "take": lambda: f"拾取 {outcome.item_name}。",  # type: ignore[attr-defined]
            "drop": lambda: f"放下 {outcome.item_name}。",  # type: ignore[attr-defined]
            "use": lambda: f"使用 {outcome.item_name}。",  # type: ignore[attr-defined]
            "equip": lambda: f"装备 {outcome.item_name}。",  # type: ignore[attr-defined]
            "unequip": lambda: f"卸下 {outcome.item_name}。",  # type: ignore[attr-defined]
            "attack": lambda: (
                f"攻击 {outcome.combat.monster_name}，造成 "  # type: ignore[attr-defined]
                f"{outcome.combat.damage_to_monster} 点伤害。"  # type: ignore[attr-defined]
            ),
            "talk": lambda: f"与 {outcome.character_name} 对话。",  # type: ignore[attr-defined]
            "choose_dialogue": lambda: "选择了对话回应。",
            "end_dialogue": lambda: "结束对话。",
            "buy": lambda: f"购买 {outcome.item_name}。",  # type: ignore[attr-defined]
            "sell": lambda: f"出售 {outcome.item_name}。",  # type: ignore[attr-defined]
            "recover": lambda: f"在 {outcome.room_name} 恢复。",  # type: ignore[attr-defined]
            "campaign_action": lambda: outcome.result_text,  # type: ignore[attr-defined]
        }
        return labels[action_type]()

    def _snapshot(self) -> dict[str, Any]:
        world = self._world
        player = world.player
        room = world.current_room
        inventory = [self._item_snapshot(stack) for stack in player.inventory.stacks]
        room_items = [self._item_snapshot(stack) for stack in room.item_stacks]
        held_ids = player.inventory.all_item_ids

        exits = []
        for direction, exit_def in sorted(world.available_exits().items()):
            requirement = exit_def.required_item_id
            exits.append(
                {
                    "direction": direction,
                    "target_room_id": exit_def.target_room_id,
                    "target_room_name": world.rooms[exit_def.target_room_id].name,
                    "required_item_id": requirement,
                    "required_item_name": (
                        world.items[requirement].name if requirement else None
                    ),
                    "locked": requirement is not None and requirement not in held_ids,
                }
            )

        monsters = [
            {
                "id": monster.id,
                "name": monster.name,
                "description": monster.description,
                "hp": monster.hp,
                "max_hp": monster.max_hp,
                "attack": monster.attack,
                "defense": monster.defense,
            }
            for monster_id in room.monster_ids
            for monster in (world.monsters[monster_id],)
        ]
        characters = [
            {
                "id": character.id,
                "name": character.name,
                "description": world.character_description(character.id),
            }
            for character in world.available_characters()
        ]

        return {
            "pack": {
                "id": world.pack_id,
                "name": world.pack_name,
                "version": world.pack_version,
            },
            "player": {
                "id": player.id,
                "name": player.name,
                "alive": player.is_alive,
                "hp": player.hp,
                "max_hp": player.max_hp,
                "level": player.level,
                "experience": player.experience,
                "experience_to_next_level": player.level * 10,
                "attack": world.effective_attack,
                "base_attack": player.attack,
                "defense": world.effective_defense,
                "base_defense": player.defense,
                "coins": player.coins,
                "inventory_capacity": player.inventory.capacity,
                "inventory_stack_count": player.inventory.stack_count,
            },
            "room": {
                "id": room.id,
                "name": room.name,
                "description": world.location_description(),
                "exits": exits,
                "items": room_items,
                "monsters": monsters,
                "characters": characters,
            },
            "inventory": inventory,
            "equipment": {
                "hand": self._equipped_item(world.equipped.hand),
                "body": self._equipped_item(world.equipped.body),
            },
            "quests": self._quest_snapshots(),
            "campaign": self._campaign_snapshot(),
            "dialogue": self._dialogue_snapshot(),
            "shop": self._shop_snapshot(),
            "flags": [
                {"id": flag_id, "value": value}
                for flag_id, value in sorted(world.flags.items())
            ],
        }

    def _item_snapshot(self, stack: object) -> dict[str, Any]:
        item_id = stack.item_id  # type: ignore[attr-defined]
        item = self._world.items[item_id]
        return {
            "id": item.id,
            "name": item.name,
            "description": item.description,
            "quantity": stack.quantity,  # type: ignore[attr-defined]
            "heal_amount": item.heal_amount,
            "slot": item.slot,
            "attack_bonus": item.attack_bonus,
            "defense_bonus": item.defense_bonus,
            "equipped": item_id in {
                self._world.equipped.hand,
                self._world.equipped.body,
            },
        }

    def _equipped_item(self, item_id: str | None) -> dict[str, Any] | None:
        if item_id is None:
            return None
        item = self._world.items[item_id]
        return {
            "id": item.id,
            "name": item.name,
            "attack_bonus": item.attack_bonus,
            "defense_bonus": item.defense_bonus,
        }

    def _quest_snapshots(self) -> list[dict[str, Any]]:
        world = self._world
        quests = []
        for quest_id in sorted(world.quest_states):
            state = world.quest_states[quest_id]
            quest = world.quest_defs[quest_id]
            target: dict[str, Any]
            if isinstance(quest, MonsterDefeatedQuestDefinition):
                monster = world.monsters[quest.target_monster_id]
                target = {
                    "kind": quest.kind,
                    "id": monster.id,
                    "name": monster.name,
                    "current": 1 if not monster.is_alive else 0,
                    "required": 1,
                }
            elif isinstance(quest, ReachRoomQuestDefinition):
                target_room = world.rooms[quest.target_room_id]
                target = {
                    "kind": quest.kind,
                    "id": target_room.id,
                    "name": target_room.name,
                    "current": 1 if player_room(world) == target_room.id else 0,
                    "required": 1,
                }
            elif isinstance(quest, CollectItemQuestDefinition):
                item = world.items[quest.target_item_id]
                stack = world.player.inventory.find_stack(item.id)
                target = {
                    "kind": quest.kind,
                    "id": item.id,
                    "name": item.name,
                    "current": stack.quantity if stack else 0,
                    "required": quest.required_quantity,
                }
            else:
                raise AssertionError(f"未知任务定义：{quest!r}")
            quests.append(
                {
                    "id": quest.id,
                    "name": quest.name,
                    "description": quest.description,
                    "completed": state.completed,
                    "reward_experience": quest.reward_experience,
                    "target": target,
                }
            )
        return quests

    def _campaign_snapshot(self) -> dict[str, Any]:
        world = self._world
        scenes = []
        for scene in world.available_scenes():
            state = world.scene_states[scene.id]
            assert state.stage_index is not None
            scenes.append(
                {
                    "id": scene.id,
                    "name": scene.name,
                    "status": state.status,
                    "stage_id": scene.stages[state.stage_index].id,
                    "description": world.scene_description(scene.id),
                }
            )
        interactables = []
        action_rows: list[dict[str, Any]] = []
        actions_by_interactable: dict[str, list[Any]] = {}
        for projected in world.available_campaign_actions():
            actions_by_interactable.setdefault(projected.interactable_id, []).append(
                projected.action
            )
        for interactable in world.available_interactables():
            actions = actions_by_interactable.get(interactable.id, [])
            action_snapshots = [
                {"id": action.id, "label": action.label}
                for action in actions
            ]
            interactables.append(
                {
                    "id": interactable.id,
                    "name": interactable.name,
                    "kind": interactable.kind,
                    "description": world.interactable_description(interactable.id),
                    "actions": action_snapshots,
                }
            )
            action_rows.extend(
                {
                    "id": action["id"],
                    "label": action["label"],
                    "interactable_id": interactable.id,
                }
                for action in action_snapshots
            )
        journal = [asdict(entry) for entry in world.available_log_entries()]
        return {
            "scenes": scenes,
            "interactables": interactables,
            "actions": action_rows,
            "objectives": [
                entry for entry in journal if entry["category"] == "objective"
            ],
            "knowledge": [
                entry for entry in journal if entry["category"] == "knowledge"
            ],
            "journal": journal,
        }

    def _dialogue_snapshot(self) -> dict[str, Any] | None:
        active = self._world.active_dialogue
        if active is None:
            return None
        dialogue = self._world.dialogue_defs[active.dialogue_id]
        character = self._world.characters[dialogue.character_id]
        node = dialogue.nodes[active.current_node_id]
        options = self._world.available_dialogue_options(dialogue.id, node.id)
        return {
            "dialogue_id": dialogue.id,
            "character_id": character.id,
            "character_name": character.name,
            "node_id": node.id,
            "text": self._world.dialogue_node_text(dialogue.id, node.id),
            "options": [
                {"index": index, "id": option.id, "text": option.text}
                for index, option in enumerate(options, 1)
            ],
        }

    def _shop_snapshot(self) -> dict[str, Any] | None:
        world = self._world
        shop = next(
            (
                value
                for value in sorted(world.shop_defs.values(), key=lambda value: value.id)
                if value.room_id == world.player.room_id
            ),
            None,
        )
        if shop is None:
            return None
        return {
            "id": shop.id,
            "name": shop.name,
            "catalog": [
                {
                    "item_id": listing.item_id,
                    "item_name": world.items[listing.item_id].name,
                    "buy_price": listing.buy_price,
                    "sell_price": listing.sell_price,
                }
                for listing in shop.catalog
            ],
        }


def player_room(world: World) -> str:
    """Keep quest progress construction explicit and easy to unit test."""
    return world.player.room_id
