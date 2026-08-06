from __future__ import annotations

from dataclasses import replace
import inspect
import json
from pathlib import Path
import tempfile
import unittest
from typing import cast
from unittest import mock

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from lore2mud._bounded_json import DEFAULT_JSON_READ_LIMITS
from lore2mud.application import (
    DeterminismContext,
    GameSession,
    LoadIntent,
    SaveIntent,
)
from lore2mud.authoring.contracts import (
    AcceptanceScenario,
    AdaptationBoundaries,
    ApprovalRecord,
    ConditionOutcome,
    GameBlueprint,
    PlayLength,
    SimulationRequest,
    WorkspaceMetadataEntry,
)
from lore2mud.authoring.preview import build_preview
from lore2mud.authoring.project import create_game_project
from lore2mud.authoring.serialization import (
    authoring_result_to_document,
    canonical_json_bytes,
    fingerprint_document,
    preview_to_document,
    project_to_document,
    simulation_report_to_document,
)
from lore2mud.authoring.sdk import AgentAuthoringSDK
from lore2mud.authoring.simulation import (
    SimulationValidationError,
    load_simulation_report_document,
    load_simulation_request,
    load_simulation_request_document,
    replay_report,
    simulate_preview,
    simulate_project,
)
from lore2mud.content import load_content_pack
from lore2mud.engine.save import SaveLoadService


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_CONTENT = ROOT / "examples" / "original_demo"
REQUEST_PATH = ROOT / "tests" / "fixtures" / "authoring" / "simulation_request.json"


def _blueprint(*, capabilities: tuple[str, ...] = ()) -> GameBlueprint:
    return GameBlueprint(
        format_version=1,
        blueprint_id="simulation_blueprint",
        title="Public Simulation",
        approval=ApprovalRecord(True, "approval_simulation", "product_owner"),
        audience="general",
        genre="fantasy",
        tone="hopeful",
        play_length=PlayLength(5, 10, 20),
        adaptation_boundaries=AdaptationBoundaries(
            ("public-safe original content",),
            ("private source content",),
        ),
        required_game_loops=("explore",),
        acceptance_scenarios=(
            AcceptanceScenario("reach_path", "Reach the public path", ConditionOutcome.WIN),
        ),
        capability_requirement_ids=capabilities,
        asset_requirements=(),
        provenance_requirements=("public_safe",),
        rights_assertions=("original_content",),
        default_determinism=DeterminismContext(7, 11),
    )


def _project(*, capabilities: tuple[str, ...] = ()):
    return create_game_project(
        project_id="simulation_project",
        blueprint=_blueprint(capabilities=capabilities),
        content_root=PUBLIC_CONTENT,
    )


def _schema_registry() -> tuple[dict[str, object], Registry]:
    schemas = {
        document["$id"]: document
        for path in (ROOT / "schemas").glob("*.schema.json")
        for document in [json.loads(path.read_text("utf-8"))]
        if "$id" in document
    }
    return schemas, Registry().with_resources(
        (uri, Resource.from_contents(document)) for uri, document in schemas.items()
    )


class SimulationTests(unittest.TestCase):
    def test_simulation_is_deterministic_replayable_and_schema_valid(self) -> None:
        project = _project()
        request = load_simulation_request(REQUEST_PATH)
        first = simulate_project(project, request)
        second = simulate_project(project, request)

        self.assertTrue(first.ok)
        self.assertEqual(first, second)
        report = first.artifact
        assert report is not None
        self.assertTrue(report.replay_verified)
        self.assertEqual(report.turns, report.witness_trace)
        self.assertNotEqual(report.initial_state_sha256, report.final_state_sha256)
        self.assertTrue(all(checkpoint.equivalent for checkpoint in report.checkpoints))
        self.assertEqual(report.outcome.value, "win")
        self.assertEqual(load_simulation_report_document(simulation_report_to_document(report)), report)
        self.assertEqual(replay_report(project, report).artifact, report)

        schemas, registry = _schema_registry()
        request_schema = schemas[
            "https://github.com/lore2mud/lore2mud/schemas/simulation_request.schema.json"
        ]
        report_schema = schemas[
            "https://github.com/lore2mud/lore2mud/schemas/simulation_report.schema.json"
        ]
        Draft202012Validator.check_schema(request_schema)
        Draft202012Validator.check_schema(report_schema)
        Draft202012Validator(request_schema, registry=registry).validate(
            json.loads(REQUEST_PATH.read_text("utf-8"))
        )
        Draft202012Validator(report_schema, registry=registry).validate(
            simulation_report_to_document(report)
        )

    def test_simulation_does_not_mutate_project_preview_or_active_session(self) -> None:
        project = _project()
        preview_result = build_preview(project)
        preview = preview_result.artifact
        assert preview is not None
        request = load_simulation_request(REQUEST_PATH)
        project_before = canonical_json_bytes(project_to_document(project))
        preview_before = canonical_json_bytes(preview_to_document(preview))

        source_before = {
            item.name: (PUBLIC_CONTENT / item.name).read_bytes()
            for item in project.content_files
        }
        active_context = DeterminismContext(99, 123)
        with tempfile.TemporaryDirectory() as directory:
            pack = load_content_pack(PUBLIC_CONTENT)
            save_service = SaveLoadService(pack, Path(directory))
            active_session = GameSession.from_content_pack(
                pack,
                save_service,
                determinism=active_context,
            )
            saved = active_session.submit(SaveIntent("active_player"))
            self.assertEqual(saved.status.value, "accepted")
            active_save_path = save_service.slot_path("active_player")
            active_save = active_save_path.read_bytes()
            active_view = active_session.view()
            active_sequence = active_session.event_sequence
            active_rng = active_session._rng.getstate()

            result = simulate_preview(preview, request)

            self.assertTrue(result.ok)
            self.assertEqual(active_session.view(), active_view)
            self.assertEqual(active_session.event_sequence, active_sequence)
            self.assertEqual(active_session._rng.getstate(), active_rng)
            self.assertIs(active_session.determinism, active_context)
            self.assertEqual(active_save_path.read_bytes(), active_save)

        self.assertEqual(project_before, canonical_json_bytes(project_to_document(project)))
        self.assertEqual(preview_before, canonical_json_bytes(preview_to_document(preview)))
        self.assertEqual(
            source_before,
            {
                item.name: (PUBLIC_CONTENT / item.name).read_bytes()
                for item in project.content_files
            },
        )

    def test_main_witness_runs_request_only_and_evidence_uses_typed_persistence(self) -> None:
        project = _project()
        request = load_simulation_request(REQUEST_PATH)
        submitted: list[type[object]] = []
        original_submit = GameSession.submit

        def tracking_submit(session: GameSession, intent):
            submitted.append(type(intent))
            return original_submit(session, intent)

        with mock.patch.object(GameSession, "submit", new=tracking_submit):
            result = simulate_project(project, request)

        self.assertTrue(result.ok)
        self.assertEqual(
            submitted[: len(request.intents)],
            [type(intent) for intent in request.intents],
        )
        self.assertIn(SaveIntent, submitted)
        self.assertIn(LoadIntent, submitted)
        import lore2mud.authoring.simulation as simulation_module

        self.assertNotIn("_serialize_world", inspect.getsource(simulation_module))

    def test_capability_guard_precedes_request_validation(self) -> None:
        project = _project(capabilities=("v2_dynamic_story",))
        invalid_request = SimulationRequest(
            format_version=2,
            seed=0,
            clock=0,
            player_name="Simulator",
            intents=(),
        )
        result = simulate_project(project, invalid_request)
        self.assertFalse(result.ok)
        self.assertEqual(
            [diagnostic.code for diagnostic in result.diagnostics],
            ["capability_requirement_unsupported_v2_2"],
        )
        self.assertEqual(result.diagnostics[0].stage.value, "preview")

    def test_workspace_metadata_cannot_change_report_content_or_fingerprint(self) -> None:
        project = _project()
        request = load_simulation_request(REQUEST_PATH)
        changed = replace(
            project,
            workspace_metadata=(
                WorkspaceMetadataEntry("layout", "graph"),
                WorkspaceMetadataEntry("zoom", "175"),
            ),
        )

        baseline = simulate_project(project, request)
        with_metadata = simulate_project(changed, request)

        self.assertTrue(baseline.ok)
        self.assertEqual(baseline, with_metadata)

    def test_typed_sdk_rejects_non_scalar_request_text_with_transport_envelope(self) -> None:
        request = replace(
            load_simulation_request(REQUEST_PATH),
            player_name="\ud800",
        )

        result = AgentAuthoringSDK().simulate(_project(), request)

        self.assertFalse(result.ok)
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.operation, "simulate")
        self.assertEqual(result.diagnostics[0].stage.value, "serialization")
        self.assertEqual(result.diagnostics[0].code, "authoring_input_too_complex")
        self.assertEqual(result.diagnostics[0].artifact_id, "simulation_request")

    def test_typed_sdk_normalizes_request_resource_limit_failures(self) -> None:
        request = load_simulation_request(REQUEST_PATH)
        nested: object = "expected"
        for _ in range(DEFAULT_JSON_READ_LIMITS.max_depth + 1):
            nested = [nested]
        deep_condition = replace(
            request.conditions[0],
            expected=cast(str | bool, nested),
        )
        wide_condition = replace(
            request.conditions[0],
            expected=cast(
                str | bool,
                [False] * DEFAULT_JSON_READ_LIMITS.max_nodes,
            ),
        )
        cases = (
            (
                replace(
                    request,
                    player_name="x"
                    * (DEFAULT_JSON_READ_LIMITS.max_string_chars + 1),
                ),
                "authoring_input_too_complex",
            ),
            (
                replace(
                    request,
                    player_name="x" * (DEFAULT_JSON_READ_LIMITS.max_bytes + 1),
                ),
                "authoring_input_too_large",
            ),
            (
                replace(request, conditions=(deep_condition,)),
                "authoring_input_too_complex",
            ),
            (
                replace(request, conditions=(wide_condition,)),
                "authoring_input_too_complex",
            ),
            (
                replace(request, seed=10**DEFAULT_JSON_READ_LIMITS.max_integer_digits),
                "authoring_input_invalid_json",
            ),
        )
        schemas, registry = _schema_registry()
        result_validator = Draft202012Validator(
            schemas[
                "https://github.com/lore2mud/lore2mud/schemas/authoring_result.schema.json"
            ],
            registry=registry,
        )
        sdk = AgentAuthoringSDK()
        project = _project()

        for limited_request, expected_code in cases:
            with self.subTest(code=expected_code):
                with (
                    mock.patch(
                        "lore2mud.authoring.simulation.build_preview",
                        side_effect=AssertionError(
                            "request resource rejection must precede preview build"
                        ),
                    ) as preview_builder,
                    mock.patch(
                        "lore2mud.authoring.simulation.load_preview_document",
                        side_effect=AssertionError(
                            "request resource rejection must precede preview load"
                        ),
                    ) as preview_loader,
                    mock.patch(
                        "lore2mud.authoring.simulation.materialized_preview_pack",
                        side_effect=AssertionError(
                            "request resource rejection must precede materialization"
                        ),
                    ) as preview_materializer,
                    mock.patch(
                        "lore2mud.authoring.simulation.GameSession.from_content_pack",
                        side_effect=AssertionError(
                            "request resource rejection must precede session creation"
                        ),
                    ) as session_builder,
                ):
                    result = sdk.simulate(project, limited_request)
                self.assertFalse(result.ok)
                self.assertIsNone(result.artifact)
                self.assertEqual(result.exit_code, 1)
                self.assertEqual(len(result.diagnostics), 1)
                self.assertEqual(result.diagnostics[0].code, expected_code)
                result_validator.validate(authoring_result_to_document(result))
                preview_builder.assert_not_called()
                preview_loader.assert_not_called()
                preview_materializer.assert_not_called()
                session_builder.assert_not_called()

        with mock.patch(
            "lore2mud.authoring.simulation.build_preview",
            side_effect=AssertionError(
                "request resource rejection must precede capability diagnostics"
            ),
        ) as preview_builder:
            blocked = sdk.simulate(
                _project(capabilities=("v2_dynamic_story",)),
                cases[0][0],
            )
        preview_builder.assert_not_called()
        self.assertEqual(
            blocked.diagnostics[0].code,
            "authoring_input_too_complex",
        )

        preview = build_preview(project).artifact
        assert preview is not None
        with (
            mock.patch(
                "lore2mud.authoring.simulation.load_preview_document",
                side_effect=AssertionError(
                    "request resource rejection must precede preview load"
                ),
            ) as preview_loader,
            mock.patch(
                "lore2mud.authoring.simulation.materialized_preview_pack",
                side_effect=AssertionError(
                    "request resource rejection must precede materialization"
                ),
            ) as preview_materializer,
            mock.patch(
                "lore2mud.authoring.simulation.GameSession.from_content_pack",
                side_effect=AssertionError(
                    "request resource rejection must precede session creation"
                ),
            ) as session_builder,
        ):
            direct = simulate_preview(preview, cases[1][0])
        self.assertEqual(direct.diagnostics[0].code, "authoring_input_too_large")
        preview_loader.assert_not_called()
        preview_materializer.assert_not_called()
        session_builder.assert_not_called()

    def test_project_resource_validation_follows_request_resource_preflight(self) -> None:
        project = _project()
        unbounded_project = replace(
            project,
            blueprint=replace(
                project.blueprint,
                default_determinism=replace(
                    project.blueprint.default_determinism,
                    seed=10**DEFAULT_JSON_READ_LIMITS.max_integer_digits,
                ),
            ),
        )
        request = load_simulation_request(REQUEST_PATH)

        with mock.patch(
            "lore2mud.authoring.simulation.build_preview",
            side_effect=AssertionError(
                "project resource rejection must precede preview construction"
            ),
        ) as preview_builder:
            project_rejection = AgentAuthoringSDK().simulate(
                unbounded_project,
                request,
            )
        self.assertEqual(
            project_rejection.diagnostics[0].code,
            "authoring_input_invalid_json",
        )
        self.assertEqual(project_rejection.diagnostics[0].artifact_id, "project")
        preview_builder.assert_not_called()

        unbounded_request = replace(
            request,
            player_name="x" * (DEFAULT_JSON_READ_LIMITS.max_bytes + 1),
        )
        with mock.patch(
            "lore2mud.authoring.simulation.validate_project",
            side_effect=AssertionError(
                "request resource rejection must precede project validation"
            ),
        ) as project_validator:
            request_rejection = AgentAuthoringSDK().simulate(
                unbounded_project,
                unbounded_request,
            )
        self.assertEqual(
            request_rejection.diagnostics[0].code,
            "authoring_input_too_large",
        )
        self.assertEqual(
            request_rejection.diagnostics[0].artifact_id,
            "simulation_request",
        )
        project_validator.assert_not_called()

    def test_simulation_request_schema_and_loader_reject_invalid_text(self) -> None:
        schemas, registry = _schema_registry()
        validator = Draft202012Validator(
            schemas[
                "https://github.com/lore2mud/lore2mud/schemas/"
                "simulation_request.schema.json"
            ],
            registry=registry,
        )
        base = json.loads(REQUEST_PATH.read_text("utf-8"))
        cases = []

        player_name = json.loads(json.dumps(base))
        player_name["player_name"] = "   "
        cases.append(player_name)

        target = json.loads(json.dumps(base))
        target["intents"][0]["target"] = "   "
        cases.append(target)

        direction = json.loads(json.dumps(base))
        direction["intents"][1]["direction"] = "   "
        cases.append(direction)

        slot = json.loads(json.dumps(base))
        slot["intents"] = [{"type": "save", "slot": "   "}]
        slot["checkpoint_after_steps"] = [0, 1]
        cases.append(slot)

        overlong_target = json.loads(json.dumps(base))
        overlong_target["intents"][0]["target"] = "x" * 200 + " "
        cases.append(overlong_target)

        overlong_direction = json.loads(json.dumps(base))
        overlong_direction["intents"][1]["direction"] = "e" * 32 + " "
        cases.append(overlong_direction)

        overlong_slot = json.loads(json.dumps(base))
        overlong_slot["intents"] = [{"type": "save", "slot": "s" * 32 + " "}]
        overlong_slot["checkpoint_after_steps"] = [0, 1]
        cases.append(overlong_slot)

        for index, document in enumerate(cases):
            with self.subTest(case=index):
                self.assertTrue(list(validator.iter_errors(document)))
                with self.assertRaises(SimulationValidationError):
                    load_simulation_request_document(document)

    def test_replay_rejects_tampered_report(self) -> None:
        project = _project()
        result = simulate_project(project, load_simulation_request(REQUEST_PATH))
        report = result.artifact
        assert report is not None
        tampered = replace(report, fingerprint="0" * 64)
        replayed = replay_report(project, tampered)
        self.assertFalse(replayed.ok)
        self.assertIsNone(replayed.artifact)
        self.assertEqual(replayed.diagnostics[0].code, "simulation_report_invalid")

    def test_report_schema_and_loader_reject_blank_player_name(self) -> None:
        result = simulate_project(_project(), load_simulation_request(REQUEST_PATH))
        report = result.artifact
        assert report is not None
        document = simulation_report_to_document(report)
        document["player_name"] = "   "
        document["fingerprint"] = fingerprint_document(
            {key: value for key, value in document.items() if key != "fingerprint"}
        )
        schemas, registry = _schema_registry()
        validator = Draft202012Validator(
            schemas[
                "https://github.com/lore2mud/lore2mud/schemas/"
                "simulation_report.schema.json"
            ],
            registry=registry,
        )

        self.assertTrue(list(validator.iter_errors(document)))
        with self.assertRaises(SimulationValidationError):
            load_simulation_report_document(document)

    def test_report_from_another_engine_version_is_rejected(self) -> None:
        result = simulate_project(_project(), load_simulation_request(REQUEST_PATH))
        report = result.artifact
        assert report is not None
        document = simulation_report_to_document(report)
        document["engine_version"] = "future-engine"
        document["fingerprint"] = fingerprint_document(
            {key: value for key, value in document.items() if key != "fingerprint"}
        )

        with self.assertRaisesRegex(SimulationValidationError, "engine_version"):
            load_simulation_report_document(document)

    def test_condition_expected_values_are_typed_by_kind(self) -> None:
        document = json.loads(REQUEST_PATH.read_text("utf-8"))
        document["conditions"] = [
            {
                "condition_id": "objective_main",
                "outcome": "win",
                "kind": "objective_status",
                "expected": "not_a_status",
            }
        ]
        with self.assertRaises(SimulationValidationError):
            load_simulation_request_document(document)

        document["conditions"] = [
            {
                "condition_id": "room_check",
                "outcome": "win",
                "kind": "room_id",
                "expected": "Room With Spaces",
            }
        ]
        with self.assertRaises(SimulationValidationError):
            load_simulation_request_document(document)


if __name__ == "__main__":
    unittest.main()
