"""Real SDK/subprocess CLI equivalence for the V2-2 authoring workflow."""

from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from lore2mud._bounded_json import DEFAULT_JSON_READ_LIMITS
from lore2mud.authoring import AgentAuthoringSDK
from lore2mud.authoring.contracts import (
    CreatorDecision,
    PublicInputDescriptor,
    TraceRecord,
    WorkspaceMetadataEntry,
)
from lore2mud.authoring.project import load_blueprint
from lore2mud.authoring.serialization import (
    authoring_result_to_document,
    blueprint_to_document,
    canonical_json_bytes,
    fingerprint_document,
    project_bytes,
    project_to_document,
    simulation_report_to_document,
    simulation_request_to_document,
)
from lore2mud.authoring.simulation import load_simulation_request


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "authoring"
BLUEPRINT = FIXTURES / "blueprint.json"
PROJECT_INPUTS = FIXTURES / "project_inputs.json"
REQUEST = FIXTURES / "simulation_request.json"
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


def _cli_subprocess_command(arguments: tuple[str, ...]) -> list[str]:
    try:
        for argument in arguments:
            argument.encode("utf-8")
    except UnicodeEncodeError:
        # POSIX argv cannot carry lone UTF-16 surrogates. Rehydrate the exact
        # arguments inside a child interpreter, then run the same CLI entry point.
        encoded_arguments = json.dumps(
            ["author", *arguments],
            ensure_ascii=True,
            separators=(",", ":"),
        )
        runner = (
            "import json; "
            "from lore2mud.cli import main; "
            f"raise SystemExit(main(json.loads({encoded_arguments!r})))"
        )
        return [sys.executable, "-c", runner]
    return [sys.executable, "-m", "lore2mud", "author", *arguments]


def _run_cli(*arguments: str) -> tuple[subprocess.CompletedProcess[bytes], object]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")
    completed = subprocess.run(
        _cli_subprocess_command(arguments),
        cwd=ROOT,
        env=environment,
        capture_output=True,
        check=False,
    )
    document = json.loads(completed.stdout.decode("utf-8"))
    return completed, document


def _typed_project_inputs():
    return {
        "public_inputs": (
            PublicInputDescriptor(
                artifact_id="public_fixture_brief",
                media_type="application/json",
                label="Public fixture brief",
            ),
        ),
        "creator_decisions": (
            CreatorDecision(
                decision_id="keep_opening_public",
                statement="Use only the original public fixture content.",
            ),
        ),
        "trace_records": (
            TraceRecord(
                trace_id="trace_public_opening",
                source_artifact_id="public_fixture_brief",
                target_artifact_id="public_fixture_project",
                decision_id="keep_opening_public",
            ),
        ),
        "workspace_metadata": (
            WorkspaceMetadataEntry(key="proofing_zoom", value="125"),
        ),
    }


class AuthoringEndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        schemas, registry = _schema_registry()
        result_schema = schemas[
            "https://github.com/lore2mud/lore2mud/schemas/authoring_result.schema.json"
        ]
        Draft202012Validator.check_schema(result_schema)
        cls.result_validator = Draft202012Validator(result_schema, registry=registry)

    def _assert_equivalent(self, direct_result, cli_result: object) -> None:
        direct_document = authoring_result_to_document(direct_result)
        self.assertEqual(cli_result, direct_document)
        self.assertEqual(canonical_json_bytes(cli_result), canonical_json_bytes(direct_document))
        self.result_validator.validate(cli_result)

    def test_real_sdk_and_subprocess_cli_workflow_are_byte_equivalent(self) -> None:
        sdk = AgentAuthoringSDK()
        blueprint = load_blueprint(BLUEPRINT)
        with tempfile.TemporaryDirectory() as directory:
            artifacts = Path(directory)
            project_path = artifacts / "project.json"
            preview_path = artifacts / "preview.json"
            report_path = artifacts / "report.json"
            replay_path = artifacts / "replay.json"
            proof_path = artifacts / "proof.json"

            direct_project = sdk.create_project(
                project_id="public_fixture_project",
                blueprint=blueprint,
                content_root=CONTENT,
                **_typed_project_inputs(),
            )
            process, cli_project = _run_cli(
                "create-project",
                "--project-id",
                "public_fixture_project",
                "--blueprint",
                str(BLUEPRINT),
                "--content",
                str(CONTENT),
                "--project-inputs",
                str(PROJECT_INPUTS),
                "--output",
                str(project_path),
            )
            self.assertEqual((process.returncode, process.stderr), (0, b""))
            self._assert_equivalent(direct_project, cli_project)
            assert direct_project.artifact is not None
            self.assertEqual(project_path.read_bytes(), project_bytes(direct_project.artifact))

            direct_validation = sdk.validate_project(direct_project.artifact)
            process, cli_validation = _run_cli(
                "validate", "--project", str(project_path)
            )
            self.assertEqual((process.returncode, process.stderr), (0, b""))
            self._assert_equivalent(direct_validation, cli_validation)

            direct_preview = sdk.build_preview(direct_project.artifact)
            process, cli_preview = _run_cli(
                "preview",
                "--project",
                str(project_path),
                "--output",
                str(preview_path),
            )
            self.assertEqual((process.returncode, process.stderr), (0, b""))
            self._assert_equivalent(direct_preview, cli_preview)
            self.assertEqual(
                preview_path.read_bytes(),
                canonical_json_bytes(cli_preview["artifact"]),
            )

            request = load_simulation_request(REQUEST)
            direct_report = sdk.simulate(direct_project.artifact, request)
            process, cli_report = _run_cli(
                "simulate",
                "--project",
                str(project_path),
                "--request",
                str(REQUEST),
                "--output",
                str(report_path),
            )
            self.assertEqual((process.returncode, process.stderr), (0, b""))
            self._assert_equivalent(direct_report, cli_report)
            self.assertEqual(
                report_path.read_bytes(),
                canonical_json_bytes(cli_report["artifact"]),
            )

            assert direct_report.artifact is not None
            direct_replay = sdk.replay(direct_project.artifact, direct_report.artifact)
            process, cli_replay = _run_cli(
                "replay",
                "--project",
                str(project_path),
                "--report",
                str(report_path),
                "--output",
                str(replay_path),
            )
            self.assertEqual((process.returncode, process.stderr), (0, b""))
            self._assert_equivalent(direct_replay, cli_replay)
            self.assertEqual(replay_path.read_bytes(), report_path.read_bytes())

            direct_proof = sdk.proof(direct_project.artifact)
            process, cli_proof = _run_cli(
                "proof",
                "--project",
                str(project_path),
                "--output",
                str(proof_path),
            )
            self.assertEqual((process.returncode, process.stderr), (0, b""))
            self._assert_equivalent(direct_proof, cli_proof)
            self.assertEqual(
                proof_path.read_bytes(),
                canonical_json_bytes(cli_proof["artifact"]),
            )

    def test_real_cli_rejects_schema_overlength_request_text_before_simulation(self) -> None:
        sdk = AgentAuthoringSDK()
        project_result = sdk.create_project(
            project_id="request_boundary_project",
            blueprint=load_blueprint(BLUEPRINT),
            content_root=CONTENT,
        )
        self.assertTrue(project_result.ok)
        assert project_result.artifact is not None

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project_path = root / "project.json"
            project_path.write_bytes(project_bytes(project_result.artifact))
            base = json.loads(REQUEST.read_text("utf-8"))

            target = json.loads(json.dumps(base))
            target["intents"][0]["target"] = "x" * 200 + " "

            direction = json.loads(json.dumps(base))
            direction["intents"][1]["direction"] = "e" * 32 + " "

            slot = json.loads(json.dumps(base))
            slot["intents"] = [{"type": "save", "slot": "s" * 32 + " "}]
            slot["checkpoint_after_steps"] = [0, 1]

            for name, document in (
                ("target", target),
                ("direction", direction),
                ("slot", slot),
            ):
                with self.subTest(field=name):
                    request_path = root / f"request_{name}.json"
                    request_path.write_bytes(canonical_json_bytes(document))
                    process, result = _run_cli(
                        "simulate",
                        "--project",
                        str(project_path),
                        "--request",
                        str(request_path),
                    )
                    self.assertEqual((process.returncode, process.stderr), (1, b""))
                    self.assertEqual(result["status"], "rejected")
                    self.assertEqual(
                        result["diagnostics"][0]["code"],
                        "simulation_request_invalid",
                    )

    def test_invalid_project_id_sdk_and_cli_rejections_are_canonical_and_equivalent(
        self,
    ) -> None:
        sdk = AgentAuthoringSDK()
        blueprint = load_blueprint(BLUEPRINT)

        for project_id in ("   ", "\ud800"):
            with self.subTest(project_id=repr(project_id)):
                direct = sdk.create_project(
                    project_id=project_id,
                    blueprint=blueprint,
                    content_root=CONTENT,
                )
                process, cli_result = _run_cli(
                    "create-project",
                    "--project-id",
                    project_id,
                    "--blueprint",
                    str(BLUEPRINT),
                    "--content",
                    str(CONTENT),
                )

                self.assertEqual((process.returncode, process.stderr), (1, b""))
                self._assert_equivalent(direct, cli_result)
                self.assertEqual(direct.diagnostics[0].artifact_id, "project")

    def test_oversized_request_sdk_and_cli_rejections_are_equivalent(self) -> None:
        sdk = AgentAuthoringSDK()
        project_result = sdk.create_project(
            project_id="oversized_request_project",
            blueprint=load_blueprint(BLUEPRINT),
            content_root=CONTENT,
        )
        self.assertTrue(project_result.ok)
        assert project_result.artifact is not None
        request = replace(
            load_simulation_request(REQUEST),
            player_name="x" * (DEFAULT_JSON_READ_LIMITS.max_bytes + 1),
        )
        direct = sdk.simulate(project_result.artifact, request)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project_path = root / "project.json"
            request_path = root / "request.json"
            project_path.write_bytes(project_bytes(project_result.artifact))
            request_path.write_text(
                json.dumps(
                    simulation_request_to_document(request),
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            process, cli_result = _run_cli(
                "simulate",
                "--project",
                str(project_path),
                "--request",
                str(request_path),
            )

        self.assertEqual((process.returncode, process.stderr), (1, b""))
        self._assert_equivalent(direct, cli_result)
        self.assertEqual(
            direct.diagnostics[0].code,
            "authoring_input_too_large",
        )

    def test_typed_blueprint_integer_resource_failure_matches_real_cli(self) -> None:
        sdk = AgentAuthoringSDK()
        blueprint = load_blueprint(BLUEPRINT)
        unbounded = replace(
            blueprint,
            default_determinism=replace(
                blueprint.default_determinism,
                seed=10**DEFAULT_JSON_READ_LIMITS.max_integer_digits,
            ),
        )
        direct = sdk.create_project(
            project_id="unbounded_blueprint_project",
            blueprint=unbounded,
            content_root=CONTENT,
        )

        with tempfile.TemporaryDirectory() as directory:
            blueprint_path = Path(directory) / "blueprint.json"
            blueprint_path.write_bytes(
                canonical_json_bytes(blueprint_to_document(unbounded))
            )
            process, cli_result = _run_cli(
                "create-project",
                "--project-id",
                "unbounded_blueprint_project",
                "--blueprint",
                str(blueprint_path),
                "--content",
                str(CONTENT),
            )

        self.assertEqual((process.returncode, process.stderr), (1, b""))
        self._assert_equivalent(direct, cli_result)
        self.assertEqual(direct.diagnostics[0].code, "authoring_input_invalid_json")
        self.assertEqual(direct.diagnostics[0].artifact_id, "blueprint")

    def test_typed_project_integer_resource_failures_match_real_cli(self) -> None:
        sdk = AgentAuthoringSDK()
        project_result = sdk.create_project(
            project_id="unbounded_project",
            blueprint=load_blueprint(BLUEPRINT),
            content_root=CONTENT,
        )
        self.assertTrue(project_result.ok)
        assert project_result.artifact is not None
        project = project_result.artifact
        request = load_simulation_request(REQUEST)
        report_result = sdk.simulate(project, request)
        self.assertTrue(report_result.ok)
        assert report_result.artifact is not None
        report = report_result.artifact
        unbounded = replace(
            project,
            blueprint=replace(
                project.blueprint,
                default_determinism=replace(
                    project.blueprint.default_determinism,
                    clock=10**DEFAULT_JSON_READ_LIMITS.max_integer_digits,
                ),
            ),
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project_path = root / "project.json"
            report_path = root / "report.json"
            project_path.write_bytes(
                canonical_json_bytes(project_to_document(unbounded))
            )
            report_path.write_bytes(
                canonical_json_bytes(simulation_report_to_document(report))
            )
            cases = (
                (
                    sdk.validate_project(unbounded),
                    ("validate", "--project", str(project_path)),
                ),
                (
                    sdk.build_preview(unbounded),
                    ("preview", "--project", str(project_path)),
                ),
                (
                    sdk.simulate(unbounded, request),
                    (
                        "simulate",
                        "--project",
                        str(project_path),
                        "--request",
                        str(REQUEST),
                    ),
                ),
                (
                    sdk.replay(unbounded, report),
                    (
                        "replay",
                        "--project",
                        str(project_path),
                        "--report",
                        str(report_path),
                    ),
                ),
                (
                    sdk.proof(unbounded),
                    ("proof", "--project", str(project_path)),
                ),
            )
            for direct, arguments in cases:
                with self.subTest(operation=direct.operation):
                    process, cli_result = _run_cli(*arguments)
                    self.assertEqual((process.returncode, process.stderr), (1, b""))
                    self._assert_equivalent(direct, cli_result)
                    self.assertEqual(
                        direct.diagnostics[0].code,
                        "authoring_input_invalid_json",
                    )
                    self.assertEqual(direct.diagnostics[0].artifact_id, "project")

    def test_typed_report_integer_resource_failure_matches_real_cli(self) -> None:
        sdk = AgentAuthoringSDK()
        project_result = sdk.create_project(
            project_id="unbounded_report_project",
            blueprint=load_blueprint(BLUEPRINT),
            content_root=CONTENT,
        )
        self.assertTrue(project_result.ok)
        assert project_result.artifact is not None
        project = project_result.artifact
        report_result = sdk.simulate(project, load_simulation_request(REQUEST))
        self.assertTrue(report_result.ok)
        assert report_result.artifact is not None
        unbounded = replace(
            report_result.artifact,
            seed=10**DEFAULT_JSON_READ_LIMITS.max_integer_digits,
        )
        direct = sdk.replay(project, unbounded)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project_path = root / "project.json"
            report_path = root / "report.json"
            project_path.write_bytes(project_bytes(project))
            report_path.write_bytes(
                canonical_json_bytes(simulation_report_to_document(unbounded))
            )
            process, cli_result = _run_cli(
                "replay",
                "--project",
                str(project_path),
                "--report",
                str(report_path),
            )

        self.assertEqual((process.returncode, process.stderr), (1, b""))
        self._assert_equivalent(direct, cli_result)
        self.assertEqual(direct.diagnostics[0].code, "authoring_input_invalid_json")
        self.assertEqual(direct.diagnostics[0].artifact_id, "report")

    def test_real_cli_rejects_report_schema_blank_player_name(self) -> None:
        sdk = AgentAuthoringSDK()
        project_result = sdk.create_project(
            project_id="report_boundary_project",
            blueprint=load_blueprint(BLUEPRINT),
            content_root=CONTENT,
        )
        self.assertTrue(project_result.ok)
        assert project_result.artifact is not None
        report_result = sdk.simulate(
            project_result.artifact,
            load_simulation_request(REQUEST),
        )
        self.assertTrue(report_result.ok)
        assert report_result.artifact is not None
        document = simulation_report_to_document(report_result.artifact)
        document["player_name"] = "   "
        document["fingerprint"] = fingerprint_document(
            {key: value for key, value in document.items() if key != "fingerprint"}
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project_path = root / "project.json"
            report_path = root / "report.json"
            project_path.write_bytes(project_bytes(project_result.artifact))
            report_path.write_bytes(canonical_json_bytes(document))
            process, result = _run_cli(
                "replay",
                "--project",
                str(project_path),
                "--report",
                str(report_path),
            )

        self.assertEqual((process.returncode, process.stderr), (1, b""))
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(
            result["diagnostics"][0]["code"],
            "simulation_report_invalid",
        )

    def test_capability_guard_is_identical_for_sdk_and_cli_before_simulation(self) -> None:
        sdk = AgentAuthoringSDK()
        blocked_blueprint = replace(
            load_blueprint(BLUEPRINT),
            capability_requirement_ids=("future_capability",),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            blocked_blueprint_path = root / "blueprint.json"
            blocked_project_path = root / "project.json"
            blocked_blueprint_path.write_bytes(
                canonical_json_bytes(
                    {
                        **json.loads(BLUEPRINT.read_text("utf-8")),
                        "capability_requirement_ids": ["future_capability"],
                    }
                )
            )
            direct_project = sdk.create_project(
                project_id="blocked_project",
                blueprint=blocked_blueprint,
                content_root=CONTENT,
            )
            process, _cli_project = _run_cli(
                "create-project",
                "--project-id",
                "blocked_project",
                "--blueprint",
                str(blocked_blueprint_path),
                "--content",
                str(CONTENT),
                "--output",
                str(blocked_project_path),
            )
            self.assertEqual((process.returncode, process.stderr), (0, b""))
            assert direct_project.artifact is not None

            direct_preview = sdk.build_preview(direct_project.artifact)
            process, cli_preview = _run_cli(
                "preview", "--project", str(blocked_project_path)
            )
            self.assertEqual((process.returncode, process.stderr), (1, b""))
            self._assert_equivalent(direct_preview, cli_preview)
            self.assertEqual(
                cli_preview["diagnostics"][0]["code"],
                "capability_requirement_unsupported_v2_2",
            )

            direct_simulation = sdk.simulate(
                direct_project.artifact,
                load_simulation_request(REQUEST),
            )
            process, cli_simulation = _run_cli(
                "simulate",
                "--project",
                str(blocked_project_path),
                "--request",
                str(REQUEST),
            )
            self.assertEqual((process.returncode, process.stderr), (1, b""))
            self._assert_equivalent(direct_simulation, cli_simulation)


if __name__ == "__main__":
    unittest.main()
