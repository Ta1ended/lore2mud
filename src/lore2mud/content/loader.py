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
        exits: dict[str, str] = {}
        for direction, target in raw_exits.items():
            if (
                not isinstance(direction, str)
                or not direction
                or not isinstance(target, str)
                or not target
            ):
                validator.issues.append(
                    f"{location}.exits 的方向和目标必须是非空字符串"
                )
                continue
            exits[direction.casefold()] = target
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
    for index, obj in enumerate(
        _load_entity_array(root, "items.json", validator)
    ):
        location = f"items.json[{index}]"
        validator.keys(
            obj,
            {
                "id",
                "name",
                "description",
                "canon_ref",
                "adaptation_notes",
            },
            location,
        )
        entity_id = validator.stable_id(
            validator.text(obj, "id", location),
            f"{location}.id",
        )
        item_defs.append(
            ItemDefinition(
                id=entity_id,
                name=validator.text(obj, "name", location),
                description=validator.text(obj, "description", location),
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
                "canon_ref",
                "adaptation_notes",
            },
            location,
        )
        entity_id = validator.stable_id(
            validator.text(obj, "id", location),
            f"{location}.id",
        )
        quest_defs.append(
            QuestDefinition(
                id=entity_id,
                name=validator.text(obj, "name", location),
                description=validator.text(obj, "description", location),
                metadata=_metadata(obj, location, validator),
            )
        )

    rooms = _unique_map(room_defs, "rooms.json", validator)
    items = _unique_map(item_defs, "items.json", validator)
    monsters = _unique_map(monster_defs, "monsters.json", validator)
    characters = _unique_map(character_defs, "characters.json", validator)
    quests = _unique_map(quest_defs, "quests.json", validator)

    if start_room_id and start_room_id not in rooms:
        validator.issues.append(
            f"pack.json.start_room_id 引用了不存在的房间：{start_room_id}"
        )

    item_placements: dict[str, str] = {}
    monster_placements: dict[str, str] = {}
    for room in rooms.values():
        for direction, target_id in room.exits.items():
            if target_id not in rooms:
                validator.issues.append(
                    f"房间 {room.id} 的出口 {direction} 引用了不存在的房间："
                    f"{target_id}"
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
        extensions=extensions,
    )


def validate_content_pack(path: str | Path) -> tuple[str, ...]:
    """Validate a pack and return no issues, or raise with all found issues."""

    load_content_pack(path)
    return ()
