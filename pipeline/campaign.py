"""Compile a deterministic CampaignSpec v1 from a NarrativeModel v1.

Public API::

    validate_registry_campaign_plan_document(data) -> RegistryCampaignPlan
    compile_campaign_spec(model, plan) -> CampaignSpec
    validate_campaign_spec_document(data) -> CampaignSpec
    registry_campaign_plan_to_document(plan) -> dict
    campaign_spec_to_document(spec) -> dict
    narrative_model_sha256(model) -> str
    write_campaign_spec(spec, output_path) -> Path

CLI::

    python -m pipeline.campaign \
        --narrative-model narrative_model.json \
        --campaign-plan registry_campaign_plan.json \
        --output campaign_spec.json

Exit codes: 0=success, 1=data/build/I/O error, 2=argument error.
"""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import os
import re
import stat
import sys
import tempfile
import unicodedata
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TypeAlias

from pipeline.narrative_model import (
    DisclosureState,
    NarrativeModel,
    NarrativeModelValidationError,
    narrative_model_to_document,
    validate_narrative_model_document,
)


class CampaignValidationError(ValueError):
    """Raised when a RegistryCampaignPlan or CampaignSpec is invalid."""

    def __init__(self, issues: tuple[str, ...]) -> None:
        self.issues = issues
        super().__init__("\n".join(f"- {issue}" for issue in issues))


class CampaignBuildError(ValueError):
    """Raised when a validated NarrativeModel cannot satisfy a campaign plan."""

    def __init__(self, issues: tuple[str, ...]) -> None:
        self.issues = issues
        super().__init__("\n".join(f"- {issue}" for issue in issues))


ActorKind: TypeAlias = Literal["player", "character", "adversary"]
SceneKind: TypeAlias = Literal[
    "exploration",
    "conversation",
    "conflict",
    "ritual",
    "internal",
    "revelation",
]

_STABLE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ACTOR_KINDS = frozenset({"player", "character", "adversary"})
_SCENE_KINDS = frozenset(
    {"exploration", "conversation", "conflict", "ritual", "internal", "revelation"}
)
_DISCLOSURE_STATES = frozenset({"heard", "suspected", "confirmed", "retracted"})


@dataclass(frozen=True, slots=True)
class SourceNarrativeModelRef:
    format_version: int
    model_id: str
    narrative_model_sha256: str


@dataclass(frozen=True, slots=True)
class CampaignOmission:
    source_ref: str
    reason: str


@dataclass(frozen=True, slots=True)
class CampaignScope:
    entity_uses: tuple[str, ...]
    entity_omissions: tuple[CampaignOmission, ...]
    perspective_uses: tuple[str, ...]
    perspective_omissions: tuple[CampaignOmission, ...]
    proposition_uses: tuple[str, ...]
    proposition_omissions: tuple[CampaignOmission, ...]
    beat_uses: tuple[str, ...]
    beat_omissions: tuple[CampaignOmission, ...]


@dataclass(frozen=True, slots=True)
class CampaignExit:
    direction: str
    name: str
    target_location_ref: str


@dataclass(frozen=True, slots=True)
class CampaignLocation:
    location_id: str
    name: str
    description: str
    source_entity_refs: tuple[str, ...]
    source_proposition_refs: tuple[str, ...]
    adaptation_notes: str
    exits: tuple[CampaignExit, ...]


@dataclass(frozen=True, slots=True)
class CampaignActor:
    actor_id: str
    kind: ActorKind
    name: str
    description: str
    source_entity_ref: str | None
    starting_location_ref: str | None
    source_proposition_refs: tuple[str, ...]
    adaptation_notes: str


@dataclass(frozen=True, slots=True)
class CampaignScene:
    scene_id: str
    kind: SceneKind
    phase_ref: str
    location_ref: str | None
    participating_actor_refs: tuple[str, ...]
    narrative_beat_refs: tuple[str, ...]
    predecessor_scene_refs: tuple[str, ...]
    source_proposition_refs: tuple[str, ...]
    adaptation_notes: str


@dataclass(frozen=True, slots=True)
class ReachLocationCompletion:
    kind: Literal["reach_location"]
    location_ref: str


@dataclass(frozen=True, slots=True)
class InteractActorCompletion:
    kind: Literal["interact_actor"]
    actor_ref: str


@dataclass(frozen=True, slots=True)
class CompleteSceneCompletion:
    kind: Literal["complete_scene"]
    scene_ref: str


@dataclass(frozen=True, slots=True)
class ApplyKnowledgeCompletion:
    kind: Literal["apply_knowledge"]
    knowledge_ref: str


ObjectiveCompletion: TypeAlias = (
    ReachLocationCompletion
    | InteractActorCompletion
    | CompleteSceneCompletion
    | ApplyKnowledgeCompletion
)


@dataclass(frozen=True, slots=True)
class CampaignObjective:
    objective_id: str
    title: str
    description: str
    phase_ref: str
    scene_refs: tuple[str, ...]
    predecessor_objective_refs: tuple[str, ...]
    mutually_exclusive_objective_refs: tuple[str, ...]
    source_proposition_refs: tuple[str, ...]
    completion: ObjectiveCompletion
    adaptation_notes: str


@dataclass(frozen=True, slots=True)
class CampaignKnowledgeBeat:
    knowledge_id: str
    scene_ref: str
    actor_ref: str
    source_beat_ref: str
    perspective_ref: str
    proposition_ref: str
    state: DisclosureState
    adaptation_notes: str


@dataclass(frozen=True, slots=True)
class CampaignKnowledgeCorrection:
    correction_id: str
    scene_ref: str
    actor_ref: str
    state: Literal["corrected"]
    corrects_knowledge_ref: str
    earlier_proposition_ref: str
    later_proposition_ref: str
    rationale: str


@dataclass(frozen=True, slots=True)
class RegistryCampaignPlan:
    format_version: int
    campaign_id: str
    source_narrative_model: SourceNarrativeModelRef
    adaptation_rationale: str
    scope: CampaignScope
    start_location_ref: str
    locations: tuple[CampaignLocation, ...]
    actors: tuple[CampaignActor, ...]
    scenes: tuple[CampaignScene, ...]
    objectives: tuple[CampaignObjective, ...]
    knowledge_beats: tuple[CampaignKnowledgeBeat, ...]
    knowledge_corrections: tuple[CampaignKnowledgeCorrection, ...]


@dataclass(frozen=True, slots=True)
class CampaignSpec:
    format_version: int
    campaign_id: str
    source_narrative_model: NarrativeModel
    adaptation_rationale: str
    scope: CampaignScope
    start_location_ref: str
    locations: tuple[CampaignLocation, ...]
    actors: tuple[CampaignActor, ...]
    scenes: tuple[CampaignScene, ...]
    objectives: tuple[CampaignObjective, ...]
    knowledge_beats: tuple[CampaignKnowledgeBeat, ...]
    knowledge_corrections: tuple[CampaignKnowledgeCorrection, ...]


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


def _stable_id(value: str, loc: str, issues: list[str]) -> None:
    if value and not _STABLE_ID_RE.fullmatch(value):
        issues.append(f"{loc} must match stable ID format ^[a-z][a-z0-9_]*$")


def _required_stable_id(
    obj: dict[str, Any], key: str, loc: str, issues: list[str]
) -> str:
    value = _required_text(obj, key, loc, issues)
    _stable_id(value, f"{loc}.{key}", issues)
    return value


def _nullable_stable_id(
    obj: dict[str, Any], key: str, loc: str, issues: list[str]
) -> str | None:
    if key not in obj:
        issues.append(f"{loc}.{key} is required and must be a stable ID or null")
        return None
    value = obj[key]
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        issues.append(f"{loc}.{key} must be a stable ID or null")
        return None
    _stable_id(value, f"{loc}.{key}", issues)
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


def _parse_source_narrative_ref(
    raw: object, loc: str, issues: list[str]
) -> SourceNarrativeModelRef:
    if not isinstance(raw, dict):
        issues.append(f"{loc} must be an object")
        raw = {}
    _unknown_keys(
        raw,
        frozenset({"format_version", "model_id", "narrative_model_sha256"}),
        loc,
        issues,
    )
    version = raw.get("format_version")
    if isinstance(version, bool) or not isinstance(version, int) or version != 1:
        issues.append(f"{loc}.format_version must be 1")
    sha256 = _required_text(raw, "narrative_model_sha256", loc, issues)
    if sha256 and not _SHA256_RE.fullmatch(sha256):
        issues.append(
            f"{loc}.narrative_model_sha256 must be 64 lowercase hexadecimal characters"
        )
    return SourceNarrativeModelRef(
        format_version=1,
        model_id=_required_stable_id(raw, "model_id", loc, issues),
        narrative_model_sha256=sha256,
    )


def _parse_omissions(
    raw: object, loc: str, ref_field: str, issues: list[str]
) -> tuple[CampaignOmission, ...]:
    if not isinstance(raw, list):
        issues.append(f"{loc} must be an array")
        return ()
    parsed: list[CampaignOmission] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw):
        entry_loc = f"{loc}[{index}]"
        if not isinstance(entry, dict):
            issues.append(f"{entry_loc} must be an object")
            continue
        _unknown_keys(entry, frozenset({ref_field, "reason"}), entry_loc, issues)
        source_ref = _required_stable_id(entry, ref_field, entry_loc, issues)
        if source_ref in seen:
            issues.append(f"{entry_loc}.{ref_field} is duplicated: {source_ref}")
        seen.add(source_ref)
        parsed.append(
            CampaignOmission(
                source_ref=source_ref,
                reason=_required_text(entry, "reason", entry_loc, issues),
            )
        )
    return tuple(sorted(parsed, key=lambda value: value.source_ref))


def _parse_scope(raw: object, loc: str, issues: list[str]) -> CampaignScope:
    if not isinstance(raw, dict):
        issues.append(f"{loc} must be an object")
        raw = {}
    fields = frozenset(
        {
            "entity_uses",
            "entity_omissions",
            "perspective_uses",
            "perspective_omissions",
            "proposition_uses",
            "proposition_omissions",
            "beat_uses",
            "beat_omissions",
        }
    )
    _unknown_keys(raw, fields, loc, issues)
    scope = CampaignScope(
        entity_uses=_parse_stable_id_array(
            raw.get("entity_uses"), f"{loc}.entity_uses", issues, nonempty=False
        ),
        entity_omissions=_parse_omissions(
            raw.get("entity_omissions"),
            f"{loc}.entity_omissions",
            "entity_ref",
            issues,
        ),
        perspective_uses=_parse_stable_id_array(
            raw.get("perspective_uses"),
            f"{loc}.perspective_uses",
            issues,
            nonempty=False,
        ),
        perspective_omissions=_parse_omissions(
            raw.get("perspective_omissions"),
            f"{loc}.perspective_omissions",
            "perspective_ref",
            issues,
        ),
        proposition_uses=_parse_stable_id_array(
            raw.get("proposition_uses"),
            f"{loc}.proposition_uses",
            issues,
            nonempty=False,
        ),
        proposition_omissions=_parse_omissions(
            raw.get("proposition_omissions"),
            f"{loc}.proposition_omissions",
            "proposition_ref",
            issues,
        ),
        beat_uses=_parse_stable_id_array(
            raw.get("beat_uses"), f"{loc}.beat_uses", issues, nonempty=False
        ),
        beat_omissions=_parse_omissions(
            raw.get("beat_omissions"),
            f"{loc}.beat_omissions",
            "beat_ref",
            issues,
        ),
    )
    categories = (
        ("entity", set(scope.entity_uses), {value.source_ref for value in scope.entity_omissions}),
        (
            "perspective",
            set(scope.perspective_uses),
            {value.source_ref for value in scope.perspective_omissions},
        ),
        (
            "proposition",
            set(scope.proposition_uses),
            {value.source_ref for value in scope.proposition_omissions},
        ),
        ("beat", set(scope.beat_uses), {value.source_ref for value in scope.beat_omissions}),
    )
    for name, used, omitted in categories:
        overlap = sorted(used & omitted)
        if overlap:
            issues.append(f"{loc} uses and omits the same {name} refs: {overlap}")
    return scope


def _parse_exits(
    raw: object, loc: str, issues: list[str]
) -> tuple[CampaignExit, ...]:
    if not isinstance(raw, list):
        issues.append(f"{loc} must be an array")
        return ()
    parsed: list[CampaignExit] = []
    directions: set[str] = set()
    names: set[str] = set()
    for index, entry in enumerate(raw):
        entry_loc = f"{loc}[{index}]"
        if not isinstance(entry, dict):
            issues.append(f"{entry_loc} must be an object")
            continue
        _unknown_keys(
            entry,
            frozenset({"direction", "name", "target_location_ref"}),
            entry_loc,
            issues,
        )
        direction = _required_text(entry, "direction", entry_loc, issues)
        name = _required_text(entry, "name", entry_loc, issues)
        target = _required_stable_id(entry, "target_location_ref", entry_loc, issues)
        direction_key = _normalization_key(direction)
        name_key = _normalization_key(name)
        if direction_key in directions:
            issues.append(f"{entry_loc}.direction duplicates a route label: {direction!r}")
        if name_key in names:
            issues.append(f"{entry_loc}.name duplicates a route label: {name!r}")
        directions.add(direction_key)
        names.add(name_key)
        parsed.append(CampaignExit(direction=direction, name=name, target_location_ref=target))
    return tuple(
        sorted(
            parsed,
            key=lambda value: (
                _normalization_key(value.direction),
                _normalization_key(value.name),
                value.target_location_ref,
            ),
        )
    )


def _parse_locations(
    raw: object, loc: str, issues: list[str]
) -> tuple[CampaignLocation, ...]:
    if not isinstance(raw, list):
        issues.append(f"{loc} must be an array")
        return ()
    if not raw:
        issues.append(f"{loc} must not be empty")
    parsed: list[CampaignLocation] = []
    seen: set[str] = set()
    allowed = frozenset(
        {
            "location_id",
            "name",
            "description",
            "source_entity_refs",
            "source_proposition_refs",
            "adaptation_notes",
            "exits",
        }
    )
    for index, entry in enumerate(raw):
        entry_loc = f"{loc}[{index}]"
        if not isinstance(entry, dict):
            issues.append(f"{entry_loc} must be an object")
            continue
        _unknown_keys(entry, allowed, entry_loc, issues)
        location_id = _required_stable_id(entry, "location_id", entry_loc, issues)
        if location_id in seen:
            issues.append(f"{entry_loc}.location_id is duplicated: {location_id}")
        seen.add(location_id)
        parsed.append(
            CampaignLocation(
                location_id=location_id,
                name=_required_text(entry, "name", entry_loc, issues),
                description=_required_text(entry, "description", entry_loc, issues),
                source_entity_refs=_parse_stable_id_array(
                    entry.get("source_entity_refs"),
                    f"{entry_loc}.source_entity_refs",
                    issues,
                    nonempty=False,
                ),
                source_proposition_refs=_parse_stable_id_array(
                    entry.get("source_proposition_refs"),
                    f"{entry_loc}.source_proposition_refs",
                    issues,
                    nonempty=False,
                ),
                adaptation_notes=_required_text(
                    entry, "adaptation_notes", entry_loc, issues
                ),
                exits=_parse_exits(entry.get("exits"), f"{entry_loc}.exits", issues),
            )
        )
    return tuple(sorted(parsed, key=lambda value: value.location_id))


def _parse_actors(
    raw: object, loc: str, issues: list[str]
) -> tuple[CampaignActor, ...]:
    if not isinstance(raw, list):
        issues.append(f"{loc} must be an array")
        return ()
    if not raw:
        issues.append(f"{loc} must not be empty")
    parsed: list[CampaignActor] = []
    seen: set[str] = set()
    allowed = frozenset(
        {
            "actor_id",
            "kind",
            "name",
            "description",
            "source_entity_ref",
            "starting_location_ref",
            "source_proposition_refs",
            "adaptation_notes",
        }
    )
    for index, entry in enumerate(raw):
        entry_loc = f"{loc}[{index}]"
        if not isinstance(entry, dict):
            issues.append(f"{entry_loc} must be an object")
            continue
        _unknown_keys(entry, allowed, entry_loc, issues)
        actor_id = _required_stable_id(entry, "actor_id", entry_loc, issues)
        if actor_id in seen:
            issues.append(f"{entry_loc}.actor_id is duplicated: {actor_id}")
        seen.add(actor_id)
        raw_kind = entry.get("kind")
        if not isinstance(raw_kind, str) or raw_kind not in _ACTOR_KINDS:
            issues.append(f"{entry_loc}.kind must be one of {sorted(_ACTOR_KINDS)}")
            kind: ActorKind = "character"
        else:
            kind = raw_kind  # type: ignore[assignment]
        parsed.append(
            CampaignActor(
                actor_id=actor_id,
                kind=kind,
                name=_required_text(entry, "name", entry_loc, issues),
                description=_required_text(entry, "description", entry_loc, issues),
                source_entity_ref=_nullable_stable_id(
                    entry, "source_entity_ref", entry_loc, issues
                ),
                starting_location_ref=_nullable_stable_id(
                    entry, "starting_location_ref", entry_loc, issues
                ),
                source_proposition_refs=_parse_stable_id_array(
                    entry.get("source_proposition_refs"),
                    f"{entry_loc}.source_proposition_refs",
                    issues,
                    nonempty=False,
                ),
                adaptation_notes=_required_text(
                    entry, "adaptation_notes", entry_loc, issues
                ),
            )
        )
    players = sorted(value.actor_id for value in parsed if value.kind == "player")
    if len(players) != 1:
        issues.append(f"{loc} must contain exactly one player actor; found {players}")
    return tuple(sorted(parsed, key=lambda value: value.actor_id))


def _parse_scenes(
    raw: object, loc: str, issues: list[str]
) -> tuple[CampaignScene, ...]:
    if not isinstance(raw, list):
        issues.append(f"{loc} must be an array")
        return ()
    if not raw:
        issues.append(f"{loc} must not be empty")
    parsed: list[CampaignScene] = []
    seen: set[str] = set()
    allowed = frozenset(
        {
            "scene_id",
            "kind",
            "phase_ref",
            "location_ref",
            "participating_actor_refs",
            "narrative_beat_refs",
            "predecessor_scene_refs",
            "source_proposition_refs",
            "adaptation_notes",
        }
    )
    for index, entry in enumerate(raw):
        entry_loc = f"{loc}[{index}]"
        if not isinstance(entry, dict):
            issues.append(f"{entry_loc} must be an object")
            continue
        _unknown_keys(entry, allowed, entry_loc, issues)
        scene_id = _required_stable_id(entry, "scene_id", entry_loc, issues)
        if scene_id in seen:
            issues.append(f"{entry_loc}.scene_id is duplicated: {scene_id}")
        seen.add(scene_id)
        raw_kind = entry.get("kind")
        if not isinstance(raw_kind, str) or raw_kind not in _SCENE_KINDS:
            issues.append(f"{entry_loc}.kind must be one of {sorted(_SCENE_KINDS)}")
            kind: SceneKind = "exploration"
        else:
            kind = raw_kind  # type: ignore[assignment]
        parsed.append(
            CampaignScene(
                scene_id=scene_id,
                kind=kind,
                phase_ref=_required_stable_id(entry, "phase_ref", entry_loc, issues),
                location_ref=_nullable_stable_id(
                    entry, "location_ref", entry_loc, issues
                ),
                participating_actor_refs=_parse_stable_id_array(
                    entry.get("participating_actor_refs"),
                    f"{entry_loc}.participating_actor_refs",
                    issues,
                    nonempty=True,
                ),
                narrative_beat_refs=_parse_stable_id_array(
                    entry.get("narrative_beat_refs"),
                    f"{entry_loc}.narrative_beat_refs",
                    issues,
                    nonempty=False,
                ),
                predecessor_scene_refs=_parse_stable_id_array(
                    entry.get("predecessor_scene_refs"),
                    f"{entry_loc}.predecessor_scene_refs",
                    issues,
                    nonempty=False,
                ),
                source_proposition_refs=_parse_stable_id_array(
                    entry.get("source_proposition_refs"),
                    f"{entry_loc}.source_proposition_refs",
                    issues,
                    nonempty=False,
                ),
                adaptation_notes=_required_text(
                    entry, "adaptation_notes", entry_loc, issues
                ),
            )
        )
    return tuple(parsed)


def _parse_completion(
    raw: object, loc: str, issues: list[str]
) -> ObjectiveCompletion:
    if not isinstance(raw, dict):
        issues.append(f"{loc} must be an object")
        return CompleteSceneCompletion(kind="complete_scene", scene_ref="")
    raw_kind = raw.get("kind")
    if raw_kind == "reach_location":
        _unknown_keys(raw, frozenset({"kind", "location_ref"}), loc, issues)
        return ReachLocationCompletion(
            kind="reach_location",
            location_ref=_required_stable_id(raw, "location_ref", loc, issues),
        )
    if raw_kind == "interact_actor":
        _unknown_keys(raw, frozenset({"kind", "actor_ref"}), loc, issues)
        return InteractActorCompletion(
            kind="interact_actor",
            actor_ref=_required_stable_id(raw, "actor_ref", loc, issues),
        )
    if raw_kind == "complete_scene":
        _unknown_keys(raw, frozenset({"kind", "scene_ref"}), loc, issues)
        return CompleteSceneCompletion(
            kind="complete_scene",
            scene_ref=_required_stable_id(raw, "scene_ref", loc, issues),
        )
    if raw_kind == "apply_knowledge":
        _unknown_keys(raw, frozenset({"kind", "knowledge_ref"}), loc, issues)
        return ApplyKnowledgeCompletion(
            kind="apply_knowledge",
            knowledge_ref=_required_stable_id(raw, "knowledge_ref", loc, issues),
        )
    issues.append(
        f"{loc}.kind must be one of "
        "['apply_knowledge', 'complete_scene', 'interact_actor', 'reach_location']"
    )
    _unknown_keys(raw, frozenset({"kind"}), loc, issues)
    return CompleteSceneCompletion(kind="complete_scene", scene_ref="")


def _parse_objectives(
    raw: object, loc: str, issues: list[str]
) -> tuple[CampaignObjective, ...]:
    if not isinstance(raw, list):
        issues.append(f"{loc} must be an array")
        return ()
    if not raw:
        issues.append(f"{loc} must not be empty")
    parsed: list[CampaignObjective] = []
    seen: set[str] = set()
    allowed = frozenset(
        {
            "objective_id",
            "title",
            "description",
            "phase_ref",
            "scene_refs",
            "predecessor_objective_refs",
            "mutually_exclusive_objective_refs",
            "source_proposition_refs",
            "completion",
            "adaptation_notes",
        }
    )
    for index, entry in enumerate(raw):
        entry_loc = f"{loc}[{index}]"
        if not isinstance(entry, dict):
            issues.append(f"{entry_loc} must be an object")
            continue
        _unknown_keys(entry, allowed, entry_loc, issues)
        objective_id = _required_stable_id(entry, "objective_id", entry_loc, issues)
        if objective_id in seen:
            issues.append(f"{entry_loc}.objective_id is duplicated: {objective_id}")
        seen.add(objective_id)
        parsed.append(
            CampaignObjective(
                objective_id=objective_id,
                title=_required_text(entry, "title", entry_loc, issues),
                description=_required_text(entry, "description", entry_loc, issues),
                phase_ref=_required_stable_id(entry, "phase_ref", entry_loc, issues),
                scene_refs=_parse_stable_id_array(
                    entry.get("scene_refs"),
                    f"{entry_loc}.scene_refs",
                    issues,
                    nonempty=True,
                ),
                predecessor_objective_refs=_parse_stable_id_array(
                    entry.get("predecessor_objective_refs"),
                    f"{entry_loc}.predecessor_objective_refs",
                    issues,
                    nonempty=False,
                ),
                mutually_exclusive_objective_refs=_parse_stable_id_array(
                    entry.get("mutually_exclusive_objective_refs"),
                    f"{entry_loc}.mutually_exclusive_objective_refs",
                    issues,
                    nonempty=False,
                ),
                source_proposition_refs=_parse_stable_id_array(
                    entry.get("source_proposition_refs"),
                    f"{entry_loc}.source_proposition_refs",
                    issues,
                    nonempty=False,
                ),
                completion=_parse_completion(
                    entry.get("completion"), f"{entry_loc}.completion", issues
                ),
                adaptation_notes=_required_text(
                    entry, "adaptation_notes", entry_loc, issues
                ),
            )
        )
    return tuple(parsed)


def _parse_knowledge_beats(
    raw: object, loc: str, issues: list[str]
) -> tuple[CampaignKnowledgeBeat, ...]:
    if not isinstance(raw, list):
        issues.append(f"{loc} must be an array")
        return ()
    parsed: list[CampaignKnowledgeBeat] = []
    seen: set[str] = set()
    projections: set[tuple[str, str, str, str, str]] = set()
    allowed = frozenset(
        {
            "knowledge_id",
            "scene_ref",
            "actor_ref",
            "source_beat_ref",
            "perspective_ref",
            "proposition_ref",
            "state",
            "adaptation_notes",
        }
    )
    for index, entry in enumerate(raw):
        entry_loc = f"{loc}[{index}]"
        if not isinstance(entry, dict):
            issues.append(f"{entry_loc} must be an object")
            continue
        _unknown_keys(entry, allowed, entry_loc, issues)
        knowledge_id = _required_stable_id(entry, "knowledge_id", entry_loc, issues)
        if knowledge_id in seen:
            issues.append(f"{entry_loc}.knowledge_id is duplicated: {knowledge_id}")
        seen.add(knowledge_id)
        actor_ref = _required_stable_id(entry, "actor_ref", entry_loc, issues)
        source_beat_ref = _required_stable_id(
            entry, "source_beat_ref", entry_loc, issues
        )
        perspective_ref = _required_stable_id(
            entry, "perspective_ref", entry_loc, issues
        )
        proposition_ref = _required_stable_id(
            entry, "proposition_ref", entry_loc, issues
        )
        raw_state = entry.get("state")
        if not isinstance(raw_state, str) or raw_state not in _DISCLOSURE_STATES:
            issues.append(
                f"{entry_loc}.state must be one of {sorted(_DISCLOSURE_STATES)}"
            )
            state: DisclosureState = "heard"
        else:
            state = raw_state  # type: ignore[assignment]
        projection = (
            actor_ref,
            source_beat_ref,
            perspective_ref,
            proposition_ref,
            state,
        )
        if projection in projections:
            issues.append(f"{entry_loc} duplicates a knowledge projection: {projection!r}")
        projections.add(projection)
        parsed.append(
            CampaignKnowledgeBeat(
                knowledge_id=knowledge_id,
                scene_ref=_required_stable_id(entry, "scene_ref", entry_loc, issues),
                actor_ref=actor_ref,
                source_beat_ref=source_beat_ref,
                perspective_ref=perspective_ref,
                proposition_ref=proposition_ref,
                state=state,
                adaptation_notes=_required_text(
                    entry, "adaptation_notes", entry_loc, issues
                ),
            )
        )
    return tuple(parsed)


def _parse_knowledge_corrections(
    raw: object, loc: str, issues: list[str]
) -> tuple[CampaignKnowledgeCorrection, ...]:
    if not isinstance(raw, list):
        issues.append(f"{loc} must be an array")
        return ()
    parsed: list[CampaignKnowledgeCorrection] = []
    seen: set[str] = set()
    allowed = frozenset(
        {
            "correction_id",
            "scene_ref",
            "actor_ref",
            "state",
            "corrects_knowledge_ref",
            "earlier_proposition_ref",
            "later_proposition_ref",
            "rationale",
        }
    )
    for index, entry in enumerate(raw):
        entry_loc = f"{loc}[{index}]"
        if not isinstance(entry, dict):
            issues.append(f"{entry_loc} must be an object")
            continue
        _unknown_keys(entry, allowed, entry_loc, issues)
        correction_id = _required_stable_id(
            entry, "correction_id", entry_loc, issues
        )
        if correction_id in seen:
            issues.append(f"{entry_loc}.correction_id is duplicated: {correction_id}")
        seen.add(correction_id)
        raw_state = entry.get("state")
        if raw_state != "corrected":
            issues.append(f"{entry_loc}.state must be 'corrected'")
        earlier = _required_stable_id(
            entry, "earlier_proposition_ref", entry_loc, issues
        )
        later = _required_stable_id(
            entry, "later_proposition_ref", entry_loc, issues
        )
        if earlier == later and earlier:
            issues.append(
                f"{entry_loc} must name different earlier and later proposition refs"
            )
        parsed.append(
            CampaignKnowledgeCorrection(
                correction_id=correction_id,
                scene_ref=_required_stable_id(entry, "scene_ref", entry_loc, issues),
                actor_ref=_required_stable_id(entry, "actor_ref", entry_loc, issues),
                state="corrected",
                corrects_knowledge_ref=_required_stable_id(
                    entry, "corrects_knowledge_ref", entry_loc, issues
                ),
                earlier_proposition_ref=earlier,
                later_proposition_ref=later,
                rationale=_required_text(entry, "rationale", entry_loc, issues),
            )
        )
    return tuple(parsed)


def _topological_ids(
    ids: set[str],
    predecessors: dict[str, tuple[str, ...]],
    label: str,
    issues: list[str],
) -> tuple[str, ...]:
    successors: dict[str, list[str]] = {value: [] for value in ids}
    indegree: dict[str, int] = {value: 0 for value in ids}
    for item_id in sorted(ids):
        for predecessor_ref in predecessors.get(item_id, ()):
            if predecessor_ref == item_id:
                issues.append(f"{label} {item_id} cannot depend on itself")
                continue
            if predecessor_ref not in ids:
                issues.append(
                    f"{label} {item_id} references unknown predecessor: {predecessor_ref}"
                )
                continue
            successors[predecessor_ref].append(item_id)
            indegree[item_id] += 1
    ready = [item_id for item_id, degree in indegree.items() if degree == 0]
    heapq.heapify(ready)
    ordered: list[str] = []
    while ready:
        item_id = heapq.heappop(ready)
        ordered.append(item_id)
        for successor in sorted(successors[item_id]):
            indegree[successor] -= 1
            if indegree[successor] == 0:
                heapq.heappush(ready, successor)
    if len(ordered) != len(ids):
        cyclic = sorted(item_id for item_id, degree in indegree.items() if degree > 0)
        issues.append(f"{label}s must form a DAG; cycle includes: {cyclic}")
        return tuple(sorted(ids))
    return tuple(ordered)


def _ancestor_map(
    order: tuple[str, ...], predecessors: dict[str, tuple[str, ...]]
) -> dict[str, set[str]]:
    ancestors: dict[str, set[str]] = {value: set() for value in order}
    for item_id in order:
        for predecessor_ref in predecessors.get(item_id, ()):
            if predecessor_ref not in ancestors:
                continue
            ancestors[item_id].add(predecessor_ref)
            ancestors[item_id].update(ancestors[predecessor_ref])
    return ancestors


def _scene_is_between(
    candidate_scene_ref: str,
    earlier_scene_ref: str,
    later_scene_ref: str,
    scene_ancestors: dict[str, set[str]],
) -> bool:
    after_earlier = (
        candidate_scene_ref == earlier_scene_ref
        or earlier_scene_ref in scene_ancestors.get(candidate_scene_ref, set())
    )
    by_later = (
        candidate_scene_ref == later_scene_ref
        or candidate_scene_ref in scene_ancestors.get(later_scene_ref, set())
    )
    return after_earlier and by_later


def _validate_objective_completion_scenes(
    objective: CampaignObjective,
    candidate_scene_refs: set[str],
    scene_by_id: dict[str, CampaignScene],
    excluded_scene_refs: set[str],
    target_label: str,
    issues: list[str],
) -> None:
    eligible_scene_refs = {
        scene_ref
        for scene_ref in objective.scene_refs
        if scene_by_id.get(scene_ref) is not None
        and scene_by_id[scene_ref].phase_ref == objective.phase_ref
    }
    if not candidate_scene_refs:
        issues.append(
            f"objective {objective.objective_id} {target_label} must resolve to a "
            "scene in its scene_refs and objective phase"
        )
        return

    outside_scene_refs = sorted(candidate_scene_refs - eligible_scene_refs)
    if outside_scene_refs:
        issues.append(
            f"objective {objective.objective_id} {target_label} must resolve only "
            "to scenes in its scene_refs and objective phase; outside scenes: "
            f"{outside_scene_refs}"
        )
    excluded_candidates = sorted(candidate_scene_refs & excluded_scene_refs)
    if excluded_candidates:
        issues.append(
            f"objective {objective.objective_id} {target_label} must not resolve "
            "to scenes owned by a mutually exclusive objective: "
            f"{excluded_candidates}"
        )


def _canonicalize_and_validate_campaign(
    scope: CampaignScope,
    start_location_ref: str,
    locations: tuple[CampaignLocation, ...],
    actors: tuple[CampaignActor, ...],
    scenes: tuple[CampaignScene, ...],
    objectives: tuple[CampaignObjective, ...],
    knowledge_beats: tuple[CampaignKnowledgeBeat, ...],
    knowledge_corrections: tuple[CampaignKnowledgeCorrection, ...],
    issues: list[str],
) -> tuple[
    tuple[CampaignScene, ...],
    tuple[CampaignObjective, ...],
    tuple[CampaignKnowledgeBeat, ...],
    tuple[CampaignKnowledgeCorrection, ...],
]:
    location_by_id = {value.location_id: value for value in locations}
    actor_by_id = {value.actor_id: value for value in actors}
    scene_by_id = {value.scene_id: value for value in scenes}
    objective_by_id = {value.objective_id: value for value in objectives}
    knowledge_by_id = {value.knowledge_id: value for value in knowledge_beats}
    correction_by_id = {
        value.correction_id: value for value in knowledge_corrections
    }

    if start_location_ref not in location_by_id:
        issues.append(
            f"start_location_ref references unknown location: {start_location_ref}"
        )
    for location in locations:
        for exit_value in location.exits:
            if exit_value.target_location_ref not in location_by_id:
                issues.append(
                    f"location {location.location_id} exit {exit_value.direction!r} "
                    f"references unknown target: {exit_value.target_location_ref}"
                )
    location_reachability: dict[str, set[str]] = {}
    for origin in sorted(location_by_id):
        reachable = {origin}
        pending = [origin]
        while pending:
            location_id = pending.pop()
            for exit_value in location_by_id[location_id].exits:
                target = exit_value.target_location_ref
                if target in location_by_id and target not in reachable:
                    reachable.add(target)
                    pending.append(target)
        location_reachability[origin] = reachable
    if start_location_ref in location_by_id:
        reachable = location_reachability[start_location_ref]
        unreachable = sorted(set(location_by_id) - reachable)
        if unreachable:
            issues.append(
                f"all locations must be reachable from {start_location_ref}: {unreachable}"
            )

    for actor in actors:
        if (
            actor.starting_location_ref is not None
            and actor.starting_location_ref not in location_by_id
        ):
            issues.append(
                f"actor {actor.actor_id} references unknown starting location: "
                f"{actor.starting_location_ref}"
            )
    players = [actor for actor in actors if actor.kind == "player"]
    if (
        len(players) == 1
        and players[0].starting_location_ref != start_location_ref
    ):
        issues.append(
            f"player actor {players[0].actor_id} starting_location_ref must equal "
            f"start_location_ref: {players[0].starting_location_ref!r} != "
            f"{start_location_ref!r}"
        )

    scene_predecessors = {
        value.scene_id: value.predecessor_scene_refs for value in scenes
    }
    scene_order = _topological_ids(
        set(scene_by_id), scene_predecessors, "scene", issues
    )
    scene_ancestors = _ancestor_map(scene_order, scene_predecessors)
    canonical_scenes = tuple(scene_by_id[value] for value in scene_order)
    scene_position = {scene_id: index for index, scene_id in enumerate(scene_order)}
    for scene in scenes:
        if scene.location_ref is not None and scene.location_ref not in location_by_id:
            issues.append(
                f"scene {scene.scene_id} references unknown location: {scene.location_ref}"
            )
        for actor_ref in scene.participating_actor_refs:
            if actor_ref not in actor_by_id:
                issues.append(
                    f"scene {scene.scene_id} references unknown actor: {actor_ref}"
                )
        if scene.location_ref is None:
            continue
        for predecessor_ref in sorted(scene_ancestors.get(scene.scene_id, set())):
            predecessor = scene_by_id.get(predecessor_ref)
            if predecessor is None or predecessor.location_ref is None:
                continue
            reachable = location_reachability.get(predecessor.location_ref, set())
            if scene.location_ref not in reachable:
                issues.append(
                    f"scene {scene.scene_id} location {scene.location_ref} is not "
                    f"reachable from predecessor scene {predecessor_ref} location "
                    f"{predecessor.location_ref}"
                )

    knowledge_ids = set(knowledge_by_id)
    correction_ids = set(correction_by_id)
    duplicate_knowledge_ids = sorted(knowledge_ids & correction_ids)
    if duplicate_knowledge_ids:
        issues.append(
            "knowledge beats and corrections share IDs: "
            f"{duplicate_knowledge_ids}"
        )
    for knowledge in knowledge_beats:
        scene = scene_by_id.get(knowledge.scene_ref)
        if scene is None:
            issues.append(
                f"knowledge beat {knowledge.knowledge_id} references unknown scene: "
                f"{knowledge.scene_ref}"
            )
        else:
            if knowledge.actor_ref not in scene.participating_actor_refs:
                issues.append(
                    f"knowledge beat {knowledge.knowledge_id} actor is not a participant "
                    f"in scene {knowledge.scene_ref}: {knowledge.actor_ref}"
                )
            if knowledge.source_beat_ref not in scene.narrative_beat_refs:
                issues.append(
                    f"knowledge beat {knowledge.knowledge_id} source beat is not bound "
                    f"by scene {knowledge.scene_ref}: {knowledge.source_beat_ref}"
                )
        if knowledge.actor_ref not in actor_by_id:
            issues.append(
                f"knowledge beat {knowledge.knowledge_id} references unknown actor: "
                f"{knowledge.actor_ref}"
            )

    for correction in knowledge_corrections:
        scene = scene_by_id.get(correction.scene_ref)
        if scene is None:
            issues.append(
                f"knowledge correction {correction.correction_id} references unknown "
                f"scene: {correction.scene_ref}"
            )
        else:
            if correction.actor_ref not in scene.participating_actor_refs:
                issues.append(
                    f"knowledge correction {correction.correction_id} actor is not a "
                    f"participant in scene {correction.scene_ref}: {correction.actor_ref}"
                )
        if correction.actor_ref not in actor_by_id:
            issues.append(
                f"knowledge correction {correction.correction_id} references unknown actor: "
                f"{correction.actor_ref}"
            )
        corrected = knowledge_by_id.get(correction.corrects_knowledge_ref)
        if corrected is None:
            issues.append(
                f"knowledge correction {correction.correction_id} references unknown "
                f"knowledge beat: {correction.corrects_knowledge_ref}"
            )
            continue
        if corrected.actor_ref != correction.actor_ref:
            issues.append(
                f"knowledge correction {correction.correction_id} actor does not match "
                f"the corrected knowledge beat"
            )
        if corrected.proposition_ref != correction.earlier_proposition_ref:
            issues.append(
                f"knowledge correction {correction.correction_id} earlier proposition "
                f"does not match {correction.corrects_knowledge_ref}"
            )
        if corrected.state not in {"heard", "suspected"}:
            issues.append(
                f"knowledge correction {correction.correction_id} must correct a heard "
                f"or suspected knowledge beat"
            )
        if corrected.scene_ref not in scene_ancestors.get(correction.scene_ref, set()):
            issues.append(
                f"knowledge correction {correction.correction_id} must occur after "
                f"{correction.corrects_knowledge_ref} through scene predecessor reachability"
            )

        retracts = [
            value
            for value in knowledge_beats
            if value.actor_ref == correction.actor_ref
            and value.perspective_ref == corrected.perspective_ref
            and value.proposition_ref == correction.earlier_proposition_ref
            and value.state == "retracted"
            and _scene_is_between(
                value.scene_ref,
                corrected.scene_ref,
                correction.scene_ref,
                scene_ancestors,
            )
        ]
        if not retracts:
            issues.append(
                f"knowledge correction {correction.correction_id} requires a reachable "
                "retracted projection for its earlier proposition"
            )
        confirmations = [
            value
            for value in knowledge_beats
            if value.actor_ref == correction.actor_ref
            and value.proposition_ref == correction.later_proposition_ref
            and value.state == "confirmed"
            and _scene_is_between(
                value.scene_ref,
                corrected.scene_ref,
                correction.scene_ref,
                scene_ancestors,
            )
        ]
        if not confirmations:
            issues.append(
                f"knowledge correction {correction.correction_id} requires a reachable "
                "confirmed projection for its later proposition"
            )

    objective_predecessors = {
        value.objective_id: value.predecessor_objective_refs for value in objectives
    }
    objective_order = _topological_ids(
        set(objective_by_id), objective_predecessors, "objective", issues
    )
    canonical_objectives = tuple(objective_by_id[value] for value in objective_order)
    all_knowledge_ids = knowledge_ids | correction_ids
    bound_scenes: set[str] = set()
    for objective in objectives:
        for scene_ref in objective.scene_refs:
            if scene_ref not in scene_by_id:
                issues.append(
                    f"objective {objective.objective_id} references unknown scene: {scene_ref}"
                )
            else:
                bound_scenes.add(scene_ref)
        for other_ref in objective.mutually_exclusive_objective_refs:
            if other_ref == objective.objective_id:
                issues.append(
                    f"objective {objective.objective_id} cannot exclude itself"
                )
                continue
            other = objective_by_id.get(other_ref)
            if other is None:
                issues.append(
                    f"objective {objective.objective_id} excludes unknown objective: "
                    f"{other_ref}"
                )
            elif objective.objective_id not in other.mutually_exclusive_objective_refs:
                issues.append(
                    f"objective mutual exclusion must be symmetric: "
                    f"{objective.objective_id} <-> {other_ref}"
                )
        excluded_scene_refs = {
            scene_ref
            for other_ref in objective.mutually_exclusive_objective_refs
            if (other := objective_by_id.get(other_ref)) is not None
            for scene_ref in other.scene_refs
        }
        completion = objective.completion
        if isinstance(completion, ReachLocationCompletion):
            if completion.location_ref not in location_by_id:
                issues.append(
                    f"objective {objective.objective_id} completion references unknown "
                    f"location: {completion.location_ref}"
                )
            else:
                _validate_objective_completion_scenes(
                    objective,
                    {
                        scene.scene_id
                        for scene in scenes
                        if scene.location_ref == completion.location_ref
                    },
                    scene_by_id,
                    excluded_scene_refs,
                    f"reach_location target {completion.location_ref}",
                    issues,
                )
        elif isinstance(completion, InteractActorCompletion):
            if completion.actor_ref not in actor_by_id:
                issues.append(
                    f"objective {objective.objective_id} completion references unknown "
                    f"actor: {completion.actor_ref}"
                )
            else:
                _validate_objective_completion_scenes(
                    objective,
                    {
                        scene.scene_id
                        for scene in scenes
                        if completion.actor_ref in scene.participating_actor_refs
                    },
                    scene_by_id,
                    excluded_scene_refs,
                    f"interact_actor target {completion.actor_ref}",
                    issues,
                )
        elif isinstance(completion, CompleteSceneCompletion):
            if completion.scene_ref not in scene_by_id:
                issues.append(
                    f"objective {objective.objective_id} completion references unknown "
                    f"scene: {completion.scene_ref}"
                )
            else:
                _validate_objective_completion_scenes(
                    objective,
                    {completion.scene_ref},
                    scene_by_id,
                    excluded_scene_refs,
                    f"complete_scene target {completion.scene_ref}",
                    issues,
                )
        elif isinstance(completion, ApplyKnowledgeCompletion):
            if completion.knowledge_ref not in all_knowledge_ids:
                issues.append(
                    f"objective {objective.objective_id} completion references unknown "
                    f"knowledge transition: {completion.knowledge_ref}"
                )
            else:
                knowledge = knowledge_by_id.get(completion.knowledge_ref)
                transition_scene_ref = (
                    knowledge.scene_ref
                    if knowledge is not None
                    else correction_by_id[completion.knowledge_ref].scene_ref
                )
                _validate_objective_completion_scenes(
                    objective,
                    {transition_scene_ref},
                    scene_by_id,
                    excluded_scene_refs,
                    f"apply_knowledge target {completion.knowledge_ref}",
                    issues,
                )
    unbound_scenes = sorted(set(scene_by_id) - bound_scenes)
    if unbound_scenes:
        issues.append(f"scenes are not bound to any objective: {unbound_scenes}")

    objective_ancestors = _ancestor_map(objective_order, objective_predecessors)
    for objective in objectives:
        ancestors = objective_ancestors.get(objective.objective_id, set())
        excluded_ancestors = sorted(
            ancestors & set(objective.mutually_exclusive_objective_refs)
        )
        if excluded_ancestors:
            issues.append(
                f"objective {objective.objective_id} depends on mutually exclusive "
                f"objectives: {excluded_ancestors}"
            )
        ordered_ancestors = sorted(ancestors)
        for index, first_ref in enumerate(ordered_ancestors):
            first = objective_by_id.get(first_ref)
            if first is None:
                continue
            excluded = set(first.mutually_exclusive_objective_refs)
            for second_ref in ordered_ancestors[index + 1 :]:
                if second_ref in excluded:
                    issues.append(
                        f"objective {objective.objective_id} requires mutually exclusive "
                        f"predecessor ancestry: {first_ref}, {second_ref}"
                    )

    bound_entities = {
        ref for location in locations for ref in location.source_entity_refs
    }
    bound_entities.update(
        actor.source_entity_ref
        for actor in actors
        if actor.source_entity_ref is not None
    )
    bound_perspectives = {value.perspective_ref for value in knowledge_beats}
    bound_propositions = {
        ref for location in locations for ref in location.source_proposition_refs
    }
    bound_propositions.update(
        ref for actor in actors for ref in actor.source_proposition_refs
    )
    bound_propositions.update(
        ref for scene in scenes for ref in scene.source_proposition_refs
    )
    bound_propositions.update(
        ref for objective in objectives for ref in objective.source_proposition_refs
    )
    bound_propositions.update(value.proposition_ref for value in knowledge_beats)
    bound_propositions.update(
        value.earlier_proposition_ref for value in knowledge_corrections
    )
    bound_propositions.update(
        value.later_proposition_ref for value in knowledge_corrections
    )
    bound_beats = {ref for scene in scenes for ref in scene.narrative_beat_refs}
    bound_beats.update(value.source_beat_ref for value in knowledge_beats)
    declared_and_bound = (
        ("entity", set(scope.entity_uses), bound_entities),
        ("perspective", set(scope.perspective_uses), bound_perspectives),
        ("proposition", set(scope.proposition_uses), bound_propositions),
        ("beat", set(scope.beat_uses), bound_beats),
    )
    for name, declared, bound in declared_and_bound:
        if declared != bound:
            issues.append(
                f"scope.{name}_uses must exactly equal campaign bindings: "
                f"declared={sorted(declared)}, bound={sorted(bound)}"
            )

    canonical_knowledge = tuple(
        sorted(
            knowledge_beats,
            key=lambda value: (
                scene_position.get(value.scene_ref, len(scene_position)),
                value.knowledge_id,
            ),
        )
    )
    canonical_corrections = tuple(
        sorted(
            knowledge_corrections,
            key=lambda value: (
                scene_position.get(value.scene_ref, len(scene_position)),
                value.correction_id,
            ),
        )
    )
    return (
        canonical_scenes,
        canonical_objectives,
        canonical_knowledge,
        canonical_corrections,
    )


def _parse_campaign_body(
    root: dict[str, Any], issues: list[str]
) -> tuple[
    str,
    str,
    CampaignScope,
    str,
    tuple[CampaignLocation, ...],
    tuple[CampaignActor, ...],
    tuple[CampaignScene, ...],
    tuple[CampaignObjective, ...],
    tuple[CampaignKnowledgeBeat, ...],
    tuple[CampaignKnowledgeCorrection, ...],
]:
    campaign_id = _required_stable_id(root, "campaign_id", "root", issues)
    adaptation_rationale = _required_text(
        root, "adaptation_rationale", "root", issues
    )
    scope = _parse_scope(root.get("scope"), "root.scope", issues)
    start_location_ref = _required_stable_id(
        root, "start_location_ref", "root", issues
    )
    locations = _parse_locations(root.get("locations"), "root.locations", issues)
    actors = _parse_actors(root.get("actors"), "root.actors", issues)
    scenes = _parse_scenes(root.get("scenes"), "root.scenes", issues)
    objectives = _parse_objectives(root.get("objectives"), "root.objectives", issues)
    knowledge_beats = _parse_knowledge_beats(
        root.get("knowledge_beats"), "root.knowledge_beats", issues
    )
    knowledge_corrections = _parse_knowledge_corrections(
        root.get("knowledge_corrections"), "root.knowledge_corrections", issues
    )
    scenes, objectives, knowledge_beats, knowledge_corrections = (
        _canonicalize_and_validate_campaign(
            scope,
            start_location_ref,
            locations,
            actors,
            scenes,
            objectives,
            knowledge_beats,
            knowledge_corrections,
            issues,
        )
    )
    return (
        campaign_id,
        adaptation_rationale,
        scope,
        start_location_ref,
        locations,
        actors,
        scenes,
        objectives,
        knowledge_beats,
        knowledge_corrections,
    )


_ROOT_FIELDS = frozenset(
    {
        "format_version",
        "campaign_id",
        "source_narrative_model",
        "adaptation_rationale",
        "scope",
        "start_location_ref",
        "locations",
        "actors",
        "scenes",
        "objectives",
        "knowledge_beats",
        "knowledge_corrections",
    }
)


def _validate_root(data: object) -> tuple[dict[str, Any], list[str]]:
    if not isinstance(data, dict):
        raise CampaignValidationError(("root must be a JSON object",))
    issues: list[str] = []
    _unknown_keys(data, _ROOT_FIELDS, "root", issues)
    version = data.get("format_version")
    if isinstance(version, bool) or not isinstance(version, int) or version != 1:
        issues.append("root.format_version must be 1")
    return data, issues


def validate_registry_campaign_plan_document(data: object) -> RegistryCampaignPlan:
    """Strictly validate and canonically order a RegistryCampaignPlan v1."""

    root, issues = _validate_root(data)
    source = _parse_source_narrative_ref(
        root.get("source_narrative_model"), "root.source_narrative_model", issues
    )
    body = _parse_campaign_body(root, issues)
    if issues:
        raise CampaignValidationError(tuple(issues))
    (
        campaign_id,
        adaptation_rationale,
        scope,
        start_location_ref,
        locations,
        actors,
        scenes,
        objectives,
        knowledge_beats,
        knowledge_corrections,
    ) = body
    return RegistryCampaignPlan(
        format_version=1,
        campaign_id=campaign_id,
        source_narrative_model=source,
        adaptation_rationale=adaptation_rationale,
        scope=scope,
        start_location_ref=start_location_ref,
        locations=locations,
        actors=actors,
        scenes=scenes,
        objectives=objectives,
        knowledge_beats=knowledge_beats,
        knowledge_corrections=knowledge_corrections,
    )


CampaignDocument: TypeAlias = RegistryCampaignPlan | CampaignSpec


def _validate_accounting_category(
    name: str,
    universe: set[str],
    used: tuple[str, ...],
    omissions: tuple[CampaignOmission, ...],
    issues: list[str],
) -> None:
    used_set = set(used)
    omitted_set = {value.source_ref for value in omissions}
    accounted = used_set | omitted_set
    missing = sorted(universe - accounted)
    foreign = sorted(accounted - universe)
    if missing:
        issues.append(f"scope does not use or omit NarrativeModel {name}s: {missing}")
    if foreign:
        issues.append(f"scope references foreign NarrativeModel {name}s: {foreign}")


def _validate_against_narrative_model(
    model: NarrativeModel, value: CampaignDocument, issues: list[str]
) -> None:
    entity_ids = set(model.scope.entity_refs)
    perspective_by_id = {
        perspective.perspective_id: perspective for perspective in model.perspectives
    }
    proposition_by_id = {
        proposition.proposition_id: proposition for proposition in model.propositions
    }
    phase_by_id = {phase.phase_id: phase for phase in model.phases}
    beat_by_id = {beat.beat_id: beat for beat in model.beats}
    _validate_accounting_category(
        "entity",
        entity_ids,
        value.scope.entity_uses,
        value.scope.entity_omissions,
        issues,
    )
    _validate_accounting_category(
        "perspective",
        set(perspective_by_id),
        value.scope.perspective_uses,
        value.scope.perspective_omissions,
        issues,
    )
    _validate_accounting_category(
        "proposition",
        set(proposition_by_id),
        value.scope.proposition_uses,
        value.scope.proposition_omissions,
        issues,
    )
    _validate_accounting_category(
        "beat",
        set(beat_by_id),
        value.scope.beat_uses,
        value.scope.beat_omissions,
        issues,
    )

    scene_by_id = {scene.scene_id: scene for scene in value.scenes}
    scene_predecessors = {
        scene.scene_id: scene.predecessor_scene_refs for scene in value.scenes
    }
    scene_order = tuple(scene.scene_id for scene in value.scenes)
    scene_ancestors = _ancestor_map(scene_order, scene_predecessors)
    for scene in value.scenes:
        phase = phase_by_id.get(scene.phase_ref)
        if phase is None:
            issues.append(
                f"scene {scene.scene_id} references unknown NarrativeModel phase: "
                f"{scene.phase_ref}"
            )
        for predecessor_ref in scene.predecessor_scene_refs:
            predecessor = scene_by_id.get(predecessor_ref)
            if predecessor is None:
                continue
            predecessor_phase = phase_by_id.get(predecessor.phase_ref)
            if (
                phase is not None
                and predecessor_phase is not None
                and predecessor_phase.sequence > phase.sequence
            ):
                issues.append(
                    f"scene {scene.scene_id} depends on later-phase scene "
                    f"{predecessor_ref}"
                )

    beat_owner: dict[str, str] = {}
    for scene in value.scenes:
        for beat_ref in scene.narrative_beat_refs:
            beat = beat_by_id.get(beat_ref)
            if beat is None:
                issues.append(
                    f"scene {scene.scene_id} references unknown NarrativeModel beat: "
                    f"{beat_ref}"
                )
                continue
            previous_owner = beat_owner.get(beat_ref)
            if previous_owner is not None and previous_owner != scene.scene_id:
                issues.append(
                    f"NarrativeModel beat {beat_ref} is bound by multiple scenes: "
                    f"{previous_owner}, {scene.scene_id}"
                )
            beat_owner[beat_ref] = scene.scene_id
            if beat.phase_ref != scene.phase_ref:
                issues.append(
                    f"scene {scene.scene_id} phase {scene.phase_ref} does not match "
                    f"NarrativeModel beat {beat_ref} phase {beat.phase_ref}"
                )

    source_predecessors = {
        beat.beat_id: beat.predecessor_refs for beat in model.beats
    }
    source_order = tuple(beat.beat_id for beat in model.beats)
    source_ancestors = _ancestor_map(source_order, source_predecessors)
    for later_beat_ref, earlier_beat_refs in source_ancestors.items():
        later_scene_ref = beat_owner.get(later_beat_ref)
        if later_scene_ref is None:
            continue
        for earlier_beat_ref in sorted(earlier_beat_refs):
            earlier_scene_ref = beat_owner.get(earlier_beat_ref)
            if earlier_scene_ref is None:
                continue
            if earlier_scene_ref not in scene_ancestors.get(later_scene_ref, set()):
                issues.append(
                    f"scene mapping contradicts NarrativeModel beat reachability: "
                    f"{earlier_beat_ref}/{earlier_scene_ref} must precede "
                    f"{later_beat_ref}/{later_scene_ref}"
                )

    objective_by_id = {
        objective.objective_id: objective for objective in value.objectives
    }
    for objective in value.objectives:
        phase = phase_by_id.get(objective.phase_ref)
        if phase is None:
            issues.append(
                f"objective {objective.objective_id} references unknown NarrativeModel "
                f"phase: {objective.phase_ref}"
            )
        for predecessor_ref in objective.predecessor_objective_refs:
            predecessor = objective_by_id.get(predecessor_ref)
            if predecessor is None:
                continue
            predecessor_phase = phase_by_id.get(predecessor.phase_ref)
            if (
                phase is not None
                and predecessor_phase is not None
                and predecessor_phase.sequence > phase.sequence
            ):
                issues.append(
                    f"objective {objective.objective_id} depends on later-phase objective "
                    f"{predecessor_ref}"
                )
        if phase is not None:
            for scene_ref in objective.scene_refs:
                scene = scene_by_id.get(scene_ref)
                if scene is None:
                    continue
                scene_phase = phase_by_id.get(scene.phase_ref)
                if scene_phase is not None and scene_phase.sequence > phase.sequence:
                    issues.append(
                        f"objective {objective.objective_id} cannot bind later-phase scene "
                        f"{scene_ref}"
                    )

    groups: dict[
        tuple[str, str, str], list[CampaignKnowledgeBeat]
    ] = defaultdict(list)
    for knowledge in value.knowledge_beats:
        beat = beat_by_id.get(knowledge.source_beat_ref)
        if beat is None:
            continue
        expected = {
            (
                disclosure.perspective_ref,
                disclosure.proposition_ref,
                disclosure.state,
            )
            for disclosure in beat.disclosures
        }
        projection = (
            knowledge.perspective_ref,
            knowledge.proposition_ref,
            knowledge.state,
        )
        if projection not in expected:
            issues.append(
                f"knowledge beat {knowledge.knowledge_id} does not exactly project a "
                f"disclosure from NarrativeModel beat {knowledge.source_beat_ref}: "
                f"{projection!r}"
            )
        groups[
            (knowledge.actor_ref, knowledge.perspective_ref, knowledge.proposition_ref)
        ].append(knowledge)

    allowed_transitions: dict[str, frozenset[str]] = {
        "heard": frozenset({"heard", "suspected", "confirmed", "retracted"}),
        "suspected": frozenset({"suspected", "confirmed", "retracted"}),
        "confirmed": frozenset({"confirmed", "retracted"}),
        "retracted": frozenset({"retracted"}),
    }
    for group_key, group in sorted(groups.items()):
        for index, first in enumerate(group):
            for second in group[index + 1 :]:
                first_before_second = first.source_beat_ref in source_ancestors.get(
                    second.source_beat_ref, set()
                )
                second_before_first = second.source_beat_ref in source_ancestors.get(
                    first.source_beat_ref, set()
                )
                if not first_before_second and not second_before_first:
                    issues.append(
                        f"knowledge track {group_key!r} has unordered source updates: "
                        f"{first.knowledge_id}, {second.knowledge_id}"
                    )
                    continue
                earlier, later = (
                    (first, second)
                    if first_before_second
                    else (second, first)
                )
                if earlier.scene_ref not in scene_ancestors.get(later.scene_ref, set()):
                    issues.append(
                        f"knowledge track {group_key!r} has source-ordered but "
                        f"scene-unordered updates: {earlier.knowledge_id}, "
                        f"{later.knowledge_id}"
                    )
                if later.state not in allowed_transitions[earlier.state]:
                    issues.append(
                        f"impossible source disclosure transition for {group_key!r}: "
                        f"{earlier.knowledge_id}={earlier.state} -> "
                        f"{later.knowledge_id}={later.state}"
                    )
        for later in group:
            earlier_events = [
                earlier
                for earlier in group
                if earlier.source_beat_ref
                in source_ancestors.get(later.source_beat_ref, set())
            ]
            if later.state == "retracted" and not any(
                earlier.state != "retracted" for earlier in earlier_events
            ):
                issues.append(
                    f"knowledge beat {later.knowledge_id} retracts without a reachable "
                    f"earlier belief for {group_key!r}"
                )


def validate_campaign_spec_document(data: object) -> CampaignSpec:
    """Strictly validate a standalone, self-contained CampaignSpec v1."""

    root, issues = _validate_root(data)
    source_model: NarrativeModel | None = None
    try:
        source_model = validate_narrative_model_document(
            root.get("source_narrative_model")
        )
    except NarrativeModelValidationError as exc:
        issues.extend(
            f"source_narrative_model: {issue}" for issue in exc.issues
        )
    body = _parse_campaign_body(root, issues)
    if source_model is not None:
        provisional = CampaignSpec(
            format_version=1,
            campaign_id=body[0],
            source_narrative_model=source_model,
            adaptation_rationale=body[1],
            scope=body[2],
            start_location_ref=body[3],
            locations=body[4],
            actors=body[5],
            scenes=body[6],
            objectives=body[7],
            knowledge_beats=body[8],
            knowledge_corrections=body[9],
        )
        _validate_against_narrative_model(source_model, provisional, issues)
    if issues:
        raise CampaignValidationError(tuple(issues))
    assert source_model is not None
    return CampaignSpec(
        format_version=1,
        campaign_id=body[0],
        source_narrative_model=source_model,
        adaptation_rationale=body[1],
        scope=body[2],
        start_location_ref=body[3],
        locations=body[4],
        actors=body[5],
        scenes=body[6],
        objectives=body[7],
        knowledge_beats=body[8],
        knowledge_corrections=body[9],
    )


def _omissions_document(
    values: tuple[CampaignOmission, ...], ref_field: str
) -> list[dict[str, str]]:
    return [
        {ref_field: value.source_ref, "reason": value.reason} for value in values
    ]


def _scope_document(scope: CampaignScope) -> dict[str, Any]:
    return {
        "entity_uses": list(scope.entity_uses),
        "entity_omissions": _omissions_document(
            scope.entity_omissions, "entity_ref"
        ),
        "perspective_uses": list(scope.perspective_uses),
        "perspective_omissions": _omissions_document(
            scope.perspective_omissions, "perspective_ref"
        ),
        "proposition_uses": list(scope.proposition_uses),
        "proposition_omissions": _omissions_document(
            scope.proposition_omissions, "proposition_ref"
        ),
        "beat_uses": list(scope.beat_uses),
        "beat_omissions": _omissions_document(scope.beat_omissions, "beat_ref"),
    }


def _completion_document(value: ObjectiveCompletion) -> dict[str, str]:
    if isinstance(value, ReachLocationCompletion):
        return {"kind": value.kind, "location_ref": value.location_ref}
    if isinstance(value, InteractActorCompletion):
        return {"kind": value.kind, "actor_ref": value.actor_ref}
    if isinstance(value, CompleteSceneCompletion):
        return {"kind": value.kind, "scene_ref": value.scene_ref}
    if isinstance(value, ApplyKnowledgeCompletion):
        return {"kind": value.kind, "knowledge_ref": value.knowledge_ref}
    raise TypeError(f"unsupported objective completion: {type(value).__name__}")


def _campaign_body_to_document(value: CampaignDocument) -> dict[str, Any]:
    return {
        "format_version": value.format_version,
        "campaign_id": value.campaign_id,
        "adaptation_rationale": value.adaptation_rationale,
        "scope": _scope_document(value.scope),
        "start_location_ref": value.start_location_ref,
        "locations": [
            {
                "location_id": location.location_id,
                "name": location.name,
                "description": location.description,
                "source_entity_refs": list(location.source_entity_refs),
                "source_proposition_refs": list(location.source_proposition_refs),
                "adaptation_notes": location.adaptation_notes,
                "exits": [
                    {
                        "direction": exit_value.direction,
                        "name": exit_value.name,
                        "target_location_ref": exit_value.target_location_ref,
                    }
                    for exit_value in location.exits
                ],
            }
            for location in value.locations
        ],
        "actors": [
            {
                "actor_id": actor.actor_id,
                "kind": actor.kind,
                "name": actor.name,
                "description": actor.description,
                "source_entity_ref": actor.source_entity_ref,
                "starting_location_ref": actor.starting_location_ref,
                "source_proposition_refs": list(actor.source_proposition_refs),
                "adaptation_notes": actor.adaptation_notes,
            }
            for actor in value.actors
        ],
        "scenes": [
            {
                "scene_id": scene.scene_id,
                "kind": scene.kind,
                "phase_ref": scene.phase_ref,
                "location_ref": scene.location_ref,
                "participating_actor_refs": list(scene.participating_actor_refs),
                "narrative_beat_refs": list(scene.narrative_beat_refs),
                "predecessor_scene_refs": list(scene.predecessor_scene_refs),
                "source_proposition_refs": list(scene.source_proposition_refs),
                "adaptation_notes": scene.adaptation_notes,
            }
            for scene in value.scenes
        ],
        "objectives": [
            {
                "objective_id": objective.objective_id,
                "title": objective.title,
                "description": objective.description,
                "phase_ref": objective.phase_ref,
                "scene_refs": list(objective.scene_refs),
                "predecessor_objective_refs": list(
                    objective.predecessor_objective_refs
                ),
                "mutually_exclusive_objective_refs": list(
                    objective.mutually_exclusive_objective_refs
                ),
                "source_proposition_refs": list(
                    objective.source_proposition_refs
                ),
                "completion": _completion_document(objective.completion),
                "adaptation_notes": objective.adaptation_notes,
            }
            for objective in value.objectives
        ],
        "knowledge_beats": [
            {
                "knowledge_id": knowledge.knowledge_id,
                "scene_ref": knowledge.scene_ref,
                "actor_ref": knowledge.actor_ref,
                "source_beat_ref": knowledge.source_beat_ref,
                "perspective_ref": knowledge.perspective_ref,
                "proposition_ref": knowledge.proposition_ref,
                "state": knowledge.state,
                "adaptation_notes": knowledge.adaptation_notes,
            }
            for knowledge in value.knowledge_beats
        ],
        "knowledge_corrections": [
            {
                "correction_id": correction.correction_id,
                "scene_ref": correction.scene_ref,
                "actor_ref": correction.actor_ref,
                "state": correction.state,
                "corrects_knowledge_ref": correction.corrects_knowledge_ref,
                "earlier_proposition_ref": correction.earlier_proposition_ref,
                "later_proposition_ref": correction.later_proposition_ref,
                "rationale": correction.rationale,
            }
            for correction in value.knowledge_corrections
        ],
    }


def registry_campaign_plan_to_document(
    plan: RegistryCampaignPlan,
) -> dict[str, Any]:
    """Serialize a validated campaign plan in canonical order."""

    if not isinstance(plan, RegistryCampaignPlan):
        raise TypeError("plan must be RegistryCampaignPlan")
    document = _campaign_body_to_document(plan)
    document["source_narrative_model"] = {
        "format_version": plan.source_narrative_model.format_version,
        "model_id": plan.source_narrative_model.model_id,
        "narrative_model_sha256": (
            plan.source_narrative_model.narrative_model_sha256
        ),
    }
    return document


def campaign_spec_to_document(spec: CampaignSpec) -> dict[str, Any]:
    """Serialize a validated CampaignSpec with its exact source snapshot."""

    if not isinstance(spec, CampaignSpec):
        raise TypeError("spec must be CampaignSpec")
    document = _campaign_body_to_document(spec)
    document["source_narrative_model"] = narrative_model_to_document(
        spec.source_narrative_model
    )
    return document


def _canonical_json_bytes(document: object) -> bytes:
    return (
        json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def narrative_model_sha256(model: NarrativeModel) -> str:
    """Return the SHA-256 of canonical NarrativeModel v1 JSON bytes."""

    if not isinstance(model, NarrativeModel):
        raise TypeError("model must be NarrativeModel")
    return hashlib.sha256(
        _canonical_json_bytes(narrative_model_to_document(model))
    ).hexdigest()


def compile_campaign_spec(
    model: NarrativeModel, plan: RegistryCampaignPlan
) -> CampaignSpec:
    """Bind an explicit campaign plan to an exact NarrativeModel snapshot."""

    if not isinstance(model, NarrativeModel):
        raise CampaignBuildError(("model must be NarrativeModel",))
    if not isinstance(plan, RegistryCampaignPlan):
        raise CampaignBuildError(("plan must be RegistryCampaignPlan",))

    issues: list[str] = []
    try:
        normalized_model = validate_narrative_model_document(
            narrative_model_to_document(model)
        )
    except (AttributeError, TypeError) as exc:
        raise CampaignBuildError((f"invalid typed NarrativeModel: {exc}",)) from exc
    except NarrativeModelValidationError as exc:
        raise CampaignBuildError(
            tuple(f"invalid NarrativeModel: {issue}" for issue in exc.issues)
        ) from exc
    if normalized_model != model:
        issues.append("model must already use canonical validated ordering")
    try:
        normalized_plan = validate_registry_campaign_plan_document(
            registry_campaign_plan_to_document(plan)
        )
    except (AttributeError, TypeError) as exc:
        raise CampaignBuildError((f"invalid typed campaign plan: {exc}",)) from exc
    except CampaignValidationError as exc:
        raise CampaignBuildError(
            tuple(f"invalid campaign plan: {issue}" for issue in exc.issues)
        ) from exc
    if normalized_plan != plan:
        issues.append("plan must already use canonical validated ordering")

    if plan.source_narrative_model.format_version != model.format_version:
        issues.append(
            "plan source_narrative_model.format_version does not match the "
            f"NarrativeModel: {plan.source_narrative_model.format_version} != "
            f"{model.format_version}"
        )
    if plan.source_narrative_model.model_id != model.model_id:
        issues.append(
            "plan source_narrative_model.model_id does not match the NarrativeModel: "
            f"{plan.source_narrative_model.model_id!r} != {model.model_id!r}"
        )
    actual_sha256 = narrative_model_sha256(model)
    if plan.source_narrative_model.narrative_model_sha256 != actual_sha256:
        issues.append(
            "plan source_narrative_model.narrative_model_sha256 does not match "
            f"canonical NarrativeModel bytes: "
            f"{plan.source_narrative_model.narrative_model_sha256!r} != "
            f"{actual_sha256!r}"
        )
    _validate_against_narrative_model(model, plan, issues)
    if issues:
        raise CampaignBuildError(tuple(issues))

    spec = CampaignSpec(
        format_version=1,
        campaign_id=plan.campaign_id,
        source_narrative_model=model,
        adaptation_rationale=plan.adaptation_rationale,
        scope=plan.scope,
        start_location_ref=plan.start_location_ref,
        locations=plan.locations,
        actors=plan.actors,
        scenes=plan.scenes,
        objectives=plan.objectives,
        knowledge_beats=plan.knowledge_beats,
        knowledge_corrections=plan.knowledge_corrections,
    )
    try:
        revalidated = validate_campaign_spec_document(
            campaign_spec_to_document(spec)
        )
    except CampaignValidationError as exc:
        raise CampaignBuildError(
            tuple(f"generated CampaignSpec is invalid: {issue}" for issue in exc.issues)
        ) from exc
    if revalidated != spec:
        raise CampaignBuildError(
            ("generated CampaignSpec changed during canonical revalidation",)
        )
    return spec


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
        return (
            os.path.exists(first_real)
            and os.path.exists(second_real)
            and os.path.samefile(first_real, second_real)
        )
    except OSError:
        return False


def write_campaign_spec(
    spec: CampaignSpec, output_path: str | os.PathLike[str]
) -> Path:
    """Atomically publish a validated spec and preserve old output on failure."""

    try:
        document = campaign_spec_to_document(spec)
    except (AttributeError, TypeError) as exc:
        raise CampaignValidationError((f"invalid typed CampaignSpec: {exc}",)) from exc
    revalidated = validate_campaign_spec_document(document)
    if revalidated != spec:
        raise CampaignValidationError(
            ("CampaignSpec changed during canonical revalidation",)
        )

    output = Path(output_path)
    if _is_link_like(output):
        raise OSError(f"output path must not be a symbolic link or reparse point: {output}")
    parent = Path(os.path.abspath(output)).parent
    if not parent.is_dir():
        raise FileNotFoundError(f"output parent does not exist: {parent}")
    payload = _canonical_json_bytes(document)

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
    """CLI entry point for deterministic campaign-spec compilation."""

    parser = argparse.ArgumentParser(
        description="Compile a deterministic CampaignSpec v1 from a NarrativeModel."
    )
    parser.add_argument(
        "--narrative-model", required=True, help="NarrativeModel v1 JSON input path"
    )
    parser.add_argument(
        "--campaign-plan", required=True, help="RegistryCampaignPlan v1 JSON input path"
    )
    parser.add_argument(
        "--output", required=True, help="CampaignSpec v1 JSON output path"
    )
    args = parser.parse_args(argv)

    inputs = [args.narrative_model, args.campaign_plan]
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
        with open(args.narrative_model, "r", encoding="utf-8") as handle:
            model = validate_narrative_model_document(json.load(handle))
        with open(args.campaign_plan, "r", encoding="utf-8") as handle:
            plan = validate_registry_campaign_plan_document(json.load(handle))
        spec = compile_campaign_spec(model, plan)
        write_campaign_spec(spec, args.output)
    except json.JSONDecodeError as exc:
        print(f"JSON parse error: {exc}", file=sys.stderr)
        return 1
    except UnicodeDecodeError as exc:
        print(f"UTF-8 decode error: {exc}", file=sys.stderr)
        return 1
    except NarrativeModelValidationError as exc:
        print(f"NarrativeModel error: {exc}", file=sys.stderr)
        return 1
    except CampaignValidationError as exc:
        print(f"Campaign validation error: {exc}", file=sys.stderr)
        return 1
    except CampaignBuildError as exc:
        print(f"Campaign build error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"I/O error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
