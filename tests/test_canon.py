"""Tests for pipeline.canon — L2W-1 canon draft promotion."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest import mock

from pipeline.canon import (
    CanonBooleanValue,
    CanonDraft,
    CanonDraftBuildingError,
    CanonDraftValidationError,
    CanonEntity,
    CanonEnumValue,
    CanonNumericValue,
    CanonRelationValue,
    CanonTextValue,
    EntityPromotionMapping,
    PromotionPlan,
    build_canon_draft,
    validate_canon_draft_document,
    validate_canon_promotion_plan,
    _sorted_json_dict,
)
from pipeline.chapter_manifests import validate_chapter_manifest
from pipeline.fact_candidates import validate_fact_candidate_document
from pipeline.fact_reviews import validate_fact_review_document, FactReviewDocument

REPO = Path(__file__).resolve().parents[1]


# ── factory helpers ─────────────────────────────────────────────────────────

def _valid_candidate() -> dict:
    return {
        "format_version": 1,
        "source_chapter": "chapter_000001",
        "extracted_by": "test-extractor/v1",
        "candidates": [
            {
                "candidate_id": "character_fog_villager",
                "entity_type": "character",
                "proposed_entity_id": None,
                "display_name": "雾岭村民",
                "aliases": ["老村民"],
                "claims": [
                    {"claim_id": "claim_origin", "predicate": "origin",
                     "value": {"kind": "text", "text": "出身于雾岭小村。"},
                     "source_chapters": ["chapter_000001"], "source_support": "explicit",
                     "certainty": "certain", "inference_basis": None},
                    {"claim_id": "claim_age", "predicate": "age",
                     "value": {"kind": "numeric", "number": 42, "unit": "years"},
                     "source_chapters": ["chapter_000001"], "source_support": "inferred",
                     "certainty": "uncertain", "inference_basis": "推测。"},
                    {"claim_id": "claim_alive", "predicate": "is_alive",
                     "value": {"kind": "boolean", "flag": True},
                     "source_chapters": ["chapter_000001"], "source_support": "explicit",
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
                    {"claim_id": "claim_type", "predicate": "location_type",
                     "value": {"kind": "enum", "enum_value": "village"},
                     "source_chapters": ["chapter_000001"], "source_support": "explicit",
                     "certainty": "certain", "inference_basis": None},
                    {"claim_id": "claim_inhabited", "predicate": "inhabited_by",
                     "value": {"kind": "relation", "candidate_ref": "character_fog_villager"},
                     "source_chapters": ["chapter_000001"], "source_support": "explicit",
                     "certainty": "certain", "inference_basis": None},
                ],
            },
        ],
    }


def _valid_review() -> dict:
    return {
        "format_version": 1,
        "review_id": "review_ch001",
        "source_chapter": "chapter_000001",
        "reviewed_by": "human-reviewer",
        "decisions": [
            {"candidate_id": "character_fog_villager", "claim_id": "claim_origin",
             "state": "accepted", "reason": "原文明确。", "superseded_by_claim_id": None},
            {"candidate_id": "character_fog_villager", "claim_id": "claim_age",
             "state": "accepted", "reason": "合逻辑推断。", "superseded_by_claim_id": None},
            {"candidate_id": "character_fog_villager", "claim_id": "claim_alive",
             "state": "accepted", "reason": "文中明确。", "superseded_by_claim_id": None},
            {"candidate_id": "location_fog_ridge", "claim_id": "claim_type",
             "state": "accepted", "reason": "明确。", "superseded_by_claim_id": None},
            {"candidate_id": "location_fog_ridge", "claim_id": "claim_inhabited",
             "state": "accepted", "reason": "文中陈述。", "superseded_by_claim_id": None},
        ],
    }


def _valid_manifest() -> dict:
    return {
        "format_version": 2,
        "source_encoding": "utf-8-sig",
        "chapter_count": 1,
        "chapters": [{
            "chapter_id": "chapter_000001", "title": "第一章 测试",
            "source_chapter_label": "第一章", "source_title": "测试",
            "volume_label": "第一卷", "source_offset": 0, "source_line": 1,
            "path": "chapter_000001.txt", "character_count": 100,
            "sha256": "a" * 64, "previous_id": None, "next_id": None,
        }],
    }


def _valid_plan() -> dict:
    return {
        "format_version": 1,
        "promotion_id": "promo_ch001",
        "source_chapter": "chapter_000001",
        "review_id": "review_ch001",
        "entity_mappings": [
            {
                "candidate_id": "character_fog_villager",
                "entity_id": "canon_char_fog_villager",
                "canonical_name": "雾岭老村民",
                "aliases": ["老村民"],
            },
            {
                "candidate_id": "location_fog_ridge",
                "entity_id": "canon_loc_fog_ridge",
                "canonical_name": "雾岭小村",
                "aliases": ["雾岭"],
            },
        ],
    }


def _build_all():
    """Return validated manifest, candidate, review, plan."""
    m = validate_chapter_manifest(_valid_manifest())
    c = validate_fact_candidate_document(_valid_candidate())
    r = validate_fact_review_document(_valid_review())
    p = validate_canon_promotion_plan(_valid_plan())
    return m, c, r, p


# ── PromotionPlan validation ────────────────────────────────────────────────

class PlanValidationTests(unittest.TestCase):
    def test_valid_plan(self) -> None:
        p = validate_canon_promotion_plan(_valid_plan())
        self.assertEqual(p.format_version, 1)
        self.assertEqual(p.promotion_id, "promo_ch001")
        self.assertEqual(len(p.entity_mappings), 2)

    def test_bool_version_rejected(self) -> None:
        d = _valid_plan()
        d["format_version"] = True
        with self.assertRaises(CanonDraftValidationError):
            validate_canon_promotion_plan(d)

    def test_duplicate_candidate_id_rejected(self) -> None:
        d = _valid_plan()
        d["entity_mappings"].append(d["entity_mappings"][0].copy())
        with self.assertRaises(CanonDraftValidationError) as ctx:
            validate_canon_promotion_plan(d)
        self.assertTrue(any("重复" in i for i in ctx.exception.issues))

    def test_duplicate_entity_id_rejected(self) -> None:
        d = _valid_plan()
        d["entity_mappings"].append({
            "candidate_id": "other", "entity_id": "canon_char_fog_villager",
            "canonical_name": "其他", "aliases": [],
        })
        with self.assertRaises(CanonDraftValidationError):
            validate_canon_promotion_plan(d)

    def test_alias_equals_canonical_name_rejected(self) -> None:
        d = _valid_plan()
        d["entity_mappings"][0]["aliases"] = ["雾岭老村民"]
        with self.assertRaises(CanonDraftValidationError) as ctx:
            validate_canon_promotion_plan(d)
        self.assertTrue(any("canonical_name" in i for i in ctx.exception.issues))

    def test_blank_canonical_name_rejected(self) -> None:
        d = _valid_plan()
        d["entity_mappings"][0]["canonical_name"] = "   "
        with self.assertRaises(CanonDraftValidationError):
            validate_canon_promotion_plan(d)

    def test_unknown_field_rejected(self) -> None:
        d = _valid_plan()
        d["extra"] = 1
        with self.assertRaises(CanonDraftValidationError):
            validate_canon_promotion_plan(d)


# ── build_canon_draft ───────────────────────────────────────────────────────

class BuildDraftTests(unittest.TestCase):
    def test_valid_build(self) -> None:
        m, c, r, p = _build_all()
        draft = build_canon_draft(r, c, m, p)
        self.assertIsInstance(draft, CanonDraft)
        self.assertEqual(draft.promotion_id, "promo_ch001")
        self.assertEqual(len(draft.entities), 2)

    def test_character_has_three_claims(self) -> None:
        m, c, r, p = _build_all()
        draft = build_canon_draft(r, c, m, p)
        char_entity = [e for e in draft.entities if e.entity_id == "canon_char_fog_villager"][0]
        self.assertEqual(len(char_entity.claims), 3)
        self.assertEqual(char_entity.entity_type, "character")

    def test_location_has_two_claims(self) -> None:
        m, c, r, p = _build_all()
        draft = build_canon_draft(r, c, m, p)
        loc_entity = [e for e in draft.entities if e.entity_id == "canon_loc_fog_ridge"][0]
        self.assertEqual(len(loc_entity.claims), 2)

    def test_relation_rewritten_to_entity_ref(self) -> None:
        m, c, r, p = _build_all()
        draft = build_canon_draft(r, c, m, p)
        loc_entity = [e for e in draft.entities if e.entity_id == "canon_loc_fog_ridge"][0]
        rel_claim = [cl for cl in loc_entity.claims if cl.claim_id == "claim_inhabited"][0]
        self.assertIsInstance(rel_claim.value, CanonRelationValue)
        self.assertEqual(rel_claim.value.entity_ref, "canon_char_fog_villager")

    def test_source_fields_copied(self) -> None:
        m, c, r, p = _build_all()
        draft = build_canon_draft(r, c, m, p)
        self.assertEqual(draft.source.chapter_id, "chapter_000001")
        self.assertEqual(draft.source.chapter_sha256, "a" * 64)
        self.assertEqual(draft.extracted_by, "test-extractor/v1")
        self.assertEqual(draft.review_id, "review_ch001")
        self.assertEqual(draft.reviewed_by, "human-reviewer")

    def test_claim_fields_preserved(self) -> None:
        m, c, r, p = _build_all()
        draft = build_canon_draft(r, c, m, p)
        char_entity = [e for e in draft.entities if e.entity_id == "canon_char_fog_villager"][0]
        age_claim = [cl for cl in char_entity.claims if cl.claim_id == "claim_age"][0]
        self.assertEqual(age_claim.source_support, "inferred")
        self.assertEqual(age_claim.certainty, "uncertain")
        self.assertEqual(age_claim.inference_basis, "推测。")
        self.assertEqual(age_claim.review_reason, "合逻辑推断。")

    def test_source_support_explicit(self) -> None:
        m, c, r, p = _build_all()
        draft = build_canon_draft(r, c, m, p)
        char_entity = [e for e in draft.entities if e.entity_id == "canon_char_fog_villager"][0]
        origin_claim = [cl for cl in char_entity.claims if cl.claim_id == "claim_origin"][0]
        self.assertEqual(origin_claim.source_support, "explicit")
        self.assertIsNone(origin_claim.inference_basis)

    def test_no_generated_at(self) -> None:
        m, c, r, p = _build_all()
        draft = build_canon_draft(r, c, m, p)
        raw = _sorted_json_dict(draft)
        self.assertNotIn("generated_at", raw)

    def test_rejected_claim_excluded(self) -> None:
        m, c, r, p = _build_all()
        # Mark claim_alive as rejected
        r2_dict = _valid_review()
        for dec in r2_dict["decisions"]:
            if dec["claim_id"] == "claim_alive":
                dec["state"] = "rejected"
        r2 = validate_fact_review_document(r2_dict)
        draft = build_canon_draft(r2, c, m, p)
        char_entity = [e for e in draft.entities if e.entity_id == "canon_char_fog_villager"][0]
        claim_ids = [cl.claim_id for cl in char_entity.claims]
        self.assertIn("claim_origin", claim_ids)
        self.assertIn("claim_age", claim_ids)
        self.assertNotIn("claim_alive", claim_ids)

    def test_superseded_claim_excluded(self) -> None:
        m, c, r, p = _build_all()
        r2_dict = _valid_review()
        for dec in r2_dict["decisions"]:
            if dec["claim_id"] == "claim_origin":
                dec["state"] = "superseded"
                dec["superseded_by_claim_id"] = "claim_age"
        r2 = validate_fact_review_document(r2_dict)
        draft = build_canon_draft(r2, c, m, p)
        char_entity = [e for e in draft.entities if e.entity_id == "canon_char_fog_villager"][0]
        claim_ids = [cl.claim_id for cl in char_entity.claims]
        self.assertNotIn("claim_origin", claim_ids)
        self.assertIn("claim_age", claim_ids)
        self.assertIn("claim_alive", claim_ids)

    def test_closure_extra_mapping_rejected(self) -> None:
        """Plan maps a candidate that exists but has no accepted claims and
        is not a relation target — must be rejected as extra closure mapping."""
        # Create candidate doc with third candidate that has only rejected claims
        cd = _valid_candidate()
        cd["candidates"].append({
            "candidate_id": "item_stone",
            "entity_type": "item",
            "proposed_entity_id": None,
            "display_name": "石头",
            "aliases": [],
            "claims": [{
                "claim_id": "claim_stone",
                "predicate": "description",
                "value": {"kind": "text", "text": "一块石头。"},
                "source_chapters": ["chapter_000001"],
                "source_support": "explicit", "certainty": "certain",
                "inference_basis": None,
            }],
        })
        c2 = validate_fact_candidate_document(cd)
        # Review: reject the stone's claim
        rd = _valid_review()
        rd["decisions"].append({
            "candidate_id": "item_stone", "claim_id": "claim_stone",
            "state": "rejected", "reason": "no", "superseded_by_claim_id": None,
        })
        r2 = validate_fact_review_document(rd)
        # Plan: include stone mapping (extra to closure)
        p2_dict = _valid_plan()
        p2_dict["entity_mappings"].append({
            "candidate_id": "item_stone", "entity_id": "canon_item_stone",
            "canonical_name": "石头", "aliases": [],
        })
        p2 = validate_canon_promotion_plan(p2_dict)
        m2 = validate_chapter_manifest(_valid_manifest())
        with self.assertRaises(CanonDraftBuildingError) as ctx:
            build_canon_draft(r2, c2, m2, p2)
        self.assertTrue(any("冗余" in i for i in ctx.exception.issues))

    def test_closure_missing_mapping_rejected(self) -> None:
        m, c, r, p = _build_all()
        p2_dict = _valid_plan()
        p2_dict["entity_mappings"] = [p2_dict["entity_mappings"][0]]
        p2 = validate_canon_promotion_plan(p2_dict)
        with self.assertRaises(CanonDraftBuildingError) as ctx:
            build_canon_draft(r, c, m, p2)
        self.assertTrue(any("缺少" in i for i in ctx.exception.issues))

    def test_empty_closure_rejected(self) -> None:
        m, c, r, p = _build_all()
        r2_dict = _valid_review()
        for dec in r2_dict["decisions"]:
            dec["state"] = "rejected"
        r2 = validate_fact_review_document(r2_dict)
        with self.assertRaises(CanonDraftBuildingError) as ctx:
            build_canon_draft(r2, c, m, p)
        self.assertTrue(any("为空" in i for i in ctx.exception.issues))

    def test_plan_review_id_mismatch_rejected(self) -> None:
        m, c, r, p = _build_all()
        p2_dict = _valid_plan()
        p2_dict["review_id"] = "wrong_review"
        p2 = validate_canon_promotion_plan(p2_dict)
        with self.assertRaises(CanonDraftBuildingError) as ctx:
            build_canon_draft(r, c, m, p2)
        self.assertTrue(any("review_id" in i for i in ctx.exception.issues))

    def test_source_chapter_mismatch_rejected(self) -> None:
        m, c, r, p = _build_all()
        p2_dict = _valid_plan()
        p2_dict["source_chapter"] = "chapter_000002"
        p2 = validate_canon_promotion_plan(p2_dict)
        with self.assertRaises(CanonDraftBuildingError) as ctx:
            build_canon_draft(r, c, m, p2)
        self.assertTrue(any("source_chapter" in i for i in ctx.exception.issues))

    def test_relation_only_entity_output(self) -> None:
        """Third candidate: no accepted own claims, but referenced by accepted
        relation from another candidate. Must be promoted as zero-claim entity
        with relation correctly rewritten to entity_ref."""
        cd = _valid_candidate()
        # Add third candidate with no accepted claims
        cd["candidates"].append({
            "candidate_id": "item_herb",
            "entity_type": "item",
            "proposed_entity_id": None,
            "display_name": "草药",
            "aliases": [],
            "claims": [{
                "claim_id": "claim_herb_desc",
                "predicate": "description",
                "value": {"kind": "text", "text": "草药。"},
                "source_chapters": ["chapter_000001"],
                "source_support": "explicit", "certainty": "certain",
                "inference_basis": None,
            }],
        })
        # Add relation claim from villager → herb
        cd["candidates"][0]["claims"].append({
            "claim_id": "claim_has_herb",
            "predicate": "possesses",
            "value": {"kind": "relation", "candidate_ref": "item_herb"},
            "source_chapters": ["chapter_000001"],
            "source_support": "explicit", "certainty": "certain",
            "inference_basis": None,
        })
        c2 = validate_fact_candidate_document(cd)
        # Review: reject herb's own claim, accept villager's claims including herb relation
        rd = _valid_review()
        rd["decisions"].append({
            "candidate_id": "item_herb", "claim_id": "claim_herb_desc",
            "state": "rejected", "reason": "不可信。", "superseded_by_claim_id": None,
        })
        rd["decisions"].append({
            "candidate_id": "character_fog_villager", "claim_id": "claim_has_herb",
            "state": "accepted", "reason": "明确。", "superseded_by_claim_id": None,
        })
        r2 = validate_fact_review_document(rd)
        # Plan: include herb mapping
        pp = _valid_plan()
        pp["entity_mappings"].append({
            "candidate_id": "item_herb", "entity_id": "canon_item_herb",
            "canonical_name": "草药", "aliases": [],
        })
        p2 = validate_canon_promotion_plan(pp)
        m2 = validate_chapter_manifest(_valid_manifest())
        draft = build_canon_draft(r2, c2, m2, p2)
        # Villager entity has the herb relation
        char_entity = [e for e in draft.entities if e.entity_id == "canon_char_fog_villager"][0]
        rel_claim = [cl for cl in char_entity.claims if cl.claim_id == "claim_has_herb"][0]
        self.assertIsInstance(rel_claim.value, CanonRelationValue)
        self.assertEqual(rel_claim.value.entity_ref, "canon_item_herb")
        # Herb entity exists with zero claims
        herb_entity = [e for e in draft.entities if e.entity_id == "canon_item_herb"]
        self.assertEqual(len(herb_entity), 1)
        self.assertEqual(len(herb_entity[0].claims), 0)
        self.assertEqual(herb_entity[0].entity_type, "item")

    # ── P1-1: binding contract enforcement tests ──────────────────────────

    def test_accepted_decision_unknown_claim_rejected(self) -> None:
        m, c, _, p = _build_all()
        rd = _valid_review()
        rd["decisions"].append({
            "candidate_id": "character_fog_villager",
            "claim_id": "nonexistent_claim",
            "state": "accepted", "reason": "n/a",
            "superseded_by_claim_id": None,
        })
        r2 = validate_fact_review_document(rd)
        with self.assertRaises(CanonDraftBuildingError) as ctx:
            build_canon_draft(r2, c, m, p)
        self.assertTrue(any("review 绑定失败" in i for i in ctx.exception.issues))

    def test_accepted_decision_wrong_candidate_rejected(self) -> None:
        m, c, _, p = _build_all()
        rd = _valid_review()
        rd["decisions"].append({
            "candidate_id": "wrong_candidate",
            "claim_id": "claim_origin",
            "state": "accepted", "reason": "n/a",
            "superseded_by_claim_id": None,
        })
        r2 = validate_fact_review_document(rd)
        with self.assertRaises(CanonDraftBuildingError) as ctx:
            build_canon_draft(r2, c, m, p)
        self.assertTrue(any("review 绑定失败" in i for i in ctx.exception.issues))

    def test_superseded_target_nonexistent_rejected(self) -> None:
        m, c, _, p = _build_all()
        rd = _valid_review()
        for dec in rd["decisions"]:
            if dec["claim_id"] == "claim_origin":
                dec["state"] = "superseded"
                dec["superseded_by_claim_id"] = "nonexistent"
        r2 = validate_fact_review_document(rd)
        with self.assertRaises(CanonDraftBuildingError) as ctx:
            build_canon_draft(r2, c, m, p)
        self.assertTrue(any("review 绑定失败" in i for i in ctx.exception.issues))

    # ── P1-2: two-pass entity_ref tests ──────────────────────────────────

    def test_forward_entity_ref_accepted(self) -> None:
        """entity_ref to entity whose entity_id is later in sort order."""
        m, c, r, p = _build_all()
        draft = build_canon_draft(r, c, m, p)
        loc_entity = [e for e in draft.entities if e.entity_id == "canon_loc_fog_ridge"][0]
        rel_claim = [cl for cl in loc_entity.claims if cl.claim_id == "claim_inhabited"][0]
        self.assertEqual(rel_claim.value.entity_ref, "canon_char_fog_villager")

    def test_entities_reversed_still_accepted(self) -> None:
        """Reverse entity order in draft validation - entity_ref must resolve."""
        m, c, r, p = _build_all()
        draft = build_canon_draft(r, c, m, p)
        raw = _sorted_json_dict(draft)
        # Reverse entities in the raw dict
        raw["entities"].reverse()
        # Must still validate because entity_ids are pre-collected
        validate_canon_draft_document(raw)

    # ── Schema structure tests ────────────────────────────────────────────

    def test_schema_draft_2020_12(self) -> None:
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "canon_draft.schema.json"
        with open(schema_path, encoding="utf-8") as f:
            schema = json.load(f)
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertIn("$defs", schema)
        self.assertIn("claim", schema["$defs"])
        self.assertIn("allOf", schema["$defs"]["claim"])

    def test_schema_no_candidate_ref(self) -> None:
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "canon_draft.schema.json"
        with open(schema_path, encoding="utf-8") as f:
            schema = json.load(f)
        raw = json.dumps(schema)
        self.assertNotIn("candidate_ref", raw)
        self.assertIn("entity_ref", raw)

    def test_schema_inference_condition(self) -> None:
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "canon_draft.schema.json"
        with open(schema_path, encoding="utf-8") as f:
            schema = json.load(f)
        claim_def = schema["$defs"]["claim"]
        all_of = claim_def.get("allOf", [])
        self.assertEqual(len(all_of), 2)
        self.assertEqual(all_of[0]["if"]["properties"]["source_support"]["const"], "inferred")
        self.assertEqual(all_of[0]["then"]["properties"]["inference_basis"]["type"], "string")
        self.assertEqual(all_of[1]["if"]["properties"]["source_support"]["const"], "explicit")
        self.assertEqual(all_of[1]["then"]["properties"]["inference_basis"]["type"], "null")

    def test_schema_five_branch_oneOf(self) -> None:
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "canon_draft.schema.json"
        with open(schema_path, encoding="utf-8") as f:
            schema = json.load(f)
        one_of = schema["$defs"]["canon_value"]["oneOf"]
        self.assertEqual(len(one_of), 5)
        kinds = set()
        defs = schema["$defs"]
        for branch in one_of:
            ref = branch.get("$ref", "")
            ref_name = ref.rsplit("/", 1)[-1]
            if ref_name and ref_name in defs:
                kinds.add(defs[ref_name]["properties"]["kind"]["const"])
            elif "properties" in branch:
                kinds.add(branch["properties"]["kind"]["const"])
        self.assertEqual(kinds, {"text", "relation", "numeric", "boolean", "enum"})

    def test_schema_required_additional_properties(self) -> None:
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "canon_draft.schema.json"
        with open(schema_path, encoding="utf-8") as f:
            schema = json.load(f)
        self.assertTrue(schema["additionalProperties"] is False)
        self.assertIn("entities", schema["required"])


# ── CanonDraft re-validation ────────────────────────────────────────────────

class RevalidateTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        m, c, r, p = _build_all()
        draft = build_canon_draft(r, c, m, p)
        raw = _sorted_json_dict(draft)
        revalidated = validate_canon_draft_document(raw)
        self.assertEqual(len(revalidated.entities), len(draft.entities))

    def test_hanging_relation_entity_ref_rejected(self) -> None:
        raw = {
            "format_version": 1,
            "promotion_id": "test",
            "source": {"chapter_id": "chapter_000001", "chapter_sha256": "a" * 64},
            "extracted_by": "test",
            "review_id": "review_test",
            "reviewed_by": "test",
            "entities": [{
                "entity_id": "canon_char",
                "entity_type": "character",
                "canonical_name": "角色", "aliases": [],
                "source_candidate_id": "char",
                "claims": [{
                    "claim_id": "c1", "predicate": "origin",
                    "value": {"kind": "relation", "entity_ref": "nonexistent"},
                    "source_chapters": ["chapter_000001"],
                    "source_support": "explicit", "certainty": "certain",
                    "inference_basis": None, "review_reason": "ok.",
                }],
            }],
        }
        with self.assertRaises(CanonDraftValidationError) as ctx:
            validate_canon_draft_document(raw)
        self.assertTrue(any("不存在的" in i for i in ctx.exception.issues))


# ── frozen ──────────────────────────────────────────────────────────────────

class FrozenTests(unittest.TestCase):
    def test_draft_frozen(self) -> None:
        m, c, r, p = _build_all()
        draft = build_canon_draft(r, c, m, p)
        with self.assertRaises(AttributeError):
            draft.format_version = 2  # type: ignore[misc]

    def test_entity_frozen(self) -> None:
        m, c, r, p = _build_all()
        draft = build_canon_draft(r, c, m, p)
        with self.assertRaises(AttributeError):
            draft.entities[0].canonical_name = "changed"  # type: ignore[misc]


# ── deterministic ordering ─────────────────────────────────────────────────

class OrderingTests(unittest.TestCase):
    def test_entities_sorted_by_entity_id(self) -> None:
        m, c, r, p = _build_all()
        draft = build_canon_draft(r, c, m, p)
        eids = [e.entity_id for e in draft.entities]
        self.assertEqual(eids, sorted(eids))

    def test_claims_sorted_by_claim_id(self) -> None:
        m, c, r, p = _build_all()
        draft = build_canon_draft(r, c, m, p)
        for entity in draft.entities:
            cids = [cl.claim_id for cl in entity.claims]
            self.assertEqual(cids, sorted(cids))

    def test_byte_identical_with_different_input_order(self) -> None:
        """Different input candidate order must produce byte-identical output."""
        m1, c1, r1, p1 = _build_all()
        d1 = build_canon_draft(r1, c1, m1, p1)

        # Reverse candidate order in candidate doc
        cd = _valid_candidate()
        cd["candidates"].reverse()
        c2 = validate_fact_candidate_document(cd)
        d2 = build_canon_draft(r1, c2, m1, p1)

        json1 = json.dumps(_sorted_json_dict(d1), sort_keys=True, indent=2)
        json2 = json.dumps(_sorted_json_dict(d2), sort_keys=True, indent=2)
        self.assertEqual(json1, json2)


# ── CLI ─────────────────────────────────────────────────────────────────────

class CLITests(unittest.TestCase):
    def _write_inputs(self, tmp: str) -> dict[str, str]:
        paths = {}
        for name, data in [
            ("manifest.json", _valid_manifest()),
            ("candidate.json", _valid_candidate()),
            ("review.json", _valid_review()),
            ("plan.json", _valid_plan()),
        ]:
            path = os.path.join(tmp, name)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            paths[name.replace(".json", "")] = path
        return paths

    def test_cli_success(self) -> None:
        from pipeline.canon import main
        with tempfile.TemporaryDirectory() as td:
            paths = self._write_inputs(td)
            out = os.path.join(td, "draft.json")
            exit_code = main([
                "--promotion-plan", paths["plan"],
                "--review", paths["review"],
                "--candidate", paths["candidate"],
                "--manifest", paths["manifest"],
                "--output", out,
            ])
            self.assertEqual(exit_code, 0)
            self.assertTrue(os.path.exists(out))
            # Re-validate output
            with open(out, encoding="utf-8") as f:
                raw = json.load(f)
            validate_canon_draft_document(raw)

    def test_cli_bad_json_exit_1(self) -> None:
        from pipeline.canon import main
        with tempfile.TemporaryDirectory() as td:
            bad = os.path.join(td, "bad.json")
            with open(bad, "w") as f:
                f.write("not valid json")
            out = os.path.join(td, "draft.json")
            exit_code = main([
                "--promotion-plan", bad,
                "--review", bad,
                "--candidate", bad,
                "--manifest", bad,
                "--output", out,
            ])
            self.assertEqual(exit_code, 1)

    def test_cli_atomic_failure_preserves_existing(self) -> None:
        """If build fails, existing output file content is unchanged."""
        from pipeline.canon import main
        with tempfile.TemporaryDirectory() as td:
            paths = self._write_inputs(td)
            out = os.path.join(td, "draft.json")
            # First run: success
            exit_code = main([
                "--promotion-plan", paths["plan"],
                "--review", paths["review"],
                "--candidate", paths["candidate"],
                "--manifest", paths["manifest"],
                "--output", out,
            ])
            self.assertEqual(exit_code, 0)
            with open(out, encoding="utf-8") as f:
                first_content = f.read()

            # Second run: broken plan (review_id mismatch) should fail
            broken_plan = _valid_plan()
            broken_plan["review_id"] = "wrong"
            broken_plan_path = os.path.join(td, "broken_plan.json")
            with open(broken_plan_path, "w", encoding="utf-8") as f:
                json.dump(broken_plan, f, ensure_ascii=False)

            exit_code = main([
                "--promotion-plan", broken_plan_path,
                "--review", paths["review"],
                "--candidate", paths["candidate"],
                "--manifest", paths["manifest"],
                "--output", out,
            ])
            self.assertEqual(exit_code, 1)

            # Existing file content unchanged
            with open(out, encoding="utf-8") as f:
                second_content = f.read()
            self.assertEqual(first_content, second_content)

    def test_cli_temp_file_cleaned_on_failure(self) -> None:
        from pipeline.canon import main
        with tempfile.TemporaryDirectory() as td:
            paths = self._write_inputs(td)
            broken_plan = os.path.join(td, "broken_plan.json")
            with open(broken_plan, "w", encoding="utf-8") as f:
                json.dump({"bad": True}, f)
            out = os.path.join(td, "draft.json")
            # Check temp dir files before
            before = set(os.listdir(td))
            main([
                "--promotion-plan", broken_plan,
                "--review", paths["review"],
                "--candidate", paths["candidate"],
                "--manifest", paths["manifest"],
                "--output", out,
            ])
            # No temp file should remain
            tmp_files = [f for f in os.listdir(td) if f.startswith(".canon_draft_")]
            self.assertEqual(len(tmp_files), 0)

    def test_cli_missing_arg_exit_2(self) -> None:
        from pipeline.canon import main
        with self.assertRaises(SystemExit) as ctx:
            main(["--promotion-plan", "x.json"])
        self.assertEqual(ctx.exception.code, 2)

    # ── P1-3: output must not overwrite input ────────────────────────────────

    def test_cli_output_equals_promotion_plan_rejected(self) -> None:
        from pipeline.canon import main
        with tempfile.TemporaryDirectory() as td:
            paths = self._write_inputs(td)
            # output = plan file
            ec = main([
                "--promotion-plan", paths["plan"],
                "--review", paths["review"],
                "--candidate", paths["candidate"],
                "--manifest", paths["manifest"],
                "--output", paths["plan"],
            ])
            self.assertEqual(ec, 1)

    def test_cli_output_equals_review_rejected(self) -> None:
        from pipeline.canon import main
        with tempfile.TemporaryDirectory() as td:
            paths = self._write_inputs(td)
            ec = main([
                "--promotion-plan", paths["plan"],
                "--review", paths["review"],
                "--candidate", paths["candidate"],
                "--manifest", paths["manifest"],
                "--output", paths["review"],
            ])
            self.assertEqual(ec, 1)

    def test_cli_output_equals_candidate_rejected(self) -> None:
        from pipeline.canon import main
        with tempfile.TemporaryDirectory() as td:
            paths = self._write_inputs(td)
            ec = main([
                "--promotion-plan", paths["plan"],
                "--review", paths["review"],
                "--candidate", paths["candidate"],
                "--manifest", paths["manifest"],
                "--output", paths["candidate"],
            ])
            self.assertEqual(ec, 1)

    def test_cli_output_equals_manifest_rejected(self) -> None:
        from pipeline.canon import main
        with tempfile.TemporaryDirectory() as td:
            paths = self._write_inputs(td)
            ec = main([
                "--promotion-plan", paths["plan"],
                "--review", paths["review"],
                "--candidate", paths["candidate"],
                "--manifest", paths["manifest"],
                "--output", paths["manifest"],
            ])
            self.assertEqual(ec, 1)

    # ── P1-4: pre-existing unrelated tmp file must not be removed ─────────

    def test_cli_preexisting_tmp_file_not_removed(self) -> None:
        """An unrelated .canon_draft_*.tmp file left by a prior crash must
        survive a failed run."""
        from pipeline.canon import main
        with tempfile.TemporaryDirectory() as td:
            paths = self._write_inputs(td)
            # Create a pre-existing tmp file with distinct content
            preexisting = os.path.join(td, ".canon_draft_preexisting.tmp")
            with open(preexisting, "w", encoding="utf-8") as f:
                f.write("preexisting content")
            # Run with bad plan
            bad = os.path.join(td, "bad.json")
            with open(bad, "w") as f:
                json.dump(1, f)
            out = os.path.join(td, "draft.json")
            main([
                "--promotion-plan", bad,
                "--review", paths["review"],
                "--candidate", paths["candidate"],
                "--manifest", paths["manifest"],
                "--output", out,
            ])
            # Preexisting tmp file unchanged
            self.assertTrue(os.path.exists(preexisting))
            with open(preexisting, encoding="utf-8") as f:
                self.assertEqual(f.read(), "preexisting content")


if __name__ == "__main__":
    unittest.main()
