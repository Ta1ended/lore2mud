"""Validate canon promotion plans, build canon drafts from reviewed facts.

Public API::

    validate_canon_promotion_plan(data) -> PromotionPlan
    build_canon_draft(review, candidate_doc, manifest, plan) -> CanonDraft
    validate_canon_draft_document(data) -> CanonDraft

CLI::

    python -m pipeline.canon \\
        --promotion-plan plan.json \\
        --review review.json \\
        --candidate candidate.json \\
        --manifest manifest.json \\
        --output canon_draft.json

Exit codes: 0=success, 1=data/binding/build/I/O error, 2=argument error.
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
from dataclasses import asdict, dataclass
from typing import Any, Literal, TypeAlias

from pipeline.chapter_manifests import ChapterManifest
from pipeline.fact_candidates import (
    FactCandidateDocument,
    TextValue as FCTextValue,
    RelationValue as FCRelationValue,
    NumericValue as FCNumericValue,
    BooleanValue as FCBooleanValue,
    EnumValue as FCEnumValue,
)
from pipeline.fact_reviews import FactReviewDocument

# ── public exceptions ───────────────────────────────────────────────────────


class CanonDraftValidationError(ValueError):
    """Raised when a promotion plan or canon draft fails structural validation."""

    def __init__(self, issues: tuple[str, ...]) -> None:
        self.issues = issues
        super().__init__("\n".join(f"- {i}" for i in issues))


class CanonDraftBuildingError(ValueError):
    """Raised when canon draft building fails (binding/closure/promotion)."""

    def __init__(self, issues: tuple[str, ...]) -> None:
        self.issues = issues
        super().__init__("\n".join(f"- {i}" for i in issues))


# ── type aliases ────────────────────────────────────────────────────────────

_STABLE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_CHAPTER_ID_RE = re.compile(r"^chapter_[0-9]{6}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

EntityType: TypeAlias = Literal[
    "character", "location", "organization", "skill", "item", "event"
]
_ENTITY_TYPES = frozenset({
    "character", "location", "organization", "skill", "item", "event",
})
SourceSupport: TypeAlias = Literal["explicit", "inferred"]
Certainty: TypeAlias = Literal["certain", "uncertain"]
_SOURCE_SUPPORTS = frozenset({"explicit", "inferred"})
_CERTAINTIES = frozenset({"certain", "uncertain"})


# ── canon value tagged union ────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class CanonTextValue:
    kind: Literal["text"] = "text"
    text: str = ""


@dataclass(frozen=True, slots=True)
class CanonRelationValue:
    kind: Literal["relation"] = "relation"
    entity_ref: str = ""


@dataclass(frozen=True, slots=True)
class CanonNumericValue:
    kind: Literal["numeric"] = "numeric"
    number: int | float = 0
    unit: str | None = None


@dataclass(frozen=True, slots=True)
class CanonBooleanValue:
    kind: Literal["boolean"] = "boolean"
    flag: bool = False


@dataclass(frozen=True, slots=True)
class CanonEnumValue:
    kind: Literal["enum"] = "enum"
    enum_value: str = ""


CanonClaimValue = (
    CanonTextValue | CanonRelationValue
    | CanonNumericValue | CanonBooleanValue | CanonEnumValue
)


# ── data models ─────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class EntityPromotionMapping:
    candidate_id: str
    entity_id: str
    canonical_name: str
    aliases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PromotionPlan:
    format_version: int
    promotion_id: str
    source_chapter: str
    review_id: str
    entity_mappings: tuple[EntityPromotionMapping, ...]


@dataclass(frozen=True, slots=True)
class CanonSource:
    chapter_id: str
    chapter_sha256: str


@dataclass(frozen=True, slots=True)
class CanonClaim:
    claim_id: str
    predicate: str
    value: CanonClaimValue
    source_chapters: tuple[str, ...]
    source_support: SourceSupport
    certainty: Certainty
    inference_basis: str | None
    review_reason: str


@dataclass(frozen=True, slots=True)
class CanonEntity:
    entity_id: str
    entity_type: EntityType
    canonical_name: str
    aliases: tuple[str, ...]
    source_candidate_id: str
    claims: tuple[CanonClaim, ...]


@dataclass(frozen=True, slots=True)
class CanonDraft:
    format_version: int
    promotion_id: str
    source: CanonSource
    extracted_by: str
    review_id: str
    reviewed_by: str
    entities: tuple[CanonEntity, ...]


# ── internal helpers ────────────────────────────────────────────────────────


def _check_unknown_keys(
    obj: dict[str, Any], allowed: frozenset[str], loc: str, issues: list[str]
) -> None:
    for key in sorted(set(obj) - allowed):
        issues.append(f"{loc} 包含未知字段：{key}")


def _require_text(
    obj: dict[str, Any], key: str, loc: str, issues: list[str]
) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        issues.append(f"{loc}.{key} 必须是非空白字符串")
        return ""
    return value


def _require_stable_id(value: str, loc: str, issues: list[str]) -> None:
    if value and not _STABLE_ID_RE.fullmatch(value):
        issues.append(f"{loc} 必须匹配稳定 ID 格式 ^[a-z][a-z0-9_]*$")


def _require_array(
    obj: dict[str, Any], key: str, loc: str, issues: list[str]
) -> list[Any]:
    value = obj.get(key)
    if not isinstance(value, list):
        issues.append(f"{loc}.{key} 必须是数组")
        return []
    return value


def _check_alias_dedup(
    aliases: list[str], canonical_name: str, loc: str, issues: list[str]
) -> None:
    seen: set[str] = set()
    canon_normalized = unicodedata.normalize("NFKC", canonical_name).casefold().strip()
    for alias in aliases:
        if not isinstance(alias, str) or not alias.strip():
            issues.append(f"{loc} 中的每个别名必须是非空白字符串")
            continue
        normalized = unicodedata.normalize("NFKC", alias).casefold().strip()
        if normalized == canon_normalized:
            issues.append(f"{loc} 中别名 {alias!r} 规范化后等于 canonical_name")
            continue
        if normalized in seen:
            issues.append(f"{loc} 中存在规范化后重复的别名：{alias!r}")
        else:
            seen.add(normalized)




# ── public entry: validate promotion plan ───────────────────────────────────


def validate_canon_promotion_plan(data: object) -> PromotionPlan:
    """Validate a parsed JSON object as a PromotionPlan."""

    issues: list[str] = []

    if not isinstance(data, dict):
        raise CanonDraftValidationError(("根对象必须是 JSON 对象",))

    allowed = frozenset({
        "format_version", "promotion_id", "source_chapter",
        "review_id", "entity_mappings",
    })
    _check_unknown_keys(data, allowed, "根对象", issues)

    # format_version
    fv = data.get("format_version")
    if fv is None:
        issues.append("format_version 是必填字段")
    elif isinstance(fv, bool) or not isinstance(fv, int):
        issues.append("format_version 必须是真正 int（bool 拒绝）")
    elif fv != 1:
        issues.append(f"format_version 必须为 1，收到 {fv}")

    # promotion_id
    pid = _require_text(data, "promotion_id", "根对象", issues)
    _require_stable_id(pid, "根对象.promotion_id", issues)

    # source_chapter
    raw_sc = data.get("source_chapter")
    if not isinstance(raw_sc, str):
        issues.append("source_chapter 必须是字符串")
    elif not _CHAPTER_ID_RE.fullmatch(raw_sc):
        issues.append(f"source_chapter 必须匹配 ^chapter_[0-9]{{6}}$，收到 {raw_sc!r}")

    # review_id
    rid = _require_text(data, "review_id", "根对象", issues)
    _require_stable_id(rid, "根对象.review_id", issues)

    # entity_mappings
    raw_mappings = _require_array(data, "entity_mappings", "根对象", issues)
    if isinstance(raw_mappings, list) and len(raw_mappings) == 0:
        issues.append("entity_mappings 不得为空数组")

    parsed_mappings: list[EntityPromotionMapping] = []
    seen_candidate: set[str] = set()
    seen_entity: set[str] = set()

    for mi, raw_m in enumerate(raw_mappings):
        mloc = f"entity_mappings[{mi}]"
        if not isinstance(raw_m, dict):
            issues.append(f"{mloc} 必须是对象")
            continue

        allowed_m = frozenset({
            "candidate_id", "entity_id", "canonical_name", "aliases",
        })
        _check_unknown_keys(raw_m, allowed_m, mloc, issues)

        cid = _require_text(raw_m, "candidate_id", mloc, issues)
        _require_stable_id(cid, f"{mloc}.candidate_id", issues)
        if cid in seen_candidate:
            issues.append(f"{mloc}.candidate_id 重复：{cid}")
        seen_candidate.add(cid)

        eid = _require_text(raw_m, "entity_id", mloc, issues)
        _require_stable_id(eid, f"{mloc}.entity_id", issues)
        if eid in seen_entity:
            issues.append(f"{mloc}.entity_id 重复：{eid}")
        seen_entity.add(eid)

        cname = _require_text(raw_m, "canonical_name", mloc, issues)

        raw_aliases = raw_m.get("aliases")
        if not isinstance(raw_aliases, list):
            issues.append(f"{mloc}.aliases 必须是数组")
            raw_aliases_list: list[str] = []
        else:
            raw_aliases_list = []
            for ai, alias in enumerate(raw_aliases):
                if isinstance(alias, str):
                    raw_aliases_list.append(alias)
                else:
                    issues.append(f"{mloc}.aliases[{ai}] 必须是字符串")
            _check_alias_dedup(raw_aliases_list, cname, f"{mloc}.aliases", issues)

        if (
            isinstance(cid, str) and cid.strip()
            and isinstance(eid, str) and eid.strip()
            and isinstance(cname, str) and cname.strip()
        ):
            parsed_mappings.append(EntityPromotionMapping(
                candidate_id=cid,
                entity_id=eid,
                canonical_name=cname,
                aliases=tuple(raw_aliases_list),
            ))

    if issues:
        raise CanonDraftValidationError(tuple(issues))

    return PromotionPlan(
        format_version=1,
        promotion_id=pid,
        source_chapter=raw_sc if isinstance(raw_sc, str) else "",
        review_id=rid,
        entity_mappings=tuple(parsed_mappings),
    )


# ── public entry: build canon draft ─────────────────────────────────────────


def build_canon_draft(
    review: FactReviewDocument,
    candidate_doc: FactCandidateDocument,
    manifest: ChapterManifest,
    plan: PromotionPlan,
) -> CanonDraft:
    """Deterministically build a CanonDraft from validated inputs.

    Raises CanonDraftBuildingError on any failure (binding, closure, etc.).
    """

    issues: list[str] = []

    # 1. Source chapter consistency
    if plan.source_chapter != review.source_chapter:
        issues.append(
            f"plan.source_chapter ({plan.source_chapter}) 必须等于 "
            f"review.source_chapter ({review.source_chapter})"
        )
    if review.source_chapter != candidate_doc.source_chapter:
        issues.append(
            f"review.source_chapter ({review.source_chapter}) 必须等于 "
            f"candidate_doc.source_chapter ({candidate_doc.source_chapter})"
        )
    sc = review.source_chapter

    # 2. plan.review_id match
    if plan.review_id != review.review_id:
        issues.append(
            f"plan.review_id ({plan.review_id}) 必须等于 "
            f"review.review_id ({review.review_id})"
        )

    # 3. Manifest contains chapter
    manifest_ids = {e.chapter_id for e in manifest.chapters}
    if sc not in manifest_ids:
        issues.append(f"source_chapter {sc} 不存在于 manifest 中")
    else:
        # Get SHA-256 for the matching entry
        manifest_sha = ""
        for entry in manifest.chapters:
            if entry.chapter_id == sc:
                manifest_sha = entry.sha256
                break

    if issues:
        raise CanonDraftBuildingError(tuple(issues))

    # 4. Enforce existing binding contracts
    try:
        from pipeline.chapter_manifests import validate_fact_candidate_sources
        validate_fact_candidate_sources(manifest, [candidate_doc])
    except Exception as exc:
        issues.append(
            f"candidate source 绑定失败：{exc}"
        )

    try:
        from pipeline.fact_reviews import validate_fact_review_bindings
        validate_fact_review_bindings(review, candidate_doc)
    except Exception as exc:
        issues.append(
            f"review 绑定失败：{exc}"
        )

    if issues:
        raise CanonDraftBuildingError(tuple(issues))

    # Build candidate_id → claims map
    cand_map: dict[str, set[str]] = {}
    for c in candidate_doc.candidates:
        cand_map[c.candidate_id] = {cl.claim_id for cl in c.claims}
    # Build decision map
    dec_map: dict[tuple[str, str], tuple[str, str]] = {}  # (cid, clid) → (state, reason)
    accepted: set[tuple[str, str]] = set()  # (cid, clid) pairs that are accepted
    accepted_candidates: set[str] = set()  # cids that have ≥1 accepted claim
    for dec in review.decisions:
        dec_map[(dec.candidate_id, dec.claim_id)] = (dec.state, dec.reason)
        if dec.state == "accepted":
            accepted.add((dec.candidate_id, dec.claim_id))
            accepted_candidates.add(dec.candidate_id)

    # 5. Plan → candidate bindings
    plan_map: dict[str, EntityPromotionMapping] = {}
    for mapping in plan.entity_mappings:
        plan_map[mapping.candidate_id] = mapping
        if mapping.candidate_id not in cand_map:
            issues.append(
                f"plan candidate_id {mapping.candidate_id} 不存在于 candidate document 中"
            )

    if issues:
        raise CanonDraftBuildingError(tuple(issues))

    # 6. Promotion closure
    # Direct: candidates with ≥1 accepted claim
    direct_cids = accepted_candidates.copy()
    # Relation targets: accepted relation claims → target candidate_id
    relation_candidate_targets: set[str] = set()
    for (cid, clid) in accepted:
        cand_obj = next((c for c in candidate_doc.candidates if c.candidate_id == cid), None)
        if cand_obj is None:
            continue
        claim_obj = next((cl for cl in cand_obj.claims if cl.claim_id == clid), None)
        if claim_obj is None:
            continue
        if isinstance(claim_obj.value, FCRelationValue):
            relation_candidate_targets.add(claim_obj.value.candidate_ref)

    closure = direct_cids | relation_candidate_targets

    if not closure:
        raise CanonDraftBuildingError((
            "promotion closure 为空：无任何 accepted claim 或 accepted relation",
        ))

    mapped_cids = set(plan_map.keys())
    if mapped_cids != closure:
        missing = closure - mapped_cids
        extra = mapped_cids - closure
        msgs = []
        if missing:
            msgs.append(f"plan 缺少闭包内 mapping：{sorted(missing)}")
        if extra:
            msgs.append(f"plan 包含闭包外冗余 mapping：{sorted(extra)}")
        raise CanonDraftBuildingError(tuple(msgs))

    # 7. Build entity_id → mapping lookup
    entity_to_mapping: dict[str, EntityPromotionMapping] = {}
    candidate_to_entity: dict[str, str] = {}
    for mapping in plan.entity_mappings:
        entity_to_mapping[mapping.entity_id] = mapping
        candidate_to_entity[mapping.candidate_id] = mapping.entity_id

    # 8. Build entities
    parsed_entities: list[CanonEntity] = []

    # Build candidate_id → entity_id sorted by entity_id for deterministic order
    sorted_cids = sorted(closure, key=lambda c: candidate_to_entity[c])

    for cid in sorted_cids:
        mapping = plan_map[cid]
        cand_obj = next(c for c in candidate_doc.candidates if c.candidate_id == cid)
        entity_type = cand_obj.entity_type

        # Collect accepted claims for this candidate
        parsed_claims: list[CanonClaim] = []
        for claim_obj in cand_obj.claims:
            pair = (cid, claim_obj.claim_id)
            if pair in accepted:
                state, reason = dec_map[pair]
                # Parse value, rewriting relation candidate_ref → entity_ref
                if isinstance(claim_obj.value, FCRelationValue):
                    target_cid = claim_obj.value.candidate_ref
                    if target_cid not in candidate_to_entity:
                        issues.append(
                            f"relation claim {claim_obj.claim_id} 的目标 "
                            f"candidate {target_cid} 不存在于 promotion mapping 中"
                        )
                        continue
                    target_eid = candidate_to_entity[target_cid]
                    cv: CanonClaimValue = CanonRelationValue(entity_ref=target_eid)
                elif isinstance(claim_obj.value, FCTextValue):
                    cv = CanonTextValue(text=claim_obj.value.text)
                elif isinstance(claim_obj.value, FCNumericValue):
                    cv = CanonNumericValue(number=claim_obj.value.number, unit=claim_obj.value.unit)
                elif isinstance(claim_obj.value, FCBooleanValue):
                    cv = CanonBooleanValue(flag=claim_obj.value.flag)
                elif isinstance(claim_obj.value, FCEnumValue):
                    cv = CanonEnumValue(enum_value=claim_obj.value.enum_value)
                else:
                    continue

                parsed_claims.append(CanonClaim(
                    claim_id=claim_obj.claim_id,
                    predicate=claim_obj.predicate,
                    value=cv,
                    source_chapters=claim_obj.source_chapters,
                    source_support=claim_obj.source_support,
                    certainty=claim_obj.certainty,
                    inference_basis=claim_obj.inference_basis,
                    review_reason=reason,
                ))

        # Sort claims by claim_id for determinism
        parsed_claims.sort(key=lambda cl: cl.claim_id)

        parsed_entities.append(CanonEntity(
            entity_id=mapping.entity_id,
            entity_type=entity_type,
            canonical_name=mapping.canonical_name,
            aliases=tuple(sorted(
                mapping.aliases,
                key=lambda a: unicodedata.normalize("NFKC", a).casefold().strip(),
            )),
            source_candidate_id=cid,
            claims=tuple(parsed_claims),
        ))

    if issues:
        raise CanonDraftBuildingError(tuple(issues))

    draft = CanonDraft(
        format_version=1,
        promotion_id=plan.promotion_id,
        source=CanonSource(chapter_id=sc, chapter_sha256=manifest_sha),
        extracted_by=candidate_doc.extracted_by,
        review_id=review.review_id,
        reviewed_by=review.reviewed_by,
        entities=tuple(parsed_entities),
    )

    # 9. Validate draft against its own schema
    try:
        validate_canon_draft_document(_sorted_json_dict(draft))
    except CanonDraftValidationError as e:
        raise CanonDraftBuildingError(
            (f"built draft 未通过语义验证: {e.issues}",)
        ) from None

    return draft



def _sorted_json_dict(draft: CanonDraft) -> dict[str, Any]:
    """Serialize CanonDraft to dict with deterministic key/collection order."""
    def sort_claim_value(v: Any) -> Any:
        if isinstance(v, dict) and "kind" in v:
            # kind always first
            return {"kind": v["kind"], **{k: v[k] for k in sorted(v) if k != "kind"}}
        return v

    def sort_claims(cl: Any) -> dict[str, Any]:
        cd = asdict(cl)
        cd["value"] = sort_claim_value(cd["value"])
        return cd

    entities_sorted = sorted(
        (_canon_entity_dict(e) for e in draft.entities),
        key=lambda e: e["entity_id"],
    )

    return {
        "format_version": draft.format_version,
        "promotion_id": draft.promotion_id,
        "source": {
            "chapter_id": draft.source.chapter_id,
            "chapter_sha256": draft.source.chapter_sha256,
        },
        "extracted_by": draft.extracted_by,
        "review_id": draft.review_id,
        "reviewed_by": draft.reviewed_by,
        "entities": entities_sorted,
    }


def _canon_entity_dict(entity: CanonEntity) -> dict[str, Any]:
    claims_sorted = sorted(
        (
            {
                "claim_id": cl.claim_id,
                "predicate": cl.predicate,
                "value": _sorted_value(cl.value),
                "source_chapters": list(cl.source_chapters),
                "source_support": cl.source_support,
                "certainty": cl.certainty,
                "inference_basis": cl.inference_basis,
                "review_reason": cl.review_reason,
            }
            for cl in entity.claims
        ),
        key=lambda c: c["claim_id"],
    )
    aliases_sorted = sorted(
        entity.aliases,
        key=lambda a: unicodedata.normalize("NFKC", a).casefold().strip(),
    )
    return {
        "entity_id": entity.entity_id,
        "entity_type": entity.entity_type,
        "canonical_name": entity.canonical_name,
        "aliases": aliases_sorted,
        "source_candidate_id": entity.source_candidate_id,
        "claims": claims_sorted,
    }


def _sorted_value(v: CanonClaimValue) -> dict[str, Any]:
    if isinstance(v, CanonRelationValue):
        return {"kind": "relation", "entity_ref": v.entity_ref}
    d = asdict(v)
    return {"kind": d["kind"], **{k: d[k] for k in sorted(d) if k != "kind"}}


# ── public entry: validate canon draft document ────────────────────────────


def validate_canon_draft_document(data: object) -> CanonDraft:
    """Validate a parsed JSON object as a CanonDraft.

    Performs full structural and semantic validation.
    """

    issues: list[str] = []

    if not isinstance(data, dict):
        raise CanonDraftValidationError(("根对象必须是 JSON 对象",))

    allowed_root = frozenset({
        "format_version", "promotion_id", "source",
        "extracted_by", "review_id", "reviewed_by", "entities",
    })
    _check_unknown_keys(data, allowed_root, "根对象", issues)

    # format_version
    fv = data.get("format_version")
    if fv is None:
        issues.append("format_version 是必填字段")
    elif isinstance(fv, bool) or not isinstance(fv, int):
        issues.append("format_version 必须是真正 int（bool 拒绝）")
    elif fv != 1:
        issues.append(f"format_version 必须为 1，收到 {fv}")

    # promotion_id
    pid = _require_text(data, "promotion_id", "根对象", issues)
    _require_stable_id(pid, "根对象.promotion_id", issues)

    # source
    raw_source = data.get("source")
    if not isinstance(raw_source, dict):
        issues.append("source 必须是对象")
    else:
        allowed_src = frozenset({"chapter_id", "chapter_sha256"})
        _check_unknown_keys(raw_source, allowed_src, "source", issues)
        src_cid = _require_text(raw_source, "chapter_id", "source", issues)
        if src_cid and not _CHAPTER_ID_RE.fullmatch(src_cid):
            issues.append("source.chapter_id 必须匹配 ^chapter_[0-9]{6}$")
        src_sha = raw_source.get("chapter_sha256")
        if not isinstance(src_sha, str):
            issues.append("source.chapter_sha256 必须是字符串")
        elif not _SHA256_RE.fullmatch(src_sha):
            issues.append("source.chapter_sha256 必须是 64 位小写十六进制")

    # extracted_by
    extracted_by = _require_text(data, "extracted_by", "根对象", issues)

    # review_id
    rid = _require_text(data, "review_id", "根对象", issues)
    _require_stable_id(rid, "根对象.review_id", issues)

    # reviewed_by
    reviewed_by = _require_text(data, "reviewed_by", "根对象", issues)

    # entities
    raw_entities = _require_array(data, "entities", "根对象", issues)
    if isinstance(raw_entities, list) and len(raw_entities) == 0:
        issues.append("entities 不得为空数组")

    parsed_entities: list[CanonEntity] = []
    seen_candidate_ids: set[str] = set()

    # ── Pass 1: collect and validate entity_ids ──────────────────────────
    entity_ids: set[str] = set()
    for ei, raw_entity in enumerate(raw_entities):
        eloc = f"entities[{ei}]"
        if not isinstance(raw_entity, dict):
            issues.append(f"{eloc} 必须是对象")
            continue
        allowed_entity = frozenset({
            "entity_id", "entity_type", "canonical_name",
            "aliases", "source_candidate_id", "claims",
        })
        _check_unknown_keys(raw_entity, allowed_entity, eloc, issues)
        eid = _require_text(raw_entity, "entity_id", eloc, issues)
        _require_stable_id(eid, f"{eloc}.entity_id", issues)
        if eid in entity_ids:
            issues.append(f"{eloc}.entity_id 重复：{eid}")
        entity_ids.add(eid)

    # ── Pass 2: parse entities with claims, using collected entity_ids ───
    seen_candidate_ids = set()
    for ei, raw_entity in enumerate(raw_entities):
        eloc = f"entities[{ei}]"
        if not isinstance(raw_entity, dict):
            continue

        eid = _require_text(raw_entity, "entity_id", eloc, issues)
        _require_stable_id(eid, f"{eloc}.entity_id", issues)

        et = raw_entity.get("entity_type")
        if et not in _ENTITY_TYPES:
            issues.append(f"{eloc}.entity_type 必须是 character|location|...|event")

        cname = _require_text(raw_entity, "canonical_name", eloc, issues)

        raw_aliases = _require_array(raw_entity, "aliases", eloc, issues)
        if isinstance(raw_aliases, list):
            _check_alias_dedup(raw_aliases, cname, f"{eloc}.aliases", issues)

        scid = _require_text(raw_entity, "source_candidate_id", eloc, issues)
        _require_stable_id(scid, f"{eloc}.source_candidate_id", issues)
        if scid in seen_candidate_ids:
            issues.append(f"{eloc}.source_candidate_id 重复：{scid}")
        seen_candidate_ids.add(scid)

        raw_claims = _require_array(raw_entity, "claims", eloc, issues)
        parsed_claims: list[CanonClaim] = []
        seen_claim_ids: set[str] = set()

        for ci, raw_claim in enumerate(raw_claims):
            cloc = f"{eloc}.claims[{ci}]"
            if not isinstance(raw_claim, dict):
                issues.append(f"{cloc} 必须是对象")
                continue

            allowed_claim = frozenset({
                "claim_id", "predicate", "value",
                "source_chapters", "source_support", "certainty",
                "inference_basis", "review_reason",
            })
            _check_unknown_keys(raw_claim, allowed_claim, cloc, issues)

            clid = _require_text(raw_claim, "claim_id", cloc, issues)
            _require_stable_id(clid, f"{cloc}.claim_id", issues)
            if clid in seen_claim_ids:
                issues.append(f"{cloc}.claim_id 重复：{clid}")
            seen_claim_ids.add(clid)

            pred = _require_text(raw_claim, "predicate", cloc, issues)
            _require_stable_id(pred, f"{cloc}.predicate", issues)

            cv = _parse_canon_value(
                raw_claim.get("value"), cloc, issues, entity_ids,
            )

            raw_sc_list = raw_claim.get("source_chapters")
            if not isinstance(raw_sc_list, list) or len(raw_sc_list) != 1:
                issues.append(f"{cloc}.source_chapters 必须是恰好一个元素的数组")
            else:
                sc_elem = raw_sc_list[0]
                if not isinstance(sc_elem, str):
                    issues.append(f"{cloc}.source_chapters[0] 必须是字符串")
                elif isinstance(src_cid, str) and src_cid and sc_elem != src_cid:
                    issues.append(
                        f"{cloc}.source_chapters[0] 必须等于 "
                        f"source.chapter_id ({src_cid})，收到 {sc_elem!r}"
                    )

            ss = raw_claim.get("source_support")
            if ss not in _SOURCE_SUPPORTS:
                issues.append(f"{cloc}.source_support 必须是 explicit|inferred")

            cert = raw_claim.get("certainty")
            if cert not in _CERTAINTIES:
                issues.append(f"{cloc}.certainty 必须是 certain|uncertain")

            ib = raw_claim.get("inference_basis")
            if ss == "inferred" and (not isinstance(ib, str) or not ib.strip()):
                issues.append(f"{cloc}.inference_basis 在 inferred 时必须是非空白字符串")
            elif ss in ("explicit",) and ib is not None:
                issues.append(f"{cloc}.inference_basis 在 explicit 时必须为 null")

            rr = raw_claim.get("review_reason")
            if not isinstance(rr, str) or not rr.strip():
                issues.append(f"{cloc}.review_reason 必须是非空白字符串")

            if (
                isinstance(clid, str) and clid.strip()
                and isinstance(pred, str) and pred.strip()
                and cv is not None
                and isinstance(raw_sc_list, list) and len(raw_sc_list) == 1
                and ss in _SOURCE_SUPPORTS
                and cert in _CERTAINTIES
                and isinstance(rr, str) and rr.strip()
            ):
                sc_tuple = tuple(s for s in raw_sc_list if isinstance(s, str))
                parsed_claims.append(CanonClaim(
                    claim_id=clid, predicate=pred, value=cv,
                    source_chapters=sc_tuple,
                    source_support=ss, certainty=cert,
                    inference_basis=ib if isinstance(ib, str) and ib.strip() else None,
                    review_reason=rr,
                ))

        if (
            isinstance(eid, str) and eid.strip()
            and et in _ENTITY_TYPES
            and isinstance(cname, str) and cname.strip()
            and isinstance(scid, str) and scid.strip()
        ):
            parsed_entities.append(CanonEntity(
                entity_id=eid, entity_type=et,
                canonical_name=cname,
                aliases=tuple(
                    a for a in raw_aliases
                    if isinstance(a, str) and a.strip()
                ),
                source_candidate_id=scid,
                claims=tuple(parsed_claims),
            ))

    if issues:
        raise CanonDraftValidationError(tuple(issues))

    return CanonDraft(
        format_version=1,
        promotion_id=pid,
        source=CanonSource(
            chapter_id=src_cid if isinstance(src_cid, str) else "",
            chapter_sha256=src_sha if isinstance(src_sha, str) else "",
        ),
        extracted_by=extracted_by,
        review_id=rid,
        reviewed_by=reviewed_by,
        entities=tuple(parsed_entities),
    )


def _parse_canon_value(
    raw: Any, loc: str, issues: list[str], entity_ids: set[str],
) -> CanonClaimValue | None:
    if not isinstance(raw, dict):
        issues.append(f"{loc}.value 必须是对象")
        return None
    kind = raw.get("kind")
    if not isinstance(kind, str):
        issues.append(f"{loc}.value.kind 必须是字符串")
        return None

    if kind == "text":
        _check_unknown_keys(raw, frozenset({"kind", "text"}), loc, issues)
        text = raw.get("text")
        if not isinstance(text, str) or not text.strip():
            issues.append(f"{loc}.value.text 必须是非空白字符串")
            return None
        return CanonTextValue(text=text)
    elif kind == "relation":
        _check_unknown_keys(raw, frozenset({"kind", "entity_ref"}), loc, issues)
        ref = raw.get("entity_ref")
        if not isinstance(ref, str) or not ref.strip():
            issues.append(f"{loc}.value.entity_ref 必须是非空白字符串")
            return None
        _require_stable_id(ref, f"{loc}.value.entity_ref", issues)
        if ref not in entity_ids:
            issues.append(
                f"{loc}.value.entity_ref 引用了不存在的 canon entity_id：{ref}"
            )
        return CanonRelationValue(entity_ref=ref)
    elif kind == "numeric":
        _check_unknown_keys(raw, frozenset({"kind", "number", "unit"}), loc, issues)
        num = raw.get("number")
        if num is None:
            issues.append(f"{loc}.value.number 是必填字段")
            return None
        if isinstance(num, bool) or not isinstance(num, (int, float)):
            issues.append(f"{loc}.value.number 必须是非 bool 的 int 或 float")
            return None
        if isinstance(num, float) and not math.isfinite(num):
            issues.append(f"{loc}.value.number 不允许 NaN 或 Infinity")
            return None
        unit = raw.get("unit")
        if unit is not None:
            if not isinstance(unit, str) or not unit.strip():
                issues.append(f"{loc}.value.unit 非 null 时必须是非空白字符串")
                return None
            _require_stable_id(unit, f"{loc}.value.unit", issues)
        return CanonNumericValue(number=num, unit=unit)
    elif kind == "boolean":
        _check_unknown_keys(raw, frozenset({"kind", "flag"}), loc, issues)
        flag = raw.get("flag")
        if not isinstance(flag, bool):
            issues.append(f"{loc}.value.flag 必须是真正 bool")
            return None
        return CanonBooleanValue(flag=flag)
    elif kind == "enum":
        _check_unknown_keys(raw, frozenset({"kind", "enum_value"}), loc, issues)
        ev = raw.get("enum_value")
        if not isinstance(ev, str) or not ev.strip():
            issues.append(f"{loc}.value.enum_value 必须是非空白字符串")
            return None
        _require_stable_id(ev, f"{loc}.value.enum_value", issues)
        return CanonEnumValue(enum_value=ev)
    else:
        issues.append(f"{loc}.value.kind 必须是 text|relation|numeric|boolean|enum")
        return None


# ── public entry: main CLI ──────────────────────────────────────────────────


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for canon draft generation.

    Exit codes: 0=success, 1=data/binding/build/I/O error, 2=argument error.
    """

    parser = argparse.ArgumentParser(
        description="Build a canon draft from reviewed fact candidates.",
    )
    parser.add_argument(
        "--promotion-plan", required=True, type=str,
        help="Path to PromotionPlan JSON file",
    )
    parser.add_argument(
        "--review", required=True, type=str,
        help="Path to FactReviewDocument JSON file",
    )
    parser.add_argument(
        "--candidate", required=True, type=str,
        help="Path to FactCandidateDocument JSON file",
    )
    parser.add_argument(
        "--manifest", required=True, type=str,
        help="Path to ChapterManifest JSON file",
    )
    parser.add_argument(
        "--output", required=True, type=str,
        help="Output path for CanonDraft JSON file",
    )

    args = parser.parse_args(argv)

    # ── P1-3: output must not overwrite any input ─────────────────────────
    output_real = os.path.realpath(args.output)
    inputs = [args.promotion_plan, args.review, args.candidate, args.manifest]
    for input_path in inputs:
        input_real = os.path.realpath(input_path)
        if os.path.normcase(output_real) == os.path.normcase(input_real):
            print(
                f"错误：output ({args.output}) 与输入 ({input_path}) 指向同一文件",
                file=sys.stderr,
            )
            return 1
        try:
            if os.path.isfile(output_real) and os.path.samefile(output_real, input_real):
                print(
                    f"错误：output ({args.output}) 与输入 ({input_path}) 是同一文件",
                    file=sys.stderr,
                )
                return 1
        except OSError:
            pass

    tmp_path: str | None = None

    try:
        # 1. Read all inputs
        def _read_json(path: str) -> Any:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)

        from pipeline.chapter_manifests import validate_chapter_manifest
        from pipeline.fact_candidates import validate_fact_candidate_document
        from pipeline.fact_reviews import validate_fact_review_document

        manifest = validate_chapter_manifest(_read_json(args.manifest))
        candidate_doc = validate_fact_candidate_document(_read_json(args.candidate))
        review = validate_fact_review_document(_read_json(args.review))
        plan = validate_canon_promotion_plan(_read_json(args.promotion_plan))

        # 2. Build draft
        draft = build_canon_draft(review, candidate_doc, manifest, plan)

        # 3. Serialize and validate
        raw_output = _sorted_json_dict(draft)
        validate_canon_draft_document(raw_output)

        # 4. Atomic write — tempfile in target directory
        out_dir = os.path.dirname(os.path.abspath(args.output)) or os.getcwd()
        json_bytes = json.dumps(
            raw_output, ensure_ascii=False, sort_keys=True, indent=2,
        ) + "\n"

        fd, tmp_path = tempfile.mkstemp(
            dir=out_dir, prefix=".canon_draft_", suffix=".tmp",
        )
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(json_bytes)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, args.output)
        tmp_path = None  # successfully committed

    except json.JSONDecodeError as exc:
        print(f"JSON 解析错误：{exc}", file=sys.stderr)
        _cleanup_tmp(tmp_path)
        return 1
    except (
        CanonDraftValidationError,
        CanonDraftBuildingError,
        ValueError,
        OSError,
    ) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        _cleanup_tmp(tmp_path)
        return 1

    return 0


def _cleanup_tmp(tmp_path: str | None) -> None:
    """Safely remove a temporary file if it exists."""
    if tmp_path is None:
        return
    try:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    except OSError:
        pass


if __name__ == "__main__":
    import sys
    sys.exit(main())
