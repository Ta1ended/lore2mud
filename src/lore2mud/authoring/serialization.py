"""Canonical JSON and typed document conversion for V2-2 authoring."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
import hashlib
import json
import math
from typing import Any, cast

from lore2mud._bounded_json import (
    BoundedJsonError,
    DEFAULT_JSON_READ_LIMITS,
    JsonReadErrorCode,
    parse_bounded_json,
)
from lore2mud.application.contracts import (
    AttackIntent,
    BuyIntent,
    CampaignActionIntent,
    ChooseDialogueIntent,
    DropIntent,
    EndDialogueIntent,
    EquipIntent,
    EquipmentSlot,
    ExamineIntent,
    ExamineTargetKind,
    GameIntent,
    LoadIntent,
    MoveIntent,
    RecoverIntent,
    SaveIntent,
    SellIntent,
    TakeIntent,
    TalkIntent,
    UnequipIntent,
    UseIntent,
    ViewIntent,
    ViewKind,
)
from lore2mud.application.session import validate_game_intent
from lore2mud.authoring.contracts import (
    AcceptanceScenario,
    AdmissibleIntentDescriptor,
    AuthoringDiagnostic,
    AuthoringResult,
    CapabilityAuthoringResult,
    CapabilityPreview,
    CapabilityProofingProjection,
    CapabilitySimulationCheckpoint,
    CapabilitySimulationReport,
    CapabilitySimulationRequest,
    CapabilitySimulationTurn,
    CanonicalContentFile,
    GameBlueprint,
    GameProject,
    PreviewBuild,
    ProofingProjection,
    SimulationCheckpoint,
    SimulationCondition,
    SimulationReport,
    SimulationRequest,
    SimulationTurn,
)


class InvalidUnicodeScalarError(ValueError):
    """Raised when an authoring value contains a lone UTF-16 surrogate."""


class AuthoringDocumentTraversalError(ValueError):
    """Raised when an in-memory authoring document cannot be traversed safely."""

    def __init__(self, reason: str, message: str) -> None:
        self.reason = reason
        super().__init__(message)


def validate_unicode_scalars(
    document: object, *, enforce_string_limit: bool = True
) -> None:
    """Reject unsafe strings and unbounded or cyclic in-memory containers."""
    limits = DEFAULT_JSON_READ_LIMITS
    stack: list[tuple[object, int, bool]] = [(document, 0, False)]
    active_containers: set[int] = set()
    nodes = 0
    oversized_text = False
    while stack:
        current, depth, leaving = stack.pop()
        if leaving:
            active_containers.remove(id(current))
            continue

        nodes += 1
        if nodes > limits.max_nodes or depth > limits.max_depth:
            raise AuthoringDocumentTraversalError(
                "complexity",
                "authoring document exceeds traversal limits"
            )
        if type(current) is str:
            if len(current) > limits.max_string_chars:
                oversized_text = True
            if any(0xD800 <= ord(character) <= 0xDFFF for character in current):
                raise InvalidUnicodeScalarError(
                    "authoring text contains an invalid Unicode surrogate"
                )
            continue

        current_type = type(current)
        if current_type not in {list, tuple, dict}:
            continue

        identity = id(current)
        if identity in active_containers:
            raise AuthoringDocumentTraversalError(
                "cycle",
                "authoring document contains a container cycle"
            )
        active_containers.add(identity)
        stack.append((current, depth, True))

        if current_type is dict:
            mapping = cast(dict[object, object], current)
            child_count = len(mapping) * 2
        elif current_type is list:
            values = cast(list[object], current)
            child_count = len(values)
        else:
            values = cast(tuple[object, ...], current)
            child_count = len(values)

        if child_count > limits.max_nodes - nodes:
            raise AuthoringDocumentTraversalError(
                "complexity",
                "authoring document exceeds traversal limits"
            )
        if current_type is dict:
            stack.extend((child, depth + 1, False) for child in mapping.keys())
            stack.extend((child, depth + 1, False) for child in mapping.values())
        else:
            stack.extend((child, depth + 1, False) for child in values)

    if oversized_text and enforce_string_limit:
        raise AuthoringDocumentTraversalError(
            "text",
            "authoring text exceeds traversal limits",
        )


def normalize_bounded_json_document(document: object) -> object:
    """Round-trip an in-memory document through the shared bounded JSON rules."""
    validate_unicode_scalars(document, enforce_string_limit=False)
    encoder = json.JSONEncoder(
        ensure_ascii=False,
        sort_keys=True,
        indent=2,
        allow_nan=False,
    )
    payload = bytearray()
    try:
        for chunk in encoder.iterencode(document):
            encoded = chunk.encode("utf-8")
            if (
                len(payload) + len(encoded) + 1
                > DEFAULT_JSON_READ_LIMITS.max_bytes
            ):
                raise BoundedJsonError(JsonReadErrorCode.TOO_LARGE)
            payload.extend(encoded)
    except UnicodeEncodeError:
        raise InvalidUnicodeScalarError(
            "authoring text contains an invalid Unicode surrogate"
        ) from None
    except BoundedJsonError:
        raise
    except (RecursionError, TypeError, ValueError):
        raise BoundedJsonError(JsonReadErrorCode.INVALID_JSON) from None
    payload.extend(b"\n")
    return parse_bounded_json(bytes(payload), DEFAULT_JSON_READ_LIMITS)


def canonical_json_bytes(document: object) -> bytes:
    """Return the one canonical human-readable JSON encoding used by V2-2."""
    validate_unicode_scalars(document)
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


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def fingerprint_document(document: object) -> str:
    return sha256_bytes(canonical_json_bytes(document))


def parse_canonical_json(payload: bytes) -> object:
    return json.loads(payload.decode("utf-8"))


def sort_diagnostics(
    diagnostics: tuple[AuthoringDiagnostic, ...] | list[AuthoringDiagnostic],
) -> tuple[AuthoringDiagnostic, ...]:
    return tuple(
        sorted(
            diagnostics,
            key=lambda value: (
                value.stage.value,
                value.artifact_id,
                value.json_pointer,
                value.code,
                value.severity.value,
            ),
        )
    )


def game_intent_to_document(intent: GameIntent) -> dict[str, object]:
    validate_game_intent(intent)
    if isinstance(intent, ViewIntent):
        return {"type": "view", "kind": intent.kind.value}
    if isinstance(intent, ExamineIntent):
        return {
            "type": "examine",
            "target": intent.target,
            "target_kind": (
                None if intent.target_kind is None else intent.target_kind.value
            ),
        }
    if isinstance(intent, MoveIntent):
        return {"type": "move", "direction": intent.direction}
    if isinstance(intent, TakeIntent):
        return {"type": "take", "target": intent.target, "quantity": intent.quantity}
    if isinstance(intent, DropIntent):
        return {"type": "drop", "target": intent.target, "quantity": intent.quantity}
    if isinstance(intent, UseIntent):
        return {"type": "use", "target": intent.target, "quantity": intent.quantity}
    if isinstance(intent, EquipIntent):
        return {"type": "equip", "target": intent.target}
    if isinstance(intent, UnequipIntent):
        return {"type": "unequip", "slot": intent.slot.value}
    if isinstance(intent, AttackIntent):
        return {"type": "attack", "target": intent.target}
    if isinstance(intent, TalkIntent):
        return {"type": "talk", "target": intent.target}
    if isinstance(intent, ChooseDialogueIntent):
        return {"type": "choose_dialogue", "index": intent.index}
    if isinstance(intent, EndDialogueIntent):
        return {"type": "end_dialogue"}
    if isinstance(intent, BuyIntent):
        return {"type": "buy", "target": intent.target, "quantity": intent.quantity}
    if isinstance(intent, SellIntent):
        return {"type": "sell", "target": intent.target, "quantity": intent.quantity}
    if isinstance(intent, CampaignActionIntent):
        return {"type": "campaign_action", "action_id": intent.action_id}
    if isinstance(intent, RecoverIntent):
        return {"type": "recover"}
    if isinstance(intent, SaveIntent):
        return {"type": "save", "slot": intent.slot}
    if isinstance(intent, LoadIntent):
        return {"type": "load", "slot": intent.slot}
    raise TypeError(f"unsupported GameIntent: {type(intent).__name__}")


def game_intent_from_document(document: object) -> GameIntent:
    data = _object(document, "intent")
    intent_type = _text(data.get("type"), "intent.type")
    constructors: dict[str, tuple[set[str], Any]] = {
        "view": ({"type", "kind"}, lambda: ViewIntent(ViewKind(_text(data["kind"], "intent.kind")))),
        "examine": (
            {"type", "target", "target_kind"},
            lambda: ExamineIntent(
                _text(data["target"], "intent.target", maximum=200),
                None
                if data["target_kind"] is None
                else ExamineTargetKind(_text(data["target_kind"], "intent.target_kind")),
            ),
        ),
        "move": (
            {"type", "direction"},
            lambda: MoveIntent(_text(data["direction"], "intent.direction", maximum=32)),
        ),
        "take": (
            {"type", "target", "quantity"},
            lambda: TakeIntent(
                _text(data["target"], "intent.target", maximum=200),
                _integer(data["quantity"], "intent.quantity"),
            ),
        ),
        "drop": (
            {"type", "target", "quantity"},
            lambda: DropIntent(
                _text(data["target"], "intent.target", maximum=200),
                _integer(data["quantity"], "intent.quantity"),
            ),
        ),
        "use": (
            {"type", "target", "quantity"},
            lambda: UseIntent(
                _text(data["target"], "intent.target", maximum=200),
                _integer(data["quantity"], "intent.quantity"),
            ),
        ),
        "equip": (
            {"type", "target"},
            lambda: EquipIntent(_text(data["target"], "intent.target", maximum=200)),
        ),
        "unequip": ({"type", "slot"}, lambda: UnequipIntent(EquipmentSlot(_text(data["slot"], "intent.slot")))),
        "attack": (
            {"type", "target"},
            lambda: AttackIntent(_text(data["target"], "intent.target", maximum=200)),
        ),
        "talk": (
            {"type", "target"},
            lambda: TalkIntent(_text(data["target"], "intent.target", maximum=200)),
        ),
        "choose_dialogue": ({"type", "index"}, lambda: ChooseDialogueIntent(_integer(data["index"], "intent.index"))),
        "end_dialogue": ({"type"}, EndDialogueIntent),
        "buy": (
            {"type", "target", "quantity"},
            lambda: BuyIntent(
                _text(data["target"], "intent.target", maximum=200),
                _integer(data["quantity"], "intent.quantity"),
            ),
        ),
        "sell": (
            {"type", "target", "quantity"},
            lambda: SellIntent(
                _text(data["target"], "intent.target", maximum=200),
                _integer(data["quantity"], "intent.quantity"),
            ),
        ),
        "campaign_action": ({"type", "action_id"}, lambda: CampaignActionIntent(_text(data["action_id"], "intent.action_id"))),
        "recover": ({"type"}, RecoverIntent),
        "save": (
            {"type", "slot"},
            lambda: SaveIntent(_optional_text(data["slot"], "intent.slot", maximum=32)),
        ),
        "load": (
            {"type", "slot"},
            lambda: LoadIntent(_optional_text(data["slot"], "intent.slot", maximum=32)),
        ),
    }
    selected = constructors.get(intent_type)
    if selected is None:
        raise ValueError(f"intent.type is unsupported: {intent_type}")
    expected, constructor = selected
    _exact_keys(data, expected, "intent")
    try:
        intent = constructor()
        validate_game_intent(intent)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid {intent_type} intent") from exc
    return intent


def blueprint_to_document(blueprint: GameBlueprint) -> dict[str, object]:
    return {
        "format_version": blueprint.format_version,
        "blueprint_id": blueprint.blueprint_id,
        "title": blueprint.title,
        "approval": {
            "approved": blueprint.approval.approved,
            "decision_id": blueprint.approval.decision_id,
            "approver": blueprint.approval.approver,
        },
        "audience": blueprint.audience,
        "genre": blueprint.genre,
        "tone": blueprint.tone,
        "play_length": {
            "minimum_minutes": blueprint.play_length.minimum_minutes,
            "target_minutes": blueprint.play_length.target_minutes,
            "maximum_minutes": blueprint.play_length.maximum_minutes,
        },
        "adaptation_boundaries": {
            "allowed": list(blueprint.adaptation_boundaries.allowed),
            "excluded": list(blueprint.adaptation_boundaries.excluded),
        },
        "required_game_loops": list(blueprint.required_game_loops),
        "acceptance_scenarios": [
            _acceptance_scenario_to_document(value)
            for value in blueprint.acceptance_scenarios
        ],
        "capability_requirement_ids": list(blueprint.capability_requirement_ids),
        "asset_requirements": list(blueprint.asset_requirements),
        "provenance_requirements": list(blueprint.provenance_requirements),
        "rights_assertions": list(blueprint.rights_assertions),
        "default_determinism": {
            "seed": blueprint.default_determinism.seed,
            "clock": blueprint.default_determinism.clock,
        },
    }


def blueprint_bytes(blueprint: GameBlueprint) -> bytes:
    return canonical_json_bytes(blueprint_to_document(blueprint))


def canonical_content_file_to_document(value: CanonicalContentFile) -> dict[str, object]:
    return {
        "name": value.name,
        "sha256": value.sha256,
        "document": parse_bounded_json(
            value.canonical_json, DEFAULT_JSON_READ_LIMITS
        ),
    }


def project_core_to_document(project: GameProject) -> dict[str, object]:
    return {
        "format_version": project.format_version,
        "project_id": project.project_id,
        "blueprint": blueprint_to_document(project.blueprint),
        "blueprint_sha256": project.blueprint_sha256,
        "public_inputs": [
            {
                "artifact_id": value.artifact_id,
                "media_type": value.media_type,
                "label": value.label,
                "visibility": value.visibility,
            }
            for value in project.public_inputs
        ],
        "content_files": [
            canonical_content_file_to_document(value) for value in project.content_files
        ],
        "creator_decisions": [
            {"decision_id": value.decision_id, "statement": value.statement}
            for value in project.creator_decisions
        ],
        "trace_records": [
            {
                "trace_id": value.trace_id,
                "source_artifact_id": value.source_artifact_id,
                "target_artifact_id": value.target_artifact_id,
                "decision_id": value.decision_id,
            }
            for value in project.trace_records
        ],
    }


def project_semantic_to_document(project: GameProject) -> dict[str, object]:
    return {
        **project_core_to_document(project),
        "build_lock": {"input_sha256": project.build_lock.input_sha256},
    }


def project_to_document(project: GameProject) -> dict[str, object]:
    return {
        **project_semantic_to_document(project),
        "workspace_metadata": [
            {"key": value.key, "value": value.value}
            for value in project.workspace_metadata
        ],
    }


def project_semantic_bytes(project: GameProject) -> bytes:
    return canonical_json_bytes(project_semantic_to_document(project))


def project_bytes(project: GameProject) -> bytes:
    return canonical_json_bytes(project_to_document(project))


def diagnostic_to_document(value: AuthoringDiagnostic) -> dict[str, object]:
    span: object = None
    if value.source_span is not None:
        span = {
            "source_artifact_id": value.source_span.source_artifact_id,
            "start_line": value.source_span.start_line,
            "start_column": value.source_span.start_column,
            "end_line": value.source_span.end_line,
            "end_column": value.source_span.end_column,
        }
    return {
        "format_version": 1,
        "stage": value.stage.value,
        "code": value.code,
        "severity": value.severity.value,
        "artifact_id": value.artifact_id,
        "json_pointer": value.json_pointer,
        "source_span": span,
        "message": value.message,
        "remediation": value.remediation,
    }


def preview_to_document(
    preview: PreviewBuild, *, include_fingerprint: bool = True
) -> dict[str, object]:
    document: dict[str, object] = {
        "format_version": preview.format_version,
        "preview_id": preview.preview_id,
        "project_id": preview.project_id,
        "kind": preview.kind,
        "sealed": preview.sealed,
        "distributable": preview.distributable,
        "release_evidence": preview.release_evidence,
        "identity_scope": preview.identity_scope,
        "profile_id": preview.profile_id,
        "blueprint_sha256": preview.blueprint_sha256,
        "project_sha256": preview.project_sha256,
        "engine_version": preview.engine_version,
        "content_files": [
            canonical_content_file_to_document(value) for value in preview.content_files
        ],
    }
    if include_fingerprint:
        document["fingerprint"] = preview.fingerprint
    return document


def simulation_request_to_document(value: SimulationRequest) -> dict[str, object]:
    return {
        "format_version": value.format_version,
        "seed": value.seed,
        "clock": value.clock,
        "player_name": value.player_name,
        "intents": [game_intent_to_document(intent) for intent in value.intents],
        "conditions": [_condition_to_document(item) for item in value.conditions],
        "checkpoint_after_steps": list(value.checkpoint_after_steps),
    }


def capability_simulation_request_to_document(
    value: CapabilitySimulationRequest,
) -> dict[str, object]:
    return {
        "format_version": value.format_version,
        "seed": value.seed,
        "clock": value.clock,
        "player_name": value.player_name,
        "steps": [_capability_step_to_document(step) for step in value.steps],
        "conditions": [_condition_to_document(item) for item in value.conditions],
        "checkpoint_after_steps": list(value.checkpoint_after_steps),
    }


def simulation_report_to_document(
    report: SimulationReport, *, include_fingerprint: bool = True
) -> dict[str, object]:
    document: dict[str, object] = {
        "format_version": report.format_version,
        "project_id": report.project_id,
        "blueprint_sha256": report.blueprint_sha256,
        "project_sha256": report.project_sha256,
        "preview_fingerprint": report.preview_fingerprint,
        "request_sha256": report.request_sha256,
        "engine_version": report.engine_version,
        "seed": report.seed,
        "clock": report.clock,
        "player_name": report.player_name,
        "initial_state_sha256": report.initial_state_sha256,
        "final_state_sha256": report.final_state_sha256,
        "initial_view_sha256": report.initial_view_sha256,
        "final_view_sha256": report.final_view_sha256,
        "turns": [_turn_to_document(value) for value in report.turns],
        "condition_results": [
            {
                "condition": _condition_to_document(value.condition),
                "matched": value.matched,
            }
            for value in report.condition_results
        ],
        "outcome": report.outcome.value,
        "witness_trace": [_turn_to_document(value) for value in report.witness_trace],
        "replay_verified": report.replay_verified,
        "checkpoints": [
            _checkpoint_to_document(value) for value in report.checkpoints
        ],
        "identity_scope": report.identity_scope,
    }
    if include_fingerprint:
        document["fingerprint"] = report.fingerprint
    return document


def capability_preview_to_document(
    value: CapabilityPreview, *, include_fingerprint: bool = True
) -> dict[str, object]:
    document = {
        "format_version": value.format_version,
        "kind": value.kind,
        "sealed": value.sealed,
        "distributable": value.distributable,
        "release_evidence": value.release_evidence,
        "identity_scope": value.identity_scope,
        "base_preview": preview_to_document(value.base_preview),
        "resolved_plan": _capability_value_to_document(value.resolved_plan),
        "plan_sha256": value.plan_sha256,
        "initial_states": [
            _capability_value_to_document(item) for item in value.initial_states
        ],
        "initial_state_sha256": value.initial_state_sha256,
        "engine_version": value.engine_version,
    }
    if include_fingerprint:
        document["fingerprint"] = value.fingerprint
    return document


def capability_simulation_report_to_document(
    value: CapabilitySimulationReport, *, include_fingerprint: bool = True
) -> dict[str, object]:
    document = {
        "format_version": value.format_version,
        "project_id": value.project_id,
        "base_report": simulation_report_to_document(value.base_report),
        "request_sha256": value.request_sha256,
        "capability_preview_fingerprint": value.capability_preview_fingerprint,
        "plan_sha256": value.plan_sha256,
        "initial_capability_state_sha256": value.initial_capability_state_sha256,
        "final_capability_state_sha256": value.final_capability_state_sha256,
        "turns": [_capability_turn_to_document(item) for item in value.turns],
        "witness_trace": [
            _capability_turn_to_document(item) for item in value.witness_trace
        ],
        "capability_event_sha256": value.capability_event_sha256,
        "capability_view_sha256": value.capability_view_sha256,
        "replay_verified": value.replay_verified,
        "checkpoints": [
            _capability_checkpoint_to_document(item) for item in value.checkpoints
        ],
        "identity_scope": value.identity_scope,
    }
    if include_fingerprint:
        document["fingerprint"] = value.fingerprint
    return document


def proofing_to_document(value: ProofingProjection) -> dict[str, object]:
    return {
        "format_version": value.format_version,
        "project_id": value.project_id,
        "preview_fingerprint": value.preview_fingerprint,
        "nodes": [
            {"node_id": item.node_id, "kind": item.kind, "label": item.label}
            for item in value.nodes
        ],
        "edges": [
            {
                "source_id": item.source_id,
                "target_id": item.target_id,
                "kind": item.kind,
            }
            for item in value.edges
        ],
        "admissible_intents": [
            _descriptor_to_document(item) for item in value.admissible_intents
        ],
        "diagnostics": [diagnostic_to_document(item) for item in value.diagnostics],
    }


def capability_proofing_to_document(
    value: CapabilityProofingProjection,
) -> dict[str, object]:
    return {
        "format_version": value.format_version,
        "project_id": value.project_id,
        "capability_preview_fingerprint": value.capability_preview_fingerprint,
        "base_proofing": proofing_to_document(value.base_proofing),
        "capability_views": [
            _capability_value_to_document(item) for item in value.capability_views
        ],
        "fingerprint": value.fingerprint,
        "diagnostics": [
            diagnostic_to_document(item) for item in sort_diagnostics(value.diagnostics)
        ],
    }


def capability_authoring_result_to_document(
    result: CapabilityAuthoringResult[object],
) -> dict[str, object]:
    return {
        "format_version": result.format_version,
        "kind": result.kind,
        "operation": result.operation,
        "status": result.status.value,
        "artifact": _capability_artifact_to_document(result.artifact),
        "diagnostics": [
            diagnostic_to_document(item) for item in sort_diagnostics(result.diagnostics)
        ],
        "exit_code": result.exit_code,
    }


def authoring_result_to_document(
    result: AuthoringResult[object] | CapabilityAuthoringResult[object],
) -> dict[str, object]:
    if isinstance(result, CapabilityAuthoringResult):
        return capability_authoring_result_to_document(result)
    return {
        "format_version": result.format_version,
        "operation": result.operation,
        "status": result.status.value,
        "artifact": _artifact_to_document(result.artifact),
        "diagnostics": [
            diagnostic_to_document(item) for item in sort_diagnostics(result.diagnostics)
        ],
        "exit_code": result.exit_code,
    }


def typed_value_to_document(value: object) -> object:
    """Serialize trusted frozen application values without exposing hidden World state."""
    if isinstance(value, GameIntent):
        return game_intent_to_document(value)
    if value is None or type(value) in {str, int, bool}:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("non-finite float is not serializable")
        return value
    if isinstance(value, Enum):
        return value.value
    if type(value) in {tuple, list}:
        sequence = cast(tuple[object, ...] | list[object], value)
        return [typed_value_to_document(item) for item in sequence]
    if type(value) is dict:
        mapping = cast(dict[object, object], value)
        if any(type(key) is not str for key in mapping):
            raise TypeError("JSON object keys must be strings")
        return {
            cast(str, key): typed_value_to_document(item)
            for key, item in mapping.items()
        }
    if is_dataclass(value) and not isinstance(value, type):
        document: dict[str, object] = {}
        for field in fields(value):
            item = getattr(value, field.name)
            if field.name == "capabilities" and item is None:
                continue
            document[field.name] = typed_value_to_document(item)
        return document
    raise TypeError(f"unsupported typed value: {type(value).__name__}")


def _artifact_to_document(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, GameBlueprint):
        return blueprint_to_document(value)
    if isinstance(value, GameProject):
        return project_to_document(value)
    if isinstance(value, PreviewBuild):
        return preview_to_document(value)
    if isinstance(value, SimulationReport):
        return simulation_report_to_document(value)
    if isinstance(value, ProofingProjection):
        return proofing_to_document(value)
    return typed_value_to_document(value)


def _capability_artifact_to_document(value: object) -> object:
    if isinstance(value, CapabilityPreview):
        return capability_preview_to_document(value)
    if isinstance(value, CapabilitySimulationReport):
        return capability_simulation_report_to_document(value)
    if isinstance(value, CapabilityProofingProjection):
        return capability_proofing_to_document(value)
    return _artifact_to_document(value)


def _acceptance_scenario_to_document(value: AcceptanceScenario) -> dict[str, object]:
    return {
        "scenario_id": value.scenario_id,
        "description": value.description,
        "outcome": value.outcome.value,
    }


def _condition_to_document(value: SimulationCondition) -> dict[str, object]:
    return {
        "condition_id": value.condition_id,
        "outcome": value.outcome.value,
        "kind": value.kind.value,
        "expected": value.expected,
    }


def _turn_to_document(value: SimulationTurn) -> dict[str, object]:
    return {
        "index": value.index,
        "intent": game_intent_to_document(value.intent),
        "status": value.status,
        "rejection_code": value.rejection_code,
        "event_types": list(value.event_types),
        "view_sha256": value.view_sha256,
    }


def _checkpoint_to_document(value: SimulationCheckpoint) -> dict[str, object]:
    return {
        "after_step": value.after_step,
        "before_state_sha256": value.before_state_sha256,
        "loaded_state_sha256": value.loaded_state_sha256,
        "before_view_sha256": value.before_view_sha256,
        "loaded_view_sha256": value.loaded_view_sha256,
        "equivalent": value.equivalent,
    }


def _capability_step_to_document(value: object) -> object:
    if isinstance(value, GameIntent):
        return game_intent_to_document(value)
    return _capability_value_to_document(value)


def _capability_turn_to_document(
    value: CapabilitySimulationTurn,
) -> dict[str, object]:
    return {
        "index": value.index,
        "step": _capability_step_to_document(value.step),
        "status": value.status,
        "rejection_code": value.rejection_code,
        "event_sha256": value.event_sha256,
        "view_sha256": value.view_sha256,
        "capability_state_sha256": value.capability_state_sha256,
        "event_sequence_after": value.event_sequence_after,
    }


def _capability_checkpoint_to_document(
    value: CapabilitySimulationCheckpoint,
) -> dict[str, object]:
    return {
        "after_step": value.after_step,
        "checkpoint_sha256": value.checkpoint_sha256,
        "restored_state_sha256": value.restored_state_sha256,
        "restored_view_sha256": value.restored_view_sha256,
        "restored_event_sequence": value.restored_event_sequence,
        "equivalent": value.equivalent,
    }


def _capability_value_to_document(value: object) -> object:
    from lore2mud.capabilities.serialization import capability_value_to_document

    return capability_value_to_document(value)


def _descriptor_to_document(value: AdmissibleIntentDescriptor) -> dict[str, object]:
    return {
        "descriptor_id": value.descriptor_id,
        "intent": game_intent_to_document(value.intent),
        "fields": [
            {"name": field.name, "value": field.value} for field in value.fields
        ],
    }


def _object(value: object, location: str) -> dict[str, object]:
    if type(value) is not dict:
        raise ValueError(f"{location} must be an object")
    return cast(dict[str, object], value)


def _exact_keys(data: dict[str, object], expected: set[str], location: str) -> None:
    if set(data) != expected:
        raise ValueError(f"{location} fields are invalid")


def _text(value: object, location: str, *, maximum: int | None = None) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{location} must be a non-blank string")
    if maximum is not None and len(value) > maximum:
        raise ValueError(f"{location} exceeds the maximum length")
    validate_unicode_scalars(value)
    return value


def _optional_text(
    value: object, location: str, *, maximum: int | None = None
) -> str | None:
    return None if value is None else _text(value, location, maximum=maximum)


def _integer(value: object, location: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{location} must be an integer")
    return value
