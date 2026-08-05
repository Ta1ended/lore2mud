"""Contract, schema, and immutable project tests for V2-2 authoring."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from typing import cast
from unittest import mock

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from lore2mud._bounded_json import DEFAULT_JSON_READ_LIMITS
from lore2mud.authoring.contracts import (
    CAPABILITY_DIAGNOSTIC_CODE,
    CreatorDecision,
    GameBlueprint,
    PublicInputDescriptor,
    SimulationCondition,
    SimulationOutcome,
    SimulationRequest,
    TraceRecord,
    WorkspaceMetadataEntry,
)
from lore2mud.authoring.project import (
    BlueprintValidationError,
    ProjectValidationError,
    capability_requirement_diagnostics,
    capture_v1_content,
    create_game_project,
    load_blueprint,
    load_blueprint_document,
    load_project_document,
)
from lore2mud.authoring.serialization import (
    blueprint_bytes,
    canonical_json_bytes,
    diagnostic_to_document,
    authoring_result_to_document,
    parse_canonical_json,
    project_bytes,
    project_semantic_bytes,
    project_to_document,
    validate_unicode_scalars,
)
from lore2mud.authoring.sdk import AgentAuthoringSDK
from lore2mud.authoring.service import AuthoringService


ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "tests" / "fixtures" / "authoring" / "blueprint.json"
CONTENT = ROOT / "examples" / "original_demo"


def _schema_registry() -> tuple[dict[str, object], Registry]:
    schemas = {
        document["$id"]: document
        for path in (ROOT / "schemas").glob("*.schema.json")
        for document in [json.loads(path.read_text("utf-8"))]
        if "$id" in document
    }
    registry = Registry().with_resources(
        (uri, Resource.from_contents(document))
        for uri, document in schemas.items()
    )
    return schemas, registry


class AuthoringContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.blueprint = load_blueprint(BLUEPRINT)

    def _project(self, **kwargs: object):
        return create_game_project(
            project_id="public_fixture_project",
            blueprint=self.blueprint,
            content_root=CONTENT,
            public_inputs=(
                PublicInputDescriptor(
                    artifact_id="public_brief",
                    media_type="application/json",
                    label="Public fixture brief",
                ),
            ),
            creator_decisions=(
                CreatorDecision(
                    decision_id="keep_opening_public",
                    statement="Use the public opening fixture.",
                ),
            ),
            trace_records=(
                TraceRecord(
                    trace_id="trace_opening",
                    source_artifact_id="public_brief",
                    target_artifact_id="public_fixture_project",
                    decision_id="keep_opening_public",
                ),
            ),
            **kwargs,
        )

    def test_blueprint_normalization_has_stable_canonical_bytes(self) -> None:
        raw = json.loads(BLUEPRINT.read_text("utf-8"))
        raw["required_game_loops"].reverse()
        raw["rights_assertions"].reverse()

        normalized = load_blueprint_document(raw)

        self.assertEqual(blueprint_bytes(normalized), blueprint_bytes(self.blueprint))
        self.assertTrue(blueprint_bytes(normalized).endswith(b"\n"))

    def test_project_capture_is_relative_immutable_and_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            content = Path(directory) / "public_content"
            shutil.copytree(CONTENT, content)
            project = create_game_project(
                project_id="public_fixture_project",
                blueprint=self.blueprint,
                content_root=content,
            )
            before = project_bytes(project)
            (content / "rooms.json").write_text("{}", encoding="utf-8")

        restored = load_project_document(parse_canonical_json(before))
        self.assertEqual(project, restored)
        self.assertEqual(before, project_bytes(restored))
        self.assertTrue(all("/" not in value.name and "\\" not in value.name for value in project.content_files))

    def test_content_loader_only_receives_the_bounded_captured_snapshot(self) -> None:
        with mock.patch("lore2mud.authoring.project.load_content_pack") as loader:
            captured = capture_v1_content(CONTENT)

        self.assertTrue(captured)
        loader.assert_called_once()
        loaded_root = Path(loader.call_args.args[0]).resolve()
        self.assertNotEqual(loaded_root, CONTENT.resolve())

    def test_workspace_metadata_is_outside_semantic_identity(self) -> None:
        first = self._project(
            workspace_metadata=(WorkspaceMetadataEntry("zoom", "100"),)
        )
        second = replace(
            first,
            workspace_metadata=(
                WorkspaceMetadataEntry("collapsed", "opening"),
                WorkspaceMetadataEntry("zoom", "175"),
            ),
        )

        self.assertNotEqual(project_bytes(first), project_bytes(second))
        self.assertEqual(project_semantic_bytes(first), project_semantic_bytes(second))
        self.assertEqual(first.build_lock, second.build_lock)

    def test_capability_requirements_have_stable_preview_diagnostics(self) -> None:
        blueprint = replace(
            self.blueprint,
            capability_requirement_ids=("future_dialogue", "future_world"),
        )
        project = create_game_project(
            project_id="blocked_project",
            blueprint=blueprint,
            content_root=CONTENT,
        )

        diagnostics = capability_requirement_diagnostics(project)

        self.assertEqual(
            [item.code for item in diagnostics],
            [CAPABILITY_DIAGNOSTIC_CODE, CAPABILITY_DIAGNOSTIC_CODE],
        )
        self.assertEqual(
            [item.json_pointer for item in diagnostics],
            [
                "/blueprint/capability_requirement_ids/0",
                "/blueprint/capability_requirement_ids/1",
            ],
        )

    def test_project_tampering_is_rejected_before_runtime_construction(self) -> None:
        document = project_to_document(self._project())
        document["content_files"][0]["sha256"] = "0" * 64

        with self.assertRaises(ProjectValidationError):
            load_project_document(document)

    def test_create_project_revalidates_typed_public_boundary_fields(self) -> None:
        with self.assertRaises(ProjectValidationError):
            create_game_project(
                project_id="unsafe_project",
                blueprint=self.blueprint,
                content_root=CONTENT,
                public_inputs=(
                    PublicInputDescriptor(
                        artifact_id="public_brief",
                        media_type="application/json",
                        label="Public fixture brief",
                        visibility="private",
                    ),
                ),
            )

    def test_typed_sdk_rejects_non_scalar_blueprint_text_with_transport_envelope(self) -> None:
        result = AgentAuthoringSDK().create_project(
            project_id="unsafe_unicode_project",
            blueprint=replace(self.blueprint, title="\ud800"),
            content_root=CONTENT,
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.operation, "create_project")
        self.assertEqual(result.diagnostics[0].stage.value, "serialization")
        self.assertEqual(result.diagnostics[0].code, "authoring_input_too_complex")
        self.assertEqual(result.diagnostics[0].artifact_id, "blueprint")

    def test_sdk_document_validation_rejects_cyclic_containers(self) -> None:
        cyclic_dict: dict[str, object] = {}
        cyclic_dict["self"] = cyclic_dict
        cyclic_list: list[object] = []
        cyclic_list.append(cyclic_list)
        shared: list[object] = []
        validate_unicode_scalars({"first": shared, "second": shared})
        sdk = AgentAuthoringSDK()
        schemas, registry = _schema_registry()
        result_validator = Draft202012Validator(
            schemas[
                "https://github.com/lore2mud/lore2mud/schemas/authoring_result.schema.json"
            ],
            registry=registry,
        )

        cases = (
            (sdk.validate_blueprint_document(cyclic_dict), "blueprint_invalid"),
            (sdk.validate_blueprint_document(cyclic_list), "blueprint_invalid"),
            (sdk.validate_project_document(cyclic_dict), "project_invalid"),
            (sdk.validate_project_document(cyclic_list), "project_invalid"),
        )

        for result, expected_code in cases:
            with self.subTest(operation=result.operation, code=expected_code):
                self.assertFalse(result.ok)
                self.assertIsNone(result.artifact)
                self.assertEqual(result.exit_code, 1)
                self.assertEqual(len(result.diagnostics), 1)
                self.assertEqual(result.diagnostics[0].code, expected_code)
                result_validator.validate(authoring_result_to_document(result))

    def test_typed_sdk_rejects_malformed_embedded_content_for_every_project_operation(
        self,
    ) -> None:
        sdk = AgentAuthoringSDK()
        project = self._project()
        request = SimulationRequest(1, 7, 11, "Public Player", ())
        report_result = sdk.simulate(project, request)
        self.assertTrue(report_result.ok)
        report = report_result.artifact
        assert report is not None
        malformed_file = replace(project.content_files[0], canonical_json=b"{")
        malformed = replace(
            project,
            content_files=(malformed_file, *project.content_files[1:]),
        )

        results = (
            sdk.validate_project(malformed),
            sdk.build_preview(malformed),
            sdk.simulate(malformed, request),
            sdk.replay(malformed, report),
            sdk.proof(malformed),
        )

        self.assertEqual(
            [result.operation for result in results],
            ["validate_project", "build_preview", "simulate", "replay", "proof"],
        )
        for result in results:
            self.assertFalse(result.ok)
            self.assertIsNone(result.artifact)
            self.assertEqual(result.exit_code, 1)
            self.assertEqual(len(result.diagnostics), 1)
            canonical_json_bytes(authoring_result_to_document(result))

    def test_typed_sdk_rejects_malformed_nested_contracts_and_report(self) -> None:
        sdk = AgentAuthoringSDK()
        project = self._project()
        request = SimulationRequest(1, 7, 11, "Public Player", ())
        report_result = sdk.simulate(project, request)
        self.assertTrue(report_result.ok)
        report = report_result.artifact
        assert report is not None

        malformed_project = replace(
            project,
            blueprint=cast(GameBlueprint, object()),
        )
        malformed_request = replace(
            request,
            conditions=cast(tuple[SimulationCondition, ...], (object(),)),
        )
        malformed_report = replace(
            report,
            outcome=cast(SimulationOutcome, object()),
        )
        results = (
            sdk.create_project(
                project_id="malformed_nested_project",
                blueprint=cast(GameBlueprint, object()),
                content_root=CONTENT,
            ),
            sdk.validate_project(malformed_project),
            sdk.build_preview(malformed_project),
            sdk.simulate(project, malformed_request),
            sdk.replay(project, malformed_report),
            sdk.proof(malformed_project),
        )

        for result in results:
            self.assertFalse(result.ok)
            self.assertIsNone(result.artifact)
            self.assertEqual(result.exit_code, 1)
            self.assertEqual(len(result.diagnostics), 1)
            canonical_json_bytes(authoring_result_to_document(result))
        self.assertEqual(
            results[3].diagnostics[0].code,
            "simulation_request_invalid",
        )
        self.assertEqual(
            results[4].diagnostics[0].code,
            "simulation_report_invalid",
        )

    def test_typed_sdk_rejects_non_json_scalars_for_project_and_report(self) -> None:
        sdk = AgentAuthoringSDK()
        project = self._project()
        request = SimulationRequest(1, 7, 11, "Public Player", ())
        report_result = sdk.simulate(project, request)
        self.assertTrue(report_result.ok)
        report = report_result.artifact
        assert report is not None

        malformed_project = replace(
            project,
            workspace_metadata=(
                WorkspaceMetadataEntry(cast(str, b"not-json"), "value"),
            ),
        )
        malformed_report = replace(report, player_name=cast(str, b"not-json"))
        with (
            mock.patch(
                "lore2mud.authoring.service.build_preview",
                side_effect=AssertionError("invalid project reached preview build"),
            ) as service_preview,
            mock.patch(
                "lore2mud.authoring.simulation.build_preview",
                side_effect=AssertionError("invalid project reached simulation preview"),
            ) as simulation_preview,
            mock.patch(
                "lore2mud.authoring.service.replay_report",
                side_effect=AssertionError("invalid artifact reached replay"),
            ) as replay,
            mock.patch(
                "lore2mud.authoring.service.build_proofing_projection",
                side_effect=AssertionError("invalid project reached proofing"),
            ) as proofing,
            mock.patch(
                "lore2mud.authoring.simulation.GameSession.from_content_pack",
                side_effect=AssertionError("invalid project reached session creation"),
            ) as session_builder,
        ):
            project_results = (
                sdk.validate_project(malformed_project),
                sdk.build_preview(malformed_project),
                sdk.simulate(malformed_project, request),
                sdk.replay(malformed_project, report),
                sdk.proof(malformed_project),
            )
            report_rejection = sdk.replay(project, malformed_report)

        service_preview.assert_not_called()
        simulation_preview.assert_not_called()
        replay.assert_not_called()
        proofing.assert_not_called()
        session_builder.assert_not_called()

        self.assertEqual(
            [result.operation for result in project_results],
            ["validate_project", "build_preview", "simulate", "replay", "proof"],
        )
        for result in project_results:
            self.assertFalse(result.ok)
            self.assertIsNone(result.artifact)
            self.assertEqual(result.exit_code, 1)
            self.assertEqual(len(result.diagnostics), 1)
            self.assertEqual(
                result.diagnostics[0].code,
                "authoring_input_invalid_json",
            )
            self.assertEqual(result.diagnostics[0].artifact_id, "project")
            canonical_json_bytes(authoring_result_to_document(result))

        self.assertFalse(report_rejection.ok)
        self.assertIsNone(report_rejection.artifact)
        self.assertEqual(report_rejection.exit_code, 1)
        self.assertEqual(len(report_rejection.diagnostics), 1)
        self.assertEqual(
            report_rejection.diagnostics[0].code,
            "authoring_input_invalid_json",
        )
        self.assertEqual(report_rejection.diagnostics[0].artifact_id, "report")
        canonical_json_bytes(authoring_result_to_document(report_rejection))

    def test_typed_sdk_bounds_embedded_content_bytes_before_parsing(self) -> None:
        project = self._project()
        oversized_file = replace(
            project.content_files[0],
            canonical_json=b" " * (DEFAULT_JSON_READ_LIMITS.max_bytes + 1),
        )
        oversized = replace(
            project,
            content_files=(oversized_file, *project.content_files[1:]),
        )

        result = AgentAuthoringSDK().validate_project(oversized)

        self.assertFalse(result.ok)
        self.assertEqual(len(result.diagnostics), 1)
        self.assertEqual(result.diagnostics[0].code, "project_invalid")
        canonical_json_bytes(authoring_result_to_document(result))

    def test_typed_sdk_caps_capability_diagnostics_at_schema_limit(self) -> None:
        sdk = AgentAuthoringSDK()
        project = self._project()
        maximum_blueprint = replace(
            self.blueprint,
            capability_requirement_ids=tuple(
                f"future_{index}" for index in range(4096)
            ),
        )
        maximum_project = create_game_project(
            project_id="maximum_capability_project",
            blueprint=maximum_blueprint,
            content_root=CONTENT,
        )
        oversized = replace(
            project,
            blueprint=replace(
                project.blueprint,
                capability_requirement_ids=tuple(
                    f"future_{index}" for index in range(4097)
                ),
            ),
        )

        maximum_result = sdk.build_preview(maximum_project)
        direct_diagnostics = capability_requirement_diagnostics(oversized)
        result = sdk.build_preview(oversized)

        self.assertFalse(maximum_result.ok)
        self.assertEqual(len(maximum_result.diagnostics), 4096)
        canonical_json_bytes(authoring_result_to_document(maximum_result))
        self.assertEqual(len(direct_diagnostics), 4096)
        self.assertFalse(result.ok)
        self.assertEqual(len(result.diagnostics), 1)
        self.assertEqual(result.diagnostics[0].code, "preview_project_invalid")
        canonical_json_bytes(authoring_result_to_document(result))

    def test_unapproved_blueprint_cannot_be_reintroduced_via_project_document(self) -> None:
        project = self._project()
        document = project_to_document(project)
        document["blueprint"]["approval"]["approved"] = False

        with self.assertRaises(ProjectValidationError):
            load_project_document(document)

    def test_project_typed_collections_are_bounded_before_sorting(self) -> None:
        inputs = (
            PublicInputDescriptor(
                artifact_id=f"input_{index}",
                media_type="application/json",
                label="Public fixture",
            )
            for index in range(4097)
        )

        with self.assertRaisesRegex(ProjectValidationError, "exceeds 4096 entries"):
            create_game_project(
                project_id="oversized_project",
                blueprint=self.blueprint,
                content_root=CONTENT,
                public_inputs=inputs,
            )

    def test_service_io_rejection_does_not_expose_absolute_path(self) -> None:
        missing = ROOT / "private-looking-root" / "not-present"
        result = AuthoringService().create_project(
            project_id="missing_project",
            blueprint=self.blueprint,
            content_root=missing,
        )

        self.assertEqual(result.exit_code, 1)
        payload = json.dumps(
            [diagnostic_to_document(item) for item in result.diagnostics]
        )
        self.assertNotIn(str(missing), payload)

    def test_content_validation_diagnostic_does_not_echo_unknown_content_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            content = Path(directory) / "content"
            shutil.copytree(CONTENT, content)
            unknown_id = "private_source_identifier"
            (content / "rooms.json").write_text(
                json.dumps([{"id": unknown_id}]),
                encoding="utf-8",
            )
            result = AuthoringService().create_project(
                project_id="invalid_content_project",
                blueprint=self.blueprint,
                content_root=content,
            )

        payload = canonical_json_bytes(
            [diagnostic_to_document(item) for item in result.diagnostics]
        )
        self.assertEqual(result.exit_code, 1)
        self.assertNotIn(unknown_id.encode("utf-8"), payload)
        self.assertNotIn(str(content).encode("utf-8"), payload)

    def test_public_validation_diagnostic_does_not_echo_unknown_field_names(self) -> None:
        document = json.loads(BLUEPRINT.read_text("utf-8"))
        private_identifier = "private_source_identifier"
        document[private_identifier] = True

        result = AuthoringService().validate_blueprint_document(document)
        payload = canonical_json_bytes(
            [diagnostic_to_document(item) for item in result.diagnostics]
        )

        self.assertEqual(result.exit_code, 1)
        self.assertNotIn(private_identifier.encode("utf-8"), payload)


class AuthoringSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas, cls.registry = _schema_registry()

    def _validator(self, name: str) -> Draft202012Validator:
        schema = self.schemas[
            f"https://github.com/lore2mud/lore2mud/schemas/{name}"
        ]
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema, registry=self.registry)

    def test_blueprint_project_and_diagnostic_schemas_accept_typed_documents(self) -> None:
        blueprint_validator = self._validator("game_blueprint.schema.json")
        project_validator = self._validator("game_project.schema.json")
        project_inputs_validator = self._validator("game_project_inputs.schema.json")
        diagnostic_validator = self._validator("authoring_diagnostic.schema.json")
        blueprint_validator.validate(parse_canonical_json(blueprint_bytes(load_blueprint(BLUEPRINT))))

        project_inputs_validator.validate(
            {
                "format_version": 1,
                "public_inputs": [
                    {
                        "artifact_id": "public_brief",
                        "media_type": "application/json",
                        "label": "Public fixture brief",
                        "visibility": "public_safe",
                    }
                ],
                "creator_decisions": [],
                "trace_records": [],
                "workspace_metadata": [],
            }
        )

        project = create_game_project(
            project_id="schema_fixture_project",
            blueprint=load_blueprint(BLUEPRINT),
            content_root=CONTENT,
        )
        project_validator.validate(project_to_document(project))

        blocked = replace(
            project,
            blueprint=replace(
                project.blueprint,
                capability_requirement_ids=("future_capability",),
            ),
        )
        diagnostic_validator.validate(
            diagnostic_to_document(capability_requirement_diagnostics(blocked)[0])
        )

    def test_blueprint_determinism_schema_and_loader_enforce_signed_64_bit(self) -> None:
        validator = self._validator("game_blueprint.schema.json")
        base = json.loads(BLUEPRINT.read_text("utf-8"))

        for field, value in (
            ("seed", -(2**63)),
            ("clock", 2**63 - 1),
        ):
            with self.subTest(
                field=field,
                value=str(value),
                boundary="accepted",
            ):
                document = json.loads(json.dumps(base))
                document["default_determinism"][field] = value
                validator.validate(document)
                self.assertEqual(
                    getattr(load_blueprint_document(document).default_determinism, field),
                    value,
                )

        for field, value in (
            ("seed", -(2**63) - 1),
            ("clock", 2**63),
        ):
            with self.subTest(
                field=field,
                value=str(value),
                boundary="rejected",
            ):
                document = json.loads(json.dumps(base))
                document["default_determinism"][field] = value
                self.assertTrue(list(validator.iter_errors(document)))
                with self.assertRaises(BlueprintValidationError):
                    load_blueprint_document(document)


if __name__ == "__main__":
    unittest.main()
