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
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from unittest.mock import patch

from pipeline.canon import CanonRelationValue, validate_canon_draft_document
from pipeline.canon_registry import (
    CanonRegistry,
    CanonRegistryBuildError,
    CanonRegistryValidationError,
    build_canon_registry,
    canon_registry_to_document,
    main,
    validate_canon_registry_document,
    validate_canon_registry_plan,
    write_canon_registry,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "canon_registry"


def _load(name: str) -> dict:
    with open(FIXTURE_DIR / name, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _draft_documents() -> list[dict]:
    return [_load("draft_ch001.json"), _load("draft_ch002.json")]


def _drafts():
    return tuple(validate_canon_draft_document(raw) for raw in _draft_documents())


def _plan_document() -> dict:
    return _load("valid_plan.json")


def _plan():
    return validate_canon_registry_plan(_plan_document())


def _registry() -> CanonRegistry:
    return build_canon_registry(_drafts(), _plan())


def _registry_document() -> dict:
    return canon_registry_to_document(_registry())


def _entity(document: dict, entity_id: str) -> dict:
    return next(item for item in document["entities"] if item["entity_id"] == entity_id)


class PlanValidationTests(unittest.TestCase):
    def test_valid_plan_is_normalized(self) -> None:
        plan = _plan()
        self.assertEqual(
            [entity.entity_id for entity in plan.entities],
            ["canon_glass_tower", "canon_mira", "canon_valley_gate"],
        )
        mira = next(entity for entity in plan.entities if entity.entity_id == "canon_mira")
        self.assertEqual(
            mira.aliases,
            ("First Watcher", "Mira of the Gate", "Valley Watcher"),
        )

    def test_plan_is_frozen(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            _plan().registry_id = "changed"

    def test_root_must_be_object(self) -> None:
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_plan([])

    def test_bool_format_version_rejected(self) -> None:
        raw = _plan_document()
        raw["format_version"] = True
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_plan(raw)

    def test_nonpositive_registry_version_rejected(self) -> None:
        raw = _plan_document()
        raw["registry_version"] = 0
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_plan(raw)

    def test_unknown_root_field_rejected(self) -> None:
        raw = _plan_document()
        raw["extra"] = True
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_plan(raw)

    def test_entities_must_be_nonempty(self) -> None:
        raw = _plan_document()
        raw["entities"] = []
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_plan(raw)

    def test_duplicate_registry_entity_id_rejected(self) -> None:
        raw = _plan_document()
        raw["entities"][1]["entity_id"] = raw["entities"][0]["entity_id"]
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_plan(raw)

    def test_alias_equal_to_canonical_name_rejected(self) -> None:
        raw = _plan_document()
        raw["entities"][0]["aliases"].append("  MIRA  ")
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_plan(raw)

    def test_nfkc_duplicate_alias_rejected(self) -> None:
        raw = _plan_document()
        raw["entities"][0]["aliases"] = ["Ａ", "a"]
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_plan(raw)

    def test_members_must_be_nonempty(self) -> None:
        raw = _plan_document()
        raw["entities"][0]["members"] = []
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_plan(raw)

    def test_duplicate_member_in_one_entity_rejected(self) -> None:
        raw = _plan_document()
        raw["entities"][0]["members"].append(
            copy.deepcopy(raw["entities"][0]["members"][0])
        )
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_plan(raw)

    def test_entity_cannot_have_two_members_from_one_promotion(self) -> None:
        raw = _plan_document()
        raw["entities"][0]["members"].append(
            {
                "promotion_id": "promo_ch001",
                "source_entity_id": "source_other",
            }
        )
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_plan(raw)

    def test_member_cannot_belong_to_two_entities(self) -> None:
        raw = _plan_document()
        raw["entities"][1]["members"] = [
            copy.deepcopy(raw["entities"][0]["members"][0])
        ]
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_plan(raw)

    def test_member_unknown_field_rejected(self) -> None:
        raw = _plan_document()
        raw["entities"][0]["members"][0]["guess"] = "same person"
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_plan(raw)

    def test_member_stable_id_required(self) -> None:
        raw = _plan_document()
        raw["entities"][0]["members"][0]["promotion_id"] = "Chapter One"
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_plan(raw)

    def test_merge_reason_required(self) -> None:
        raw = _plan_document()
        raw["entities"][0]["merge_reason"] = "  "
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_plan(raw)


class BuildRegistryTests(unittest.TestCase):
    def test_valid_build(self) -> None:
        registry = _registry()
        self.assertEqual(registry.registry_id, "fixture_registry")
        self.assertEqual(len(registry.sources), 2)
        self.assertEqual(len(registry.entities), 3)

    def test_relations_are_rewritten_to_registry_ids(self) -> None:
        document = _registry_document()
        mira = _entity(document, "canon_mira")
        relation_targets = [
            claim["value"]["entity_ref"]
            for claim in mira["claims"]
            if claim["value"]["kind"] == "relation"
        ]
        self.assertEqual(relation_targets, ["canon_glass_tower", "canon_valley_gate"])

    def test_conflicting_claims_are_preserved_not_resolved(self) -> None:
        mira = _entity(_registry_document(), "canon_mira")
        role_values = [
            claim["value"]["enum_value"]
            for claim in mira["claims"]
            if claim["predicate"] == "role"
        ]
        self.assertEqual(role_values, ["watcher", "guardian"])

    def test_same_claim_id_from_two_sources_is_preserved(self) -> None:
        mira = _entity(_registry_document(), "canon_mira")
        source_ids = [
            (
                claim["source"]["promotion_id"],
                claim["source"]["source_claim_id"],
            )
            for claim in mira["claims"]
            if claim["source"]["source_claim_id"] == "claim_home"
        ]
        self.assertEqual(
            source_ids,
            [("promo_ch001", "claim_home"), ("promo_ch002", "claim_home")],
        )

    def test_source_names_and_aliases_are_preserved(self) -> None:
        mira = _entity(_registry_document(), "canon_mira")
        self.assertEqual(
            [member["source_canonical_name"] for member in mira["members"]],
            ["Mira", "Mira of the Gate"],
        )
        self.assertEqual(mira["members"][1]["source_aliases"], ["Valley Watcher"])

    def test_plan_controls_registry_name_without_losing_sources(self) -> None:
        raw = _plan_document()
        raw["entities"][0]["canonical_name"] = "Mira Registry Name"
        registry = build_canon_registry(_drafts(), validate_canon_registry_plan(raw))
        mira = next(entity for entity in registry.entities if entity.entity_id == "canon_mira")
        self.assertEqual(mira.canonical_name, "Mira Registry Name")
        self.assertEqual(mira.members[1].source_canonical_name, "Mira of the Gate")

    def test_missing_source_entity_mapping_rejected(self) -> None:
        raw = _plan_document()
        raw["entities"] = raw["entities"][:-1]
        with self.assertRaises(CanonRegistryBuildError):
            build_canon_registry(_drafts(), validate_canon_registry_plan(raw))

    def test_extra_source_entity_mapping_rejected(self) -> None:
        raw = _plan_document()
        raw["entities"][1]["members"][0]["source_entity_id"] = "source_missing"
        with self.assertRaises(CanonRegistryBuildError):
            build_canon_registry(_drafts(), validate_canon_registry_plan(raw))

    def test_one_draft_rejected(self) -> None:
        with self.assertRaises(CanonRegistryBuildError):
            build_canon_registry(_drafts()[:1], _plan())

    def test_duplicate_promotion_id_rejected(self) -> None:
        first, second = _drafts()
        duplicate = replace(second, promotion_id=first.promotion_id)
        with self.assertRaises(CanonRegistryBuildError):
            build_canon_registry((first, duplicate), _plan())

    def test_duplicate_chapter_id_rejected(self) -> None:
        first, second = _drafts()
        duplicate = replace(second, source=first.source)
        with self.assertRaises(CanonRegistryBuildError):
            build_canon_registry((first, duplicate), _plan())

    def test_mixed_entity_types_in_merge_rejected(self) -> None:
        raw = _plan_document()
        raw["entities"][0]["members"][1], raw["entities"][1]["members"][0] = (
            raw["entities"][1]["members"][0],
            raw["entities"][0]["members"][1],
        )
        with self.assertRaises(CanonRegistryBuildError):
            build_canon_registry(_drafts(), validate_canon_registry_plan(raw))

    def test_string_is_not_a_draft_sequence(self) -> None:
        with self.assertRaises(CanonRegistryBuildError):
            build_canon_registry("not-drafts", _plan())

    def test_plan_type_is_checked(self) -> None:
        with self.assertRaises(CanonRegistryBuildError):
            build_canon_registry(_drafts(), object())

    def test_each_input_must_be_a_canon_draft(self) -> None:
        with self.assertRaises(CanonRegistryBuildError):
            build_canon_registry((_drafts()[0], object()), _plan())

    def test_draft_order_does_not_change_output(self) -> None:
        forward = canon_registry_to_document(build_canon_registry(_drafts(), _plan()))
        reverse = canon_registry_to_document(
            build_canon_registry(tuple(reversed(_drafts())), _plan())
        )
        self.assertEqual(forward, reverse)

    def test_plan_collection_order_does_not_change_output(self) -> None:
        raw = _plan_document()
        raw["entities"].reverse()
        for entity in raw["entities"]:
            entity["members"].reverse()
            entity["aliases"].reverse()
        reverse_plan = validate_canon_registry_plan(raw)
        self.assertEqual(
            canon_registry_to_document(_registry()),
            canon_registry_to_document(build_canon_registry(_drafts(), reverse_plan)),
        )

    def test_dangling_source_relation_rejected(self) -> None:
        first, second = _drafts()
        source_entity = first.entities[0]
        broken_claim = replace(
            source_entity.claims[0],
            value=CanonRelationValue(entity_ref="source_missing"),
        )
        broken_entity = replace(
            source_entity,
            claims=(broken_claim, *source_entity.claims[1:]),
        )
        broken_first = replace(first, entities=(broken_entity, *first.entities[1:]))
        with self.assertRaises(CanonRegistryBuildError):
            build_canon_registry((broken_first, second), _plan())


class RegistryDocumentValidationTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        registry = _registry()
        self.assertEqual(
            validate_canon_registry_document(canon_registry_to_document(registry)),
            registry,
        )

    def test_registry_is_frozen(self) -> None:
        with self.assertRaises(FrozenInstanceError):
            _registry().registry_version = 2

    def test_unknown_root_field_rejected(self) -> None:
        raw = _registry_document()
        raw["extra"] = []
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_document(raw)

    def test_two_sources_required(self) -> None:
        raw = _registry_document()
        raw["sources"] = raw["sources"][:1]
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_document(raw)

    def test_duplicate_source_promotion_rejected(self) -> None:
        raw = _registry_document()
        raw["sources"][1]["promotion_id"] = raw["sources"][0]["promotion_id"]
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_document(raw)

    def test_duplicate_source_chapter_rejected(self) -> None:
        raw = _registry_document()
        raw["sources"][1]["chapter_id"] = raw["sources"][0]["chapter_id"]
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_document(raw)

    def test_invalid_source_hash_rejected(self) -> None:
        raw = _registry_document()
        raw["sources"][0]["chapter_sha256"] = "nope"
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_document(raw)

    def test_duplicate_entity_id_rejected(self) -> None:
        raw = _registry_document()
        raw["entities"][1]["entity_id"] = raw["entities"][0]["entity_id"]
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_document(raw)

    def test_member_promotion_must_exist(self) -> None:
        raw = _registry_document()
        raw["entities"][0]["members"][0]["promotion_id"] = "promo_missing"
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_document(raw)

    def test_every_source_must_have_a_member(self) -> None:
        raw = _registry_document()
        raw["entities"] = [
            entity
            for entity in raw["entities"]
            if entity["entity_id"] != "canon_valley_gate"
        ]
        mira = _entity(raw, "canon_mira")
        mira["members"] = [
            member
            for member in mira["members"]
            if member["promotion_id"] != "promo_ch002"
        ]
        mira["claims"] = [
            claim
            for claim in mira["claims"]
            if claim["source"]["promotion_id"] != "promo_ch002"
        ]
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_document(raw)

    def test_member_cannot_be_reused_by_another_entity(self) -> None:
        raw = _registry_document()
        raw["entities"][2]["members"].append(
            copy.deepcopy(raw["entities"][0]["members"][0])
        )
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_document(raw)

    def test_entity_cannot_have_two_members_from_one_source(self) -> None:
        raw = _registry_document()
        mira = _entity(raw, "canon_mira")
        mira["members"].append(
            {
                "promotion_id": "promo_ch001",
                "source_entity_id": "source_other",
                "source_candidate_id": "candidate_other",
                "source_canonical_name": "Other Source Name",
                "source_aliases": [],
            }
        )
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_document(raw)

    def test_claim_source_must_belong_to_entity_member(self) -> None:
        raw = _registry_document()
        mira = _entity(raw, "canon_mira")
        mira["claims"][0]["source"]["source_entity_id"] = "source_gate"
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_document(raw)

    def test_duplicate_claim_source_rejected(self) -> None:
        raw = _registry_document()
        mira = _entity(raw, "canon_mira")
        mira["claims"].append(copy.deepcopy(mira["claims"][0]))
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_document(raw)

    def test_dangling_registry_relation_rejected(self) -> None:
        raw = _registry_document()
        mira = _entity(raw, "canon_mira")
        mira["claims"][0]["value"]["entity_ref"] = "canon_missing"
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_document(raw)

    def test_claim_chapter_must_match_promotion_source(self) -> None:
        raw = _registry_document()
        mira = _entity(raw, "canon_mira")
        mira["claims"][0]["source_chapters"] = ["chapter_000002"]
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_document(raw)

    def test_explicit_claim_requires_null_inference_basis(self) -> None:
        raw = _registry_document()
        mira = _entity(raw, "canon_mira")
        mira["claims"][0]["inference_basis"] = "not allowed"
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_document(raw)

    def test_explicit_claim_still_requires_inference_basis_field(self) -> None:
        raw = _registry_document()
        mira = _entity(raw, "canon_mira")
        del mira["claims"][0]["inference_basis"]
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_document(raw)

    def test_inferred_claim_requires_basis(self) -> None:
        raw = _registry_document()
        mira = _entity(raw, "canon_mira")
        inferred = next(
            claim for claim in mira["claims"] if claim["source_support"] == "inferred"
        )
        inferred["inference_basis"] = None
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_document(raw)

    def test_numeric_bool_rejected(self) -> None:
        raw = _registry_document()
        claim = _entity(raw, "canon_glass_tower")["claims"][0]
        claim["value"] = {"kind": "numeric", "number": True, "unit": None}
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_document(raw)

    def test_numeric_nan_rejected(self) -> None:
        raw = _registry_document()
        claim = _entity(raw, "canon_glass_tower")["claims"][0]
        claim["value"] = {"kind": "numeric", "number": float("nan"), "unit": None}
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_document(raw)

    def test_numeric_value_still_requires_unit_field(self) -> None:
        raw = _registry_document()
        claim = _entity(raw, "canon_glass_tower")["claims"][0]
        claim["value"] = {"kind": "numeric", "number": 3}
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_document(raw)

    def test_alias_equal_to_canonical_name_rejected(self) -> None:
        raw = _registry_document()
        raw["entities"][0]["aliases"] = [raw["entities"][0]["canonical_name"]]
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_document(raw)

    def test_forward_relation_reference_is_valid(self) -> None:
        raw = _registry_document()
        self.assertEqual(validate_canon_registry_document(raw), _registry())

    def test_empty_claims_are_valid_for_relation_only_members(self) -> None:
        raw = _registry_document()
        raw["entities"][0]["claims"] = []
        parsed = validate_canon_registry_document(raw)
        self.assertEqual(parsed.entities[0].claims, ())

    def test_unknown_member_field_rejected(self) -> None:
        raw = _registry_document()
        raw["entities"][0]["members"][0]["extra"] = "no"
        with self.assertRaises(CanonRegistryValidationError):
            validate_canon_registry_document(raw)

    def test_validator_normalizes_entity_order(self) -> None:
        raw = _registry_document()
        raw["entities"].reverse()
        parsed = validate_canon_registry_document(raw)
        self.assertEqual(
            [entity.entity_id for entity in parsed.entities],
            ["canon_glass_tower", "canon_mira", "canon_valley_gate"],
        )


class GoldenAndSchemaTests(unittest.TestCase):
    def test_generated_document_matches_golden_fixture(self) -> None:
        self.assertEqual(_registry_document(), _load("expected_registry.json"))

    def test_generated_bytes_are_deterministic(self) -> None:
        first = json.dumps(
            _registry_document(), ensure_ascii=False, sort_keys=True, indent=2
        )
        second = json.dumps(
            canon_registry_to_document(
                build_canon_registry(tuple(reversed(_drafts())), _plan())
            ),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        self.assertEqual(first, second)

    def test_schema_documents_parse(self) -> None:
        for name in ("canon_registry_plan.schema.json", "canon_registry.schema.json"):
            with open(Path("schemas") / name, "r", encoding="utf-8") as handle:
                self.assertIsInstance(json.load(handle), dict)

    def test_schemas_use_draft_2020_12(self) -> None:
        for name in ("canon_registry_plan.schema.json", "canon_registry.schema.json"):
            with open(Path("schemas") / name, "r", encoding="utf-8") as handle:
                schema = json.load(handle)
            self.assertEqual(
                schema["$schema"], "https://json-schema.org/draft/2020-12/schema"
            )
            self.assertFalse(schema["additionalProperties"])

    def test_registry_schema_requires_two_sources(self) -> None:
        with open("schemas/canon_registry.schema.json", "r", encoding="utf-8") as handle:
            schema = json.load(handle)
        self.assertEqual(schema["properties"]["sources"]["minItems"], 2)

    def test_registry_relation_uses_registry_stable_id(self) -> None:
        with open("schemas/canon_registry.schema.json", "r", encoding="utf-8") as handle:
            schema = json.load(handle)
        self.assertEqual(
            schema["$defs"]["relation_value"]["properties"]["entity_ref"]["$ref"],
            "#/$defs/stable_id",
        )

    def test_plan_schema_members_are_explicit(self) -> None:
        with open(
            "schemas/canon_registry_plan.schema.json", "r", encoding="utf-8"
        ) as handle:
            schema = json.load(handle)
        self.assertEqual(
            schema["$defs"]["member"]["required"],
            ["promotion_id", "source_entity_id"],
        )
        self.assertFalse(schema["$defs"]["member"]["additionalProperties"])


class WriterAndCliTests(unittest.TestCase):
    def test_writer_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "registry.json"
            result = write_canon_registry(_registry(), output)
            self.assertEqual(result, output.resolve())
            with open(output, "r", encoding="utf-8") as handle:
                parsed = validate_canon_registry_document(json.load(handle))
            self.assertEqual(parsed, _registry())

    def test_writer_flushes_with_fsync(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "registry.json"
            with patch("pipeline.canon_registry.os.fsync") as fsync:
                write_canon_registry(_registry(), output)
            fsync.assert_called_once()

    def test_writer_failure_preserves_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "registry.json"
            output.write_text("old\n", encoding="utf-8")
            with patch(
                "pipeline.canon_registry.os.replace", side_effect=OSError("blocked")
            ):
                with self.assertRaises(OSError):
                    write_canon_registry(_registry(), output)
            self.assertEqual(output.read_text(encoding="utf-8"), "old\n")
            self.assertEqual(list(Path(temp_dir).glob(".registry.json.*.tmp")), [])

    def test_writer_validates_before_creating_temp_file(self) -> None:
        invalid = replace(_registry(), sources=_registry().sources[:1])
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("pipeline.canon_registry.tempfile.mkstemp") as mkstemp:
                with self.assertRaises(CanonRegistryValidationError):
                    write_canon_registry(invalid, Path(temp_dir) / "registry.json")
            mkstemp.assert_not_called()

    def test_writer_rejects_missing_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "missing" / "registry.json"
            with self.assertRaises(FileNotFoundError):
                write_canon_registry(_registry(), output)

    def test_cli_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "registry.json"
            exit_code = main(
                [
                    "--canon-draft",
                    str(FIXTURE_DIR / "draft_ch001.json"),
                    "--canon-draft",
                    str(FIXTURE_DIR / "draft_ch002.json"),
                    "--registry-plan",
                    str(FIXTURE_DIR / "valid_plan.json"),
                    "--output",
                    str(output),
                ]
            )
            self.assertEqual(exit_code, 0)
            with open(output, "r", encoding="utf-8") as handle:
                self.assertEqual(json.load(handle), _load("expected_registry.json"))

    def test_cli_requires_two_draft_arguments(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                main(
                    [
                        "--canon-draft",
                        str(FIXTURE_DIR / "draft_ch001.json"),
                        "--registry-plan",
                        str(FIXTURE_DIR / "valid_plan.json"),
                        "--output",
                        "unused.json",
                    ]
                )
        self.assertEqual(caught.exception.code, 2)

    def test_cli_rejects_output_equal_to_input(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            exit_code = main(
                [
                    "--canon-draft",
                    str(FIXTURE_DIR / "draft_ch001.json"),
                    "--canon-draft",
                    str(FIXTURE_DIR / "draft_ch002.json"),
                    "--registry-plan",
                    str(FIXTURE_DIR / "valid_plan.json"),
                    "--output",
                    str(FIXTURE_DIR / "valid_plan.json"),
                ]
            )
        self.assertEqual(exit_code, 1)
        self.assertIn("指向同一文件", stderr.getvalue())

    def test_cli_bad_json_returns_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            bad = Path(temp_dir) / "bad.json"
            bad.write_text("{", encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                exit_code = main(
                    [
                        "--canon-draft",
                        str(FIXTURE_DIR / "draft_ch001.json"),
                        "--canon-draft",
                        str(FIXTURE_DIR / "draft_ch002.json"),
                        "--registry-plan",
                        str(bad),
                        "--output",
                        str(Path(temp_dir) / "out.json"),
                    ]
                )
            self.assertEqual(exit_code, 1)
            self.assertIn("JSON 解析错误", stderr.getvalue())

    def test_cli_invalid_utf8_returns_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            bad = Path(temp_dir) / "bad.json"
            bad.write_bytes(b"\xff")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                exit_code = main(
                    [
                        "--canon-draft",
                        str(FIXTURE_DIR / "draft_ch001.json"),
                        "--canon-draft",
                        str(FIXTURE_DIR / "draft_ch002.json"),
                        "--registry-plan",
                        str(bad),
                        "--output",
                        str(Path(temp_dir) / "out.json"),
                    ]
                )
            self.assertEqual(exit_code, 1)
            self.assertIn("UTF-8 解码错误", stderr.getvalue())

    def test_module_subprocess_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "registry.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pipeline.canon_registry",
                    "--canon-draft",
                    str(FIXTURE_DIR / "draft_ch001.json"),
                    "--canon-draft",
                    str(FIXTURE_DIR / "draft_ch002.json"),
                    "--registry-plan",
                    str(FIXTURE_DIR / "valid_plan.json"),
                    "--output",
                    str(output),
                ],
                cwd=Path(__file__).parents[1],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            with open(output, "r", encoding="utf-8") as handle:
                validate_canon_registry_document(json.load(handle))


if __name__ == "__main__":
    unittest.main()
