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
    GameEvent,
    GameEventKind,
    GameIntent,
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
    CAPABILITY_REPORT_IDENTITY_SCOPE,
    REPORT_IDENTITY_SCOPE,
    AuthoringDiagnostic,
    AuthoringResult,
    AuthoringStage,
    AuthoringStatus,
    CapabilityAuthoringResult,
    CapabilityPreview,
    CapabilitySimulationCheckpoint,
    CapabilitySimulationReport,
    CapabilitySimulationRequest,
    CapabilitySimulationTurn,
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
    PreviewArtifact,
    PreviewValidationError,
    build_preview,
    load_capability_preview_document,
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
    capability_preview_to_document,
    capability_simulation_report_to_document,
    capability_simulation_request_to_document,
    fingerprint_document,
    game_intent_from_document,
    normalize_bounded_json_document,
    simulation_report_to_document,
    simulation_request_to_document,
    typed_value_to_document,
    validate_unicode_scalars,
)
from lore2mud.capabilities.contracts import CapabilityIntent
from lore2mud.capabilities.persistence import (
    create_capability_checkpoint,
    restore_capability_checkpoint,
)
from lore2mud.capabilities.reference import engine_capability_catalog
from lore2mud.capabilities.runtime import CapabilityRuntimeError, CapabilityRuntimeHost
from lore2mud.capabilities.serialization import (
    canonical_json_object,
    fingerprint_capability_value,
)
from lore2mud.content.loader import ContentValidationError
from lore2mud.engine.save import SaveLoadError, SaveLoadService


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


@dataclass(frozen=True, slots=True)
class _CapabilityTraceRun:
    initial_view: GameView
    final_view: GameView
    initial_state_sha256: str
    final_state_sha256: str
    turns: tuple[CapabilitySimulationTurn, ...]
    events: tuple[GameEvent, ...]


SimulationArtifact = SimulationReport | CapabilitySimulationReport
SimulationResult = (
    AuthoringResult[SimulationReport]
    | CapabilityAuthoringResult[CapabilitySimulationReport]
)


def simulate_project(
    project: GameProject,
    request: SimulationRequest | CapabilitySimulationRequest,
) -> SimulationResult:
    """Build and simulate from a project without bypassing capability resolution."""
    resource_rejection = _preflight_simulation_request_resources(request)
    if resource_rejection is not None:
        if type(request) is CapabilitySimulationRequest:
            return _capability_rejected("simulate", resource_rejection.diagnostics)
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
        if isinstance(preview_result, CapabilityAuthoringResult):
            return _capability_rejected("simulate", preview_result.diagnostics)
        return _rejected("simulate", preview_result.diagnostics)
    preview = preview_result.artifact
    assert preview is not None
    if type(preview) is CapabilityPreview:
        if type(request) is not CapabilitySimulationRequest:
            return _capability_rejected(
                "simulate",
                (
                    _diagnostic(
                        preview.base_preview.project_id,
                        "simulation_request_invalid",
                        "/request",
                        "A capability preview requires CapabilitySimulationRequest v1.",
                        "Use the mixed steps request shape for a capability project.",
                    ),
                ),
            )
        return _simulate_capability_preview(preview, request)
    assert isinstance(preview, PreviewBuild)
    if type(request) is not SimulationRequest:
        return _rejected(
            "simulate",
            (
                _diagnostic(
                    preview.project_id,
                    "simulation_request_invalid",
                    "/request",
                    "The simulation request is invalid.",
                    "Use SimulationRequest v1 for a project without capabilities.",
                ),
            ),
        )
    return _simulate_legacy_preview(preview, request)


def simulate_preview(
    preview: PreviewArtifact,
    request: SimulationRequest | CapabilitySimulationRequest,
) -> SimulationResult:
    """Dispatch isolated simulation by the public preview and request lane."""
    if type(preview) is CapabilityPreview:
        if type(request) is not CapabilitySimulationRequest:
            return _capability_rejected(
                "simulate",
                (
                    _diagnostic(
                        preview.base_preview.project_id,
                        "simulation_request_invalid",
                        "/request",
                        "A capability preview requires CapabilitySimulationRequest v1.",
                        "Use the mixed steps request shape for a capability project.",
                    ),
                ),
            )
        return _simulate_capability_preview(preview, request)
    if type(preview) is not PreviewBuild:
        return _rejected(
            "simulate",
            (
                _diagnostic(
                    "preview",
                    "simulation_preview_invalid",
                    "/preview",
                    "The preview is invalid.",
                    "Rebuild the preview from a valid public-safe project.",
                ),
            ),
        )
    if type(request) is not SimulationRequest:
        return _rejected(
            "simulate",
            (
                _diagnostic(
                    preview.project_id,
                    "simulation_request_invalid",
                    "/request",
                    "The simulation request is invalid.",
                    "Use SimulationRequest v1 for a project without capabilities.",
                ),
            ),
        )
    return _simulate_legacy_preview(preview, request)


def _simulate_legacy_preview(
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
        if type(validated_preview) is not PreviewBuild:
            raise SimulationValidationError(
                ("preview is not a typed PreviewBuild v1",)
            )
        validated_request = validate_simulation_request(request)
        if type(validated_request) is not SimulationRequest:
            raise SimulationValidationError(
                ("request is not a typed SimulationRequest v1",)
            )
        normalized_request = validated_request
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


def _simulate_capability_preview(
    preview: CapabilityPreview,
    request: CapabilitySimulationRequest,
) -> CapabilityAuthoringResult[CapabilitySimulationReport]:
    """Run one mixed-intent capability witness in isolated sessions."""
    resource_rejection = _preflight_simulation_request_resources(request)
    if resource_rejection is not None:
        return _capability_rejected("simulate", resource_rejection.diagnostics)
    try:
        validated_preview = load_capability_preview_document(
            capability_preview_to_document(preview)
        )
        validated_request = validate_simulation_request(request)
        if type(validated_request) is not CapabilitySimulationRequest:
            raise SimulationValidationError(
                ("request is not a typed CapabilitySimulationRequest v1",)
            )
        witness = _run_capability_trace(validated_preview, validated_request)
        replay = _run_capability_trace(validated_preview, validated_request)
        checkpoints = tuple(
            _capability_checkpoint(validated_preview, validated_request, after_step)
            for after_step in validated_request.checkpoint_after_steps
        )
        legacy_request = _legacy_request_from_capability_request(validated_request)
        base_result = _simulate_legacy_preview(
            validated_preview.base_preview,
            legacy_request,
        )
        if not base_result.ok or base_result.artifact is None:
            return _capability_rejected("simulate", base_result.diagnostics)
        base_report = base_result.artifact
    except _SimulationRequestNormalizationError as exc:
        return _capability_rejected(
            "simulate", _simulation_request_resource_rejection(exc.code).diagnostics
        )
    except InvalidUnicodeScalarError:
        return _capability_rejected(
            "simulate", _simulation_request_unicode_rejection().diagnostics
        )
    except SimulationValidationError:
        return _capability_rejected(
            "simulate",
            (
                _diagnostic(
                    preview.base_preview.project_id,
                    "simulation_request_invalid",
                    "/",
                    "The capability simulation request is invalid.",
                    "Correct the bounded mixed request and retry.",
                ),
            ),
        )
    except (PreviewValidationError, ContentValidationError, OSError, BoundedJsonError):
        return _capability_rejected(
            "simulate",
            (
                _diagnostic(
                    preview.base_preview.project_id,
                    "simulation_preview_invalid",
                    "/preview",
                    "The capability preview could not be loaded in an isolated session.",
                    "Rebuild the preview from a valid public-safe project.",
                ),
            ),
        )
    except (CapabilityRuntimeError, SaveLoadError, _SimulationExecutionError):
        return _capability_rejected(
            "simulate",
            (
                _diagnostic(
                    preview.base_preview.project_id,
                    "simulation_evidence_failed",
                    "/",
                    "The isolated capability simulation could not produce complete evidence.",
                    "Correct the request or capability inputs and retry.",
                ),
            ),
        )

    capability_event_sha256 = _capability_event_hash(witness.events)
    capability_view_sha256 = _capability_view_hash(witness.final_view)
    replay_verified = (
        witness.turns == replay.turns
        and witness.initial_state_sha256 == replay.initial_state_sha256
        and witness.final_state_sha256 == replay.final_state_sha256
        and _capability_event_hash(witness.events) == _capability_event_hash(replay.events)
        and _capability_view_hash(witness.initial_view)
        == _capability_view_hash(replay.initial_view)
        and capability_view_sha256 == _capability_view_hash(replay.final_view)
        and base_report.replay_verified
    )
    report_without_fingerprint = CapabilitySimulationReport(
        format_version=1,
        project_id=validated_preview.base_preview.project_id,
        base_report=base_report,
        request_sha256=fingerprint_document(
            capability_simulation_request_to_document(validated_request)
        ),
        capability_preview_fingerprint=validated_preview.fingerprint,
        plan_sha256=validated_preview.plan_sha256,
        initial_capability_state_sha256=witness.initial_state_sha256,
        final_capability_state_sha256=witness.final_state_sha256,
        turns=witness.turns,
        witness_trace=witness.turns,
        capability_event_sha256=capability_event_sha256,
        capability_view_sha256=capability_view_sha256,
        replay_verified=replay_verified,
        checkpoints=checkpoints,
        fingerprint="",
    )
    report = CapabilitySimulationReport(
        format_version=report_without_fingerprint.format_version,
        project_id=report_without_fingerprint.project_id,
        base_report=report_without_fingerprint.base_report,
        request_sha256=report_without_fingerprint.request_sha256,
        capability_preview_fingerprint=report_without_fingerprint.capability_preview_fingerprint,
        plan_sha256=report_without_fingerprint.plan_sha256,
        initial_capability_state_sha256=report_without_fingerprint.initial_capability_state_sha256,
        final_capability_state_sha256=report_without_fingerprint.final_capability_state_sha256,
        turns=report_without_fingerprint.turns,
        witness_trace=report_without_fingerprint.witness_trace,
        capability_event_sha256=report_without_fingerprint.capability_event_sha256,
        capability_view_sha256=report_without_fingerprint.capability_view_sha256,
        replay_verified=report_without_fingerprint.replay_verified,
        checkpoints=report_without_fingerprint.checkpoints,
        fingerprint=fingerprint_document(
            capability_simulation_report_to_document(
                report_without_fingerprint,
                include_fingerprint=False,
            )
        ),
    )
    return _capability_success("simulate", report)


def replay_report(
    project: GameProject,
    report: SimulationReport | CapabilitySimulationReport,
) -> SimulationResult:
    """Replay either the legacy witness or the capability witness envelope."""
    if type(report) is CapabilitySimulationReport:
        preview_result = build_preview(project)
        if not preview_result.ok or preview_result.artifact is None:
            if isinstance(preview_result, CapabilityAuthoringResult):
                return _capability_rejected("replay", preview_result.diagnostics)
            return _rejected("replay", preview_result.diagnostics)
        if type(preview_result.artifact) is not CapabilityPreview:
            return _rejected(
                "replay",
                (
                    _diagnostic(
                        project.project_id,
                        "simulation_report_project_mismatch",
                        "/report/preview_fingerprint",
                        "The capability report does not belong to a capability preview.",
                        "Replay the report against the exact capability project.",
                    ),
                ),
            )
        return _replay_capability_preview(
            project,
            preview_result.artifact,
            report,
        )

    assert isinstance(report, SimulationReport)
    preview_result = build_preview(project)
    if preview_result.ok and type(preview_result.artifact) is CapabilityPreview:
        return _capability_rejected(
            "replay",
            (
                _diagnostic(
                    project.project_id,
                    "simulation_report_invalid",
                    "/report",
                    "A capability project requires CapabilitySimulationReport v1.",
                    "Replay the capability report emitted by the simulation service.",
                ),
            ),
        )
    return _replay_legacy_report(project, report)


def _replay_legacy_report(
    project: GameProject, report: SimulationReport
) -> AuthoringResult[SimulationReport]:
    """Re-run a report witness in fresh sessions and require byte-equivalent evidence."""
    preview_result = build_preview(project)
    if not preview_result.ok:
        return _rejected("replay", preview_result.diagnostics)
    preview = preview_result.artifact
    assert preview is not None
    if type(preview) is not PreviewBuild:
        return _rejected(
            "replay",
            (
                _diagnostic(
                    project.project_id,
                    "simulation_report_invalid",
                    "/report",
                    "A capability project requires CapabilitySimulationReport v1.",
                    "Replay the capability report emitted by the simulation service.",
                ),
            ),
        )
    assert isinstance(preview, PreviewBuild)
    try:
        validated_report = validate_simulation_report(report)
        if type(validated_report) is not SimulationReport:
            raise SimulationValidationError(
                ("report is not a typed SimulationReport v1",)
            )
        expected = validated_report
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
    replayed = _simulate_legacy_preview(preview, request)
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


def _replay_capability_preview(
    project: GameProject,
    preview: CapabilityPreview,
    report: CapabilitySimulationReport,
) -> CapabilityAuthoringResult[CapabilitySimulationReport]:
    try:
        expected = validate_simulation_report(report)
        if type(expected) is not CapabilitySimulationReport:
            raise SimulationValidationError(
                ("report is not a typed CapabilitySimulationReport v1",)
            )
    except SimulationValidationError:
        return _capability_rejected(
            "replay",
            (
                _diagnostic(
                    project.project_id,
                    "simulation_report_invalid",
                    "/report",
                    "The capability simulation report is invalid.",
                    "Provide an intact CapabilitySimulationReport v1.",
                ),
            ),
        )

    if (
        expected.project_id != preview.base_preview.project_id
        or expected.capability_preview_fingerprint != preview.fingerprint
        or expected.plan_sha256 != preview.plan_sha256
    ):
        return _capability_rejected(
            "replay",
            (
                _diagnostic(
                    project.project_id,
                    "simulation_report_project_mismatch",
                    "/report/capability_preview_fingerprint",
                    "The capability report does not belong to this project preview.",
                    "Replay the report against the exact project that produced it.",
                ),
            ),
        )

    request = CapabilitySimulationRequest(
        format_version=1,
        seed=expected.base_report.seed,
        clock=expected.base_report.clock,
        player_name=expected.base_report.player_name,
        steps=tuple(turn.step for turn in expected.witness_trace),
        conditions=tuple(
            condition.condition for condition in expected.base_report.condition_results
        ),
        checkpoint_after_steps=tuple(
            checkpoint.after_step for checkpoint in expected.checkpoints
        ),
    )
    replayed = _simulate_capability_preview(preview, request)
    if not replayed.ok or replayed.artifact is None:
        return _capability_rejected("replay", replayed.diagnostics)
    if capability_simulation_report_to_document(replayed.artifact) != (
        capability_simulation_report_to_document(expected)
    ):
        return _capability_rejected(
            "replay",
            (
                _diagnostic(
                    project.project_id,
                    "simulation_replay_mismatch",
                    "/report/witness_trace",
                    "Fresh capability replay evidence differs from the supplied report.",
                    "Regenerate the report from the exact preview and request inputs.",
                ),
            ),
        )
    return _capability_success("replay", replayed.artifact)


def load_simulation_request(
    path: Path,
) -> SimulationRequest | CapabilitySimulationRequest:
    return load_simulation_request_document(read_authoring_json(path))


def load_simulation_request_document(
    document: object,
) -> SimulationRequest | CapabilitySimulationRequest:
    if type(document) is dict and "steps" in cast(dict[object, object], document):
        return load_capability_simulation_request_document(document)
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


def load_capability_simulation_request_document(
    document: object,
) -> CapabilitySimulationRequest:
    data = _object(document, "request")
    _exact_keys(
        data,
        {
            "format_version",
            "seed",
            "clock",
            "player_name",
            "steps",
            "conditions",
            "checkpoint_after_steps",
        },
        "request",
    )
    if _integer(data["format_version"], "request.format_version") != 1:
        raise SimulationValidationError(("request.format_version must be 1",))
    steps = tuple(
        _load_capability_step(item)
        for item in _list(data["steps"], "request.steps", maximum=_MAX_INTENTS)
    )
    conditions = tuple(
        sorted(
            (
                _load_condition(item)
                for item in _list(
                    data["conditions"],
                    "request.conditions",
                    maximum=_MAX_CONDITIONS,
                )
            ),
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
        value < 0 or value > len(steps) for value in checkpoints
    ):
        raise SimulationValidationError(("request checkpoint steps are invalid",))
    return CapabilitySimulationRequest(
        format_version=1,
        seed=_bounded_integer(data["seed"], "request.seed"),
        clock=_bounded_integer(data["clock"], "request.clock"),
        player_name=_text(data["player_name"], "request.player_name", maximum=128),
        steps=steps,
        conditions=conditions,
        checkpoint_after_steps=checkpoints,
    )


def _normalize_simulation_request_document(
    request: SimulationRequest | CapabilitySimulationRequest,
) -> object:
    try:
        if type(request) is SimulationRequest:
            document = simulation_request_to_document(request)
        elif type(request) is CapabilitySimulationRequest:
            document = capability_simulation_request_to_document(request)
        else:
            raise SimulationValidationError(
                ("request is not a typed simulation request v1",)
            )
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
    request: SimulationRequest | CapabilitySimulationRequest,
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


def validate_simulation_request(
    request: SimulationRequest | CapabilitySimulationRequest,
) -> SimulationRequest | CapabilitySimulationRequest:
    normalized_document = _normalize_simulation_request_document(request)
    return load_simulation_request_document(normalized_document)


def load_simulation_report(
    path: Path,
) -> SimulationReport | CapabilitySimulationReport:
    return load_simulation_report_document(read_authoring_json(path))


def validate_simulation_report(
    report: SimulationReport | CapabilitySimulationReport,
) -> SimulationReport | CapabilitySimulationReport:
    if type(report) is CapabilitySimulationReport:
        try:
            document = capability_simulation_report_to_document(report)
        except (AttributeError, RecursionError, TypeError, ValueError):
            raise SimulationValidationError(
                ("report is not a valid typed report",)
            ) from None
        return load_capability_simulation_report_document(
            normalize_bounded_json_document(document)
        )
    elif type(report) is SimulationReport:
        try:
            document = simulation_report_to_document(report)
        except (AttributeError, RecursionError, TypeError, ValueError):
            raise SimulationValidationError(
                ("report is not a valid typed report",)
            ) from None
        loaded = load_simulation_report_document(
            normalize_bounded_json_document(document)
        )
        if type(loaded) is not SimulationReport:
            raise SimulationValidationError(
                ("report is not a typed SimulationReport v1",)
            )
        return loaded
    else:
        raise SimulationValidationError(("report is not a typed simulation report v1",))


def load_simulation_report_document(
    document: object,
) -> SimulationReport | CapabilitySimulationReport:
    if type(document) is dict and "base_report" in cast(dict[object, object], document):
        return load_capability_simulation_report_document(document)
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


def load_capability_simulation_report_document(
    document: object,
) -> CapabilitySimulationReport:
    """Load and validate a capability report envelope and its legacy witness."""
    data = _object(document, "capability_report")
    _exact_keys(
        data,
        {
            "format_version",
            "project_id",
            "base_report",
            "request_sha256",
            "capability_preview_fingerprint",
            "plan_sha256",
            "initial_capability_state_sha256",
            "final_capability_state_sha256",
            "turns",
            "witness_trace",
            "capability_event_sha256",
            "capability_view_sha256",
            "replay_verified",
            "checkpoints",
            "identity_scope",
            "fingerprint",
        },
        "capability_report",
    )
    if _integer(data["format_version"], "capability_report.format_version") != 1:
        raise SimulationValidationError(("capability_report.format_version must be 1",))
    if data["identity_scope"] != CAPABILITY_REPORT_IDENTITY_SCOPE:
        raise SimulationValidationError(("capability_report.identity_scope is invalid",))

    # The embedded report is deliberately parsed through the legacy loader so
    # its identity scope and canonical fingerprint remain independently sealed.
    base_report_document = data["base_report"]
    base_report = load_simulation_report_document(base_report_document)
    if type(base_report) is not SimulationReport:
        raise SimulationValidationError(("capability_report.base_report is invalid",))
    project_id = _stable_id(data["project_id"], "capability_report.project_id")
    if base_report.project_id != project_id:
        raise SimulationValidationError(
            ("capability_report.project_id does not match base_report",)
        )

    turns = tuple(
        _load_capability_turn(item)
        for item in _list(
            data["turns"], "capability_report.turns", maximum=_MAX_INTENTS
        )
    )
    witness = tuple(
        _load_capability_turn(item)
        for item in _list(
            data["witness_trace"],
            "capability_report.witness_trace",
            maximum=_MAX_INTENTS,
        )
    )
    if turns != witness:
        raise SimulationValidationError(
            ("capability_report witness trace is inconsistent",)
        )
    indexes = tuple(turn.index for turn in turns)
    zero_based = tuple(range(len(turns)))
    one_based = tuple(range(1, len(turns) + 1))
    if indexes not in {zero_based, one_based}:
        raise SimulationValidationError(("capability_report turn indexes are invalid",))
    legacy_turns = tuple(turn for turn in turns if isinstance(turn.step, GameIntent))
    if tuple(turn.step for turn in legacy_turns) != tuple(
        turn.intent for turn in base_report.turns
    ):
        raise SimulationValidationError(
            ("capability_report.base_report is not the filtered legacy subsequence",)
        )
    # A capability witness carries the same deterministic legacy subsequence;
    # reject impossible checkpoint/turn indexes before any replay can consume it.
    checkpoints = tuple(
        _load_capability_checkpoint(item)
        for item in _list(
            data["checkpoints"],
            "capability_report.checkpoints",
            maximum=_MAX_INTENTS + 1,
        )
    )
    if any(
        item.after_step < 0 or item.after_step > len(turns) for item in checkpoints
    ):
        raise SimulationValidationError(
            ("capability_report checkpoint steps are invalid",)
        )
    checkpoint_steps = tuple(item.after_step for item in checkpoints)
    if checkpoint_steps != tuple(sorted(set(checkpoint_steps))):
        raise SimulationValidationError(
            ("capability_report checkpoints are not in canonical order",)
        )
    replay_verified = _boolean(
        data["replay_verified"], "capability_report.replay_verified"
    )
    report = CapabilitySimulationReport(
        format_version=1,
        project_id=project_id,
        base_report=base_report,
        request_sha256=_sha256(
            data["request_sha256"], "capability_report.request_sha256"
        ),
        capability_preview_fingerprint=_sha256(
            data["capability_preview_fingerprint"],
            "capability_report.capability_preview_fingerprint",
        ),
        plan_sha256=_sha256(data["plan_sha256"], "capability_report.plan_sha256"),
        initial_capability_state_sha256=_sha256(
            data["initial_capability_state_sha256"],
            "capability_report.initial_capability_state_sha256",
        ),
        final_capability_state_sha256=_sha256(
            data["final_capability_state_sha256"],
            "capability_report.final_capability_state_sha256",
        ),
        turns=turns,
        witness_trace=witness,
        capability_event_sha256=_sha256(
            data["capability_event_sha256"],
            "capability_report.capability_event_sha256",
        ),
        capability_view_sha256=_sha256(
            data["capability_view_sha256"],
            "capability_report.capability_view_sha256",
        ),
        replay_verified=replay_verified,
        checkpoints=checkpoints,
        fingerprint=_sha256(data["fingerprint"], "capability_report.fingerprint"),
    )
    expected_fingerprint = fingerprint_document(
        capability_simulation_report_to_document(report, include_fingerprint=False)
    )
    if report.fingerprint != expected_fingerprint:
        raise SimulationValidationError(
            ("capability_report.fingerprint does not match canonical bytes",)
        )
    return report


def _run_capability_trace(
    preview: CapabilityPreview,
    request: CapabilitySimulationRequest,
) -> _CapabilityTraceRun:
    with _isolated_capability_session(preview, request) as (session, _pack, _service):
        initial_view = session.view()
        initial_state_sha256 = _capability_state_hash(session)
        final_view = initial_view
        turns: list[CapabilitySimulationTurn] = []
        events: list[GameEvent] = []
        for index, step in enumerate(request.steps, 1):
            result = session.submit(step)
            final_view = result.view
            events.extend(result.events)
            turns.append(
                CapabilitySimulationTurn(
                    index=index,
                    step=step,
                    status=result.status.value,
                    rejection_code=(
                        None if result.rejection is None else result.rejection.code.value
                    ),
                    event_sha256=_capability_event_hash(result.events),
                    view_sha256=_full_capability_view_hash(result.view),
                    capability_state_sha256=_capability_state_hash(session),
                    event_sequence_after=session.event_sequence,
                )
            )
        return _CapabilityTraceRun(
            initial_view=initial_view,
            final_view=final_view,
            initial_state_sha256=initial_state_sha256,
            final_state_sha256=_capability_state_hash(session),
            turns=tuple(turns),
            events=tuple(events),
        )


def _capability_checkpoint(
    preview: CapabilityPreview,
    request: CapabilitySimulationRequest,
    after_step: int,
) -> CapabilitySimulationCheckpoint:
    with _isolated_capability_session(preview, request) as (session, pack, _service):
        _submit_capability_prefix(session, request, after_step)
        checkpoint = create_capability_checkpoint(session, pack)
        restore_capability_checkpoint(session, pack, checkpoint)
        restored_state_sha256 = _capability_state_hash(session)
        restored_view_sha256 = _full_capability_view_hash(session.view())
        equivalent = (
            checkpoint.state_sha256 == restored_state_sha256
            and checkpoint.view_sha256 == restored_view_sha256
            and checkpoint.event_sequence == session.event_sequence
        )
        return CapabilitySimulationCheckpoint(
            after_step=after_step,
            checkpoint_sha256=checkpoint.fingerprint,
            restored_state_sha256=restored_state_sha256,
            restored_view_sha256=restored_view_sha256,
            restored_event_sequence=session.event_sequence,
            equivalent=equivalent,
        )


@contextmanager
def _isolated_capability_session(
    preview: CapabilityPreview,
    request: CapabilitySimulationRequest,
):
    with materialized_preview_pack(preview) as pack:
        with tempfile.TemporaryDirectory(
            prefix="lore2mud-v2-capability-simulation-save-"
        ) as save_dir:
            service = SaveLoadService(pack, Path(save_dir))
            catalog = engine_capability_catalog()
            host = CapabilityRuntimeHost(
                preview.resolved_plan,
                catalog.implementation_registry,
                states=preview.initial_states,
            )
            context = DeterminismContext(seed=request.seed, clock=request.clock)
            session = GameSession.from_content_pack(
                pack,
                service,
                player_name=request.player_name,
                determinism=context,
                capability_host=host,
            )
            yield session, pack, service


def _submit_capability_prefix(
    session: GameSession,
    request: CapabilitySimulationRequest,
    length: int,
) -> None:
    for step in request.steps[:length]:
        session.submit(step)


def _legacy_request_from_capability_request(
    request: CapabilitySimulationRequest,
) -> SimulationRequest:
    return SimulationRequest(
        format_version=1,
        seed=request.seed,
        clock=request.clock,
        player_name=request.player_name,
        intents=tuple(step for step in request.steps if isinstance(step, GameIntent)),
        conditions=request.conditions,
        checkpoint_after_steps=(),
    )


def _capability_state_hash(session: GameSession) -> str:
    host = session.capability_host
    if not isinstance(host, CapabilityRuntimeHost):
        raise _SimulationExecutionError("capability runtime host is unavailable")
    return fingerprint_capability_value(host.states)


def _capability_event_hash(events: tuple[GameEvent, ...]) -> str:
    return fingerprint_capability_value(
        tuple(event for event in events if event.kind is GameEventKind.CAPABILITY)
    )


def _capability_view_hash(view: GameView) -> str:
    return fingerprint_capability_value(view.capabilities)


def _full_capability_view_hash(view: GameView) -> str:
    return fingerprint_capability_value(view)


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


def _load_capability_step(value: object):
    data = _object(value, "step")
    if "type" in data:
        try:
            return game_intent_from_document(data)
        except (TypeError, ValueError):
            raise SimulationValidationError(("step contains an invalid intent",)) from None
    _exact_keys(
        data,
        {"capability_id", "action_id", "parameters"},
        "step",
    )
    try:
        parameters = canonical_json_object(data["parameters"])
    except (TypeError, ValueError):
        raise SimulationValidationError(
            ("step.parameters must be a bounded canonical JSON object",)
        ) from None
    return CapabilityIntent(
        capability_id=_stable_id(data["capability_id"], "step.capability_id"),
        action_id=_stable_id(data["action_id"], "step.action_id"),
        parameters=parameters,
    )


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


def _load_capability_turn(value: object) -> CapabilitySimulationTurn:
    data = _object(value, "capability_turn")
    _exact_keys(
        data,
        {
            "index",
            "step",
            "status",
            "rejection_code",
            "event_sha256",
            "view_sha256",
            "capability_state_sha256",
            "event_sequence_after",
        },
        "capability_turn",
    )
    step = _load_capability_step(data["step"])
    status = _enum(TurnStatus, data["status"], "capability_turn.status")
    rejection_code: str | None
    if data["rejection_code"] is None:
        rejection_code = None
    else:
        rejection_code = _enum(
            RejectionCode,
            data["rejection_code"],
            "capability_turn.rejection_code",
        ).value
    if (status is TurnStatus.ACCEPTED) != (rejection_code is None):
        raise SimulationValidationError(
            ("capability_turn rejection fields are inconsistent",)
        )
    event_sequence_after = _integer(
        data["event_sequence_after"], "capability_turn.event_sequence_after"
    )
    if event_sequence_after < 0:
        raise SimulationValidationError(
            ("capability_turn.event_sequence_after must be non-negative",)
        )
    return CapabilitySimulationTurn(
        index=_integer(data["index"], "capability_turn.index"),
        step=step,
        status=status.value,
        rejection_code=rejection_code,
        event_sha256=_sha256(
            data["event_sha256"], "capability_turn.event_sha256"
        ),
        view_sha256=_sha256(data["view_sha256"], "capability_turn.view_sha256"),
        capability_state_sha256=_sha256(
            data["capability_state_sha256"],
            "capability_turn.capability_state_sha256",
        ),
        event_sequence_after=event_sequence_after,
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


def _load_capability_checkpoint(value: object) -> CapabilitySimulationCheckpoint:
    data = _object(value, "capability_checkpoint")
    _exact_keys(
        data,
        {
            "after_step",
            "checkpoint_sha256",
            "restored_state_sha256",
            "restored_view_sha256",
            "restored_event_sequence",
            "equivalent",
        },
        "capability_checkpoint",
    )
    restored_event_sequence = _integer(
        data["restored_event_sequence"],
        "capability_checkpoint.restored_event_sequence",
    )
    if restored_event_sequence < 0:
        raise SimulationValidationError(
            ("capability_checkpoint.restored_event_sequence must be non-negative",)
        )
    return CapabilitySimulationCheckpoint(
        after_step=_integer(data["after_step"], "capability_checkpoint.after_step"),
        checkpoint_sha256=_sha256(
            data["checkpoint_sha256"], "capability_checkpoint.checkpoint_sha256"
        ),
        restored_state_sha256=_sha256(
            data["restored_state_sha256"],
            "capability_checkpoint.restored_state_sha256",
        ),
        restored_view_sha256=_sha256(
            data["restored_view_sha256"],
            "capability_checkpoint.restored_view_sha256",
        ),
        restored_event_sequence=restored_event_sequence,
        equivalent=_boolean(
            data["equivalent"], "capability_checkpoint.equivalent"
        ),
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


def _capability_success(
    operation: str,
    artifact: CapabilitySimulationReport,
) -> CapabilityAuthoringResult[CapabilitySimulationReport]:
    return CapabilityAuthoringResult(
        format_version=1,
        operation=operation,
        status=AuthoringStatus.SUCCESS,
        artifact=artifact,
        diagnostics=(),
        exit_code=0,
    )


def _capability_rejected(
    operation: str,
    diagnostics: tuple[AuthoringDiagnostic, ...],
) -> CapabilityAuthoringResult[CapabilitySimulationReport]:
    return CapabilityAuthoringResult(
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
