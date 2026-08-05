"""SDK and structured-CLI parity tests for the V2-2 authoring boundary."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from typing import cast
from unittest import mock

from lore2mud._bounded_json import BoundedJsonError, JsonReadErrorCode
from lore2mud.authoring.contracts import (
    AuthoringDiagnostic,
    AuthoringResult,
    AuthoringStage,
    AuthoringStatus,
    CreatorDecision,
    DiagnosticSeverity,
    GameBlueprint,
    GameProject,
    PreviewBuild,
    ProofingProjection,
    PublicInputDescriptor,
    SimulationReport,
    SimulationRequest,
    TraceRecord,
    WorkspaceMetadataEntry,
)
from lore2mud.authoring.sdk import AgentAuthoringSDK
from lore2mud.authoring.serialization import (
    authoring_result_to_document,
    canonical_json_bytes,
)
from lore2mud.authoring import structured_cli
from lore2mud.cli import main


def _success(operation: str, artifact: object) -> AuthoringResult[object]:
    return AuthoringResult(
        format_version=1,
        operation=operation,
        status=AuthoringStatus.SUCCESS,
        artifact=artifact,
        diagnostics=(),
        exit_code=0,
    )


def _rejected(operation: str) -> AuthoringResult[object]:
    return AuthoringResult(
        format_version=1,
        operation=operation,
        status=AuthoringStatus.REJECTED,
        artifact=None,
        diagnostics=(
            AuthoringDiagnostic(
                stage=AuthoringStage.PREVIEW,
                code="capability_requirement_unsupported_v2_2",
                severity=DiagnosticSeverity.ERROR,
                artifact_id="public_project",
                json_pointer="/blueprint/capability_requirement_ids/0",
                source_span=None,
                message="The fixed V2-2 profile cannot satisfy this requirement.",
                remediation="Remove the requirement or wait for V2-3.",
            ),
        ),
        exit_code=1,
    )


class AgentAuthoringSDKTests(unittest.TestCase):
    def test_sdk_forwards_every_operation_to_one_injected_service(self) -> None:
        service = mock.MagicMock()
        blueprint_document = {"kind": "blueprint"}
        project_document = {"kind": "project"}
        blueprint = cast(GameBlueprint, object())
        project = cast(GameProject, object())
        request = cast(SimulationRequest, object())
        report = cast(SimulationReport, object())
        public_inputs = (object(),)
        creator_decisions = (object(),)
        trace_records = (object(),)
        workspace_metadata = (object(),)

        service.validate_blueprint_document.return_value = _success(
            "validate_blueprint", blueprint
        )
        service.validate_project_document.return_value = _success(
            "validate_project", project
        )
        service.create_project.return_value = _success("create_project", project)
        service.validate_project.return_value = _success("validate_project", project)
        service.build_preview.return_value = _success("build_preview", object())
        service.simulate.return_value = _success("simulate", object())
        service.replay.return_value = _success("replay", object())
        service.proof.return_value = _success("proof", object())
        sdk = AgentAuthoringSDK(service)

        self.assertIs(
            sdk.validate_blueprint_document(blueprint_document),
            service.validate_blueprint_document.return_value,
        )
        self.assertIs(
            sdk.validate_project_document(project_document),
            service.validate_project_document.return_value,
        )
        self.assertIs(
            sdk.create_project(
                project_id="public_project",
                blueprint=blueprint,
                content_root=Path("public_content"),
                public_inputs=cast(tuple, public_inputs),
                creator_decisions=cast(tuple, creator_decisions),
                trace_records=cast(tuple, trace_records),
                workspace_metadata=cast(tuple, workspace_metadata),
            ),
            service.create_project.return_value,
        )
        self.assertIs(
            sdk.validate_project(project),
            service.validate_project.return_value,
        )
        self.assertIs(
            sdk.build_preview(project),
            service.build_preview.return_value,
        )
        self.assertIs(
            sdk.simulate(project, request),
            service.simulate.return_value,
        )
        self.assertIs(
            sdk.replay(project, report),
            service.replay.return_value,
        )
        self.assertIs(sdk.proof(project), service.proof.return_value)

        service.create_project.assert_called_once_with(
            project_id="public_project",
            blueprint=blueprint,
            content_root=Path("public_content"),
            public_inputs=public_inputs,
            creator_decisions=creator_decisions,
            trace_records=trace_records,
            workspace_metadata=workspace_metadata,
        )
        service.validate_project.assert_called_once_with(project)
        service.build_preview.assert_called_once_with(project)
        service.simulate.assert_called_once_with(project, request)
        service.replay.assert_called_once_with(project, report)
        service.proof.assert_called_once_with(project)


class _FakeSDK:
    def __init__(self) -> None:
        self.project = cast(GameProject, {"kind": "project"})
        self.blueprint = cast(GameBlueprint, {"kind": "blueprint"})
        self.calls: list[tuple[str, object]] = []
        self.results: dict[str, AuthoringResult[object]] = {
            "create_project": _success("create_project", {"kind": "project"}),
            "validate_project": _success("validate_project", {"kind": "project"}),
            "build_preview": _success("build_preview", {"kind": "preview"}),
            "simulate": _success("simulate", {"kind": "simulation_report"}),
            "replay": _success("replay", {"kind": "simulation_report"}),
            "proof": _success("proof", {"kind": "proofing_projection"}),
        }

    def validate_blueprint_document(
        self, document: object
    ) -> AuthoringResult[GameBlueprint]:
        self.calls.append(("validate_blueprint_document", document))
        return cast(
            AuthoringResult[GameBlueprint],
            _success("validate_blueprint", self.blueprint),
        )

    def validate_project_document(
        self, document: object
    ) -> AuthoringResult[GameProject]:
        self.calls.append(("validate_project_document", document))
        return cast(
            AuthoringResult[GameProject],
            _success("validate_project", self.project),
        )

    def create_project(self, **kwargs: object) -> AuthoringResult[GameProject]:
        self.calls.append(("create_project", kwargs))
        return cast(AuthoringResult[GameProject], self.results["create_project"])

    def build_preview(self, project: GameProject) -> AuthoringResult[PreviewBuild]:
        self.calls.append(("build_preview", project))
        return cast(AuthoringResult[PreviewBuild], self.results["build_preview"])

    def simulate(
        self, project: GameProject, request: SimulationRequest
    ) -> AuthoringResult[SimulationReport]:
        self.calls.append(("simulate", (project, request)))
        return cast(AuthoringResult[SimulationReport], self.results["simulate"])

    def replay(
        self, project: GameProject, report: SimulationReport
    ) -> AuthoringResult[SimulationReport]:
        self.calls.append(("replay", (project, report)))
        return cast(AuthoringResult[SimulationReport], self.results["replay"])

    def proof(self, project: GameProject) -> AuthoringResult[ProofingProjection]:
        self.calls.append(("proof", project))
        return cast(AuthoringResult[ProofingProjection], self.results["proof"])


class StructuredAuthoringCLITests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.blueprint_path = self.root / "blueprint.json"
        self.project_path = self.root / "project.json"
        self.request_path = self.root / "request.json"
        self.report_path = self.root / "report.json"
        self.content_root = self.root / "content"
        self.content_root.mkdir()
        self.content_room_path = self.content_root / "rooms.json"
        self.content_room_path.write_text('[{"id":"room_public"}]\n', encoding="utf-8")
        for path in (
            self.blueprint_path,
            self.project_path,
            self.request_path,
            self.report_path,
        ):
            path.write_text("{}\n", encoding="utf-8")
        self.fake_sdk = _FakeSDK()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _run(self, argv: list[str]) -> tuple[int, bytes]:
        stdout = io.StringIO()
        with (
            mock.patch.object(
                structured_cli,
                "AgentAuthoringSDK",
                return_value=self.fake_sdk,
            ),
            mock.patch.object(
                structured_cli,
                "_load_simulation_request_document",
                return_value=cast(SimulationRequest, object()),
            ),
            mock.patch.object(
                structured_cli,
                "_load_simulation_report_document",
                return_value=cast(SimulationReport, object()),
            ),
            mock.patch("sys.stdout", stdout),
        ):
            exit_code = main(argv)
        return exit_code, stdout.getvalue().encode("utf-8")

    def test_all_six_subcommands_emit_canonical_json_and_dispatch_to_sdk(self) -> None:
        cases = (
            (
                [
                    "author",
                    "create-project",
                    "--project-id",
                    "public_project",
                    "--blueprint",
                    str(self.blueprint_path),
                    "--content",
                    str(self.content_root),
                ],
                "create_project",
            ),
            (
                ["author", "validate", "--project", str(self.project_path)],
                "validate_project",
            ),
            (
                ["author", "preview", "--project", str(self.project_path)],
                "build_preview",
            ),
            (
                [
                    "author",
                    "simulate",
                    "--project",
                    str(self.project_path),
                    "--request",
                    str(self.request_path),
                ],
                "simulate",
            ),
            (
                [
                    "author",
                    "replay",
                    "--project",
                    str(self.project_path),
                    "--report",
                    str(self.report_path),
                ],
                "replay",
            ),
            (
                ["author", "proof", "--project", str(self.project_path)],
                "proof",
            ),
        )
        for argv, operation in cases:
            with self.subTest(operation=operation):
                exit_code, payload = self._run(argv)
                document = json.loads(payload.decode("utf-8"))
                self.assertEqual(exit_code, 0)
                self.assertEqual(document["operation"], operation)
                self.assertEqual(document["status"], "success")
                self.assertEqual(document["exit_code"], 0)
                self.assertEqual(payload, canonical_json_bytes(document))

    def test_successful_output_is_atomic_canonical_artifact_only(self) -> None:
        output_path = self.root / "artifacts" / "preview.json"

        exit_code, stdout_payload = self._run(
            [
                "author",
                "preview",
                "--project",
                str(self.project_path),
                "--output",
                str(output_path),
            ]
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            output_path.read_bytes(),
            canonical_json_bytes({"kind": "preview"}),
        )
        self.assertEqual(
            stdout_payload,
            canonical_json_bytes(
                authoring_result_to_document(self.fake_sdk.results["build_preview"])
            ),
        )
        self.assertEqual(list(output_path.parent.glob("*.tmp")), [])

    def test_output_cannot_overwrite_project_input(self) -> None:
        original = self.project_path.read_bytes()

        exit_code, payload = self._run(
            [
                "author",
                "preview",
                "--project",
                str(self.project_path),
                "--output",
                str(self.project_path),
            ]
        )

        document = json.loads(payload.decode("utf-8"))
        self.assertEqual(exit_code, 1)
        self.assertEqual(self.project_path.read_bytes(), original)
        self.assertEqual(
            document["diagnostics"][0]["code"],
            "artifact_output_aliases_input",
        )

    def test_create_output_cannot_overwrite_a_content_source(self) -> None:
        original = self.content_room_path.read_bytes()

        exit_code, payload = self._run(
            [
                "author",
                "create-project",
                "--project-id",
                "public_project",
                "--blueprint",
                str(self.blueprint_path),
                "--content",
                str(self.content_root),
                "--output",
                str(self.content_room_path),
            ]
        )

        document = json.loads(payload.decode("utf-8"))
        self.assertEqual(exit_code, 1)
        self.assertEqual(self.content_room_path.read_bytes(), original)
        self.assertEqual(
            document["diagnostics"][0]["code"],
            "artifact_output_aliases_input",
        )

    def test_rejected_domain_result_is_equivalent_and_writes_no_artifact(self) -> None:
        rejected = _rejected("build_preview")
        self.fake_sdk.results["build_preview"] = rejected
        output_path = self.root / "preview.json"

        exit_code, payload = self._run(
            [
                "author",
                "preview",
                "--project",
                str(self.project_path),
                "--output",
                str(output_path),
            ]
        )

        self.assertEqual(exit_code, 1)
        self.assertFalse(output_path.exists())
        self.assertEqual(
            payload,
            canonical_json_bytes(authoring_result_to_document(rejected)),
        )

    def test_invalid_service_artifact_becomes_structured_serialization_rejection(
        self,
    ) -> None:
        self.fake_sdk.results["build_preview"] = _success(
            "build_preview",
            object(),
        )

        exit_code, payload = self._run(
            ["author", "preview", "--project", str(self.project_path)]
        )

        document = json.loads(payload.decode("utf-8"))
        self.assertEqual(exit_code, 1)
        self.assertEqual(document["status"], "rejected")
        self.assertEqual(
            document["diagnostics"][0]["code"],
            "authoring_result_not_serializable",
        )

    def test_bounded_json_failure_returns_public_diagnostic_before_service(self) -> None:
        private_named_path = self.root / "private-canon-source.json"
        private_named_path.write_text("{}\n", encoding="utf-8")
        stdout = io.StringIO()
        with (
            mock.patch.object(
                structured_cli,
                "read_bounded_json",
                side_effect=BoundedJsonError(JsonReadErrorCode.INVALID_JSON),
            ),
            mock.patch.object(structured_cli, "AgentAuthoringSDK") as sdk_type,
            mock.patch("sys.stdout", stdout),
        ):
            exit_code = main(
                ["author", "preview", "--project", str(private_named_path)]
            )

        document = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertEqual(
            document["diagnostics"][0]["code"],
            "authoring_input_invalid_json",
        )
        self.assertNotIn(str(private_named_path), stdout.getvalue())
        self.assertNotIn(private_named_path.name, stdout.getvalue())
        sdk_type.assert_not_called()

    def test_sdk_and_cli_emit_the_same_service_result(self) -> None:
        service = mock.MagicMock()
        project = cast(GameProject, {"kind": "project"})
        expected = _success("build_preview", {"kind": "preview"})
        service.validate_project_document.return_value = _success(
            "validate_project", project
        )
        service.build_preview.return_value = expected
        sdk = AgentAuthoringSDK(service)
        direct_result = sdk.build_preview(project)
        stdout = io.StringIO()

        with (
            mock.patch.object(structured_cli, "AgentAuthoringSDK", return_value=sdk),
            mock.patch("sys.stdout", stdout),
        ):
            exit_code = main(
                ["author", "preview", "--project", str(self.project_path)]
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            stdout.getvalue().encode("utf-8"),
            canonical_json_bytes(authoring_result_to_document(direct_result)),
        )

    def test_nonempty_project_inputs_match_the_sdk_call_and_result(self) -> None:
        project_inputs_path = self.root / "project_inputs.json"
        project_inputs_document = {
            "format_version": 1,
            "public_inputs": [
                {
                    "artifact_id": "source_public",
                    "media_type": "text/plain",
                    "label": "Public source",
                    "visibility": "public_safe",
                }
            ],
            "creator_decisions": [
                {
                    "decision_id": "decision_scope",
                    "statement": "Use only the public synthetic fixture.",
                }
            ],
            "trace_records": [
                {
                    "trace_id": "trace_room",
                    "source_artifact_id": "source_public",
                    "target_artifact_id": "room_public",
                    "decision_id": "decision_scope",
                }
            ],
            "workspace_metadata": [
                {"key": "proofing_zoom", "value": "125"}
            ],
        }
        project_inputs_path.write_bytes(canonical_json_bytes(project_inputs_document))
        public_inputs = (
            PublicInputDescriptor(
                artifact_id="source_public",
                media_type="text/plain",
                label="Public source",
                visibility="public_safe",
            ),
        )
        creator_decisions = (
            CreatorDecision(
                decision_id="decision_scope",
                statement="Use only the public synthetic fixture.",
            ),
        )
        trace_records = (
            TraceRecord(
                trace_id="trace_room",
                source_artifact_id="source_public",
                target_artifact_id="room_public",
                decision_id="decision_scope",
            ),
        )
        workspace_metadata = (
            WorkspaceMetadataEntry(key="proofing_zoom", value="125"),
        )
        service = mock.MagicMock()
        blueprint = cast(GameBlueprint, {"kind": "blueprint"})
        expected = _success("create_project", {"kind": "project"})
        service.validate_blueprint_document.return_value = _success(
            "validate_blueprint", blueprint
        )
        service.create_project.return_value = expected
        sdk = AgentAuthoringSDK(service)
        direct_result = sdk.create_project(
            project_id="public_project",
            blueprint=blueprint,
            content_root=self.content_root,
            public_inputs=public_inputs,
            creator_decisions=creator_decisions,
            trace_records=trace_records,
            workspace_metadata=workspace_metadata,
        )
        service.create_project.reset_mock()
        stdout = io.StringIO()

        with (
            mock.patch.object(structured_cli, "AgentAuthoringSDK", return_value=sdk),
            mock.patch("sys.stdout", stdout),
        ):
            exit_code = main(
                [
                    "author",
                    "create-project",
                    "--project-id",
                    "public_project",
                    "--blueprint",
                    str(self.blueprint_path),
                    "--content",
                    str(self.content_root),
                    "--project-inputs",
                    str(project_inputs_path),
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            stdout.getvalue().encode("utf-8"),
            canonical_json_bytes(authoring_result_to_document(direct_result)),
        )
        service.create_project.assert_called_once_with(
            project_id="public_project",
            blueprint=blueprint,
            content_root=self.content_root,
            public_inputs=public_inputs,
            creator_decisions=creator_decisions,
            trace_records=trace_records,
            workspace_metadata=workspace_metadata,
        )

    def test_project_inputs_unknown_fields_and_invalid_shapes_reject_stably(self) -> None:
        base = {
            "format_version": 1,
            "public_inputs": [],
            "creator_decisions": [],
            "trace_records": [],
            "workspace_metadata": [],
        }
        cases = (
            ({**base, "private_extension": []}, "/"),
            ({**base, "public_inputs": {}}, "/public_inputs"),
            (
                {
                    **base,
                    "public_inputs": [
                        {
                            "artifact_id": "source_public",
                            "media_type": "text/plain",
                            "label": "Public source",
                            "visibility": "public_safe",
                        }
                    ]
                    * 4_097,
                },
                "/public_inputs",
            ),
        )
        for index, (document, pointer) in enumerate(cases):
            with self.subTest(case=index):
                project_inputs_path = self.root / f"invalid_project_inputs_{index}.json"
                project_inputs_path.write_bytes(canonical_json_bytes(document))
                stdout = io.StringIO()
                with (
                    mock.patch.object(structured_cli, "AgentAuthoringSDK") as sdk_type,
                    mock.patch("sys.stdout", stdout),
                ):
                    exit_code = main(
                        [
                            "author",
                            "create-project",
                            "--project-id",
                            "public_project",
                            "--blueprint",
                            str(self.blueprint_path),
                            "--content",
                            str(self.content_root),
                            "--project-inputs",
                            str(project_inputs_path),
                        ]
                    )

                result_document = json.loads(stdout.getvalue())
                self.assertEqual(exit_code, 1)
                self.assertEqual(
                    result_document["diagnostics"][0]["code"],
                    "project_inputs_invalid",
                )
                self.assertEqual(
                    result_document["diagnostics"][0]["json_pointer"],
                    pointer,
                )
                sdk_type.assert_not_called()

    def test_project_input_collection_limits_accept_exact_and_reject_over(self) -> None:
        base = {
            "format_version": 1,
            "public_inputs": [],
            "creator_decisions": [],
            "trace_records": [],
            "workspace_metadata": [],
        }
        cases = (
            (
                "public_inputs",
                4_096,
                {
                    "artifact_id": "source_public",
                    "media_type": "text/plain",
                    "label": "Public source",
                    "visibility": "public_safe",
                },
                "public_inputs",
            ),
            (
                "creator_decisions",
                4_096,
                {
                    "decision_id": "decision_scope",
                    "statement": "Use public synthetic material.",
                },
                "creator_decisions",
            ),
            (
                "trace_records",
                8_192,
                {
                    "trace_id": "trace_room",
                    "source_artifact_id": "source_public",
                    "target_artifact_id": "room_public",
                    "decision_id": "decision_scope",
                },
                "trace_records",
            ),
            (
                "workspace_metadata",
                4_096,
                {"key": "proofing_zoom", "value": "125"},
                "workspace_metadata",
            ),
        )
        for field, limit, item, attribute in cases:
            with self.subTest(field=field, boundary="exact"):
                parsed = structured_cli._project_inputs_from_document(
                    {**base, field: [item] * limit}
                )
                self.assertEqual(len(getattr(parsed, attribute)), limit)
            with self.subTest(field=field, boundary="over"):
                with self.assertRaises(
                    structured_cli._ProjectInputsParseError
                ) as caught:
                    structured_cli._project_inputs_from_document(
                        {**base, field: [item] * (limit + 1)}
                    )
                self.assertEqual(caught.exception.json_pointer, f"/{field}")

    def test_author_argparse_misuse_exits_two(self) -> None:
        for argv in (["author"], ["author", "preview"]):
            with self.subTest(argv=argv), self.assertRaises(SystemExit) as caught:
                main(argv)
            self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
