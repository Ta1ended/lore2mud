"""Tests for pipeline.fact_reviews — v1 review document validation and binding."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from pipeline.fact_reviews import (
    FactReviewDocument,
    FactReviewValidationError,
    FactReviewBindingValidationError,
    ReviewDecision,
    validate_fact_review_document,
    validate_fact_review_bindings,
)
from pipeline.fact_candidates import FactCandidateDocument, validate_fact_candidate_document

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "fact_reviews"


def _valid_review() -> dict:
    return json.loads((FIXTURE_DIR / "valid_review.json").read_text(encoding="utf-8"))


def _minimal_review(**overrides: object) -> dict:
    d: dict = {
        "format_version": 1,
        "review_id": "review_test",
        "source_chapter": "chapter_000001",
        "reviewed_by": "test-human",
        "decisions": [{
            "candidate_id": "character_test",
            "claim_id": "claim_test",
            "state": "accepted",
            "reason": "原文明确。",
            "superseded_by_claim_id": None,
        }],
    }
    d.update(overrides)
    return d


def _make_candidate_doc(source_chapter: str = "chapter_000001") -> FactCandidateDocument:
    return validate_fact_candidate_document({
        "format_version": 1,
        "source_chapter": source_chapter,
        "extracted_by": "test",
        "candidates": [
            {
                "candidate_id": "character_fog_villager",
                "entity_type": "character",
                "proposed_entity_id": None,
                "display_name": "雾岭村民",
                "aliases": [],
                "claims": [
                    {"claim_id": "claim_fog_villager_origin", "predicate": "origin",
                     "value": {"kind": "text", "text": "出身。"},
                     "source_chapters": [source_chapter], "source_support": "explicit",
                     "certainty": "certain", "inference_basis": None},
                    {"claim_id": "claim_fog_villager_age", "predicate": "age",
                     "value": {"kind": "numeric", "number": 42, "unit": "years"},
                     "source_chapters": [source_chapter], "source_support": "inferred",
                     "certainty": "uncertain", "inference_basis": "推测。"},
                    {"claim_id": "claim_fog_villager_age_v2", "predicate": "age",
                     "value": {"kind": "numeric", "number": 45, "unit": "years"},
                     "source_chapters": [source_chapter], "source_support": "explicit",
                     "certainty": "certain", "inference_basis": None},
                    {"claim_id": "claim_fog_villager_alive", "predicate": "is_alive",
                     "value": {"kind": "boolean", "flag": True},
                     "source_chapters": [source_chapter], "source_support": "explicit",
                     "certainty": "certain", "inference_basis": None},
                ],
            },
            {
                "candidate_id": "location_fog_ridge",
                "entity_type": "location",
                "proposed_entity_id": None,
                "display_name": "雾岭小村",
                "aliases": [],
                "claims": [
                    {"claim_id": "claim_fog_ridge_type", "predicate": "location_type",
                     "value": {"kind": "enum", "enum_value": "village"},
                     "source_chapters": [source_chapter], "source_support": "explicit",
                     "certainty": "certain", "inference_basis": None},
                ],
            },
        ],
    })


# ── fixture loading ─────────────────────────────────────────────────────────

class FixtureTests(unittest.TestCase):
    def test_valid_review_fixture_loads(self) -> None:
        doc = validate_fact_review_document(_valid_review())
        self.assertIsInstance(doc, FactReviewDocument)
        self.assertEqual(doc.format_version, 1)
        self.assertEqual(doc.review_id, "review_character_fog_villager")
        self.assertEqual(len(doc.decisions), 4)

    def test_fixture_states(self) -> None:
        doc = validate_fact_review_document(_valid_review())
        states = [d.state for d in doc.decisions]
        self.assertEqual(states, ["accepted", "superseded", "rejected", "conflicted"])

    def test_fixture_superseded_has_bid(self) -> None:
        doc = validate_fact_review_document(_valid_review())
        self.assertEqual(doc.decisions[1].state, "superseded")
        self.assertEqual(doc.decisions[1].superseded_by_claim_id, "claim_fog_villager_age_v2")

    def test_fixture_binding_passes(self) -> None:
        review = validate_fact_review_document(_valid_review())
        cand = _make_candidate_doc()
        result = validate_fact_review_bindings(review, cand)
        self.assertEqual(result, review)


# ── frozen ──────────────────────────────────────────────────────────────────

class FrozenTests(unittest.TestCase):
    def test_document_frozen(self) -> None:
        doc = validate_fact_review_document(_minimal_review())
        with self.assertRaises(AttributeError):
            doc.format_version = 2  # type: ignore[misc]

    def test_decision_frozen(self) -> None:
        doc = validate_fact_review_document(_minimal_review())
        with self.assertRaises(AttributeError):
            doc.decisions[0].state = "rejected"  # type: ignore[misc]

    def test_decisions_is_tuple(self) -> None:
        doc = validate_fact_review_document(_minimal_review())
        self.assertIsInstance(doc.decisions, tuple)


# ── format_version ──────────────────────────────────────────────────────────

class FormatVersionTests(unittest.TestCase):
    def test_bool_rejected(self) -> None:
        with self.assertRaises(FactReviewValidationError):
            validate_fact_review_document(_minimal_review(format_version=True))

    def test_wrong_version_rejected(self) -> None:
        with self.assertRaises(FactReviewValidationError):
            validate_fact_review_document(_minimal_review(format_version=2))


# ── unknown fields ──────────────────────────────────────────────────────────

class UnknownFieldTests(unittest.TestCase):
    def test_root_unknown_rejected(self) -> None:
        d = _minimal_review()
        d["extra"] = 1
        with self.assertRaises(FactReviewValidationError) as ctx:
            validate_fact_review_document(d)
        self.assertTrue(any("未知字段" in i for i in ctx.exception.issues))

    def test_decision_unknown_rejected(self) -> None:
        d = _minimal_review()
        d["decisions"][0]["confidence"] = 0.9
        with self.assertRaises(FactReviewValidationError) as ctx:
            validate_fact_review_document(d)
        self.assertTrue(any("未知字段" in i for i in ctx.exception.issues))


# ── missing fields ──────────────────────────────────────────────────────────

class MissingFieldTests(unittest.TestCase):
    def test_missing_review_id(self) -> None:
        d = _minimal_review()
        del d["review_id"]
        with self.assertRaises(FactReviewValidationError):
            validate_fact_review_document(d)

    def test_missing_decisions(self) -> None:
        d = _minimal_review()
        del d["decisions"]
        with self.assertRaises(FactReviewValidationError):
            validate_fact_review_document(d)

    def test_missing_superseded_by_claim_id_key(self) -> None:
        d = _minimal_review()
        del d["decisions"][0]["superseded_by_claim_id"]
        with self.assertRaises(FactReviewValidationError) as ctx:
            validate_fact_review_document(d)
        self.assertTrue(any("superseded_by_claim_id" in i for i in ctx.exception.issues))


# ── blank values ────────────────────────────────────────────────────────────

class BlankValueTests(unittest.TestCase):
    def test_blank_review_id(self) -> None:
        with self.assertRaises(FactReviewValidationError):
            validate_fact_review_document(_minimal_review(review_id="   "))

    def test_blank_candidate_id(self) -> None:
        d = _minimal_review()
        d["decisions"][0]["candidate_id"] = ""
        with self.assertRaises(FactReviewValidationError):
            validate_fact_review_document(d)

    def test_blank_reason(self) -> None:
        d = _minimal_review()
        d["decisions"][0]["reason"] = "   "
        with self.assertRaises(FactReviewValidationError):
            validate_fact_review_document(d)


# ── empty decisions array ───────────────────────────────────────────────────

class EmptyDecisionsTests(unittest.TestCase):
    def test_empty_rejected(self) -> None:
        d = _minimal_review(decisions=[])
        with self.assertRaises(FactReviewValidationError):
            validate_fact_review_document(d)


# ── duplicate (candidate_id, claim_id) ──────────────────────────────────────

class DuplicatePairTests(unittest.TestCase):
    def test_duplicate_pair_rejected(self) -> None:
        d = _minimal_review()
        dec = d["decisions"][0].copy()
        d["decisions"].append(dec)
        with self.assertRaises(FactReviewValidationError) as ctx:
            validate_fact_review_document(d)
        self.assertTrue(any("重复" in i for i in ctx.exception.issues))


# ── state enum ──────────────────────────────────────────────────────────────

class StateTests(unittest.TestCase):
    def test_invalid_state_rejected(self) -> None:
        d = _minimal_review()
        d["decisions"][0]["state"] = "pending"
        with self.assertRaises(FactReviewValidationError):
            validate_fact_review_document(d)

    def test_all_states_accepted(self) -> None:
        for state in ("accepted", "rejected", "superseded", "conflicted"):
            d = _minimal_review()
            d["decisions"][0]["state"] = state
            if state == "superseded":
                d["decisions"][0]["superseded_by_claim_id"] = "claim_other"
            doc = validate_fact_review_document(d)
            self.assertEqual(doc.decisions[0].state, state)

    def test_state_non_string_rejected(self) -> None:
        d = _minimal_review()
        d["decisions"][0]["state"] = 123
        with self.assertRaises(FactReviewValidationError):
            validate_fact_review_document(d)


# ── superseded_by_claim_id conditional ──────────────────────────────────────

class SupersededConditionalTests(unittest.TestCase):
    def test_superseded_null_bid_rejected(self) -> None:
        d = _minimal_review()
        d["decisions"][0]["state"] = "superseded"
        with self.assertRaises(FactReviewValidationError) as ctx:
            validate_fact_review_document(d)
        self.assertTrue(any("superseded_by_claim_id" in i for i in ctx.exception.issues))

    def test_superseded_blank_bid_rejected(self) -> None:
        d = _minimal_review()
        d["decisions"][0]["state"] = "superseded"
        d["decisions"][0]["superseded_by_claim_id"] = "   "
        with self.assertRaises(FactReviewValidationError):
            validate_fact_review_document(d)

    def test_accepted_requires_null_bid(self) -> None:
        d = _minimal_review()
        d["decisions"][0]["superseded_by_claim_id"] = "claim_other"
        with self.assertRaises(FactReviewValidationError) as ctx:
            validate_fact_review_document(d)
        self.assertTrue(any("superseded_by_claim_id" in i for i in ctx.exception.issues))

    def test_rejected_requires_null_bid(self) -> None:
        d = _minimal_review()
        d["decisions"][0]["state"] = "rejected"
        d["decisions"][0]["superseded_by_claim_id"] = "claim_other"
        with self.assertRaises(FactReviewValidationError):
            validate_fact_review_document(d)

    def test_conflicted_requires_null_bid(self) -> None:
        d = _minimal_review()
        d["decisions"][0]["state"] = "conflicted"
        d["decisions"][0]["superseded_by_claim_id"] = "claim_other"
        with self.assertRaises(FactReviewValidationError):
            validate_fact_review_document(d)


# ── partial review (not all claims covered) ─────────────────────────────────

class PartialReviewTests(unittest.TestCase):
    def test_partial_review_accepted(self) -> None:
        """Only some claims reviewed; rest unreviewed."""
        d = _valid_review()
        d["decisions"] = d["decisions"][:2]
        validate_fact_review_document(d)


# ── source chapter binding ──────────────────────────────────────────────────

class SourceChapterBindingTests(unittest.TestCase):
    def test_mismatch_rejected(self) -> None:
        review = validate_fact_review_document(_minimal_review())
        cand = _make_candidate_doc(source_chapter="chapter_000002")
        with self.assertRaises(FactReviewBindingValidationError) as ctx:
            validate_fact_review_bindings(review, cand)
        self.assertTrue(any("source_chapter" in i for i in ctx.exception.issues))

    def test_match_accepted(self) -> None:
        review = validate_fact_review_document(_minimal_review(
            source_chapter="chapter_000002",
            decisions=[{
                "candidate_id": "character_fog_villager",
                "claim_id": "claim_fog_villager_origin",
                "state": "accepted",
                "reason": "confirmed.",
                "superseded_by_claim_id": None,
            }],
        ))
        cand = _make_candidate_doc(source_chapter="chapter_000002")
        result = validate_fact_review_bindings(review, cand)
        self.assertEqual(result, review)


# ── candidate_id / claim_id binding ─────────────────────────────────────────

class CandidateClaimBindingTests(unittest.TestCase):
    def test_missing_candidate_rejected(self) -> None:
        d = _minimal_review()
        d["decisions"][0]["candidate_id"] = "nonexistent"
        review = validate_fact_review_document(d)
        with self.assertRaises(FactReviewBindingValidationError) as ctx:
            validate_fact_review_bindings(review, _make_candidate_doc())
        self.assertTrue(any("不存在" in i for i in ctx.exception.issues))

    def test_missing_claim_rejected(self) -> None:
        d = _minimal_review()
        d["decisions"][0]["candidate_id"] = "character_fog_villager"
        d["decisions"][0]["claim_id"] = "nonexistent"
        review = validate_fact_review_document(d)
        with self.assertRaises(FactReviewBindingValidationError) as ctx:
            validate_fact_review_bindings(review, _make_candidate_doc())
        self.assertTrue(any("不属于" in i for i in ctx.exception.issues))


# ── supersede self-reference ────────────────────────────────────────────────

class SupersedeSelfTests(unittest.TestCase):
    def test_self_supersede_rejected(self) -> None:
        review = validate_fact_review_document(_minimal_review(
            decisions=[{
                "candidate_id": "character_fog_villager",
                "claim_id": "claim_fog_villager_origin",
                "state": "superseded",
                "reason": "self-ref",
                "superseded_by_claim_id": "claim_fog_villager_origin",
            }],
        ))
        with self.assertRaises(FactReviewBindingValidationError) as ctx:
            validate_fact_review_bindings(review, _make_candidate_doc())
        self.assertTrue(any("自身" in i for i in ctx.exception.issues))


# ── supersede cross-candidate ───────────────────────────────────────────────

class SupersedeCrossCandidateTests(unittest.TestCase):
    def test_cross_candidate_supersede_rejected(self) -> None:
        review = validate_fact_review_document(_minimal_review(
            decisions=[{
                "candidate_id": "character_fog_villager",
                "claim_id": "claim_fog_villager_origin",
                "state": "superseded",
                "reason": "cross-candidate",
                "superseded_by_claim_id": "claim_fog_ridge_type",
            }],
        ))
        with self.assertRaises(FactReviewBindingValidationError) as ctx:
            validate_fact_review_bindings(review, _make_candidate_doc())
        self.assertTrue(any("不属于" in i for i in ctx.exception.issues))


# ── non FactCandidateDocument binding ───────────────────────────────────────

class NonDocumentBindingTests(unittest.TestCase):
    def test_non_doc_rejected(self) -> None:
        review = validate_fact_review_document(_minimal_review())
        with self.assertRaises(FactReviewBindingValidationError) as ctx:
            validate_fact_review_bindings(review, "bad")
        self.assertTrue(any("FactCandidateDocument" in i for i in ctx.exception.issues))

    def test_none_rejected(self) -> None:
        review = validate_fact_review_document(_minimal_review())
        with self.assertRaises(FactReviewBindingValidationError):
            validate_fact_review_bindings(review, None)

    def test_dict_rejected(self) -> None:
        review = validate_fact_review_document(_minimal_review())
        with self.assertRaises(FactReviewBindingValidationError):
            validate_fact_review_bindings(review, {"key": "val"})


# ── binding does not modify input ───────────────────────────────────────────

class BindingImmutabilityTests(unittest.TestCase):
    def test_binding_returns_same_review(self) -> None:
        review = validate_fact_review_document(_minimal_review(
            decisions=[{
                "candidate_id": "character_fog_villager",
                "claim_id": "claim_fog_villager_origin",
                "state": "accepted",
                "reason": "confirmed.",
                "superseded_by_claim_id": None,
            }],
        ))
        result = validate_fact_review_bindings(review, _make_candidate_doc())
        self.assertIs(result, review)


# ── non-dict root ───────────────────────────────────────────────────────────

class NonDictRootTests(unittest.TestCase):
    def test_list_rejected(self) -> None:
        with self.assertRaises(FactReviewValidationError):
            validate_fact_review_document([1, 2])

    def test_none_rejected(self) -> None:
        with self.assertRaises(FactReviewValidationError):
            validate_fact_review_document(None)


# ── issues order determinism ────────────────────────────────────────────────

class IssuesOrderTests(unittest.TestCase):
    def test_deterministic(self) -> None:
        d = _minimal_review(format_version=2)
        d["decisions"][0]["state"] = "bad"
        results = []
        for _ in range(3):
            try:
                validate_fact_review_document(d)
            except FactReviewValidationError as e:
                results.append(e.issues)
        self.assertTrue(all(r == results[0] for r in results))


# ── Schema structure ────────────────────────────────────────────────────────

class SchemaParseTests(unittest.TestCase):
    def test_schema_valid_json(self) -> None:
        p = Path(__file__).resolve().parents[1] / "schemas" / "fact_review.schema.json"
        s = json.loads(p.read_text(encoding="utf-8"))
        self.assertIn("$schema", s)
        self.assertIn("$defs", s)

    def test_decision_has_if_then_else(self) -> None:
        p = Path(__file__).resolve().parents[1] / "schemas" / "fact_review.schema.json"
        s = json.loads(p.read_text(encoding="utf-8"))
        dec = s["$defs"]["decision"]
        self.assertIn("if", dec)
        self.assertIn("then", dec)
        self.assertIn("else", dec)
        self.assertEqual(dec["if"]["properties"]["state"]["const"], "superseded")


if __name__ == "__main__":
    unittest.main()
