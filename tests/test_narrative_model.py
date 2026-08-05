"""Tests for deterministic NarrativeModel v1 compilation."""

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
from pipeline.narrative_model import (
    NarrativeModelBuildError,
    NarrativeModelValidationError,
    NarrativePlan,
    compile_narrative_model,
    main,
    narrative_model_to_document,
    narrative_plan_to_document,
    validate_narrative_model_document,
    validate_narrative_plan_document,
    write_narrative_model,
)


REPO = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO / "tests" / "fixtures" / "canon_registry" / "expected_registry.json"
FIXTURE_DIR = REPO / "tests" / "fixtures" / "narrative_model"
PLAN_PATH = FIXTURE_DIR / "valid_plan.json"
MODEL_PATH = FIXTURE_DIR / "expected_model.json"


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
    document = _read_json(PLAN_PATH)
    assert isinstance(document, dict)
    return document


def _plan() -> NarrativePlan:
    return validate_narrative_plan_document(_plan_document())


def _model():
    return compile_narrative_model(_registry(), _plan())


def _model_document() -> dict:
    document = narrative_model_to_document(_model())
    assert isinstance(document, dict)
    return document


def _claim_ref(
    promotion_id: str, source_entity_id: str, source_claim_id: str
) -> dict[str, str]:
    return {
        "promotion_id": promotion_id,
        "source_entity_id": source_entity_id,
        "source_claim_id": source_claim_id,
    }


def _claim_key(value: dict) -> tuple[str, str, str]:
    return (
        value["promotion_id"],
        value["source_entity_id"],
        value["source_claim_id"],
    )


def _remove_claim(document: dict, claim_ref: dict[str, str]) -> None:
    key = _claim_key(claim_ref)
    document["scope"]["claim_uses"] = [
        value for value in document["scope"]["claim_uses"] if _claim_key(value) != key
    ]
    for proposition in document["propositions"]:
        proposition["claim_refs"] = [
            value
            for value in proposition["claim_refs"]
            if _claim_key(value) != key
        ]


def _all_claims_omitted_plan_document() -> dict:
    document = _plan_document()
    claim_uses = copy.deepcopy(document["scope"]["claim_uses"])
    document["scope"]["claim_uses"] = []
    document["scope"]["claim_omissions"] = [
        {
            "claim_ref": claim_ref,
            "reason": "This reviewed claim is outside the selected narrative cut.",
        }
        for claim_ref in claim_uses
    ]
    for proposition in document["propositions"]:
        proposition["claim_refs"] = []
        if proposition["status"] in {"canon_supported", "conflicted"}:
            proposition["status"] = "unknown"
    return document


class PlanValidationTests(unittest.TestCase):
    def test_valid_plan_is_frozen_and_canonical(self) -> None:
        plan = _plan()
        self.assertEqual(plan.model_id, "fixture_narrative")
        self.assertEqual(
            [beat.beat_id for beat in plan.beats],
            ["beat_arrival", "beat_reports", "beat_choice"],
        )
        self.assertEqual(narrative_plan_to_document(plan), _plan_document())
        with self.assertRaises(FrozenInstanceError):
            plan.model_id = "changed"  # type: ignore[misc]

    def test_root_and_versions_are_strict_true_integers(self) -> None:
        with self.assertRaises(NarrativeModelValidationError):
            validate_narrative_plan_document([])
        for field, value in (
            ("format_version", True),
            ("format_version", 1.0),
            ("format_version", 2),
        ):
            with self.subTest(field=field, value=value):
                document = _plan_document()
                document[field] = value
                with self.assertRaises(NarrativeModelValidationError):
                    validate_narrative_plan_document(document)
        for value in (True, 1.0, 0):
            with self.subTest(registry_version=value):
                document = _plan_document()
                document["source_registry"]["registry_version"] = value
                with self.assertRaises(NarrativeModelValidationError):
                    validate_narrative_plan_document(document)

    def test_unknown_fields_and_bad_stable_ids_are_rejected(self) -> None:
        document = _plan_document()
        document["extra"] = True
        with self.assertRaises(NarrativeModelValidationError):
            validate_narrative_plan_document(document)

        document = _plan_document()
        document["model_id"] = "Fixture-Narrative"
        with self.assertRaises(NarrativeModelValidationError):
            validate_narrative_plan_document(document)

        document = _plan_document()
        document["scope"]["claim_uses"][0]["source_claim_id"] = "claim-id"
        with self.assertRaises(NarrativeModelValidationError):
            validate_narrative_plan_document(document)

    def test_scope_requires_unique_uses_and_non_overlapping_omissions(self) -> None:
        for refs in ([], ["canon_mira", "canon_mira"], "canon_mira"):
            with self.subTest(entity_refs=refs):
                document = _plan_document()
                document["scope"]["entity_refs"] = refs
                with self.assertRaises(NarrativeModelValidationError):
                    validate_narrative_plan_document(document)

        document = _plan_document()
        document["scope"]["claim_uses"].append(
            copy.deepcopy(document["scope"]["claim_uses"][0])
        )
        with self.assertRaises(NarrativeModelValidationError):
            validate_narrative_plan_document(document)

        document = _plan_document()
        del document["scope"]["claim_uses"]
        with self.assertRaises(NarrativeModelValidationError):
            validate_narrative_plan_document(document)

        document = _plan_document()
        document["scope"]["claim_omissions"] = [
            {
                "claim_ref": copy.deepcopy(document["scope"]["claim_uses"][0]),
                "reason": "duplicate scope entry",
            }
        ]
        with self.assertRaises(NarrativeModelValidationError):
            validate_narrative_plan_document(document)

        document = _plan_document()
        document["scope"]["claim_omissions"] = [
            {
                "claim_ref": _claim_ref(
                    "promo_ch001", "source_tower", "claim_description"
                ),
                "reason": "   ",
            }
        ]
        with self.assertRaises(NarrativeModelValidationError):
            validate_narrative_plan_document(document)

    def test_proposition_status_claim_cardinality_is_enforced(self) -> None:
        cases = (
            ("prop_tower_setting", "claim_refs", []),
            (
                "prop_mira_home",
                "claim_refs",
                [_claim_ref("promo_ch001", "source_mira", "claim_home")],
            ),
            (
                "prop_open_question",
                "claim_refs",
                [_claim_ref("promo_ch001", "source_tower", "claim_description")],
            ),
            (
                "prop_player_goal",
                "claim_refs",
                [_claim_ref("promo_ch001", "source_tower", "claim_description")],
            ),
        )
        for proposition_id, field, value in cases:
            with self.subTest(proposition_id=proposition_id):
                document = _plan_document()
                proposition = next(
                    value
                    for value in document["propositions"]
                    if value["proposition_id"] == proposition_id
                )
                proposition[field] = value
                with self.assertRaises(NarrativeModelValidationError):
                    validate_narrative_plan_document(document)

    def test_cross_object_body_references_are_checked(self) -> None:
        document = _plan_document()
        document["perspectives"][0]["entity_ref"] = "canon_missing"
        with self.assertRaises(NarrativeModelValidationError):
            validate_narrative_plan_document(document)

        document = _plan_document()
        document["beats"][0]["phase_ref"] = "phase_missing"
        with self.assertRaises(NarrativeModelValidationError):
            validate_narrative_plan_document(document)

        document = _plan_document()
        document["beats"][0]["disclosures"][0]["perspective_ref"] = "perspective_gate"
        with self.assertRaises(NarrativeModelValidationError):
            validate_narrative_plan_document(document)

        document = _plan_document()
        document["beats"][0]["disclosures"][0]["proposition_ref"] = "prop_gate_setting"
        with self.assertRaises(NarrativeModelValidationError):
            validate_narrative_plan_document(document)

    def test_phases_and_beats_form_a_forward_dag(self) -> None:
        document = _plan_document()
        document["phases"][1]["sequence"] = 1
        with self.assertRaises(NarrativeModelValidationError):
            validate_narrative_plan_document(document)

        document = _plan_document()
        document["beats"][0]["predecessor_refs"] = ["beat_choice"]
        with self.assertRaises(NarrativeModelValidationError):
            validate_narrative_plan_document(document)

        document = _plan_document()
        document["beats"][2]["predecessor_refs"].append("beat_choice")
        with self.assertRaises(NarrativeModelValidationError):
            validate_narrative_plan_document(document)

        document = _plan_document()
        document["beats"][0]["predecessor_refs"] = ["beat_reports"]
        with self.assertRaises(NarrativeModelValidationError):
            validate_narrative_plan_document(document)

    def test_every_perspective_proposition_and_phase_must_be_used(self) -> None:
        document = _plan_document()
        document["beats"][2]["perspective_refs"] = ["perspective_mira"]
        document["beats"][2]["disclosures"] = [
            document["beats"][2]["disclosures"][1]
        ]
        with self.assertRaises(NarrativeModelValidationError):
            validate_narrative_plan_document(document)

        document = _plan_document()
        document["beats"][2]["proposition_refs"] = ["prop_gate_setting"]
        document["beats"][2]["disclosures"] = [
            document["beats"][2]["disclosures"][0]
        ]
        with self.assertRaises(NarrativeModelValidationError):
            validate_narrative_plan_document(document)

        document = _plan_document()
        document["beats"][2]["phase_ref"] = "phase_reports"
        with self.assertRaises(NarrativeModelValidationError):
            validate_narrative_plan_document(document)

    def test_plan_collection_order_is_normalized_deterministically(self) -> None:
        document = _plan_document()
        document["scope"]["entity_refs"].reverse()
        document["scope"]["claim_uses"].reverse()
        document["perspectives"].reverse()
        document["propositions"].reverse()
        document["phases"].reverse()
        document["beats"].reverse()
        for beat in document["beats"]:
            beat["predecessor_refs"].reverse()
            beat["perspective_refs"].reverse()
            beat["proposition_refs"].reverse()
            beat["disclosures"].reverse()
        self.assertEqual(
            narrative_plan_to_document(validate_narrative_plan_document(document)),
            _plan_document(),
        )

    def test_plan_serializer_rejects_wrong_type(self) -> None:
        with self.assertRaises(TypeError):
            narrative_plan_to_document({})  # type: ignore[arg-type]


class CompilationTests(unittest.TestCase):
    def test_compiler_binds_exact_provenance_and_matches_golden(self) -> None:
        model = _model()
        self.assertEqual(
            [source.promotion_id for source in model.source_registry.sources],
            ["promo_ch001", "promo_ch002"],
        )
        self.assertEqual(narrative_model_to_document(model), _read_json(MODEL_PATH))

    def test_all_scoped_claims_may_be_reasonedly_omitted(self) -> None:
        plan = validate_narrative_plan_document(_all_claims_omitted_plan_document())
        self.assertEqual(plan.scope.claim_uses, ())
        self.assertEqual(len(plan.scope.claim_omissions), 6)

        model = compile_narrative_model(_registry(), plan)
        self.assertEqual(model.scope.claim_uses, ())
        self.assertEqual(len(model.scope.claim_omissions), 6)
        self.assertEqual(
            [source.promotion_id for source in model.source_registry.sources],
            ["promo_ch001", "promo_ch002"],
        )
        self.assertEqual(
            validate_narrative_model_document(narrative_model_to_document(model)),
            model,
        )

    def test_registry_identity_and_version_must_match(self) -> None:
        for field, value in (("registry_id", "other_registry"), ("registry_version", 2)):
            with self.subTest(field=field):
                document = _plan_document()
                document["source_registry"][field] = value
                with self.assertRaises(NarrativeModelBuildError):
                    compile_narrative_model(
                        _registry(), validate_narrative_plan_document(document)
                    )

    def test_unknown_scoped_entity_is_rejected(self) -> None:
        document = _plan_document()
        document["scope"]["entity_refs"].append("canon_missing")
        with self.assertRaises(NarrativeModelBuildError) as caught:
            compile_narrative_model(
                _registry(), validate_narrative_plan_document(document)
            )
        self.assertIn("unknown registry entities", str(caught.exception))

    def test_every_scoped_claim_must_be_used_or_reasonedly_omitted(self) -> None:
        claim_ref = _claim_ref("promo_ch001", "source_tower", "claim_description")
        document = _plan_document()
        _remove_claim(document, claim_ref)
        tower_proposition = next(
            value
            for value in document["propositions"]
            if value["proposition_id"] == "prop_tower_setting"
        )
        tower_proposition["status"] = "unknown"
        with self.assertRaises(NarrativeModelBuildError) as caught:
            compile_narrative_model(
                _registry(), validate_narrative_plan_document(document)
            )
        self.assertIn("does not use or reasonedly omit", str(caught.exception))

        document = _plan_document()
        _remove_claim(document, claim_ref)
        tower_proposition = next(
            value
            for value in document["propositions"]
            if value["proposition_id"] == "prop_tower_setting"
        )
        tower_proposition["status"] = "unknown"
        document["scope"]["claim_omissions"] = [
            {"claim_ref": claim_ref, "reason": "The setting claim is outside this cut."}
        ]
        model = compile_narrative_model(
            _registry(), validate_narrative_plan_document(document)
        )
        self.assertEqual(len(model.scope.claim_omissions), 1)
        self.assertEqual(model.scope.claim_omissions[0].claim_ref.source_claim_id, "claim_description")

    def test_foreign_claim_provenance_is_rejected(self) -> None:
        document = _plan_document()
        original = _claim_ref("promo_ch001", "source_tower", "claim_description")
        replacement = _claim_ref("promo_ch001", "source_tower", "claim_missing")
        for value in document["scope"]["claim_uses"]:
            if _claim_key(value) == _claim_key(original):
                value.update(replacement)
        for proposition in document["propositions"]:
            for value in proposition["claim_refs"]:
                if _claim_key(value) == _claim_key(original):
                    value.update(replacement)
        with self.assertRaises(NarrativeModelBuildError) as caught:
            compile_narrative_model(
                _registry(), validate_narrative_plan_document(document)
            )
        self.assertIn("foreign registry claims", str(caught.exception))

    def test_scoped_entity_without_claims_is_rejected(self) -> None:
        document = _registry_document()
        tower = next(
            value for value in document["entities"] if value["entity_id"] == "canon_glass_tower"
        )
        tower["claims"] = []
        with self.assertRaises(NarrativeModelBuildError) as caught:
            compile_narrative_model(
                validate_canon_registry_document(document), _plan()
            )
        self.assertIn("has no claims", str(caught.exception))

    def test_malformed_typed_inputs_do_not_leak_type_errors(self) -> None:
        malformed_registry = replace(_registry(), entities=("bad",))  # type: ignore[arg-type]
        with self.assertRaises(NarrativeModelBuildError):
            compile_narrative_model(malformed_registry, _plan())

        malformed_plan = replace(_plan(), model_id=1)  # type: ignore[arg-type]
        with self.assertRaises(NarrativeModelBuildError):
            compile_narrative_model(_registry(), malformed_plan)

    def test_noncanonical_typed_inputs_are_rejected(self) -> None:
        plan = _plan()
        noncanonical_plan = replace(plan, perspectives=tuple(reversed(plan.perspectives)))
        with self.assertRaises(NarrativeModelBuildError):
            compile_narrative_model(_registry(), noncanonical_plan)

        registry = _registry()
        noncanonical_registry = replace(registry, entities=tuple(reversed(registry.entities)))
        with self.assertRaises(NarrativeModelBuildError):
            compile_narrative_model(noncanonical_registry, plan)

    def test_compilation_does_not_mutate_input_registry_document(self) -> None:
        document = _registry_document()
        before = copy.deepcopy(document)
        registry = validate_canon_registry_document(document)
        compile_narrative_model(registry, _plan())
        self.assertEqual(document, before)
        self.assertEqual(canon_registry_to_document(registry), before)


class ModelValidationTests(unittest.TestCase):
    def test_round_trip_is_frozen_and_canonical(self) -> None:
        model = _model()
        self.assertEqual(
            validate_narrative_model_document(narrative_model_to_document(model)), model
        )
        with self.assertRaises(FrozenInstanceError):
            model.model_id = "changed"  # type: ignore[misc]

    def test_source_snapshot_exactly_covers_scoped_claim_promotions(self) -> None:
        document = _model_document()
        document["source_registry"]["sources"].pop()
        with self.assertRaises(NarrativeModelValidationError):
            validate_narrative_model_document(document)

        document = _model_document()
        extra = copy.deepcopy(document["source_registry"]["sources"][0])
        extra.update(
            promotion_id="promo_extra",
            chapter_id="chapter_000003",
            chapter_sha256="c" * 64,
            review_id="review_extra",
        )
        document["source_registry"]["sources"].append(extra)
        with self.assertRaises(NarrativeModelValidationError):
            validate_narrative_model_document(document)

    def test_model_root_and_source_snapshot_are_strict(self) -> None:
        for field, value in (("format_version", True), ("format_version", 1.0)):
            with self.subTest(field=field, value=value):
                document = _model_document()
                document[field] = value
                with self.assertRaises(NarrativeModelValidationError):
                    validate_narrative_model_document(document)

        document = _model_document()
        document["source_registry"]["sources"][0]["chapter_sha256"] = "A" * 64
        with self.assertRaises(NarrativeModelValidationError):
            validate_narrative_model_document(document)

        document = _model_document()
        document["source_registry"]["sources"].append(
            copy.deepcopy(document["source_registry"]["sources"][0])
        )
        with self.assertRaises(NarrativeModelValidationError):
            validate_narrative_model_document(document)

    def test_scope_proposition_coverage_and_omission_overlap_are_checked(self) -> None:
        document = _model_document()
        document["scope"]["claim_uses"].pop()
        with self.assertRaises(NarrativeModelValidationError):
            validate_narrative_model_document(document)

        document = _model_document()
        document["scope"]["claim_omissions"] = [
            {
                "claim_ref": copy.deepcopy(document["scope"]["claim_uses"][0]),
                "reason": "same claim",
            }
        ]
        with self.assertRaises(NarrativeModelValidationError):
            validate_narrative_model_document(document)

    def test_model_serializer_rejects_wrong_type(self) -> None:
        with self.assertRaises(TypeError):
            narrative_model_to_document({})  # type: ignore[arg-type]


class SchemaAndGoldenTests(unittest.TestCase):
    def _schema(self, name: str) -> dict:
        document = _read_json(REPO / "schemas" / name)
        assert isinstance(document, dict)
        return document

    def test_schemas_are_draft_2020_12_and_strict(self) -> None:
        for name in ("narrative_plan.schema.json", "narrative_model.schema.json"):
            schema = self._schema(name)
            self.assertEqual(
                schema["$schema"], "https://json-schema.org/draft/2020-12/schema"
            )
            self.assertFalse(schema["additionalProperties"])

    def test_plan_and_model_share_their_common_structural_definitions(self) -> None:
        plan = self._schema("narrative_plan.schema.json")
        model = self._schema("narrative_model.schema.json")
        for name in (
            "stable_id",
            "non_blank",
            "claim_ref",
            "claim_omission",
            "scope",
            "perspective",
            "proposition",
            "phase",
            "disclosure",
            "beat",
        ):
            self.assertEqual(plan["$defs"][name], model["$defs"][name])
        self.assertIn("source_registry_ref", plan["$defs"])
        self.assertIn("source_registry_snapshot", model["$defs"])
        self.assertNotIn(
            "minItems", plan["$defs"]["scope"]["properties"]["claim_uses"]
        )
        self.assertNotIn(
            "minItems", model["$defs"]["scope"]["properties"]["claim_uses"]
        )

    def test_golden_document_validates_and_matches_compiler(self) -> None:
        expected = _read_json(MODEL_PATH)
        self.assertEqual(validate_narrative_model_document(expected), _model())
        self.assertEqual(narrative_model_to_document(_model()), expected)

    def test_golden_bytes_are_stable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "model.json"
            write_narrative_model(_model(), output)
            self.assertEqual(output.read_bytes(), MODEL_PATH.read_bytes())


class WriterTests(unittest.TestCase):
    def test_writer_returns_resolved_path_and_fsyncs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "model.json"
            with patch("pipeline.narrative_model.os.fsync") as fsync:
                result = write_narrative_model(_model(), output)
            self.assertEqual(result, output.resolve())
            fsync.assert_called_once()

    def test_replace_failure_preserves_existing_output_and_cleans_temp(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "model.json"
            output.write_bytes(b"old\n")
            with patch(
                "pipeline.narrative_model.os.replace", side_effect=OSError("blocked")
            ):
                with self.assertRaises(OSError):
                    write_narrative_model(_model(), output)
            self.assertEqual(output.read_bytes(), b"old\n")
            self.assertEqual(list(Path(temp_dir).glob(".model.json.*.tmp")), [])

    def test_prevalidation_happens_before_temp_creation(self) -> None:
        invalid = replace(_model(), model_id="Not a stable ID")
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("pipeline.narrative_model.tempfile.mkstemp") as mkstemp:
                with self.assertRaises(NarrativeModelValidationError):
                    write_narrative_model(invalid, Path(temp_dir) / "model.json")
            mkstemp.assert_not_called()

    def test_missing_parent_and_malformed_typed_model_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(FileNotFoundError):
                write_narrative_model(_model(), Path(temp_dir) / "missing" / "model.json")

            malformed = replace(_model(), beats=("bad",))  # type: ignore[arg-type]
            with self.assertRaises(NarrativeModelValidationError):
                write_narrative_model(malformed, Path(temp_dir) / "model.json")

    def test_writer_rejects_output_symlinks_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            target = temp / "target.json"
            target.write_bytes(b"old\n")
            output = temp / "model.json"
            try:
                os.symlink(target, output)
            except OSError as exc:
                self.skipTest(f"symbolic links unavailable: {exc}")
            with self.assertRaises(OSError):
                write_narrative_model(_model(), output)
            self.assertEqual(target.read_bytes(), b"old\n")

    def test_writer_contains_open_flush_fsync_and_replace(self) -> None:
        source = inspect.getsource(write_narrative_model)
        for token in ("os.fdopen", "handle.flush()", "os.fsync", "os.replace"):
            self.assertIn(token, source)


class CliTests(unittest.TestCase):
    def _args(self, output: Path) -> list[str]:
        return [
            "--canon-registry",
            str(REGISTRY_PATH),
            "--narrative-plan",
            str(PLAN_PATH),
            "--output",
            str(output),
        ]

    def test_in_process_cli_matches_golden_and_preserves_inputs(self) -> None:
        registry_before = REGISTRY_PATH.read_bytes()
        plan_before = PLAN_PATH.read_bytes()
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "model.json"
            self.assertEqual(main(self._args(output)), 0)
            self.assertEqual(output.read_bytes(), MODEL_PATH.read_bytes())
        self.assertEqual(REGISTRY_PATH.read_bytes(), registry_before)
        self.assertEqual(PLAN_PATH.read_bytes(), plan_before)

    def test_subprocess_cli_matches_golden(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "model.json"
            completed = subprocess.run(
                [sys.executable, "-m", "pipeline.narrative_model", *self._args(output)],
                cwd=REPO,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(output.read_bytes(), MODEL_PATH.read_bytes())

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
            args[args.index(str(PLAN_PATH))] = str(bad)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(args), 1)
            self.assertFalse(output.exists())

            bad.write_text("[]\n", encoding="utf-8")
            args = self._args(output)
            args[args.index(str(REGISTRY_PATH))] = str(bad)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(args), 1)
            self.assertFalse(output.exists())

    def test_direct_output_aliases_are_rejected_before_reading(self) -> None:
        for input_path in (REGISTRY_PATH, PLAN_PATH):
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
                plan.write_bytes(PLAN_PATH.read_bytes())
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
                    "--narrative-plan",
                    str(plan),
                    "--output",
                    str(output),
                ]
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(main(args), 1)
                self.assertEqual(source.read_bytes(), before)
                self.assertEqual(output.read_bytes(), before)

    def test_symlink_inputs_and_outputs_are_rejected_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            temp = Path(td)
            registry = temp / "registry.json"
            plan = temp / "plan.json"
            registry.write_bytes(REGISTRY_PATH.read_bytes())
            plan.write_bytes(PLAN_PATH.read_bytes())
            registry_link = temp / "registry-link.json"
            output_link = temp / "output-link.json"
            try:
                os.symlink(registry, registry_link)
                os.symlink(registry, output_link)
            except OSError as exc:
                self.skipTest(f"symbolic links unavailable: {exc}")

            args = [
                "--canon-registry",
                str(registry_link),
                "--narrative-plan",
                str(plan),
                "--output",
                str(temp / "out.json"),
            ]
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(args), 1)

            args = [
                "--canon-registry",
                str(registry),
                "--narrative-plan",
                str(plan),
                "--output",
                str(output_link),
            ]
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(args), 1)
            self.assertEqual(registry.read_bytes(), REGISTRY_PATH.read_bytes())

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
                        "--narrative-plan",
                        str(same),
                        "--output",
                        str(Path(temp_dir) / "out.json"),
                    ]
                )
            self.assertEqual(result, 1)
            self.assertIn("Input paths point to the same file", stderr.getvalue())

    def test_existing_output_is_replaced_and_missing_parent_returns_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "model.json"
            output.write_bytes(b"old\n")
            self.assertEqual(main(self._args(output)), 0)
            self.assertEqual(output.read_bytes(), MODEL_PATH.read_bytes())

            missing = Path(temp_dir) / "missing" / "model.json"
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(self._args(missing)), 1)
            self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
