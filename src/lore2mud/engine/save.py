"""Versioned local save/load service for lore2mud.

Implements atomic save writes and strict validation on load.
Serialization logic lives here, not in CommandProcessor.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from lore2mud.content.models import ContentPack, QuestDefinition
from lore2mud.engine.models import Monster, Player, QuestState, Room
from lore2mud.engine.world import World
from lore2mud.inventory.models import EquippedItems, Inventory, Item

SAVE_FORMAT_VERSION = 4
DEFAULT_SLOT = "default.json"


class SaveLoadError(Exception):
    """Raised when save or load fails."""


def _validate_int(value: object, name: str, *, minimum: int | None = None) -> int:
    """Validate that value is an int (not bool) and meets minimum."""
    if isinstance(value, bool):
        raise SaveLoadError(f"{name} 必须是整数，不能是布尔值")
    if not isinstance(value, int):
        raise SaveLoadError(f"{name} 必须是整数")
    if minimum is not None and value < minimum:
        raise SaveLoadError(f"{name} 必须 >= {minimum}")
    return value


def _serialize_world(world: World) -> dict:
    """Serialize all mutable state from a World into a JSON-safe dict."""
    player = world.player
    rooms_data: dict[str, dict] = {}
    for room_id, room in world.rooms.items():
        rooms_data[room_id] = {
            "item_ids": list(room.item_ids),
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

    return {
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
            "inventory_item_ids": list(player.inventory.item_ids),
        },
        "equipped": {
            "hand": world.equipped.hand,
            "body": world.equipped.body,
        },
        "rooms": rooms_data,
        "monsters": monsters_data,
        "quest_states": quest_states_data,
    }


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
        # Clean up temp file on any failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _validate_and_build_world(data: dict, pack: ContentPack) -> World:
    """Validate save data and build a new World. Raises SaveLoadError on any issue."""
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

    if hp < 0 or hp > max_hp:
        raise SaveLoadError(f"player.hp ({hp}) 必须在 0 和 max_hp ({max_hp}) 之间")

    inv_ids_raw = player_data.get("inventory_item_ids")
    if not isinstance(inv_ids_raw, list):
        raise SaveLoadError("player.inventory_item_ids 必须是数组")
    inv_ids: list[str] = []
    for i, entry in enumerate(inv_ids_raw):
        if not isinstance(entry, str):
            raise SaveLoadError(f"player.inventory_item_ids[{i}] 必须是字符串")
        inv_ids.append(entry)
    if len(inv_ids) != len(set(inv_ids)):
        raise SaveLoadError("player.inventory_item_ids 包含重复物品")

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
    all_save_item_ids: set[str] = set()
    all_save_monster_ids: set[str] = set()
    for room_id, room_data in rooms_data.items():
        if not isinstance(room_data, dict):
            raise SaveLoadError(f"rooms.{room_id} 必须是对象")
        if "item_ids" not in room_data:
            raise SaveLoadError(f"rooms.{room_id} 缺少 item_ids 字段")
        if "monster_ids" not in room_data:
            raise SaveLoadError(f"rooms.{room_id} 缺少 monster_ids 字段")
        item_ids_raw = room_data["item_ids"]
        monster_ids_raw = room_data["monster_ids"]
        if not isinstance(item_ids_raw, list):
            raise SaveLoadError(f"rooms.{room_id}.item_ids 必须是数组")
        if not isinstance(monster_ids_raw, list):
            raise SaveLoadError(f"rooms.{room_id}.monster_ids 必须是数组")

        item_ids: list[str] = []
        for i, entry in enumerate(item_ids_raw):
            if not isinstance(entry, str):
                raise SaveLoadError(
                    f"rooms.{room_id}.item_ids[{i}] 必须是字符串"
                )
            item_ids.append(entry)

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
            item_ids=item_ids,
            monster_ids=monster_ids,
        )

        # Track all items and monsters for cross-room duplicate checks
        for iid in item_ids:
            if iid in all_save_item_ids:
                raise SaveLoadError(
                    f"物品 {iid} 重复出现在多个房间中"
                )
            all_save_item_ids.add(iid)

        for mid in monster_ids:
            if mid in all_save_monster_ids:
                raise SaveLoadError(
                    f"怪物 {mid} 重复出现在多个房间中"
                )
            all_save_monster_ids.add(mid)

    # --- Validate references ---
    # Player room must exist
    if player_room_id not in pack_room_ids:
        raise SaveLoadError(
            f"玩家房间 {player_room_id!r} 在内容包中不存在"
        )

    # All item IDs must exist in content pack
    pack_item_ids = set(pack.items.keys())
    for iid in all_save_item_ids:
        if iid not in pack_item_ids:
            raise SaveLoadError(f"物品 {iid!r} 在内容包中不存在")

    # Item in inventory must not also be in a room
    for iid in inv_ids:
        if iid in all_save_item_ids:
            raise SaveLoadError(
                f"物品 {iid!r} 同时出现在房间和背包中"
            )
        if iid not in pack_item_ids:
            raise SaveLoadError(f"背包物品 {iid!r} 在内容包中不存在")

    # Inventory capacity check
    capacity = pack.player.inventory_capacity
    if len(inv_ids) > capacity:
        raise SaveLoadError(
            f"背包物品数 ({len(inv_ids)}) 超过容量上限 ({capacity})"
        )

    # All monster IDs must exist in content pack
    pack_monster_ids = set(pack.monsters.keys())
    for mid in all_save_monster_ids:
        if mid not in pack_monster_ids:
            raise SaveLoadError(f"怪物 {mid!r} 在内容包中不存在")

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
            if slot_raw not in inv_ids:
                raise SaveLoadError(
                    f"equipped.{slot_name} 物品 {slot_raw!r} 不在背包中"
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
        hp=hp,
        inventory=Inventory(capacity=capacity, item_ids=inv_ids),
    )

    # --- Build World ---
    return World(
        pack_id=pack.id,
        pack_name=pack.name,
        pack_version=pack.version,
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
            )
            for item_id, item_def in pack.items.items()
        },
        monsters=monsters,
        player=player,
        quest_defs=dict(pack.quests),
        quest_states=quest_states,
        equipped=equipped,
    )


class SaveLoadService:
    """Holds content pack reference and save path; provides save/load to CLI."""

    def __init__(self, pack: ContentPack, save_dir: Path) -> None:
        self._pack = pack
        self._save_dir = save_dir
        self._save_path = save_dir / DEFAULT_SLOT

    @property
    def save_path(self) -> Path:
        return self._save_path

    def save(self, world: World) -> str:
        """Save current world state. Returns success message."""
        data = _serialize_world(world)
        _atomic_write(self._save_path, data)
        return f"存档成功：{self._save_path}"

    def load(self) -> World:
        """Load world from save file. Raises SaveLoadError on any failure."""
        if not self._save_path.is_file():
            raise SaveLoadError(f"存档文件不存在：{self._save_path}")

        try:
            raw_text = self._save_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise SaveLoadError(f"读取存档失败：{exc}") from exc

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise SaveLoadError(f"存档文件不是有效 JSON：{exc}") from exc

        if not isinstance(data, dict):
            raise SaveLoadError("存档顶层必须是 JSON 对象")

        return _validate_and_build_world(data, self._pack)
