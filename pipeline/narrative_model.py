"""Compile a deterministic public-safe narrative model from a CanonRegistry.

Public API::

    validate_narrative_plan_document(data) -> NarrativePlan
    compile_narrative_model(registry, plan) -> NarrativeModel
    validate_narrative_model_document(data) -> NarrativeModel
    narrative_plan_to_document(plan) -> dict
    narrative_model_to_document(model) -> dict
    write_narrative_model(model, output_path) -> Path

CLI::

    python -m pipeline.narrative_model \
        --canon-registry canon_registry.json \
        --narrative-plan narrative_plan.json \
        --output narrative_model.json

Exit codes: 0=success, 1=data/build/I/O error, 2=argument error.
"""

from __future__ import annotations

import argparse
import heapq
import json
import os
import re
import stat
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TypeAlias

from pipeline.canon_registry import (
    CanonRegistry,
    CanonRegistryValidationError,
    RegistrySource,
    canon_registry_to_document,
    validate_canon_registry_document,
)


class NarrativeModelValidationError(ValueError):
    """Raised when a NarrativePlan or NarrativeModel document is invalid."""

    def __init__(self, issues: tuple[str, ...]) -> None:
        self.issues = issues
        super().__init__("\n".join(f"- {issue}" for issue in issues))


class NarrativeModelBuildError(ValueError):
    """Raised when a validated registry cannot satisfy a narrative plan."""

    def __init__(self, issues: tuple[str, ...]) -> None:
        self.issues = issues
        super().__init__("\n".join(f"- {issue}" for issue in issues))


PropositionStatus: TypeAlias = Literal[
    "canon_supported", "conflicted", "adaptation_only", "unknown"
]
DisclosureState: TypeAlias = Literal[
    "heard", "suspected", "confirmed", "retracted"
]

_STABLE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_CHAPTER_ID_RE = re.compile(r"^chapter_[0-9]{6}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_PROPOSITION_STATUSES = frozenset(
    {"canon_supported", "conflicted", "adaptation_only", "unknown"}
)
_DISCLOSURE_STATES = frozenset(
    {"heard", "suspected", "confirmed", "retracted"}
)


@dataclass(frozen=True, slots=True)
class NarrativeClaimRef:
    promotion_id: str
    source_entity_id: str
    source_claim_id: str


@dataclass(frozen=True, slots=True)
class NarrativeClaimOmission:
    claim_ref: NarrativeClaimRef
    reason: str


@dataclass(frozen=True, slots=True)
class NarrativeScope:
    entity_refs: tuple[str, ...]
    claim_uses: tuple[NarrativeClaimRef, ...]
    claim_omissions: tuple[NarrativeClaimOmission, ...]


@dataclass(frozen=True, slots=True)
class NarrativePerspective:
    perspective_id: str
    entity_ref: str
    summary: str


@dataclass(frozen=True, slots=True)
class NarrativeProposition:
    proposition_id: str
    statement: str
    status: PropositionStatus
    claim_refs: tuple[NarrativeClaimRef, ...]
    rationale: str


@dataclass(frozen=True, slots=True)
class NarrativePhase:
    phase_id: str
    sequence: int
    summary: str


@dataclass(frozen=True, slots=True)
class NarrativeDisclosure:
    perspective_ref: str
    proposition_ref: str
    state: DisclosureState


@dataclass(frozen=True, slots=True)
class NarrativeBeat:
    beat_id: str
    phase_ref: str
    predecessor_refs: tuple[str, ...]
    perspective_refs: tuple[str, ...]
    proposition_refs: tuple[str, ...]
    disclosures: tuple[NarrativeDisclosure, ...]
    summary: str


@dataclass(frozen=True, slots=True)
class SourceRegistryRef:
    registry_id: str
    registry_version: int


@dataclass(frozen=True, slots=True)
class SourceRegistrySnapshot:
    registry_id: str
    registry_version: int
    sources: tuple[RegistrySource, ...]


@dataclass(frozen=True, slots=True)
class NarrativePlan:
    format_version: int
    model_id: str
    source_registry: SourceRegistryRef
    scope: NarrativeScope
    perspectives: tuple[NarrativePerspective, ...]
    propositions: tuple[NarrativeProposition, ...]
    phases: tuple[NarrativePhase, ...]
    beats: tuple[NarrativeBeat, ...]


@dataclass(frozen=True, slots=True)
class NarrativeModel:
    format_version: int
    model_id: str
    source_registry: SourceRegistrySnapshot
    scope: NarrativeScope
    perspectives: tuple[NarrativePerspective, ...]
    propositions: tuple[NarrativeProposition, ...]
    phases: tuple[NarrativePhase, ...]
    beats: tuple[NarrativeBeat, ...]


def _claim_key(value: NarrativeClaimRef) -> tuple[str, str, str]:
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


def _stable_id(value: str, loc: str, issues: list[str]) -> None:
    if value and not _STABLE_ID_RE.fullmatch(value):
        issues.append(f"{loc} must match stable ID format ^[a-z][a-z0-9_]*$")


def _json_integer(
    obj: dict[str, Any],
    key: str,
    loc: str,
    issues: list[str],
    *,
    minimum: int,
) -> int:
    value = obj.get(key)
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < minimum
    ):
        issues.append(f"{loc}.{key} must be a true int >= {minimum}")
        return minimum
    return value


def _required_array(
    obj: dict[str, Any], key: str, loc: str, issues: list[str], *, nonempty: bool
) -> list[Any]:
    value = obj.get(key)
    if not isinstance(value, list):
        issues.append(f"{loc}.{key} must be an array")
        return []
    if nonempty and not value:
        issues.append(f"{loc}.{key} must not be empty")
    return value


def _parse_stable_id_array(
    raw: object, loc: str, issues: list[str], *, nonempty: bool
) -> tuple[str, ...]:
    if not isinstance(raw, list):
        issues.append(f"{loc} must be an array")
        return ()
    if nonempty and not raw:
        issues.append(f"{loc} must not be empty")
    parsed: list[str] = []
    seen: set[str] = set()
    for index, value in enumerate(raw):
        item_loc = f"{loc}[{index}]"
        if not isinstance(value, str) or not value.strip():
            issues.append(f"{item_loc} must be a non-blank string")
            continue
        _stable_id(value, item_loc, issues)
        if value in seen:
            issues.append(f"{item_loc} duplicates stable ID: {value}")
        seen.add(value)
        parsed.append(value)
    return tuple(sorted(parsed))


def _parse_claim_ref(
    raw: object, loc: str, issues: list[str]
) -> NarrativeClaimRef | None:
    if not isinstance(raw, dict):
        issues.append(f"{loc} must be an object")
        return None
    _unknown_keys(
        raw,
        frozenset({"promotion_id", "source_entity_id", "source_claim_id"}),
        loc,
        issues,
    )
    promotion_id = _required_text(raw, "promotion_id", loc, issues)
    source_entity_id = _required_text(raw, "source_entity_id", loc, issues)
    source_claim_id = _required_text(raw, "source_claim_id", loc, issues)
    _stable_id(promotion_id, f"{loc}.promotion_id", issues)
    _stable_id(source_entity_id, f"{loc}.source_entity_id", issues)
    _stable_id(source_claim_id, f"{loc}.source_claim_id", issues)
    return NarrativeClaimRef(
        promotion_id=promotion_id,
        source_entity_id=source_entity_id,
        source_claim_id=source_claim_id,
    )


def _parse_claim_refs(
    raw: object, loc: str, issues: list[str], *, nonempty: bool
) -> tuple[NarrativeClaimRef, ...]:
    if not isinstance(raw, list):
        issues.append(f"{loc} must be an array")
        return ()
    if nonempty and not raw:
        issues.append(f"{loc} must not be empty")
    parsed: list[NarrativeClaimRef] = []
    seen: set[tuple[str, str, str]] = set()
    for index, entry in enumerate(raw):
        claim_ref = _parse_claim_ref(entry, f"{loc}[{index}]", issues)
        if claim_ref is None:
            continue
        key = _claim_key(claim_ref)
        if key in seen:
            issues.append(f"{loc}[{index}] duplicates claim provenance: {key!r}")
        seen.add(key)
        parsed.append(claim_ref)
    return tuple(sorted(parsed, key=_claim_key))


def _parse_source_registry_ref(
    raw: object, loc: str, issues: list[str]
) -> SourceRegistryRef:
    if not isinstance(raw, dict):
        issues.append(f"{loc} must be an object")
        raw = {}
    _unknown_keys(
        raw, frozenset({"registry_id", "registry_version"}), loc, issues
    )
    registry_id = _required_text(raw, "registry_id", loc, issues)
    _stable_id(registry_id, f"{loc}.registry_id", issues)
    return SourceRegistryRef(
        registry_id=registry_id,
        registry_version=_json_integer(
            raw, "registry_version", loc, issues, minimum=1
        ),
    )


def _parse_registry_source(
    raw: object, loc: str, issues: list[str]
) -> RegistrySource | None:
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
    extracted_by = _required_text(raw, "extracted_by", loc, issues)
    review_id = _required_text(raw, "review_id", loc, issues)
    reviewed_by = _required_text(raw, "reviewed_by", loc, issues)
    _stable_id(promotion_id, f"{loc}.promotion_id", issues)
    _stable_id(review_id, f"{loc}.review_id", issues)
    if chapter_id and not _CHAPTER_ID_RE.fullmatch(chapter_id):
        issues.append(f"{loc}.chapter_id must match chapter_NNNNNN")
    if chapter_sha256 and not _SHA256_RE.fullmatch(chapter_sha256):
        issues.append(f"{loc}.chapter_sha256 must be a lowercase SHA-256")
    return RegistrySource(
        promotion_id=promotion_id,
        chapter_id=chapter_id,
        chapter_sha256=chapter_sha256,
        extracted_by=extracted_by,
        review_id=review_id,
        reviewed_by=reviewed_by,
    )


def _parse_source_registry_snapshot(
    raw: object, loc: str, issues: list[str]
) -> SourceRegistrySnapshot:
    if not isinstance(raw, dict):
        issues.append(f"{loc} must be an object")
        raw = {}
    _unknown_keys(
        raw,
        frozenset({"registry_id", "registry_version", "sources"}),
        loc,
        issues,
    )
    registry_id = _required_text(raw, "registry_id", loc, issues)
    _stable_id(registry_id, f"{loc}.registry_id", issues)
    registry_version = _json_integer(
        raw, "registry_version", loc, issues, minimum=1
    )
    raw_sources = _required_array(raw, "sources", loc, issues, nonempty=True)
    sources: list[RegistrySource] = []
    promotions: set[str] = set()
    chapters: set[str] = set()
    for index, raw_source in enumerate(raw_sources):
        source = _parse_registry_source(raw_source, f"{loc}.sources[{index}]", issues)
        if source is None:
            continue
        if source.promotion_id in promotions:
            issues.append(
                f"{loc}.sources[{index}] duplicates promotion_id: {source.promotion_id}"
            )
        if source.chapter_id in chapters:
            issues.append(
                f"{loc}.sources[{index}] duplicates chapter_id: {source.chapter_id}"
            )
        promotions.add(source.promotion_id)
        chapters.add(source.chapter_id)
        sources.append(source)
    return SourceRegistrySnapshot(
        registry_id=registry_id,
        registry_version=registry_version,
        sources=tuple(
            sorted(sources, key=lambda item: (item.chapter_id, item.promotion_id))
        ),
    )


def _parse_scope(raw: object, loc: str, issues: list[str]) -> NarrativeScope:
    if not isinstance(raw, dict):
        issues.append(f"{loc} must be an object")
        raw = {}
    _unknown_keys(
        raw,
        frozenset({"entity_refs", "claim_uses", "claim_omissions"}),
        loc,
        issues,
    )
    entity_refs = _parse_stable_id_array(
        raw.get("entity_refs"), f"{loc}.entity_refs", issues, nonempty=True
    )
    claim_uses = _parse_claim_refs(
        raw.get("claim_uses"), f"{loc}.claim_uses", issues, nonempty=False
    )
    omissions: list[NarrativeClaimOmission] = []
    omission_keys: set[tuple[str, str, str]] = set()
    raw_omissions = _required_array(
        raw, "claim_omissions", loc, issues, nonempty=False
    )
    for index, entry in enumerate(raw_omissions):
        entry_loc = f"{loc}.claim_omissions[{index}]"
        if not isinstance(entry, dict):
            issues.append(f"{entry_loc} must be an object")
            continue
        _unknown_keys(entry, frozenset({"claim_ref", "reason"}), entry_loc, issues)
        claim_ref = _parse_claim_ref(entry.get("claim_ref"), f"{entry_loc}.claim_ref", issues)
        reason = _required_text(entry, "reason", entry_loc, issues)
        if claim_ref is None:
            continue
        key = _claim_key(claim_ref)
        if key in omission_keys:
            issues.append(f"{entry_loc} duplicates omitted claim: {key!r}")
        omission_keys.add(key)
        omissions.append(NarrativeClaimOmission(claim_ref=claim_ref, reason=reason))
    use_keys = {_claim_key(value) for value in claim_uses}
    overlap = sorted(use_keys & omission_keys)
    if overlap:
        issues.append(f"{loc} uses and omits the same claims: {overlap!r}")
    return NarrativeScope(
        entity_refs=entity_refs,
        claim_uses=claim_uses,
        claim_omissions=tuple(
            sorted(omissions, key=lambda value: _claim_key(value.claim_ref))
        ),
    )


def _parse_perspectives(
    raw: object, loc: str, issues: list[str]
) -> tuple[NarrativePerspective, ...]:
    if not isinstance(raw, list):
        issues.append(f"{loc} must be an array")
        return ()
    if not raw:
        issues.append(f"{loc} must not be empty")
    parsed: list[NarrativePerspective] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw):
        entry_loc = f"{loc}[{index}]"
        if not isinstance(entry, dict):
            issues.append(f"{entry_loc} must be an object")
            continue
        _unknown_keys(
            entry,
            frozenset({"perspective_id", "entity_ref", "summary"}),
            entry_loc,
            issues,
        )
        perspective_id = _required_text(entry, "perspective_id", entry_loc, issues)
        entity_ref = _required_text(entry, "entity_ref", entry_loc, issues)
        _stable_id(perspective_id, f"{entry_loc}.perspective_id", issues)
        _stable_id(entity_ref, f"{entry_loc}.entity_ref", issues)
        if perspective_id in seen:
            issues.append(f"{entry_loc}.perspective_id is duplicated")
        seen.add(perspective_id)
        parsed.append(
            NarrativePerspective(
                perspective_id=perspective_id,
                entity_ref=entity_ref,
                summary=_required_text(entry, "summary", entry_loc, issues),
            )
        )
    return tuple(sorted(parsed, key=lambda value: value.perspective_id))


def _parse_propositions(
    raw: object, loc: str, issues: list[str]
) -> tuple[NarrativeProposition, ...]:
    if not isinstance(raw, list):
        issues.append(f"{loc} must be an array")
        return ()
    if not raw:
        issues.append(f"{loc} must not be empty")
    parsed: list[NarrativeProposition] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw):
        entry_loc = f"{loc}[{index}]"
        if not isinstance(entry, dict):
            issues.append(f"{entry_loc} must be an object")
            continue
        _unknown_keys(
            entry,
            frozenset(
                {"proposition_id", "statement", "status", "claim_refs", "rationale"}
            ),
            entry_loc,
            issues,
        )
        proposition_id = _required_text(entry, "proposition_id", entry_loc, issues)
        _stable_id(proposition_id, f"{entry_loc}.proposition_id", issues)
        if proposition_id in seen:
            issues.append(f"{entry_loc}.proposition_id is duplicated")
        seen.add(proposition_id)
        raw_status = entry.get("status")
        if not isinstance(raw_status, str) or raw_status not in _PROPOSITION_STATUSES:
            issues.append(
                f"{entry_loc}.status must be one of {sorted(_PROPOSITION_STATUSES)}"
            )
            status: PropositionStatus = "unknown"
        else:
            status = raw_status  # type: ignore[assignment]
        claim_refs = _parse_claim_refs(
            entry.get("claim_refs"),
            f"{entry_loc}.claim_refs",
            issues,
            nonempty=False,
        )
        if status == "canon_supported" and not claim_refs:
            issues.append(f"{entry_loc}.claim_refs must not be empty for canon_supported")
        if status == "conflicted" and len(claim_refs) < 2:
            issues.append(f"{entry_loc}.claim_refs needs at least two claims for conflicted")
        if status in {"adaptation_only", "unknown"} and claim_refs:
            issues.append(f"{entry_loc}.claim_refs must be empty for {status}")
        parsed.append(
            NarrativeProposition(
                proposition_id=proposition_id,
                statement=_required_text(entry, "statement", entry_loc, issues),
                status=status,
                claim_refs=claim_refs,
                rationale=_required_text(entry, "rationale", entry_loc, issues),
            )
        )
    return tuple(sorted(parsed, key=lambda value: value.proposition_id))


def _parse_phases(
    raw: object, loc: str, issues: list[str]
) -> tuple[NarrativePhase, ...]:
    if not isinstance(raw, list):
        issues.append(f"{loc} must be an array")
        return ()
    if not raw:
        issues.append(f"{loc} must not be empty")
    parsed: list[NarrativePhase] = []
    ids: set[str] = set()
    sequences: set[int] = set()
    for index, entry in enumerate(raw):
        entry_loc = f"{loc}[{index}]"
        if not isinstance(entry, dict):
            issues.append(f"{entry_loc} must be an object")
            continue
        _unknown_keys(
            entry, frozenset({"phase_id", "sequence", "summary"}), entry_loc, issues
        )
        phase_id = _required_text(entry, "phase_id", entry_loc, issues)
        _stable_id(phase_id, f"{entry_loc}.phase_id", issues)
        sequence = _json_integer(entry, "sequence", entry_loc, issues, minimum=1)
        if phase_id in ids:
            issues.append(f"{entry_loc}.phase_id is duplicated")
        if sequence in sequences:
            issues.append(f"{entry_loc}.sequence is duplicated: {sequence}")
        ids.add(phase_id)
        sequences.add(sequence)
        parsed.append(
            NarrativePhase(
                phase_id=phase_id,
                sequence=sequence,
                summary=_required_text(entry, "summary", entry_loc, issues),
            )
        )
    expected = set(range(1, len(parsed) + 1))
    if sequences != expected:
        issues.append(
            f"{loc}.sequence must be contiguous from 1: "
            f"actual={sorted(sequences)}, expected={sorted(expected)}"
        )
    return tuple(sorted(parsed, key=lambda value: (value.sequence, value.phase_id)))


def _parse_disclosures(
    raw: object, loc: str, issues: list[str]
) -> tuple[NarrativeDisclosure, ...]:
    if not isinstance(raw, list):
        issues.append(f"{loc} must be an array")
        return ()
    parsed: list[NarrativeDisclosure] = []
    seen_pairs: set[tuple[str, str]] = set()
    for index, entry in enumerate(raw):
        entry_loc = f"{loc}[{index}]"
        if not isinstance(entry, dict):
            issues.append(f"{entry_loc} must be an object")
            continue
        _unknown_keys(
            entry,
            frozenset({"perspective_ref", "proposition_ref", "state"}),
            entry_loc,
            issues,
        )
        perspective_ref = _required_text(entry, "perspective_ref", entry_loc, issues)
        proposition_ref = _required_text(entry, "proposition_ref", entry_loc, issues)
        _stable_id(perspective_ref, f"{entry_loc}.perspective_ref", issues)
        _stable_id(proposition_ref, f"{entry_loc}.proposition_ref", issues)
        raw_state = entry.get("state")
        if not isinstance(raw_state, str) or raw_state not in _DISCLOSURE_STATES:
            issues.append(
                f"{entry_loc}.state must be one of {sorted(_DISCLOSURE_STATES)}"
            )
            state: DisclosureState = "heard"
        else:
            state = raw_state  # type: ignore[assignment]
        pair = (perspective_ref, proposition_ref)
        if pair in seen_pairs:
            issues.append(
                f"{entry_loc} repeats perspective/proposition disclosure: {pair!r}"
            )
        seen_pairs.add(pair)
        parsed.append(
            NarrativeDisclosure(
                perspective_ref=perspective_ref,
                proposition_ref=proposition_ref,
                state=state,
            )
        )
    return tuple(
        sorted(
            parsed,
            key=lambda value: (
                value.perspective_ref,
                value.proposition_ref,
                value.state,
            ),
        )
    )


def _parse_beats(raw: object, loc: str, issues: list[str]) -> tuple[NarrativeBeat, ...]:
    if not isinstance(raw, list):
        issues.append(f"{loc} must be an array")
        return ()
    if not raw:
        issues.append(f"{loc} must not be empty")
    parsed: list[NarrativeBeat] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw):
        entry_loc = f"{loc}[{index}]"
        if not isinstance(entry, dict):
            issues.append(f"{entry_loc} must be an object")
            continue
        _unknown_keys(
            entry,
            frozenset(
                {
                    "beat_id",
                    "phase_ref",
                    "predecessor_refs",
                    "perspective_refs",
                    "proposition_refs",
                    "disclosures",
                    "summary",
                }
            ),
            entry_loc,
            issues,
        )
        beat_id = _required_text(entry, "beat_id", entry_loc, issues)
        phase_ref = _required_text(entry, "phase_ref", entry_loc, issues)
        _stable_id(beat_id, f"{entry_loc}.beat_id", issues)
        _stable_id(phase_ref, f"{entry_loc}.phase_ref", issues)
        if beat_id in seen:
            issues.append(f"{entry_loc}.beat_id is duplicated")
        seen.add(beat_id)
        parsed.append(
            NarrativeBeat(
                beat_id=beat_id,
                phase_ref=phase_ref,
                predecessor_refs=_parse_stable_id_array(
                    entry.get("predecessor_refs"),
                    f"{entry_loc}.predecessor_refs",
                    issues,
                    nonempty=False,
                ),
                perspective_refs=_parse_stable_id_array(
                    entry.get("perspective_refs"),
                    f"{entry_loc}.perspective_refs",
                    issues,
                    nonempty=True,
                ),
                proposition_refs=_parse_stable_id_array(
                    entry.get("proposition_refs"),
                    f"{entry_loc}.proposition_refs",
                    issues,
                    nonempty=True,
                ),
                disclosures=_parse_disclosures(
                    entry.get("disclosures"), f"{entry_loc}.disclosures", issues
                ),
                summary=_required_text(entry, "summary", entry_loc, issues),
            )
        )
    return tuple(parsed)


def _canonicalize_and_validate_body(
    scope: NarrativeScope,
    perspectives: tuple[NarrativePerspective, ...],
    propositions: tuple[NarrativeProposition, ...],
    phases: tuple[NarrativePhase, ...],
    beats: tuple[NarrativeBeat, ...],
    issues: list[str],
) -> tuple[NarrativeBeat, ...]:
    scope_entities = set(scope.entity_refs)
    perspective_by_id = {value.perspective_id: value for value in perspectives}
    proposition_by_id = {value.proposition_id: value for value in propositions}
    phase_by_id = {value.phase_id: value for value in phases}
    beat_by_id = {value.beat_id: value for value in beats}

    for perspective in perspectives:
        if perspective.entity_ref not in scope_entities:
            issues.append(
                f"perspective {perspective.perspective_id} references an entity "
                f"outside scope: {perspective.entity_ref}"
            )

    scope_use_keys = {_claim_key(value) for value in scope.claim_uses}
    proposition_claim_keys = {
        _claim_key(claim_ref)
        for proposition in propositions
        for claim_ref in proposition.claim_refs
    }
    if proposition_claim_keys != scope_use_keys:
        issues.append(
            "scope.claim_uses must exactly equal proposition claim_refs: "
            f"scope={sorted(scope_use_keys)!r}, "
            f"propositions={sorted(proposition_claim_keys)!r}"
        )

    used_perspectives: set[str] = set()
    used_propositions: set[str] = set()
    used_phases: set[str] = set()
    successors: dict[str, list[str]] = {beat_id: [] for beat_id in beat_by_id}
    indegree: dict[str, int] = {beat_id: 0 for beat_id in beat_by_id}
    for beat in beats:
        phase = phase_by_id.get(beat.phase_ref)
        if phase is None:
            issues.append(f"beat {beat.beat_id} references unknown phase: {beat.phase_ref}")
        else:
            used_phases.add(beat.phase_ref)
        for perspective_ref in beat.perspective_refs:
            if perspective_ref not in perspective_by_id:
                issues.append(
                    f"beat {beat.beat_id} references unknown perspective: {perspective_ref}"
                )
            else:
                used_perspectives.add(perspective_ref)
        for proposition_ref in beat.proposition_refs:
            if proposition_ref not in proposition_by_id:
                issues.append(
                    f"beat {beat.beat_id} references unknown proposition: {proposition_ref}"
                )
            else:
                used_propositions.add(proposition_ref)
        for disclosure in beat.disclosures:
            if disclosure.perspective_ref not in beat.perspective_refs:
                issues.append(
                    f"beat {beat.beat_id} disclosure perspective is not listed by the beat: "
                    f"{disclosure.perspective_ref}"
                )
            if disclosure.proposition_ref not in beat.proposition_refs:
                issues.append(
                    f"beat {beat.beat_id} disclosure proposition is not listed by the beat: "
                    f"{disclosure.proposition_ref}"
                )
        for predecessor_ref in beat.predecessor_refs:
            if predecessor_ref == beat.beat_id:
                issues.append(f"beat {beat.beat_id} cannot depend on itself")
                continue
            predecessor = beat_by_id.get(predecessor_ref)
            if predecessor is None:
                issues.append(
                    f"beat {beat.beat_id} references unknown predecessor: {predecessor_ref}"
                )
                continue
            predecessor_phase = phase_by_id.get(predecessor.phase_ref)
            if (
                phase is not None
                and predecessor_phase is not None
                and predecessor_phase.sequence > phase.sequence
            ):
                issues.append(
                    f"beat {beat.beat_id} depends on later-phase beat {predecessor_ref}"
                )
            successors[predecessor_ref].append(beat.beat_id)
            indegree[beat.beat_id] += 1

    missing_perspectives = sorted(set(perspective_by_id) - used_perspectives)
    missing_propositions = sorted(set(proposition_by_id) - used_propositions)
    missing_phases = sorted(set(phase_by_id) - used_phases)
    if missing_perspectives:
        issues.append(f"perspectives are unused by beats: {missing_perspectives}")
    if missing_propositions:
        issues.append(f"propositions are unused by beats: {missing_propositions}")
    if missing_phases:
        issues.append(f"phases contain no beats: {missing_phases}")

    phase_sequence = {value.phase_id: value.sequence for value in phases}
    ready: list[tuple[int, str]] = []
    for beat_id, degree in indegree.items():
        if degree == 0:
            beat = beat_by_id[beat_id]
            heapq.heappush(ready, (phase_sequence.get(beat.phase_ref, 0), beat_id))
    ordered: list[NarrativeBeat] = []
    while ready:
        _, beat_id = heapq.heappop(ready)
        ordered.append(beat_by_id[beat_id])
        for successor in sorted(successors[beat_id]):
            indegree[successor] -= 1
            if indegree[successor] == 0:
                successor_beat = beat_by_id[successor]
                heapq.heappush(
                    ready,
                    (phase_sequence.get(successor_beat.phase_ref, 0), successor),
                )
    if len(ordered) != len(beats):
        cyclic = sorted(beat_id for beat_id, degree in indegree.items() if degree > 0)
        issues.append(f"beats must form a DAG; cycle includes: {cyclic}")
        return tuple(
            sorted(
                beats,
                key=lambda value: (phase_sequence.get(value.phase_ref, 0), value.beat_id),
            )
        )
    return tuple(ordered)


def _parse_narrative_body(
    data: dict[str, Any], issues: list[str]
) -> tuple[
    str,
    NarrativeScope,
    tuple[NarrativePerspective, ...],
    tuple[NarrativeProposition, ...],
    tuple[NarrativePhase, ...],
    tuple[NarrativeBeat, ...],
]:
    model_id = _required_text(data, "model_id", "root", issues)
    _stable_id(model_id, "root.model_id", issues)
    scope = _parse_scope(data.get("scope"), "root.scope", issues)
    perspectives = _parse_perspectives(data.get("perspectives"), "root.perspectives", issues)
    propositions = _parse_propositions(data.get("propositions"), "root.propositions", issues)
    phases = _parse_phases(data.get("phases"), "root.phases", issues)
    beats = _parse_beats(data.get("beats"), "root.beats", issues)
    beats = _canonicalize_and_validate_body(
        scope, perspectives, propositions, phases, beats, issues
    )
    return model_id, scope, perspectives, propositions, phases, beats


def _validate_root(data: object) -> tuple[dict[str, Any], list[str]]:
    if not isinstance(data, dict):
        raise NarrativeModelValidationError(("root must be a JSON object",))
    issues: list[str] = []
    _unknown_keys(
        data,
        frozenset(
            {
                "format_version",
                "model_id",
                "source_registry",
                "scope",
                "perspectives",
                "propositions",
                "phases",
                "beats",
            }
        ),
        "root",
        issues,
    )
    version = data.get("format_version")
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version != 1
    ):
        issues.append("root.format_version must be 1")
    return data, issues


def validate_narrative_plan_document(data: object) -> NarrativePlan:
    """Strictly validate and canonically order a NarrativePlan v1 document."""

    root, issues = _validate_root(data)
    source_registry = _parse_source_registry_ref(
        root.get("source_registry"), "root.source_registry", issues
    )
    model_id, scope, perspectives, propositions, phases, beats = _parse_narrative_body(
        root, issues
    )
    if issues:
        raise NarrativeModelValidationError(tuple(issues))
    return NarrativePlan(
        format_version=1,
        model_id=model_id,
        source_registry=source_registry,
        scope=scope,
        perspectives=perspectives,
        propositions=propositions,
        phases=phases,
        beats=beats,
    )


def validate_narrative_model_document(data: object) -> NarrativeModel:
    """Strictly validate a standalone NarrativeModel v1 document."""

    root, issues = _validate_root(data)
    source_registry = _parse_source_registry_snapshot(
        root.get("source_registry"), "root.source_registry", issues
    )
    model_id, scope, perspectives, propositions, phases, beats = _parse_narrative_body(
        root, issues
    )
    referenced_promotions = {
        claim_ref.promotion_id
        for claim_ref in scope.claim_uses
    } | {
        omission.claim_ref.promotion_id for omission in scope.claim_omissions
    }
    source_promotions = {source.promotion_id for source in source_registry.sources}
    if referenced_promotions != source_promotions:
        issues.append(
            "source_registry.sources must exactly cover scoped claim promotions: "
            f"sources={sorted(source_promotions)}, claims={sorted(referenced_promotions)}"
        )
    if issues:
        raise NarrativeModelValidationError(tuple(issues))
    return NarrativeModel(
        format_version=1,
        model_id=model_id,
        source_registry=source_registry,
        scope=scope,
        perspectives=perspectives,
        propositions=propositions,
        phases=phases,
        beats=beats,
    )


def _claim_ref_document(value: NarrativeClaimRef) -> dict[str, str]:
    return {
        "promotion_id": value.promotion_id,
        "source_entity_id": value.source_entity_id,
        "source_claim_id": value.source_claim_id,
    }


def _scope_document(scope: NarrativeScope) -> dict[str, Any]:
    return {
        "entity_refs": list(scope.entity_refs),
        "claim_uses": [_claim_ref_document(value) for value in scope.claim_uses],
        "claim_omissions": [
            {
                "claim_ref": _claim_ref_document(value.claim_ref),
                "reason": value.reason,
            }
            for value in scope.claim_omissions
        ],
    }


def _body_document(value: NarrativePlan | NarrativeModel) -> dict[str, Any]:
    return {
        "format_version": value.format_version,
        "model_id": value.model_id,
        "scope": _scope_document(value.scope),
        "perspectives": [
            {
                "perspective_id": perspective.perspective_id,
                "entity_ref": perspective.entity_ref,
                "summary": perspective.summary,
            }
            for perspective in value.perspectives
        ],
        "propositions": [
            {
                "proposition_id": proposition.proposition_id,
                "statement": proposition.statement,
                "status": proposition.status,
                "claim_refs": [
                    _claim_ref_document(claim_ref)
                    for claim_ref in proposition.claim_refs
                ],
                "rationale": proposition.rationale,
            }
            for proposition in value.propositions
        ],
        "phases": [
            {
                "phase_id": phase.phase_id,
                "sequence": phase.sequence,
                "summary": phase.summary,
            }
            for phase in value.phases
        ],
        "beats": [
            {
                "beat_id": beat.beat_id,
                "phase_ref": beat.phase_ref,
                "predecessor_refs": list(beat.predecessor_refs),
                "perspective_refs": list(beat.perspective_refs),
                "proposition_refs": list(beat.proposition_refs),
                "disclosures": [
                    {
                        "perspective_ref": disclosure.perspective_ref,
                        "proposition_ref": disclosure.proposition_ref,
                        "state": disclosure.state,
                    }
                    for disclosure in beat.disclosures
                ],
                "summary": beat.summary,
            }
            for beat in value.beats
        ],
    }


def narrative_plan_to_document(plan: NarrativePlan) -> dict[str, Any]:
    """Serialize a validated plan in canonical order."""

    if not isinstance(plan, NarrativePlan):
        raise TypeError("plan must be NarrativePlan")
    document = _body_document(plan)
    document["source_registry"] = {
        "registry_id": plan.source_registry.registry_id,
        "registry_version": plan.source_registry.registry_version,
    }
    return document


def narrative_model_to_document(model: NarrativeModel) -> dict[str, Any]:
    """Serialize a validated narrative model in canonical order."""

    if not isinstance(model, NarrativeModel):
        raise TypeError("model must be NarrativeModel")
    document = _body_document(model)
    document["source_registry"] = {
        "registry_id": model.source_registry.registry_id,
        "registry_version": model.source_registry.registry_version,
        "sources": [
            {
                "promotion_id": source.promotion_id,
                "chapter_id": source.chapter_id,
                "chapter_sha256": source.chapter_sha256,
                "extracted_by": source.extracted_by,
                "review_id": source.review_id,
                "reviewed_by": source.reviewed_by,
            }
            for source in model.source_registry.sources
        ],
    }
    return document


def compile_narrative_model(
    registry: CanonRegistry, plan: NarrativePlan
) -> NarrativeModel:
    """Bind an explicit plan to exact registry claims without generating canon."""

    if not isinstance(registry, CanonRegistry):
        raise NarrativeModelBuildError(("registry must be CanonRegistry",))
    if not isinstance(plan, NarrativePlan):
        raise NarrativeModelBuildError(("plan must be NarrativePlan",))

    issues: list[str] = []
    try:
        normalized_registry = validate_canon_registry_document(
            canon_registry_to_document(registry)
        )
    except (AttributeError, TypeError) as exc:
        raise NarrativeModelBuildError((f"invalid typed source registry: {exc}",)) from exc
    except CanonRegistryValidationError as exc:
        raise NarrativeModelBuildError(
            tuple(f"invalid source registry: {issue}" for issue in exc.issues)
        ) from exc
    if normalized_registry != registry:
        issues.append("registry must already use canonical validated ordering")
    try:
        normalized_plan = validate_narrative_plan_document(
            narrative_plan_to_document(plan)
        )
    except (AttributeError, TypeError) as exc:
        raise NarrativeModelBuildError((f"invalid typed narrative plan: {exc}",)) from exc
    except NarrativeModelValidationError as exc:
        raise NarrativeModelBuildError(
            tuple(f"invalid narrative plan: {issue}" for issue in exc.issues)
        ) from exc
    if normalized_plan != plan:
        issues.append("plan must already use canonical validated ordering")

    if plan.source_registry.registry_id != registry.registry_id:
        issues.append(
            "plan source_registry.registry_id does not match the CanonRegistry: "
            f"{plan.source_registry.registry_id!r} != {registry.registry_id!r}"
        )
    if plan.source_registry.registry_version != registry.registry_version:
        issues.append(
            "plan source_registry.registry_version does not match the CanonRegistry: "
            f"{plan.source_registry.registry_version} != {registry.registry_version}"
        )

    entities_by_id = {entity.entity_id: entity for entity in registry.entities}
    missing_entities = sorted(set(plan.scope.entity_refs) - set(entities_by_id))
    if missing_entities:
        issues.append(f"scope references unknown registry entities: {missing_entities}")

    expected_claims: dict[tuple[str, str, str], str] = {}
    for entity_ref in plan.scope.entity_refs:
        entity = entities_by_id.get(entity_ref)
        if entity is None:
            continue
        if not entity.claims:
            issues.append(f"scoped registry entity has no claims: {entity_ref}")
        for claim in entity.claims:
            key = (
                claim.source.promotion_id,
                claim.source.source_entity_id,
                claim.source.source_claim_id,
            )
            expected_claims[key] = entity_ref

    used_keys = {_claim_key(value) for value in plan.scope.claim_uses}
    omitted_keys = {
        _claim_key(value.claim_ref) for value in plan.scope.claim_omissions
    }
    accounted_keys = used_keys | omitted_keys
    missing_claims = sorted(set(expected_claims) - accounted_keys)
    foreign_claims = sorted(accounted_keys - set(expected_claims))
    if missing_claims:
        issues.append(
            f"scope does not use or reasonedly omit registry claims: {missing_claims!r}"
        )
    if foreign_claims:
        issues.append(f"scope references foreign registry claims: {foreign_claims!r}")

    sources_by_promotion = {
        source.promotion_id: source for source in registry.sources
    }
    used_promotions = {key[0] for key in accounted_keys}
    missing_sources = sorted(used_promotions - set(sources_by_promotion))
    if missing_sources:
        issues.append(f"scoped claims reference missing registry sources: {missing_sources}")
    if issues:
        raise NarrativeModelBuildError(tuple(issues))

    model = NarrativeModel(
        format_version=1,
        model_id=plan.model_id,
        source_registry=SourceRegistrySnapshot(
            registry_id=registry.registry_id,
            registry_version=registry.registry_version,
            sources=tuple(
                sorted(
                    (sources_by_promotion[value] for value in used_promotions),
                    key=lambda source: (source.chapter_id, source.promotion_id),
                )
            ),
        ),
        scope=plan.scope,
        perspectives=plan.perspectives,
        propositions=plan.propositions,
        phases=plan.phases,
        beats=plan.beats,
    )
    try:
        revalidated = validate_narrative_model_document(
            narrative_model_to_document(model)
        )
    except NarrativeModelValidationError as exc:
        raise NarrativeModelBuildError(
            tuple(f"generated NarrativeModel is invalid: {issue}" for issue in exc.issues)
        ) from exc
    if revalidated != model:
        raise NarrativeModelBuildError(
            ("generated NarrativeModel changed during canonical revalidation",)
        )
    return model


def _is_link_like(path: str | os.PathLike[str]) -> bool:
    try:
        metadata = os.lstat(path)
    except FileNotFoundError:
        return False
    if stat.S_ISLNK(metadata.st_mode):
        return True
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(reparse_flag and attributes & reparse_flag)


def _paths_alias(
    first: str | os.PathLike[str], second: str | os.PathLike[str]
) -> bool:
    first_real = os.path.realpath(os.path.abspath(first))
    second_real = os.path.realpath(os.path.abspath(second))
    if os.path.normcase(first_real) == os.path.normcase(second_real):
        return True
    try:
        return os.path.exists(first_real) and os.path.exists(second_real) and os.path.samefile(
            first_real, second_real
        )
    except OSError:
        return False


def write_narrative_model(
    model: NarrativeModel, output_path: str | os.PathLike[str]
) -> Path:
    """Atomically publish a validated model and preserve old output on failure."""

    try:
        document = narrative_model_to_document(model)
    except (AttributeError, TypeError) as exc:
        raise NarrativeModelValidationError(
            (f"invalid typed NarrativeModel: {exc}",)
        ) from exc
    revalidated = validate_narrative_model_document(document)
    if revalidated != model:
        raise NarrativeModelValidationError(
            ("NarrativeModel changed during canonical revalidation",)
        )

    output = Path(output_path)
    if _is_link_like(output):
        raise OSError(f"output path must not be a symbolic link or reparse point: {output}")
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
            dir=parent, prefix=f".{output.name}.", suffix=".tmp"
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


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for deterministic narrative-model compilation."""

    parser = argparse.ArgumentParser(
        description="Compile a deterministic NarrativeModel v1 from a CanonRegistry."
    )
    parser.add_argument(
        "--canon-registry", required=True, help="CanonRegistry v1 JSON input path"
    )
    parser.add_argument(
        "--narrative-plan", required=True, help="NarrativePlan v1 JSON input path"
    )
    parser.add_argument(
        "--output", required=True, help="NarrativeModel v1 JSON output path"
    )
    args = parser.parse_args(argv)

    inputs = [args.canon_registry, args.narrative_plan]
    for input_path in inputs:
        if _is_link_like(input_path):
            print(
                f"Input path must not be a symbolic link or reparse point: {input_path}",
                file=sys.stderr,
            )
            return 1
    if _paths_alias(inputs[0], inputs[1]):
        print(
            f"Input paths point to the same file: {inputs[0]} and {inputs[1]}",
            file=sys.stderr,
        )
        return 1
    if _is_link_like(args.output):
        print(
            f"Output path must not be a symbolic link or reparse point: {args.output}",
            file=sys.stderr,
        )
        return 1
    for input_path in inputs:
        if _paths_alias(args.output, input_path):
            print(
                f"Output ({args.output}) points to an input file ({input_path})",
                file=sys.stderr,
            )
            return 1

    try:
        with open(args.canon_registry, "r", encoding="utf-8") as handle:
            registry = validate_canon_registry_document(json.load(handle))
        with open(args.narrative_plan, "r", encoding="utf-8") as handle:
            plan = validate_narrative_plan_document(json.load(handle))
        model = compile_narrative_model(registry, plan)
        write_narrative_model(model, args.output)
    except json.JSONDecodeError as exc:
        print(f"JSON parse error: {exc}", file=sys.stderr)
        return 1
    except UnicodeDecodeError as exc:
        print(f"UTF-8 decode error: {exc}", file=sys.stderr)
        return 1
    except CanonRegistryValidationError as exc:
        print(f"CanonRegistry error: {exc}", file=sys.stderr)
        return 1
    except NarrativeModelValidationError as exc:
        print(f"Narrative validation error: {exc}", file=sys.stderr)
        return 1
    except NarrativeModelBuildError as exc:
        print(f"Narrative build error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"I/O error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
