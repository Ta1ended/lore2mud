"""Load JSON content packs and reject malformed or dangling references."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from lore2mud.content.models import (
    CanonReference,
    CharacterDefinition,
    ContentMetadata,
    ContentPack,
    DialogueDefinition,
    DialogueNode,
    DialogueOption,
    ExitDefinition,
    ItemDefinition,
    MonsterDefinition,
    PlayerDefaults,
    QuestDefinition,
    RoomDefinition,
)

STABLE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
ENTITY_FILES = (
    "rooms.json",
    "items.json",
    "monsters.json",
    "characters.json",
    "quests.json",
    "dialogues.json",
)


class ContentValidationError(ValueError):
    def __init__(self, issues: list[str]) -> None:
        self.issues = tuple(issues)
        super().__init__("\n".join(f"- {issue}" for issue in issues))


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ContentValidationError([f"缺少文件：{path.name}"]) from None
    except UnicodeDecodeError:
        raise ContentValidationError(
            [f"{path.name} 不是有效 UTF-8 编码"]
        ) from None
    except json.JSONDecodeError as exc:
        raise ContentValidationError(
            [f"{path.name} 不是有效 JSON：第 {exc.lineno} 行 {exc.msg}"]
        ) from None


class _Validator:
    def __init__(self) -> None:
        self.issues: list[str] = []

    def object(self, value: Any, location: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            self.issues.append(f"{location} 必须是对象")
            return {}
        return value

    def keys(
        self,
        obj: dict[str, Any],
        allowed: set[str],
        location: str,
    ) -> None:
        for key in sorted(set(obj) - allowed):
            self.issues.append(f"{location} 包含未知字段：{key}")

    def array(self, value: Any, location: str) -> list[Any]:
        if not isinstance(value, list):
            self.issues.append(f"{location} 必须是数组")
            return []
        return value

    def text(
        self,
        obj: dict[str, Any],
        key: str,
        location: str,
        *,
        required: bool = True,
        default: str = "",
    ) -> str:
        if key not in obj and not required:
            return default
        value = obj.get(key)
        if not isinstance(value, str) or not value.strip():
            self.issues.append(f"{location}.{key} 必须是非空字符串")
            return default
        return value

    def integer(
        self,
        obj: dict[str, Any],
        key: str,
        location: str,
        *,
        minimum: int = 0,
        default: int = 0,
        required: bool = True,
    ) -> int:
        if key not in obj:
            if required:
                self.issues.append(f"{location}.{key} 是必填字段")
            return default
        value = obj.get(key, default)
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or value < minimum
        ):
            self.issues.append(f"{location}.{key} 必须是 >= {minimum} 的整数")
            return default
        return value

    def stable_id(self, value: str, location: str) -> str:
        if value and not STABLE_ID_PATTERN.fullmatch(value):
            self.issues.append(
                f"{location} 必须是稳定 ID（小写字母开头，仅含小写字母、数字、下划线）"
            )
        return value

    def string_list(
        self,
        value: Any,
        location: str,
    ) -> tuple[str, ...]:
        values = self.array(value, location)
        result: list[str] = []
        for index, entry in enumerate(values):
            if not isinstance(entry, str) or not entry.strip():
                self.issues.append(f"{location}[{index}] 必须是非空字符串")
            else:
                result.append(entry)
        if len(result) != len(set(result)):
            self.issues.append(f"{location} 不得包含重复 ID")
        return tuple(result)


def _metadata(
    obj: dict[str, Any],
    location: str,
    validator: _Validator,
) -> ContentMetadata:
    adaptation_notes = obj.get("adaptation_notes")
    if adaptation_notes is not None and not isinstance(adaptation_notes, str):
        validator.issues.append(f"{location}.adaptation_notes 必须是字符串")
        adaptation_notes = None

    raw_ref = obj.get("canon_ref")
    if raw_ref is None:
        return ContentMetadata(adaptation_notes=adaptation_notes)
    ref = validator.object(raw_ref, f"{location}.canon_ref")
    validator.keys(
        ref,
        {"entity_id", "source_chapters"},
        f"{location}.canon_ref",
    )
    entity_id = validator.text(
        ref,
        "entity_id",
        f"{location}.canon_ref",
    )
    validator.stable_id(entity_id, f"{location}.canon_ref.entity_id")
    source_chapters = validator.string_list(
        ref.get("source_chapters"),
        f"{location}.canon_ref.source_chapters",
    )
    if not source_chapters:
        validator.issues.append(
            f"{location}.canon_ref.source_chapters 至少需要一个来源章节"
        )
    return ContentMetadata(
        canon_ref=CanonReference(
            entity_id=entity_id,
            source_chapters=source_chapters,
        ),
        adaptation_notes=adaptation_notes,
    )


def _load_entity_array(
    root: Path,
    filename: str,
    validator: _Validator,
) -> list[dict[str, Any]]:
    try:
        raw = _read_json(root / filename)
    except ContentValidationError as exc:
        validator.issues.extend(exc.issues)
        return []
    values = validator.array(raw, filename)
    return [
        validator.object(value, f"{filename}[{index}]")
        for index, value in enumerate(values)
    ]


def _unique_map(
    definitions: list[Any],
    filename: str,
    validator: _Validator,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for definition in definitions:
        if definition.id in result:
            validator.issues.append(
                f"{filename} 包含重复 ID：{definition.id}"
            )
        elif definition.id:
            result[definition.id] = definition
    return result


def load_content_pack(path: str | Path) -> ContentPack:
    root = Path(path).resolve()
    validator = _Validator()
    if not root.is_dir():
        raise ContentValidationError([f"内容包目录不存在：{root}"])

    try:
        raw_pack = _read_json(root / "pack.json")
    except ContentValidationError as exc:
        raise ContentValidationError(list(exc.issues)) from None
    pack_data = validator.object(raw_pack, "pack.json")
    validator.keys(
        pack_data,
        {
            "id",
            "name",
            "version",
            "start_room_id",
            "player",
            "extensions",
        },
        "pack.json",
    )
    pack_id = validator.stable_id(
        validator.text(pack_data, "id", "pack.json"),
        "pack.json.id",
    )
    pack_name = validator.text(pack_data, "name", "pack.json")
    version = validator.text(pack_data, "version", "pack.json")
    start_room_id = validator.stable_id(
        validator.text(pack_data, "start_room_id", "pack.json"),
        "pack.json.start_room_id",
    )
    player_data = validator.object(pack_data.get("player", {}), "pack.json.player")
    validator.keys(
        player_data,
        {"max_hp", "attack", "defense", "inventory_capacity"},
        "pack.json.player",
    )
    player = PlayerDefaults(
        max_hp=validator.integer(
            player_data, "max_hp", "pack.json.player", minimum=1, default=20
        ),
        attack=validator.integer(
            player_data, "attack", "pack.json.player", minimum=1, default=5
        ),
        defense=validator.integer(
            player_data, "defense", "pack.json.player", minimum=0, default=1
        ),
        inventory_capacity=validator.integer(
            player_data,
            "inventory_capacity",
            "pack.json.player",
            minimum=1,
            default=20,
        ),
    )

    room_defs: list[RoomDefinition] = []
    for index, obj in enumerate(
        _load_entity_array(root, "rooms.json", validator)
    ):
        location = f"rooms.json[{index}]"
        validator.keys(
            obj,
            {
                "id",
                "name",
                "description",
                "exits",
                "item_ids",
                "monster_ids",
                "canon_ref",
                "adaptation_notes",
            },
            location,
        )
        entity_id = validator.stable_id(
            validator.text(obj, "id", location),
            f"{location}.id",
        )
        raw_exits = validator.object(obj.get("exits", {}), f"{location}.exits")
        exits: dict[str, ExitDefinition] = {}
        for direction, raw_exit in raw_exits.items():
            exit_location = f"{location}.exits[{direction!r}]"
            if not isinstance(direction, str) or not direction.strip():
                validator.issues.append(
                    f"{location}.exits 的方向必须是非空字符串"
                )
                continue
            normalized_direction = direction.casefold()

            if isinstance(raw_exit, str):
                if not raw_exit.strip():
                    validator.issues.append(
                        f"{exit_location} 必须是非空字符串或出口对象"
                    )
                    continue
                exit_def = ExitDefinition(
                    target_room_id=validator.stable_id(
                        raw_exit, f"{exit_location}.target_room_id"
                    )
                )
            elif isinstance(raw_exit, dict):
                exit_obj = validator.object(raw_exit, exit_location)
                validator.keys(
                    exit_obj,
                    {"target_room_id", "required_item_id"},
                    exit_location,
                )
                target_room_id = validator.stable_id(
                    validator.text(exit_obj, "target_room_id", exit_location),
                    f"{exit_location}.target_room_id",
                )
                required_item_id: str | None = None
                if "required_item_id" in exit_obj:
                    required_item_id = validator.stable_id(
                        validator.text(
                            exit_obj, "required_item_id", exit_location
                        ),
                        f"{exit_location}.required_item_id",
                    )
                exit_def = ExitDefinition(
                    target_room_id=target_room_id,
                    required_item_id=required_item_id,
                )
            else:
                validator.issues.append(
                    f"{exit_location} 必须是非空字符串或出口对象"
                )
                continue

            if normalized_direction in exits:
                validator.issues.append(
                    f"{location}.exits 包含大小写无关的重复方向："
                    f"{direction}"
                )
                continue
            exits[normalized_direction] = exit_def
        room_defs.append(
            RoomDefinition(
                id=entity_id,
                name=validator.text(obj, "name", location),
                description=validator.text(obj, "description", location),
                exits=exits,
                item_ids=validator.string_list(
                    obj.get("item_ids", []), f"{location}.item_ids"
                ),
                monster_ids=validator.string_list(
                    obj.get("monster_ids", []), f"{location}.monster_ids"
                ),
                metadata=_metadata(obj, location, validator),
            )
        )

    item_defs: list[ItemDefinition] = []
    for index, obj in enumerate(_load_entity_array(root, "items.json", validator)):
        location = f"items.json[{index}]"
        validator.keys(
            obj,
            {
                "id",
                "name",
                "description",
                "heal_amount",
                "slot",
                "attack_bonus",
                "defense_bonus",
                "canon_ref",
                "adaptation_notes",
            },
            location,
        )
        entity_id = validator.stable_id(
            validator.text(obj, "id", location), f"{location}.id",
        )
        # heal_amount: optional; only validate when present.
        heal_amount: int | None = None
        if "heal_amount" in obj:
            heal_amount = validator.integer(
                obj, "heal_amount", location, minimum=1, default=0,
            )
        # slot: optional; must be "hand" or "body" if present.
        slot: str | None = None
        if "slot" in obj:
            raw_slot = obj.get("slot")
            if raw_slot is None:
                validator.issues.append(
                    f"{location}.slot 不能为 null；省略该字段表示不可装备"
                )
            elif not isinstance(raw_slot, str) or raw_slot not in ("hand", "body"):
                validator.issues.append(
                    f"{location}.slot 必须是 \"hand\" 或 \"body\""
                )
            else:
                slot = raw_slot
        # attack_bonus: optional; only validate when present.
        attack_bonus = 0
        if "attack_bonus" in obj:
            attack_bonus = validator.integer(
                obj, "attack_bonus", location, minimum=1, default=0,
            )
        # defense_bonus: optional; only validate when present.
        defense_bonus = 0
        if "defense_bonus" in obj:
            defense_bonus = validator.integer(
                obj, "defense_bonus", location, minimum=1, default=0,
            )
        # Cross-field validation.
        if slot is not None and attack_bonus < 1 and defense_bonus < 1:
            validator.issues.append(
                f"{location}: slot 为 {slot!r} 时必须有对应的正整数 bonus"
            )
        if attack_bonus >= 1 and slot is None:
            validator.issues.append(
                f"{location}: attack_bonus >= 1 时必须指定 slot"
            )
        if defense_bonus >= 1 and slot is None:
            validator.issues.append(
                f"{location}: defense_bonus >= 1 时必须指定 slot"
            )
        if slot is not None and heal_amount is not None:
            validator.issues.append(
                f"{location}: 同时指定 slot 和 heal_amount 是非法组合"
            )
        if attack_bonus >= 1 and defense_bonus >= 1:
            validator.issues.append(
                f"{location}: attack_bonus 和 defense_bonus 不可同时指定"
            )
        # Slot-specific bonus validation.
        if slot == "hand" and defense_bonus >= 1:
            validator.issues.append(
                f"{location}: hand 槽不可指定 defense_bonus"
            )
        if slot == "body" and attack_bonus >= 1:
            validator.issues.append(
                f"{location}: body 槽不可指定 attack_bonus"
            )
        item_defs.append(
            ItemDefinition(
                id=entity_id,
                name=validator.text(obj, "name", location),
                description=validator.text(obj, "description", location),
                heal_amount=heal_amount,
                slot=slot,
                attack_bonus=attack_bonus,
                defense_bonus=defense_bonus,
                metadata=_metadata(obj, location, validator),
            )
        )

    monster_defs: list[MonsterDefinition] = []
    for index, obj in enumerate(
        _load_entity_array(root, "monsters.json", validator)
    ):
        location = f"monsters.json[{index}]"
        validator.keys(
            obj,
            {
                "id",
                "name",
                "description",
                "room_id",
                "max_hp",
                "attack",
                "defense",
                "experience_reward",
                "canon_ref",
                "adaptation_notes",
            },
            location,
        )
        entity_id = validator.stable_id(
            validator.text(obj, "id", location),
            f"{location}.id",
        )
        room_id = validator.stable_id(
            validator.text(obj, "room_id", location),
            f"{location}.room_id",
        )
        monster_defs.append(
            MonsterDefinition(
                id=entity_id,
                name=validator.text(obj, "name", location),
                description=validator.text(obj, "description", location),
                room_id=room_id,
                max_hp=validator.integer(
                    obj, "max_hp", location, minimum=1, default=1
                ),
                attack=validator.integer(
                    obj, "attack", location, minimum=1, default=1
                ),
                defense=validator.integer(
                    obj, "defense", location, minimum=0, default=0
                ),
                experience_reward=validator.integer(
                    obj,
                    "experience_reward",
                    location,
                    minimum=0,
                    default=0,
                ),
                metadata=_metadata(obj, location, validator),
            )
        )

    character_defs: list[CharacterDefinition] = []
    for index, obj in enumerate(
        _load_entity_array(root, "characters.json", validator)
    ):
        location = f"characters.json[{index}]"
        validator.keys(
            obj,
            {
                "id",
                "name",
                "description",
                "room_id",
                "canon_ref",
                "adaptation_notes",
            },
            location,
        )
        entity_id = validator.stable_id(
            validator.text(obj, "id", location),
            f"{location}.id",
        )
        room_id = validator.stable_id(
            validator.text(obj, "room_id", location),
            f"{location}.room_id",
        )
        character_defs.append(
            CharacterDefinition(
                id=entity_id,
                name=validator.text(obj, "name", location),
                description=validator.text(obj, "description", location),
                room_id=room_id,
                metadata=_metadata(obj, location, validator),
            )
        )

    quest_defs: list[QuestDefinition] = []
    for index, obj in enumerate(
        _load_entity_array(root, "quests.json", validator)
    ):
        location = f"quests.json[{index}]"
        validator.keys(
            obj,
            {
                "id",
                "name",
                "description",
                "trigger_room_id",
                "target_monster_id",
                "reward_experience",
                "canon_ref",
                "adaptation_notes",
            },
            location,
        )
        entity_id = validator.stable_id(
            validator.text(obj, "id", location),
            f"{location}.id",
        )
        trigger_room_id = validator.stable_id(
            validator.text(obj, "trigger_room_id", location),
            f"{location}.trigger_room_id",
        )
        target_monster_id = validator.stable_id(
            validator.text(obj, "target_monster_id", location),
            f"{location}.target_monster_id",
        )
        reward_experience = validator.integer(
            obj,
            "reward_experience",
            location,
            minimum=0,
            default=0,
        )
        quest_defs.append(
            QuestDefinition(
                id=entity_id,
                name=validator.text(obj, "name", location),
                description=validator.text(obj, "description", location),
                trigger_room_id=trigger_room_id,
                target_monster_id=target_monster_id,
                reward_experience=reward_experience,
                metadata=_metadata(obj, location, validator),
            )
        )

    rooms = _unique_map(room_defs, "rooms.json", validator)
    items = _unique_map(item_defs, "items.json", validator)
    monsters = _unique_map(monster_defs, "monsters.json", validator)
    characters = _unique_map(character_defs, "characters.json", validator)
    quests = _unique_map(quest_defs, "quests.json", validator)

    # --- dialogues ---
    dialogue_defs_list: list[DialogueDefinition] = []
    dialogue_character_ids: set[str] = set()
    for index, obj in enumerate(
        _load_entity_array(root, "dialogues.json", validator)
    ):
        location = f"dialogues.json[{index}]"
        validator.keys(
            obj,
            {
                "id",
                "character_id",
                "start_node_id",
                "nodes",
                "canon_ref",
                "adaptation_notes",
            },
            location,
        )
        dlg_id = validator.stable_id(
            validator.text(obj, "id", location), f"{location}.id"
        )
        char_id = validator.stable_id(
            validator.text(obj, "character_id", location),
            f"{location}.character_id",
        )
        start_nid = validator.text(obj, "start_node_id", location)

        nodes_raw = validator.array(obj.get("nodes"), f"{location}.nodes")
        if not nodes_raw:
            validator.issues.append(f"{location}.nodes 不能为空")

        node_map: dict[str, DialogueNode] = {}
        for ni, node_obj in enumerate(nodes_raw):
            nloc = f"{location}.nodes[{ni}]"
            node_obj = validator.object(node_obj, nloc)
            validator.keys(node_obj, {"id", "text", "options"}, nloc)
            nid = validator.stable_id(
                validator.text(node_obj, "id", nloc), f"{nloc}.id"
            )
            ntext = validator.text(node_obj, "text", nloc)

            if "options" not in node_obj:
                validator.issues.append(f"{nloc} 缺少 options 字段")
                opts_raw_list: list = []
            else:
                opts_raw_list = validator.array(
                    node_obj["options"], f"{nloc}.options"
                )

            opts: list[DialogueOption] = []
            opt_ids_seen: set[str] = set()
            for oi, opt_obj in enumerate(opts_raw_list):
                oloc = f"{nloc}.options[{oi}]"
                opt_obj = validator.object(opt_obj, oloc)
                validator.keys(
                    opt_obj,
                    {"id", "text", "next_node_id", "grant_item_id"},
                    oloc,
                )
                oid = validator.stable_id(
                    validator.text(opt_obj, "id", oloc), f"{oloc}.id"
                )
                otxt = validator.text(opt_obj, "text", oloc)
                next_raw = opt_obj.get("next_node_id")
                if next_raw is None:
                    next_id: str | None = None
                elif isinstance(next_raw, str) and next_raw.strip():
                    next_id = next_raw
                else:
                    validator.issues.append(
                        f"{oloc}.next_node_id 必须是非空字符串或 null"
                    )
                    next_id = None
                grant_item_id: str | None = None
                if "grant_item_id" in opt_obj:
                    raw_grant_item_id = opt_obj["grant_item_id"]
                    if (
                        isinstance(raw_grant_item_id, str)
                        and raw_grant_item_id.strip()
                    ):
                        grant_item_id = validator.stable_id(
                            raw_grant_item_id,
                            f"{oloc}.grant_item_id",
                        )
                    else:
                        validator.text(opt_obj, "grant_item_id", oloc)
                if oid in opt_ids_seen:
                    validator.issues.append(f"{nloc} 选项 ID 重复：{oid}")
                opt_ids_seen.add(oid)
                opts.append(
                    DialogueOption(
                        id=oid,
                        text=otxt,
                        next_node_id=next_id,
                        grant_item_id=grant_item_id,
                    )
                )

            if nid in node_map:
                validator.issues.append(f"{location} 节点 ID 重复：{nid}")
            node_map[nid] = DialogueNode(
                id=nid, text=ntext, options=tuple(opts)
            )

        if start_nid and start_nid not in node_map:
            validator.issues.append(
                f"{location}.start_node_id {start_nid!r} 在 nodes 中不存在"
            )
        for node in node_map.values():
            for opt in node.options:
                if (
                    opt.next_node_id is not None
                    and opt.next_node_id not in node_map
                ):
                    validator.issues.append(
                        f"{location} 节点 {node.id} 选项 {opt.id} "
                        f"引用了不存在的节点：{opt.next_node_id}"
                    )
        if char_id in dialogue_character_ids:
            validator.issues.append(f"角色 {char_id} 有多个对话定义")
        dialogue_character_ids.add(char_id)
        dialogue_defs_list.append(
            DialogueDefinition(
                id=dlg_id,
                character_id=char_id,
                start_node_id=start_nid,
                nodes=node_map,
                metadata=_metadata(obj, location, validator),
            )
        )

    dialogues = _unique_map(dialogue_defs_list, "dialogues.json", validator)

    if start_room_id and start_room_id not in rooms:
        validator.issues.append(
            f"pack.json.start_room_id 引用了不存在的房间：{start_room_id}"
        )

    item_placements: dict[str, str] = {}
    monster_placements: dict[str, str] = {}
    for room in rooms.values():
        for direction, exit_def in room.exits.items():
            if exit_def.target_room_id not in rooms:
                validator.issues.append(
                    f"房间 {room.id} 的出口 {direction} 引用了不存在的房间："
                    f"{exit_def.target_room_id}"
                )
            if (
                exit_def.required_item_id is not None
                and exit_def.required_item_id not in items
            ):
                validator.issues.append(
                    f"房间 {room.id} 的出口 {direction} 所需物品不存在："
                    f"{exit_def.required_item_id}"
                )
        for item_id in room.item_ids:
            if item_id not in items:
                validator.issues.append(
                    f"房间 {room.id} 引用了不存在的物品：{item_id}"
                )
            elif item_id in item_placements:
                validator.issues.append(
                    f"物品 {item_id} 同时放置在 {item_placements[item_id]} "
                    f"和 {room.id}"
                )
            else:
                item_placements[item_id] = room.id
        for monster_id in room.monster_ids:
            if monster_id not in monsters:
                validator.issues.append(
                    f"房间 {room.id} 引用了不存在的怪物：{monster_id}"
                )
            elif monster_id in monster_placements:
                validator.issues.append(
                    f"怪物 {monster_id} 同时放置在 "
                    f"{monster_placements[monster_id]} 和 {room.id}"
                )
            else:
                monster_placements[monster_id] = room.id

    for monster in monsters.values():
        if monster.room_id not in rooms:
            validator.issues.append(
                f"怪物 {monster.id} 的 room_id 引用了不存在的房间："
                f"{monster.room_id}"
            )
        elif monster_placements.get(monster.id) != monster.room_id:
            validator.issues.append(
                f"怪物 {monster.id} 的 room_id 与房间 monster_ids 不一致"
            )
    for character in characters.values():
        if character.room_id not in rooms:
            validator.issues.append(
                f"角色 {character.id} 的 room_id 引用了不存在的房间："
                f"{character.room_id}"
            )
    granted_item_options: dict[str, list[str]] = {}
    for dialogue in dialogues.values():
        if dialogue.character_id not in characters:
            validator.issues.append(
                f"对话 {dialogue.id} 的 character_id 引用了不存在的角色："
                f"{dialogue.character_id}"
            )
        for node in dialogue.nodes.values():
            for option in node.options:
                grant_item_id = option.grant_item_id
                if grant_item_id is None:
                    continue
                option_location = (
                    f"对话 {dialogue.id} 节点 {node.id} 选项 {option.id}"
                )
                granted_item_options.setdefault(grant_item_id, []).append(
                    option_location
                )
                item = items.get(grant_item_id)
                if item is None:
                    validator.issues.append(
                        f"{option_location} 的 grant_item_id 引用了不存在的物品："
                        f"{grant_item_id}"
                    )
                    continue
                if item.heal_amount is not None:
                    validator.issues.append(
                        f"{option_location} 的 grant_item_id 不能引用消耗品："
                        f"{grant_item_id}"
                    )
                if grant_item_id in item_placements:
                    validator.issues.append(
                        f"{option_location} 的 grant_item_id 物品已放置在房间 "
                        f"{item_placements[grant_item_id]}：{grant_item_id}"
                    )
    for item_id, option_locations in granted_item_options.items():
        if len(option_locations) > 1:
            validator.issues.append(
                f"物品 {item_id} 被多个对话选项奖励：{option_locations}"
            )
    # Track quest→monster mapping for duplicate target check
    quest_target_map: dict[str, list[str]] = {}
    for quest in quests.values():
        if quest.trigger_room_id not in rooms:
            validator.issues.append(
                f"任务 {quest.id} 的 trigger_room_id 引用了不存在的房间："
                f"{quest.trigger_room_id}"
            )
        if quest.target_monster_id not in monsters:
            validator.issues.append(
                f"任务 {quest.id} 的 target_monster_id 引用了不存在的怪物："
                f"{quest.target_monster_id}"
            )
        quest_target_map.setdefault(quest.target_monster_id, []).append(quest.id)
    for monster_id, quest_ids in quest_target_map.items():
        if len(quest_ids) > 1:
            validator.issues.append(
                f"怪物 {monster_id} 被多个任务作为目标：{sorted(quest_ids)}"
            )

    if validator.issues:
        raise ContentValidationError(validator.issues)

    extensions = pack_data.get("extensions", {})
    if not isinstance(extensions, dict):
        raise ContentValidationError(["pack.json.extensions 必须是对象"])

    return ContentPack(
        id=pack_id,
        name=pack_name,
        version=version,
        start_room_id=start_room_id,
        player=player,
        rooms=rooms,
        items=items,
        monsters=monsters,
        characters=characters,
        quests=quests,
        dialogues=dialogues,
        extensions=extensions,
    )


def validate_content_pack(path: str | Path) -> tuple[str, ...]:
    """Validate a pack and return no issues, or raise with all found issues."""

    load_content_pack(path)
    return ()
