"""Build a deterministic read-only inspection report from a CanonRegistry.

Public API::

    validate_registry_inspection_plan(data) -> RegistryInspectionPlan
    compile_registry_inspection(registry, plan) -> RegistryInspectionReport
    validate_registry_inspection_report_document(data) -> RegistryInspectionReport
    registry_inspection_report_to_document(report) -> dict
    write_registry_inspection_report(report, output_path) -> Path

CLI::

    python -m pipeline.registry_inspection \
        --canon-registry canon_registry.json \
        --inspection-plan inspection_plan.json \
        --output inspection_report.json

The plan selects exact registry entity IDs. The compiler copies the selected
entities without search, inference, conflict resolution, or registry mutation.
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
from typing import Any

from pipeline.canon import (
    CanonBooleanValue,
    CanonClaimValue,
    CanonEnumValue,
    CanonNumericValue,
    CanonRelationValue,
    CanonTextValue,
)
from pipeline.canon_registry import (
    CanonRegistry,
    CanonRegistryValidationError,
    RegistryClaim,
    RegistryClaimSource,
    RegistryEntity,
    RegistryMember,
    RegistrySource,
    canon_registry_to_document,
    validate_canon_registry_document,
)


_STABLE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_CHAPTER_ID_RE = re.compile(r"^chapter_[0-9]{6}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ENTITY_TYPES = frozenset(
    {"character", "location", "organization", "skill", "item", "event"}
)
_SOURCE_SUPPORTS = frozenset({"explicit", "inferred"})
_CERTAINTIES = frozenset({"certain", "uncertain"})


class RegistryInspectionValidationError(ValueError):
    """Raised when an inspection plan or report document is invalid."""

    def __init__(self, issues: tuple[str, ...]) -> None:
        self.issues = issues
        super().__init__("\n".join(f"- {issue}" for issue in issues))


class RegistryInspectionBuildError(ValueError):
    """Raised when a validated registry cannot satisfy an inspection plan."""

    def __init__(self, issues: tuple[str, ...]) -> None:
        self.issues = issues
        super().__init__("\n".join(f"- {issue}" for issue in issues))


@dataclass(frozen=True, slots=True)
class RegistryInspectionPlan:
    format_version: int
    inspection_id: str
    source_registry_id: str
    source_registry_version: int
    entity_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RegistryInspectionReport:
    format_version: int
    inspection_id: str
    source_registry_id: str
    source_registry_version: int
    selected_entity_refs: tuple[str, ...]
    sources: tuple[RegistrySource, ...]
    entities: tuple[RegistryEntity, ...]


def _normalization_key(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold().strip()


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


def _positive_int(
    obj: dict[str, Any], key: str, loc: str, issues: list[str]
) -> int:
    value = obj.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        issues.append(f"{loc}.{key} must be a true int >= 1")
        return 1
    return value


def _required_array(
    obj: dict[str, Any], key: str, loc: str, issues: list[str]
) -> list[Any]:
    value = obj.get(key)
    if not isinstance(value, list):
        issues.append(f"{loc}.{key} must be an array")
        return []
    return value


def _stable_id(value: str, loc: str, issues: list[str]) -> None:
    if value and not _STABLE_ID_RE.fullmatch(value):
        issues.append(f"{loc} must match stable ID format ^[a-z][a-z0-9_]*$")


def _parse_stable_id_array(
    raw: Any,
    loc: str,
    issues: list[str],
    *,
    nonempty: bool,
) -> tuple[str, ...]:
    if not isinstance(raw, list):
        issues.append(f"{loc} must be an array")
        return ()
    if nonempty and not raw:
        issues.append(f"{loc} must not be empty")
    values: list[str] = []
    seen: set[str] = set()
    for index, value in enumerate(raw):
        if not isinstance(value, str) or not value.strip():
            issues.append(f"{loc}[{index}] must be a non-blank string")
            continue
        _stable_id(value, f"{loc}[{index}]", issues)
        if value in seen:
            issues.append(f"{loc}[{index}] duplicates stable ID: {value}")
        seen.add(value)
        values.append(value)
    return tuple(sorted(values))


def _parse_aliases(
    raw: Any, canonical_name: str, loc: str, issues: list[str]
) -> tuple[str, ...]:
    if not isinstance(raw, list):
        issues.append(f"{loc} must be an array")
        return ()
    canonical_key = _normalization_key(canonical_name)
    parsed: list[str] = []
    seen: set[str] = set()
    for index, alias in enumerate(raw):
        if not isinstance(alias, str) or not alias.strip():
            issues.append(f"{loc}[{index}] must be a non-blank string")
            continue
        normalized = _normalization_key(alias)
        if normalized == canonical_key:
            issues.append(f"{loc}[{index}] normalizes to canonical_name")
        elif normalized in seen:
            issues.append(f"{loc}[{index}] is a normalized duplicate: {alias!r}")
        seen.add(normalized)
        parsed.append(alias)
    return tuple(sorted(parsed, key=_normalization_key))


def validate_registry_inspection_plan(data: object) -> RegistryInspectionPlan:
    """Validate and canonically order a RegistryInspectionPlan v1 document."""

    if not isinstance(data, dict):
        raise RegistryInspectionValidationError(("root must be a JSON object",))
    issues: list[str] = []
    _unknown_keys(
        data,
        frozenset(
            {
                "format_version",
                "inspection_id",
                "source_registry_id",
                "source_registry_version",
                "entity_refs",
            }
        ),
        "root",
        issues,
    )
    format_version = data.get("format_version")
    if (
        isinstance(format_version, bool)
        or not isinstance(format_version, int)
        or format_version != 1
    ):
        issues.append("root.format_version must be 1")
    inspection_id = _required_text(data, "inspection_id", "root", issues)
    _stable_id(inspection_id, "root.inspection_id", issues)
    source_registry_id = _required_text(
        data, "source_registry_id", "root", issues
    )
    _stable_id(source_registry_id, "root.source_registry_id", issues)
    source_registry_version = _positive_int(
        data, "source_registry_version", "root", issues
    )
    entity_refs = _parse_stable_id_array(
        data.get("entity_refs"), "root.entity_refs", issues, nonempty=True
    )
    if issues:
        raise RegistryInspectionValidationError(tuple(issues))
    return RegistryInspectionPlan(
        format_version=1,
        inspection_id=inspection_id,
        source_registry_id=source_registry_id,
        source_registry_version=source_registry_version,
        entity_refs=entity_refs,
    )


def registry_inspection_plan_to_document(
    plan: RegistryInspectionPlan,
) -> dict[str, Any]:
    """Serialize a plan using canonical entity-ref ordering."""

    if not isinstance(plan, RegistryInspectionPlan):
        raise TypeError("plan must be RegistryInspectionPlan")
    return {
        "format_version": plan.format_version,
        "inspection_id": plan.inspection_id,
        "source_registry_id": plan.source_registry_id,
        "source_registry_version": plan.source_registry_version,
        "entity_refs": list(sorted(plan.entity_refs)),
    }


def _parse_source(
    raw: Any, index: int, issues: list[str]
) -> RegistrySource | None:
    loc = f"sources[{index}]"
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
    _stable_id(promotion_id, f"{loc}.promotion_id", issues)
    chapter_id = _required_text(raw, "chapter_id", loc, issues)
    if chapter_id and not _CHAPTER_ID_RE.fullmatch(chapter_id):
        issues.append(f"{loc}.chapter_id must match chapter_NNNNNN")
    chapter_sha256 = _required_text(raw, "chapter_sha256", loc, issues)
    if chapter_sha256 and not _SHA256_RE.fullmatch(chapter_sha256):
        issues.append(f"{loc}.chapter_sha256 must be 64 lowercase hex characters")
    extracted_by = _required_text(raw, "extracted_by", loc, issues)
    review_id = _required_text(raw, "review_id", loc, issues)
    _stable_id(review_id, f"{loc}.review_id", issues)
    reviewed_by = _required_text(raw, "reviewed_by", loc, issues)
    return RegistrySource(
        promotion_id=promotion_id,
        chapter_id=chapter_id,
        chapter_sha256=chapter_sha256,
        extracted_by=extracted_by,
        review_id=review_id,
        reviewed_by=reviewed_by,
    )


def _parse_claim_value(
    raw: Any, loc: str, issues: list[str]
) -> CanonClaimValue | None:
    if not isinstance(raw, dict):
        issues.append(f"{loc} must be an object")
        return None
    kind = raw.get("kind")
    if kind == "text":
        _unknown_keys(raw, frozenset({"kind", "text"}), loc, issues)
        return CanonTextValue(text=_required_text(raw, "text", loc, issues))
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
            issues.append(f"{loc}.number must be a finite JSON number; bool is rejected")
            number = 0
        if "unit" not in raw:
            issues.append(f"{loc}.unit is required")
        unit = raw.get("unit")
        if unit is not None:
            if not isinstance(unit, str) or not unit.strip():
                issues.append(f"{loc}.unit must be null or a non-blank string")
                unit = None
            else:
                _stable_id(unit, f"{loc}.unit", issues)
        return CanonNumericValue(number=number, unit=unit)
    if kind == "boolean":
        _unknown_keys(raw, frozenset({"kind", "flag"}), loc, issues)
        flag = raw.get("flag")
        if not isinstance(flag, bool):
            issues.append(f"{loc}.flag must be boolean")
            flag = False
        return CanonBooleanValue(flag=flag)
    if kind == "enum":
        _unknown_keys(raw, frozenset({"kind", "enum_value"}), loc, issues)
        enum_value = _required_text(raw, "enum_value", loc, issues)
        _stable_id(enum_value, f"{loc}.enum_value", issues)
        return CanonEnumValue(enum_value=enum_value)
    issues.append(f"{loc}.kind must be text|relation|numeric|boolean|enum")
    return None


def _parse_member(
    raw: Any, entity_index: int, member_index: int, issues: list[str]
) -> RegistryMember | None:
    loc = f"entities[{entity_index}].members[{member_index}]"
    if not isinstance(raw, dict):
        issues.append(f"{loc} must be an object")
        return None
    _unknown_keys(
        raw,
        frozenset(
            {
                "promotion_id",
                "source_entity_id",
                "source_candidate_id",
                "source_canonical_name",
                "source_aliases",
            }
        ),
        loc,
        issues,
    )
    promotion_id = _required_text(raw, "promotion_id", loc, issues)
    source_entity_id = _required_text(raw, "source_entity_id", loc, issues)
    source_candidate_id = _required_text(raw, "source_candidate_id", loc, issues)
    for field, value in (
        ("promotion_id", promotion_id),
        ("source_entity_id", source_entity_id),
        ("source_candidate_id", source_candidate_id),
    ):
        _stable_id(value, f"{loc}.{field}", issues)
    source_canonical_name = _required_text(
        raw, "source_canonical_name", loc, issues
    )
    source_aliases = _parse_aliases(
        raw.get("source_aliases"),
        source_canonical_name,
        f"{loc}.source_aliases",
        issues,
    )
    return RegistryMember(
        promotion_id=promotion_id,
        source_entity_id=source_entity_id,
        source_candidate_id=source_candidate_id,
        source_canonical_name=source_canonical_name,
        source_aliases=source_aliases,
    )


def _parse_claim(
    raw: Any,
    entity_index: int,
    claim_index: int,
    member_keys: set[tuple[str, str]],
    sources_by_promotion: dict[str, RegistrySource],
    issues: list[str],
) -> RegistryClaim | None:
    loc = f"entities[{entity_index}].claims[{claim_index}]"
    if not isinstance(raw, dict):
        issues.append(f"{loc} must be an object")
        return None
    _unknown_keys(
        raw,
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
        loc,
        issues,
    )
    raw_source = raw.get("source")
    if not isinstance(raw_source, dict):
        issues.append(f"{loc}.source must be an object")
        raw_source = {}
    else:
        _unknown_keys(
            raw_source,
            frozenset({"promotion_id", "source_entity_id", "source_claim_id"}),
            f"{loc}.source",
            issues,
        )
    promotion_id = _required_text(raw_source, "promotion_id", f"{loc}.source", issues)
    source_entity_id = _required_text(
        raw_source, "source_entity_id", f"{loc}.source", issues
    )
    source_claim_id = _required_text(
        raw_source, "source_claim_id", f"{loc}.source", issues
    )
    for field, value in (
        ("promotion_id", promotion_id),
        ("source_entity_id", source_entity_id),
        ("source_claim_id", source_claim_id),
    ):
        _stable_id(value, f"{loc}.source.{field}", issues)
    if (promotion_id, source_entity_id) not in member_keys:
        issues.append(
            f"{loc}.source must match a member of its report entity: "
            f"{(promotion_id, source_entity_id)!r}"
        )
    predicate = _required_text(raw, "predicate", loc, issues)
    _stable_id(predicate, f"{loc}.predicate", issues)
    value = _parse_claim_value(raw.get("value"), f"{loc}.value", issues)

    raw_chapters = raw.get("source_chapters")
    source_chapters: tuple[str, ...] = ()
    if not isinstance(raw_chapters, list) or len(raw_chapters) != 1:
        issues.append(f"{loc}.source_chapters must contain exactly one item")
    else:
        chapter_id = raw_chapters[0]
        if not isinstance(chapter_id, str) or not _CHAPTER_ID_RE.fullmatch(chapter_id):
            issues.append(f"{loc}.source_chapters[0] must match chapter_NNNNNN")
        else:
            source_chapters = (chapter_id,)
            source = sources_by_promotion.get(promotion_id)
            if source is None:
                issues.append(
                    f"{loc}.source.promotion_id has no report source: {promotion_id}"
                )
            elif source.chapter_id != chapter_id:
                issues.append(
                    f"{loc}.source_chapters does not match promotion source chapter"
                )

    source_support = raw.get("source_support")
    if not isinstance(source_support, str) or source_support not in _SOURCE_SUPPORTS:
        issues.append(f"{loc}.source_support must be explicit|inferred")
        source_support = "explicit"
    certainty = raw.get("certainty")
    if not isinstance(certainty, str) or certainty not in _CERTAINTIES:
        issues.append(f"{loc}.certainty must be certain|uncertain")
        certainty = "certain"
    if "inference_basis" not in raw:
        issues.append(f"{loc}.inference_basis is required")
    inference_basis = raw.get("inference_basis")
    if source_support == "explicit":
        if inference_basis is not None:
            issues.append(f"{loc}.inference_basis must be null for explicit support")
            inference_basis = None
    elif not isinstance(inference_basis, str) or not inference_basis.strip():
        issues.append(f"{loc}.inference_basis must be non-blank for inferred support")
        inference_basis = ""
    review_reason = _required_text(raw, "review_reason", loc, issues)
    if value is None:
        return None
    return RegistryClaim(
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


def _parse_entity(
    raw: Any,
    index: int,
    sources_by_promotion: dict[str, RegistrySource],
    issues: list[str],
) -> RegistryEntity | None:
    loc = f"entities[{index}]"
    if not isinstance(raw, dict):
        issues.append(f"{loc} must be an object")
        return None
    _unknown_keys(
        raw,
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
        loc,
        issues,
    )
    entity_id = _required_text(raw, "entity_id", loc, issues)
    _stable_id(entity_id, f"{loc}.entity_id", issues)
    entity_type = raw.get("entity_type")
    if not isinstance(entity_type, str) or entity_type not in _ENTITY_TYPES:
        issues.append(
            f"{loc}.entity_type must be character|location|organization|skill|item|event"
        )
        entity_type = "character"
    canonical_name = _required_text(raw, "canonical_name", loc, issues)
    aliases = _parse_aliases(
        raw.get("aliases"), canonical_name, f"{loc}.aliases", issues
    )

    raw_members = _required_array(raw, "members", loc, issues)
    if not raw_members:
        issues.append(f"{loc}.members must not be empty")
    members: list[RegistryMember] = []
    member_keys: set[tuple[str, str]] = set()
    candidate_keys: set[tuple[str, str]] = set()
    member_promotions: set[str] = set()
    for member_index, raw_member in enumerate(raw_members):
        member = _parse_member(raw_member, index, member_index, issues)
        if member is None:
            continue
        member_key = (member.promotion_id, member.source_entity_id)
        candidate_key = (member.promotion_id, member.source_candidate_id)
        if member_key in member_keys:
            issues.append(f"{loc}.members duplicates member: {member_key!r}")
        if candidate_key in candidate_keys:
            issues.append(f"{loc}.members duplicates candidate: {candidate_key!r}")
        if member.promotion_id in member_promotions:
            issues.append(
                f"{loc}.members contains more than one member from promotion: "
                f"{member.promotion_id}"
            )
        member_keys.add(member_key)
        candidate_keys.add(candidate_key)
        member_promotions.add(member.promotion_id)
        members.append(member)

    raw_claims = _required_array(raw, "claims", loc, issues)
    claims: list[RegistryClaim] = []
    claim_keys: set[tuple[str, str, str]] = set()
    for claim_index, raw_claim in enumerate(raw_claims):
        claim = _parse_claim(
            raw_claim,
            index,
            claim_index,
            member_keys,
            sources_by_promotion,
            issues,
        )
        if claim is None:
            continue
        claim_key = (
            claim.source.promotion_id,
            claim.source.source_entity_id,
            claim.source.source_claim_id,
        )
        if claim_key in claim_keys:
            issues.append(f"{loc}.claims duplicates composite source: {claim_key!r}")
        claim_keys.add(claim_key)
        claims.append(claim)

    merge_reason = _required_text(raw, "merge_reason", loc, issues)
    return RegistryEntity(
        entity_id=entity_id,
        entity_type=entity_type,
        canonical_name=canonical_name,
        aliases=aliases,
        members=tuple(
            sorted(
                members,
                key=lambda item: (item.promotion_id, item.source_entity_id),
            )
        ),
        claims=tuple(
            sorted(
                claims,
                key=lambda item: (
                    item.source.promotion_id,
                    item.source.source_entity_id,
                    item.source.source_claim_id,
                ),
            )
        ),
        merge_reason=merge_reason,
    )


def validate_registry_inspection_report_document(
    data: object,
) -> RegistryInspectionReport:
    """Validate a standalone RegistryInspectionReport v1 document."""

    if not isinstance(data, dict):
        raise RegistryInspectionValidationError(("root must be a JSON object",))
    issues: list[str] = []
    _unknown_keys(
        data,
        frozenset(
            {
                "format_version",
                "inspection_id",
                "source_registry_id",
                "source_registry_version",
                "selected_entity_refs",
                "sources",
                "entities",
            }
        ),
        "root",
        issues,
    )
    format_version = data.get("format_version")
    if (
        isinstance(format_version, bool)
        or not isinstance(format_version, int)
        or format_version != 1
    ):
        issues.append("root.format_version must be 1")
    inspection_id = _required_text(data, "inspection_id", "root", issues)
    _stable_id(inspection_id, "root.inspection_id", issues)
    source_registry_id = _required_text(
        data, "source_registry_id", "root", issues
    )
    _stable_id(source_registry_id, "root.source_registry_id", issues)
    source_registry_version = _positive_int(
        data, "source_registry_version", "root", issues
    )
    selected_entity_refs = _parse_stable_id_array(
        data.get("selected_entity_refs"),
        "root.selected_entity_refs",
        issues,
        nonempty=True,
    )

    raw_sources = _required_array(data, "sources", "root", issues)
    sources: list[RegistrySource] = []
    sources_by_promotion: dict[str, RegistrySource] = {}
    seen_chapters: set[str] = set()
    for index, raw_source in enumerate(raw_sources):
        source = _parse_source(raw_source, index, issues)
        if source is None:
            continue
        if source.promotion_id in sources_by_promotion:
            issues.append(f"sources duplicates promotion_id: {source.promotion_id}")
        if source.chapter_id in seen_chapters:
            issues.append(f"sources duplicates chapter_id: {source.chapter_id}")
        sources_by_promotion[source.promotion_id] = source
        seen_chapters.add(source.chapter_id)
        sources.append(source)

    raw_entities = _required_array(data, "entities", "root", issues)
    if not raw_entities:
        issues.append("root.entities must not be empty")
    entities: list[RegistryEntity] = []
    entity_ids: set[str] = set()
    global_member_keys: set[tuple[str, str]] = set()
    global_candidate_keys: set[tuple[str, str]] = set()
    global_claim_keys: set[tuple[str, str, str]] = set()
    used_promotions: set[str] = set()
    for index, raw_entity in enumerate(raw_entities):
        entity = _parse_entity(raw_entity, index, sources_by_promotion, issues)
        if entity is None:
            continue
        if entity.entity_id in entity_ids:
            issues.append(f"entities duplicates entity_id: {entity.entity_id}")
        entity_ids.add(entity.entity_id)
        for member in entity.members:
            member_key = (member.promotion_id, member.source_entity_id)
            candidate_key = (member.promotion_id, member.source_candidate_id)
            if member_key in global_member_keys:
                issues.append(f"entities reuse member provenance: {member_key!r}")
            if candidate_key in global_candidate_keys:
                issues.append(f"entities reuse candidate provenance: {candidate_key!r}")
            global_member_keys.add(member_key)
            global_candidate_keys.add(candidate_key)
        for claim in entity.claims:
            claim_key = (
                claim.source.promotion_id,
                claim.source.source_entity_id,
                claim.source.source_claim_id,
            )
            if claim_key in global_claim_keys:
                issues.append(f"entities reuse claim provenance: {claim_key!r}")
            global_claim_keys.add(claim_key)
            used_promotions.add(claim.source.promotion_id)
        entities.append(entity)

    if set(selected_entity_refs) != entity_ids:
        issues.append(
            "selected_entity_refs must exactly equal report entity IDs: "
            f"selected={sorted(selected_entity_refs)}, entities={sorted(entity_ids)}"
        )
    source_promotions = set(sources_by_promotion)
    if source_promotions != used_promotions:
        issues.append(
            "sources must exactly cover promotions used by selected claims: "
            f"sources={sorted(source_promotions)}, claims={sorted(used_promotions)}"
        )

    if issues:
        raise RegistryInspectionValidationError(tuple(issues))
    return RegistryInspectionReport(
        format_version=1,
        inspection_id=inspection_id,
        source_registry_id=source_registry_id,
        source_registry_version=source_registry_version,
        selected_entity_refs=selected_entity_refs,
        sources=tuple(
            sorted(sources, key=lambda item: (item.chapter_id, item.promotion_id))
        ),
        entities=tuple(sorted(entities, key=lambda item: item.entity_id)),
    )


def registry_inspection_report_to_document(
    report: RegistryInspectionReport,
) -> dict[str, Any]:
    """Serialize a report with the CanonRegistry canonical nested ordering."""

    if not isinstance(report, RegistryInspectionReport):
        raise TypeError("report must be RegistryInspectionReport")
    registry_document = canon_registry_to_document(
        CanonRegistry(
            format_version=1,
            registry_id=report.source_registry_id,
            registry_version=report.source_registry_version,
            sources=report.sources,
            entities=report.entities,
        )
    )
    return {
        "format_version": report.format_version,
        "inspection_id": report.inspection_id,
        "source_registry_id": report.source_registry_id,
        "source_registry_version": report.source_registry_version,
        "selected_entity_refs": list(sorted(report.selected_entity_refs)),
        "sources": registry_document["sources"],
        "entities": registry_document["entities"],
    }


def compile_registry_inspection(
    registry: CanonRegistry, plan: RegistryInspectionPlan
) -> RegistryInspectionReport:
    """Select exact registry entities and copy them into a read-only report."""

    if not isinstance(registry, CanonRegistry):
        raise RegistryInspectionBuildError(("registry must be CanonRegistry",))
    if not isinstance(plan, RegistryInspectionPlan):
        raise RegistryInspectionBuildError(("plan must be RegistryInspectionPlan",))

    issues: list[str] = []
    try:
        normalized_registry = validate_canon_registry_document(
            canon_registry_to_document(registry)
        )
    except (AttributeError, TypeError) as exc:
        raise RegistryInspectionBuildError(
            (f"invalid typed source registry: {exc}",)
        ) from exc
    except CanonRegistryValidationError as exc:
        raise RegistryInspectionBuildError(
            tuple(f"invalid source registry: {issue}" for issue in exc.issues)
        ) from exc
    if normalized_registry != registry:
        issues.append("registry must already use canonical validated ordering")
    try:
        normalized_plan = validate_registry_inspection_plan(
            registry_inspection_plan_to_document(plan)
        )
    except (AttributeError, TypeError) as exc:
        raise RegistryInspectionBuildError(
            (f"invalid typed inspection plan: {exc}",)
        ) from exc
    except RegistryInspectionValidationError as exc:
        raise RegistryInspectionBuildError(
            tuple(f"invalid inspection plan: {issue}" for issue in exc.issues)
        ) from exc
    if normalized_plan != plan:
        issues.append("plan must already use canonical validated ordering")
    if plan.source_registry_id != registry.registry_id:
        issues.append(
            "plan source_registry_id does not match registry: "
            f"{plan.source_registry_id!r} != {registry.registry_id!r}"
        )
    if plan.source_registry_version != registry.registry_version:
        issues.append(
            "plan source_registry_version does not match registry: "
            f"{plan.source_registry_version} != {registry.registry_version}"
        )

    entities_by_id = {entity.entity_id: entity for entity in registry.entities}
    missing = sorted(set(plan.entity_refs) - set(entities_by_id))
    if missing:
        issues.append(f"plan selects unknown registry entity IDs: {missing}")
    if issues:
        raise RegistryInspectionBuildError(tuple(issues))

    selected_entities = tuple(entities_by_id[ref] for ref in plan.entity_refs)
    used_promotions = {
        claim.source.promotion_id
        for entity in selected_entities
        for claim in entity.claims
    }
    sources_by_promotion = {
        source.promotion_id: source for source in registry.sources
    }
    missing_sources = sorted(used_promotions - set(sources_by_promotion))
    if missing_sources:
        raise RegistryInspectionBuildError(
            (f"selected claims reference missing registry sources: {missing_sources}",)
        )
    report = RegistryInspectionReport(
        format_version=1,
        inspection_id=plan.inspection_id,
        source_registry_id=registry.registry_id,
        source_registry_version=registry.registry_version,
        selected_entity_refs=plan.entity_refs,
        sources=tuple(
            sorted(
                (sources_by_promotion[promotion_id] for promotion_id in used_promotions),
                key=lambda item: (item.chapter_id, item.promotion_id),
            )
        ),
        entities=selected_entities,
    )
    try:
        revalidated = validate_registry_inspection_report_document(
            registry_inspection_report_to_document(report)
        )
    except RegistryInspectionValidationError as exc:
        raise RegistryInspectionBuildError(
            tuple(f"generated report is invalid: {issue}" for issue in exc.issues)
        ) from exc
    if revalidated != report:
        raise RegistryInspectionBuildError(
            ("generated report changed during canonical revalidation",)
        )
    return report


def write_registry_inspection_report(
    report: RegistryInspectionReport, output_path: str | os.PathLike[str]
) -> Path:
    """Atomically write a validated report and preserve old output on failure."""

    try:
        document = registry_inspection_report_to_document(report)
    except (AttributeError, TypeError) as exc:
        raise RegistryInspectionValidationError(
            (f"invalid typed inspection report: {exc}",)
        ) from exc
    revalidated = validate_registry_inspection_report_document(document)
    if revalidated != report:
        raise RegistryInspectionValidationError(
            ("report changed during canonical revalidation",)
        )

    output = Path(output_path)
    parent = Path(os.path.abspath(output)).parent
    if not parent.is_dir():
        raise FileNotFoundError(f"output parent does not exist: {parent}")
    payload = (
        json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
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
        return (
            os.path.exists(first_real)
            and os.path.exists(second_real)
            and os.path.samefile(first_real, second_real)
        )
    except OSError:
        return False


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for deterministic registry inspection."""

    parser = argparse.ArgumentParser(
        description="Build a deterministic read-only CanonRegistry inspection report."
    )
    parser.add_argument(
        "--canon-registry", required=True, help="CanonRegistry v1 JSON input path"
    )
    parser.add_argument(
        "--inspection-plan",
        required=True,
        help="RegistryInspectionPlan v1 JSON input path",
    )
    parser.add_argument(
        "--output", required=True, help="RegistryInspectionReport v1 JSON output path"
    )
    args = parser.parse_args(argv)

    inputs = [args.canon_registry, args.inspection_plan]
    for index, first in enumerate(inputs):
        for second in inputs[index + 1 :]:
            if _same_path(first, second):
                print(
                    f"Input paths point to the same file: {first} and {second}",
                    file=sys.stderr,
                )
                return 1
        if _same_path(args.output, first):
            print(
                f"Output ({args.output}) points to an input file ({first})",
                file=sys.stderr,
            )
            return 1

    try:
        with open(args.canon_registry, "r", encoding="utf-8") as handle:
            registry = validate_canon_registry_document(json.load(handle))
        with open(args.inspection_plan, "r", encoding="utf-8") as handle:
            plan = validate_registry_inspection_plan(json.load(handle))
        report = compile_registry_inspection(registry, plan)
        write_registry_inspection_report(report, args.output)
    except json.JSONDecodeError as exc:
        print(f"JSON parse error: {exc}", file=sys.stderr)
        return 1
    except UnicodeDecodeError as exc:
        print(f"UTF-8 decode error: {exc}", file=sys.stderr)
        return 1
    except CanonRegistryValidationError as exc:
        print(f"CanonRegistry error: {exc}", file=sys.stderr)
        return 1
    except RegistryInspectionValidationError as exc:
        print(f"Registry inspection validation error: {exc}", file=sys.stderr)
        return 1
    except RegistryInspectionBuildError as exc:
        print(f"Registry inspection build error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"I/O error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
