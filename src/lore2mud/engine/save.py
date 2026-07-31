"""Versioned local save/load service for lore2mud.

Implements atomic save writes and strict validation on load.
Serialization logic lives here, not in CommandProcessor.
"""

from __future__ import annotations
import json
import os
import re
import tempfile
from pathlib import Path

from lore2mud.content.models import ContentPack
from lore2mud.engine.models import (
    Character,
    DialogueState,
    Monster,
    Player,
    QuestState,
    Room,
)
from lore2mud.engine.world import World
from lore2mud.inventory.models import EquippedItems, Inventory, Item, ItemStack

SAVE_FORMAT_VERSION = 7
DEFAULT_SLOT = "default.json"
_SLOT_NAME_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}")
_WINDOWS_RESERVED_SLOT_NAMES = frozenset(
    {"con", "prn", "aux", "nul"}
    | {f"com{number}" for number in range(1, 10)}
    | {f"lpt{number}" for number in range(1, 10)}
)
_SAVE_TOP_LEVEL_KEYS = frozenset(
    {
        "save_format_version",
        "content_pack",
        "player",
        "equipped",
        "rooms",
        "monsters",
        "quest_states",
        "flags",
        "active_dialogue",
    }
)
_CONTENT_PACK_KEYS = frozenset({"id", "version"})
_PLAYER_KEYS = frozenset(
    {
        "id",
        "name",
        "room_id",
        "max_hp",
        "hp",
        "attack",
        "defense",
        "level",
        "experience",
        "coins",
        "inventory_stacks",
    }
)
_ROOM_KEYS = frozenset({"item_stacks", "monster_ids"})
_MONSTER_KEYS = frozenset({"hp"})
_STACK_KEYS = frozenset({"item_id", "quantity"})
_STABLE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class SaveLoadError(Exception):
    """Raised when save or load fails."""


def _validate_int(
    value: object, name: str, *, minimum: int | None = None
) -> int:
    """Validate that value is an int (not bool) and meets minimum."""
    if isinstance(value, bool):
        raise SaveLoadError(f"{name} 必须是整数，不能是布尔值")
    if not isinstance(value, int):
        raise SaveLoadError(f"{name} 必须是整数")
    if minimum is not None and value < minimum:
        raise SaveLoadError(f"{name} 必须 >= {minimum}")
    return value


def _reject_unknown_fields(
    value: dict, allowed_keys: frozenset[str], location: str
) -> None:
    unknown = set(value) - allowed_keys
    if unknown:
        raise SaveLoadError(f"{location} 包含未知字段：{sorted(unknown)}")


def _validate_flags(raw: object, location: str) -> dict[str, bool]:
    """Validate the exact stable-ID-to-bool flags mapping at both boundaries."""
    if not isinstance(raw, dict):
        raise SaveLoadError(f"{location} 必须是对象")
    result: dict[str, bool] = {}
    for flag_id, value in raw.items():
        if not isinstance(flag_id, str) or not _STABLE_ID_PATTERN.fullmatch(flag_id):
            raise SaveLoadError(f"{location} 的 flag ID 必须是稳定 ID")
        if not isinstance(value, bool):
            raise SaveLoadError(f"{location}.{flag_id} 必须是布尔值")
        result[flag_id] = value
    return result


def _serialize_stacks(stacks: list[ItemStack]) -> list[dict]:
    return [{"item_id": s.item_id, "quantity": s.quantity} for s in stacks]


def _serialize_world(world: World) -> dict:
    """Serialize all mutable state from a World into a JSON-safe dict."""
    player = world.player
    coins = _validate_int(player.coins, "player.coins", minimum=0)
    flags = _validate_flags(world.flags, "flags")
    rooms_data: dict[str, dict] = {}
    for room_id, room in world.rooms.items():
        rooms_data[room_id] = {
            "item_stacks": _serialize_stacks(room.item_stacks),
            "monster_ids": list(room.monster_ids),
        }

    monsters_data: dict[str, dict] = {}
    for monster_id, monster in world.monsters.items():
        monsters_data[monster_id] = {
            "hp": monster.hp,
        }

    quest_states_data: dict[str, dict] = {}
    for quest_id, qs in world.quest_states.items():
        quest_states_data[quest_id] = {
            "completed": qs.completed,
        }

    result = {
        "save_format_version": SAVE_FORMAT_VERSION,
        "content_pack": {
            "id": world.pack_id,
            "version": world.pack_version,
        },
        "player": {
            "id": player.id,
            "name": player.name,
            "room_id": player.room_id,
            "max_hp": player.max_hp,
            "hp": player.hp,
            "attack": player.attack,
            "defense": player.defense,
            "level": player.level,
            "experience": player.experience,
            "coins": coins,
            "inventory_stacks": _serialize_stacks(player.inventory.stacks),
        },
        "equipped": {
            "hand": world.equipped.hand,
            "body": world.equipped.body,
        },
        "rooms": rooms_data,
        "monsters": monsters_data,
        "quest_states": quest_states_data,
        "flags": flags,
        "active_dialogue": (
            {
                "dialogue_id": world.active_dialogue.dialogue_id,
                "current_node_id": world.active_dialogue.current_node_id,
            }
            if world.active_dialogue is not None
            else None
        ),
    }
    # --- Validate active_dialogue before serializing ---
    if world.active_dialogue is not None:
        dlg_id = world.active_dialogue.dialogue_id
        dlg = world.dialogue_defs.get(dlg_id)
        if dlg is None:
            raise SaveLoadError(
                f"active_dialogue.dialogue_id {dlg_id!r} 不存在"
            )
        node_id = world.active_dialogue.current_node_id
        node = dlg.nodes.get(node_id)
        if node is None:
            raise SaveLoadError(
                f"active_dialogue.current_node_id {node_id!r} 在对话中不存在"
            )
        if not node.options:
            raise SaveLoadError(
                f"active_dialogue 指向终端节点 {node_id!r}"
            )
        char = world.characters.get(dlg.character_id)
        if char is None:
            raise SaveLoadError(
                f"对话 {dlg.id!r} 引用的角色 {dlg.character_id!r} 不存在"
            )
        if char.room_id != world.player.room_id:
            raise SaveLoadError(
                f"active_dialogue 角色 {dlg.character_id!r} 在房间 "
                f"{char.room_id!r}，与玩家房间 {world.player.room_id!r} 不一致"
            )
    return result


def _atomic_write(path: Path, data: dict) -> None:
    """Write JSON to a temp file in the same directory, then atomic replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        suffix=".tmp", dir=str(path.parent), prefix=".save_"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _validate_stacks(
    raw: object,
    location: str,
    pack: ContentPack,
    *,
    track_placements: dict[str, list[str]] | None = None,
    container_name: str = "",
) -> list[ItemStack]:
    """Validate a stacks array and return runtime ItemStacks."""
    if not isinstance(raw, list):
        raise SaveLoadError(f"{location} 必须是数组")
    result: list[ItemStack] = []
    seen_ids: set[str] = set()
    for i, entry in enumerate(raw):
        loc = f"{location}[{i}]"
        if not isinstance(entry, dict):
            raise SaveLoadError(f"{loc} 必须是对象")
        _reject_unknown_fields(entry, _STACK_KEYS, loc)

        item_id_raw = entry.get("item_id")
        if not isinstance(item_id_raw, str) or not item_id_raw:
            raise SaveLoadError(f"{loc}.item_id 必须是非空字符串")
        if item_id_raw not in pack.items:
            raise SaveLoadError(f"{loc} 物品 {item_id_raw!r} 在内容包中不存在")
        if item_id_raw in seen_ids:
            raise SaveLoadError(f"{location} 包含重复物品 {item_id_raw!r}")
        seen_ids.add(item_id_raw)

        qty_raw = entry.get("quantity")
        qty = _validate_int(qty_raw, f"{loc}.quantity", minimum=1)
        item_def = pack.items[item_id_raw]
        if qty > item_def.stack_limit:
            raise SaveLoadError(
                f"{loc} 数量 {qty} 超过栈上限 ({item_def.stack_limit})"
            )
        if item_def.stack_limit == 1 and qty != 1:
            raise SaveLoadError(
                f"{loc} stack_limit=1 的物品数量必须为 1"
            )

        result.append(ItemStack(item_id=item_id_raw, quantity=qty))

        if track_placements is not None:
            track_placements.setdefault(item_id_raw, []).append(container_name)

    return result


def _validate_and_build_world(data: dict, pack: ContentPack) -> World:
    """Validate save data and build a new World. Raises SaveLoadError on any issue."""
    _reject_unknown_fields(data, _SAVE_TOP_LEVEL_KEYS, "存档顶层")

    # --- save_format_version ---
    fmt = data.get("save_format_version")
    if isinstance(fmt, bool) or not isinstance(fmt, int) or fmt != SAVE_FORMAT_VERSION:
        raise SaveLoadError(
            f"存档格式版本不匹配：期望 {SAVE_FORMAT_VERSION}，实际 {fmt}"
        )

    # --- content_pack identity ---
    cp = data.get("content_pack")
    if not isinstance(cp, dict):
        raise SaveLoadError("存档缺少 content_pack 字段")
    _reject_unknown_fields(cp, _CONTENT_PACK_KEYS, "content_pack")
    if cp.get("id") != pack.id:
        raise SaveLoadError(
            f"内容包 ID 不匹配：期望 {pack.id!r}，实际 {cp.get('id')!r}"
        )
    if cp.get("version") != pack.version:
        raise SaveLoadError(
            f"内容包版本不匹配：期望 {pack.version!r}，实际 {cp.get('version')!r}"
        )

    # --- player ---
    player_data = data.get("player")
    if not isinstance(player_data, dict):
        raise SaveLoadError("存档缺少 player 字段")
    _reject_unknown_fields(player_data, _PLAYER_KEYS, "player")

    player_id = player_data.get("id")
    if player_id != "player_local":
        raise SaveLoadError(f"玩家 ID 不匹配：期望 'player_local'，实际 {player_id!r}")

    player_name = player_data.get("name")
    if not isinstance(player_name, str) or not player_name:
        raise SaveLoadError("player.name 必须是非空字符串")

    player_room_id = player_data.get("room_id")
    if not isinstance(player_room_id, str):
        raise SaveLoadError("player.room_id 必须是字符串")

    max_hp = _validate_int(player_data.get("max_hp"), "player.max_hp", minimum=1)
    hp = _validate_int(player_data.get("hp"), "player.hp")
    attack = _validate_int(player_data.get("attack"), "player.attack", minimum=1)
    defense = _validate_int(player_data.get("defense"), "player.defense", minimum=0)
    level = _validate_int(player_data.get("level"), "player.level", minimum=1)
    experience = _validate_int(
        player_data.get("experience"), "player.experience", minimum=0
    )
    coins = _validate_int(player_data.get("coins"), "player.coins", minimum=0)

    if hp < 0 or hp > max_hp:
        raise SaveLoadError(f"player.hp ({hp}) 必须在 0 和 max_hp ({max_hp}) 之间")

    capacity = pack.player.inventory_capacity

    # --- inventory stacks ---
    inv_stacks_raw = player_data.get("inventory_stacks")
    all_placements: dict[str, list[str]] = {}
    inv_stacks = _validate_stacks(
        inv_stacks_raw, "player.inventory_stacks", pack,
        track_placements=all_placements, container_name="__inventory__",
    )
    if len(inv_stacks) > capacity:
        raise SaveLoadError(
            f"背包栈位数 ({len(inv_stacks)}) 超过容量上限 ({capacity})"
        )

    # --- rooms ---
    rooms_data = data.get("rooms")
    if not isinstance(rooms_data, dict):
        raise SaveLoadError("存档缺少 rooms 字段")

    pack_room_ids = set(pack.rooms.keys())
    save_room_ids = set(rooms_data.keys())
    if save_room_ids != pack_room_ids:
        missing = pack_room_ids - save_room_ids
        extra = save_room_ids - pack_room_ids
        parts: list[str] = []
        if missing:
            parts.append(f"缺少：{sorted(missing)}")
        if extra:
            parts.append(f"多余：{sorted(extra)}")
        raise SaveLoadError(f"房间键集合不匹配：{'; '.join(parts)}")

    rooms: dict[str, Room] = {}
    for room_id, room_data in rooms_data.items():
        if not isinstance(room_data, dict):
            raise SaveLoadError(f"rooms.{room_id} 必须是对象")
        _reject_unknown_fields(room_data, _ROOM_KEYS, f"rooms.{room_id}")
        if "item_stacks" not in room_data:
            raise SaveLoadError(f"rooms.{room_id} 缺少 item_stacks 字段")
        if "monster_ids" not in room_data:
            raise SaveLoadError(f"rooms.{room_id} 缺少 monster_ids 字段")

        room_stacks = _validate_stacks(
            room_data["item_stacks"], f"rooms.{room_id}.item_stacks", pack,
            track_placements=all_placements, container_name=room_id,
        )

        monster_ids_raw = room_data["monster_ids"]
        if not isinstance(monster_ids_raw, list):
            raise SaveLoadError(f"rooms.{room_id}.monster_ids 必须是数组")

        monster_ids: list[str] = []
        for i, entry in enumerate(monster_ids_raw):
            if not isinstance(entry, str):
                raise SaveLoadError(
                    f"rooms.{room_id}.monster_ids[{i}] 必须是字符串"
                )
            monster_ids.append(entry)

        rooms[room_id] = Room(
            id=room_id,
            name=pack.rooms[room_id].name,
            description=pack.rooms[room_id].description,
            exits=dict(pack.rooms[room_id].exits),
            item_stacks=room_stacks,
            monster_ids=monster_ids,
        )

    # --- Cross-container uniqueness for stack_limit==1 ---
    inv_item_ids = {s.item_id for s in inv_stacks}
    room_item_ids: set[str] = set()
    for room in rooms.values():
        for s in room.item_stacks:
            room_item_ids.add(s.item_id)

    for item_id in all_placements:
        containers = all_placements[item_id]
        if len(containers) > 1 and pack.items[item_id].stack_limit == 1:
            raise SaveLoadError(
                f"stack_limit=1 的物品 {item_id!r} 出现在多个容器中：{containers}"
            )

    # Item in inventory must not also be in a room (for non-stackable)
    for iid in inv_item_ids:
        if iid in room_item_ids and pack.items[iid].stack_limit == 1:
            raise SaveLoadError(
                f"物品 {iid!r} 同时出现在房间和背包中"
            )

    # --- Validate references ---
    if player_room_id not in pack_room_ids:
        raise SaveLoadError(
            f"玩家房间 {player_room_id!r} 在内容包中不存在"
        )

    # --- monsters ---
    monsters_data = data.get("monsters")
    if not isinstance(monsters_data, dict):
        raise SaveLoadError("存档缺少 monsters 字段")

    pack_monster_ids_set = set(pack.monsters.keys())
    save_monster_ids = set(monsters_data.keys())
    if save_monster_ids != pack_monster_ids_set:
        missing = pack_monster_ids_set - save_monster_ids
        extra = save_monster_ids - pack_monster_ids_set
        parts = []
        if missing:
            parts.append(f"缺少：{sorted(missing)}")
        if extra:
            parts.append(f"多余：{sorted(extra)}")
        raise SaveLoadError(f"怪物键集合不匹配：{'; '.join(parts)}")

    monsters: dict[str, Monster] = {}
    for monster_id, monster_data in monsters_data.items():
        if not isinstance(monster_data, dict):
            raise SaveLoadError(f"monsters.{monster_id} 必须是对象")
        _reject_unknown_fields(
            monster_data, _MONSTER_KEYS, f"monsters.{monster_id}"
        )
        m_hp = _validate_int(monster_data.get("hp"), f"monsters.{monster_id}.hp")
        m_def = pack.monsters[monster_id]
        if m_hp < 0 or m_hp > m_def.max_hp:
            raise SaveLoadError(
                f"monsters.{monster_id}.hp ({m_hp}) 必须在 0 和 "
                f"max_hp ({m_def.max_hp}) 之间"
            )
        monsters[monster_id] = Monster(
            id=monster_id,
            name=m_def.name,
            description=m_def.description,
            max_hp=m_def.max_hp,
            attack=m_def.attack,
            defense=m_def.defense,
            experience_reward=m_def.experience_reward,
            hp=m_hp,
            loot_item=m_def.loot_item,
        )

    # Alive monster non-stackable loot must not be placed
    for monster_id, monster in monsters.items():
        loot = monster.loot_item
        if loot is None:
            continue
        if not monster.is_alive:
            continue
        item_def = pack.items.get(loot.item_id)
        if item_def is None:
            continue
        if item_def.stack_limit == 1:
            containers = all_placements.get(loot.item_id, [])
            if containers:
                raise SaveLoadError(
                    f"存活怪物 {monster_id!r} 的战利品 {loot.item_id!r} "
                    f"已出现在容器 {containers} 中"
                )

    # --- quest_states ---
    quest_states_raw = data.get("quest_states")
    if not isinstance(quest_states_raw, dict):
        raise SaveLoadError("存档缺少 quest_states 字段")

    pack_quest_ids = set(pack.quests.keys())
    quest_states: dict[str, QuestState] = {}
    for quest_id, qs_data in quest_states_raw.items():
        if quest_id not in pack_quest_ids:
            raise SaveLoadError(f"任务 {quest_id!r} 在内容包中不存在")
        if not isinstance(qs_data, dict):
            raise SaveLoadError(f"quest_states.{quest_id} 必须是对象")

        allowed_keys = {"completed"}
        unknown = set(qs_data.keys()) - allowed_keys
        if unknown:
            raise SaveLoadError(
                f"quest_states.{quest_id} 包含未知字段：{sorted(unknown)}"
            )

        completed_raw = qs_data.get("completed")
        if isinstance(completed_raw, bool):
            completed = completed_raw
        else:
            raise SaveLoadError(
                f"quest_states.{quest_id}.completed 必须是布尔值"
            )

        quest_states[quest_id] = QuestState(
            quest_id=quest_id,
            completed=completed,
        )

    # --- flags ---
    if "flags" not in data:
        raise SaveLoadError("存档缺少 flags 字段")
    flags = _validate_flags(data["flags"], "flags")

    # --- equipped (symmetric hand + body) ---
    equipped_raw = data.get("equipped")
    if not isinstance(equipped_raw, dict):
        raise SaveLoadError("存档缺少 equipped 字段")

    allowed_equip_keys = {"hand", "body"}
    unknown_equip = set(equipped_raw.keys()) - allowed_equip_keys
    if unknown_equip:
        raise SaveLoadError(
            f"equipped 包含未知字段：{sorted(unknown_equip)}"
        )

    equipped_hand: str | None = None
    equipped_body: str | None = None
    for slot_name in ("hand", "body"):
        if slot_name not in equipped_raw:
            raise SaveLoadError(f"equipped 缺少 {slot_name} 字段")

        slot_raw = equipped_raw[slot_name]
        equipped_val: str | None = None
        if slot_raw is not None:
            if not isinstance(slot_raw, str):
                raise SaveLoadError(f"equipped.{slot_name} 必须是字符串或 null")
            if slot_raw not in pack.items:
                raise SaveLoadError(
                    f"equipped.{slot_name} 物品 {slot_raw!r} 在内容包中不存在"
                )
            # Check stack exists and quantity == 1
            inv_stack = None
            for s in inv_stacks:
                if s.item_id == slot_raw:
                    inv_stack = s
                    break
            if inv_stack is None:
                raise SaveLoadError(
                    f"equipped.{slot_name} 物品 {slot_raw!r} 不在背包栈中"
                )
            if inv_stack.quantity != 1:
                raise SaveLoadError(
                    f"equipped.{slot_name} 物品 {slot_raw!r} 数量必须为 1"
                )
            item_def = pack.items[slot_raw]
            if item_def.slot != slot_name:
                raise SaveLoadError(
                    f"equipped.{slot_name} 物品 {slot_raw!r} 的 slot 不是 {slot_name}"
                )
            if item_def.heal_amount is not None:
                raise SaveLoadError(
                    f"equipped.{slot_name} 物品 {slot_raw!r} 有 heal_amount，不可装备"
                )
            if slot_name == "hand":
                if item_def.attack_bonus < 1:
                    raise SaveLoadError(
                        f"equipped.hand 物品 {slot_raw!r} 的 attack_bonus 不是正整数"
                    )
                if item_def.defense_bonus != 0:
                    raise SaveLoadError(
                        f"equipped.hand 物品 {slot_raw!r} 有 defense_bonus，不可装备"
                    )
            else:  # body
                if item_def.defense_bonus < 1:
                    raise SaveLoadError(
                        f"equipped.body 物品 {slot_raw!r} 的 defense_bonus 不是正整数"
                    )
                if item_def.attack_bonus != 0:
                    raise SaveLoadError(
                        f"equipped.body 物品 {slot_raw!r} 有 attack_bonus，不可装备"
                    )
            equipped_val = slot_raw

        if slot_name == "hand":
            equipped_hand = equipped_val
        else:
            equipped_body = equipped_val

    equipped = EquippedItems(hand=equipped_hand, body=equipped_body)

    # --- active_dialogue (required in v7) ---
    if "active_dialogue" not in data:
        raise SaveLoadError("存档缺少 active_dialogue 字段")
    active_dialogue_raw = data["active_dialogue"]
    active_dialogue: DialogueState | None = None
    if active_dialogue_raw is not None:
        if not isinstance(active_dialogue_raw, dict):
            raise SaveLoadError("active_dialogue 必须是对象或 null")
        allowed_dlg_keys = {"dialogue_id", "current_node_id"}
        unknown_dlg = set(active_dialogue_raw.keys()) - allowed_dlg_keys
        if unknown_dlg:
            raise SaveLoadError(
                f"active_dialogue 包含未知字段：{sorted(unknown_dlg)}"
            )
        dlg_id = active_dialogue_raw.get("dialogue_id")
        if not isinstance(dlg_id, str) or not dlg_id:
            raise SaveLoadError(
                "active_dialogue.dialogue_id 必须是非空字符串"
            )
        dlg_node_id = active_dialogue_raw.get("current_node_id")
        if not isinstance(dlg_node_id, str) or not dlg_node_id:
            raise SaveLoadError(
                "active_dialogue.current_node_id 必须是非空字符串"
            )
        if dlg_id not in pack.dialogues:
            raise SaveLoadError(
                f"active_dialogue.dialogue_id {dlg_id!r} 在内容包中不存在"
            )
        ddef = pack.dialogues[dlg_id]
        if dlg_node_id not in ddef.nodes:
            raise SaveLoadError(
                f"active_dialogue.current_node_id {dlg_node_id!r} "
                f"在对话 {dlg_id!r} 中不存在"
            )
        if not ddef.nodes[dlg_node_id].options:
            raise SaveLoadError(
                f"active_dialogue 指向终端节点 {dlg_node_id!r}，应为 null"
            )
        dlg_char = pack.characters.get(ddef.character_id)
        if dlg_char is None:
            raise SaveLoadError(
                f"对话 {dlg_id!r} 引用的角色 {ddef.character_id!r} 不存在"
            )
        if dlg_char.room_id != player_room_id:
            raise SaveLoadError(
                f"active_dialogue 角色 {ddef.character_id!r} 在房间 "
                f"{dlg_char.room_id!r}，与玩家房间 {player_room_id!r} 不一致"
            )
        active_dialogue = DialogueState(
            dialogue_id=dlg_id, current_node_id=dlg_node_id
        )

    # --- Build player ---
    player = Player(
        id="player_local",
        name=player_name,
        room_id=player_room_id,
        max_hp=max_hp,
        attack=attack,
        defense=defense,
        level=level,
        experience=experience,
        coins=coins,
        hp=hp,
        inventory=Inventory(capacity=capacity, stacks=inv_stacks),
    )

    # --- Build characters ---
    characters = {
        char_id: Character(
            id=char_def.id,
            name=char_def.name,
            description=char_def.description,
            room_id=char_def.room_id,
        )
        for char_id, char_def in pack.characters.items()
    }

    # --- Build World ---
    return World(
        pack_id=pack.id,
        pack_name=pack.name,
        pack_version=pack.version,
        start_room_id=pack.start_room_id,
        rooms=rooms,
        items={
            item_id: Item(
                id=item_id,
                name=item_def.name,
                description=item_def.description,
                heal_amount=item_def.heal_amount,
                slot=item_def.slot,
                attack_bonus=item_def.attack_bonus,
                defense_bonus=item_def.defense_bonus,
                stack_limit=item_def.stack_limit,
            )
            for item_id, item_def in pack.items.items()
        },
        monsters=monsters,
        player=player,
        quest_defs=dict(pack.quests),
        quest_states=quest_states,
        flags=flags,
        equipped=equipped,
        characters=characters,
        dialogue_defs=dict(pack.dialogues),
        shop_defs=dict(pack.shops),
        active_dialogue=active_dialogue,
    )


class SaveLoadService:
    """Holds content pack reference and safe local save-slot paths."""

    def __init__(self, pack: ContentPack, save_dir: Path) -> None:
        self._pack = pack
        self._save_dir = save_dir
        self._save_path = save_dir / DEFAULT_SLOT

    @property
    def save_path(self) -> Path:
        """Return the backward-compatible path for the default save slot."""
        return self._save_path

    def slot_path(self, slot: str) -> Path:
        """Return the validated path for one named save slot."""
        return self._path_for_slot(slot)

    def save(self, world: World, slot: str | None = None) -> str:
        """Save current world state. Returns success message."""
        save_path = self._path_for_slot(slot)
        data = _serialize_world(world)
        try:
            _atomic_write(save_path, data)
        except OSError as exc:
            raise SaveLoadError(f"写入存档失败：{exc}") from exc
        return f"存档成功：{save_path}"

    def load(self, slot: str | None = None) -> World:
        """Load world from save file. Raises SaveLoadError on any failure."""
        save_path = self._path_for_slot(slot)
        if not save_path.is_file():
            raise SaveLoadError(f"存档文件不存在：{save_path}")

        try:
            raw_text = save_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise SaveLoadError(f"读取存档失败：{exc}") from exc

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise SaveLoadError(f"存档文件不是有效 JSON：{exc}") from exc

        if not isinstance(data, dict):
            raise SaveLoadError("存档顶层必须是 JSON 对象")

        return _validate_and_build_world(data, self._pack)

    def _path_for_slot(self, slot: str | None) -> Path:
        if slot is None:
            return self._save_path
        if (
            not isinstance(slot, str)
            or not _SLOT_NAME_PATTERN.fullmatch(slot)
            or slot in _WINDOWS_RESERVED_SLOT_NAMES
        ):
            raise SaveLoadError(
                "存档槽位必须为 1–32 位小写字母、数字、连字符或下划线，"
                "且以字母或数字开头。"
            )
        return self._save_dir / f"{slot}.json"
