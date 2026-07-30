"""Build a deterministic multi-chapter canon registry from canon drafts.

Public API::

    validate_canon_registry_plan(data) -> CanonRegistryPlan
    build_canon_registry(canon_drafts, plan) -> CanonRegistry
    validate_canon_registry_document(data) -> CanonRegistry
    canon_registry_to_document(registry) -> dict
    write_canon_registry(registry, output_path) -> Path

CLI::

    python -m pipeline.canon_registry \
        --canon-draft chapter_000001.json \
        --canon-draft chapter_000002.json \
        --registry-plan registry_plan.json \
        --output canon_registry.json

Exit codes: 0=success, 1=data/build/I/O error, 2=argument error.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import tempfile
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TypeAlias

from pipeline.canon import (
    CanonBooleanValue,
    CanonClaimValue,
    CanonDraft,
    CanonDraftValidationError,
    CanonEnumValue,
    CanonNumericValue,
    CanonRelationValue,
    CanonTextValue,
    validate_canon_draft_document,
)


class CanonRegistryValidationError(ValueError):
    """Raised when a registry plan or registry document is invalid."""

    def __init__(self, issues: tuple[str, ...]) -> None:
        self.issues = issues
        super().__init__("\n".join(f"- {issue}" for issue in issues))


class CanonRegistryBuildError(ValueError):
    """Raised when validated drafts cannot be assembled under a registry plan."""

    def __init__(self, issues: tuple[str, ...]) -> None:
        self.issues = issues
        super().__init__("\n".join(f"- {issue}" for issue in issues))


_STABLE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_CHAPTER_ID_RE = re.compile(r"^chapter_[0-9]{6}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

EntityType: TypeAlias = Literal[
    "character", "location", "organization", "skill", "item", "event"
]
SourceSupport: TypeAlias = Literal["explicit", "inferred"]
Certainty: TypeAlias = Literal["certain", "uncertain"]

_ENTITY_TYPES = frozenset(
    {"character", "location", "organization", "skill", "item", "event"}
)
_SOURCE_SUPPORTS = frozenset({"explicit", "inferred"})
_CERTAINTIES = frozenset({"certain", "uncertain"})


@dataclass(frozen=True, slots=True)
class RegistryMemberPlan:
    promotion_id: str
    source_entity_id: str


@dataclass(frozen=True, slots=True)
class RegistryEntityPlan:
    entity_id: str
    canonical_name: str
    aliases: tuple[str, ...]
    members: tuple[RegistryMemberPlan, ...]
    merge_reason: str


@dataclass(frozen=True, slots=True)
class CanonRegistryPlan:
    format_version: int
    registry_id: str
    registry_version: int
    entities: tuple[RegistryEntityPlan, ...]


@dataclass(frozen=True, slots=True)
class RegistrySource:
    promotion_id: str
    chapter_id: str
    chapter_sha256: str
    extracted_by: str
    review_id: str
    reviewed_by: str


@dataclass(frozen=True, slots=True)
class RegistryMember:
    promotion_id: str
    source_entity_id: str
    source_candidate_id: str
    source_canonical_name: str
    source_aliases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RegistryClaimSource:
    promotion_id: str
    source_entity_id: str
    source_claim_id: str


@dataclass(frozen=True, slots=True)
class RegistryClaim:
    source: RegistryClaimSource
    predicate: str
    value: CanonClaimValue
    source_chapters: tuple[str, ...]
    source_support: SourceSupport
    certainty: Certainty
    inference_basis: str | None
    review_reason: str


@dataclass(frozen=True, slots=True)
class RegistryEntity:
    entity_id: str
    entity_type: EntityType
    canonical_name: str
    aliases: tuple[str, ...]
    members: tuple[RegistryMember, ...]
    claims: tuple[RegistryClaim, ...]
    merge_reason: str


@dataclass(frozen=True, slots=True)
class CanonRegistry:
    format_version: int
    registry_id: str
    registry_version: int
    sources: tuple[RegistrySource, ...]
    entities: tuple[RegistryEntity, ...]


def _normalization_key(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold().strip()


def _unknown_keys(
    obj: dict[str, Any], allowed: frozenset[str], loc: str, issues: list[str]
) -> None:
    for key in sorted(set(obj) - allowed):
        issues.append(f"{loc} 包含未知字段：{key}")


def _required_text(
    obj: dict[str, Any], key: str, loc: str, issues: list[str]
) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        issues.append(f"{loc}.{key} 必须是非空白字符串")
        return ""
    return value


def _stable_id(value: str, loc: str, issues: list[str]) -> None:
    if value and not _STABLE_ID_RE.fullmatch(value):
        issues.append(f"{loc} 必须匹配稳定 ID 格式 ^[a-z][a-z0-9_]*$")


def _required_array(
    obj: dict[str, Any], key: str, loc: str, issues: list[str]
) -> list[Any]:
    value = obj.get(key)
    if not isinstance(value, list):
        issues.append(f"{loc}.{key} 必须是数组")
        return []
    return value


def _positive_int(
    obj: dict[str, Any], key: str, loc: str, issues: list[str]
) -> int:
    value = obj.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        issues.append(f"{loc}.{key} 必须是 >= 1 的真正 int")
        return 1
    return value


def _aliases(
    raw: Any, canonical_name: str, loc: str, issues: list[str]
) -> tuple[str, ...]:
    if not isinstance(raw, list):
        issues.append(f"{loc} 必须是数组")
        return ()

    canonical_key = _normalization_key(canonical_name)
    seen: set[str] = set()
    parsed: list[str] = []
    for index, alias in enumerate(raw):
        if not isinstance(alias, str) or not alias.strip():
            issues.append(f"{loc}[{index}] 必须是非空白字符串")
            continue
        normalized = _normalization_key(alias)
        if normalized == canonical_key:
            issues.append(f"{loc}[{index}] 规范化后等于 canonical_name")
        elif normalized in seen:
            issues.append(f"{loc}[{index}] 规范化后重复：{alias!r}")
        else:
            seen.add(normalized)
        parsed.append(alias)
    return tuple(sorted(parsed, key=_normalization_key))


def validate_canon_registry_plan(data: object) -> CanonRegistryPlan:
    """Validate a parsed RegistryPlan v1 document."""

    issues: list[str] = []
    if not isinstance(data, dict):
        raise CanonRegistryValidationError(("根对象必须是 JSON 对象",))

    _unknown_keys(
        data,
        frozenset({"format_version", "registry_id", "registry_version", "entities"}),
        "根对象",
        issues,
    )
    format_version = data.get("format_version")
    if (
        isinstance(format_version, bool)
        or not isinstance(format_version, int)
        or format_version != 1
    ):
        issues.append("根对象.format_version 必须为 1")

    registry_id = _required_text(data, "registry_id", "根对象", issues)
    _stable_id(registry_id, "根对象.registry_id", issues)
    registry_version = _positive_int(data, "registry_version", "根对象", issues)
    raw_entities = _required_array(data, "entities", "根对象", issues)
    if not raw_entities:
        issues.append("根对象.entities 不得为空数组")

    parsed_entities: list[RegistryEntityPlan] = []
    seen_entity_ids: set[str] = set()
    seen_members: set[tuple[str, str]] = set()

    for entity_index, raw_entity in enumerate(raw_entities):
        entity_loc = f"entities[{entity_index}]"
        if not isinstance(raw_entity, dict):
            issues.append(f"{entity_loc} 必须是对象")
            continue
        _unknown_keys(
            raw_entity,
            frozenset(
                {"entity_id", "canonical_name", "aliases", "members", "merge_reason"}
            ),
            entity_loc,
            issues,
        )
        entity_id = _required_text(raw_entity, "entity_id", entity_loc, issues)
        _stable_id(entity_id, f"{entity_loc}.entity_id", issues)
        if entity_id in seen_entity_ids:
            issues.append(f"{entity_loc}.entity_id 重复：{entity_id}")
        seen_entity_ids.add(entity_id)

        canonical_name = _required_text(
            raw_entity, "canonical_name", entity_loc, issues
        )
        aliases = _aliases(
            raw_entity.get("aliases"),
            canonical_name,
            f"{entity_loc}.aliases",
            issues,
        )
        merge_reason = _required_text(
            raw_entity, "merge_reason", entity_loc, issues
        )
        raw_members = _required_array(raw_entity, "members", entity_loc, issues)
        if not raw_members:
            issues.append(f"{entity_loc}.members 不得为空数组")

        parsed_members: list[RegistryMemberPlan] = []
        local_members: set[tuple[str, str]] = set()
        local_promotions: set[str] = set()
        for member_index, raw_member in enumerate(raw_members):
            member_loc = f"{entity_loc}.members[{member_index}]"
            if not isinstance(raw_member, dict):
                issues.append(f"{member_loc} 必须是对象")
                continue
            _unknown_keys(
                raw_member,
                frozenset({"promotion_id", "source_entity_id"}),
                member_loc,
                issues,
            )
            promotion_id = _required_text(
                raw_member, "promotion_id", member_loc, issues
            )
            source_entity_id = _required_text(
                raw_member, "source_entity_id", member_loc, issues
            )
            _stable_id(promotion_id, f"{member_loc}.promotion_id", issues)
            _stable_id(source_entity_id, f"{member_loc}.source_entity_id", issues)
            member_key = (promotion_id, source_entity_id)
            if member_key in local_members:
                issues.append(f"{member_loc} 在当前 entity 内重复：{member_key!r}")
            if promotion_id in local_promotions:
                issues.append(
                    f"{member_loc}.promotion_id 在当前 entity 内重复：{promotion_id}"
                )
            if member_key in seen_members:
                issues.append(f"{member_loc} 被多个 registry entity 重复映射：{member_key!r}")
            local_members.add(member_key)
            local_promotions.add(promotion_id)
            seen_members.add(member_key)
            parsed_members.append(
                RegistryMemberPlan(
                    promotion_id=promotion_id,
                    source_entity_id=source_entity_id,
                )
            )

        parsed_entities.append(
            RegistryEntityPlan(
                entity_id=entity_id,
                canonical_name=canonical_name,
                aliases=aliases,
                members=tuple(
                    sorted(
                        parsed_members,
                        key=lambda member: (
                            member.promotion_id,
                            member.source_entity_id,
                        ),
                    )
                ),
                merge_reason=merge_reason,
            )
        )

    if issues:
        raise CanonRegistryValidationError(tuple(issues))

    return CanonRegistryPlan(
        format_version=1,
        registry_id=registry_id,
        registry_version=registry_version,
        entities=tuple(sorted(parsed_entities, key=lambda entity: entity.entity_id)),
    )


def build_canon_registry(
    canon_drafts: Sequence[CanonDraft], plan: CanonRegistryPlan
) -> CanonRegistry:
    """Build a registry without inferring identity or resolving claim conflicts."""

    if isinstance(canon_drafts, (str, bytes)) or not isinstance(canon_drafts, Sequence):
        raise CanonRegistryBuildError(("canon_drafts 必须是 CanonDraft 序列",))
    if not isinstance(plan, CanonRegistryPlan):
        raise CanonRegistryBuildError(("plan 必须是 CanonRegistryPlan",))

    drafts = tuple(canon_drafts)
    issues: list[str] = []
    if len(drafts) < 2:
        issues.append("L2W-3 至少需要两个 CanonDraft")

    promotion_ids: set[str] = set()
    chapter_ids: set[str] = set()
    source_entities: dict[tuple[str, str], Any] = {}
    sources: list[RegistrySource] = []

    for draft_index, draft in enumerate(drafts):
        if not isinstance(draft, CanonDraft):
            issues.append(f"canon_drafts[{draft_index}] 必须是 CanonDraft")
            continue
        if draft.promotion_id in promotion_ids:
            issues.append(f"CanonDraft promotion_id 重复：{draft.promotion_id}")
        promotion_ids.add(draft.promotion_id)
        if draft.source.chapter_id in chapter_ids:
            issues.append(f"CanonDraft source.chapter_id 重复：{draft.source.chapter_id}")
        chapter_ids.add(draft.source.chapter_id)
        sources.append(
            RegistrySource(
                promotion_id=draft.promotion_id,
                chapter_id=draft.source.chapter_id,
                chapter_sha256=draft.source.chapter_sha256,
                extracted_by=draft.extracted_by,
                review_id=draft.review_id,
                reviewed_by=draft.reviewed_by,
            )
        )
        for entity in draft.entities:
            source_key = (draft.promotion_id, entity.entity_id)
            if source_key in source_entities:
                issues.append(f"CanonDraft source entity 重复：{source_key!r}")
            source_entities[source_key] = entity

    if issues:
        raise CanonRegistryBuildError(tuple(issues))

    source_to_registry: dict[tuple[str, str], str] = {}
    for planned_entity in plan.entities:
        for member in planned_entity.members:
            source_key = (member.promotion_id, member.source_entity_id)
            if source_key in source_to_registry:
                issues.append(f"RegistryPlan member 重复映射：{source_key!r}")
            source_to_registry[source_key] = planned_entity.entity_id

    source_keys = set(source_entities)
    planned_keys = set(source_to_registry)
    missing = source_keys - planned_keys
    extra = planned_keys - source_keys
    if missing:
        issues.append(f"RegistryPlan 缺少 source entity：{sorted(missing)}")
    if extra:
        issues.append(f"RegistryPlan 引用不存在的 source entity：{sorted(extra)}")
    if issues:
        raise CanonRegistryBuildError(tuple(issues))

    registry_entities: list[RegistryEntity] = []
    for planned_entity in plan.entities:
        source_members = [
            (member, source_entities[(member.promotion_id, member.source_entity_id)])
            for member in planned_entity.members
        ]
        entity_types = {source_entity.entity_type for _, source_entity in source_members}
        if len(entity_types) != 1:
            issues.append(
                f"registry entity {planned_entity.entity_id} 合并了不一致的实体类型："
                f"{sorted(entity_types)}"
            )
            continue
        entity_type = next(iter(entity_types))

        members: list[RegistryMember] = []
        claims: list[RegistryClaim] = []
        for member_plan, source_entity in source_members:
            members.append(
                RegistryMember(
                    promotion_id=member_plan.promotion_id,
                    source_entity_id=member_plan.source_entity_id,
                    source_candidate_id=source_entity.source_candidate_id,
                    source_canonical_name=source_entity.canonical_name,
                    source_aliases=tuple(
                        sorted(source_entity.aliases, key=_normalization_key)
                    ),
                )
            )
            for claim in source_entity.claims:
                value = claim.value
                if isinstance(value, CanonRelationValue):
                    relation_key = (member_plan.promotion_id, value.entity_ref)
                    target_entity_id = source_to_registry.get(relation_key)
                    if target_entity_id is None:
                        issues.append(
                            f"relation {relation_key!r} 没有 registry 映射"
                        )
                        continue
                    value = CanonRelationValue(entity_ref=target_entity_id)
                claims.append(
                    RegistryClaim(
                        source=RegistryClaimSource(
                            promotion_id=member_plan.promotion_id,
                            source_entity_id=member_plan.source_entity_id,
                            source_claim_id=claim.claim_id,
                        ),
                        predicate=claim.predicate,
                        value=value,
                        source_chapters=claim.source_chapters,
                        source_support=claim.source_support,
                        certainty=claim.certainty,
                        inference_basis=claim.inference_basis,
                        review_reason=claim.review_reason,
                    )
                )

        registry_entities.append(
            RegistryEntity(
                entity_id=planned_entity.entity_id,
                entity_type=entity_type,
                canonical_name=planned_entity.canonical_name,
                aliases=tuple(
                    sorted(planned_entity.aliases, key=_normalization_key)
                ),
                members=tuple(
                    sorted(
                        members,
                        key=lambda member: (
                            member.promotion_id,
                            member.source_entity_id,
                        ),
                    )
                ),
                claims=tuple(
                    sorted(
                        claims,
                        key=lambda claim: (
                            claim.source.promotion_id,
                            claim.source.source_entity_id,
                            claim.source.source_claim_id,
                        ),
                    )
                ),
                merge_reason=planned_entity.merge_reason,
            )
        )

    if issues:
        raise CanonRegistryBuildError(tuple(issues))

    registry = CanonRegistry(
        format_version=1,
        registry_id=plan.registry_id,
        registry_version=plan.registry_version,
        sources=tuple(
            sorted(sources, key=lambda source: (source.chapter_id, source.promotion_id))
        ),
        entities=tuple(sorted(registry_entities, key=lambda entity: entity.entity_id)),
    )
    try:
        validated = validate_canon_registry_document(
            canon_registry_to_document(registry)
        )
    except CanonRegistryValidationError as exc:
        raise CanonRegistryBuildError(
            (f"生成的 CanonRegistry 未通过自校验：{exc.issues}",)
        ) from None
    if validated != registry:
        raise CanonRegistryBuildError(("生成的 CanonRegistry 规范化后不一致",))
    return registry


def _value_to_document(value: CanonClaimValue) -> dict[str, Any]:
    if isinstance(value, CanonTextValue):
        return {"kind": "text", "text": value.text}
    if isinstance(value, CanonRelationValue):
        return {"kind": "relation", "entity_ref": value.entity_ref}
    if isinstance(value, CanonNumericValue):
        return {"kind": "numeric", "number": value.number, "unit": value.unit}
    if isinstance(value, CanonBooleanValue):
        return {"kind": "boolean", "flag": value.flag}
    if isinstance(value, CanonEnumValue):
        return {"kind": "enum", "enum_value": value.enum_value}
    raise TypeError(f"不支持的 CanonClaimValue：{type(value).__name__}")


def canon_registry_to_document(registry: CanonRegistry) -> dict[str, Any]:
    """Serialize a registry using the canonical deterministic collection order."""

    if not isinstance(registry, CanonRegistry):
        raise TypeError("registry 必须是 CanonRegistry")
    return {
        "format_version": registry.format_version,
        "registry_id": registry.registry_id,
        "registry_version": registry.registry_version,
        "sources": [
            {
                "promotion_id": source.promotion_id,
                "chapter_id": source.chapter_id,
                "chapter_sha256": source.chapter_sha256,
                "extracted_by": source.extracted_by,
                "review_id": source.review_id,
                "reviewed_by": source.reviewed_by,
            }
            for source in sorted(
                registry.sources,
                key=lambda item: (item.chapter_id, item.promotion_id),
            )
        ],
        "entities": [
            {
                "entity_id": entity.entity_id,
                "entity_type": entity.entity_type,
                "canonical_name": entity.canonical_name,
                "aliases": list(sorted(entity.aliases, key=_normalization_key)),
                "members": [
                    {
                        "promotion_id": member.promotion_id,
                        "source_entity_id": member.source_entity_id,
                        "source_candidate_id": member.source_candidate_id,
                        "source_canonical_name": member.source_canonical_name,
                        "source_aliases": list(
                            sorted(member.source_aliases, key=_normalization_key)
                        ),
                    }
                    for member in sorted(
                        entity.members,
                        key=lambda item: (
                            item.promotion_id,
                            item.source_entity_id,
                        ),
                    )
                ],
                "claims": [
                    {
                        "source": {
                            "promotion_id": claim.source.promotion_id,
                            "source_entity_id": claim.source.source_entity_id,
                            "source_claim_id": claim.source.source_claim_id,
                        },
                        "predicate": claim.predicate,
                        "value": _value_to_document(claim.value),
                        "source_chapters": list(claim.source_chapters),
                        "source_support": claim.source_support,
                        "certainty": claim.certainty,
                        "inference_basis": claim.inference_basis,
                        "review_reason": claim.review_reason,
                    }
                    for claim in sorted(
                        entity.claims,
                        key=lambda item: (
                            item.source.promotion_id,
                            item.source.source_entity_id,
                            item.source.source_claim_id,
                        ),
                    )
                ],
                "merge_reason": entity.merge_reason,
            }
            for entity in sorted(registry.entities, key=lambda item: item.entity_id)
        ],
    }


def _parse_claim_value(
    raw: Any, loc: str, issues: list[str]
) -> CanonClaimValue | None:
    if not isinstance(raw, dict):
        issues.append(f"{loc} 必须是对象")
        return None
    kind = raw.get("kind")
    if kind == "text":
        _unknown_keys(raw, frozenset({"kind", "text"}), loc, issues)
        text = _required_text(raw, "text", loc, issues)
        return CanonTextValue(text=text)
    if kind == "relation":
        _unknown_keys(raw, frozenset({"kind", "entity_ref"}), loc, issues)
        entity_ref = _required_text(raw, "entity_ref", loc, issues)
        _stable_id(entity_ref, f"{loc}.entity_ref", issues)
        return CanonRelationValue(entity_ref=entity_ref)
    if kind == "numeric":
        _unknown_keys(raw, frozenset({"kind", "number", "unit"}), loc, issues)
        number = raw.get("number")
        if (
            isinstance(number, bool)
            or not isinstance(number, (int, float))
            or (isinstance(number, float) and not math.isfinite(number))
        ):
            issues.append(f"{loc}.number 必须是有限 JSON 数字（bool 拒绝）")
            number = 0
        if "unit" not in raw:
            issues.append(f"{loc}.unit 是必填字段")
        unit = raw.get("unit")
        if unit is not None:
            if not isinstance(unit, str) or not unit.strip():
                issues.append(f"{loc}.unit 必须是 null 或非空白字符串")
                unit = None
            else:
                _stable_id(unit, f"{loc}.unit", issues)
        return CanonNumericValue(number=number, unit=unit)
    if kind == "boolean":
        _unknown_keys(raw, frozenset({"kind", "flag"}), loc, issues)
        flag = raw.get("flag")
        if not isinstance(flag, bool):
            issues.append(f"{loc}.flag 必须是 boolean")
            flag = False
        return CanonBooleanValue(flag=flag)
    if kind == "enum":
        _unknown_keys(raw, frozenset({"kind", "enum_value"}), loc, issues)
        enum_value = _required_text(raw, "enum_value", loc, issues)
        _stable_id(enum_value, f"{loc}.enum_value", issues)
        return CanonEnumValue(enum_value=enum_value)
    issues.append(f"{loc}.kind 必须是 text|relation|numeric|boolean|enum")
    return None


def validate_canon_registry_document(data: object) -> CanonRegistry:
    """Validate a parsed CanonRegistry v1 document and normalize its order."""

    issues: list[str] = []
    if not isinstance(data, dict):
        raise CanonRegistryValidationError(("根对象必须是 JSON 对象",))
    _unknown_keys(
        data,
        frozenset(
            {"format_version", "registry_id", "registry_version", "sources", "entities"}
        ),
        "根对象",
        issues,
    )
    format_version = data.get("format_version")
    if (
        isinstance(format_version, bool)
        or not isinstance(format_version, int)
        or format_version != 1
    ):
        issues.append("根对象.format_version 必须为 1")
    registry_id = _required_text(data, "registry_id", "根对象", issues)
    _stable_id(registry_id, "根对象.registry_id", issues)
    registry_version = _positive_int(data, "registry_version", "根对象", issues)

    raw_sources = _required_array(data, "sources", "根对象", issues)
    if len(raw_sources) < 2:
        issues.append("根对象.sources 至少需要两项")
    sources: list[RegistrySource] = []
    sources_by_promotion: dict[str, RegistrySource] = {}
    seen_chapters: set[str] = set()
    for source_index, raw_source in enumerate(raw_sources):
        source_loc = f"sources[{source_index}]"
        if not isinstance(raw_source, dict):
            issues.append(f"{source_loc} 必须是对象")
            continue
        _unknown_keys(
            raw_source,
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
            source_loc,
            issues,
        )
        promotion_id = _required_text(
            raw_source, "promotion_id", source_loc, issues
        )
        _stable_id(promotion_id, f"{source_loc}.promotion_id", issues)
        chapter_id = _required_text(raw_source, "chapter_id", source_loc, issues)
        if chapter_id and not _CHAPTER_ID_RE.fullmatch(chapter_id):
            issues.append(f"{source_loc}.chapter_id 必须匹配 chapter_NNNNNN")
        chapter_sha256 = _required_text(
            raw_source, "chapter_sha256", source_loc, issues
        )
        if chapter_sha256 and not _SHA256_RE.fullmatch(chapter_sha256):
            issues.append(f"{source_loc}.chapter_sha256 必须是 64 位小写 hex")
        extracted_by = _required_text(
            raw_source, "extracted_by", source_loc, issues
        )
        review_id = _required_text(raw_source, "review_id", source_loc, issues)
        _stable_id(review_id, f"{source_loc}.review_id", issues)
        reviewed_by = _required_text(
            raw_source, "reviewed_by", source_loc, issues
        )
        if promotion_id in sources_by_promotion:
            issues.append(f"{source_loc}.promotion_id 重复：{promotion_id}")
        if chapter_id in seen_chapters:
            issues.append(f"{source_loc}.chapter_id 重复：{chapter_id}")
        seen_chapters.add(chapter_id)
        source = RegistrySource(
            promotion_id=promotion_id,
            chapter_id=chapter_id,
            chapter_sha256=chapter_sha256,
            extracted_by=extracted_by,
            review_id=review_id,
            reviewed_by=reviewed_by,
        )
        sources_by_promotion[promotion_id] = source
        sources.append(source)

    raw_entities = _required_array(data, "entities", "根对象", issues)
    if not raw_entities:
        issues.append("根对象.entities 不得为空数组")

    entity_ids: set[str] = set()
    raw_entity_records: list[
        tuple[dict[str, Any], str, str, str, tuple[str, ...], str]
    ] = []
    for entity_index, raw_entity in enumerate(raw_entities):
        entity_loc = f"entities[{entity_index}]"
        if not isinstance(raw_entity, dict):
            issues.append(f"{entity_loc} 必须是对象")
            continue
        _unknown_keys(
            raw_entity,
            frozenset(
                {
                    "entity_id",
                    "entity_type",
                    "canonical_name",
                    "aliases",
                    "members",
                    "claims",
                    "merge_reason",
                }
            ),
            entity_loc,
            issues,
        )
        entity_id = _required_text(raw_entity, "entity_id", entity_loc, issues)
        _stable_id(entity_id, f"{entity_loc}.entity_id", issues)
        if entity_id in entity_ids:
            issues.append(f"{entity_loc}.entity_id 重复：{entity_id}")
        entity_ids.add(entity_id)
        raw_type = raw_entity.get("entity_type")
        if not isinstance(raw_type, str) or raw_type not in _ENTITY_TYPES:
            issues.append(f"{entity_loc}.entity_type 必须是受支持的实体类型")
            entity_type = "character"
        else:
            entity_type = raw_type
        canonical_name = _required_text(
            raw_entity, "canonical_name", entity_loc, issues
        )
        aliases = _aliases(
            raw_entity.get("aliases"),
            canonical_name,
            f"{entity_loc}.aliases",
            issues,
        )
        merge_reason = _required_text(
            raw_entity, "merge_reason", entity_loc, issues
        )
        if not isinstance(raw_entity.get("members"), list):
            issues.append(f"{entity_loc}.members 必须是数组")
        elif not raw_entity["members"]:
            issues.append(f"{entity_loc}.members 不得为空数组")
        if not isinstance(raw_entity.get("claims"), list):
            issues.append(f"{entity_loc}.claims 必须是数组")
        raw_entity_records.append(
            (
                raw_entity,
                entity_loc,
                entity_id,
                entity_type,
                aliases,
                merge_reason,
            )
        )

    parsed_entities: list[RegistryEntity] = []
    global_members: set[tuple[str, str]] = set()
    global_source_candidates: set[tuple[str, str]] = set()
    global_claims: set[tuple[str, str, str]] = set()
    relation_targets: list[tuple[str, str, str]] = []
    for (
        raw_entity,
        entity_loc,
        entity_id,
        entity_type,
        aliases,
        merge_reason,
    ) in raw_entity_records:
        canonical_name = (
            raw_entity.get("canonical_name")
            if isinstance(raw_entity.get("canonical_name"), str)
            else ""
        )
        members: list[RegistryMember] = []
        local_member_keys: set[tuple[str, str]] = set()
        local_member_promotions: set[str] = set()
        raw_members = raw_entity.get("members")
        if isinstance(raw_members, list):
            for member_index, raw_member in enumerate(raw_members):
                member_loc = f"{entity_loc}.members[{member_index}]"
                if not isinstance(raw_member, dict):
                    issues.append(f"{member_loc} 必须是对象")
                    continue
                _unknown_keys(
                    raw_member,
                    frozenset(
                        {
                            "promotion_id",
                            "source_entity_id",
                            "source_candidate_id",
                            "source_canonical_name",
                            "source_aliases",
                        }
                    ),
                    member_loc,
                    issues,
                )
                promotion_id = _required_text(
                    raw_member, "promotion_id", member_loc, issues
                )
                source_entity_id = _required_text(
                    raw_member, "source_entity_id", member_loc, issues
                )
                source_candidate_id = _required_text(
                    raw_member, "source_candidate_id", member_loc, issues
                )
                _stable_id(promotion_id, f"{member_loc}.promotion_id", issues)
                _stable_id(
                    source_entity_id, f"{member_loc}.source_entity_id", issues
                )
                _stable_id(
                    source_candidate_id,
                    f"{member_loc}.source_candidate_id",
                    issues,
                )
                source_canonical_name = _required_text(
                    raw_member, "source_canonical_name", member_loc, issues
                )
                source_aliases = _aliases(
                    raw_member.get("source_aliases"),
                    source_canonical_name,
                    f"{member_loc}.source_aliases",
                    issues,
                )
                member_key = (promotion_id, source_entity_id)
                source_candidate_key = (promotion_id, source_candidate_id)
                if promotion_id not in sources_by_promotion:
                    issues.append(
                        f"{member_loc}.promotion_id 不存在于 sources：{promotion_id}"
                    )
                if member_key in local_member_keys:
                    issues.append(f"{member_loc} 在当前 entity 内重复：{member_key!r}")
                if promotion_id in local_member_promotions:
                    issues.append(
                        f"{member_loc}.promotion_id 在当前 entity 内重复："
                        f"{promotion_id}"
                    )
                if member_key in global_members:
                    issues.append(f"{member_loc} 被多个 entity 重复使用：{member_key!r}")
                if source_candidate_key in global_source_candidates:
                    issues.append(
                        f"{member_loc}.source_candidate_id 在同一 promotion 中重复："
                        f"{source_candidate_key!r}"
                    )
                local_member_keys.add(member_key)
                local_member_promotions.add(promotion_id)
                global_members.add(member_key)
                global_source_candidates.add(source_candidate_key)
                members.append(
                    RegistryMember(
                        promotion_id=promotion_id,
                        source_entity_id=source_entity_id,
                        source_candidate_id=source_candidate_id,
                        source_canonical_name=source_canonical_name,
                        source_aliases=source_aliases,
                    )
                )

        claims: list[RegistryClaim] = []
        raw_claims = raw_entity.get("claims")
        if isinstance(raw_claims, list):
            for claim_index, raw_claim in enumerate(raw_claims):
                claim_loc = f"{entity_loc}.claims[{claim_index}]"
                if not isinstance(raw_claim, dict):
                    issues.append(f"{claim_loc} 必须是对象")
                    continue
                _unknown_keys(
                    raw_claim,
                    frozenset(
                        {
                            "source",
                            "predicate",
                            "value",
                            "source_chapters",
                            "source_support",
                            "certainty",
                            "inference_basis",
                            "review_reason",
                        }
                    ),
                    claim_loc,
                    issues,
                )
                raw_claim_source = raw_claim.get("source")
                if not isinstance(raw_claim_source, dict):
                    issues.append(f"{claim_loc}.source 必须是对象")
                    raw_claim_source = {}
                else:
                    _unknown_keys(
                        raw_claim_source,
                        frozenset(
                            {"promotion_id", "source_entity_id", "source_claim_id"}
                        ),
                        f"{claim_loc}.source",
                        issues,
                    )
                promotion_id = _required_text(
                    raw_claim_source, "promotion_id", f"{claim_loc}.source", issues
                )
                source_entity_id = _required_text(
                    raw_claim_source,
                    "source_entity_id",
                    f"{claim_loc}.source",
                    issues,
                )
                source_claim_id = _required_text(
                    raw_claim_source,
                    "source_claim_id",
                    f"{claim_loc}.source",
                    issues,
                )
                _stable_id(
                    promotion_id, f"{claim_loc}.source.promotion_id", issues
                )
                _stable_id(
                    source_entity_id,
                    f"{claim_loc}.source.source_entity_id",
                    issues,
                )
                _stable_id(
                    source_claim_id,
                    f"{claim_loc}.source.source_claim_id",
                    issues,
                )
                member_key = (promotion_id, source_entity_id)
                claim_key = (promotion_id, source_entity_id, source_claim_id)
                if member_key not in local_member_keys:
                    issues.append(
                        f"{claim_loc}.source 不属于当前 registry entity 的 members："
                        f"{member_key!r}"
                    )
                if claim_key in global_claims:
                    issues.append(f"{claim_loc}.source 重复：{claim_key!r}")
                global_claims.add(claim_key)

                predicate = _required_text(
                    raw_claim, "predicate", claim_loc, issues
                )
                _stable_id(predicate, f"{claim_loc}.predicate", issues)
                value = _parse_claim_value(
                    raw_claim.get("value"), f"{claim_loc}.value", issues
                )
                if isinstance(value, CanonRelationValue):
                    if value.entity_ref not in entity_ids:
                        issues.append(
                            f"{claim_loc}.value.entity_ref 不存在于 registry："
                            f"{value.entity_ref}"
                        )
                    else:
                        relation_targets.append(
                            (claim_loc, promotion_id, value.entity_ref)
                        )

                raw_chapters = raw_claim.get("source_chapters")
                source_chapters: tuple[str, ...] = ()
                if not isinstance(raw_chapters, list) or len(raw_chapters) != 1:
                    issues.append(f"{claim_loc}.source_chapters 必须恰好包含一项")
                else:
                    chapter_id = raw_chapters[0]
                    if not isinstance(chapter_id, str) or not _CHAPTER_ID_RE.fullmatch(
                        chapter_id
                    ):
                        issues.append(
                            f"{claim_loc}.source_chapters[0] 必须匹配 chapter_NNNNNN"
                        )
                    else:
                        source_chapters = (chapter_id,)
                        source = sources_by_promotion.get(promotion_id)
                        if source is not None and source.chapter_id != chapter_id:
                            issues.append(
                                f"{claim_loc}.source_chapters[0] 必须等于 source promotion "
                                f"{promotion_id} 的 chapter_id {source.chapter_id}"
                            )

                raw_support = raw_claim.get("source_support")
                if not isinstance(raw_support, str) or raw_support not in _SOURCE_SUPPORTS:
                    issues.append(
                        f"{claim_loc}.source_support 必须是 explicit|inferred"
                    )
                    source_support = "explicit"
                else:
                    source_support = raw_support
                raw_certainty = raw_claim.get("certainty")
                if not isinstance(raw_certainty, str) or raw_certainty not in _CERTAINTIES:
                    issues.append(f"{claim_loc}.certainty 必须是 certain|uncertain")
                    certainty = "certain"
                else:
                    certainty = raw_certainty
                if "inference_basis" not in raw_claim:
                    issues.append(f"{claim_loc}.inference_basis 是必填字段")
                inference_basis = raw_claim.get("inference_basis")
                if source_support == "inferred":
                    if not isinstance(inference_basis, str) or not inference_basis.strip():
                        issues.append(
                            f"{claim_loc}.inference_basis 在 inferred 时必须是非空字符串"
                        )
                        inference_basis = None
                elif inference_basis is not None:
                    issues.append(
                        f"{claim_loc}.inference_basis 在 explicit 时必须为 null"
                    )
                    inference_basis = None
                review_reason = _required_text(
                    raw_claim, "review_reason", claim_loc, issues
                )
                if value is not None:
                    claims.append(
                        RegistryClaim(
                            source=RegistryClaimSource(
                                promotion_id=promotion_id,
                                source_entity_id=source_entity_id,
                                source_claim_id=source_claim_id,
                            ),
                            predicate=predicate,
                            value=value,
                            source_chapters=source_chapters,
                            source_support=source_support,
                            certainty=certainty,
                            inference_basis=inference_basis,
                            review_reason=review_reason,
                        )
                    )

        parsed_entities.append(
            RegistryEntity(
                entity_id=entity_id,
                entity_type=entity_type,
                canonical_name=canonical_name,
                aliases=aliases,
                members=tuple(
                    sorted(
                        members,
                        key=lambda member: (
                            member.promotion_id,
                            member.source_entity_id,
                        ),
                    )
                ),
                claims=tuple(
                    sorted(
                        claims,
                        key=lambda claim: (
                            claim.source.promotion_id,
                            claim.source.source_entity_id,
                            claim.source.source_claim_id,
                        ),
                    )
                ),
                merge_reason=merge_reason,
            )
        )

    member_promotion_counts: dict[str, dict[str, int]] = {}
    for entity in parsed_entities:
        promotion_counts = member_promotion_counts.setdefault(entity.entity_id, {})
        for member in entity.members:
            promotion_counts[member.promotion_id] = (
                promotion_counts.get(member.promotion_id, 0) + 1
            )
    for claim_loc, promotion_id, target_entity_id in relation_targets:
        target_count = member_promotion_counts.get(target_entity_id, {}).get(
            promotion_id, 0
        )
        if target_count != 1:
            issues.append(
                f"{claim_loc}.value.entity_ref 的目标 entity 必须恰好包含一个同来源 "
                f"promotion member：{promotion_id!r} -> {target_entity_id!r}"
            )

    unused_sources = set(sources_by_promotion) - {
        promotion_id for promotion_id, _ in global_members
    }
    if unused_sources:
        issues.append(f"sources 包含没有任何 member 的来源：{sorted(unused_sources)}")

    if issues:
        raise CanonRegistryValidationError(tuple(issues))
    return CanonRegistry(
        format_version=1,
        registry_id=registry_id,
        registry_version=registry_version,
        sources=tuple(
            sorted(sources, key=lambda source: (source.chapter_id, source.promotion_id))
        ),
        entities=tuple(sorted(parsed_entities, key=lambda entity: entity.entity_id)),
    )


def write_canon_registry(
    registry: CanonRegistry, output_path: str | os.PathLike[str]
) -> Path:
    """Atomically write a validated registry, preserving old output on failure."""

    document = canon_registry_to_document(registry)
    revalidated = validate_canon_registry_document(document)
    if revalidated != registry:
        raise CanonRegistryValidationError(("registry 规范化后与输入不一致",))

    output = Path(output_path)
    parent = Path(os.path.abspath(output)).parent
    if not parent.is_dir():
        raise FileNotFoundError(f"输出父目录不存在：{parent}")
    payload = (
        json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")

    fd: int | None = None
    tmp_path: str | None = None
    try:
        fd, tmp_path = tempfile.mkstemp(
            dir=parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
        )
        with os.fdopen(fd, "wb") as handle:
            fd = None
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, output)
        tmp_path = None
    except BaseException:
        if fd is not None:
            os.close(fd)
        if tmp_path is not None:
            try:
                os.remove(tmp_path)
            except FileNotFoundError:
                pass
            except OSError:
                pass
        raise
    return output.resolve()


def _same_path(first: str, second: str) -> bool:
    first_real = os.path.realpath(first)
    second_real = os.path.realpath(second)
    if os.path.normcase(first_real) == os.path.normcase(second_real):
        return True
    try:
        return os.path.exists(first_real) and os.path.exists(second_real) and os.path.samefile(
            first_real, second_real
        )
    except OSError:
        return False


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for registry generation."""

    parser = argparse.ArgumentParser(
        description="Build a deterministic canon registry from multiple canon drafts."
    )
    parser.add_argument(
        "--canon-draft",
        action="append",
        required=True,
        help="CanonDraft JSON path; provide at least twice",
    )
    parser.add_argument("--registry-plan", required=True, help="RegistryPlan JSON path")
    parser.add_argument("--output", required=True, help="CanonRegistry JSON output path")
    args = parser.parse_args(argv)
    if len(args.canon_draft) < 2:
        parser.error("--canon-draft 至少需要提供两次")

    input_paths = [*args.canon_draft, args.registry_plan]
    for input_path in input_paths:
        if _same_path(args.output, input_path):
            print(
                f"错误：output ({args.output}) 与输入 ({input_path}) 指向同一文件",
                file=sys.stderr,
            )
            return 1

    try:
        with open(args.registry_plan, "r", encoding="utf-8") as handle:
            plan = validate_canon_registry_plan(json.load(handle))
        drafts: list[CanonDraft] = []
        for draft_path in args.canon_draft:
            with open(draft_path, "r", encoding="utf-8") as handle:
                drafts.append(validate_canon_draft_document(json.load(handle)))
        registry = build_canon_registry(drafts, plan)
        write_canon_registry(registry, args.output)
    except json.JSONDecodeError as exc:
        print(f"JSON 解析错误：{exc}", file=sys.stderr)
        return 1
    except UnicodeDecodeError as exc:
        print(f"UTF-8 解码错误：{exc}", file=sys.stderr)
        return 1
    except CanonDraftValidationError as exc:
        print(f"CanonDraft 错误：{exc}", file=sys.stderr)
        return 1
    except CanonRegistryValidationError as exc:
        print(f"Registry 校验错误：{exc}", file=sys.stderr)
        return 1
    except CanonRegistryBuildError as exc:
        print(f"Registry 构建错误：{exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"I/O 错误：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
