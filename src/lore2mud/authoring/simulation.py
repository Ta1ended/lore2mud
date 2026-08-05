"""Deterministic, isolated V2-2 simulation and replay evidence."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import re
import tempfile
from typing import cast

from lore2mud import __version__
from lore2mud._bounded_json import (
    BoundedJsonError,
    DEFAULT_JSON_READ_LIMITS,
    JsonReadErrorCode,
    read_bounded_json,
)
from lore2mud.application.contracts import (
    DeterminismContext,
    GameEventKind,
    GameView,
    RejectionCode,
    SaveIntent,
    LoadIntent,
    KnowledgeStatus,
    ObjectiveStatus,
    TurnStatus,
)
from lore2mud.application.session import GameSession
from lore2mud.authoring.contracts import (
    REPORT_IDENTITY_SCOPE,
    AuthoringDiagnostic,
    AuthoringResult,
    AuthoringStage,
    AuthoringStatus,
    ConditionOutcome,
    DiagnosticSeverity,
    GameProject,
    PreviewBuild,
    SimulationCheckpoint,
    SimulationCondition,
    SimulationConditionKind,
    SimulationConditionResult,
    SimulationOutcome,
    SimulationReport,
    SimulationRequest,
    SimulationTurn,
)
from lore2mud.authoring.preview import (
    PreviewValidationError,
    build_preview,
    load_preview_document,
    materialized_preview_pack,
)
from lore2mud.authoring.project import (
    BlueprintValidationError,
    ProjectValidationError,
    read_authoring_json,
    validate_project,
)
from lore2mud.authoring.serialization import (
    AuthoringDocumentTraversalError,
    InvalidUnicodeScalarError,
    fingerprint_document,
    game_intent_from_document,
    normalize_bounded_json_document,
    simulation_report_to_document,
    simulation_request_to_document,
    typed_value_to_document,
    validate_unicode_scalars,
)
from lore2mud.content.loader import ContentValidationError
from lore2mud.engine.save import SaveLoadService


_STABLE_ID = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MAX_INTENTS = 1024
_MAX_CONDITIONS = 256


class SimulationValidationError(ValueError):
    """Raised when an untrusted simulation artifact is invalid."""

    def __init__(self, issues: Sequence[str]) -> None:
        self.issues = tuple(issues)
        super().__init__("; ".join(self.issues))


class _SimulationRequestNormalizationError(SimulationValidationError):
    def __init__(self, code: JsonReadErrorCode) -> None:
        self.code = code
        super().__init__(("simulation request cannot be normalized safely",))


class _SimulationExecutionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class _TraceRun:
    initial_view: GameView
    final_view: GameView
    turns: tuple[SimulationTurn, ...]


def simulate_project(
    project: GameProject, request: SimulationRequest
) -> AuthoringResult[SimulationReport]:
    """Build and simulate from a project so the capability gate is never bypassed."""
    resource_rejection = _preflight_simulation_request_resources(request)
    if resource_rejection is not None:
        return resource_rejection
    try:
        normalized_project = validate_project(project)
    except InvalidUnicodeScalarError:
        return _authoring_input_resource_rejection(
            "simulate", "project", JsonReadErrorCode.TOO_COMPLEX
        )
    except AuthoringDocumentTraversalError:
        return _authoring_input_resource_rejection(
            "simulate", "project", JsonReadErrorCode.TOO_COMPLEX
        )
    except BoundedJsonError as exc:
        return _authoring_input_resource_rejection("simulate", "project", exc.code)
    except (BlueprintValidationError, ProjectValidationError):
        preview_result = build_preview(project)
    else:
        preview_result = build_preview(normalized_project)
    if not preview_result.ok:
        return _rejected("simulate", preview_result.diagnostics)
    preview = preview_result.artifact
    assert preview is not None
    return simulate_preview(preview, request)


def simulate_preview(
    preview: PreviewBuild, request: SimulationRequest
) -> AuthoringResult[SimulationReport]:
    """Run request intents only in a fresh witness session and build replay evidence."""
    resource_rejection = _preflight_simulation_request_resources(request)
    if resource_rejection is not None:
        return resource_rejection
    try:
        validated_preview = load_preview_document(
            _preview_document(preview)
        )
        normalized_request = validate_simulation_request(request)
        witness = _run_trace(validated_preview, normalized_request)
        replay = _run_trace(validated_preview, normalized_request)
        initial_state_sha256 = _state_hash_after(
            validated_preview, normalized_request, after_step=0
        )
        final_state_sha256 = _state_hash_after(
            validated_preview,
            normalized_request,
            after_step=len(normalized_request.intents),
        )
        checkpoints = tuple(
            _checkpoint(validated_preview, normalized_request, after_step)
            for after_step in normalized_request.checkpoint_after_steps
        )
    except _SimulationRequestNormalizationError as exc:
        return _simulation_request_resource_rejection(exc.code)
    except InvalidUnicodeScalarError:
        return _simulation_request_unicode_rejection()
    except SimulationValidationError:
        return _rejected(
            "simulate",
            (
                _diagnostic(
                    preview.project_id,
                    "simulation_request_invalid",
                    "/",
                    "The simulation request is invalid.",
                    "Correct the bounded typed request and retry.",
                ),
            ),
        )
    except (PreviewValidationError, ContentValidationError, OSError, BoundedJsonError):
        return _rejected(
            "simulate",
            (
                _diagnostic(
                    preview.project_id,
                    "simulation_preview_invalid",
                    "/preview",
                    "The preview could not be loaded in an isolated session.",
                    "Rebuild the preview from a valid public-safe project.",
                ),
            ),
        )
    except _SimulationExecutionError:
        return _rejected(
            "simulate",
            (
                _diagnostic(
                    preview.project_id,
                    "simulation_evidence_failed",
                    "/",
                    "The isolated simulation could not produce complete evidence.",
                    "Correct persistence inputs or the request and retry.",
                ),
            ),
        )

    initial_view_sha256 = _view_hash(witness.initial_view)
    final_view_sha256 = _view_hash(witness.final_view)
    replay_verified = (
        witness.turns == replay.turns
        and initial_view_sha256 == _view_hash(replay.initial_view)
        and final_view_sha256 == _view_hash(replay.final_view)
    )
    condition_results = tuple(
        SimulationConditionResult(condition, _condition_matches(condition, witness.final_view))
        for condition in normalized_request.conditions
    )
    outcome = _outcome(condition_results)
    request_sha256 = fingerprint_document(
        simulation_request_to_document(normalized_request)
    )
    report_without_fingerprint = SimulationReport(
        format_version=1,
        project_id=validated_preview.project_id,
        blueprint_sha256=validated_preview.blueprint_sha256,
        project_sha256=validated_preview.project_sha256,
        preview_fingerprint=validated_preview.fingerprint,
        request_sha256=request_sha256,
        engine_version=__version__,
        seed=normalized_request.seed,
        clock=normalized_request.clock,
        player_name=normalized_request.player_name,
        initial_state_sha256=initial_state_sha256,
        final_state_sha256=final_state_sha256,
        initial_view_sha256=initial_view_sha256,
        final_view_sha256=final_view_sha256,
        turns=witness.turns,
        condition_results=condition_results,
        outcome=outcome,
        witness_trace=witness.turns,
        replay_verified=replay_verified,
        checkpoints=checkpoints,
        fingerprint="",
    )
    fingerprint = fingerprint_document(
        simulation_report_to_document(report_without_fingerprint, include_fingerprint=False)
    )
    report = SimulationReport(
        format_version=report_without_fingerprint.format_version,
        project_id=report_without_fingerprint.project_id,
        blueprint_sha256=report_without_fingerprint.blueprint_sha256,
        project_sha256=report_without_fingerprint.project_sha256,
        preview_fingerprint=report_without_fingerprint.preview_fingerprint,
        request_sha256=report_without_fingerprint.request_sha256,
        engine_version=report_without_fingerprint.engine_version,
        seed=report_without_fingerprint.seed,
        clock=report_without_fingerprint.clock,
        player_name=report_without_fingerprint.player_name,
        initial_state_sha256=report_without_fingerprint.initial_state_sha256,
        final_state_sha256=report_without_fingerprint.final_state_sha256,
        initial_view_sha256=report_without_fingerprint.initial_view_sha256,
        final_view_sha256=report_without_fingerprint.final_view_sha256,
        turns=report_without_fingerprint.turns,
        condition_results=report_without_fingerprint.condition_results,
        outcome=report_without_fingerprint.outcome,
        witness_trace=report_without_fingerprint.witness_trace,
        replay_verified=report_without_fingerprint.replay_verified,
        checkpoints=report_without_fingerprint.checkpoints,
        fingerprint=fingerprint,
    )
    return AuthoringResult(
        format_version=1,
        operation="simulate",
        status=AuthoringStatus.SUCCESS,
        artifact=report,
        diagnostics=(),
        exit_code=0,
    )


def replay_report(
    project: GameProject, report: SimulationReport
) -> AuthoringResult[SimulationReport]:
    """Re-run a report witness in fresh sessions and require byte-equivalent evidence."""
    preview_result = build_preview(project)
    if not preview_result.ok:
        return _rejected("replay", preview_result.diagnostics)
    preview = preview_result.artifact
    assert preview is not None
    try:
        expected = validate_simulation_report(report)
    except SimulationValidationError:
        return _rejected(
            "replay",
            (
                _diagnostic(
                    preview.project_id,
                    "simulation_report_invalid",
                    "/report",
                    "The simulation report is invalid.",
                    "Provide an intact V2-2 SimulationReport v1.",
                ),
            ),
        )
    if (
        expected.project_id != preview.project_id
        or expected.blueprint_sha256 != preview.blueprint_sha256
        or expected.project_sha256 != preview.project_sha256
        or expected.preview_fingerprint != preview.fingerprint
    ):
        return _rejected(
            "replay",
            (
                _diagnostic(
                    preview.project_id,
                    "simulation_report_project_mismatch",
                    "/report/preview_fingerprint",
                    "The report does not belong to this project preview.",
                    "Replay the report against the exact project that produced it.",
                ),
            ),
        )
    request = SimulationRequest(
        format_version=1,
        seed=expected.seed,
        clock=expected.clock,
        player_name=expected.player_name,
        intents=tuple(turn.intent for turn in expected.witness_trace),
        conditions=tuple(result.condition for result in expected.condition_results),
        checkpoint_after_steps=tuple(item.after_step for item in expected.checkpoints),
    )
    replayed = simulate_preview(preview, request)
    if not replayed.ok or replayed.artifact is None:
        return _rejected("replay", replayed.diagnostics)
    if simulation_report_to_document(replayed.artifact) != simulation_report_to_document(
        expected
    ):
        return _rejected(
            "replay",
            (
                _diagnostic(
                    project.project_id,
                    "simulation_replay_mismatch",
                    "/report/witness_trace",
                    "Fresh replay evidence differs from the supplied report.",
                    "Regenerate the report from the exact preview and request inputs.",
                ),
            ),
        )
    return AuthoringResult(
        format_version=1,
        operation="replay",
        status=AuthoringStatus.SUCCESS,
        artifact=replayed.artifact,
        diagnostics=(),
        exit_code=0,
    )


def load_simulation_request(path: Path) -> SimulationRequest:
    return load_simulation_request_document(read_authoring_json(path))


def load_simulation_request_document(document: object) -> SimulationRequest:
    data = _object(document, "request")
    _exact_keys(
        data,
        {
            "format_version",
            "seed",
            "clock",
            "player_name",
            "intents",
            "conditions",
            "checkpoint_after_steps",
        },
        "request",
    )
    if _integer(data["format_version"], "request.format_version") != 1:
        raise SimulationValidationError(("request.format_version must be 1",))
    seed = _bounded_integer(data["seed"], "request.seed")
    clock = _bounded_integer(data["clock"], "request.clock")
    player_name = _text(data["player_name"], "request.player_name", maximum=128)
    raw_intents = _list(data["intents"], "request.intents", maximum=_MAX_INTENTS)
    try:
        intents = tuple(game_intent_from_document(item) for item in raw_intents)
    except (TypeError, ValueError):
        raise SimulationValidationError(("request.intents contains an invalid intent",)) from None
    conditions = tuple(
        sorted(
            (_load_condition(item) for item in _list(
                data["conditions"], "request.conditions", maximum=_MAX_CONDITIONS
            )),
            key=lambda item: (
                item.condition_id,
                item.kind.value,
                item.outcome.value,
                str(item.expected),
            ),
        )
    )
    if len({item.condition_id for item in conditions}) != len(conditions):
        raise SimulationValidationError(("request.conditions contains duplicate IDs",))
    checkpoints = tuple(
        sorted(
            _integer(item, "request.checkpoint_after_steps[]")
            for item in _list(
                data["checkpoint_after_steps"],
                "request.checkpoint_after_steps",
                maximum=_MAX_INTENTS + 1,
            )
        )
    )
    if len(set(checkpoints)) != len(checkpoints) or any(
        value < 0 or value > len(intents) for value in checkpoints
    ):
        raise SimulationValidationError(("request checkpoint steps are invalid",))
    return SimulationRequest(
        format_version=1,
        seed=seed,
        clock=clock,
        player_name=player_name,
        intents=intents,
        conditions=conditions,
        checkpoint_after_steps=checkpoints,
    )


def _normalize_simulation_request_document(request: SimulationRequest) -> object:
    if type(request) is not SimulationRequest:
        raise SimulationValidationError(("request is not a typed SimulationRequest v1",))
    try:
        document = simulation_request_to_document(request)
    except (AttributeError, RecursionError, TypeError, ValueError):
        raise SimulationValidationError(("request is not a valid typed request",)) from None
    try:
        normalized_document = normalize_bounded_json_document(document)
    except InvalidUnicodeScalarError:
        raise
    except AuthoringDocumentTraversalError:
        raise _SimulationRequestNormalizationError(
            JsonReadErrorCode.TOO_COMPLEX
        ) from None
    except BoundedJsonError as exc:
        raise _SimulationRequestNormalizationError(exc.code) from None
    except (RecursionError, TypeError, ValueError):
        raise SimulationValidationError(("request is not a valid typed request",)) from None
    return normalized_document


def _preflight_simulation_request_resources(
    request: SimulationRequest,
) -> AuthoringResult[SimulationReport] | None:
    try:
        _normalize_simulation_request_document(request)
    except _SimulationRequestNormalizationError as exc:
        return _simulation_request_resource_rejection(exc.code)
    except InvalidUnicodeScalarError:
        return _simulation_request_unicode_rejection()
    except SimulationValidationError:
        # Shape/domain diagnostics keep their existing ordering; only resource
        # failures must precede preview construction and loading.
        return None
    return None


def _simulation_request_resource_rejection(
    code: JsonReadErrorCode,
) -> AuthoringResult[SimulationReport]:
    return _authoring_input_resource_rejection(
        "simulate", "simulation_request", code
    )


def _authoring_input_resource_rejection(
    operation: str,
    artifact_id: str,
    code: JsonReadErrorCode,
) -> AuthoringResult[SimulationReport]:
    return _rejected(
        operation,
        (
            _diagnostic(
                artifact_id,
                f"authoring_input_{code.value}",
                "/",
                "The authoring JSON input could not be read safely.",
                "Provide readable UTF-8 JSON within the documented resource limits.",
                stage=AuthoringStage.SERIALIZATION,
            ),
        ),
    )


def _simulation_request_unicode_rejection() -> AuthoringResult[SimulationReport]:
    return _simulation_request_resource_rejection(JsonReadErrorCode.TOO_COMPLEX)


def validate_simulation_request(request: SimulationRequest) -> SimulationRequest:
    normalized_document = _normalize_simulation_request_document(request)
    return load_simulation_request_document(normalized_document)


def load_simulation_report(path: Path) -> SimulationReport:
    return load_simulation_report_document(read_authoring_json(path))


def validate_simulation_report(report: SimulationReport) -> SimulationReport:
    if type(report) is not SimulationReport:
        raise SimulationValidationError(("report is not a typed SimulationReport v1",))
    try:
        document = simulation_report_to_document(report)
    except (AttributeError, RecursionError, TypeError, ValueError):
        raise SimulationValidationError(("report is not a valid typed report",)) from None
    return load_simulation_report_document(normalize_bounded_json_document(document))


def load_simulation_report_document(document: object) -> SimulationReport:
    data = _object(document, "report")
    _exact_keys(
        data,
        {
            "format_version",
            "project_id",
            "blueprint_sha256",
            "project_sha256",
            "preview_fingerprint",
            "request_sha256",
            "engine_version",
            "seed",
            "clock",
            "player_name",
            "initial_state_sha256",
            "final_state_sha256",
            "initial_view_sha256",
            "final_view_sha256",
            "turns",
            "condition_results",
            "outcome",
            "witness_trace",
            "replay_verified",
            "checkpoints",
            "identity_scope",
            "fingerprint",
        },
        "report",
    )
    if _integer(data["format_version"], "report.format_version") != 1:
        raise SimulationValidationError(("report.format_version must be 1",))
    if data["identity_scope"] != REPORT_IDENTITY_SCOPE:
        raise SimulationValidationError(("report.identity_scope is invalid",))
    turns = tuple(
        _load_turn(item)
        for item in _list(data["turns"], "report.turns", maximum=_MAX_INTENTS)
    )
    witness = tuple(
        _load_turn(item)
        for item in _list(
            data["witness_trace"], "report.witness_trace", maximum=_MAX_INTENTS
        )
    )
    if turns != witness or any(turn.index != index for index, turn in enumerate(turns, 1)):
        raise SimulationValidationError(("report witness trace is inconsistent",))
    condition_results = tuple(
        _load_condition_result(item)
        for item in _list(
            data["condition_results"],
            "report.condition_results",
            maximum=_MAX_CONDITIONS,
        )
    )
    checkpoints = tuple(
        _load_checkpoint(item)
        for item in _list(
            data["checkpoints"], "report.checkpoints", maximum=_MAX_INTENTS + 1
        )
    )
    replay_verified = _boolean(data["replay_verified"], "report.replay_verified")
    engine_version = _text(data["engine_version"], "report.engine_version", maximum=64)
    if engine_version != __version__:
        raise SimulationValidationError(("report.engine_version is not supported",))
    report = SimulationReport(
        format_version=1,
        project_id=_stable_id(data["project_id"], "report.project_id"),
        blueprint_sha256=_sha256(data["blueprint_sha256"], "report.blueprint_sha256"),
        project_sha256=_sha256(data["project_sha256"], "report.project_sha256"),
        preview_fingerprint=_sha256(
            data["preview_fingerprint"], "report.preview_fingerprint"
        ),
        request_sha256=_sha256(data["request_sha256"], "report.request_sha256"),
        engine_version=engine_version,
        seed=_bounded_integer(data["seed"], "report.seed"),
        clock=_bounded_integer(data["clock"], "report.clock"),
        player_name=_text(data["player_name"], "report.player_name", maximum=128),
        initial_state_sha256=_sha256(
            data["initial_state_sha256"], "report.initial_state_sha256"
        ),
        final_state_sha256=_sha256(
            data["final_state_sha256"], "report.final_state_sha256"
        ),
        initial_view_sha256=_sha256(
            data["initial_view_sha256"], "report.initial_view_sha256"
        ),
        final_view_sha256=_sha256(
            data["final_view_sha256"], "report.final_view_sha256"
        ),
        turns=turns,
        condition_results=condition_results,
        outcome=_enum(SimulationOutcome, data["outcome"], "report.outcome"),
        witness_trace=witness,
        replay_verified=replay_verified,
        checkpoints=checkpoints,
        fingerprint=_sha256(data["fingerprint"], "report.fingerprint"),
    )
    expected_fingerprint = fingerprint_document(
        simulation_report_to_document(report, include_fingerprint=False)
    )
    if report.fingerprint != expected_fingerprint:
        raise SimulationValidationError(("report.fingerprint does not match canonical bytes",))
    return report


def _run_trace(preview: PreviewBuild, request: SimulationRequest) -> _TraceRun:
    with _isolated_session(preview, request) as (session, _service):
        initial_view = session.view()
        final_view = initial_view
        turns: list[SimulationTurn] = []
        for index, intent in enumerate(request.intents, 1):
            result = session.submit(intent)
            final_view = result.view
            turns.append(
                SimulationTurn(
                    index=index,
                    intent=intent,
                    status=result.status.value,
                    rejection_code=(
                        None if result.rejection is None else result.rejection.code.value
                    ),
                    event_types=tuple(event.kind.value for event in result.events),
                    view_sha256=_view_hash(result.view),
                )
            )
        return _TraceRun(initial_view, final_view, tuple(turns))


def _state_hash_after(
    preview: PreviewBuild, request: SimulationRequest, *, after_step: int
) -> str:
    with _isolated_session(preview, request) as (session, service):
        _submit_prefix(session, request, after_step)
        return _save_state_hash(session, service, "evidence_state")


def _checkpoint(
    preview: PreviewBuild, request: SimulationRequest, after_step: int
) -> SimulationCheckpoint:
    with _isolated_session(preview, request) as (session, service):
        _submit_prefix(session, request, after_step)
        before_view_sha256 = _view_hash(session.view())
        before_state_sha256 = _save_state_hash(session, service, "checkpoint_before")
        loaded = session.submit(LoadIntent("checkpoint_before"))
        if loaded.status is not TurnStatus.ACCEPTED:
            raise _SimulationExecutionError("checkpoint load rejected")
        loaded_view_sha256 = _view_hash(loaded.view)
        loaded_state_sha256 = _save_state_hash(session, service, "checkpoint_loaded")
        return SimulationCheckpoint(
            after_step=after_step,
            before_state_sha256=before_state_sha256,
            loaded_state_sha256=loaded_state_sha256,
            before_view_sha256=before_view_sha256,
            loaded_view_sha256=loaded_view_sha256,
            equivalent=(
                before_state_sha256 == loaded_state_sha256
                and before_view_sha256 == loaded_view_sha256
            ),
        )


@contextmanager
def _isolated_session(preview: PreviewBuild, request: SimulationRequest):
    with materialized_preview_pack(preview) as pack:
        with tempfile.TemporaryDirectory(prefix="lore2mud-v2-simulation-save-") as save_dir:
            service = SaveLoadService(pack, Path(save_dir))
            context = DeterminismContext(seed=request.seed, clock=request.clock)
            session = GameSession.from_content_pack(
                pack,
                service,
                player_name=request.player_name,
                determinism=context,
            )
            yield session, service


def _submit_prefix(session: GameSession, request: SimulationRequest, length: int) -> None:
    for intent in request.intents[:length]:
        session.submit(intent)


def _save_state_hash(
    session: GameSession, service: SaveLoadService, slot: str
) -> str:
    result = session.submit(SaveIntent(slot))
    if result.status is not TurnStatus.ACCEPTED:
        raise _SimulationExecutionError("evidence save rejected")
    document = read_bounded_json(service.slot_path(slot), DEFAULT_JSON_READ_LIMITS)
    return fingerprint_document(document)


def _view_hash(view: GameView) -> str:
    return fingerprint_document(typed_value_to_document(view))


def _condition_matches(condition: SimulationCondition, view: GameView) -> bool:
    if condition.kind is SimulationConditionKind.PLAYER_ALIVE:
        return view.player.alive is condition.expected
    if condition.kind is SimulationConditionKind.ROOM_ID:
        return view.room.id == condition.expected
    if condition.kind is SimulationConditionKind.QUEST_COMPLETED:
        return any(
            quest.id == condition.condition_id and quest.completed is condition.expected
            for quest in view.quests
        )
    if condition.kind is SimulationConditionKind.OBJECTIVE_STATUS:
        return any(
            entry.id == condition.condition_id
            and entry.status is not None
            and entry.status.value == condition.expected
            for entry in view.campaign.objectives
        )
    if condition.kind is SimulationConditionKind.KNOWLEDGE_STATUS:
        return any(
            entry.id == condition.condition_id
            and entry.status is not None
            and entry.status.value == condition.expected
            for entry in view.campaign.knowledge
        )
    raise AssertionError(f"unsupported condition kind: {condition.kind}")


def _outcome(results: tuple[SimulationConditionResult, ...]) -> SimulationOutcome:
    if any(
        result.matched and result.condition.outcome is ConditionOutcome.LOSS
        for result in results
    ):
        return SimulationOutcome.LOSS
    if any(
        result.matched and result.condition.outcome is ConditionOutcome.WIN
        for result in results
    ):
        return SimulationOutcome.WIN
    return SimulationOutcome.UNDETERMINED


def _load_condition(value: object) -> SimulationCondition:
    data = _object(value, "condition")
    _exact_keys(data, {"condition_id", "outcome", "kind", "expected"}, "condition")
    condition_id = _stable_id(data["condition_id"], "condition.condition_id")
    outcome = _enum(ConditionOutcome, data["outcome"], "condition.outcome")
    kind = _enum(SimulationConditionKind, data["kind"], "condition.kind")
    expected = data["expected"]
    if kind in {SimulationConditionKind.PLAYER_ALIVE, SimulationConditionKind.QUEST_COMPLETED}:
        expected = _boolean(expected, "condition.expected")
    elif kind is SimulationConditionKind.ROOM_ID:
        expected = _stable_id(expected, "condition.expected")
    elif kind is SimulationConditionKind.OBJECTIVE_STATUS:
        expected = _enum(ObjectiveStatus, expected, "condition.expected").value
    else:
        assert kind is SimulationConditionKind.KNOWLEDGE_STATUS
        expected = _enum(KnowledgeStatus, expected, "condition.expected").value
    return SimulationCondition(condition_id, outcome, kind, expected)


def _load_turn(value: object) -> SimulationTurn:
    data = _object(value, "turn")
    _exact_keys(
        data,
        {"index", "intent", "status", "rejection_code", "event_types", "view_sha256"},
        "turn",
    )
    try:
        intent = game_intent_from_document(data["intent"])
    except (TypeError, ValueError):
        raise SimulationValidationError(("turn.intent is invalid",)) from None
    status = _enum(TurnStatus, data["status"], "turn.status")
    rejection_code: str | None
    if data["rejection_code"] is None:
        rejection_code = None
    else:
        rejection_code = _enum(
            RejectionCode, data["rejection_code"], "turn.rejection_code"
        ).value
    if (status is TurnStatus.ACCEPTED) != (rejection_code is None):
        raise SimulationValidationError(("turn rejection fields are inconsistent",))
    event_types = tuple(
        _enum(GameEventKind, item, "turn.event_types[]").value
        for item in _list(data["event_types"], "turn.event_types", maximum=8)
    )
    if status is TurnStatus.REJECTED and event_types:
        raise SimulationValidationError(("rejected turns cannot contain events",))
    return SimulationTurn(
        index=_integer(data["index"], "turn.index"),
        intent=intent,
        status=status.value,
        rejection_code=rejection_code,
        event_types=event_types,
        view_sha256=_sha256(data["view_sha256"], "turn.view_sha256"),
    )


def _load_condition_result(value: object) -> SimulationConditionResult:
    data = _object(value, "condition_result")
    _exact_keys(data, {"condition", "matched"}, "condition_result")
    return SimulationConditionResult(
        _load_condition(data["condition"]),
        _boolean(data["matched"], "condition_result.matched"),
    )


def _load_checkpoint(value: object) -> SimulationCheckpoint:
    data = _object(value, "checkpoint")
    _exact_keys(
        data,
        {
            "after_step",
            "before_state_sha256",
            "loaded_state_sha256",
            "before_view_sha256",
            "loaded_view_sha256",
            "equivalent",
        },
        "checkpoint",
    )
    return SimulationCheckpoint(
        after_step=_integer(data["after_step"], "checkpoint.after_step"),
        before_state_sha256=_sha256(
            data["before_state_sha256"], "checkpoint.before_state_sha256"
        ),
        loaded_state_sha256=_sha256(
            data["loaded_state_sha256"], "checkpoint.loaded_state_sha256"
        ),
        before_view_sha256=_sha256(
            data["before_view_sha256"], "checkpoint.before_view_sha256"
        ),
        loaded_view_sha256=_sha256(
            data["loaded_view_sha256"], "checkpoint.loaded_view_sha256"
        ),
        equivalent=_boolean(data["equivalent"], "checkpoint.equivalent"),
    )


def _preview_document(preview: PreviewBuild) -> dict[str, object]:
    from lore2mud.authoring.serialization import preview_to_document

    return preview_to_document(preview)


def _rejected(
    operation: str, diagnostics: tuple[AuthoringDiagnostic, ...]
) -> AuthoringResult[SimulationReport]:
    return AuthoringResult(
        format_version=1,
        operation=operation,
        status=AuthoringStatus.REJECTED,
        artifact=None,
        diagnostics=diagnostics,
        exit_code=1,
    )


def _diagnostic(
    artifact_id: str,
    code: str,
    pointer: str,
    message: str,
    remediation: str,
    *,
    stage: AuthoringStage = AuthoringStage.SIMULATION,
) -> AuthoringDiagnostic:
    return AuthoringDiagnostic(
        stage=stage,
        code=code,
        severity=DiagnosticSeverity.ERROR,
        artifact_id=artifact_id,
        json_pointer=pointer,
        source_span=None,
        message=message,
        remediation=remediation,
    )


def _object(value: object, location: str) -> dict[str, object]:
    if type(value) is not dict:
        raise SimulationValidationError((f"{location} must be an object",))
    return cast(dict[str, object], value)


def _exact_keys(data: dict[str, object], expected: set[str], location: str) -> None:
    if set(data) != expected:
        raise SimulationValidationError((f"{location} fields are invalid",))


def _list(value: object, location: str, *, maximum: int) -> list[object]:
    if type(value) is not list or len(cast(list[object], value)) > maximum:
        raise SimulationValidationError((f"{location} must be a bounded array",))
    return cast(list[object], value)


def _text(value: object, location: str, *, maximum: int) -> str:
    if type(value) is not str or not value.strip() or len(value) > maximum:
        raise SimulationValidationError((f"{location} must be a bounded non-blank string",))
    try:
        validate_unicode_scalars(value)
    except InvalidUnicodeScalarError:
        raise SimulationValidationError((f"{location} contains an invalid Unicode surrogate",)) from None
    return value


def _stable_id(value: object, location: str) -> str:
    text = _text(value, location, maximum=64)
    if _STABLE_ID.fullmatch(text) is None:
        raise SimulationValidationError((f"{location} must be a stable ID",))
    return text


def _sha256(value: object, location: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise SimulationValidationError((f"{location} must be a lowercase SHA-256",))
    return value


def _integer(value: object, location: str) -> int:
    if type(value) is not int:
        raise SimulationValidationError((f"{location} must be an integer",))
    return value


def _bounded_integer(value: object, location: str) -> int:
    number = _integer(value, location)
    if number < -(2**63) or number > 2**63 - 1:
        raise SimulationValidationError((f"{location} is outside the signed 64-bit range",))
    return number


def _boolean(value: object, location: str) -> bool:
    if type(value) is not bool:
        raise SimulationValidationError((f"{location} must be a boolean",))
    return value


def _enum(enum_type, value: object, location: str):
    if type(value) is not str:
        raise SimulationValidationError((f"{location} is invalid",))
    try:
        return enum_type(value)
    except ValueError:
        raise SimulationValidationError((f"{location} is invalid",)) from None
