"""Validate v1 fact-candidate document envelopes.

Public API::

    validate_fact_candidate_document(data) -> FactCandidateDocument

Accepts a parsed JSON dict (or any mapping-like ``object``).
Returns a fully frozen dataclass tree on success.
Raises :class:`FactCandidateValidationError` with ordered issues on failure.

No file I/O, no private-data access, no dependencies beyond the standard library.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Literal, TypeAlias

# ── public exception ────────────────────────────────────────────────────────


class FactCandidateValidationError(ValueError):
    """Raised when a fact-candidate document fails structural validation."""

    def __init__(self, issues: tuple[str, ...]) -> None:
        self.issues = issues
        super().__init__("\n".join(f"- {i}" for i in issues))


# ── type aliases ────────────────────────────────────────────────────────────

EntityType: TypeAlias = Literal[
    "character", "location", "organization", "skill", "item", "event"
]
SourceSupport: TypeAlias = Literal["explicit", "inferred"]
Certainty: TypeAlias = Literal["certain", "uncertain"]

_ENTITY_TYPES = frozenset({
    "character", "location", "organization", "skill", "item", "event",
})
_SOURCE_SUPPORTS = frozenset({"explicit", "inferred"})
_CERTAINTIES = frozenset({"certain", "uncertain"})

_STABLE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_CHAPTER_ID_RE = re.compile(r"^chapter_[0-9]{6}$")


# ── value tagged union ──────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class TextValue:
    kind: Literal["text"] = "text"
    text: str = ""


@dataclass(frozen=True, slots=True)
class RelationValue:
    kind: Literal["relation"] = "relation"
    candidate_ref: str = ""


@dataclass(frozen=True, slots=True)
class NumericValue:
    kind: Literal["numeric"] = "numeric"
    number: int | float = 0
    unit: str | None = None


@dataclass(frozen=True, slots=True)
class BooleanValue:
    kind: Literal["boolean"] = "boolean"
    flag: bool = False


@dataclass(frozen=True, slots=True)
class EnumValue:
    kind: Literal["enum"] = "enum"
    enum_value: str = ""


ClaimValue = TextValue | RelationValue | NumericValue | BooleanValue | EnumValue


# ── claim ───────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Claim:
    claim_id: str
    predicate: str
    value: ClaimValue
    source_chapters: tuple[str, ...]
    source_support: SourceSupport
    certainty: Certainty
    inference_basis: str | None


# ── candidate ───────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Candidate:
    candidate_id: str
    entity_type: EntityType
    proposed_entity_id: str | None
    display_name: str
    aliases: tuple[str, ...]
    claims: tuple[Claim, ...]


# ── document envelope ───────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class FactCandidateDocument:
    format_version: int
    source_chapter: str
    extracted_by: str
    candidates: tuple[Candidate, ...]


# ── internal helpers (all append to the shared issues list) ─────────────────


def _check_unknown_keys(
    obj: dict[str, Any], allowed: set[str], loc: str, issues: list[str]
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


def _optional_text_nullable(
    obj: dict[str, Any], key: str, loc: str, issues: list[str]
) -> str | None:
    """Require the key to be explicitly present; value may be null or non-blank string."""
    if key not in obj:
        issues.append(f"{loc}.{key} 是必填字段（可为 null）")
        return None
    value = obj[key]
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        issues.append(f"{loc}.{key} 非 null 时必须是非空白字符串")
        return None
    return value


def _check_stable_id(value: str, loc: str, issues: list[str]) -> None:
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


def _check_alias_dedup(aliases: list[str], loc: str, issues: list[str]) -> None:
    seen: set[str] = set()
    for alias in aliases:
        if not isinstance(alias, str) or not alias.strip():
            issues.append(f"{loc} 中的每个别名必须是非空白字符串")
            continue
        normalized = unicodedata.normalize("NFKC", alias).casefold().strip()
        if normalized in seen:
            issues.append(f"{loc} 中存在规范化后重复的别名：{alias!r}")
        else:
            seen.add(normalized)


# ── value tagged union parser ───────────────────────────────────────────────


def _parse_value(
    raw: Any,
    loc: str,
    candidate_ids: set[str],
    issues: list[str],
) -> ClaimValue | None:
    if not isinstance(raw, dict):
        issues.append(f"{loc}.value 必须是对象")
        return None

    kind = raw.get("kind")
    if not isinstance(kind, str):
        issues.append(f"{loc}.value.kind 必须是字符串")
        return None

    if kind == "text":
        _check_unknown_keys(raw, {"kind", "text"}, f"{loc}.value", issues)
        text = raw.get("text")
        if not isinstance(text, str) or not text.strip():
            issues.append(f"{loc}.value.text 必须是非空白字符串")
            return None
        return TextValue(text=text)

    if kind == "relation":
        _check_unknown_keys(raw, {"kind", "candidate_ref"}, f"{loc}.value", issues)
        ref = raw.get("candidate_ref")
        if not isinstance(ref, str) or not ref.strip():
            issues.append(f"{loc}.value.candidate_ref 必须是非空白字符串")
            return None
        _check_stable_id(ref, f"{loc}.value.candidate_ref", issues)
        if ref not in candidate_ids:
            issues.append(
                f"{loc}.value.candidate_ref 引用了不存在的 candidate_id：{ref}"
            )
        return RelationValue(candidate_ref=ref)

    if kind == "numeric":
        _check_unknown_keys(raw, {"kind", "number", "unit"}, f"{loc}.value", issues)
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
        if "unit" not in raw:
            issues.append(f"{loc}.value.unit 是必填字段（可为 null）")
            return None
        unit = raw["unit"]
        if unit is not None:
            if not isinstance(unit, str) or not unit.strip():
                issues.append(f"{loc}.value.unit 非 null 时必须是非空白字符串")
                return None
            _check_stable_id(unit, f"{loc}.value.unit", issues)
        return NumericValue(number=num, unit=unit)

    if kind == "boolean":
        _check_unknown_keys(raw, {"kind", "flag"}, f"{loc}.value", issues)
        flag = raw.get("flag")
        if not isinstance(flag, bool):
            issues.append(f"{loc}.value.flag 必须是真正 bool（int 0/1 拒绝）")
            return None
        return BooleanValue(flag=flag)

    if kind == "enum":
        _check_unknown_keys(raw, {"kind", "enum_value"}, f"{loc}.value", issues)
        ev = raw.get("enum_value")
        if not isinstance(ev, str) or not ev.strip():
            issues.append(f"{loc}.value.enum_value 必须是非空白字符串")
            return None
        _check_stable_id(ev, f"{loc}.value.enum_value", issues)
        return EnumValue(enum_value=ev)

    issues.append(f"{loc}.value.kind 必须是 text|relation|numeric|boolean|enum")
    return None


# ── public entry point ──────────────────────────────────────────────────────


def validate_fact_candidate_document(data: object) -> FactCandidateDocument:
    """Validate a parsed JSON object as a v1 fact-candidate document.

    Returns a frozen :class:`FactCandidateDocument` on success.
    Raises :class:`FactCandidateValidationError` with all ordered issues on failure.
    """

    issues: list[str] = []

    # ── root must be object ──────────────────────────────────────────────
    if not isinstance(data, dict):
        raise FactCandidateValidationError(("根对象必须是 JSON 对象",))

    allowed_root = {"format_version", "source_chapter", "extracted_by", "candidates"}
    _check_unknown_keys(data, allowed_root, "根对象", issues)

    # format_version
    fv = data.get("format_version")
    if fv is None:
        issues.append("format_version 是必填字段")
    elif isinstance(fv, bool) or not isinstance(fv, int):
        issues.append("format_version 必须是真正 int（bool 拒绝）")
    elif fv != 1:
        issues.append(f"format_version 必须为 1，收到 {fv}")

    # source_chapter
    raw_sc = data.get("source_chapter")
    if not isinstance(raw_sc, str):
        issues.append("source_chapter 是必填字段且必须是字符串")
        source_chapter = ""
    elif not _CHAPTER_ID_RE.fullmatch(raw_sc):
        issues.append(
            f"source_chapter 必须匹配 ^chapter_[0-9]{{6}}$，收到 {raw_sc!r}"
        )
        source_chapter = ""
    else:
        source_chapter = raw_sc

    # extracted_by
    raw_eb = data.get("extracted_by")
    if not isinstance(raw_eb, str) or not raw_eb.strip():
        issues.append("extracted_by 必须是非空白字符串")

    # candidates — preliminary array check
    raw_candidates = data.get("candidates")
    if not isinstance(raw_candidates, list):
        issues.append("candidates 必须是数组")
        raw_candidates = []
    elif len(raw_candidates) == 0:
        issues.append("candidates 不得为空数组")

    # first pass: collect candidate_ids for cross-reference
    candidate_ids: set[str] = set()
    for raw_cand in raw_candidates:
        if isinstance(raw_cand, dict):
            cid = raw_cand.get("candidate_id")
            if isinstance(cid, str):
                candidate_ids.add(cid)

    # ── parse each candidate ─────────────────────────────────────────────
    parsed_candidates: list[Candidate] = []
    seen_candidate_ids: set[str] = set()

    for ci, raw_cand in enumerate(raw_candidates):
        cloc = f"candidates[{ci}]"
        if not isinstance(raw_cand, dict):
            issues.append(f"{cloc} 必须是对象")
            continue

        allowed_cand = {
            "candidate_id", "entity_type", "proposed_entity_id",
            "display_name", "aliases", "claims",
        }
        _check_unknown_keys(raw_cand, allowed_cand, cloc, issues)

        # candidate_id
        cid = raw_cand.get("candidate_id")
        if not isinstance(cid, str) or not cid.strip():
            issues.append(f"{cloc}.candidate_id 必须是非空白字符串")
        else:
            _check_stable_id(cid, f"{cloc}.candidate_id", issues)
            if cid in seen_candidate_ids:
                issues.append(f"{cloc}.candidate_id 重复：{cid}")
            seen_candidate_ids.add(cid)

        # entity_type
        et = raw_cand.get("entity_type")
        if not isinstance(et, str) or et not in _ENTITY_TYPES:
            issues.append(
                f"{cloc}.entity_type 必须是 "
                "character|location|organization|skill|item|event"
            )

        # proposed_entity_id — must be explicitly present, may be null
        pei = _optional_text_nullable(raw_cand, "proposed_entity_id", cloc, issues)
        if pei is not None:
            _check_stable_id(pei, f"{cloc}.proposed_entity_id", issues)

        # display_name
        dn = _require_text(raw_cand, "display_name", cloc, issues)

        # aliases — required array, may be empty
        raw_aliases = raw_cand.get("aliases")
        if not isinstance(raw_aliases, list):
            issues.append(f"{cloc}.aliases 是必填字段且必须是数组")
            raw_aliases_list: list[str] = []
        else:
            raw_aliases_list = []
            for ai, alias in enumerate(raw_aliases):
                if isinstance(alias, str):
                    raw_aliases_list.append(alias)
                else:
                    issues.append(f"{cloc}.aliases[{ai}] 必须是字符串")
            _check_alias_dedup(raw_aliases_list, f"{cloc}.aliases", issues)

        # claims — required, non-empty
        raw_claims = _require_array(raw_cand, "claims", cloc, issues)
        if isinstance(raw_claims, list) and len(raw_claims) == 0:
            issues.append(f"{cloc}.claims 不得为空数组")

        parsed_claims: list[Claim] = []
        seen_claim_ids: set[str] = set()

        for cli, raw_claim in enumerate(raw_claims):
            clloc = f"{cloc}.claims[{cli}]"
            if not isinstance(raw_claim, dict):
                issues.append(f"{clloc} 必须是对象")
                continue

            allowed_claim = {
                "claim_id", "predicate", "value", "source_chapters",
                "source_support", "certainty", "inference_basis",
            }
            _check_unknown_keys(raw_claim, allowed_claim, clloc, issues)

            # claim_id
            clid = raw_claim.get("claim_id")
            if not isinstance(clid, str) or not clid.strip():
                issues.append(f"{clloc}.claim_id 必须是非空白字符串")
            else:
                _check_stable_id(clid, f"{clloc}.claim_id", issues)
                if clid in seen_claim_ids:
                    issues.append(f"{clloc}.claim_id 重复：{clid}")
                seen_claim_ids.add(clid)

            # predicate — must match stable ID
            pred = raw_claim.get("predicate")
            if not isinstance(pred, str) or not pred.strip():
                issues.append(f"{clloc}.predicate 必须是非空白字符串")
            else:
                _check_stable_id(pred, f"{clloc}.predicate", issues)

            # value
            claim_value = _parse_value(
                raw_claim.get("value"), clloc, candidate_ids, issues
            )

            # source_chapters — must be exactly [document.source_chapter]
            raw_sc_list = raw_claim.get("source_chapters")
            if not isinstance(raw_sc_list, list):
                issues.append(f"{clloc}.source_chapters 必须是数组")
            elif len(raw_sc_list) != 1:
                issues.append(
                    f"{clloc}.source_chapters 必须是恰好一个元素的数组"
                )
            else:
                sc_elem = raw_sc_list[0]
                if not isinstance(sc_elem, str):
                    issues.append(f"{clloc}.source_chapters[0] 必须是字符串")
                elif source_chapter and sc_elem != source_chapter:
                    issues.append(
                        f"{clloc}.source_chapters[0] 必须等于 "
                        f"document.source_chapter ({source_chapter})，"
                        f"收到 {sc_elem!r}"
                    )

            # source_support
            ss = raw_claim.get("source_support")
            if not isinstance(ss, str) or ss not in _SOURCE_SUPPORTS:
                issues.append(f"{clloc}.source_support 必须是 explicit|inferred")

            # certainty
            cert = raw_claim.get("certainty")
            if not isinstance(cert, str) or cert not in _CERTAINTIES:
                issues.append(f"{clloc}.certainty 必须是 certain|uncertain")

            # inference_basis — conditional
            ib = raw_claim.get("inference_basis")
            if "inference_basis" not in raw_claim:
                issues.append(f"{clloc}.inference_basis 是必填字段（可为 null）")
            elif ss == "inferred":
                if not isinstance(ib, str) or not ib.strip():
                    issues.append(
                        f"{clloc}.inference_basis 在 source_support=inferred 时"
                        " 必须是非空白字符串"
                    )
            elif ib is not None:
                issues.append(
                    f"{clloc}.inference_basis 在 source_support!=inferred 时"
                    " 必须为 null"
                )

            # build Claim only if all critical fields present
            if (
                isinstance(clid, str)
                and clid.strip()
                and isinstance(pred, str)
                and pred.strip()
                and claim_value is not None
                and isinstance(raw_sc_list, list)
                and len(raw_sc_list) == 1
                and isinstance(ss, str)
                and ss in _SOURCE_SUPPORTS
                and isinstance(cert, str)
                and cert in _CERTAINTIES
            ):
                sc_tuple = tuple(s for s in raw_sc_list if isinstance(s, str))
                parsed_claims.append(
                    Claim(
                        claim_id=clid,
                        predicate=pred,
                        value=claim_value,
                        source_chapters=sc_tuple,
                        source_support=ss,
                        certainty=cert,
                        inference_basis=(
                            ib if isinstance(ib, str) and ib.strip() else None
                        ),
                    )
                )

        # build Candidate only if all critical fields present
        if (
            isinstance(cid, str)
            and cid.strip()
            and isinstance(et, str)
            and et in _ENTITY_TYPES
            and isinstance(dn, str)
            and dn.strip()
        ):
            parsed_candidates.append(
                Candidate(
                    candidate_id=cid,
                    entity_type=et,
                    proposed_entity_id=pei,
                    display_name=dn,
                    aliases=tuple(raw_aliases_list),
                    claims=tuple(parsed_claims),
                )
            )

    if issues:
        raise FactCandidateValidationError(tuple(issues))

    return FactCandidateDocument(
        format_version=1,
        source_chapter=source_chapter,
        extracted_by=raw_eb.strip() if isinstance(raw_eb, str) else "",
        candidates=tuple(parsed_candidates),
    )
