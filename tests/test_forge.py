"""Tests for the resumable public Forge workbench."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

import pipeline.forge as forge

from lore2mud.content.loader import load_content_pack
from pipeline.forge import (
    ForgeExecutionError,
    ForgeValidationError,
    ForgeWorkspace,
    _WorkspaceLock,
    _load_state,
    _write_state,
    forge_workspace_to_document,
    initialize_forge_workspace,
    inspect_forge_workspace,
    load_forge_workspace,
    main,
    run_forge_workspace,
    validate_forge_state,
    validate_forge_workspace,
)
from pipeline.registry_inspection import (
    validate_registry_inspection_report_document,
)


REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "examples" / "forge_workbench"


def _read_json(path: Path) -> object:
    with open(path, "r", encoding="utf-8") as stream:
        return json.load(stream)


def _stage(report: dict[str, object], name: str) -> dict[str, object]:
    stages = report["stages"]
    assert isinstance(stages, list)
    return next(stage for stage in stages if stage["stage"] == name)


class WorkspaceValidationTests(unittest.TestCase):
    def _document(self) -> dict[str, object]:
        document = _read_json(TEMPLATE / "forge-workspace.json")
        assert isinstance(document, dict)
        return document

    def test_valid_manifest_is_frozen_and_canonical(self) -> None:
        workspace = validate_forge_workspace(self._document())
        self.assertIsInstance(workspace, ForgeWorkspace)
        self.assertEqual(workspace.workspace_id, "forge_registry_demo")
        self.assertEqual(forge_workspace_to_document(workspace), self._document())

    def test_root_version_id_and_unknown_fields_are_strict(self) -> None:
        for mutation in (
            lambda value: value.update(extra=True),
            lambda value: value.update(format_version=True),
            lambda value: value.update(format_version=2),
            lambda value: value.update(workspace_id="Forge Demo"),
        ):
            with self.subTest(mutation=mutation):
                document = self._document()
                mutation(document)
                with self.assertRaises(ForgeValidationError):
                    validate_forge_workspace(document)
        with self.assertRaises(ForgeValidationError):
            validate_forge_workspace([])

    def test_unsafe_and_nonnormal_paths_are_rejected(self) -> None:
        for value in (
            "../registry.json",
            "inputs//registry.json",
            "inputs/./registry.json",
            "/absolute/registry.json",
            "inputs\\registry.json",
        ):
            with self.subTest(value=value):
                document = self._document()
                document["source_registry"] = value
                with self.assertRaises(ForgeValidationError):
                    validate_forge_workspace(document)

    def test_inputs_must_be_distinct_and_outside_artifact_root(self) -> None:
        document = self._document()
        document["inspection_plan"] = document["source_registry"]
        with self.assertRaises(ForgeValidationError):
            validate_forge_workspace(document)
        document = self._document()
        document["source_registry"] = "artifacts/registry.json"
        with self.assertRaises(ForgeValidationError):
            validate_forge_workspace(document)

    def test_serializer_rejects_wrong_type(self) -> None:
        with self.assertRaises(TypeError):
            forge_workspace_to_document({})  # type: ignore[arg-type]


class ForgeWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.parent = Path(self._temporary.name)
        self.workspace = self.parent / "workspace"
        initialize_forge_workspace(self.workspace, TEMPLATE)

    def tearDown(self) -> None:
        self._temporary.cleanup()

    def test_init_creates_a_ready_workspace_without_generated_state(self) -> None:
        report = inspect_forge_workspace(self.workspace)
        self.assertEqual(report["overall_status"], "READY")
        self.assertEqual(
            [_stage(report, name)["status"] for name in ("inspection", "adaptation")],
            ["READY", "READY"],
        )
        self.assertTrue((self.workspace / "artifacts").is_dir())
        self.assertFalse((self.workspace / ".forge").exists())
        self.assertEqual(
            (self.workspace / "inputs" / "canon_registry.json").read_bytes(),
            (TEMPLATE / "inputs" / "canon_registry.json").read_bytes(),
        )

    def test_init_refuses_existing_target(self) -> None:
        with self.assertRaises(ForgeExecutionError):
            initialize_forge_workspace(self.workspace, TEMPLATE)

    def test_init_rejects_a_target_inside_the_template(self) -> None:
        template_copy = self.parent / "template"
        initialize_forge_workspace(template_copy, TEMPLATE)
        with self.assertRaises(ForgeValidationError):
            initialize_forge_workspace(template_copy / "nested", template_copy)

    def test_template_symlink_is_rejected_when_supported(self) -> None:
        template = self.parent / "unsafe-template"
        initialize_forge_workspace(template, TEMPLATE)
        link = template / "linked.json"
        try:
            os.symlink(template / "forge-workspace.json", link)
        except OSError as exc:
            self.skipTest(f"symbolic links unavailable: {exc}")
        target = self.parent / "from-unsafe-template"
        with self.assertRaises(ForgeValidationError):
            initialize_forge_workspace(target, template)

    def test_first_run_publishes_valid_report_pack_and_state(self) -> None:
        inputs_before = {
            path.relative_to(self.workspace).as_posix(): path.read_bytes()
            for path in (
                self.workspace / "inputs" / "canon_registry.json",
                self.workspace / "plans" / "registry_inspection_plan.json",
                self.workspace / "plans" / "registry_adaptation_plan.json",
            )
        }
        report, succeeded = run_forge_workspace(self.workspace)
        self.assertTrue(succeeded)
        self.assertEqual(report["overall_status"], "CURRENT")

        inspection = _stage(report, "inspection")
        inspection_output = self.workspace / inspection["outputs"][0]["path"]
        validate_registry_inspection_report_document(_read_json(inspection_output))

        adaptation = _stage(report, "adaptation")
        adaptation_output = self.workspace / adaptation["outputs"][0]["path"]
        pack = load_content_pack(adaptation_output)
        self.assertEqual(pack.id, "registry_micro_demo")

        state = _read_json(self.workspace / ".forge" / "state.json")
        self.assertEqual(
            validate_forge_state(state, "forge_registry_demo"), state
        )
        self.assertEqual(
            inputs_before,
            {
                path.relative_to(self.workspace).as_posix(): path.read_bytes()
                for path in (
                    self.workspace / "inputs" / "canon_registry.json",
                    self.workspace / "plans" / "registry_inspection_plan.json",
                    self.workspace / "plans" / "registry_adaptation_plan.json",
                )
            },
        )

    def test_resume_skips_current_stages_without_rewriting_state(self) -> None:
        run_forge_workspace(self.workspace)
        state_path = self.workspace / ".forge" / "state.json"
        state_before = state_path.read_bytes()
        report, succeeded = run_forge_workspace(self.workspace)
        self.assertTrue(succeeded)
        self.assertEqual(state_path.read_bytes(), state_before)
        self.assertEqual(
            [(action["stage"], action["action"]) for action in report["actions"]],
            [("inspection", "skipped"), ("adaptation", "skipped")],
        )

    def test_forced_rerun_preserves_prior_output_and_bytes(self) -> None:
        first, _ = run_forge_workspace(self.workspace, stages=("adaptation",))
        first_record = _stage(first, "adaptation")["outputs"][0]
        first_path = self.workspace / first_record["path"]
        second, succeeded = run_forge_workspace(
            self.workspace, stages=("adaptation",), force=True
        )
        self.assertTrue(succeeded)
        second_record = _stage(second, "adaptation")["outputs"][0]
        second_path = self.workspace / second_record["path"]
        self.assertNotEqual(first_path, second_path)
        self.assertTrue(first_path.is_dir())
        self.assertTrue(second_path.is_dir())
        self.assertEqual(first_record["sha256"], second_record["sha256"])
        self.assertEqual(_stage(second, "adaptation")["attempts"], 2)

    def test_failed_attempt_retains_last_success_and_reason(self) -> None:
        first, _ = run_forge_workspace(self.workspace, stages=("adaptation",))
        first_record = copy.deepcopy(_stage(first, "adaptation")["outputs"][0])
        plan_path = self.workspace / "plans" / "registry_adaptation_plan.json"
        original = plan_path.read_bytes()
        document = _read_json(plan_path)
        assert isinstance(document, dict)
        document["format_version"] = 2
        plan_path.write_text(json.dumps(document), encoding="utf-8")

        failed, succeeded = run_forge_workspace(
            self.workspace, stages=("adaptation",)
        )
        self.assertFalse(succeeded)
        stage = _stage(failed, "adaptation")
        self.assertEqual(stage["status"], "FAILED")
        self.assertIn("format_version", stage["reason"])
        self.assertEqual(stage["outputs"], [first_record])
        self.assertTrue((self.workspace / first_record["path"]).is_dir())

        plan_path.write_bytes(original)
        restored = inspect_forge_workspace(self.workspace)
        self.assertEqual(_stage(restored, "adaptation")["status"], "CURRENT")

    def test_changed_valid_input_creates_a_new_success(self) -> None:
        first, _ = run_forge_workspace(self.workspace, stages=("adaptation",))
        first_record = _stage(first, "adaptation")["outputs"][0]
        plan_path = self.workspace / "plans" / "registry_adaptation_plan.json"
        document = _read_json(plan_path)
        assert isinstance(document, dict)
        document["pack"]["name"] = "Registry Micro Demo Revised"
        plan_path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        stale = inspect_forge_workspace(self.workspace)
        self.assertEqual(_stage(stale, "adaptation")["status"], "STALE")
        second, succeeded = run_forge_workspace(
            self.workspace, stages=("adaptation",)
        )
        self.assertTrue(succeeded)
        second_record = _stage(second, "adaptation")["outputs"][0]
        self.assertNotEqual(first_record["path"], second_record["path"])
        self.assertTrue((self.workspace / first_record["path"]).exists())
        self.assertEqual(
            load_content_pack(self.workspace / second_record["path"]).name,
            "Registry Micro Demo Revised",
        )

    def test_missing_input_is_blocked_and_run_records_failure(self) -> None:
        plan = self.workspace / "plans" / "registry_inspection_plan.json"
        plan.unlink()
        report = inspect_forge_workspace(self.workspace)
        self.assertEqual(_stage(report, "inspection")["status"], "BLOCKED")
        failed, succeeded = run_forge_workspace(
            self.workspace, stages=("inspection",)
        )
        self.assertFalse(succeeded)
        self.assertEqual(_stage(failed, "inspection")["status"], "FAILED")
        self.assertIn("FileNotFoundError", _stage(failed, "inspection")["reason"])

    def test_semantically_invalid_input_is_blocked_before_run(self) -> None:
        plan = self.workspace / "plans" / "registry_inspection_plan.json"
        plan.write_text("[]\n", encoding="utf-8")
        report = inspect_forge_workspace(self.workspace)
        stage = _stage(report, "inspection")
        self.assertEqual(stage["status"], "BLOCKED")
        self.assertIn("RegistryInspectionValidationError", stage["reason"])

    def test_modified_successful_output_is_stale(self) -> None:
        report, _ = run_forge_workspace(self.workspace, stages=("inspection",))
        output = self.workspace / _stage(report, "inspection")["outputs"][0]["path"]
        output.write_bytes(output.read_bytes() + b" ")
        stale = inspect_forge_workspace(self.workspace)
        stage = _stage(stale, "inspection")
        self.assertEqual(stage["status"], "STALE")
        self.assertIn("changed", stage["reason"])

    def test_hardlink_input_alias_is_rejected(self) -> None:
        registry = self.workspace / "inputs" / "canon_registry.json"
        plan = self.workspace / "plans" / "registry_inspection_plan.json"
        plan.unlink()
        try:
            os.link(registry, plan)
        except OSError as exc:
            self.skipTest(f"hard links unavailable: {exc}")
        with self.assertRaises(ForgeValidationError):
            inspect_forge_workspace(self.workspace)

    def test_symlink_input_is_rejected_when_supported(self) -> None:
        plan = self.workspace / "plans" / "registry_inspection_plan.json"
        original = self.parent / "plan.json"
        original.write_bytes(plan.read_bytes())
        plan.unlink()
        try:
            os.symlink(original, plan)
        except OSError as exc:
            self.skipTest(f"symbolic links unavailable: {exc}")
        with self.assertRaises(ForgeValidationError):
            inspect_forge_workspace(self.workspace)

    def test_windows_junction_reparse_point_is_rejected(self) -> None:
        with patch(
            "pipeline.forge.os.lstat",
            return_value=SimpleNamespace(st_file_attributes=0x400),
        ):
            with self.assertRaises(ForgeValidationError) as caught:
                load_forge_workspace(self.workspace)
        self.assertIn("junction", str(caught.exception))

    def test_workspace_lock_rejects_a_second_runner(self) -> None:
        loaded = load_forge_workspace(self.workspace)
        with _WorkspaceLock(loaded):
            with self.assertRaises(ForgeExecutionError):
                with _WorkspaceLock(loaded):
                    self.fail("second lock unexpectedly acquired")

    def test_state_replace_failure_preserves_previous_bytes(self) -> None:
        run_forge_workspace(self.workspace, stages=("inspection",))
        loaded = load_forge_workspace(self.workspace)
        state_path = self.workspace / ".forge" / "state.json"
        before = state_path.read_bytes()
        state = copy.deepcopy(_load_state(loaded))
        state["stages"]["inspection"]["attempts"] = 2
        with patch("pipeline.forge.os.replace", side_effect=OSError("blocked")):
            with self.assertRaises(OSError):
                _write_state(loaded, state)
        self.assertEqual(state_path.read_bytes(), before)
        self.assertEqual(list((self.workspace / ".forge").glob(".state.*.tmp")), [])

    def test_state_outputs_must_stay_under_their_stage_run_root(self) -> None:
        run_forge_workspace(self.workspace, stages=("inspection",))
        loaded = load_forge_workspace(self.workspace)
        state = copy.deepcopy(_load_state(loaded))
        state["stages"]["inspection"]["last_success"]["outputs"][0]["path"] = (
            "inputs/canon_registry.json"
        )
        with self.assertRaises(ForgeValidationError) as caught:
            _write_state(loaded, state)
        self.assertIn("inspection_runs", str(caught.exception))

    def test_input_fingerprint_is_recomputed_after_stage_execution(self) -> None:
        original_writer = forge.write_registry_inspection_report
        plan = self.workspace / "plans" / "registry_inspection_plan.json"

        def write_then_change(compiled: object, output: Path) -> None:
            original_writer(compiled, output)  # type: ignore[arg-type]
            plan.write_bytes(plan.read_bytes() + b" ")

        with patch(
            "pipeline.forge.write_registry_inspection_report",
            side_effect=write_then_change,
        ):
            report, succeeded = run_forge_workspace(
                self.workspace, stages=("inspection",)
            )
        self.assertFalse(succeeded)
        self.assertEqual(_stage(report, "inspection")["outputs"], [])
        state = _load_state(load_forge_workspace(self.workspace))
        failure = state["stages"]["inspection"]["last_run"]
        self.assertEqual(failure["status"], "failed")
        self.assertIn("changed during execution", failure["error"])
        self.assertEqual(
            list((self.workspace / "artifacts" / "inspection_runs").iterdir()), []
        )


class SchemaTests(unittest.TestCase):
    def test_schemas_declare_strict_draft_2020_12_contracts(self) -> None:
        workspace_schema = _read_json(REPO / "schemas" / "forge_workspace.schema.json")
        state_schema = _read_json(REPO / "schemas" / "forge_state.schema.json")
        for schema in (workspace_schema, state_schema):
            self.assertEqual(
                schema["$schema"], "https://json-schema.org/draft/2020-12/schema"
            )
            self.assertFalse(schema["additionalProperties"])
            self.assertIsInstance(schema["required"], list)
            self.assertIsInstance(schema["$defs"], dict)
        validate_forge_workspace(_read_json(TEMPLATE / "forge-workspace.json"))

    def test_generated_state_matches_the_python_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "workspace"
            initialize_forge_workspace(workspace_path, TEMPLATE)
            run_forge_workspace(workspace_path)
            loaded = load_forge_workspace(workspace_path)
            self.assertEqual(
                validate_forge_state(
                    _read_json(workspace_path / ".forge" / "state.json"),
                    loaded.config.workspace_id,
                    loaded.config.artifact_root,
                ),
                _read_json(workspace_path / ".forge" / "state.json"),
            )


class CliTests(unittest.TestCase):
    def test_subprocess_cli_completes_the_public_end_to_end_loop(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "workspace"
            commands = (
                ("init", str(workspace), "--template", str(TEMPLATE)),
                ("status", str(workspace), "--json"),
                ("run", str(workspace), "--json"),
                ("check", str(workspace), "--json"),
            )
            completed: list[subprocess.CompletedProcess[str]] = []
            for arguments in commands:
                result = subprocess.run(
                    [sys.executable, "-m", "pipeline.forge", *arguments],
                    cwd=REPO,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                completed.append(result)
            self.assertEqual(json.loads(completed[1].stdout)["overall_status"], "READY")
            self.assertEqual(json.loads(completed[2].stdout)["overall_status"], "CURRENT")
            self.assertEqual(json.loads(completed[3].stdout)["overall_status"], "CURRENT")

    def test_check_returns_one_until_outputs_are_current(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "workspace"
            initialize_forge_workspace(workspace, TEMPLATE)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["check", str(workspace)]), 1)
            run_forge_workspace(workspace)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["check", str(workspace)]), 0)

    def test_invalid_workspace_returns_one_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self.assertEqual(main(["status", temp_dir]), 1)
            self.assertIn("missing forge-workspace.json", stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())

    def test_missing_cli_arguments_exit_two(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                main(["run"])
        self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
