"""Tests for pipeline.fact_candidates — v1 fact-candidate document validation."""

from __future__ import annotations

import json
import math
import unittest
from pathlib import Path

from pipeline.fact_candidates import (
    BooleanValue,
    Candidate,
    Claim,
    EnumValue,
    FactCandidateDocument,
    FactCandidateValidationError,
    NumericValue,
    RelationValue,
    TextValue,
    validate_fact_candidate_document,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "fact_candidates"


def _minimal_doc(**overrides: object) -> dict:
    """Return a minimal valid document dict, with optional overrides."""
    doc: dict = {
        "format_version": 1,
        "source_chapter": "chapter_000001",
        "extracted_by": "test-tool/v1",
        "candidates": [
            {
                "candidate_id": "character_test",
                "entity_type": "character",
                "proposed_entity_id": None,
                "display_name": "测试角色",
                "aliases": [],
                "claims": [
                    {
                        "claim_id": "claim_test_text",
                        "predicate": "origin",
                        "value": {"kind": "text", "text": "来源文本。"},
                        "source_chapters": ["chapter_000001"],
                        "source_support": "explicit",
                        "certainty": "certain",
                        "inference_basis": None,
                    }
                ],
            }
        ],
    }
    doc.update(overrides)
    return doc


def _with_claim_value(doc: dict, value: dict) -> dict:
    """Replace the first claim's value in the minimal doc."""
    doc["candidates"][0]["claims"][0]["value"] = value
    return doc


# ── fixture loading ─────────────────────────────────────────────────────────

class FixtureTests(unittest.TestCase):
    def test_valid_character_fixture_loads(self) -> None:
        path = FIXTURE_DIR / "valid_character.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        doc = validate_fact_candidate_document(raw)
        self.assertIsInstance(doc, FactCandidateDocument)
        self.assertEqual(doc.format_version, 1)
        self.assertEqual(doc.source_chapter, "chapter_000001")
        self.assertEqual(len(doc.candidates), 2)

    def test_fixture_candidate_fields(self) -> None:
        path = FIXTURE_DIR / "valid_character.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        doc = validate_fact_candidate_document(raw)
        c0 = doc.candidates[0]
        self.assertEqual(c0.candidate_id, "character_fog_villager")
        self.assertEqual(c0.entity_type, "character")
        self.assertEqual(c0.proposed_entity_id, "character_fog_villager")
        self.assertEqual(c0.display_name, "雾岭村民")
        self.assertEqual(c0.aliases, ("老村民", "村民"))
        self.assertEqual(len(c0.claims), 4)

    def test_fixture_relation_cross_ref(self) -> None:
        """The fixture's second candidate references the first via relation."""
        path = FIXTURE_DIR / "valid_character.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        doc = validate_fact_candidate_document(raw)
        c1 = doc.candidates[1]
        self.assertEqual(c1.candidate_id, "location_fog_ridge")
        # The relation claim references character_fog_villager
        rel_claim = c1.claims[1]
        self.assertIsInstance(rel_claim.value, RelationValue)
        self.assertEqual(rel_claim.value.candidate_ref, "character_fog_villager")

    def test_fixture_proposed_entity_id_null(self) -> None:
        path = FIXTURE_DIR / "valid_character.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        doc = validate_fact_candidate_document(raw)
        self.assertIsNone(doc.candidates[1].proposed_entity_id)


# ── return type is frozen ───────────────────────────────────────────────────

class FrozenTests(unittest.TestCase):
    def test_document_is_frozen(self) -> None:
        doc = validate_fact_candidate_document(_minimal_doc())
        with self.assertRaises(AttributeError):
            doc.format_version = 2  # type: ignore[misc]

    def test_candidate_is_frozen(self) -> None:
        doc = validate_fact_candidate_document(_minimal_doc())
        with self.assertRaises(AttributeError):
            doc.candidates[0].display_name = "changed"  # type: ignore[misc]

    def test_claim_is_frozen(self) -> None:
        doc = validate_fact_candidate_document(_minimal_doc())
        with self.assertRaises(AttributeError):
            doc.candidates[0].claims[0].predicate = "changed"  # type: ignore[misc]

    def test_value_is_frozen(self) -> None:
        doc = validate_fact_candidate_document(_minimal_doc())
        with self.assertRaises(AttributeError):
            doc.candidates[0].claims[0].value.text = "changed"  # type: ignore[misc]


# ── top-level unknown fields ────────────────────────────────────────────────

class RootUnknownFieldTests(unittest.TestCase):
    def test_unknown_root_field_rejected(self) -> None:
        doc = _minimal_doc(extra_field="bad")
        with self.assertRaises(FactCandidateValidationError) as ctx:
            validate_fact_candidate_document(doc)
        self.assertTrue(any("未知字段" in i and "extra_field" in i for i in ctx.exception.issues))

    def test_unknown_candidate_field_rejected(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["model_guess"] = "bad"
        with self.assertRaises(FactCandidateValidationError) as ctx:
            validate_fact_candidate_document(doc)
        self.assertTrue(any("未知字段" in i and "model_guess" in i for i in ctx.exception.issues))

    def test_unknown_claim_field_rejected(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["claims"][0]["confidence"] = 0.9
        with self.assertRaises(FactCandidateValidationError) as ctx:
            validate_fact_candidate_document(doc)
        self.assertTrue(any("未知字段" in i and "confidence" in i for i in ctx.exception.issues))

    def test_unknown_value_field_rejected(self) -> None:
        doc = _with_claim_value(_minimal_doc(), {"kind": "text", "text": "ok", "extra": 1})
        with self.assertRaises(FactCandidateValidationError) as ctx:
            validate_fact_candidate_document(doc)
        self.assertTrue(any("未知字段" in i for i in ctx.exception.issues))


# ── missing required fields ─────────────────────────────────────────────────

class MissingFieldTests(unittest.TestCase):
    def test_missing_format_version(self) -> None:
        doc = _minimal_doc()
        del doc["format_version"]
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_missing_source_chapter(self) -> None:
        doc = _minimal_doc()
        del doc["source_chapter"]
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_missing_extracted_by(self) -> None:
        doc = _minimal_doc()
        del doc["extracted_by"]
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_missing_candidates(self) -> None:
        doc = _minimal_doc()
        del doc["candidates"]
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_missing_candidate_id(self) -> None:
        doc = _minimal_doc()
        del doc["candidates"][0]["candidate_id"]
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_missing_entity_type(self) -> None:
        doc = _minimal_doc()
        del doc["candidates"][0]["entity_type"]
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_missing_proposed_entity_id_key(self) -> None:
        """proposed_entity_id must be explicitly present."""
        doc = _minimal_doc()
        del doc["candidates"][0]["proposed_entity_id"]
        with self.assertRaises(FactCandidateValidationError) as ctx:
            validate_fact_candidate_document(doc)
        self.assertTrue(any("proposed_entity_id" in i for i in ctx.exception.issues))

    def test_missing_display_name(self) -> None:
        doc = _minimal_doc()
        del doc["candidates"][0]["display_name"]
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_missing_aliases(self) -> None:
        doc = _minimal_doc()
        del doc["candidates"][0]["aliases"]
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_missing_claims(self) -> None:
        doc = _minimal_doc()
        del doc["candidates"][0]["claims"]
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_missing_claim_id(self) -> None:
        doc = _minimal_doc()
        del doc["candidates"][0]["claims"][0]["claim_id"]
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_missing_value(self) -> None:
        doc = _minimal_doc()
        del doc["candidates"][0]["claims"][0]["value"]
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_missing_source_chapters(self) -> None:
        doc = _minimal_doc()
        del doc["candidates"][0]["claims"][0]["source_chapters"]
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_missing_source_support(self) -> None:
        doc = _minimal_doc()
        del doc["candidates"][0]["claims"][0]["source_support"]
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_missing_certainty(self) -> None:
        doc = _minimal_doc()
        del doc["candidates"][0]["claims"][0]["certainty"]
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_missing_inference_basis(self) -> None:
        doc = _minimal_doc()
        del doc["candidates"][0]["claims"][0]["inference_basis"]
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)


# ── format_version ──────────────────────────────────────────────────────────

class FormatVersionTests(unittest.TestCase):
    def test_version_2_rejected(self) -> None:
        doc = _minimal_doc(format_version=2)
        with self.assertRaises(FactCandidateValidationError) as ctx:
            validate_fact_candidate_document(doc)
        self.assertTrue(any("format_version" in i for i in ctx.exception.issues))

    def test_version_true_rejected(self) -> None:
        doc = _minimal_doc(format_version=True)
        with self.assertRaises(FactCandidateValidationError) as ctx:
            validate_fact_candidate_document(doc)
        self.assertTrue(any("int" in i for i in ctx.exception.issues))

    def test_version_false_rejected(self) -> None:
        doc = _minimal_doc(format_version=False)
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)


# ── source_chapter ──────────────────────────────────────────────────────────

class SourceChapterTests(unittest.TestCase):
    def test_chapter_short_rejected(self) -> None:
        doc = _minimal_doc(source_chapter="ch1")
        with self.assertRaises(FactCandidateValidationError) as ctx:
            validate_fact_candidate_document(doc)
        self.assertTrue(any("source_chapter" in i for i in ctx.exception.issues))

    def test_chapter_no_digits_rejected(self) -> None:
        doc = _minimal_doc(source_chapter="chapter_abc")
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_chapter_5_digits_rejected(self) -> None:
        doc = _minimal_doc(source_chapter="chapter_00001")
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_chapter_7_digits_rejected(self) -> None:
        doc = _minimal_doc(source_chapter="chapter_0000001")
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)


# ── extracted_by ────────────────────────────────────────────────────────────

class ExtractedByTests(unittest.TestCase):
    def test_blank_rejected(self) -> None:
        doc = _minimal_doc(extracted_by="   ")
        with self.assertRaises(FactCandidateValidationError) as ctx:
            validate_fact_candidate_document(doc)
        self.assertTrue(any("extracted_by" in i for i in ctx.exception.issues))

    def test_non_string_rejected(self) -> None:
        doc = _minimal_doc(extracted_by=123)
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)


# ── candidates array ────────────────────────────────────────────────────────

class CandidatesArrayTests(unittest.TestCase):
    def test_empty_array_rejected(self) -> None:
        doc = _minimal_doc(candidates=[])
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_non_array_rejected(self) -> None:
        doc = _minimal_doc(candidates="not-array")
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_non_object_element_rejected(self) -> None:
        doc = _minimal_doc(candidates=["not-object"])
        with self.assertRaises(FactCandidateValidationError) as ctx:
            validate_fact_candidate_document(doc)
        self.assertTrue(any("对象" in i for i in ctx.exception.issues))


# ── candidate_id ────────────────────────────────────────────────────────────

class CandidateIdTests(unittest.TestCase):
    def test_blank_rejected(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["candidate_id"] = ""
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_uppercase_rejected(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["candidate_id"] = "Character_test"
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_hyphen_rejected(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["candidate_id"] = "character-test"
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_start_digit_rejected(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["candidate_id"] = "1character"
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_duplicate_rejected(self) -> None:
        doc = _minimal_doc()
        cand = doc["candidates"][0].copy()
        doc["candidates"] = [cand, cand.copy()]
        with self.assertRaises(FactCandidateValidationError) as ctx:
            validate_fact_candidate_document(doc)
        self.assertTrue(any("重复" in i and "candidate_id" in i for i in ctx.exception.issues))


# ── entity_type ─────────────────────────────────────────────────────────────

class EntityTypeTests(unittest.TestCase):
    def test_invalid_type_rejected(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["entity_type"] = "person"
        with self.assertRaises(FactCandidateValidationError) as ctx:
            validate_fact_candidate_document(doc)
        self.assertTrue(any("entity_type" in i for i in ctx.exception.issues))

    def test_all_valid_types(self) -> None:
        for etype in ("character", "location", "organization", "skill", "item", "event"):
            doc = _minimal_doc()
            doc["candidates"][0]["entity_type"] = etype
            result = validate_fact_candidate_document(doc)
            self.assertEqual(result.candidates[0].entity_type, etype)


# ── P1-1: enum fields must not leak TypeError on unhashable types ────────────

class EnumTypeErrorTests(unittest.TestCase):
    """entity_type, source_support, certainty must accept any JSON type
    and raise FactCandidateValidationError, never TypeError."""

    _BAD_VALUES = [None, True, False, 0, 42, 3.14, ["x"], {"k": "v"}]

    def _make_doc(self, field: str, value: object) -> dict:
        doc = _minimal_doc()
        if field == "entity_type":
            doc["candidates"][0]["entity_type"] = value
        else:
            doc["candidates"][0]["claims"][0][field] = value
        return doc

    def test_enum_fields_reject_bad_types(self) -> None:
        for field in ("entity_type", "source_support", "certainty"):
            for bad in self._BAD_VALUES:
                with self.subTest(field=field, value=bad):
                    with self.assertRaises(FactCandidateValidationError):
                        validate_fact_candidate_document(
                            self._make_doc(field, bad)
                        )


# ── proposed_entity_id ──────────────────────────────────────────────────────

class ProposedEntityIdTests(unittest.TestCase):
    def test_null_accepted(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["proposed_entity_id"] = None
        result = validate_fact_candidate_document(doc)
        self.assertIsNone(result.candidates[0].proposed_entity_id)

    def test_valid_id_accepted(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["proposed_entity_id"] = "character_test"
        result = validate_fact_candidate_document(doc)
        self.assertEqual(result.candidates[0].proposed_entity_id, "character_test")

    def test_bad_format_rejected(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["proposed_entity_id"] = "Bad-ID"
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)


# ── display_name ────────────────────────────────────────────────────────────

class DisplayNameTests(unittest.TestCase):
    def test_blank_rejected(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["display_name"] = "   "
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)


# ── aliases ─────────────────────────────────────────────────────────────────

class AliasTests(unittest.TestCase):
    def test_empty_array_accepted(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["aliases"] = []
        result = validate_fact_candidate_document(doc)
        self.assertEqual(result.candidates[0].aliases, ())

    def test_non_array_rejected(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["aliases"] = "not-array"
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_blank_element_rejected(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["aliases"] = [""]
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_non_string_element_rejected(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["aliases"] = [123]
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_nfkc_duplicate_rejected(self) -> None:
        """Fullwidth and halfwidth forms normalize to the same value."""
        doc = _minimal_doc()
        doc["candidates"][0]["aliases"] = ["\uff41\uff42", "ab"]
        with self.assertRaises(FactCandidateValidationError) as ctx:
            validate_fact_candidate_document(doc)
        self.assertTrue(any("重复" in i for i in ctx.exception.issues))

    def test_casefold_duplicate_rejected(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["aliases"] = ["ABC", "abc"]
        with self.assertRaises(FactCandidateValidationError) as ctx:
            validate_fact_candidate_document(doc)
        self.assertTrue(any("重复" in i for i in ctx.exception.issues))

    def test_strip_duplicate_rejected(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["aliases"] = ["hello", "  hello  "]
        with self.assertRaises(FactCandidateValidationError) as ctx:
            validate_fact_candidate_document(doc)
        self.assertTrue(any("重复" in i for i in ctx.exception.issues))

    def test_original_values_preserved(self) -> None:
        """Original alias values are not modified by normalization."""
        doc = _minimal_doc()
        doc["candidates"][0]["aliases"] = ["  Hello  ", "World"]
        result = validate_fact_candidate_document(doc)
        self.assertEqual(result.candidates[0].aliases, ("  Hello  ", "World"))

    def test_distinct_aliases_accepted(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["aliases"] = ["alpha", "beta", "gamma"]
        result = validate_fact_candidate_document(doc)
        self.assertEqual(len(result.candidates[0].aliases), 3)


# ── claims array ────────────────────────────────────────────────────────────

class ClaimsArrayTests(unittest.TestCase):
    def test_empty_claims_rejected(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["claims"] = []
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_non_array_rejected(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["claims"] = "not-array"
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_non_object_element_rejected(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["claims"] = ["not-object"]
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)


# ── claim_id ────────────────────────────────────────────────────────────────

class ClaimIdTests(unittest.TestCase):
    def test_blank_rejected(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["claims"][0]["claim_id"] = ""
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_bad_format_rejected(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["claims"][0]["claim_id"] = "Bad-ID"
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_duplicate_rejected(self) -> None:
        doc = _minimal_doc()
        claim = doc["candidates"][0]["claims"][0].copy()
        doc["candidates"][0]["claims"] = [claim, claim.copy()]
        with self.assertRaises(FactCandidateValidationError) as ctx:
            validate_fact_candidate_document(doc)
        self.assertTrue(any("重复" in i and "claim_id" in i for i in ctx.exception.issues))


# ── predicate ───────────────────────────────────────────────────────────────

class PredicateTests(unittest.TestCase):
    def test_blank_rejected(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["claims"][0]["predicate"] = ""
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_bad_format_rejected(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["claims"][0]["predicate"] = "Not_Stable"
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_valid_stable_id(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["claims"][0]["predicate"] = "inhabited_by"
        result = validate_fact_candidate_document(doc)
        self.assertEqual(result.candidates[0].claims[0].predicate, "inhabited_by")


# ── source_chapters ─────────────────────────────────────────────────────────

class SourceChaptersTests(unittest.TestCase):
    def test_empty_array_rejected(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["claims"][0]["source_chapters"] = []
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_two_elements_rejected(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["claims"][0]["source_chapters"] = [
            "chapter_000001", "chapter_000002"
        ]
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_mismatch_rejected(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["claims"][0]["source_chapters"] = ["chapter_000002"]
        with self.assertRaises(FactCandidateValidationError) as ctx:
            validate_fact_candidate_document(doc)
        self.assertTrue(any("source_chapter" in i for i in ctx.exception.issues))

    def test_matching_accepted(self) -> None:
        doc = _minimal_doc()
        result = validate_fact_candidate_document(doc)
        self.assertEqual(
            result.candidates[0].claims[0].source_chapters, ("chapter_000001",)
        )


# ── source_support and certainty ────────────────────────────────────────────

class EvidenceDimensionTests(unittest.TestCase):
    def test_invalid_source_support_rejected(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["claims"][0]["source_support"] = "observed"
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_invalid_certainty_rejected(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["claims"][0]["certainty"] = "maybe"
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)


# ── inference_basis conditional ─────────────────────────────────────────────

class InferenceBasisTests(unittest.TestCase):
    def test_inferred_requires_basis(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["claims"][0]["source_support"] = "inferred"
        doc["candidates"][0]["claims"][0]["inference_basis"] = None
        with self.assertRaises(FactCandidateValidationError) as ctx:
            validate_fact_candidate_document(doc)
        self.assertTrue(any("inference_basis" in i for i in ctx.exception.issues))

    def test_inferred_blank_basis_rejected(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["claims"][0]["source_support"] = "inferred"
        doc["candidates"][0]["claims"][0]["inference_basis"] = "   "
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_inferred_valid_basis_accepted(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["claims"][0]["source_support"] = "inferred"
        doc["candidates"][0]["claims"][0]["inference_basis"] = "从上下文推断。"
        result = validate_fact_candidate_document(doc)
        self.assertEqual(result.candidates[0].claims[0].inference_basis, "从上下文推断。")

    def test_explicit_null_basis_accepted(self) -> None:
        doc = _minimal_doc()
        result = validate_fact_candidate_document(doc)
        self.assertIsNone(result.candidates[0].claims[0].inference_basis)

    def test_explicit_non_null_basis_rejected(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["claims"][0]["source_support"] = "explicit"
        doc["candidates"][0]["claims"][0]["inference_basis"] = "should be null"
        with self.assertRaises(FactCandidateValidationError) as ctx:
            validate_fact_candidate_document(doc)
        self.assertTrue(any("inference_basis" in i for i in ctx.exception.issues))


# ── value: text ─────────────────────────────────────────────────────────────

class TextValueTests(unittest.TestCase):
    def test_valid_text(self) -> None:
        doc = _with_claim_value(_minimal_doc(), {"kind": "text", "text": "描述。"})
        result = validate_fact_candidate_document(doc)
        v = result.candidates[0].claims[0].value
        self.assertIsInstance(v, TextValue)
        self.assertEqual(v.text, "描述。")

    def test_blank_text_rejected(self) -> None:
        doc = _with_claim_value(_minimal_doc(), {"kind": "text", "text": "   "})
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_empty_text_rejected(self) -> None:
        doc = _with_claim_value(_minimal_doc(), {"kind": "text", "text": ""})
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)


# ── value: relation ─────────────────────────────────────────────────────────

class RelationValueTests(unittest.TestCase):
    def test_valid_relation(self) -> None:
        doc = _minimal_doc()
        doc["candidates"].append({
            "candidate_id": "location_test",
            "entity_type": "location",
            "proposed_entity_id": None,
            "display_name": "测试地点",
            "aliases": [],
            "claims": [{
                "claim_id": "claim_loc_rel",
                "predicate": "lives_in",
                "value": {"kind": "relation", "candidate_ref": "character_test"},
                "source_chapters": ["chapter_000001"],
                "source_support": "explicit",
                "certainty": "certain",
                "inference_basis": None,
            }],
        })
        result = validate_fact_candidate_document(doc)
        v = result.candidates[1].claims[0].value
        self.assertIsInstance(v, RelationValue)
        self.assertEqual(v.candidate_ref, "character_test")

    def test_missing_candidate_ref_rejected(self) -> None:
        doc = _with_claim_value(_minimal_doc(), {"kind": "relation"})
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_dangling_ref_rejected(self) -> None:
        doc = _with_claim_value(
            _minimal_doc(),
            {"kind": "relation", "candidate_ref": "nonexistent"},
        )
        with self.assertRaises(FactCandidateValidationError) as ctx:
            validate_fact_candidate_document(doc)
        self.assertTrue(any("不存在" in i and "candidate_ref" in i for i in ctx.exception.issues))

    def test_bad_ref_format_rejected(self) -> None:
        doc = _with_claim_value(
            _minimal_doc(),
            {"kind": "relation", "candidate_ref": "Bad-Ref"},
        )
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)


# ── value: numeric ──────────────────────────────────────────────────────────

class NumericValueTests(unittest.TestCase):
    def test_valid_int(self) -> None:
        doc = _with_claim_value(
            _minimal_doc(), {"kind": "numeric", "number": 42, "unit": "years"}
        )
        result = validate_fact_candidate_document(doc)
        v = result.candidates[0].claims[0].value
        self.assertIsInstance(v, NumericValue)
        self.assertEqual(v.number, 42.0)
        self.assertEqual(v.unit, "years")

    def test_valid_float(self) -> None:
        doc = _with_claim_value(
            _minimal_doc(), {"kind": "numeric", "number": 3.14, "unit": "meters"}
        )
        result = validate_fact_candidate_document(doc)
        v = result.candidates[0].claims[0].value
        self.assertIsInstance(v, NumericValue)
        self.assertAlmostEqual(v.number, 3.14)

    def test_valid_null_unit(self) -> None:
        doc = _with_claim_value(
            _minimal_doc(), {"kind": "numeric", "number": 5, "unit": None}
        )
        result = validate_fact_candidate_document(doc)
        self.assertIsNone(result.candidates[0].claims[0].value.unit)

    def test_bool_rejected(self) -> None:
        doc = _with_claim_value(
            _minimal_doc(), {"kind": "numeric", "number": True, "unit": None}
        )
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_nan_rejected(self) -> None:
        doc = _with_claim_value(
            _minimal_doc(), {"kind": "numeric", "number": float("nan"), "unit": None}
        )
        with self.assertRaises(FactCandidateValidationError) as ctx:
            validate_fact_candidate_document(doc)
        self.assertTrue(any("NaN" in i or "Infinity" in i for i in ctx.exception.issues))

    def test_positive_infinity_rejected(self) -> None:
        doc = _with_claim_value(
            _minimal_doc(), {"kind": "numeric", "number": float("inf"), "unit": None}
        )
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_negative_infinity_rejected(self) -> None:
        doc = _with_claim_value(
            _minimal_doc(), {"kind": "numeric", "number": float("-inf"), "unit": None}
        )
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_missing_number_rejected(self) -> None:
        doc = _with_claim_value(
            _minimal_doc(), {"kind": "numeric", "unit": None}
        )
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_missing_unit_key_rejected(self) -> None:
        doc = _with_claim_value(
            _minimal_doc(), {"kind": "numeric", "number": 1}
        )
        with self.assertRaises(FactCandidateValidationError) as ctx:
            validate_fact_candidate_document(doc)
        self.assertTrue(any("unit" in i for i in ctx.exception.issues))

    def test_bad_unit_format_rejected(self) -> None:
        doc = _with_claim_value(
            _minimal_doc(), {"kind": "numeric", "number": 1, "unit": "Not_Stable"}
        )
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)


# ── P1-2: numeric int precision and OverflowError ───────────────────────────

class NumericPrecisionTests(unittest.TestCase):
    """Integers must be preserved as int; only floats get isfinite check."""

    def test_int_42_stays_int(self) -> None:
        doc = _with_claim_value(
            _minimal_doc(), {"kind": "numeric", "number": 42, "unit": None}
        )
        result = validate_fact_candidate_document(doc)
        num = result.candidates[0].claims[0].value.number
        self.assertIsInstance(num, int)
        self.assertEqual(num, 42)

    def test_int_2_pow_53_plus_1_exact(self) -> None:
        big = 2**53 + 1
        doc = _with_claim_value(
            _minimal_doc(), {"kind": "numeric", "number": big, "unit": None}
        )
        result = validate_fact_candidate_document(doc)
        num = result.candidates[0].claims[0].value.number
        self.assertIsInstance(num, int)
        self.assertEqual(num, big)

    def test_int_10_pow_400_no_overflow(self) -> None:
        huge = 10**400
        doc = _with_claim_value(
            _minimal_doc(), {"kind": "numeric", "number": huge, "unit": None}
        )
        result = validate_fact_candidate_document(doc)
        num = result.candidates[0].claims[0].value.number
        self.assertIsInstance(num, int)
        self.assertEqual(num, huge)

    def test_float_stays_float(self) -> None:
        doc = _with_claim_value(
            _minimal_doc(), {"kind": "numeric", "number": 3.14, "unit": None}
        )
        result = validate_fact_candidate_document(doc)
        num = result.candidates[0].claims[0].value.number
        self.assertIsInstance(num, float)
        self.assertAlmostEqual(num, 3.14)

    def test_int_0_stays_int(self) -> None:
        doc = _with_claim_value(
            _minimal_doc(), {"kind": "numeric", "number": 0, "unit": None}
        )
        result = validate_fact_candidate_document(doc)
        self.assertIsInstance(result.candidates[0].claims[0].value.number, int)


# ── value: boolean ──────────────────────────────────────────────────────────

class BooleanValueTests(unittest.TestCase):
    def test_true_accepted(self) -> None:
        doc = _with_claim_value(
            _minimal_doc(), {"kind": "boolean", "flag": True}
        )
        result = validate_fact_candidate_document(doc)
        v = result.candidates[0].claims[0].value
        self.assertIsInstance(v, BooleanValue)
        self.assertTrue(v.flag)

    def test_false_accepted(self) -> None:
        doc = _with_claim_value(
            _minimal_doc(), {"kind": "boolean", "flag": False}
        )
        result = validate_fact_candidate_document(doc)
        self.assertFalse(result.candidates[0].claims[0].value.flag)

    def test_int_1_rejected(self) -> None:
        doc = _with_claim_value(
            _minimal_doc(), {"kind": "boolean", "flag": 1}
        )
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_int_0_rejected(self) -> None:
        doc = _with_claim_value(
            _minimal_doc(), {"kind": "boolean", "flag": 0}
        )
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_missing_flag_rejected(self) -> None:
        doc = _with_claim_value(_minimal_doc(), {"kind": "boolean"})
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)


# ── value: enum ─────────────────────────────────────────────────────────────

class EnumValueTests(unittest.TestCase):
    def test_valid_enum(self) -> None:
        doc = _with_claim_value(
            _minimal_doc(), {"kind": "enum", "enum_value": "elder"}
        )
        result = validate_fact_candidate_document(doc)
        v = result.candidates[0].claims[0].value
        self.assertIsInstance(v, EnumValue)
        self.assertEqual(v.enum_value, "elder")

    def test_blank_rejected(self) -> None:
        doc = _with_claim_value(
            _minimal_doc(), {"kind": "enum", "enum_value": ""}
        )
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_bad_format_rejected(self) -> None:
        doc = _with_claim_value(
            _minimal_doc(), {"kind": "enum", "enum_value": "Not_Stable"}
        )
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)

    def test_missing_enum_value_rejected(self) -> None:
        doc = _with_claim_value(_minimal_doc(), {"kind": "enum"})
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(doc)


# ── value: unknown kind ────────────────────────────────────────────────────

class UnknownKindTests(unittest.TestCase):
    def test_unknown_kind_rejected(self) -> None:
        doc = _with_claim_value(
            _minimal_doc(), {"kind": "string", "text": "hello"}
        )
        with self.assertRaises(FactCandidateValidationError) as ctx:
            validate_fact_candidate_document(doc)
        self.assertTrue(any("kind" in i for i in ctx.exception.issues))


# ── non-dict root ───────────────────────────────────────────────────────────

class NonDictRootTests(unittest.TestCase):
    def test_list_rejected(self) -> None:
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document([1, 2, 3])

    def test_string_rejected(self) -> None:
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document("not a dict")

    def test_none_rejected(self) -> None:
        with self.assertRaises(FactCandidateValidationError):
            validate_fact_candidate_document(None)


# ── issues order ────────────────────────────────────────────────────────────

class IssuesOrderTests(unittest.TestCase):
    def test_issues_are_deterministic(self) -> None:
        """Same input produces same issues order."""
        doc = _minimal_doc()
        doc["candidates"][0]["claims"][0]["source_support"] = "bad"
        doc["candidates"][0]["claims"][0]["certainty"] = "bad"
        results = []
        for _ in range(5):
            try:
                validate_fact_candidate_document(doc)
            except FactCandidateValidationError as exc:
                results.append(exc.issues)
        self.assertTrue(all(r == results[0] for r in results))


# ── Schema parseable ────────────────────────────────────────────────────────

class SchemaParseTests(unittest.TestCase):
    def test_schema_is_valid_json(self) -> None:
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "fact_candidate.schema.json"
        raw = schema_path.read_text(encoding="utf-8")
        schema = json.loads(raw)
        self.assertIn("$schema", schema)
        self.assertIn("properties", schema)
        self.assertIn("$defs", schema)

    def test_non_blank_pattern_on_extracted_by(self) -> None:
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "fact_candidate.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        eb = schema["properties"]["extracted_by"]
        self.assertIn("pattern", eb, "extracted_by must have a whitespace-rejecting pattern")
        self.assertNotIn("minLength", eb, "extracted_by should rely on pattern, not just minLength")

    def test_non_blank_pattern_on_display_name(self) -> None:
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "fact_candidate.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        dn = schema["$defs"]["candidate"]["properties"]["display_name"]
        # display_name uses $ref to non_blank_string
        self.assertIn("$ref", dn)

    def test_non_blank_string_def_exists(self) -> None:
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "fact_candidate.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        nbs = schema["$defs"]["non_blank_string"]
        self.assertIn("pattern", nbs)
        self.assertIn("\\S", nbs["pattern"])

    def test_claim_has_if_then_else_for_inference_basis(self) -> None:
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "fact_candidate.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        claim = schema["$defs"]["claim"]
        self.assertIn("if", claim, "claim must have if/then/else for inference_basis")
        self.assertIn("then", claim)
        self.assertIn("else", claim)
        # if checks source_support == "inferred"
        self.assertEqual(claim["if"]["properties"]["source_support"]["const"], "inferred")
        # then requires non-blank inference_basis
        then_ib = claim["then"]["properties"]["inference_basis"]
        self.assertIn("$ref", then_ib)
        # else requires null
        else_ib = claim["else"]["properties"]["inference_basis"]
        self.assertEqual(else_ib["type"], "null")

    def test_text_value_uses_non_blank_pattern(self) -> None:
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "fact_candidate.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        text_prop = schema["$defs"]["text_value"]["properties"]["text"]
        self.assertIn("$ref", text_prop)

    def test_alias_items_use_non_blank_pattern(self) -> None:
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "fact_candidate.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        alias_items = schema["$defs"]["candidate"]["properties"]["aliases"]["items"]
        self.assertIn("$ref", alias_items)


# ── multi-candidate multi-claim ─────────────────────────────────────────────

class MultiCandidateTests(unittest.TestCase):
    def test_two_candidates_valid(self) -> None:
        doc = _minimal_doc()
        doc["candidates"].append({
            "candidate_id": "location_other",
            "entity_type": "location",
            "proposed_entity_id": "location_other",
            "display_name": "另一地点",
            "aliases": ["别名"],
            "claims": [{
                "claim_id": "claim_loc_desc",
                "predicate": "description",
                "value": {"kind": "text", "text": "描述文本。"},
                "source_chapters": ["chapter_000001"],
                "source_support": "explicit",
                "certainty": "certain",
                "inference_basis": None,
            }],
        })
        result = validate_fact_candidate_document(doc)
        self.assertEqual(len(result.candidates), 2)


# ── comprehensive value branch: missing kind ────────────────────────────────

class MissingKindTests(unittest.TestCase):
    def test_missing_kind_rejected(self) -> None:
        doc = _with_claim_value(_minimal_doc(), {"text": "hello"})
        with self.assertRaises(FactCandidateValidationError) as ctx:
            validate_fact_candidate_document(doc)
        self.assertTrue(any("kind" in i for i in ctx.exception.issues))


# ── integration: return type correctness ────────────────────────────────────

class ReturnTypeTests(unittest.TestCase):
    def test_returns_fact_candidate_document(self) -> None:
        doc = _minimal_doc()
        result = validate_fact_candidate_document(doc)
        self.assertIsInstance(result, FactCandidateDocument)

    def test_candidates_are_tuple(self) -> None:
        doc = _minimal_doc()
        result = validate_fact_candidate_document(doc)
        self.assertIsInstance(result.candidates, tuple)

    def test_claims_are_tuple(self) -> None:
        doc = _minimal_doc()
        result = validate_fact_candidate_document(doc)
        self.assertIsInstance(result.candidates[0].claims, tuple)

    def test_aliases_are_tuple(self) -> None:
        doc = _minimal_doc()
        doc["candidates"][0]["aliases"] = ["a", "b"]
        result = validate_fact_candidate_document(doc)
        self.assertIsInstance(result.candidates[0].aliases, tuple)

    def test_source_chapters_are_tuple(self) -> None:
        doc = _minimal_doc()
        result = validate_fact_candidate_document(doc)
        self.assertIsInstance(result.candidates[0].claims[0].source_chapters, tuple)


if __name__ == "__main__":
    unittest.main()
