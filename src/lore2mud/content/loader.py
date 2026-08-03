"""Load JSON content packs and reject malformed or dangling references."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from lore2mud.content.models import (
    AcceptQuestEffect,
    ActorViewDefinition,
    AdjustNarrativeStateEffect,
    AdvanceObjectiveEffect,
    AdvanceSceneEffect,
    CampaignActionDefinition,
    CampaignDefinition,
    CampaignEffect,
    CanonReference,
    CharacterDefinition,
    ConditionalText,
    ContentMetadata,
    ContentPack,
    CorrectKnowledgeEffect,
    DialogueDefinition,
    DialogueEffect,
    DialogueNodeViewDefinition,
    DialogueNode,
    DialogueOption,
    DialogueViewDefinition,
    ExitDefinition,
    CollectItemQuestDefinition,
    GrantExperienceEffect,
    GrantItemEffect,
    InteractableDefinition,
    ItemDefinition,
    ItemStackDefinition,
    KnowledgeDefinition,
    LocationViewDefinition,
    LogEntryDefinition,
    MonsterDefeatedQuestDefinition,
    MonsterDefinition,
    MoveActorEffect,
    ObjectiveDefinition,
    PlayerDefaults,
    QuestDefinition,
    ReachRoomQuestDefinition,
    RemoveItemEffect,
    RetractKnowledgeEffect,
    RevealKnowledgeEffect,
    RoomDefinition,
    SceneDefinition,
    SceneStageDefinition,
    SetNarrativeStateEffect,
    SetFlagEffect,
    ShopDefinition,
    ShopListingDefinition,
)
from lore2mud.narrative.models import (
    AllCondition,
    AnyCondition,
    AtLocationCondition,
    BoolStateDefinition,
    EnumStateDefinition,
    HasItemCondition,
    IntStateDefinition,
    NarrativeCondition,
    NarrativeStateDefinition,
    NarrativeValue,
    NotCondition,
    QuestStatusCondition,
    StateCompareCondition,
    StateEqualsCondition,
    narrative_value_is_valid,
)

STABLE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
ENTITY_FILES = (
    "rooms.json",
    "items.json",
    "monsters.json",
    "characters.json",
    "quests.json",
    "dialogues.json",
    "shops.json",
)
NARRATIVE_STATE_FILE = "narrative_state.json"
NARRATIVE_STATE_FORMAT_VERSION = 1
CAMPAIGN_FILE = "campaign.json"
CAMPAIGN_FORMAT_VERSION = 1
MAX_CONDITION_DEPTH = 16
MAX_CONDITION_NODES = 256


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


def _unique_attribute_map(
    definitions: list[Any],
    attribute: str,
    filename: str,
    validator: _Validator,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for definition in definitions:
        entity_id = getattr(definition, attribute)
        if entity_id in result:
            validator.issues.append(f"{filename} 包含重复 ID：{entity_id}")
        elif entity_id:
            result[entity_id] = definition
    return result


def _signed_integer(
    value: object,
    location: str,
    validator: _Validator,
) -> int | None:
    if not isinstance(value, int) or isinstance(value, bool):
        validator.issues.append(f"{location} 必须是整数")
        return None
    return value


def _load_narrative_state_definitions(
    root: Path,
    validator: _Validator,
) -> dict[str, NarrativeStateDefinition]:
    path = root / NARRATIVE_STATE_FILE
    if not path.exists():
        return {}
    try:
        raw = _read_json(path)
    except ContentValidationError as exc:
        validator.issues.extend(exc.issues)
        return {}

    document = validator.object(raw, NARRATIVE_STATE_FILE)
    validator.keys(
        document,
        {"format_version", "states"},
        NARRATIVE_STATE_FILE,
    )
    raw_version = document.get("format_version")
    if (
        not isinstance(raw_version, int)
        or isinstance(raw_version, bool)
        or raw_version != NARRATIVE_STATE_FORMAT_VERSION
    ):
        validator.issues.append(
            f"{NARRATIVE_STATE_FILE}.format_version 必须是 "
            f"{NARRATIVE_STATE_FORMAT_VERSION}"
        )

    if "states" not in document:
        validator.issues.append(f"{NARRATIVE_STATE_FILE}.states 是必填字段")
        raw_states: list[Any] = []
    else:
        raw_states = validator.array(
            document["states"], f"{NARRATIVE_STATE_FILE}.states"
        )

    definitions: list[NarrativeStateDefinition] = []
    for index, raw_definition in enumerate(raw_states):
        location = f"{NARRATIVE_STATE_FILE}.states[{index}]"
        obj = validator.object(raw_definition, location)
        raw_kind = obj.get("kind")
        state_id = validator.stable_id(
            validator.text(obj, "id", location), f"{location}.id"
        )

        if raw_kind == "bool":
            validator.keys(obj, {"id", "kind", "initial"}, location)
            raw_initial = obj.get("initial")
            if not isinstance(raw_initial, bool):
                validator.issues.append(f"{location}.initial 必须是布尔值")
                initial = False
            else:
                initial = raw_initial
            definitions.append(BoolStateDefinition(state_id, initial))
        elif raw_kind == "int":
            validator.keys(
                obj,
                {"id", "kind", "initial", "minimum", "maximum"},
                location,
            )
            initial = _signed_integer(
                obj.get("initial"), f"{location}.initial", validator
            )
            minimum = (
                _signed_integer(
                    obj["minimum"], f"{location}.minimum", validator
                )
                if "minimum" in obj
                else None
            )
            maximum = (
                _signed_integer(
                    obj["maximum"], f"{location}.maximum", validator
                )
                if "maximum" in obj
                else None
            )
            if minimum is not None and maximum is not None and minimum > maximum:
                validator.issues.append(
                    f"{location}.minimum 不得大于 maximum"
                )
            definition = IntStateDefinition(
                state_id,
                0 if initial is None else initial,
                minimum,
                maximum,
            )
            if initial is not None and not narrative_value_is_valid(
                definition, initial
            ):
                validator.issues.append(
                    f"{location}.initial 必须在声明的整数范围内"
                )
            definitions.append(definition)
        elif raw_kind == "enum":
            validator.keys(
                obj, {"id", "kind", "initial", "values"}, location
            )
            values = validator.string_list(
                obj.get("values"), f"{location}.values"
            )
            if not values:
                validator.issues.append(f"{location}.values 至少需要一个值")
            for value_index, value in enumerate(values):
                validator.stable_id(
                    value, f"{location}.values[{value_index}]"
                )
            initial = validator.stable_id(
                validator.text(obj, "initial", location),
                f"{location}.initial",
            )
            if initial and initial not in values:
                validator.issues.append(
                    f"{location}.initial 必须是 values 中的一个值"
                )
            definitions.append(EnumStateDefinition(state_id, initial, values))
        else:
            validator.keys(obj, {"id", "kind"}, location)
            validator.issues.append(
                f"{location}.kind 必须是 bool、int 或 enum"
            )

    return _unique_map(definitions, NARRATIVE_STATE_FILE, validator)


def _condition_value(
    raw: object,
    location: str,
    validator: _Validator,
) -> NarrativeValue:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str):
        return raw
    validator.issues.append(f"{location} 必须是布尔值、整数或字符串")
    return False


def _parse_narrative_condition(
    raw: object,
    location: str,
    validator: _Validator,
    *,
    state_defs: dict[str, NarrativeStateDefinition],
    rooms: dict[str, RoomDefinition],
    items: dict[str, ItemDefinition],
    quests: dict[str, QuestDefinition],
    depth: int,
    node_count: list[int],
) -> NarrativeCondition:
    node_count[0] += 1
    if depth > MAX_CONDITION_DEPTH:
        validator.issues.append(
            f"{location} 超过条件最大深度 {MAX_CONDITION_DEPTH}"
        )
        return AllCondition(())
    if node_count[0] > MAX_CONDITION_NODES:
        validator.issues.append(
            f"{location} 超过条件最大节点数 {MAX_CONDITION_NODES}"
        )
        return AllCondition(())

    obj = validator.object(raw, location)
    raw_kind = obj.get("kind")
    if raw_kind == "state_equals":
        validator.keys(obj, {"kind", "state_id", "value"}, location)
        state_id = validator.stable_id(
            validator.text(obj, "state_id", location),
            f"{location}.state_id",
        )
        value = _condition_value(obj.get("value"), f"{location}.value", validator)
        definition = state_defs.get(state_id)
        if definition is None:
            validator.issues.append(
                f"{location}.state_id 引用了不存在的叙事状态：{state_id}"
            )
        elif not narrative_value_is_valid(definition, value):
            validator.issues.append(
                f"{location}.value 不符合状态 {state_id} 的类型或值域"
            )
        return StateEqualsCondition(state_id, value)

    if raw_kind == "state_compare":
        validator.keys(
            obj, {"kind", "state_id", "operator", "value"}, location
        )
        state_id = validator.stable_id(
            validator.text(obj, "state_id", location),
            f"{location}.state_id",
        )
        raw_operator = obj.get("operator")
        if raw_operator not in {"lt", "lte", "gt", "gte"}:
            validator.issues.append(
                f"{location}.operator 必须是 lt、lte、gt 或 gte"
            )
            operator = "lt"
        else:
            operator = raw_operator
        value = _signed_integer(
            obj.get("value"), f"{location}.value", validator
        )
        definition = state_defs.get(state_id)
        if not isinstance(definition, IntStateDefinition):
            validator.issues.append(
                f"{location}.state_id 必须引用 int 叙事状态：{state_id}"
            )
        elif value is not None and not narrative_value_is_valid(definition, value):
            validator.issues.append(
                f"{location}.value 必须在状态 {state_id} 的整数范围内"
            )
        return StateCompareCondition(state_id, operator, 0 if value is None else value)

    if raw_kind == "has_item":
        validator.keys(obj, {"kind", "item_id", "quantity"}, location)
        item_id = validator.stable_id(
            validator.text(obj, "item_id", location), f"{location}.item_id"
        )
        quantity = validator.integer(
            obj, "quantity", location, minimum=1, default=1
        )
        item = items.get(item_id)
        if item is None:
            validator.issues.append(
                f"{location}.item_id 引用了不存在的物品：{item_id}"
            )
        elif quantity > item.stack_limit:
            validator.issues.append(
                f"{location}.quantity {quantity} 超过物品 {item_id} 的栈上限 "
                f"({item.stack_limit})"
            )
        return HasItemCondition(item_id, quantity)

    if raw_kind == "at_location":
        validator.keys(obj, {"kind", "location_id"}, location)
        location_id = validator.stable_id(
            validator.text(obj, "location_id", location),
            f"{location}.location_id",
        )
        if location_id not in rooms:
            validator.issues.append(
                f"{location}.location_id 引用了不存在的房间：{location_id}"
            )
        return AtLocationCondition(location_id)

    if raw_kind == "quest_status":
        validator.keys(obj, {"kind", "quest_id", "status"}, location)
        quest_id = validator.stable_id(
            validator.text(obj, "quest_id", location),
            f"{location}.quest_id",
        )
        if quest_id not in quests:
            validator.issues.append(
                f"{location}.quest_id 引用了不存在的任务：{quest_id}"
            )
        raw_status = obj.get("status")
        if raw_status not in {"not_accepted", "active", "completed"}:
            validator.issues.append(
                f"{location}.status 必须是 not_accepted、active 或 completed"
            )
            status = "not_accepted"
        else:
            status = raw_status
        return QuestStatusCondition(quest_id, status)

    if raw_kind in {"all", "any"}:
        validator.keys(obj, {"kind", "conditions"}, location)
        raw_children = validator.array(
            obj.get("conditions"), f"{location}.conditions"
        )
        if not raw_children:
            validator.issues.append(f"{location}.conditions 至少需要一个条件")
        children = tuple(
            _parse_narrative_condition(
                child,
                f"{location}.conditions[{index}]",
                validator,
                state_defs=state_defs,
                rooms=rooms,
                items=items,
                quests=quests,
                depth=depth + 1,
                node_count=node_count,
            )
            for index, child in enumerate(raw_children)
        )
        return AllCondition(children) if raw_kind == "all" else AnyCondition(children)

    if raw_kind == "not":
        validator.keys(obj, {"kind", "condition"}, location)
        child = _parse_narrative_condition(
            obj.get("condition"),
            f"{location}.condition",
            validator,
            state_defs=state_defs,
            rooms=rooms,
            items=items,
            quests=quests,
            depth=depth + 1,
            node_count=node_count,
        )
        return NotCondition(child)

    validator.keys(obj, {"kind"}, location)
    validator.issues.append(
        f"{location}.kind 必须是 state_equals、state_compare、has_item、"
        "at_location、quest_status、all、any 或 not"
    )
    return AllCondition(())


def _campaign_condition(
    raw: object,
    location: str,
    validator: _Validator,
    *,
    state_defs: dict[str, NarrativeStateDefinition],
    rooms: dict[str, RoomDefinition],
    items: dict[str, ItemDefinition],
    quests: dict[str, QuestDefinition],
) -> NarrativeCondition:
    return _parse_narrative_condition(
        raw,
        location,
        validator,
        state_defs=state_defs,
        rooms=rooms,
        items=items,
        quests=quests,
        depth=1,
        node_count=[0],
    )


def _conditional_texts(
    raw: object,
    location: str,
    validator: _Validator,
    *,
    state_defs: dict[str, NarrativeStateDefinition],
    rooms: dict[str, RoomDefinition],
    items: dict[str, ItemDefinition],
    quests: dict[str, QuestDefinition],
    required: bool,
) -> tuple[ConditionalText, ...]:
    values = validator.array(raw, location)
    if required and not values:
        validator.issues.append(f"{location} 至少需要一个文本投影")
    result: list[ConditionalText] = []
    unconditional = 0
    for index, raw_value in enumerate(values):
        entry_location = f"{location}[{index}]"
        obj = validator.object(raw_value, entry_location)
        validator.keys(obj, {"text", "condition"}, entry_location)
        condition = None
        if "condition" in obj:
            condition = _campaign_condition(
                obj["condition"],
                f"{entry_location}.condition",
                validator,
                state_defs=state_defs,
                rooms=rooms,
                items=items,
                quests=quests,
            )
        else:
            unconditional += 1
        result.append(
            ConditionalText(
                text=validator.text(obj, "text", entry_location),
                condition=condition,
            )
        )
    if result and unconditional != 1:
        validator.issues.append(f"{location} 必须恰有一个无条件回退文本")
    return tuple(result)


def _optional_campaign_condition(
    obj: dict[str, Any],
    location: str,
    validator: _Validator,
    *,
    state_defs: dict[str, NarrativeStateDefinition],
    rooms: dict[str, RoomDefinition],
    items: dict[str, ItemDefinition],
    quests: dict[str, QuestDefinition],
) -> NarrativeCondition | None:
    if "condition" not in obj:
        return None
    return _campaign_condition(
        obj["condition"],
        f"{location}.condition",
        validator,
        state_defs=state_defs,
        rooms=rooms,
        items=items,
        quests=quests,
    )


def _parse_campaign_effect(
    raw: object,
    location: str,
    validator: _Validator,
    *,
    state_defs: dict[str, NarrativeStateDefinition],
    rooms: dict[str, RoomDefinition],
    items: dict[str, ItemDefinition],
    characters: dict[str, CharacterDefinition],
    quests: dict[str, QuestDefinition],
    scenes: dict[str, SceneDefinition],
    objectives: dict[str, ObjectiveDefinition],
    knowledge: dict[str, KnowledgeDefinition],
) -> CampaignEffect:
    obj = validator.object(raw, location)
    kind = obj.get("kind")
    if kind == "grant_item":
        validator.keys(obj, {"kind", "item_id", "quantity"}, location)
        item_id = validator.stable_id(
            validator.text(obj, "item_id", location), f"{location}.item_id"
        )
        quantity = validator.integer(obj, "quantity", location, minimum=1, default=1)
        item = items.get(item_id)
        if item is None:
            validator.issues.append(
                f"{location}.item_id 引用了不存在的物品：{item_id}"
            )
        elif quantity > item.stack_limit:
            validator.issues.append(
                f"{location}.quantity {quantity} 超过物品 {item_id} 的栈上限 "
                f"({item.stack_limit})"
            )
        return GrantItemEffect(item_id, quantity)
    if kind == "grant_experience":
        validator.keys(obj, {"kind", "amount"}, location)
        return GrantExperienceEffect(
            validator.integer(obj, "amount", location, minimum=1, default=1)
        )
    if kind == "accept_quest":
        validator.keys(obj, {"kind", "quest_id"}, location)
        quest_id = validator.stable_id(
            validator.text(obj, "quest_id", location), f"{location}.quest_id"
        )
        if quest_id not in quests:
            validator.issues.append(
                f"{location}.quest_id 引用了不存在的任务：{quest_id}"
            )
        return AcceptQuestEffect(quest_id)
    if kind == "set_flag":
        validator.keys(obj, {"kind", "flag_id", "value"}, location)
        flag_id = validator.stable_id(
            validator.text(obj, "flag_id", location), f"{location}.flag_id"
        )
        raw_value = obj.get("value")
        if not isinstance(raw_value, bool):
            validator.issues.append(f"{location}.value 必须是布尔值")
            raw_value = False
        return SetFlagEffect(flag_id, raw_value)
    if kind == "set_narrative_state":
        validator.keys(obj, {"kind", "state_id", "value"}, location)
        state_id = validator.stable_id(
            validator.text(obj, "state_id", location), f"{location}.state_id"
        )
        value = _condition_value(obj.get("value"), f"{location}.value", validator)
        definition = state_defs.get(state_id)
        if definition is None:
            validator.issues.append(
                f"{location}.state_id 引用了不存在的叙事状态：{state_id}"
            )
        elif not narrative_value_is_valid(definition, value):
            validator.issues.append(
                f"{location}.value 不符合状态 {state_id} 的类型或值域"
            )
        return SetNarrativeStateEffect(state_id, value)
    if kind == "adjust_narrative_state":
        validator.keys(obj, {"kind", "state_id", "amount"}, location)
        state_id = validator.stable_id(
            validator.text(obj, "state_id", location), f"{location}.state_id"
        )
        amount = _signed_integer(obj.get("amount"), f"{location}.amount", validator)
        if amount == 0:
            validator.issues.append(f"{location}.amount 不能为 0")
        if not isinstance(state_defs.get(state_id), IntStateDefinition):
            validator.issues.append(
                f"{location}.state_id 必须引用 int 叙事状态：{state_id}"
            )
        return AdjustNarrativeStateEffect(state_id, 0 if amount is None else amount)
    if kind == "remove_item":
        validator.keys(obj, {"kind", "item_id", "quantity"}, location)
        item_id = validator.stable_id(
            validator.text(obj, "item_id", location), f"{location}.item_id"
        )
        quantity = validator.integer(obj, "quantity", location, minimum=1, default=1)
        if item_id not in items:
            validator.issues.append(
                f"{location}.item_id 引用了不存在的物品：{item_id}"
            )
        return RemoveItemEffect(item_id, quantity)
    if kind == "move_actor":
        allowed = {"kind", "actor_id", "location_id", "presence", "enabled", "incapacitated"}
        validator.keys(obj, allowed, location)
        actor_id = validator.stable_id(
            validator.text(obj, "actor_id", location), f"{location}.actor_id"
        )
        if actor_id not in characters:
            validator.issues.append(
                f"{location}.actor_id 引用了不存在的角色：{actor_id}"
            )
        location_id = None
        if "location_id" in obj:
            location_id = validator.stable_id(
                validator.text(obj, "location_id", location),
                f"{location}.location_id",
            )
            if location_id not in rooms:
                validator.issues.append(
                    f"{location}.location_id 引用了不存在的房间：{location_id}"
                )
        presence = obj.get("presence")
        if presence is not None and presence not in {"present", "absent"}:
            validator.issues.append(f"{location}.presence 必须是 present 或 absent")
            presence = None
        optional_bools: dict[str, bool | None] = {}
        for key in ("enabled", "incapacitated"):
            raw_bool = obj.get(key)
            if key in obj and not isinstance(raw_bool, bool):
                validator.issues.append(f"{location}.{key} 必须是布尔值")
                raw_bool = None
            optional_bools[key] = raw_bool
        if not any(key in obj for key in allowed - {"kind", "actor_id"}):
            validator.issues.append(f"{location} 至少需要一个 actor 状态变更字段")
        return MoveActorEffect(
            actor_id,
            location_id,
            presence,
            optional_bools["enabled"],
            optional_bools["incapacitated"],
        )
    if kind == "advance_scene":
        validator.keys(obj, {"kind", "scene_id", "transition"}, location)
        scene_id = validator.stable_id(
            validator.text(obj, "scene_id", location), f"{location}.scene_id"
        )
        if scene_id not in scenes:
            validator.issues.append(
                f"{location}.scene_id 引用了不存在的场景：{scene_id}"
            )
        transition = obj.get("transition")
        if transition not in {"activate", "advance", "complete"}:
            validator.issues.append(
                f"{location}.transition 必须是 activate、advance 或 complete"
            )
            transition = "activate"
        return AdvanceSceneEffect(scene_id, transition)
    if kind == "advance_objective":
        validator.keys(obj, {"kind", "objective_id", "transition"}, location)
        objective_id = validator.stable_id(
            validator.text(obj, "objective_id", location),
            f"{location}.objective_id",
        )
        if objective_id not in objectives:
            validator.issues.append(
                f"{location}.objective_id 引用了不存在的目标：{objective_id}"
            )
        transition = obj.get("transition")
        if transition not in {"activate", "start", "complete", "fail"}:
            validator.issues.append(
                f"{location}.transition 必须是 activate、start、complete 或 fail"
            )
            transition = "activate"
        return AdvanceObjectiveEffect(objective_id, transition)
    if kind == "reveal_knowledge":
        validator.keys(obj, {"kind", "knowledge_id", "status"}, location)
        knowledge_id = validator.stable_id(
            validator.text(obj, "knowledge_id", location),
            f"{location}.knowledge_id",
        )
        if knowledge_id not in knowledge:
            validator.issues.append(
                f"{location}.knowledge_id 引用了不存在的知识：{knowledge_id}"
            )
        status = obj.get("status")
        if status not in {"heard", "suspected", "confirmed"}:
            validator.issues.append(
                f"{location}.status 必须是 heard、suspected 或 confirmed"
            )
            status = "heard"
        return RevealKnowledgeEffect(knowledge_id, status)
    if kind in {"retract_knowledge", "correct_knowledge"}:
        validator.keys(obj, {"kind", "knowledge_id"}, location)
        knowledge_id = validator.stable_id(
            validator.text(obj, "knowledge_id", location),
            f"{location}.knowledge_id",
        )
        if knowledge_id not in knowledge:
            validator.issues.append(
                f"{location}.knowledge_id 引用了不存在的知识：{knowledge_id}"
            )
        if kind == "retract_knowledge":
            return RetractKnowledgeEffect(knowledge_id)
        return CorrectKnowledgeEffect(knowledge_id)
    validator.keys(obj, {"kind"}, location)
    validator.issues.append(f"{location}.kind 不是支持的 campaign effect")
    return SetFlagEffect("invalid_effect", False)


def _load_campaign_definition(
    root: Path,
    validator: _Validator,
    *,
    state_defs: dict[str, NarrativeStateDefinition],
    rooms: dict[str, RoomDefinition],
    items: dict[str, ItemDefinition],
    characters: dict[str, CharacterDefinition],
    quests: dict[str, QuestDefinition],
    dialogues: dict[str, DialogueDefinition],
) -> CampaignDefinition | None:
    path = root / CAMPAIGN_FILE
    if not path.exists():
        return None
    try:
        raw = _read_json(path)
    except ContentValidationError as exc:
        validator.issues.extend(exc.issues)
        return None
    document = validator.object(raw, CAMPAIGN_FILE)
    section_names = {
        "location_views",
        "actor_views",
        "dialogue_views",
        "scenes",
        "interactables",
        "actions",
        "objectives",
        "knowledge",
        "log_entries",
    }
    validator.keys(document, {"format_version"} | section_names, CAMPAIGN_FILE)
    version = document.get("format_version")
    if (
        not isinstance(version, int)
        or isinstance(version, bool)
        or version != CAMPAIGN_FORMAT_VERSION
    ):
        validator.issues.append(
            f"{CAMPAIGN_FILE}.format_version 必须是 {CAMPAIGN_FORMAT_VERSION}"
        )
    for name in sorted(section_names):
        if name not in document:
            validator.issues.append(f"{CAMPAIGN_FILE}.{name} 是必填字段")

    condition_args = {
        "state_defs": state_defs,
        "rooms": rooms,
        "items": items,
        "quests": quests,
    }

    location_view_values: list[LocationViewDefinition] = []
    for index, raw_view in enumerate(
        validator.array(document.get("location_views"), f"{CAMPAIGN_FILE}.location_views")
    ):
        location = f"{CAMPAIGN_FILE}.location_views[{index}]"
        obj = validator.object(raw_view, location)
        validator.keys(obj, {"location_id", "descriptions", "exits"}, location)

        if "descriptions" not in obj:
            validator.issues.append(f"{location}.descriptions 是必填字段")
        if "exits" not in obj:
            validator.issues.append(f"{location}.exits 是必填字段")
        location_id = validator.stable_id(
            validator.text(obj, "location_id", location), f"{location}.location_id"
        )
        if location_id not in rooms:
            validator.issues.append(
                f"{location}.location_id 引用了不存在的房间：{location_id}"
            )
        descriptions = _conditional_texts(
            obj.get("descriptions", []),
            f"{location}.descriptions",
            validator,
            required=False,
            **condition_args,
        )
        exit_conditions: dict[str, NarrativeCondition] = {}
        for exit_index, raw_exit in enumerate(
            validator.array(obj.get("exits", []), f"{location}.exits")
        ):
            exit_location = f"{location}.exits[{exit_index}]"
            exit_obj = validator.object(raw_exit, exit_location)
            validator.keys(exit_obj, {"direction", "condition"}, exit_location)
            direction = validator.text(exit_obj, "direction", exit_location).casefold()
            if location_id in rooms and direction not in rooms[location_id].exits:
                validator.issues.append(
                    f"{exit_location}.direction 引用了不存在的出口：{direction}"
                )
            if direction in exit_conditions:
                validator.issues.append(
                    f"{location}.exits 包含重复方向：{direction}"
                )
            exit_conditions[direction] = _campaign_condition(
                exit_obj.get("condition"),
                f"{exit_location}.condition",
                validator,
                **condition_args,
            )
        location_view_values.append(
            LocationViewDefinition(location_id, descriptions, exit_conditions)
        )
    location_views = _unique_attribute_map(
        location_view_values, "location_id", CAMPAIGN_FILE, validator
    )

    actor_view_values: list[ActorViewDefinition] = []
    for index, raw_view in enumerate(
        validator.array(document.get("actor_views"), f"{CAMPAIGN_FILE}.actor_views")
    ):
        location = f"{CAMPAIGN_FILE}.actor_views[{index}]"
        obj = validator.object(raw_view, location)
        validator.keys(obj, {"actor_id", "descriptions", "condition"}, location)

        if "descriptions" not in obj:
            validator.issues.append(f"{location}.descriptions 是必填字段")
        actor_id = validator.stable_id(
            validator.text(obj, "actor_id", location), f"{location}.actor_id"
        )
        if actor_id not in characters:
            validator.issues.append(
                f"{location}.actor_id 引用了不存在的角色：{actor_id}"
            )
        actor_view_values.append(
            ActorViewDefinition(
                actor_id,
                _conditional_texts(
                    obj.get("descriptions", []),
                    f"{location}.descriptions",
                    validator,
                    required=False,
                    **condition_args,
                ),
                _optional_campaign_condition(obj, location, validator, **condition_args),
            )
        )
    actor_views = _unique_attribute_map(
        actor_view_values, "actor_id", CAMPAIGN_FILE, validator
    )

    dialogue_view_values: list[DialogueViewDefinition] = []
    for index, raw_view in enumerate(
        validator.array(document.get("dialogue_views"), f"{CAMPAIGN_FILE}.dialogue_views")
    ):
        location = f"{CAMPAIGN_FILE}.dialogue_views[{index}]"
        obj = validator.object(raw_view, location)
        validator.keys(obj, {"dialogue_id", "nodes"}, location)
        dialogue_id = validator.stable_id(
            validator.text(obj, "dialogue_id", location), f"{location}.dialogue_id"
        )
        dialogue = dialogues.get(dialogue_id)
        if dialogue is None:
            validator.issues.append(
                f"{location}.dialogue_id 引用了不存在的对话：{dialogue_id}"
            )
        node_values: list[DialogueNodeViewDefinition] = []
        raw_nodes = validator.array(obj.get("nodes"), f"{location}.nodes")
        if not raw_nodes:
            validator.issues.append(f"{location}.nodes 不能为空")
        for node_index, raw_node in enumerate(raw_nodes):
            node_location = f"{location}.nodes[{node_index}]"
            node_obj = validator.object(raw_node, node_location)
            validator.keys(node_obj, {"node_id", "texts"}, node_location)
            node_id = validator.stable_id(
                validator.text(node_obj, "node_id", node_location),
                f"{node_location}.node_id",
            )
            if dialogue is not None and node_id not in dialogue.nodes:
                validator.issues.append(
                    f"{node_location}.node_id 引用了不存在的节点：{node_id}"
                )
            node_values.append(
                DialogueNodeViewDefinition(
                    node_id,
                    _conditional_texts(
                        node_obj.get("texts"),
                        f"{node_location}.texts",
                        validator,
                        required=True,
                        **condition_args,
                    ),
                )
            )
        dialogue_view_values.append(
            DialogueViewDefinition(
                dialogue_id,
                _unique_attribute_map(
                    node_values, "node_id", CAMPAIGN_FILE, validator
                ),
            )
        )
    dialogue_views = _unique_attribute_map(
        dialogue_view_values, "dialogue_id", CAMPAIGN_FILE, validator
    )

    objective_values: list[ObjectiveDefinition] = []
    for index, raw_objective in enumerate(
        validator.array(document.get("objectives"), f"{CAMPAIGN_FILE}.objectives")
    ):
        location = f"{CAMPAIGN_FILE}.objectives[{index}]"
        obj = validator.object(raw_objective, location)
        validator.keys(
            obj,
            {"id", "title", "description", "initial_status", "dependency_ids", "exclusive_with"},
            location,
        )

        if "initial_status" not in obj:
            validator.issues.append(f"{location}.initial_status 是必填字段")
        if "dependency_ids" not in obj:
            validator.issues.append(f"{location}.dependency_ids 是必填字段")
        if "exclusive_with" not in obj:
            validator.issues.append(f"{location}.exclusive_with 是必填字段")
        objective_id = validator.stable_id(
            validator.text(obj, "id", location), f"{location}.id"
        )
        initial_status = obj.get("initial_status", "inactive")
        if initial_status not in {"inactive", "active"}:
            validator.issues.append(
                f"{location}.initial_status 必须是 inactive 或 active"
            )
            initial_status = "inactive"
        dependencies = validator.string_list(
            obj.get("dependency_ids", []), f"{location}.dependency_ids"
        )
        exclusive = validator.string_list(
            obj.get("exclusive_with", []), f"{location}.exclusive_with"
        )
        for value_index, value in enumerate(dependencies):
            validator.stable_id(value, f"{location}.dependency_ids[{value_index}]")
        for value_index, value in enumerate(exclusive):
            validator.stable_id(value, f"{location}.exclusive_with[{value_index}]")
        if objective_id in set(dependencies) | set(exclusive):
            validator.issues.append(f"{location} 不能引用自身")
        if initial_status == "active" and dependencies:
            validator.issues.append(
                f"{location} 初始 active 目标不能声明依赖"
            )
        objective_values.append(
            ObjectiveDefinition(
                objective_id,
                validator.text(obj, "title", location),
                validator.text(obj, "description", location),
                initial_status,
                dependencies,
                exclusive,
            )
        )
    objectives = _unique_map(objective_values, CAMPAIGN_FILE, validator)

    knowledge_values: list[KnowledgeDefinition] = []
    knowledge_statuses = {"unknown", "heard", "suspected", "confirmed", "retracted", "corrected"}
    visible_knowledge_statuses = knowledge_statuses - {"unknown"}
    for index, raw_knowledge in enumerate(
        validator.array(document.get("knowledge"), f"{CAMPAIGN_FILE}.knowledge")
    ):
        location = f"{CAMPAIGN_FILE}.knowledge[{index}]"
        obj = validator.object(raw_knowledge, location)
        validator.keys(obj, {"id", "title", "initial_status", "texts"}, location)

        if "initial_status" not in obj:
            validator.issues.append(f"{location}.initial_status 是必填字段")
        knowledge_id = validator.stable_id(
            validator.text(obj, "id", location), f"{location}.id"
        )
        initial_status = obj.get("initial_status", "unknown")
        if initial_status not in knowledge_statuses:
            validator.issues.append(f"{location}.initial_status 不是支持的知识状态")
            initial_status = "unknown"
        raw_texts = validator.object(obj.get("texts"), f"{location}.texts")
        validator.keys(raw_texts, visible_knowledge_statuses, f"{location}.texts")
        texts: dict[str, str] = {}
        for status in sorted(visible_knowledge_statuses):
            texts[status] = validator.text(raw_texts, status, f"{location}.texts")
        knowledge_values.append(
            KnowledgeDefinition(
                knowledge_id,
                validator.text(obj, "title", location),
                texts,
                initial_status,
            )
        )
    knowledge = _unique_map(knowledge_values, CAMPAIGN_FILE, validator)

    scene_values: list[SceneDefinition] = []
    for index, raw_scene in enumerate(
        validator.array(document.get("scenes"), f"{CAMPAIGN_FILE}.scenes")
    ):
        location = f"{CAMPAIGN_FILE}.scenes[{index}]"
        obj = validator.object(raw_scene, location)
        validator.keys(
            obj, {"id", "name", "location_id", "initial_status", "condition", "stages"}, location
        )

        if "initial_status" not in obj:
            validator.issues.append(f"{location}.initial_status 是必填字段")
        scene_id = validator.stable_id(
            validator.text(obj, "id", location), f"{location}.id"
        )
        location_id = validator.stable_id(
            validator.text(obj, "location_id", location), f"{location}.location_id"
        )
        if location_id not in rooms:
            validator.issues.append(
                f"{location}.location_id 引用了不存在的房间：{location_id}"
            )
        initial_status = obj.get("initial_status", "inactive")
        if initial_status not in {"inactive", "active"}:
            validator.issues.append(
                f"{location}.initial_status 必须是 inactive 或 active"
            )
            initial_status = "inactive"
        stage_values: list[SceneStageDefinition] = []
        for stage_index, raw_stage in enumerate(
            validator.array(obj.get("stages"), f"{location}.stages")
        ):
            stage_location = f"{location}.stages[{stage_index}]"
            stage_obj = validator.object(raw_stage, stage_location)
            validator.keys(
                stage_obj, {"id", "descriptions", "interactable_ids"}, stage_location
            )
            stage_id = validator.stable_id(
                validator.text(stage_obj, "id", stage_location), f"{stage_location}.id"
            )
            stage_values.append(
                SceneStageDefinition(
                    stage_id,
                    _conditional_texts(
                        stage_obj.get("descriptions"),
                        f"{stage_location}.descriptions",
                        validator,
                        required=True,
                        **condition_args,
                    ),
                    validator.string_list(
                        stage_obj.get("interactable_ids"),
                        f"{stage_location}.interactable_ids",
                    ),
                )
            )
        if not stage_values:
            validator.issues.append(f"{location}.stages 至少需要一个阶段")
        stage_map = _unique_map(stage_values, CAMPAIGN_FILE, validator)
        scene_values.append(
            SceneDefinition(
                scene_id,
                validator.text(obj, "name", location),
                location_id,
                tuple(stage_map.values()),
                initial_status,
                _optional_campaign_condition(obj, location, validator, **condition_args),
            )
        )
    scenes = _unique_map(scene_values, CAMPAIGN_FILE, validator)

    interactable_values: list[InteractableDefinition] = []
    for index, raw_interactable in enumerate(
        validator.array(document.get("interactables"), f"{CAMPAIGN_FILE}.interactables")
    ):
        location = f"{CAMPAIGN_FILE}.interactables[{index}]"
        obj = validator.object(raw_interactable, location)
        validator.keys(
            obj,
            {"id", "name", "kind", "target_id", "location_id", "scene_id", "action_ids", "descriptions", "condition"},
            location,
        )
        interactable_id = validator.stable_id(
            validator.text(obj, "id", location), f"{location}.id"
        )
        kind = obj.get("kind")
        if kind not in {"actor", "location", "object", "ritual", "inner"}:
            validator.issues.append(f"{location}.kind 不是支持的 interactable 类型")
            kind = "object"
        target_id = None
        if "target_id" in obj:
            target_id = validator.stable_id(
                validator.text(obj, "target_id", location), f"{location}.target_id"
            )
        location_id = None
        if "location_id" in obj:
            location_id = validator.stable_id(
                validator.text(obj, "location_id", location), f"{location}.location_id"
            )
            if location_id not in rooms:
                validator.issues.append(
                    f"{location}.location_id 引用了不存在的房间：{location_id}"
                )
        scene_id = None
        if "scene_id" in obj:
            scene_id = validator.stable_id(
                validator.text(obj, "scene_id", location), f"{location}.scene_id"
            )
            if scene_id not in scenes:
                validator.issues.append(
                    f"{location}.scene_id 引用了不存在的场景：{scene_id}"
                )
        if location_id is not None and scene_id is not None:
            validator.issues.append(
                f"{location} 不能同时指定 location_id 和 scene_id"
            )
        if kind == "actor":
            if target_id not in characters:
                validator.issues.append(
                    f"{location}.target_id 必须引用存在的角色"
                )
        elif kind == "location":
            if target_id not in rooms:
                validator.issues.append(
                    f"{location}.target_id 必须引用存在的房间"
                )
        elif kind == "object" and target_id is not None and target_id not in items:
            validator.issues.append(
                f"{location}.target_id 必须引用存在的物品或省略"
            )
        if kind in {"object", "ritual", "inner"} and location_id is None and scene_id is None:
            validator.issues.append(
                f"{location} 必须指定 location_id 或 scene_id"
            )
        action_ids = validator.string_list(
            obj.get("action_ids"), f"{location}.action_ids"
        )
        if not action_ids:
            validator.issues.append(f"{location}.action_ids 至少需要一个动作")
        interactable_values.append(
            InteractableDefinition(
                interactable_id,
                validator.text(obj, "name", location),
                kind,
                action_ids,
                _conditional_texts(
                    obj.get("descriptions"),
                    f"{location}.descriptions",
                    validator,
                    required=True,
                    **condition_args,
                ),
                target_id,
                location_id,
                scene_id,
                _optional_campaign_condition(obj, location, validator, **condition_args),
            )
        )
    interactables = _unique_map(interactable_values, CAMPAIGN_FILE, validator)

    action_values: list[CampaignActionDefinition] = []
    for index, raw_action in enumerate(
        validator.array(document.get("actions"), f"{CAMPAIGN_FILE}.actions")
    ):
        location = f"{CAMPAIGN_FILE}.actions[{index}]"
        obj = validator.object(raw_action, location)
        validator.keys(obj, {"id", "label", "result_text", "effects", "condition"}, location)
        action_id = validator.stable_id(
            validator.text(obj, "id", location), f"{location}.id"
        )
        raw_effects = validator.array(obj.get("effects"), f"{location}.effects")
        effects = tuple(
            _parse_campaign_effect(
                raw_effect,
                f"{location}.effects[{effect_index}]",
                validator,
                state_defs=state_defs,
                rooms=rooms,
                items=items,
                characters=characters,
                quests=quests,
                scenes=scenes,
                objectives=objectives,
                knowledge=knowledge,
            )
            for effect_index, raw_effect in enumerate(raw_effects)
        )
        action_values.append(
            CampaignActionDefinition(
                action_id,
                validator.text(obj, "label", location),
                validator.text(obj, "result_text", location),
                effects,
                _optional_campaign_condition(obj, location, validator, **condition_args),
            )
        )
    actions = _unique_map(action_values, CAMPAIGN_FILE, validator)

    log_values: list[LogEntryDefinition] = []
    for index, raw_log in enumerate(
        validator.array(document.get("log_entries"), f"{CAMPAIGN_FILE}.log_entries")
    ):
        location = f"{CAMPAIGN_FILE}.log_entries[{index}]"
        obj = validator.object(raw_log, location)
        validator.keys(obj, {"id", "category", "texts", "condition"}, location)
        log_id = validator.stable_id(
            validator.text(obj, "id", location), f"{location}.id"
        )
        category = obj.get("category")
        if category not in {"story", "objective", "knowledge"}:
            validator.issues.append(
                f"{location}.category 必须是 story、objective 或 knowledge"
            )
            category = "story"
        log_values.append(
            LogEntryDefinition(
                log_id,
                category,
                _conditional_texts(
                    obj.get("texts"),
                    f"{location}.texts",
                    validator,
                    required=True,
                    **condition_args,
                ),
                _optional_campaign_condition(obj, location, validator, **condition_args),
            )
        )
    log_entries = _unique_map(log_values, CAMPAIGN_FILE, validator)

    for objective in objectives.values():
        for dependency_id in objective.dependency_ids:
            if dependency_id not in objectives:
                validator.issues.append(
                    f"目标 {objective.id} 引用了不存在的依赖：{dependency_id}"
                )
        for exclusive_id in objective.exclusive_with:
            other = objectives.get(exclusive_id)
            if other is None:
                validator.issues.append(
                    f"目标 {objective.id} 引用了不存在的互斥目标：{exclusive_id}"
                )
            elif objective.id not in other.exclusive_with:
                validator.issues.append(
                    f"目标互斥必须对称声明：{objective.id} <-> {exclusive_id}"
                )
            elif objective.initial_status == other.initial_status == "active":
                validator.issues.append(
                    f"互斥目标不能同时初始 active：{objective.id}、{exclusive_id}"
                )

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit_objective(objective_id: str) -> None:
        if objective_id in visiting:
            validator.issues.append(f"目标依赖图包含环：{objective_id}")
            return
        if objective_id in visited or objective_id not in objectives:
            return
        visiting.add(objective_id)
        for dependency_id in objectives[objective_id].dependency_ids:
            visit_objective(dependency_id)
        visiting.remove(objective_id)
        visited.add(objective_id)

    for objective_id in sorted(objectives):
        visit_objective(objective_id)

    scene_interactable_ids: set[str] = set()
    for scene in scenes.values():
        for stage in scene.stages:
            for interactable_id in stage.interactable_ids:
                interactable = interactables.get(interactable_id)
                if interactable is None:
                    validator.issues.append(
                        f"场景 {scene.id} 阶段 {stage.id} 引用了不存在的 interactable："
                        f"{interactable_id}"
                    )
                elif interactable.scene_id != scene.id:
                    validator.issues.append(
                        f"interactable {interactable_id} 的 scene_id 与场景 {scene.id} 不一致"
                    )
                scene_interactable_ids.add(interactable_id)
    action_owners: dict[str, list[str]] = {}
    for interactable in interactables.values():
        if interactable.scene_id is not None and interactable.id not in scene_interactable_ids:
            validator.issues.append(
                f"场景 interactable {interactable.id} 未被任何阶段引用"
            )
        for action_id in interactable.action_ids:
            action_owners.setdefault(action_id, []).append(interactable.id)
            if action_id not in actions:
                validator.issues.append(
                    f"interactable {interactable.id} 引用了不存在的动作：{action_id}"
                )
    for action_id in sorted(actions):
        owners = action_owners.get(action_id, [])
        if len(owners) != 1:
            validator.issues.append(
                f"动作 {action_id} 必须恰属于一个 interactable，实际：{owners}"
            )

    return CampaignDefinition(
        location_views=location_views,
        actor_views=actor_views,
        dialogue_views=dialogue_views,
        scenes=scenes,
        interactables=interactables,
        actions=actions,
        objectives=objectives,
        knowledge=knowledge,
        log_entries=log_entries,
    )


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
        {"max_hp", "attack", "defense", "inventory_capacity", "coins"},
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
        coins=validator.integer(
            player_data,
            "coins",
            "pack.json.player",
            minimum=0,
            default=0,
        ),
    )

    narrative_state_defs = _load_narrative_state_definitions(root, validator)

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
                "item_stacks",
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
        item_stacks_raw = obj.get("item_stacks", [])
        item_stacks_list: list[ItemStackDefinition] = []
        if isinstance(item_stacks_raw, list):
            for si, stack_obj in enumerate(item_stacks_raw):
                sloc = f"{location}.item_stacks[{si}]"
                if not isinstance(stack_obj, dict):
                    validator.issues.append(f"{sloc} 必须是对象")
                    continue
                validator.keys(stack_obj, {"item_id", "quantity"}, sloc)
                sid_raw = stack_obj.get("item_id")
                if not isinstance(sid_raw, str) or not sid_raw.strip():
                    validator.issues.append(f"{sloc}.item_id 必须是非空字符串")
                    continue
                sid = validator.stable_id(sid_raw, f"{sloc}.item_id")
                sqty = validator.integer(
                    stack_obj, "quantity", sloc, minimum=1, default=1,
                )
                item_stacks_list.append(ItemStackDefinition(item_id=sid, quantity=sqty))
        else:
            validator.issues.append(f"{location}.item_stacks 必须是数组")

        room_defs.append(
            RoomDefinition(
                id=entity_id,
                name=validator.text(obj, "name", location),
                description=validator.text(obj, "description", location),
                exits=exits,
                item_stacks=tuple(item_stacks_list),
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
                "stack_limit",
                "droppable",
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
        # stack_limit: optional; default 1.
        stack_limit = 1
        if "stack_limit" in obj:
            stack_limit = validator.integer(
                obj, "stack_limit", location, minimum=1, default=1,
            )
        # Equipment items must have stack_limit == 1.
        if slot is not None and stack_limit != 1:
            validator.issues.append(
                f"{location}: 可装备物品的 stack_limit 必须为 1"
            )
        droppable = obj.get("droppable", True)
        if not isinstance(droppable, bool):
            validator.issues.append(f"{location}.droppable 必须是布尔值")
            droppable = True
        item_defs.append(
            ItemDefinition(
                id=entity_id,
                name=validator.text(obj, "name", location),
                description=validator.text(obj, "description", location),
                heal_amount=heal_amount,
                slot=slot,
                attack_bonus=attack_bonus,
                defense_bonus=defense_bonus,
                stack_limit=stack_limit,
                droppable=droppable,
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
                "loot_item",
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
        loot_item: ItemStackDefinition | None = None
        if "loot_item" in obj:
            raw_loot = obj["loot_item"]
            if isinstance(raw_loot, dict):
                loot_loc = f"{location}.loot_item"
                validator.keys(raw_loot, {"item_id", "quantity"}, loot_loc)
                loot_id_raw = raw_loot.get("item_id")
                if isinstance(loot_id_raw, str) and loot_id_raw.strip():
                    loot_id = validator.stable_id(loot_id_raw, f"{loot_loc}.item_id")
                    loot_qty = validator.integer(
                        raw_loot, "quantity", loot_loc, minimum=1, default=1,
                    )
                    loot_item = ItemStackDefinition(item_id=loot_id, quantity=loot_qty)
                else:
                    validator.issues.append(f"{loot_loc}.item_id 必须是非空字符串")
            elif raw_loot is not None:
                validator.issues.append(f"{location}.loot_item 必须是对象或省略")
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
                loot_item=loot_item,
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
    common_quest_keys = {
        "id",
        "name",
        "description",
        "kind",
        "trigger_room_id",
        "reward_experience",
        "canon_ref",
        "adaptation_notes",
    }
    for index, obj in enumerate(
        _load_entity_array(root, "quests.json", validator)
    ):
        location = f"quests.json[{index}]"
        kind = validator.text(obj, "kind", location)
        entity_id = validator.stable_id(
            validator.text(obj, "id", location),
            f"{location}.id",
        )
        trigger_room_id = validator.stable_id(
            validator.text(obj, "trigger_room_id", location),
            f"{location}.trigger_room_id",
        )
        reward_experience = validator.integer(
            obj,
            "reward_experience",
            location,
            minimum=0,
            default=0,
        )
        common = {
            "id": entity_id,
            "name": validator.text(obj, "name", location),
            "description": validator.text(obj, "description", location),
            "trigger_room_id": trigger_room_id,
            "reward_experience": reward_experience,
            "metadata": _metadata(obj, location, validator),
        }

        if kind == "monster_defeated":
            validator.keys(
                obj,
                common_quest_keys | {"target_monster_id"},
                location,
            )
            target_monster_id = validator.stable_id(
                validator.text(obj, "target_monster_id", location),
                f"{location}.target_monster_id",
            )
            quest_defs.append(
                MonsterDefeatedQuestDefinition(
                    **common,
                    target_monster_id=target_monster_id,
                )
            )
        elif kind == "reach_room":
            validator.keys(
                obj,
                common_quest_keys | {"target_room_id"},
                location,
            )
            target_room_id = validator.stable_id(
                validator.text(obj, "target_room_id", location),
                f"{location}.target_room_id",
            )
            quest_defs.append(
                ReachRoomQuestDefinition(
                    **common,
                    target_room_id=target_room_id,
                )
            )
        elif kind == "collect_item":
            validator.keys(
                obj,
                common_quest_keys | {"target_item_id", "required_quantity"},
                location,
            )
            target_item_id = validator.stable_id(
                validator.text(obj, "target_item_id", location),
                f"{location}.target_item_id",
            )
            required_quantity = validator.integer(
                obj,
                "required_quantity",
                location,
                minimum=1,
                default=1,
            )
            quest_defs.append(
                CollectItemQuestDefinition(
                    **common,
                    target_item_id=target_item_id,
                    required_quantity=required_quantity,
                )
            )
        else:
            validator.keys(obj, common_quest_keys, location)
            validator.issues.append(
                f"{location}.kind 必须是 monster_defeated、reach_room 或 collect_item"
            )

    rooms = _unique_map(room_defs, "rooms.json", validator)
    items = _unique_map(item_defs, "items.json", validator)
    monsters = _unique_map(monster_defs, "monsters.json", validator)
    characters = _unique_map(character_defs, "characters.json", validator)
    quests = _unique_map(quest_defs, "quests.json", validator)

    # --- dialogues ---
    dialogue_defs_list: list[DialogueDefinition] = []
    legacy_flag_ids: set[str] = set()
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
                    {"id", "text", "next_node_id", "effects", "condition"},
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
                if "effects" not in opt_obj:
                    validator.issues.append(f"{oloc} 缺少 effects 字段")
                    effects_raw: list[Any] = []
                else:
                    effects_raw = validator.array(
                        opt_obj["effects"], f"{oloc}.effects"
                    )

                effects: list[DialogueEffect] = []
                granted_item_ids: set[str] = set()
                accepted_quest_ids: set[str] = set()
                set_flag_ids: set[str] = set()
                grant_experience_count = 0
                for ei, effect_raw in enumerate(effects_raw):
                    eloc = f"{oloc}.effects[{ei}]"
                    effect_obj = validator.object(effect_raw, eloc)
                    raw_kind = effect_obj.get("kind")
                    if not isinstance(raw_kind, str) or not raw_kind:
                        validator.issues.append(f"{eloc}.kind 必须是非空字符串")
                        validator.keys(effect_obj, {"kind"}, eloc)
                        continue

                    if raw_kind == "grant_item":
                        validator.keys(
                            effect_obj, {"kind", "item_id", "quantity"}, eloc
                        )
                        item_id = validator.stable_id(
                            validator.text(effect_obj, "item_id", eloc),
                            f"{eloc}.item_id",
                        )
                        quantity = validator.integer(
                            effect_obj, "quantity", eloc, minimum=1, default=1
                        )
                        if item_id in granted_item_ids:
                            validator.issues.append(
                                f"{oloc}.effects 不得重复 grant_item.item_id：{item_id}"
                            )
                        granted_item_ids.add(item_id)
                        effects.append(GrantItemEffect(item_id, quantity))
                    elif raw_kind == "grant_experience":
                        validator.keys(effect_obj, {"kind", "amount"}, eloc)
                        amount = validator.integer(
                            effect_obj, "amount", eloc, minimum=1, default=1
                        )
                        grant_experience_count += 1
                        if grant_experience_count > 1:
                            validator.issues.append(
                                f"{oloc}.effects 最多只能有一个 grant_experience"
                            )
                        effects.append(GrantExperienceEffect(amount))
                    elif raw_kind == "accept_quest":
                        validator.keys(effect_obj, {"kind", "quest_id"}, eloc)
                        quest_id = validator.stable_id(
                            validator.text(effect_obj, "quest_id", eloc),
                            f"{eloc}.quest_id",
                        )
                        if quest_id in accepted_quest_ids:
                            validator.issues.append(
                                f"{oloc}.effects 不得重复 accept_quest.quest_id：{quest_id}"
                            )
                        accepted_quest_ids.add(quest_id)
                        effects.append(AcceptQuestEffect(quest_id))
                    elif raw_kind == "set_flag":
                        validator.keys(
                            effect_obj, {"kind", "flag_id", "value"}, eloc
                        )
                        flag_id = validator.stable_id(
                            validator.text(effect_obj, "flag_id", eloc),
                            f"{eloc}.flag_id",
                        )
                        raw_value = effect_obj.get("value")
                        if not isinstance(raw_value, bool):
                            validator.issues.append(
                                f"{eloc}.value 必须是布尔值"
                            )
                            value = False
                        else:
                            value = raw_value
                        if flag_id in set_flag_ids:
                            validator.issues.append(
                                f"{oloc}.effects 不得重复 set_flag.flag_id：{flag_id}"
                            )
                        set_flag_ids.add(flag_id)
                        legacy_flag_ids.add(flag_id)
                        effects.append(SetFlagEffect(flag_id, value))
                    else:
                        validator.keys(effect_obj, {"kind"}, eloc)
                        validator.issues.append(
                            f"{eloc}.kind 必须是 grant_item、grant_experience、"
                            "accept_quest 或 set_flag"
                        )
                condition: NarrativeCondition | None = None
                if "condition" in opt_obj:
                    condition = _parse_narrative_condition(
                        opt_obj["condition"],
                        f"{oloc}.condition",
                        validator,
                        state_defs=narrative_state_defs,
                        rooms=rooms,
                        items=items,
                        quests=quests,
                        depth=1,
                        node_count=[0],
                    )
                if oid in opt_ids_seen:
                    validator.issues.append(f"{nloc} 选项 ID 重复：{oid}")
                opt_ids_seen.add(oid)
                opts.append(
                    DialogueOption(
                        id=oid,
                        text=otxt,
                        next_node_id=next_id,
                        effects=tuple(effects),
                        condition=condition,
                    )
                )

            if opts and not any(option.condition is None for option in opts):
                validator.issues.append(
                    f"{nloc}.options 至少需要一个无条件选项"
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
    for state_id in sorted(set(narrative_state_defs) & legacy_flag_ids):
        validator.issues.append(
            f"叙事状态 ID {state_id} 不得与 legacy flag ID 重复"
        )

    # --- shops ---
    shop_defs_list: list[ShopDefinition] = []
    for index, obj in enumerate(_load_entity_array(root, "shops.json", validator)):
        location = f"shops.json[{index}]"
        validator.keys(
            obj,
            {
                "id",
                "name",
                "room_id",
                "catalog",
                "canon_ref",
                "adaptation_notes",
            },
            location,
        )
        shop_id = validator.stable_id(
            validator.text(obj, "id", location), f"{location}.id"
        )
        room_id = validator.stable_id(
            validator.text(obj, "room_id", location), f"{location}.room_id"
        )
        catalog_raw = validator.array(obj.get("catalog"), f"{location}.catalog")
        if not catalog_raw:
            validator.issues.append(f"{location}.catalog 必须是非空数组")
        catalog: list[ShopListingDefinition] = []
        catalog_item_ids: set[str] = set()
        for listing_index, listing_raw in enumerate(catalog_raw):
            listing_location = f"{location}.catalog[{listing_index}]"
            listing_obj = validator.object(listing_raw, listing_location)
            validator.keys(
                listing_obj,
                {"item_id", "buy_price", "sell_price"},
                listing_location,
            )
            item_id = validator.stable_id(
                validator.text(listing_obj, "item_id", listing_location),
                f"{listing_location}.item_id",
            )
            buy_price = validator.integer(
                listing_obj,
                "buy_price",
                listing_location,
                minimum=1,
                default=1,
            )
            sell_price = validator.integer(
                listing_obj,
                "sell_price",
                listing_location,
                minimum=1,
                default=1,
            )
            if sell_price > buy_price:
                validator.issues.append(
                    f"{listing_location}.sell_price 不得大于 buy_price"
                )
            if item_id in catalog_item_ids:
                validator.issues.append(
                    f"{location}.catalog 包含重复 item_id：{item_id}"
                )
            catalog_item_ids.add(item_id)
            catalog.append(
                ShopListingDefinition(
                    item_id=item_id,
                    buy_price=buy_price,
                    sell_price=sell_price,
                )
            )
        shop_defs_list.append(
            ShopDefinition(
                id=shop_id,
                name=validator.text(obj, "name", location),
                room_id=room_id,
                catalog=tuple(catalog),
                metadata=_metadata(obj, location, validator),
            )
        )

    shops = _unique_map(shop_defs_list, "shops.json", validator)

    campaign = _load_campaign_definition(
        root,
        validator,
        state_defs=narrative_state_defs,
        rooms=rooms,
        items=items,
        characters=characters,
        quests=quests,
        dialogues=dialogues,
    )

    if start_room_id and start_room_id not in rooms:
        validator.issues.append(
            f"pack.json.start_room_id 引用了不存在的房间：{start_room_id}"
        )

    # --- Cross-reference validation with stackable/non-stackable rules ---
    # Build item_id → list of source descriptions for conflict detection.
    item_sources: dict[str, list[str]] = {}  # item_id → [source descriptions]
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
        seen_in_room: set[str] = set()
        for stack_def in room.item_stacks:
            iid = stack_def.item_id
            if iid not in items:
                validator.issues.append(
                    f"房间 {room.id} 引用了不存在的物品：{iid}"
                )
                continue
            if iid in seen_in_room:
                validator.issues.append(
                    f"房间 {room.id} 包含重复物品栈：{iid}"
                )
            seen_in_room.add(iid)
            # Check quantity <= stack_limit
            item_def = items[iid]
            if stack_def.quantity > item_def.stack_limit:
                validator.issues.append(
                    f"房间 {room.id} 物品 {iid} 数量 {stack_def.quantity} "
                    f"超过栈上限 ({item_def.stack_limit})"
                )
            if item_def.stack_limit == 1 and stack_def.quantity != 1:
                validator.issues.append(
                    f"房间 {room.id} 物品 {iid} stack_limit=1 时数量必须为 1"
                )
            item_sources.setdefault(iid, []).append(f"房间 {room.id}")

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

    loot_item_monsters: dict[str, list[str]] = {}
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
        if monster.loot_item is None:
            continue
        loot_def = monster.loot_item
        loot_item_monsters.setdefault(loot_def.item_id, []).append(monster.id)
        if loot_def.item_id not in items:
            validator.issues.append(
                f"怪物 {monster.id} 的 loot_item 引用了不存在的物品："
                f"{loot_def.item_id}"
            )
            continue
        item_def = items[loot_def.item_id]
        if loot_def.quantity > item_def.stack_limit:
            validator.issues.append(
                f"怪物 {monster.id} 的 loot_item 数量 {loot_def.quantity} "
                f"超过栈上限 ({item_def.stack_limit})"
            )
        if item_def.stack_limit == 1 and loot_def.quantity != 1:
            validator.issues.append(
                f"怪物 {monster.id} 的 loot_item {loot_def.item_id} "
                f"stack_limit=1 时数量必须为 1"
            )
        item_sources.setdefault(loot_def.item_id, []).append(
            f"怪物 {monster.id} loot"
        )

    for character in characters.values():
        if character.room_id not in rooms:
            validator.issues.append(
                f"角色 {character.id} 的 room_id 引用了不存在的房间："
                f"{character.room_id}"
            )

    shop_room_ids: dict[str, str] = {}
    for shop in shops.values():
        if shop.room_id not in rooms:
            validator.issues.append(
                f"商店 {shop.id} 的 room_id 引用了不存在的房间：{shop.room_id}"
            )
        elif shop.room_id in shop_room_ids:
            validator.issues.append(
                f"房间 {shop.room_id} 不能同时拥有多个商店："
                f"{shop_room_ids[shop.room_id]} 和 {shop.id}"
            )
        else:
            shop_room_ids[shop.room_id] = shop.id
        for listing in shop.catalog:
            if listing.item_id not in items:
                validator.issues.append(
                    f"商店 {shop.id} 的 catalog 引用了不存在的物品："
                    f"{listing.item_id}"
                )
                continue
            item_sources.setdefault(listing.item_id, []).append(
                f"商店 {shop.id} catalog"
            )

    for dialogue in dialogues.values():
        if dialogue.character_id not in characters:
            validator.issues.append(
                f"对话 {dialogue.id} 的 character_id 引用了不存在的角色："
                f"{dialogue.character_id}"
            )
        for node in dialogue.nodes.values():
            for option in node.options:
                option_location = (
                    f"对话 {dialogue.id} 节点 {node.id} 选项 {option.id}"
                )
                for effect in option.effects:
                    if isinstance(effect, GrantItemEffect):
                        item = items.get(effect.item_id)
                        if item is None:
                            validator.issues.append(
                                f"{option_location} 的 grant_item 引用了不存在的物品："
                                f"{effect.item_id}"
                            )
                            continue
                        if item.heal_amount is not None:
                            validator.issues.append(
                                f"{option_location} 的 grant_item 不能引用消耗品："
                                f"{effect.item_id}"
                            )
                        if effect.quantity > item.stack_limit:
                            validator.issues.append(
                                f"{option_location} 的 grant_item 数量 {effect.quantity} "
                                f"超过栈上限 ({item.stack_limit})"
                            )
                        if item.stack_limit == 1 and effect.quantity != 1:
                            validator.issues.append(
                                f"{option_location} 的 grant_item {effect.item_id} "
                                f"stack_limit=1 时数量必须为 1"
                            )
                        item_sources.setdefault(effect.item_id, []).append(
                            option_location
                        )
                    elif isinstance(effect, AcceptQuestEffect):
                        if effect.quest_id not in quests:
                            validator.issues.append(
                                f"{option_location} 的 accept_quest 引用了不存在的任务："
                                f"{effect.quest_id}"
                            )

    if campaign is not None:
        for action in campaign.actions.values():
            for effect in action.effects:
                if not isinstance(effect, GrantItemEffect):
                    continue
                if effect.item_id not in items:
                    continue
                item_sources.setdefault(effect.item_id, []).append(
                    f"campaign 动作 {action.id}"
                )

    # Non-stackable (stack_limit==1) cross-source conflict detection.
    for item_id, sources in item_sources.items():
        if len(sources) > 1 and items[item_id].stack_limit == 1:
            validator.issues.append(
                f"stack_limit=1 的物品 {item_id} 被多个来源引用：{sources}"
            )

    for item_id, monster_ids in loot_item_monsters.items():
        if len(monster_ids) > 1:
            validator.issues.append(
                f"物品 {item_id} 被多个怪物作为战利品：{sorted(monster_ids)}"
            )
    # Track (kind, target) so each concrete world condition maps to one quest.
    quest_target_map: dict[tuple[str, str], list[str]] = {}
    for quest in quests.values():
        if quest.trigger_room_id not in rooms:
            validator.issues.append(
                f"任务 {quest.id} 的 trigger_room_id 引用了不存在的房间："
                f"{quest.trigger_room_id}"
            )
        if isinstance(quest, MonsterDefeatedQuestDefinition):
            target_id = quest.target_monster_id
            if target_id not in monsters:
                validator.issues.append(
                    f"任务 {quest.id} 的 target_monster_id 引用了不存在的怪物："
                    f"{target_id}"
                )
        elif isinstance(quest, ReachRoomQuestDefinition):
            target_id = quest.target_room_id
            if target_id not in rooms:
                validator.issues.append(
                    f"任务 {quest.id} 的 target_room_id 引用了不存在的房间："
                    f"{target_id}"
                )
        else:
            target_id = quest.target_item_id
            item = items.get(target_id)
            if item is None:
                validator.issues.append(
                    f"任务 {quest.id} 的 target_item_id 引用了不存在的物品："
                    f"{target_id}"
                )
            elif quest.required_quantity > item.stack_limit:
                validator.issues.append(
                    f"任务 {quest.id} 的 required_quantity {quest.required_quantity} "
                    f"超过物品 {target_id} 的栈上限 ({item.stack_limit})"
                )
        quest_target_map.setdefault((quest.kind, target_id), []).append(quest.id)
    for (kind, target_id), quest_ids in quest_target_map.items():
        if len(quest_ids) > 1:
            validator.issues.append(
                f"{kind} 目标 {target_id} 被多个任务使用：{sorted(quest_ids)}"
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
        shops=shops,
        narrative_state_defs=narrative_state_defs,
        campaign=campaign,
        extensions=extensions,
    )


def validate_content_pack(path: str | Path) -> tuple[str, ...]:
    """Validate a pack and return no issues, or raise with all found issues."""

    load_content_pack(path)
    return ()
