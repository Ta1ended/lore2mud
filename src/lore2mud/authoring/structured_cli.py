"""Structured JSON command adapter for the shared V2-2/V2-3 service."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import sys
import tempfile
from typing import cast

from lore2mud._bounded_json import (
    BoundedJsonError,
    DEFAULT_JSON_READ_LIMITS,
    read_bounded_json,
)
from lore2mud.authoring.contracts import (
    AuthoringDiagnostic,
    AuthoringResult,
    AuthoringStage,
    AuthoringStatus,
    CapabilityAuthoringResult,
    CreatorDecision,
    DiagnosticSeverity,
    GameBlueprint,
    GameProject,
    PublicInputDescriptor,
    TraceRecord,
    WorkspaceMetadataEntry,
)
from lore2mud.authoring.sdk import AgentAuthoringSDK
from lore2mud.authoring.serialization import (
    authoring_result_to_document,
    canonical_json_bytes,
)
from lore2mud.authoring.simulation import (
    load_simulation_report_document as _load_simulation_report_document,
    load_simulation_request_document as _load_simulation_request_document,
)


_MAX_PROJECT_INPUT_ITEMS = 4_096
_MAX_TRACE_RECORDS = 8_192

CliAuthoringResult = AuthoringResult[object] | CapabilityAuthoringResult[object]


def add_author_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the ``author`` command family on the top-level parser."""
    author_parser = subparsers.add_parser(
        "author",
        help="Run the structured V2-2 authoring interface",
    )
    commands = author_parser.add_subparsers(
        dest="author_command",
        required=True,
    )

    create_parser = commands.add_parser(
        "create-project",
        help="Create a normalized GameProject v1",
    )
    create_parser.add_argument("--project-id", required=True)
    create_parser.add_argument("--blueprint", type=Path, required=True)
    create_parser.add_argument("--content", type=Path, required=True)
    create_parser.add_argument(
        "--project-inputs",
        type=Path,
        help="Optional typed public-input, decision, trace, and workspace metadata JSON",
    )
    _add_output_argument(create_parser)
    create_parser.set_defaults(func=run_author_command)

    validate_parser = commands.add_parser(
        "validate",
        help="Validate and normalize a GameProject v1",
    )
    validate_parser.add_argument("--project", type=Path, required=True)
    _add_output_argument(validate_parser)
    validate_parser.set_defaults(func=run_author_command)

    preview_parser = commands.add_parser(
        "preview",
        help="Build a fixed-profile, non-distributable preview",
    )
    preview_parser.add_argument("--project", type=Path, required=True)
    _add_output_argument(preview_parser)
    preview_parser.set_defaults(func=run_author_command)

    simulate_parser = commands.add_parser(
        "simulate",
        help="Run an isolated deterministic simulation",
    )
    simulate_parser.add_argument("--project", type=Path, required=True)
    simulate_parser.add_argument("--request", type=Path, required=True)
    _add_output_argument(simulate_parser)
    simulate_parser.set_defaults(func=run_author_command)

    replay_parser = commands.add_parser(
        "replay",
        help="Replay and verify a SimulationReport v1 witness",
    )
    replay_parser.add_argument("--project", type=Path, required=True)
    replay_parser.add_argument("--report", type=Path, required=True)
    _add_output_argument(replay_parser)
    replay_parser.set_defaults(func=run_author_command)

    proof_parser = commands.add_parser(
        "proof",
        help="Build a player-safe read-only proofing projection",
    )
    proof_parser.add_argument("--project", type=Path, required=True)
    _add_output_argument(proof_parser)
    proof_parser.set_defaults(func=run_author_command)

    provenance_parser = commands.add_parser(
        "validate-provenance",
        help="Validate a public-safe provenance and rights manifest",
    )
    provenance_parser.add_argument("--manifest", type=Path, required=True)
    _add_output_argument(provenance_parser)
    provenance_parser.set_defaults(func=run_author_command)

    anchor_parser = commands.add_parser(
        "validate-anchors",
        help="Validate explicit incremental anchor migrations",
    )
    anchor_parser.add_argument("--request", type=Path, required=True)
    _add_output_argument(anchor_parser)
    anchor_parser.set_defaults(func=run_author_command)

    seal_parser = commands.add_parser(
        "seal",
        help="Build one deterministic sealed GamePackage v2 candidate",
    )
    seal_parser.add_argument("--request", type=Path, required=True)
    _add_output_argument(seal_parser)
    seal_parser.set_defaults(func=run_author_command)


def run_author_command(args: argparse.Namespace) -> int:
    """Execute one parsed authoring command and emit one canonical result."""
    command = cast(str, args.author_command)
    if command == "create-project":
        result = _create_project(args)
        protected_inputs = tuple(
            path
            for path in (
                cast(Path, args.blueprint),
                cast(Path | None, args.project_inputs),
            )
            if path is not None
        )
        protected_directories = (cast(Path, args.content),)
    elif command == "validate":
        result = _validate_project(args)
        protected_inputs = (cast(Path, args.project),)
        protected_directories = ()
    elif command == "preview":
        result = _build_preview(args)
        protected_inputs = (cast(Path, args.project),)
        protected_directories = ()
    elif command == "simulate":
        result = _simulate(args)
        protected_inputs = (cast(Path, args.project), cast(Path, args.request))
        protected_directories = ()
    elif command == "replay":
        result = _replay(args)
        protected_inputs = (cast(Path, args.project), cast(Path, args.report))
        protected_directories = ()
    elif command == "proof":
        result = _proof(args)
        protected_inputs = (cast(Path, args.project),)
        protected_directories = ()
    elif command == "validate-provenance":
        result = _validate_provenance(args)
        protected_inputs = (cast(Path, args.manifest),)
        protected_directories = ()
    elif command == "validate-anchors":
        result = _validate_anchors(args)
        protected_inputs = (cast(Path, args.request),)
        protected_directories = ()
    elif command == "seal":
        result = _seal(args)
        protected_inputs = (cast(Path, args.request),)
        protected_directories = ()
    else:
        raise RuntimeError(f"unhandled authoring command: {command}")

    return _emit_result(
        result,
        output=cast(Path | None, getattr(args, "output", None)),
        protected_inputs=protected_inputs,
        protected_directories=protected_directories,
    )


def _add_output_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--output",
        type=Path,
        help="Atomically write the successful artifact as canonical JSON",
    )


def _create_project(args: argparse.Namespace) -> AuthoringResult[object]:
    document, rejected = _read_document(
        cast(Path, args.blueprint),
        operation="create_project",
        artifact_id="blueprint",
    )
    if rejected is not None:
        return rejected
    inputs = _ProjectInputs()
    inputs_path = cast(Path | None, args.project_inputs)
    if inputs_path is not None:
        inputs_document, rejected = _read_document(
            inputs_path,
            operation="create_project",
            artifact_id="project_inputs",
        )
        if rejected is not None:
            return rejected
        try:
            inputs = _project_inputs_from_document(inputs_document)
        except _ProjectInputsParseError as exc:
            return _input_validation_rejection(
                "create_project",
                AuthoringStage.SERIALIZATION,
                "project_inputs_invalid",
                "project_inputs",
                exc.message,
                "Correct the document to match the project-input transport contract.",
                json_pointer=exc.json_pointer,
            )
    sdk = AgentAuthoringSDK()
    blueprint_result = sdk.validate_blueprint_document(document)
    if not blueprint_result.ok or blueprint_result.artifact is None:
        return _retag_rejection(
            cast(AuthoringResult[object], blueprint_result),
            "create_project",
        )
    result = sdk.create_project(
        project_id=cast(str, args.project_id),
        blueprint=cast(GameBlueprint, blueprint_result.artifact),
        content_root=cast(Path, args.content),
        public_inputs=inputs.public_inputs,
        creator_decisions=inputs.creator_decisions,
        trace_records=inputs.trace_records,
        workspace_metadata=inputs.workspace_metadata,
    )
    return cast(AuthoringResult[object], result)


def _validate_project(args: argparse.Namespace) -> AuthoringResult[object]:
    document, rejected = _read_document(
        cast(Path, args.project),
        operation="validate_project",
        artifact_id="project",
    )
    if rejected is not None:
        return rejected
    return cast(
        AuthoringResult[object],
        AgentAuthoringSDK().validate_project_document(document),
    )


def _build_preview(args: argparse.Namespace) -> CliAuthoringResult:
    sdk, project, rejected = _load_project(
        cast(Path, args.project),
        operation="build_preview",
    )
    if rejected is not None:
        return rejected
    assert sdk is not None and project is not None
    return cast(CliAuthoringResult, sdk.build_preview(project))


def _simulate(args: argparse.Namespace) -> CliAuthoringResult:
    sdk, project, rejected = _load_project(
        cast(Path, args.project),
        operation="simulate",
    )
    if rejected is not None:
        return rejected
    assert sdk is not None and project is not None
    request_document, rejected = _read_document(
        cast(Path, args.request),
        operation="simulate",
        artifact_id="simulation_request",
    )
    if rejected is not None:
        return rejected
    try:
        request = _load_simulation_request_document(request_document)
    except (TypeError, ValueError):
        return _input_validation_rejection(
            "simulate",
            AuthoringStage.SIMULATION,
            "simulation_request_invalid",
            "simulation_request",
            "The simulation request is not a valid SimulationRequest v1 document.",
            "Correct the request fields and retry the simulation.",
        )
    return cast(CliAuthoringResult, sdk.simulate(project, request))


def _replay(args: argparse.Namespace) -> CliAuthoringResult:
    sdk, project, rejected = _load_project(
        cast(Path, args.project),
        operation="replay",
    )
    if rejected is not None:
        return rejected
    assert sdk is not None and project is not None
    report_document, rejected = _read_document(
        cast(Path, args.report),
        operation="replay",
        artifact_id="report",
    )
    if rejected is not None:
        return rejected
    try:
        report = _load_simulation_report_document(report_document)
    except (TypeError, ValueError):
        return _input_validation_rejection(
            "replay",
            AuthoringStage.SIMULATION,
            "simulation_report_invalid",
            "simulation_report",
            "The replay input is not a valid SimulationReport v1 document.",
            "Provide an unchanged report emitted by the simulation service.",
        )
    return cast(CliAuthoringResult, sdk.replay(project, report))


def _proof(args: argparse.Namespace) -> CliAuthoringResult:
    sdk, project, rejected = _load_project(
        cast(Path, args.project),
        operation="proof",
    )
    if rejected is not None:
        return rejected
    assert sdk is not None and project is not None
    return cast(CliAuthoringResult, sdk.proof(project))


def _validate_provenance(args: argparse.Namespace) -> CliAuthoringResult:
    document, rejected = _read_document(
        cast(Path, args.manifest),
        operation="validate_provenance",
        artifact_id="provenance",
        reject_duplicate_members=True,
    )
    if rejected is not None:
        return rejected
    return cast(CliAuthoringResult, AgentAuthoringSDK().validate_provenance_document(document))


def _validate_anchors(args: argparse.Namespace) -> CliAuthoringResult:
    document, rejected = _read_document(
        cast(Path, args.request),
        operation="validate_anchors",
        artifact_id="anchors",
        reject_duplicate_members=True,
    )
    if rejected is not None:
        return rejected
    return cast(
        CliAuthoringResult,
        AgentAuthoringSDK().validate_anchor_migrations_document(document),
    )


def _seal(args: argparse.Namespace) -> CliAuthoringResult:
    document, rejected = _read_document(
        cast(Path, args.request),
        operation="seal",
        artifact_id="seal_request",
        reject_duplicate_members=True,
    )
    if rejected is not None:
        return rejected
    return cast(CliAuthoringResult, AgentAuthoringSDK().seal_document(document))


def _load_project(
    path: Path,
    *,
    operation: str,
) -> tuple[
    AgentAuthoringSDK | None,
    GameProject | None,
    AuthoringResult[object] | None,
]:
    document, rejected = _read_document(
        path,
        operation=operation,
        artifact_id="project",
    )
    if rejected is not None:
        return None, None, rejected
    sdk = AgentAuthoringSDK()
    result = sdk.validate_project_document(document)
    if not result.ok or result.artifact is None:
        return (
            None,
            None,
            _retag_rejection(
                cast(AuthoringResult[object], result),
                operation,
            ),
        )
    return sdk, cast(GameProject, result.artifact), None


def _read_document(
    path: Path,
    *,
    operation: str,
    artifact_id: str,
    reject_duplicate_members: bool = False,
) -> tuple[object, AuthoringResult[object] | None]:
    try:
        return (
            read_bounded_json(
                path,
                DEFAULT_JSON_READ_LIMITS,
                reject_duplicate_members=reject_duplicate_members,
            ),
            None,
        )
    except BoundedJsonError as exc:
        return None, _input_validation_rejection(
            operation,
            AuthoringStage.SERIALIZATION,
            f"authoring_input_{exc.code.value}",
            artifact_id,
            "The authoring JSON input could not be read safely.",
            "Provide readable UTF-8 JSON within the documented resource limits.",
        )


def _retag_rejection(result: AuthoringResult[object], operation: str) -> AuthoringResult[object]:
    if not result.ok:
        return AuthoringResult(
            format_version=result.format_version,
            operation=operation,
            status=AuthoringStatus.REJECTED,
            artifact=None,
            diagnostics=result.diagnostics,
            exit_code=1,
        )
    return _input_validation_rejection(
        operation,
        AuthoringStage.SERIALIZATION,
        "authoring_service_result_invalid",
        "authoring_result",
        "The shared authoring service returned no artifact for a successful result.",
        "Retry with a valid service implementation.",
    )


def _input_validation_rejection(
    operation: str,
    stage: AuthoringStage,
    code: str,
    artifact_id: str,
    message: str,
    remediation: str,
    *,
    json_pointer: str = "/",
) -> AuthoringResult[object]:
    return AuthoringResult(
        format_version=1,
        operation=operation,
        status=AuthoringStatus.REJECTED,
        artifact=None,
        diagnostics=(
            AuthoringDiagnostic(
                stage=stage,
                code=code,
                severity=DiagnosticSeverity.ERROR,
                artifact_id=artifact_id,
                json_pointer=json_pointer,
                source_span=None,
                message=message,
                remediation=remediation,
            ),
        ),
        exit_code=1,
    )


def _emit_result(
    result: CliAuthoringResult,
    *,
    output: Path | None,
    protected_inputs: tuple[Path, ...],
    protected_directories: tuple[Path, ...],
) -> int:
    emitted = result
    if output is not None and result.ok and result.artifact is not None:
        if _aliases_input(output, protected_inputs, protected_directories):
            emitted = _input_validation_rejection(
                result.operation,
                AuthoringStage.SERIALIZATION,
                "artifact_output_aliases_input",
                "output",
                "The artifact output cannot replace an authoring input.",
                "Choose a distinct output path and retry.",
            )
        else:
            try:
                document = authoring_result_to_document(result)["artifact"]
                artifact_payload = canonical_json_bytes(document)
            except (TypeError, ValueError, UnicodeError):
                emitted = _result_serialization_rejection(result.operation)
            else:
                try:
                    _atomic_write(output, artifact_payload)
                except OSError:
                    emitted = _input_validation_rejection(
                        result.operation,
                        AuthoringStage.SERIALIZATION,
                        "artifact_output_io_error",
                        "output",
                        "The artifact output could not be written atomically.",
                        "Choose a writable output location and retry.",
                    )

    try:
        payload = canonical_json_bytes(authoring_result_to_document(emitted))
    except (TypeError, ValueError, UnicodeError):
        emitted = _result_serialization_rejection(result.operation)
        payload = canonical_json_bytes(authoring_result_to_document(emitted))
    _write_stdout(payload)
    return 0 if emitted.ok else 1


def _result_serialization_rejection(operation: str) -> AuthoringResult[object]:
    return _input_validation_rejection(
        operation,
        AuthoringStage.SERIALIZATION,
        "authoring_result_not_serializable",
        "authoring_result",
        "The shared authoring result could not be serialized safely.",
        "Retry with a valid typed authoring service result.",
    )


@dataclass(frozen=True, slots=True)
class _ProjectInputs:
    public_inputs: tuple[PublicInputDescriptor, ...] = ()
    creator_decisions: tuple[CreatorDecision, ...] = ()
    trace_records: tuple[TraceRecord, ...] = ()
    workspace_metadata: tuple[WorkspaceMetadataEntry, ...] = ()


class _ProjectInputsParseError(ValueError):
    def __init__(self, json_pointer: str, message: str) -> None:
        super().__init__(message)
        self.json_pointer = json_pointer
        self.message = message


def _project_inputs_from_document(document: object) -> _ProjectInputs:
    data = _transport_object(
        document,
        {
            "format_version",
            "public_inputs",
            "creator_decisions",
            "trace_records",
            "workspace_metadata",
        },
        "/",
    )
    if type(data["format_version"]) is not int or data["format_version"] != 1:
        raise _ProjectInputsParseError(
            "/format_version",
            "Project inputs must declare format_version 1.",
        )
    return _ProjectInputs(
        public_inputs=tuple(
            _public_input_from_document(item, index)
            for index, item in enumerate(_transport_array(data["public_inputs"], "/public_inputs"))
        ),
        creator_decisions=tuple(
            _creator_decision_from_document(item, index)
            for index, item in enumerate(
                _transport_array(data["creator_decisions"], "/creator_decisions")
            )
        ),
        trace_records=tuple(
            _trace_record_from_document(item, index)
            for index, item in enumerate(
                _transport_array(
                    data["trace_records"],
                    "/trace_records",
                    max_items=_MAX_TRACE_RECORDS,
                )
            )
        ),
        workspace_metadata=tuple(
            _workspace_metadata_from_document(item, index)
            for index, item in enumerate(
                _transport_array(
                    data["workspace_metadata"],
                    "/workspace_metadata",
                    max_items=_MAX_PROJECT_INPUT_ITEMS,
                )
            )
        ),
    )


def _public_input_from_document(value: object, index: int) -> PublicInputDescriptor:
    pointer = f"/public_inputs/{index}"
    data = _transport_object(
        value,
        {"artifact_id", "media_type", "label", "visibility"},
        pointer,
    )
    return PublicInputDescriptor(
        artifact_id=_transport_text(data["artifact_id"], f"{pointer}/artifact_id"),
        media_type=_transport_text(data["media_type"], f"{pointer}/media_type"),
        label=_transport_text(data["label"], f"{pointer}/label"),
        visibility=_transport_text(data["visibility"], f"{pointer}/visibility"),
    )


def _creator_decision_from_document(value: object, index: int) -> CreatorDecision:
    pointer = f"/creator_decisions/{index}"
    data = _transport_object(value, {"decision_id", "statement"}, pointer)
    return CreatorDecision(
        decision_id=_transport_text(data["decision_id"], f"{pointer}/decision_id"),
        statement=_transport_text(data["statement"], f"{pointer}/statement"),
    )


def _trace_record_from_document(value: object, index: int) -> TraceRecord:
    pointer = f"/trace_records/{index}"
    data = _transport_object(
        value,
        {
            "trace_id",
            "source_artifact_id",
            "target_artifact_id",
            "decision_id",
        },
        pointer,
    )
    return TraceRecord(
        trace_id=_transport_text(data["trace_id"], f"{pointer}/trace_id"),
        source_artifact_id=_transport_text(
            data["source_artifact_id"],
            f"{pointer}/source_artifact_id",
        ),
        target_artifact_id=_transport_text(
            data["target_artifact_id"],
            f"{pointer}/target_artifact_id",
        ),
        decision_id=_transport_text(data["decision_id"], f"{pointer}/decision_id"),
    )


def _workspace_metadata_from_document(value: object, index: int) -> WorkspaceMetadataEntry:
    pointer = f"/workspace_metadata/{index}"
    data = _transport_object(value, {"key", "value"}, pointer)
    return WorkspaceMetadataEntry(
        key=_transport_text(data["key"], f"{pointer}/key"),
        value=_transport_text(data["value"], f"{pointer}/value"),
    )


def _transport_object(
    value: object,
    expected_keys: set[str],
    json_pointer: str,
) -> dict[str, object]:
    if type(value) is not dict:
        raise _ProjectInputsParseError(
            json_pointer,
            "Project inputs contain an invalid object shape.",
        )
    data = cast(dict[str, object], value)
    if set(data) != expected_keys:
        raise _ProjectInputsParseError(
            json_pointer,
            "Project inputs contain missing or unknown fields.",
        )
    return data


def _transport_array(
    value: object,
    json_pointer: str,
    *,
    max_items: int = _MAX_PROJECT_INPUT_ITEMS,
) -> list[object]:
    if type(value) is not list:
        raise _ProjectInputsParseError(
            json_pointer,
            "Project inputs contain an invalid array shape.",
        )
    if len(value) > max_items:
        raise _ProjectInputsParseError(
            json_pointer,
            "Project inputs exceed the allowed collection size.",
        )
    return value


def _transport_text(value: object, json_pointer: str) -> str:
    if type(value) is not str:
        raise _ProjectInputsParseError(
            json_pointer,
            "Project inputs contain a non-string field.",
        )
    return value


def _aliases_input(
    output: Path,
    inputs: tuple[Path, ...],
    directories: tuple[Path, ...],
) -> bool:
    output_key = _path_key(output)
    if any(output_key == _path_key(input_path) for input_path in inputs):
        return True
    for directory in directories:
        directory_key = _path_key(directory)
        try:
            if os.path.commonpath((output_key, directory_key)) == directory_key:
                return True
        except ValueError:
            continue
    return False


def _path_key(path: Path) -> str:
    return os.path.normcase(os.path.realpath(os.path.abspath(path)))


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _write_stdout(payload: bytes) -> None:
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is not None:
        buffer.write(payload)
        buffer.flush()
        return
    sys.stdout.write(payload.decode("utf-8"))
