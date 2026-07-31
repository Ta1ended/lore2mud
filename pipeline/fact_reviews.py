"""Validate v1 fact-review documents and claim-level review bindings.

Public API::

    validate_fact_review_document(data) -> FactReviewDocument
    validate_fact_review_bindings(review, candidate_document) -> FactReviewDocument

No file I/O, no private-data access, standard library only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from pipeline.fact_candidates import FactCandidateDocument

# ── public exceptions ───────────────────────────────────────────────────────


class FactReviewValidationError(ValueError):
    """Raised when a fact-review document fails structural validation."""

    def __init__(self, issues: tuple[str, ...]) -> None:
        self.issues = issues
        super().__init__("\n".join(f"- {i}" for i in issues))


class FactReviewBindingValidationError(ValueError):
    """Raised when review-candidate binding fails."""

    def __init__(self, issues: tuple[str, ...]) -> None:
        self.issues = issues
        super().__init__("\n".join(f"- {i}" for i in issues))


# ── frozen data models ──────────────────────────────────────────────────────

ReviewState = Literal["accepted", "rejected", "superseded", "conflicted"]
_STATES = frozenset({"accepted", "rejected", "superseded", "conflicted"})

_STABLE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_CHAPTER_ID_RE = re.compile(r"^chapter_[0-9]{6}$")


@dataclass(frozen=True, slots=True)
class ReviewDecision:
    candidate_id: str
    claim_id: str
    state: ReviewState
    reason: str
    superseded_by_claim_id: str | None


@dataclass(frozen=True, slots=True)
class FactReviewDocument:
    format_version: int
    review_id: str
    source_chapter: str
    reviewed_by: str
    decisions: tuple[ReviewDecision, ...]


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


# ── public entry point: review validation ───────────────────────────────────


def validate_fact_review_document(data: object) -> FactReviewDocument:
    """Validate a parsed JSON object as a v1 fact-review document.

    Returns a frozen :class:`FactReviewDocument` on success.
    Raises :class:`FactReviewValidationError` on failure.
    """

    issues: list[str] = []

    if not isinstance(data, dict):
        raise FactReviewValidationError(("根对象必须是 JSON 对象",))

    allowed_root = frozenset({
        "format_version", "review_id", "source_chapter",
        "reviewed_by", "decisions",
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

    # review_id
    review_id = _require_text(data, "review_id", "根对象", issues)
    _require_stable_id(review_id, "根对象.review_id", issues)

    # source_chapter
    raw_sc = data.get("source_chapter")
    if not isinstance(raw_sc, str):
        issues.append("source_chapter 必须是字符串")
        source_chapter = ""
    elif not _CHAPTER_ID_RE.fullmatch(raw_sc):
        issues.append(f"source_chapter 必须匹配 ^chapter_[0-9]{{6}}$，收到 {raw_sc!r}")
        source_chapter = ""
    else:
        source_chapter = raw_sc

    # reviewed_by
    reviewed_by = _require_text(data, "reviewed_by", "根对象", issues)

    # decisions
    raw_decisions = _require_array(data, "decisions", "根对象", issues)
    if isinstance(raw_decisions, list) and len(raw_decisions) == 0:
        issues.append("decisions 不得为空数组")

    parsed_decisions: list[ReviewDecision] = []
    seen_pairs: set[tuple[str, str]] = set()

    for di, raw_dec in enumerate(raw_decisions):
        dloc = f"decisions[{di}]"
        if not isinstance(raw_dec, dict):
            issues.append(f"{dloc} 必须是对象")
            continue

        allowed_dec = frozenset({
            "candidate_id", "claim_id", "state",
            "reason", "superseded_by_claim_id",
        })
        _check_unknown_keys(raw_dec, allowed_dec, dloc, issues)

        # candidate_id
        cid = raw_dec.get("candidate_id")
        if not isinstance(cid, str) or not cid.strip():
            issues.append(f"{dloc}.candidate_id 必须是非空白字符串")
        else:
            _require_stable_id(cid, f"{dloc}.candidate_id", issues)

        # claim_id
        clid = raw_dec.get("claim_id")
        if not isinstance(clid, str) or not clid.strip():
            issues.append(f"{dloc}.claim_id 必须是非空白字符串")
        else:
            _require_stable_id(clid, f"{dloc}.claim_id", issues)

        # uniqueness
        if isinstance(cid, str) and isinstance(clid, str):
            pair = (cid, clid)
            if pair in seen_pairs:
                issues.append(f"{dloc} 的 (candidate_id={cid}, claim_id={clid}) 重复")
            seen_pairs.add(pair)

        # state
        state = raw_dec.get("state")
        if not isinstance(state, str) or state not in _STATES:
            issues.append(f"{dloc}.state 必须是 accepted|rejected|superseded|conflicted")

        # reason
        reason = _require_text(raw_dec, "reason", dloc, issues)

        # superseded_by_claim_id — explicit presence, conditional
        if "superseded_by_claim_id" not in raw_dec:
            issues.append(f"{dloc}.superseded_by_claim_id 是必填字段（可为 null）")
            sbid: str | None = None
        else:
            raw_sbid = raw_dec["superseded_by_claim_id"]
            if isinstance(state, str) and state == "superseded":
                if not isinstance(raw_sbid, str) or not raw_sbid.strip():
                    issues.append(
                        f"{dloc}.superseded_by_claim_id 在 state=superseded 时"
                        " 必须是非空白稳定 ID"
                    )
                    sbid = None
                else:
                    _require_stable_id(raw_sbid, f"{dloc}.superseded_by_claim_id", issues)
                    sbid = raw_sbid
            elif raw_sbid is not None:
                issues.append(
                    f"{dloc}.superseded_by_claim_id 在 state!={state} 时必须为 null"
                )
                sbid = None
            else:
                sbid = None

        # build decision if critical fields present
        if (
            isinstance(cid, str) and cid.strip()
            and isinstance(clid, str) and clid.strip()
            and isinstance(state, str) and state in _STATES
            and isinstance(reason, str) and reason.strip()
        ):
            parsed_decisions.append(ReviewDecision(
                candidate_id=cid,
                claim_id=clid,
                state=state,
                reason=reason,
                superseded_by_claim_id=sbid,
            ))

    if issues:
        raise FactReviewValidationError(tuple(issues))

    return FactReviewDocument(
        format_version=1,
        review_id=review_id,
        source_chapter=source_chapter,
        reviewed_by=reviewed_by,
        decisions=tuple(parsed_decisions),
    )


# ── public entry point: review-candidate binding ────────────────────────────


def validate_fact_review_bindings(
    review: FactReviewDocument,
    candidate_document: object,
) -> FactReviewDocument:
    """Validate that a review's decisions reference claims in the candidate document.

    Returns the review unchanged on success.
    Raises :class:`FactReviewBindingValidationError` on failure.

    *candidate_document* must be a :class:`FactCandidateDocument` instance.
    """

    issues: list[str] = []

    if not isinstance(candidate_document, FactCandidateDocument):
        raise FactReviewBindingValidationError((
            f"candidate_document 必须是 FactCandidateDocument 实例，"
            f"收到 {type(candidate_document).__name__}",
        ))

    # source chapter match
    if review.source_chapter != candidate_document.source_chapter:
        issues.append(
            f"review.source_chapter ({review.source_chapter}) 必须等于 "
            f"candidate_document.source_chapter ({candidate_document.source_chapter})"
        )

    # build candidate→claims map
    candidate_claims: dict[str, set[str]] = {}
    for candidate in candidate_document.candidates:
        candidate_claims[candidate.candidate_id] = {
            claim.claim_id for claim in candidate.claims
        }

    for decision in review.decisions:
        # candidate_id must exist
        if decision.candidate_id not in candidate_claims:
            issues.append(
                f"candidate_id {decision.candidate_id} 不存在于 candidate document 中"
            )
            continue

        claims = candidate_claims[decision.candidate_id]

        # claim_id must exist in that candidate
        if decision.claim_id not in claims:
            issues.append(
                f"claim_id {decision.claim_id} 不属于 candidate {decision.candidate_id}"
            )

        # superseded_by_claim_id must be in same candidate and not self
        if decision.superseded_by_claim_id is not None:
            if decision.superseded_by_claim_id not in claims:
                issues.append(
                    f"superseded_by_claim_id {decision.superseded_by_claim_id}"
                    f" 不属于 candidate {decision.candidate_id}"
                )
            elif decision.superseded_by_claim_id == decision.claim_id:
                issues.append(
                    f"superseded_by_claim_id 不得等于自身 claim_id"
                    f" ({decision.claim_id})"
                )

    if issues:
        raise FactReviewBindingValidationError(tuple(issues))

    return review
