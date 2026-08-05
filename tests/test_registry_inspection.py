"""Tests for deterministic read-only CanonRegistry inspection reports."""

from __future__ import annotations

import contextlib
import copy
import inspect
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from unittest.mock import patch

from pipeline.canon_registry import (
    CanonRegistry,
    canon_registry_to_document,
    validate_canon_registry_document,
)
from pipeline.registry_inspection import (
    RegistryInspectionBuildError,
    RegistryInspectionPlan,
    RegistryInspectionValidationError,
    compile_registry_inspection,
    main,
    registry_inspection_plan_to_document,
    registry_inspection_report_to_document,
    validate_registry_inspection_plan,
    validate_registry_inspection_report_document,
    write_registry_inspection_report,
)


REPO = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO / "tests" / "fixtures" / "canon_registry" / "expected_registry.json"
FIXTURE_DIR = REPO / "tests" / "fixtures" / "registry_inspection"


def _read_json(path: Path) -> object:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _registry_document() -> dict:
    document = _read_json(REGISTRY_PATH)
    assert isinstance(document, dict)
    return document


def _registry() -> CanonRegistry:
    return validate_canon_registry_document(_registry_document())


def _plan_document() -> dict:
    document = _read_json(FIXTURE_DIR / "valid_plan.json")
    assert isinstance(document, dict)
    return document


def _plan() -> RegistryInspectionPlan:
    return validate_registry_inspection_plan(_plan_document())


def _report():
    return compile_registry_inspection(_registry(), _plan())


def _report_document() -> dict:
    document = registry_inspection_report_to_document(_report())
    assert isinstance(document, dict)
    return document


def _entity(document: dict, entity_id: str) -> dict:
    return next(item for item in document["entities"] if item["entity_id"] == entity_id)


class PlanValidationTests(unittest.TestCase):
    def test_valid_plan_is_frozen_and_canonical(self) -> None:
        plan = _plan()
        self.assertEqual(plan.entity_refs, ("canon_mira",))
        self.assertEqual(registry_inspection_plan_to_document(plan), _plan_document())
        with self.assertRaises(FrozenInstanceError):
            plan.inspection_id = "changed"  # type: ignore[misc]

    def test_root_must_be_object_and_unknown_fields_are_rejected(self) -> None:
        with self.assertRaises(RegistryInspectionValidationError):
            validate_registry_inspection_plan([])
        document = _plan_document()
        document["extra"] = True
        with self.assertRaises(RegistryInspectionValidationError):
            validate_registry_inspection_plan(document)

    def test_bool_and_version_matrix_is_rejected(self) -> None:
        for field, value in (
            ("format_version", True),
            ("format_version", 2),
            ("source_registry_version", False),
            ("source_registry_version", 0),
        ):
            with self.subTest(field=field, value=value):
                document = _plan_document()
                document[field] = value
                with self.assertRaises(RegistryInspectionValidationError):
                    validate_registry_inspection_plan(document)

    def test_entity_refs_must_be_nonempty_stable_and_unique(self) -> None:
        for refs in ([], ["Canon_Mira"], ["canon_mira", "canon_mira"], "canon_mira"):
            with self.subTest(refs=refs):
                document = _plan_document()
                document["entity_refs"] = refs
                with self.assertRaises(RegistryInspectionValidationError):
                    validate_registry_inspection_plan(document)

    def test_entity_refs_are_sorted_deterministically(self) -> None:
        document = _plan_document()
        document["entity_refs"] = ["canon_valley_gate", "canon_glass_tower"]
        plan = validate_registry_inspection_plan(document)
        self.assertEqual(
            plan.entity_refs, ("canon_glass_tower", "canon_valley_gate")
        )

    def test_plan_serializer_rejects_wrong_type(self) -> None:
        with self.assertRaises(TypeError):
            registry_inspection_plan_to_document({})  # type: ignore[arg-type]


class CompilationTests(unittest.TestCase):
    def test_exact_selected_entity_and_claim_sources_are_copied(self) -> None:
        registry = _registry()
        report = compile_registry_inspection(registry, _plan())
        source_entity = next(
            entity for entity in registry.entities if entity.entity_id == "canon_mira"
        )
        self.assertEqual(report.entities, (source_entity,))
        self.assertEqual(report.selected_entity_refs, ("canon_mira",))
        self.assertEqual(
            [source.promotion_id for source in report.sources],
            ["promo_ch001", "promo_ch002"],
        )
        self.assertEqual(len(report.entities[0].members), 2)
        self.assertEqual(len(report.entities[0].claims), 4)

    def test_conflicting_claims_and_unselected_relation_targets_are_preserved(self) -> None:
        report = _report()
        role_values = [
            claim.value.enum_value
            for claim in report.entities[0].claims
            if claim.predicate == "role"
        ]
        relation_targets = [
            claim.value.entity_ref
            for claim in report.entities[0].claims
            if claim.predicate == "home"
        ]
        self.assertEqual(role_values, ["watcher", "guardian"])
        self.assertEqual(relation_targets, ["canon_glass_tower", "canon_valley_gate"])
        self.assertEqual(report.selected_entity_refs, ("canon_mira",))

    def test_registry_identity_and_version_must_match(self) -> None:
        for field, value in (
            ("source_registry_id", "other_registry"),
            ("source_registry_version", 2),
        ):
            with self.subTest(field=field):
                plan = replace(_plan(), **{field: value})
                with self.assertRaises(RegistryInspectionBuildError):
                    compile_registry_inspection(_registry(), plan)

    def test_unknown_entity_is_rejected(self) -> None:
        plan = replace(_plan(), entity_refs=("canon_missing",))
        with self.assertRaises(RegistryInspectionBuildError) as caught:
            compile_registry_inspection(_registry(), plan)
        self.assertIn("unknown registry entity", str(caught.exception))

    def test_wrong_types_are_rejected(self) -> None:
        with self.assertRaises(RegistryInspectionBuildError):
            compile_registry_inspection({}, _plan())  # type: ignore[arg-type]
        with self.assertRaises(RegistryInspectionBuildError):
            compile_registry_inspection(_registry(), {})  # type: ignore[arg-type]

    def test_malformed_typed_dataclass_members_do_not_leak_type_errors(self) -> None:
        malformed_registry = replace(_registry(), entities=("bad",))  # type: ignore[arg-type]
        with self.assertRaises(RegistryInspectionBuildError):
            compile_registry_inspection(malformed_registry, _plan())
        malformed_plan = replace(_plan(), entity_refs=("canon_mira", 1))  # type: ignore[arg-type]
        with self.assertRaises(RegistryInspectionBuildError):
            compile_registry_inspection(_registry(), malformed_plan)

    def test_noncanonical_plan_and_registry_are_rejected(self) -> None:
        multi_document = _plan_document()
        multi_document["entity_refs"] = ["canon_mira", "canon_glass_tower"]
        canonical_plan = validate_registry_inspection_plan(multi_document)
        noncanonical_plan = replace(
            canonical_plan, entity_refs=tuple(reversed(canonical_plan.entity_refs))
        )
        with self.assertRaises(RegistryInspectionBuildError):
            compile_registry_inspection(_registry(), noncanonical_plan)

        registry = _registry()
        noncanonical_registry = replace(
            registry, entities=tuple(reversed(registry.entities))
        )
        with self.assertRaises(RegistryInspectionBuildError):
            compile_registry_inspection(noncanonical_registry, canonical_plan)

    def test_multiple_selection_is_sorted_and_sources_are_deduplicated(self) -> None:
        document = _plan_document()
        document["entity_refs"] = ["canon_mira", "canon_glass_tower"]
        report = compile_registry_inspection(
            _registry(), validate_registry_inspection_plan(document)
        )
        self.assertEqual(
            report.selected_entity_refs, ("canon_glass_tower", "canon_mira")
        )
        self.assertEqual(
            [entity.entity_id for entity in report.entities],
            ["canon_glass_tower", "canon_mira"],
        )
        self.assertEqual(len(report.sources), 2)

    def test_one_chapter_selection_includes_only_its_claim_source(self) -> None:
        document = _plan_document()
        document["entity_refs"] = ["canon_glass_tower"]
        report = compile_registry_inspection(
            _registry(), validate_registry_inspection_plan(document)
        )
        self.assertEqual(
            [source.promotion_id for source in report.sources], ["promo_ch001"]
        )

    def test_entity_without_claims_produces_an_empty_source_subset(self) -> None:
        document = _registry_document()
        _entity(document, "canon_glass_tower")["claims"] = []
        registry = validate_canon_registry_document(document)
        plan_document = _plan_document()
        plan_document["entity_refs"] = ["canon_glass_tower"]
        report = compile_registry_inspection(
            registry, validate_registry_inspection_plan(plan_document)
        )
        self.assertEqual(report.sources, ())
        self.assertEqual(report.entities[0].claims, ())
        self.assertEqual(
            validate_registry_inspection_report_document(
                registry_inspection_report_to_document(report)
            ),
            report,
        )

    def test_compilation_does_not_mutate_registry_document(self) -> None:
        document = _registry_document()
        before = copy.deepcopy(document)
        registry = validate_canon_registry_document(document)
        compile_registry_inspection(registry, _plan())
        self.assertEqual(document, before)
        self.assertEqual(canon_registry_to_document(registry), before)


class ReportValidationTests(unittest.TestCase):
    def test_round_trip_and_frozen_model(self) -> None:
        report = _report()
        self.assertEqual(
            validate_registry_inspection_report_document(
                registry_inspection_report_to_document(report)
            ),
            report,
        )
        with self.assertRaises(FrozenInstanceError):
            report.inspection_id = "changed"  # type: ignore[misc]

    def test_root_bool_unknown_and_wrong_type_are_rejected(self) -> None:
        with self.assertRaises(RegistryInspectionValidationError):
            validate_registry_inspection_report_document([])
        for field, value in (("format_version", True), ("source_registry_version", False)):
            document = _report_document()
            document[field] = value
            with self.assertRaises(RegistryInspectionValidationError):
                validate_registry_inspection_report_document(document)
        document = _report_document()
        document["extra"] = "no"
        with self.assertRaises(RegistryInspectionValidationError):
            validate_registry_inspection_report_document(document)

    def test_selected_refs_must_exactly_cover_entities(self) -> None:
        for refs in ([], ["canon_missing"], ["canon_mira", "canon_mira"]):
            with self.subTest(refs=refs):
                document = _report_document()
                document["selected_entity_refs"] = refs
                with self.assertRaises(RegistryInspectionValidationError):
                    validate_registry_inspection_report_document(document)

    def test_sources_must_exactly_cover_claim_promotions(self) -> None:
        document = _report_document()
        document["sources"].pop()
        with self.assertRaises(RegistryInspectionValidationError):
            validate_registry_inspection_report_document(document)

        document = _report_document()
        extra = copy.deepcopy(document["sources"][0])
        extra.update(
            promotion_id="promo_extra",
            chapter_id="chapter_000003",
            chapter_sha256="c" * 64,
            review_id="review_extra",
        )
        document["sources"].append(extra)
        with self.assertRaises(RegistryInspectionValidationError):
            validate_registry_inspection_report_document(document)

    def test_claim_chapter_must_match_source_record(self) -> None:
        document = _report_document()
        document["entities"][0]["claims"][0]["source_chapters"] = [
            "chapter_000002"
        ]
        with self.assertRaises(RegistryInspectionValidationError):
            validate_registry_inspection_report_document(document)

    def test_claim_must_match_member_and_composite_sources_are_unique(self) -> None:
        document = _report_document()
        document["entities"][0]["claims"][0]["source"][
            "source_entity_id"
        ] = "source_other"
        with self.assertRaises(RegistryInspectionValidationError):
            validate_registry_inspection_report_document(document)

        document = _report_document()
        document["entities"][0]["claims"].append(
            copy.deepcopy(document["entities"][0]["claims"][0])
        )
        with self.assertRaises(RegistryInspectionValidationError):
            validate_registry_inspection_report_document(document)

    def test_entity_member_and_alias_integrity(self) -> None:
        document = _report_document()
        document["entities"][0]["aliases"].append("MIRA")
        with self.assertRaises(RegistryInspectionValidationError):
            validate_registry_inspection_report_document(document)

        document = _report_document()
        duplicate = copy.deepcopy(document["entities"][0]["members"][0])
        duplicate["source_entity_id"] = "source_other"
        duplicate["source_candidate_id"] = "candidate_other"
        document["entities"][0]["members"].append(duplicate)
        with self.assertRaises(RegistryInspectionValidationError):
            validate_registry_inspection_report_document(document)

        document = _report_document()
        duplicate = copy.deepcopy(document["entities"][0]["members"][0])
        duplicate["source_entity_id"] = "source_other"
        document["entities"][0]["members"].append(duplicate)
        with self.assertRaises(RegistryInspectionValidationError):
            validate_registry_inspection_report_document(document)

    def test_claim_value_and_inference_contracts_are_strict(self) -> None:
        document = _report_document()
        document["entities"][0]["claims"][0]["value"] = {
            "kind": "numeric",
            "number": True,
            "unit": None,
        }
        with self.assertRaises(RegistryInspectionValidationError):
            validate_registry_inspection_report_document(document)

        document = _report_document()
        document["entities"][0]["claims"][0]["inference_basis"] = "not allowed"
        with self.assertRaises(RegistryInspectionValidationError):
            validate_registry_inspection_report_document(document)

        document = _report_document()
        inferred = next(
            claim
            for claim in document["entities"][0]["claims"]
            if claim["source_support"] == "inferred"
        )
        inferred["inference_basis"] = None
        with self.assertRaises(RegistryInspectionValidationError):
            validate_registry_inspection_report_document(document)

    def test_unknown_nested_fields_and_duplicate_entity_ids_are_rejected(self) -> None:
        document = _report_document()
        document["entities"][0]["extra"] = True
        with self.assertRaises(RegistryInspectionValidationError):
            validate_registry_inspection_report_document(document)

        document = _report_document()
        document["entities"].append(copy.deepcopy(document["entities"][0]))
        with self.assertRaises(RegistryInspectionValidationError):
            validate_registry_inspection_report_document(document)

    def test_all_collection_orders_are_normalized(self) -> None:
        plan_document = _plan_document()
        plan_document["entity_refs"] = ["canon_mira", "canon_glass_tower"]
        report = compile_registry_inspection(
            _registry(), validate_registry_inspection_plan(plan_document)
        )
        document = registry_inspection_report_to_document(report)
        document["selected_entity_refs"].reverse()
        document["sources"].reverse()
        document["entities"].reverse()
        mira = _entity(document, "canon_mira")
        mira["aliases"].reverse()
        mira["members"].reverse()
        mira["claims"].reverse()
        self.assertEqual(validate_registry_inspection_report_document(document), report)

    def test_report_serializer_rejects_wrong_type(self) -> None:
        with self.assertRaises(TypeError):
            registry_inspection_report_to_document({})  # type: ignore[arg-type]


class SchemaAndGoldenTests(unittest.TestCase):
    def _schema(self, name: str) -> dict:
        document = _read_json(REPO / "schemas" / name)
        assert isinstance(document, dict)
        return document

    def test_schemas_are_draft_2020_12_and_strict(self) -> None:
        for name in (
            "registry_inspection_plan.schema.json",
            "registry_inspection_report.schema.json",
        ):
            schema = self._schema(name)
            self.assertEqual(
                schema["$schema"], "https://json-schema.org/draft/2020-12/schema"
            )
            self.assertFalse(schema["additionalProperties"])

    def test_plan_and_report_cardinality_contracts(self) -> None:
        plan = self._schema("registry_inspection_plan.schema.json")
        report = self._schema("registry_inspection_report.schema.json")
        self.assertEqual(plan["properties"]["entity_refs"]["minItems"], 1)
        self.assertTrue(plan["properties"]["entity_refs"]["uniqueItems"])
        self.assertEqual(report["properties"]["selected_entity_refs"]["minItems"], 1)
        self.assertNotIn("minItems", report["properties"]["sources"])
        self.assertEqual(report["properties"]["entities"]["minItems"], 1)

    def test_report_nested_defs_match_canon_registry_contract(self) -> None:
        report = self._schema("registry_inspection_report.schema.json")
        registry = self._schema("canon_registry.schema.json")
        for name in (
            "stable_id",
            "non_blank",
            "source",
            "member",
            "claim_source",
            "canon_value",
            "claim",
            "entity",
        ):
            self.assertEqual(report["$defs"][name], registry["$defs"][name])

    def test_golden_document_validates_and_matches_compiler(self) -> None:
        expected = _read_json(FIXTURE_DIR / "expected_report.json")
        self.assertEqual(validate_registry_inspection_report_document(expected), _report())
        self.assertEqual(registry_inspection_report_to_document(_report()), expected)

    def test_golden_bytes_are_stable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "report.json"
            write_registry_inspection_report(_report(), output)
            self.assertEqual(
                output.read_bytes(), (FIXTURE_DIR / "expected_report.json").read_bytes()
            )


class WriterTests(unittest.TestCase):
    def test_writer_returns_resolved_path_and_fsyncs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "report.json"
            with patch("pipeline.registry_inspection.os.fsync") as fsync:
                result = write_registry_inspection_report(_report(), output)
            self.assertEqual(result, output.resolve())
            fsync.assert_called_once()

    def test_replace_failure_preserves_existing_output_and_cleans_temp(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "report.json"
            output.write_bytes(b"old\n")
            with patch(
                "pipeline.registry_inspection.os.replace",
                side_effect=OSError("blocked"),
            ):
                with self.assertRaises(OSError):
                    write_registry_inspection_report(_report(), output)
            self.assertEqual(output.read_bytes(), b"old\n")
            self.assertEqual(list(Path(temp_dir).glob(".report.json.*.tmp")), [])

    def test_prevalidation_happens_before_temp_creation(self) -> None:
        invalid = replace(_report(), selected_entity_refs=("canon_missing",))
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("pipeline.registry_inspection.tempfile.mkstemp") as mkstemp:
                with self.assertRaises(RegistryInspectionValidationError):
                    write_registry_inspection_report(
                        invalid, Path(temp_dir) / "report.json"
                    )
            mkstemp.assert_not_called()

    def test_missing_parent_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(FileNotFoundError):
                write_registry_inspection_report(
                    _report(), Path(temp_dir) / "missing" / "report.json"
                )

    def test_malformed_typed_report_does_not_leak_attribute_error(self) -> None:
        malformed = replace(_report(), entities=("bad",))  # type: ignore[arg-type]
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(RegistryInspectionValidationError):
                write_registry_inspection_report(
                    malformed, Path(temp_dir) / "report.json"
                )

    def test_writer_contains_open_flush_fsync_and_replace(self) -> None:
        source = inspect.getsource(write_registry_inspection_report)
        for token in ("os.fdopen", "handle.flush()", "os.fsync", "os.replace"):
            self.assertIn(token, source)


class CliTests(unittest.TestCase):
    def _args(self, output: Path) -> list[str]:
        return [
            "--canon-registry",
            str(REGISTRY_PATH),
            "--inspection-plan",
            str(FIXTURE_DIR / "valid_plan.json"),
            "--output",
            str(output),
        ]

    def test_in_process_cli_matches_golden_and_preserves_inputs(self) -> None:
        registry_before = REGISTRY_PATH.read_bytes()
        plan_before = (FIXTURE_DIR / "valid_plan.json").read_bytes()
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "report.json"
            self.assertEqual(main(self._args(output)), 0)
            self.assertEqual(
                output.read_bytes(), (FIXTURE_DIR / "expected_report.json").read_bytes()
            )
        self.assertEqual(REGISTRY_PATH.read_bytes(), registry_before)
        self.assertEqual((FIXTURE_DIR / "valid_plan.json").read_bytes(), plan_before)

    def test_subprocess_cli_matches_golden(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "report.json"
            completed = subprocess.run(
                [sys.executable, "-m", "pipeline.registry_inspection", *self._args(output)],
                cwd=REPO,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(
                output.read_bytes(), (FIXTURE_DIR / "expected_report.json").read_bytes()
            )

    def test_missing_arguments_exit_two(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                main(["--canon-registry", str(REGISTRY_PATH)])
        self.assertEqual(caught.exception.code, 2)

    def test_bad_json_and_invalid_documents_return_one_without_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            bad = temp / "bad.json"
            bad.write_text("{", encoding="utf-8")
            output = temp / "out.json"
            args = self._args(output)
            args[args.index(str(FIXTURE_DIR / "valid_plan.json"))] = str(bad)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(args), 1)
            self.assertFalse(output.exists())

            bad.write_text("[]\n", encoding="utf-8")
            args = self._args(output)
            args[args.index(str(REGISTRY_PATH))] = str(bad)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(args), 1)
            self.assertFalse(output.exists())

    def test_output_direct_aliases_are_rejected_before_reading(self) -> None:
        for input_path in (REGISTRY_PATH, FIXTURE_DIR / "valid_plan.json"):
            with self.subTest(input_name=input_path.name):
                stderr = io.StringIO()
                with contextlib.redirect_stderr(stderr):
                    self.assertEqual(main(self._args(input_path)), 1)
                self.assertIn("points to an input file", stderr.getvalue())

    def test_output_hardlink_aliases_are_rejected_and_inputs_unchanged(self) -> None:
        for source_name in ("registry.json", "plan.json"):
            with self.subTest(source_name=source_name), tempfile.TemporaryDirectory() as td:
                temp = Path(td)
                registry = temp / "registry.json"
                plan = temp / "plan.json"
                registry.write_bytes(REGISTRY_PATH.read_bytes())
                plan.write_bytes((FIXTURE_DIR / "valid_plan.json").read_bytes())
                source = registry if source_name == "registry.json" else plan
                output = temp / "output.json"
                try:
                    os.link(source, output)
                except OSError as exc:
                    self.skipTest(f"hard links unavailable: {exc}")
                before = source.read_bytes()
                args = [
                    "--canon-registry",
                    str(registry),
                    "--inspection-plan",
                    str(plan),
                    "--output",
                    str(output),
                ]
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(main(args), 1)
                self.assertEqual(source.read_bytes(), before)
                self.assertEqual(output.read_bytes(), before)

    def test_output_symlink_alias_is_rejected_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            temp = Path(td)
            registry = temp / "registry.json"
            plan = temp / "plan.json"
            registry.write_bytes(REGISTRY_PATH.read_bytes())
            plan.write_bytes((FIXTURE_DIR / "valid_plan.json").read_bytes())
            output = temp / "output.json"
            try:
                os.symlink(registry, output)
            except OSError as exc:
                self.skipTest(f"symbolic links unavailable: {exc}")
            before = registry.read_bytes()
            args = [
                "--canon-registry",
                str(registry),
                "--inspection-plan",
                str(plan),
                "--output",
                str(output),
            ]
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(args), 1)
            self.assertEqual(registry.read_bytes(), before)

    def test_input_alias_is_rejected_before_parsing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            same = Path(temp_dir) / "same.json"
            same.write_text("not json", encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                result = main(
                    [
                        "--canon-registry",
                        str(same),
                        "--inspection-plan",
                        str(same),
                        "--output",
                        str(Path(temp_dir) / "out.json"),
                    ]
                )
            self.assertEqual(result, 1)
            self.assertIn("Input paths point to the same file", stderr.getvalue())

    def test_existing_unrelated_output_is_atomically_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "report.json"
            output.write_bytes(b"old\n")
            self.assertEqual(main(self._args(output)), 0)
            self.assertEqual(
                output.read_bytes(), (FIXTURE_DIR / "expected_report.json").read_bytes()
            )

    def test_missing_output_parent_returns_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "missing" / "report.json"
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(self._args(output)), 1)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
