"""Compile a CanonRegistry into one deterministic micro content pack.

The plan is deliberately human-authored. Registry claims provide provenance only;
all game-facing text and numbers are copied verbatim from the plan.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Any, Literal

from lore2mud.content.loader import ContentValidationError, load_content_pack
from pipeline.adaptation import (
    DialogueAdaptation,
    DialogueNodeDef,
    DialogueOptionDef,
    ManifestGameOnly,
    ManifestPack,
    PackProfile,
    PlayerSub,
    QuestAdaptation,
)
from pipeline.canon_registry import (
    CanonRegistry,
    CanonRegistryValidationError,
    RegistrySource,
    validate_canon_registry_document,
)


_STABLE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_CHAPTER_ID_RE = re.compile(r"^chapter_[0-9]{6}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

_CONTENT_FIELDS = (
    "pack",
    "rooms",
    "items",
    "characters",
    "quests",
    "dialogues",
    "monsters",
    "shops",
)
_MANIFEST_FILENAME = "registry_adaptation_manifest.json"
_ALLOWED_FILES = frozenset(
    {
        "pack.json",
        "rooms.json",
        "items.json",
        "characters.json",
        "quests.json",
        "dialogues.json",
        "monsters.json",
        "shops.json",
        _MANIFEST_FILENAME,
    }
)


class RegistryAdaptationValidationError(ValueError):
    """Raised when a registry adaptation plan or manifest is invalid."""

    def __init__(self, issues: tuple[str, ...]) -> None:
        self.issues = issues
        super().__init__("\n".join(f"- {issue}" for issue in issues))


class RegistryCompilationError(ValueError):
    """Raised when a validated registry and plan cannot be compiled."""

    def __init__(self, issues: tuple[str, ...]) -> None:
        self.issues = issues
        super().__init__("\n".join(f"- {issue}" for issue in issues))


@dataclass(frozen=True, slots=True)
class RegistryClaimRef:
    promotion_id: str
    source_entity_id: str
    source_claim_id: str


@dataclass(frozen=True, slots=True)
class RegistryEntityAdaptation:
    registry_entity_ref: str
    game_id: str
    name: str
    description: str
    registry_claim_refs: tuple[RegistryClaimRef, ...]
    adaptation_notes: str


@dataclass(frozen=True, slots=True)
class RegistryOmissionEntry:
    registry_entity_ref: str
    reason: str


@dataclass(frozen=True, slots=True)
class RegistryAdaptationPlan:
    format_version: int
    adaptation_id: str
    source_registry_id: str
    source_registry_version: int
    pack: PackProfile
    room: RegistryEntityAdaptation
    character: RegistryEntityAdaptation
    item: RegistryEntityAdaptation
    quest: QuestAdaptation
    dialogue: DialogueAdaptation
    omissions: tuple[RegistryOmissionEntry, ...]


@dataclass(frozen=True, slots=True)
class RegistryManifestSource:
    promotion_id: str
    chapter_id: str
    chapter_sha256: str
    extracted_by: str
    review_id: str
    reviewed_by: str


@dataclass(frozen=True, slots=True)
class RegistryManifestBinding:
    game_kind: Literal["room", "character", "item"]
    game_id: str
    registry_entity_ref: str
    registry_claim_refs: tuple[RegistryClaimRef, ...]
    source_chapters: tuple[str, ...]
    adaptation_notes: str


@dataclass(frozen=True, slots=True)
class RegistryManifestOmission:
    registry_entity_ref: str
    reason: str


@dataclass(frozen=True, slots=True)
class RegistryAdaptationManifest:
    format_version: int
    adaptation_id: str
    source_registry_id: str
    source_registry_version: int
    sources: tuple[RegistryManifestSource, ...]
    pack: ManifestPack
    bindings: tuple[RegistryManifestBinding, ...]
    omissions: tuple[RegistryManifestOmission, ...]
    game_only: tuple[ManifestGameOnly, ...]


@dataclass(frozen=True, slots=True)
class RegistryMicroContentPack:
    pack: dict[str, Any]
    rooms: tuple[dict[str, Any], ...]
    items: tuple[dict[str, Any], ...]
    characters: tuple[dict[str, Any], ...]
    quests: tuple[dict[str, Any], ...]
    dialogues: tuple[dict[str, Any], ...]
    monsters: tuple[dict[str, Any], ...]
    shops: tuple[dict[str, Any], ...]
    manifest: RegistryAdaptationManifest

    def __post_init__(self) -> None:
        if not isinstance(self.pack, dict):
            raise TypeError(f"pack must be dict, got {type(self.pack).__name__}")
        for attribute in _CONTENT_FIELDS[1:]:
            value = getattr(self, attribute)
            if not isinstance(value, tuple):
                raise TypeError(
                    f"{attribute} must be tuple, got {type(value).__name__}"
                )
            for index, entry in enumerate(value):
                if not isinstance(entry, dict):
                    raise TypeError(
                        f"{attribute}[{index}] must be dict, "
                        f"got {type(entry).__name__}"
                    )
        if not isinstance(self.manifest, RegistryAdaptationManifest):
            raise TypeError("manifest must be RegistryAdaptationManifest")


def _normalization_key(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold().strip()


def _claim_ref_key(value: RegistryClaimRef) -> tuple[str, str, str]:
    return (value.promotion_id, value.source_entity_id, value.source_claim_id)


def _unknown_keys(
    obj: dict[str, Any], allowed: frozenset[str], loc: str, issues: list[str]
) -> None:
    for key in sorted(set(obj) - allowed):
        issues.append(f"{loc} contains unknown field: {key}")


def _required_text(
    obj: dict[str, Any], key: str, loc: str, issues: list[str]
) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        issues.append(f"{loc}.{key} must be a non-blank string")
        return ""
    return value


def _required_integer(
    obj: dict[str, Any],
    key: str,
    loc: str,
    issues: list[str],
    *,
    minimum: int,
    fallback: int,
) -> int:
    if key not in obj:
        issues.append(f"{loc}.{key} is required")
        return fallback
    value = obj.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        issues.append(f"{loc}.{key} must be an integer >= {minimum}")
        return fallback
    return value


def _stable_id(value: str, loc: str, issues: list[str]) -> None:
    if value and not _STABLE_ID_RE.fullmatch(value):
        issues.append(f"{loc} must match stable ID syntax")


def _parse_claim_refs(
    raw: object, loc: str, issues: list[str], *, nonempty: bool = True
) -> tuple[RegistryClaimRef, ...]:
    if not isinstance(raw, list):
        issues.append(f"{loc} must be an array")
        return ()
    if nonempty and not raw:
        issues.append(f"{loc} must not be empty")
    parsed: list[RegistryClaimRef] = []
    seen: set[tuple[str, str, str]] = set()
    for index, entry in enumerate(raw):
        entry_loc = f"{loc}[{index}]"
        if not isinstance(entry, dict):
            issues.append(f"{entry_loc} must be an object")
            continue
        _unknown_keys(
            entry,
            frozenset({"promotion_id", "source_entity_id", "source_claim_id"}),
            entry_loc,
            issues,
        )
        promotion_id = _required_text(entry, "promotion_id", entry_loc, issues)
        source_entity_id = _required_text(
            entry, "source_entity_id", entry_loc, issues
        )
        source_claim_id = _required_text(entry, "source_claim_id", entry_loc, issues)
        _stable_id(promotion_id, f"{entry_loc}.promotion_id", issues)
        _stable_id(source_entity_id, f"{entry_loc}.source_entity_id", issues)
        _stable_id(source_claim_id, f"{entry_loc}.source_claim_id", issues)
        parsed_ref = RegistryClaimRef(
            promotion_id=promotion_id,
            source_entity_id=source_entity_id,
            source_claim_id=source_claim_id,
        )
        key = _claim_ref_key(parsed_ref)
        if key in seen:
            issues.append(f"{entry_loc} duplicates claim ref {key!r}")
        seen.add(key)
        parsed.append(parsed_ref)
    return tuple(sorted(parsed, key=_claim_ref_key))


def _parse_string_array(
    raw: object,
    loc: str,
    issues: list[str],
    *,
    pattern: re.Pattern[str] | None = None,
    nonempty: bool = True,
) -> tuple[str, ...]:
    if not isinstance(raw, list):
        issues.append(f"{loc} must be an array")
        return ()
    if nonempty and not raw:
        issues.append(f"{loc} must not be empty")
    values: list[str] = []
    seen: set[str] = set()
    for index, value in enumerate(raw):
        value_loc = f"{loc}[{index}]"
        if not isinstance(value, str) or not value.strip():
            issues.append(f"{value_loc} must be a non-blank string")
            continue
        if pattern is not None and not pattern.fullmatch(value):
            issues.append(f"{value_loc} has an invalid format")
        normalized = _normalization_key(value)
        if normalized in seen:
            issues.append(f"{value_loc} is duplicated after normalization")
        seen.add(normalized)
        values.append(value)
    return tuple(sorted(values, key=_normalization_key))


def _parse_pack(raw: object, loc: str, issues: list[str]) -> PackProfile:
    if not isinstance(raw, dict):
        issues.append(f"{loc} must be an object")
        return PackProfile("", "", "", "", PlayerSub())
    _unknown_keys(
        raw,
        frozenset({"id", "name", "version", "start_room_id", "player"}),
        loc,
        issues,
    )
    pack_id = _required_text(raw, "id", loc, issues)
    name = _required_text(raw, "name", loc, issues)
    version = _required_text(raw, "version", loc, issues)
    start_room_id = _required_text(raw, "start_room_id", loc, issues)
    _stable_id(pack_id, f"{loc}.id", issues)
    _stable_id(start_room_id, f"{loc}.start_room_id", issues)

    raw_player = raw.get("player")
    if not isinstance(raw_player, dict):
        issues.append(f"{loc}.player must be an object")
        player = PlayerSub()
    else:
        _unknown_keys(
            raw_player,
            frozenset(
                {"max_hp", "attack", "defense", "inventory_capacity", "coins"}
            ),
            f"{loc}.player",
            issues,
        )
        player = PlayerSub(
            max_hp=_required_integer(
                raw_player,
                "max_hp",
                f"{loc}.player",
                issues,
                minimum=1,
                fallback=20,
            ),
            attack=_required_integer(
                raw_player,
                "attack",
                f"{loc}.player",
                issues,
                minimum=1,
                fallback=5,
            ),
            defense=_required_integer(
                raw_player,
                "defense",
                f"{loc}.player",
                issues,
                minimum=0,
                fallback=1,
            ),
            inventory_capacity=_required_integer(
                raw_player,
                "inventory_capacity",
                f"{loc}.player",
                issues,
                minimum=1,
                fallback=20,
            ),
            coins=_required_integer(
                raw_player,
                "coins",
                f"{loc}.player",
                issues,
                minimum=0,
                fallback=0,
            ),
        )
    return PackProfile(pack_id, name, version, start_room_id, player)


def _parse_entity_adaptation(
    raw: object, loc: str, issues: list[str]
) -> RegistryEntityAdaptation:
    if not isinstance(raw, dict):
        issues.append(f"{loc} must be an object")
        return RegistryEntityAdaptation("", "", "", "", (), "")
    _unknown_keys(
        raw,
        frozenset(
            {
                "registry_entity_ref",
                "game_id",
                "name",
                "description",
                "registry_claim_refs",
                "adaptation_notes",
            }
        ),
        loc,
        issues,
    )
    entity_ref = _required_text(raw, "registry_entity_ref", loc, issues)
    game_id = _required_text(raw, "game_id", loc, issues)
    _stable_id(entity_ref, f"{loc}.registry_entity_ref", issues)
    _stable_id(game_id, f"{loc}.game_id", issues)
    return RegistryEntityAdaptation(
        registry_entity_ref=entity_ref,
        game_id=game_id,
        name=_required_text(raw, "name", loc, issues),
        description=_required_text(raw, "description", loc, issues),
        registry_claim_refs=_parse_claim_refs(
            raw.get("registry_claim_refs"),
            f"{loc}.registry_claim_refs",
            issues,
        ),
        adaptation_notes=_required_text(raw, "adaptation_notes", loc, issues),
    )


def _parse_quest(raw: object, loc: str, issues: list[str]) -> QuestAdaptation:
    if not isinstance(raw, dict):
        issues.append(f"{loc} must be an object")
        return QuestAdaptation("", "collect_item", "", "", "", 1, 1, "")
    _unknown_keys(
        raw,
        frozenset(
            {
                "game_id",
                "kind",
                "name",
                "description",
                "target_item_id",
                "required_quantity",
                "reward_experience",
                "adaptation_notes",
            }
        ),
        loc,
        issues,
    )
    game_id = _required_text(raw, "game_id", loc, issues)
    target_item_id = _required_text(raw, "target_item_id", loc, issues)
    _stable_id(game_id, f"{loc}.game_id", issues)
    _stable_id(target_item_id, f"{loc}.target_item_id", issues)
    if raw.get("kind") != "collect_item":
        issues.append(f"{loc}.kind must be collect_item")
    return QuestAdaptation(
        game_id=game_id,
        kind="collect_item",
        name=_required_text(raw, "name", loc, issues),
        description=_required_text(raw, "description", loc, issues),
        target_item_id=target_item_id,
        required_quantity=_required_integer(
            raw, "required_quantity", loc, issues, minimum=1, fallback=1
        ),
        reward_experience=_required_integer(
            raw, "reward_experience", loc, issues, minimum=1, fallback=1
        ),
        adaptation_notes=_required_text(raw, "adaptation_notes", loc, issues),
    )


def _parse_dialogue(
    raw: object, loc: str, issues: list[str]
) -> DialogueAdaptation:
    if not isinstance(raw, dict):
        issues.append(f"{loc} must be an object")
        return DialogueAdaptation("", "", "", (), "")
    _unknown_keys(
        raw,
        frozenset(
            {"game_id", "character_id", "start_node_id", "nodes", "adaptation_notes"}
        ),
        loc,
        issues,
    )
    game_id = _required_text(raw, "game_id", loc, issues)
    character_id = _required_text(raw, "character_id", loc, issues)
    start_node_id = _required_text(raw, "start_node_id", loc, issues)
    _stable_id(game_id, f"{loc}.game_id", issues)
    _stable_id(character_id, f"{loc}.character_id", issues)
    _stable_id(start_node_id, f"{loc}.start_node_id", issues)

    raw_nodes = raw.get("nodes")
    if not isinstance(raw_nodes, list):
        issues.append(f"{loc}.nodes must be an array")
        raw_nodes = []
    elif not raw_nodes:
        issues.append(f"{loc}.nodes must not be empty")

    node_ids: set[str] = set()
    next_node_ids: set[str] = set()
    nodes: list[DialogueNodeDef] = []
    for node_index, raw_node in enumerate(raw_nodes):
        node_loc = f"{loc}.nodes[{node_index}]"
        if not isinstance(raw_node, dict):
            issues.append(f"{node_loc} must be an object")
            continue
        _unknown_keys(
            raw_node, frozenset({"id", "text", "options"}), node_loc, issues
        )
        node_id = _required_text(raw_node, "id", node_loc, issues)
        _stable_id(node_id, f"{node_loc}.id", issues)
        if node_id in node_ids:
            issues.append(f"{node_loc}.id is duplicated: {node_id}")
        node_ids.add(node_id)
        node_text = _required_text(raw_node, "text", node_loc, issues)
        raw_options = raw_node.get("options")
        if not isinstance(raw_options, list):
            issues.append(f"{node_loc}.options must be an array")
            raw_options = []
        elif not raw_options:
            issues.append(f"{node_loc}.options must not be empty")
        option_ids: set[str] = set()
        options: list[DialogueOptionDef] = []
        for option_index, raw_option in enumerate(raw_options):
            option_loc = f"{node_loc}.options[{option_index}]"
            if not isinstance(raw_option, dict):
                issues.append(f"{option_loc} must be an object")
                continue
            _unknown_keys(
                raw_option,
                frozenset({"id", "text", "next_node_id", "effects"}),
                option_loc,
                issues,
            )
            option_id = _required_text(raw_option, "id", option_loc, issues)
            _stable_id(option_id, f"{option_loc}.id", issues)
            if option_id in option_ids:
                issues.append(f"{option_loc}.id is duplicated: {option_id}")
            option_ids.add(option_id)
            option_text = _required_text(raw_option, "text", option_loc, issues)
            next_node_id = raw_option.get("next_node_id")
            if next_node_id is not None:
                if not isinstance(next_node_id, str) or not next_node_id.strip():
                    issues.append(
                        f"{option_loc}.next_node_id must be a non-blank string or null"
                    )
                    next_node_id = None
                else:
                    _stable_id(next_node_id, f"{option_loc}.next_node_id", issues)
                    next_node_ids.add(next_node_id)
            effects = raw_option.get("effects")
            if not isinstance(effects, list) or effects:
                issues.append(f"{option_loc}.effects must be an empty array")
            options.append(DialogueOptionDef(option_id, option_text, next_node_id))
        nodes.append(DialogueNodeDef(node_id, node_text, tuple(options)))

    if start_node_id not in node_ids:
        issues.append(f"{loc}.start_node_id does not reference a node")
    for missing_id in sorted(next_node_ids - node_ids):
        issues.append(f"{loc} references missing next_node_id: {missing_id}")
    return DialogueAdaptation(
        game_id=game_id,
        character_id=character_id,
        start_node_id=start_node_id,
        nodes=tuple(nodes),
        adaptation_notes=_required_text(raw, "adaptation_notes", loc, issues),
    )


def _parse_omissions(
    raw: object, loc: str, issues: list[str]
) -> tuple[RegistryOmissionEntry, ...]:
    if not isinstance(raw, list):
        issues.append(f"{loc} must be an array")
        return ()
    parsed: list[RegistryOmissionEntry] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw):
        entry_loc = f"{loc}[{index}]"
        if not isinstance(entry, dict):
            issues.append(f"{entry_loc} must be an object")
            continue
        _unknown_keys(
            entry, frozenset({"registry_entity_ref", "reason"}), entry_loc, issues
        )
        entity_ref = _required_text(entry, "registry_entity_ref", entry_loc, issues)
        _stable_id(entity_ref, f"{entry_loc}.registry_entity_ref", issues)
        if entity_ref in seen:
            issues.append(f"{entry_loc}.registry_entity_ref is duplicated")
        seen.add(entity_ref)
        parsed.append(
            RegistryOmissionEntry(
                registry_entity_ref=entity_ref,
                reason=_required_text(entry, "reason", entry_loc, issues),
            )
        )
    return tuple(sorted(parsed, key=lambda value: value.registry_entity_ref))


def validate_registry_adaptation_plan(data: object) -> RegistryAdaptationPlan:
    """Strictly validate and canonicalize a RegistryAdaptationPlan v1."""

    if not isinstance(data, dict):
        raise RegistryAdaptationValidationError(("root must be a JSON object",))
    issues: list[str] = []
    _unknown_keys(
        data,
        frozenset(
            {
                "format_version",
                "adaptation_id",
                "source_registry_id",
                "source_registry_version",
                "pack",
                "room",
                "character",
                "item",
                "quest",
                "dialogue",
                "omissions",
            }
        ),
        "root",
        issues,
    )
    format_version = _required_integer(
        data, "format_version", "root", issues, minimum=1, fallback=1
    )
    if format_version != 1:
        issues.append("format_version must be 1")
    adaptation_id = _required_text(data, "adaptation_id", "root", issues)
    source_registry_id = _required_text(data, "source_registry_id", "root", issues)
    _stable_id(adaptation_id, "adaptation_id", issues)
    _stable_id(source_registry_id, "source_registry_id", issues)
    source_registry_version = _required_integer(
        data,
        "source_registry_version",
        "root",
        issues,
        minimum=1,
        fallback=1,
    )
    plan = RegistryAdaptationPlan(
        format_version=1,
        adaptation_id=adaptation_id,
        source_registry_id=source_registry_id,
        source_registry_version=source_registry_version,
        pack=_parse_pack(data.get("pack"), "pack", issues),
        room=_parse_entity_adaptation(data.get("room"), "room", issues),
        character=_parse_entity_adaptation(
            data.get("character"), "character", issues
        ),
        item=_parse_entity_adaptation(data.get("item"), "item", issues),
        quest=_parse_quest(data.get("quest"), "quest", issues),
        dialogue=_parse_dialogue(data.get("dialogue"), "dialogue", issues),
        omissions=_parse_omissions(data.get("omissions"), "omissions", issues),
    )
    if issues:
        raise RegistryAdaptationValidationError(tuple(issues))
    return plan


def _manifest_source(source: RegistrySource) -> RegistryManifestSource:
    return RegistryManifestSource(
        promotion_id=source.promotion_id,
        chapter_id=source.chapter_id,
        chapter_sha256=source.chapter_sha256,
        extracted_by=source.extracted_by,
        review_id=source.review_id,
        reviewed_by=source.reviewed_by,
    )


def compile_registry_micro_pack(
    registry: CanonRegistry, plan: RegistryAdaptationPlan
) -> RegistryMicroContentPack:
    """Compile one registry-backed room, character, item, quest, and dialogue."""

    if not isinstance(registry, CanonRegistry):
        raise TypeError("registry must be CanonRegistry")
    if not isinstance(plan, RegistryAdaptationPlan):
        raise TypeError("plan must be RegistryAdaptationPlan")

    issues: list[str] = []
    if plan.source_registry_id != registry.registry_id:
        issues.append(
            "source_registry_id must equal the input CanonRegistry registry_id"
        )
    if plan.source_registry_version != registry.registry_version:
        issues.append(
            "source_registry_version must equal the input CanonRegistry version"
        )

    entities = {entity.entity_id: entity for entity in registry.entities}
    expected_types = {"room": "location", "character": "character", "item": "item"}
    adaptations = (
        ("room", plan.room),
        ("character", plan.character),
        ("item", plan.item),
    )
    adapted: dict[str, str] = {}
    claim_chapters_by_kind: dict[str, tuple[str, ...]] = {}
    selected_promotions: set[str] = set()
    for kind, adaptation in adaptations:
        entity_ref = adaptation.registry_entity_ref
        if entity_ref in adapted:
            issues.append(
                f"{kind}.registry_entity_ref is already used by {adapted[entity_ref]}"
            )
        adapted[entity_ref] = kind
        entity = entities.get(entity_ref)
        if entity is None:
            issues.append(f"{kind}.registry_entity_ref is missing from CanonRegistry")
            continue
        if entity.entity_type != expected_types[kind]:
            issues.append(
                f"{kind}.registry_entity_ref has type {entity.entity_type}; "
                f"expected {expected_types[kind]}"
            )

        actual_claims = {
            (
                claim.source.promotion_id,
                claim.source.source_entity_id,
                claim.source.source_claim_id,
            ): claim
            for claim in entity.claims
        }
        selected_keys = [_claim_ref_key(ref) for ref in adaptation.registry_claim_refs]
        seen_selected: set[tuple[str, str, str]] = set()
        for selected_key in selected_keys:
            if selected_key in seen_selected:
                issues.append(f"{kind}.registry_claim_refs duplicates {selected_key!r}")
            seen_selected.add(selected_key)
            selected_promotions.add(selected_key[0])
            if selected_key not in actual_claims:
                issues.append(
                    f"{kind}.registry_claim_refs contains a foreign claim: "
                    f"{selected_key!r}"
                )
        missing_claims = set(actual_claims) - seen_selected
        if missing_claims:
            issues.append(
                f"{kind}.registry_claim_refs omits registry claims: "
                f"{sorted(missing_claims)!r}"
            )
        if not actual_claims:
            issues.append(f"{kind} registry entity has no claims to bind")
        chapters = {
            chapter
            for claim_key in seen_selected & set(actual_claims)
            for chapter in actual_claims[claim_key].source_chapters
        }
        claim_chapters_by_kind[kind] = tuple(sorted(chapters))

    if len(selected_promotions) < 2:
        issues.append("selected registry claims must span at least two promotions")

    omitted: set[str] = set()
    for omission in plan.omissions:
        entity_ref = omission.registry_entity_ref
        if entity_ref in omitted:
            issues.append(f"omissions duplicates registry entity {entity_ref}")
        omitted.add(entity_ref)
        if entity_ref not in entities:
            issues.append(f"omissions references missing registry entity {entity_ref}")
        if entity_ref in adapted:
            issues.append(f"omissions includes adapted registry entity {entity_ref}")
    covered = set(adapted) | omitted
    missing_entities = set(entities) - covered
    extra_entities = covered - set(entities)
    if missing_entities:
        issues.append(f"registry entities are not covered: {sorted(missing_entities)!r}")
    if extra_entities:
        issues.append(f"plan references unknown entities: {sorted(extra_entities)!r}")

    game_ids: dict[str, str] = {}
    for kind, adaptation in (
        *adaptations,
        ("quest", plan.quest),
        ("dialogue", plan.dialogue),
    ):
        if adaptation.game_id in game_ids:
            issues.append(
                f"game_id {adaptation.game_id!r} is shared by "
                f"{game_ids[adaptation.game_id]} and {kind}"
            )
        game_ids[adaptation.game_id] = kind
    if plan.pack.start_room_id != plan.room.game_id:
        issues.append("pack.start_room_id must equal room.game_id")
    if plan.dialogue.character_id != plan.character.game_id:
        issues.append("dialogue.character_id must equal character.game_id")
    if plan.quest.target_item_id != plan.item.game_id:
        issues.append("quest.target_item_id must equal item.game_id")
    if plan.quest.kind != "collect_item":
        issues.append("quest.kind must be collect_item")
    if plan.quest.required_quantity != 1:
        issues.append("quest.required_quantity must be 1")
    if issues:
        raise RegistryCompilationError(tuple(issues))

    pack_document = {
        "id": plan.pack.id,
        "name": plan.pack.name,
        "version": plan.pack.version,
        "start_room_id": plan.pack.start_room_id,
        "player": {
            "max_hp": plan.pack.player.max_hp,
            "attack": plan.pack.player.attack,
            "defense": plan.pack.player.defense,
            "inventory_capacity": plan.pack.player.inventory_capacity,
            "coins": plan.pack.player.coins,
        },
        "extensions": {
            "canon_provider": {
                "kind": "registry_adaptation_manifest",
                "format_version": 1,
                "path": _MANIFEST_FILENAME,
            }
        },
    }
    rooms = (
        {
            "id": plan.room.game_id,
            "name": plan.room.name,
            "description": plan.room.description,
            "exits": {},
            "item_stacks": [{"item_id": plan.item.game_id, "quantity": 1}],
            "monster_ids": [],
            "canon_ref": {
                "entity_id": plan.room.registry_entity_ref,
                "source_chapters": list(claim_chapters_by_kind["room"]),
            },
            "adaptation_notes": plan.room.adaptation_notes,
        },
    )
    items = (
        {
            "id": plan.item.game_id,
            "name": plan.item.name,
            "description": plan.item.description,
            "stack_limit": 1,
            "canon_ref": {
                "entity_id": plan.item.registry_entity_ref,
                "source_chapters": list(claim_chapters_by_kind["item"]),
            },
            "adaptation_notes": plan.item.adaptation_notes,
        },
    )
    characters = (
        {
            "id": plan.character.game_id,
            "name": plan.character.name,
            "description": plan.character.description,
            "room_id": plan.pack.start_room_id,
            "canon_ref": {
                "entity_id": plan.character.registry_entity_ref,
                "source_chapters": list(claim_chapters_by_kind["character"]),
            },
            "adaptation_notes": plan.character.adaptation_notes,
        },
    )
    quests = (
        {
            "id": plan.quest.game_id,
            "kind": "collect_item",
            "name": plan.quest.name,
            "description": plan.quest.description,
            "trigger_room_id": plan.pack.start_room_id,
            "target_item_id": plan.quest.target_item_id,
            "required_quantity": 1,
            "reward_experience": plan.quest.reward_experience,
            "adaptation_notes": plan.quest.adaptation_notes,
        },
    )
    dialogue_nodes = [
        {
            "id": node.id,
            "text": node.text,
            "options": [
                {
                    "id": option.id,
                    "text": option.text,
                    "next_node_id": option.next_node_id,
                    "effects": [],
                }
                for option in node.options
            ],
        }
        for node in sorted(plan.dialogue.nodes, key=lambda node: node.id)
    ]
    dialogues = (
        {
            "id": plan.dialogue.game_id,
            "character_id": plan.dialogue.character_id,
            "start_node_id": plan.dialogue.start_node_id,
            "nodes": dialogue_nodes,
            "adaptation_notes": plan.dialogue.adaptation_notes,
        },
    )

    bindings = tuple(
        sorted(
            (
                RegistryManifestBinding(
                    game_kind=kind,
                    game_id=adaptation.game_id,
                    registry_entity_ref=adaptation.registry_entity_ref,
                    registry_claim_refs=tuple(
                        sorted(adaptation.registry_claim_refs, key=_claim_ref_key)
                    ),
                    source_chapters=claim_chapters_by_kind[kind],
                    adaptation_notes=adaptation.adaptation_notes,
                )
                for kind, adaptation in adaptations
            ),
            key=lambda binding: (binding.game_kind, binding.game_id),
        )
    )
    manifest = RegistryAdaptationManifest(
        format_version=1,
        adaptation_id=plan.adaptation_id,
        source_registry_id=registry.registry_id,
        source_registry_version=registry.registry_version,
        sources=tuple(
            sorted(
                (_manifest_source(source) for source in registry.sources),
                key=lambda source: (source.chapter_id, source.promotion_id),
            )
        ),
        pack=ManifestPack(id=plan.pack.id, version=plan.pack.version),
        bindings=bindings,
        omissions=tuple(
            RegistryManifestOmission(
                registry_entity_ref=omission.registry_entity_ref,
                reason=omission.reason,
            )
            for omission in sorted(
                plan.omissions, key=lambda value: value.registry_entity_ref
            )
        ),
        game_only=tuple(
            sorted(
                (
                    ManifestGameOnly(
                        game_kind="quest",
                        game_id=plan.quest.game_id,
                        adaptation_notes=plan.quest.adaptation_notes,
                    ),
                    ManifestGameOnly(
                        game_kind="dialogue",
                        game_id=plan.dialogue.game_id,
                        adaptation_notes=plan.dialogue.adaptation_notes,
                    ),
                ),
                key=lambda entry: (entry.game_kind, entry.game_id),
            )
        ),
    )
    validated_manifest = validate_registry_adaptation_manifest_document(
        registry_adaptation_manifest_to_document(manifest)
    )
    if validated_manifest != manifest:
        raise RegistryCompilationError(("compiled manifest is not canonical",))
    return RegistryMicroContentPack(
        pack=pack_document,
        rooms=rooms,
        items=items,
        characters=characters,
        quests=quests,
        dialogues=dialogues,
        monsters=(),
        shops=(),
        manifest=manifest,
    )


def _parse_manifest_source(
    raw: object, loc: str, issues: list[str]
) -> RegistryManifestSource | None:
    if not isinstance(raw, dict):
        issues.append(f"{loc} must be an object")
        return None
    _unknown_keys(
        raw,
        frozenset(
            {
                "promotion_id",
                "chapter_id",
                "chapter_sha256",
                "extracted_by",
                "review_id",
                "reviewed_by",
            }
        ),
        loc,
        issues,
    )
    promotion_id = _required_text(raw, "promotion_id", loc, issues)
    chapter_id = _required_text(raw, "chapter_id", loc, issues)
    chapter_sha256 = _required_text(raw, "chapter_sha256", loc, issues)
    review_id = _required_text(raw, "review_id", loc, issues)
    _stable_id(promotion_id, f"{loc}.promotion_id", issues)
    _stable_id(review_id, f"{loc}.review_id", issues)
    if chapter_id and not _CHAPTER_ID_RE.fullmatch(chapter_id):
        issues.append(f"{loc}.chapter_id must match chapter_NNNNNN")
    if chapter_sha256 and not _SHA256_RE.fullmatch(chapter_sha256):
        issues.append(f"{loc}.chapter_sha256 must be 64 lowercase hex characters")
    return RegistryManifestSource(
        promotion_id=promotion_id,
        chapter_id=chapter_id,
        chapter_sha256=chapter_sha256,
        extracted_by=_required_text(raw, "extracted_by", loc, issues),
        review_id=review_id,
        reviewed_by=_required_text(raw, "reviewed_by", loc, issues),
    )


def _parse_manifest_binding(
    raw: object, loc: str, issues: list[str]
) -> RegistryManifestBinding | None:
    if not isinstance(raw, dict):
        issues.append(f"{loc} must be an object")
        return None
    _unknown_keys(
        raw,
        frozenset(
            {
                "game_kind",
                "game_id",
                "registry_entity_ref",
                "registry_claim_refs",
                "source_chapters",
                "adaptation_notes",
            }
        ),
        loc,
        issues,
    )
    raw_kind = raw.get("game_kind")
    if not isinstance(raw_kind, str) or raw_kind not in {"room", "character", "item"}:
        issues.append(f"{loc}.game_kind must be room, character, or item")
        game_kind: Literal["room", "character", "item"] = "room"
    else:
        game_kind = raw_kind
    game_id = _required_text(raw, "game_id", loc, issues)
    entity_ref = _required_text(raw, "registry_entity_ref", loc, issues)
    _stable_id(game_id, f"{loc}.game_id", issues)
    _stable_id(entity_ref, f"{loc}.registry_entity_ref", issues)
    return RegistryManifestBinding(
        game_kind=game_kind,
        game_id=game_id,
        registry_entity_ref=entity_ref,
        registry_claim_refs=_parse_claim_refs(
            raw.get("registry_claim_refs"), f"{loc}.registry_claim_refs", issues
        ),
        source_chapters=_parse_string_array(
            raw.get("source_chapters"),
            f"{loc}.source_chapters",
            issues,
            pattern=_CHAPTER_ID_RE,
        ),
        adaptation_notes=_required_text(raw, "adaptation_notes", loc, issues),
    )


def _parse_manifest_omissions(
    raw: object, loc: str, issues: list[str]
) -> tuple[RegistryManifestOmission, ...]:
    if not isinstance(raw, list):
        issues.append(f"{loc} must be an array")
        return ()
    parsed: list[RegistryManifestOmission] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw):
        entry_loc = f"{loc}[{index}]"
        if not isinstance(entry, dict):
            issues.append(f"{entry_loc} must be an object")
            continue
        _unknown_keys(
            entry, frozenset({"registry_entity_ref", "reason"}), entry_loc, issues
        )
        entity_ref = _required_text(entry, "registry_entity_ref", entry_loc, issues)
        _stable_id(entity_ref, f"{entry_loc}.registry_entity_ref", issues)
        if entity_ref in seen:
            issues.append(f"{entry_loc}.registry_entity_ref is duplicated")
        seen.add(entity_ref)
        parsed.append(
            RegistryManifestOmission(
                registry_entity_ref=entity_ref,
                reason=_required_text(entry, "reason", entry_loc, issues),
            )
        )
    return tuple(sorted(parsed, key=lambda entry: entry.registry_entity_ref))


def _parse_game_only(
    raw: object, loc: str, issues: list[str]
) -> tuple[ManifestGameOnly, ...]:
    if not isinstance(raw, list):
        issues.append(f"{loc} must be an array")
        return ()
    if len(raw) != 2:
        issues.append(f"{loc} must contain exactly two entries")
    parsed: list[ManifestGameOnly] = []
    seen_kinds: set[str] = set()
    seen_ids: set[str] = set()
    for index, entry in enumerate(raw):
        entry_loc = f"{loc}[{index}]"
        if not isinstance(entry, dict):
            issues.append(f"{entry_loc} must be an object")
            continue
        _unknown_keys(
            entry,
            frozenset({"game_kind", "game_id", "adaptation_notes"}),
            entry_loc,
            issues,
        )
        game_kind = entry.get("game_kind")
        if not isinstance(game_kind, str) or game_kind not in {"quest", "dialogue"}:
            issues.append(f"{entry_loc}.game_kind must be quest or dialogue")
            game_kind = "quest"
        if game_kind in seen_kinds:
            issues.append(f"{entry_loc}.game_kind is duplicated")
        seen_kinds.add(game_kind)
        game_id = _required_text(entry, "game_id", entry_loc, issues)
        _stable_id(game_id, f"{entry_loc}.game_id", issues)
        if game_id in seen_ids:
            issues.append(f"{entry_loc}.game_id is duplicated")
        seen_ids.add(game_id)
        parsed.append(
            ManifestGameOnly(
                game_kind=game_kind,
                game_id=game_id,
                adaptation_notes=_required_text(
                    entry, "adaptation_notes", entry_loc, issues
                ),
            )
        )
    return tuple(sorted(parsed, key=lambda entry: (entry.game_kind, entry.game_id)))


def validate_registry_adaptation_manifest_document(
    data: object,
) -> RegistryAdaptationManifest:
    """Validate a standalone registry adaptation manifest and its chapter derivation."""

    if not isinstance(data, dict):
        raise RegistryAdaptationValidationError(("root must be a JSON object",))
    issues: list[str] = []
    _unknown_keys(
        data,
        frozenset(
            {
                "format_version",
                "adaptation_id",
                "source_registry_id",
                "source_registry_version",
                "sources",
                "pack",
                "bindings",
                "omissions",
                "game_only",
            }
        ),
        "root",
        issues,
    )
    format_version = _required_integer(
        data, "format_version", "root", issues, minimum=1, fallback=1
    )
    if format_version != 1:
        issues.append("format_version must be 1")
    adaptation_id = _required_text(data, "adaptation_id", "root", issues)
    source_registry_id = _required_text(data, "source_registry_id", "root", issues)
    _stable_id(adaptation_id, "adaptation_id", issues)
    _stable_id(source_registry_id, "source_registry_id", issues)
    source_registry_version = _required_integer(
        data,
        "source_registry_version",
        "root",
        issues,
        minimum=1,
        fallback=1,
    )

    raw_sources = data.get("sources")
    if not isinstance(raw_sources, list):
        issues.append("sources must be an array")
        raw_sources = []
    elif len(raw_sources) < 2:
        issues.append("sources must contain at least two registry sources")
    sources: list[RegistryManifestSource] = []
    source_promotions: set[str] = set()
    source_chapters: set[str] = set()
    for index, raw_source in enumerate(raw_sources):
        source = _parse_manifest_source(raw_source, f"sources[{index}]", issues)
        if source is None:
            continue
        if source.promotion_id in source_promotions:
            issues.append(f"sources[{index}].promotion_id is duplicated")
        if source.chapter_id in source_chapters:
            issues.append(f"sources[{index}].chapter_id is duplicated")
        source_promotions.add(source.promotion_id)
        source_chapters.add(source.chapter_id)
        sources.append(source)
    source_by_promotion = {source.promotion_id: source for source in sources}

    raw_pack = data.get("pack")
    if not isinstance(raw_pack, dict):
        issues.append("pack must be an object")
        manifest_pack = ManifestPack("", "")
    else:
        _unknown_keys(raw_pack, frozenset({"id", "version"}), "pack", issues)
        pack_id = _required_text(raw_pack, "id", "pack", issues)
        _stable_id(pack_id, "pack.id", issues)
        manifest_pack = ManifestPack(
            id=pack_id, version=_required_text(raw_pack, "version", "pack", issues)
        )

    raw_bindings = data.get("bindings")
    if not isinstance(raw_bindings, list):
        issues.append("bindings must be an array")
        raw_bindings = []
    elif len(raw_bindings) != 3:
        issues.append("bindings must contain exactly three entries")
    bindings: list[RegistryManifestBinding] = []
    binding_kinds: set[str] = set()
    binding_ids: set[str] = set()
    binding_entities: set[str] = set()
    all_claim_promotions: set[str] = set()
    for index, raw_binding in enumerate(raw_bindings):
        binding = _parse_manifest_binding(
            raw_binding, f"bindings[{index}]", issues
        )
        if binding is None:
            continue
        if binding.game_kind in binding_kinds:
            issues.append(f"bindings[{index}].game_kind is duplicated")
        if binding.game_id in binding_ids:
            issues.append(f"bindings[{index}].game_id is duplicated")
        if binding.registry_entity_ref in binding_entities:
            issues.append(f"bindings[{index}].registry_entity_ref is duplicated")
        binding_kinds.add(binding.game_kind)
        binding_ids.add(binding.game_id)
        binding_entities.add(binding.registry_entity_ref)
        implied_chapters: set[str] = set()
        for claim_ref in binding.registry_claim_refs:
            all_claim_promotions.add(claim_ref.promotion_id)
            source = source_by_promotion.get(claim_ref.promotion_id)
            if source is None:
                issues.append(
                    f"bindings[{index}] claim promotion is absent from sources: "
                    f"{claim_ref.promotion_id}"
                )
            else:
                implied_chapters.add(source.chapter_id)
        if set(binding.source_chapters) != implied_chapters:
            issues.append(
                f"bindings[{index}].source_chapters must exactly match claim promotions"
            )
        bindings.append(binding)
    if len(all_claim_promotions) < 2:
        issues.append("binding claim refs must span at least two promotions")

    omissions = _parse_manifest_omissions(
        data.get("omissions"), "omissions", issues
    )
    omission_entities = {entry.registry_entity_ref for entry in omissions}
    overlap = binding_entities & omission_entities
    if overlap:
        issues.append(f"bindings and omissions overlap: {sorted(overlap)!r}")

    game_only = _parse_game_only(data.get("game_only"), "game_only", issues)
    game_only_ids = {entry.game_id for entry in game_only}
    id_overlap = binding_ids & game_only_ids
    if id_overlap:
        issues.append(f"bindings and game_only share game IDs: {sorted(id_overlap)!r}")

    if issues:
        raise RegistryAdaptationValidationError(tuple(issues))
    return RegistryAdaptationManifest(
        format_version=1,
        adaptation_id=adaptation_id,
        source_registry_id=source_registry_id,
        source_registry_version=source_registry_version,
        sources=tuple(
            sorted(sources, key=lambda source: (source.chapter_id, source.promotion_id))
        ),
        pack=manifest_pack,
        bindings=tuple(
            sorted(bindings, key=lambda binding: (binding.game_kind, binding.game_id))
        ),
        omissions=omissions,
        game_only=game_only,
    )


def _claim_ref_document(claim_ref: RegistryClaimRef) -> dict[str, str]:
    return {
        "promotion_id": claim_ref.promotion_id,
        "source_entity_id": claim_ref.source_entity_id,
        "source_claim_id": claim_ref.source_claim_id,
    }


def registry_adaptation_manifest_to_document(
    manifest: RegistryAdaptationManifest,
) -> dict[str, Any]:
    """Return the canonical JSON-ready manifest document."""

    if not isinstance(manifest, RegistryAdaptationManifest):
        raise TypeError("manifest must be RegistryAdaptationManifest")
    return {
        "format_version": 1,
        "adaptation_id": manifest.adaptation_id,
        "source_registry_id": manifest.source_registry_id,
        "source_registry_version": manifest.source_registry_version,
        "sources": [
            {
                "promotion_id": source.promotion_id,
                "chapter_id": source.chapter_id,
                "chapter_sha256": source.chapter_sha256,
                "extracted_by": source.extracted_by,
                "review_id": source.review_id,
                "reviewed_by": source.reviewed_by,
            }
            for source in manifest.sources
        ],
        "pack": {"id": manifest.pack.id, "version": manifest.pack.version},
        "bindings": [
            {
                "game_kind": binding.game_kind,
                "game_id": binding.game_id,
                "registry_entity_ref": binding.registry_entity_ref,
                "registry_claim_refs": [
                    _claim_ref_document(claim_ref)
                    for claim_ref in binding.registry_claim_refs
                ],
                "source_chapters": list(binding.source_chapters),
                "adaptation_notes": binding.adaptation_notes,
            }
            for binding in manifest.bindings
        ],
        "omissions": [
            {
                "registry_entity_ref": omission.registry_entity_ref,
                "reason": omission.reason,
            }
            for omission in manifest.omissions
        ],
        "game_only": [
            {
                "game_kind": entry.game_kind,
                "game_id": entry.game_id,
                "adaptation_notes": entry.adaptation_notes,
            }
            for entry in manifest.game_only
        ],
    }


def _json_bytes(data: object) -> bytes:
    return (
        json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
        + b"\n"
    )


def registry_pack_to_documents(
    pack: RegistryMicroContentPack,
) -> list[tuple[str, bytes]]:
    """Serialize a registry micro pack to its deterministic nine documents."""

    if not isinstance(pack, RegistryMicroContentPack):
        raise TypeError("pack must be RegistryMicroContentPack")
    return [
        ("pack.json", _json_bytes(pack.pack)),
        ("rooms.json", _json_bytes(list(pack.rooms))),
        ("items.json", _json_bytes(list(pack.items))),
        ("characters.json", _json_bytes(list(pack.characters))),
        ("quests.json", _json_bytes(list(pack.quests))),
        ("dialogues.json", _json_bytes(list(pack.dialogues))),
        ("monsters.json", _json_bytes(list(pack.monsters))),
        ("shops.json", _json_bytes(list(pack.shops))),
        (
            _MANIFEST_FILENAME,
            _json_bytes(registry_adaptation_manifest_to_document(pack.manifest)),
        ),
    ]


def _validate_registry_documents(documents: list[tuple[str, bytes]]) -> None:
    names = [name for name, _ in documents]
    if len(names) != len(set(names)):
        raise RegistryCompilationError(("documents contain duplicate filenames",))
    if set(names) != _ALLOWED_FILES:
        missing = sorted(_ALLOWED_FILES - set(names))
        extra = sorted(set(names) - _ALLOWED_FILES)
        issues: list[str] = []
        if missing:
            issues.append(f"documents are missing files: {missing!r}")
        if extra:
            issues.append(f"documents contain extra files: {extra!r}")
        raise RegistryCompilationError(tuple(issues))
    parsed: dict[str, object] = {}
    for name, payload in documents:
        path = PurePath(name)
        if path.is_absolute() or len(path.parts) != 1 or ".." in path.parts:
            raise RegistryCompilationError((f"document filename escapes output: {name}",))
        if not isinstance(payload, bytes):
            raise RegistryCompilationError((f"{name} payload must be bytes",))
        try:
            parsed[name] = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RegistryCompilationError(
                (f"{name} is not valid UTF-8 JSON: {exc}",)
            ) from exc
    if not isinstance(parsed["pack.json"], dict):
        raise RegistryCompilationError(("pack.json root must be an object",))
    for name in _ALLOWED_FILES - {"pack.json", _MANIFEST_FILENAME}:
        if not isinstance(parsed[name], list):
            raise RegistryCompilationError((f"{name} root must be an array",))
    validate_registry_adaptation_manifest_document(parsed[_MANIFEST_FILENAME])


def write_registry_micro_pack(
    pack: RegistryMicroContentPack, output_dir: str | os.PathLike[str]
) -> Path:
    """Atomically publish a validated registry micro pack without overwriting."""

    output = Path(output_dir)
    documents = registry_pack_to_documents(pack)
    _validate_registry_documents(documents)
    manifest_document = json.loads(
        next(payload for name, payload in documents if name == _MANIFEST_FILENAME)
    )
    if validate_registry_adaptation_manifest_document(manifest_document) != pack.manifest:
        raise RegistryAdaptationValidationError(
            ("serialized manifest does not match the pack manifest",)
        )

    if os.path.lexists(str(output)):
        raise FileExistsError(f"output already exists: {output}")
    parent = output.resolve().parent
    if not parent.is_dir():
        raise FileNotFoundError(f"output parent does not exist: {parent}")

    staging = Path(tempfile.mkdtemp(dir=parent, prefix=".l2w_registry_adaptation_"))
    try:
        for filename, payload in documents:
            with open(staging / filename, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())

        load_content_pack(staging)
        with open(staging / _MANIFEST_FILENAME, encoding="utf-8") as stream:
            staged_manifest = validate_registry_adaptation_manifest_document(
                json.load(stream)
            )
        if staged_manifest != pack.manifest:
            raise RegistryAdaptationValidationError(
                ("staged manifest does not match the pack manifest",)
            )

        if os.path.lexists(str(output)):
            raise FileExistsError(f"output was created before publish: {output}")
        os.replace(str(staging), str(output))
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return output.resolve()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compile a micro content pack from CanonRegistry + explicit plan."
    )
    parser.add_argument("--canon-registry", required=True)
    parser.add_argument("--adaptation-plan", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    try:
        with open(args.canon_registry, encoding="utf-8") as stream:
            registry = validate_canon_registry_document(json.load(stream))
        with open(args.adaptation_plan, encoding="utf-8") as stream:
            plan = validate_registry_adaptation_plan(json.load(stream))
        pack = compile_registry_micro_pack(registry, plan)
        write_registry_micro_pack(pack, args.output_dir)
    except json.JSONDecodeError as exc:
        print(f"JSON parse error: {exc}", file=sys.stderr)
        return 1
    except UnicodeDecodeError as exc:
        print(f"UTF-8 decode error: {exc}", file=sys.stderr)
        return 1
    except CanonRegistryValidationError as exc:
        print(f"CanonRegistry error: {exc}", file=sys.stderr)
        return 1
    except RegistryAdaptationValidationError as exc:
        print(f"Registry adaptation error: {exc}", file=sys.stderr)
        return 1
    except RegistryCompilationError as exc:
        print(f"Compilation error: {exc}", file=sys.stderr)
        return 1
    except ContentValidationError as exc:
        print(f"Content validation error: {exc}", file=sys.stderr)
        return 1
    except (FileExistsError, FileNotFoundError, OSError) as exc:
        print(f"I/O error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
