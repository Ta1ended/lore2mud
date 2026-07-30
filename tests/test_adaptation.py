"""Tests for pipeline.adaptation — L2W-2 micro content pack compilation."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pipeline.canon import validate_canon_draft_document, build_canon_draft
from pipeline.chapter_manifests import validate_chapter_manifest
from pipeline.fact_candidates import validate_fact_candidate_document
from pipeline.fact_reviews import validate_fact_review_document
from pipeline.adaptation import (
    AdaptationPlan, AdaptationManifest, AdaptationValidationError, CompilationError,
    MicroContentPack, CompiledDocument,
    validate_adaptation_plan, compile_micro_pack, write_micro_pack,
    validate_adaptation_manifest_document,
)

# ── Helpers ────────────────────────────────────────────────────────────────

_VALID_PLAN = {
    "format_version": 1,
    "adaptation_id": "adapt_test",
    "source_promotion_id": "promo_test",
    "source_chapter": "chapter_000001",
    "pack": {
        "id": "test_micro", "name": "测试微场景", "version": "0.1.0",
        "start_room_id": "room_test",
        "player": {"max_hp": 20, "attack": 5, "defense": 1, "inventory_capacity": 20, "coins": 0},
    },
    "room": {
        "canon_entity_ref": "e_loc", "game_id": "room_test",
        "name": "测试房间", "description": "一个测试房间。",
        "canon_claim_refs": ["c_type"], "adaptation_notes": "唯一房间。",
    },
    "character": {
        "canon_entity_ref": "e_char", "game_id": "char_test",
        "name": "测试角色", "description": "一个测试角色。",
        "canon_claim_refs": ["c_origin"], "adaptation_notes": "叙事 NPC。",
    },
    "item": {
        "canon_entity_ref": "e_item", "game_id": "item_test",
        "name": "测试物品", "description": "一个测试物品。",
        "canon_claim_refs": [], "adaptation_notes": "收集物。",
    },
    "quest": {
        "game_id": "quest_test", "kind": "collect_item",
        "name": "测试任务", "description": "收集物品。",
        "target_item_id": "item_test", "required_quantity": 1, "reward_experience": 10,
        "adaptation_notes": "自动接取。",
    },
    "dialogue": {
        "game_id": "dial_test", "character_id": "char_test",
        "start_node_id": "start",
        "nodes": [{
            "id": "start", "text": "你好。",
            "options": [{"id": "opt_leave", "text": "再会。", "next_node_id": None, "effects": []}],
        }],
        "adaptation_notes": "纯叙事。",
    },
    "omissions": [{"canon_entity_ref": "e_extra", "reason": "不在范围。"}],
}

_CANON_DRAFT_JSON = {
    "format_version": 1,
    "promotion_id": "promo_test",
    "source": {"chapter_id": "chapter_000001", "chapter_sha256": "a" * 64},
    "extracted_by": "tester",
    "review_id": "review_test",
    "reviewed_by": "human",
    "entities": [
        {
            "entity_id": "e_loc", "entity_type": "location",
            "canonical_name": "地点", "aliases": [],
            "source_candidate_id": "s_loc",
            "claims": [{"claim_id": "c_type", "predicate": "type",
                "value": {"kind": "enum", "enum_value": "village"},
                "source_chapters": ["chapter_000001"], "source_support": "explicit",
                "certainty": "certain", "inference_basis": None, "review_reason": "ok."}],
        },
        {
            "entity_id": "e_char", "entity_type": "character",
            "canonical_name": "角色", "aliases": [],
            "source_candidate_id": "s_char",
            "claims": [{"claim_id": "c_origin", "predicate": "origin",
                "value": {"kind": "text", "text": "出身于此。"},
                "source_chapters": ["chapter_000001"], "source_support": "explicit",
                "certainty": "certain", "inference_basis": None, "review_reason": "ok."}],
        },
        {
            "entity_id": "e_item", "entity_type": "item",
            "canonical_name": "物品", "aliases": [],
            "source_candidate_id": "s_item",
            "claims": [{"claim_id": "c_desc", "predicate": "description",
                "value": {"kind": "text", "text": "物品。"},
                "source_chapters": ["chapter_000001"], "source_support": "explicit",
                "certainty": "certain", "inference_basis": None, "review_reason": "ok."}],
        },
        {
            "entity_id": "e_extra", "entity_type": "character",
            "canonical_name": "额外", "aliases": [],
            "source_candidate_id": "s_extra",
            "claims": [{"claim_id": "c_extra", "predicate": "origin",
                "value": {"kind": "text", "text": "额外。"},
                "source_chapters": ["chapter_000001"], "source_support": "explicit",
                "certainty": "certain", "inference_basis": None, "review_reason": "ok."}],
        },
    ],
}


def _canon_draft():
    return validate_canon_draft_document(_CANON_DRAFT_JSON)


def _plan():
    return validate_adaptation_plan(_VALID_PLAN)


# ── Plan structural validation ─────────────────────────────────────────────

class PlanStructuralValidationTests(unittest.TestCase):
    def test_valid_plan(self) -> None:
        plan = _plan()
        self.assertEqual(plan.adaptation_id, "adapt_test")
        self.assertEqual(plan.room.game_id, "room_test")

    def test_format_version_mismatch(self) -> None:
        d = dict(_VALID_PLAN)
        d["format_version"] = 2
        with self.assertRaises(AdaptationValidationError):
            validate_adaptation_plan(d)

    def test_bool_version_rejected(self) -> None:
        d = dict(_VALID_PLAN)
        d["format_version"] = True
        with self.assertRaises(AdaptationValidationError):
            validate_adaptation_plan(d)

    def test_unknown_field_rejected(self) -> None:
        d = dict(_VALID_PLAN)
        d["extra"] = 1
        with self.assertRaises(AdaptationValidationError):
            validate_adaptation_plan(d)

    def test_quest_kind_wrong(self) -> None:
        d = dict(_VALID_PLAN)
        d["quest"] = dict(d["quest"])
        d["quest"]["kind"] = "reach_room"
        with self.assertRaises(AdaptationValidationError):
            validate_adaptation_plan(d)

    def test_nodes_have_effects_empty(self) -> None:
        d = dict(_VALID_PLAN)
        d["dialogue"] = dict(d["dialogue"])
        d["dialogue"]["nodes"] = [dict(d["dialogue"]["nodes"][0])]
        d["dialogue"]["nodes"][0]["options"] = [dict(d["dialogue"]["nodes"][0]["options"][0])]
        d["dialogue"]["nodes"][0]["options"][0]["effects"] = [{"something": 1}]
        with self.assertRaises(AdaptationValidationError):
            validate_adaptation_plan(d)

    def test_start_node_id_missing(self) -> None:
        d = dict(_VALID_PLAN)
        d["dialogue"] = dict(d["dialogue"])
        d["dialogue"]["start_node_id"] = "nonexistent"
        with self.assertRaises(AdaptationValidationError):
            validate_adaptation_plan(d)

    def test_node_id_duplicate(self) -> None:
        d = dict(_VALID_PLAN)
        d["dialogue"] = dict(d["dialogue"])
        n = d["dialogue"]["nodes"][0]
        d["dialogue"]["nodes"] = [dict(n), dict(n)]
        with self.assertRaises(AdaptationValidationError):
            validate_adaptation_plan(d)

    def test_option_id_duplicate(self) -> None:
        d = dict(_VALID_PLAN)
        d["dialogue"] = dict(d["dialogue"])
        n = d["dialogue"]["nodes"][0]
        n2 = {"id": "start", "text": "其他",
              "options": [{"id": "same", "text": "A", "next_node_id": None, "effects": []},
                          {"id": "same", "text": "B", "next_node_id": None, "effects": []}]}
        d["dialogue"]["nodes"] = [n2]
        with self.assertRaises(AdaptationValidationError):
            validate_adaptation_plan(d)

    def test_omission_entity_ref_duplicate(self) -> None:
        d = dict(_VALID_PLAN)
        d["omissions"] = [dict(d["omissions"][0]), dict(d["omissions"][0])]
        with self.assertRaises(AdaptationValidationError):
            validate_adaptation_plan(d)

    def test_canon_claim_refs_dedup(self) -> None:
        d = dict(_VALID_PLAN)
        d["room"] = dict(d["room"])
        d["room"]["canon_claim_refs"] = ["c_type", "c_type"]
        with self.assertRaises(AdaptationValidationError):
            validate_adaptation_plan(d)


# ── Compilation errors ─────────────────────────────────────────────────────

class CompilationValidationTests(unittest.TestCase):
    def test_valid_compile(self) -> None:
        pack = compile_micro_pack(_canon_draft(), _plan())
        self.assertIsInstance(pack, MicroContentPack)
        self.assertEqual(len(pack.documents), 9)

    def test_source_promotion_mismatch(self) -> None:
        plan = _plan()
        plan2 = AdaptationPlan(
            format_version=1, adaptation_id=plan.adaptation_id,
            source_promotion_id="wrong", source_chapter=plan.source_chapter,
            pack=plan.pack, room=plan.room, character=plan.character,
            item=plan.item, quest=plan.quest, dialogue=plan.dialogue,
            omissions=plan.omissions,
        )
        with self.assertRaises(CompilationError):
            compile_micro_pack(_canon_draft(), plan2)

    def test_source_chapter_mismatch(self) -> None:
        plan = _plan()
        plan2 = AdaptationPlan(
            format_version=1, adaptation_id=plan.adaptation_id,
            source_promotion_id=plan.source_promotion_id,
            source_chapter="chapter_000002",
            pack=plan.pack, room=plan.room, character=plan.character,
            item=plan.item, quest=plan.quest, dialogue=plan.dialogue,
            omissions=plan.omissions,
        )
        with self.assertRaises(CompilationError):
            compile_micro_pack(_canon_draft(), plan2)

    def test_entity_ref_nonexistent(self) -> None:
        plan = _plan()
        room2 = type(plan.room)(canon_entity_ref="nonexistent", game_id=plan.room.game_id,
            name=plan.room.name, description=plan.room.description,
            canon_claim_refs=plan.room.canon_claim_refs,
            adaptation_notes=plan.room.adaptation_notes)
        with self.assertRaises(CompilationError):
            compile_micro_pack(_canon_draft(), type(plan)(
                format_version=1, adaptation_id=plan.adaptation_id,
                source_promotion_id=plan.source_promotion_id,
                source_chapter=plan.source_chapter,
                pack=plan.pack, room=room2, character=plan.character,
                item=plan.item, quest=plan.quest, dialogue=plan.dialogue,
                omissions=plan.omissions,
            ))

    def test_entity_type_mismatch(self) -> None:
        plan = _plan()
        room2 = type(plan.room)(canon_entity_ref="e_char", game_id=plan.room.game_id,
            name=plan.room.name, description=plan.room.description,
            canon_claim_refs=plan.room.canon_claim_refs,
            adaptation_notes=plan.room.adaptation_notes)
        with self.assertRaises(CompilationError):
            compile_micro_pack(_canon_draft(), type(plan)(
                format_version=1, adaptation_id=plan.adaptation_id,
                source_promotion_id=plan.source_promotion_id,
                source_chapter=plan.source_chapter,
                pack=plan.pack, room=room2, character=plan.character,
                item=plan.item, quest=plan.quest, dialogue=plan.dialogue,
                omissions=plan.omissions,
            ))

    def test_claim_ref_wrong_entity(self) -> None:
        plan = _plan()
        room2 = type(plan.room)(canon_entity_ref="e_loc", game_id=plan.room.game_id,
            name=plan.room.name, description=plan.room.description,
            canon_claim_refs=("c_origin",),  # belongs to e_char, not e_loc
            adaptation_notes=plan.room.adaptation_notes)
        with self.assertRaises(CompilationError):
            compile_micro_pack(_canon_draft(), type(plan)(
                format_version=1, adaptation_id=plan.adaptation_id,
                source_promotion_id=plan.source_promotion_id,
                source_chapter=plan.source_chapter,
                pack=plan.pack, room=room2, character=plan.character,
                item=plan.item, quest=plan.quest, dialogue=plan.dialogue,
                omissions=plan.omissions,
            ))

    def test_coverage_missing_entity(self) -> None:
        plan = _plan()
        plan2 = type(plan)(
            format_version=1, adaptation_id=plan.adaptation_id,
            source_promotion_id=plan.source_promotion_id,
            source_chapter=plan.source_chapter,
            pack=plan.pack, room=plan.room, character=plan.character,
            item=plan.item, quest=plan.quest, dialogue=plan.dialogue,
            omissions=tuple(o for o in plan.omissions if o.canon_entity_ref != "e_extra"),
        )
        with self.assertRaises(CompilationError):
            compile_micro_pack(_canon_draft(), plan2)

    def test_selected_in_omissions(self) -> None:
        plan = _plan()
        plan2 = type(plan)(
            format_version=1, adaptation_id=plan.adaptation_id,
            source_promotion_id=plan.source_promotion_id,
            source_chapter=plan.source_chapter,
            pack=plan.pack, room=plan.room, character=plan.character,
            item=plan.item, quest=plan.quest, dialogue=plan.dialogue,
            omissions=(type(plan.omissions[0])(
                canon_entity_ref="e_loc", reason="测试"),),
        )
        with self.assertRaises(CompilationError):
            compile_micro_pack(_canon_draft(), plan2)

    def test_game_id_duplicate(self) -> None:
        plan = _plan()
        room2 = type(plan.room)(canon_entity_ref="e_loc", game_id="char_test",
            name=plan.room.name, description=plan.room.description,
            canon_claim_refs=plan.room.canon_claim_refs,
            adaptation_notes=plan.room.adaptation_notes)
        with self.assertRaises(CompilationError):
            compile_micro_pack(_canon_draft(), type(plan)(
                format_version=1, adaptation_id=plan.adaptation_id,
                source_promotion_id=plan.source_promotion_id,
                source_chapter=plan.source_chapter,
                pack=plan.pack, room=room2, character=plan.character,
                item=plan.item, quest=plan.quest, dialogue=plan.dialogue,
                omissions=plan.omissions,
            ))

    def test_start_room_mismatch(self) -> None:
        plan = _plan()
        pack2 = type(plan.pack)(id=plan.pack.id, name=plan.pack.name,
            version=plan.pack.version, start_room_id="wrong",
            player=plan.pack.player)
        with self.assertRaises(CompilationError):
            compile_micro_pack(_canon_draft(), type(plan)(
                format_version=1, adaptation_id=plan.adaptation_id,
                source_promotion_id=plan.source_promotion_id,
                source_chapter=plan.source_chapter,
                pack=pack2, room=plan.room, character=plan.character,
                item=plan.item, quest=plan.quest, dialogue=plan.dialogue,
                omissions=plan.omissions,
            ))


# ── Output shape ───────────────────────────────────────────────────────────

class OutputShapeTests(unittest.TestCase):
    def setUp(self):
        self.pack = compile_micro_pack(_canon_draft(), _plan())

    def test_nine_documents(self) -> None:
        fns = sorted(d.filename for d in self.pack.documents)
        self.assertEqual(fns, [
            "adaptation_manifest.json", "characters.json", "dialogues.json",
            "items.json", "monsters.json", "pack.json", "quests.json",
            "rooms.json", "shops.json",
        ])

    def test_item_has_no_heal_slot_bonus(self) -> None:
        doc = [d for d in self.pack.documents if d.filename == "items.json"][0]
        items = json.loads(doc.payload)
        keys = set(items[0].keys())
        self.assertEqual(keys, {"id", "name", "description", "stack_limit", "canon_ref", "adaptation_notes"})

    def test_quest_no_canon_ref(self) -> None:
        doc = [d for d in self.pack.documents if d.filename == "quests.json"][0]
        quests = json.loads(doc.payload)
        self.assertNotIn("canon_ref", quests[0])

    def test_dialogue_no_canon_ref(self) -> None:
        doc = [d for d in self.pack.documents if d.filename == "dialogues.json"][0]
        dials = json.loads(doc.payload)
        self.assertNotIn("canon_ref", dials[0])

    def test_dialogue_nodes_array(self) -> None:
        doc = [d for d in self.pack.documents if d.filename == "dialogues.json"][0]
        dials = json.loads(doc.payload)
        self.assertIsInstance(dials[0]["nodes"], list)

    def test_dialogue_options_have_effects(self) -> None:
        doc = [d for d in self.pack.documents if d.filename == "dialogues.json"][0]
        dials = json.loads(doc.payload)
        for node in dials[0]["nodes"]:
            for opt in node["options"]:
                self.assertIn("effects", opt)
                self.assertEqual(opt["effects"], [])

    def test_description_verbatim(self) -> None:
        doc = [d for d in self.pack.documents if d.filename == "rooms.json"][0]
        rooms = json.loads(doc.payload)
        self.assertEqual(rooms[0]["description"], "一个测试房间。")

    def test_load_content_pack(self) -> None:
        from lore2mud.content.loader import load_content_pack
        with tempfile.TemporaryDirectory() as td:
            for doc in self.pack.documents:
                with open(os.path.join(td, doc.filename), "wb") as f:
                    f.write(doc.payload)
            cp = load_content_pack(td)
            self.assertEqual(cp.id, "test_micro")
            self.assertEqual(len(cp.rooms), 1)
            self.assertEqual(len(cp.quests), 1)
            self.assertEqual(cp.quests["quest_test"].kind, "collect_item")
            self.assertEqual(len(cp.dialogues), 1)
            self.assertEqual(len(cp.characters), 1)
            self.assertEqual(len(cp.items), 1)


# ── Manifest ───────────────────────────────────────────────────────────────

class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.pack = compile_micro_pack(_canon_draft(), _plan())

    def test_manifest_has_three_bindings(self) -> None:
        m = self.pack.manifest
        self.assertEqual(len(m.bindings), 3)
        kinds = {b.game_kind for b in m.bindings}
        self.assertEqual(kinds, {"room", "character", "item"})

    def test_manifest_has_two_game_only(self) -> None:
        m = self.pack.manifest
        self.assertEqual(len(m.game_only), 2)
        kinds = {g.game_kind for g in m.game_only}
        self.assertEqual(kinds, {"quest", "dialogue"})

    def test_manifest_full_omissions(self) -> None:
        m = self.pack.manifest
        self.assertEqual(len(m.omissions), 1)
        self.assertEqual(m.omissions[0].canon_entity_ref, "e_extra")

    def test_manifest_revalidate(self) -> None:
        doc = [d for d in self.pack.documents if d.filename == "adaptation_manifest.json"][0]
        raw = json.loads(doc.payload)
        revalidated = validate_adaptation_manifest_document(raw)
        self.assertEqual(revalidated, self.pack.manifest)

    def test_manifest_source_fields(self) -> None:
        m = self.pack.manifest
        self.assertEqual(m.source.promotion_id, "promo_test")
        self.assertEqual(m.source.chapter_id, "chapter_000001")
        self.assertEqual(m.source.chapter_sha256, "a" * 64)


# ── Frozen ─────────────────────────────────────────────────────────────────

class FrozenTests(unittest.TestCase):
    def test_plan_frozen(self) -> None:
        plan = _plan()
        with self.assertRaises(AttributeError):
            plan.adaptation_id = "changed"  # type: ignore

    def test_payload_bytes_immutable(self) -> None:
        pack = compile_micro_pack(_canon_draft(), _plan())
        doc = pack.documents[0]
        with self.assertRaises(AttributeError):
            doc.filename = "changed"  # type: ignore


# ── Determinism ────────────────────────────────────────────────────────────

class DeterminismTests(unittest.TestCase):
    def test_reversed_entities_same(self) -> None:
        rev = dict(_CANON_DRAFT_JSON)
        rev["entities"] = list(reversed(rev["entities"]))
        cd_rev = validate_canon_draft_document(rev)
        cd = validate_canon_draft_document(_CANON_DRAFT_JSON)
        p1 = compile_micro_pack(cd, _plan())
        p2 = compile_micro_pack(cd_rev, _plan())
        for d1, d2 in zip(
            sorted(p1.documents, key=lambda x: x.filename),
            sorted(p2.documents, key=lambda x: x.filename),
        ):
            self.assertEqual(d1.payload, d2.payload, f"差异: {d1.filename}")

    def test_reversed_omissions_same(self) -> None:
        plan = _plan()
        oms = list(plan.omissions)
        oms2 = list(reversed(oms))
        plan2 = type(plan)(
            format_version=1, adaptation_id=plan.adaptation_id,
            source_promotion_id=plan.source_promotion_id,
            source_chapter=plan.source_chapter,
            pack=plan.pack, room=plan.room, character=plan.character,
            item=plan.item, quest=plan.quest, dialogue=plan.dialogue,
            omissions=tuple(oms2),
        )
        p1 = compile_micro_pack(_canon_draft(), plan)
        p2 = compile_micro_pack(_canon_draft(), plan2)
        for d1, d2 in zip(
            sorted(p1.documents, key=lambda x: x.filename),
            sorted(p2.documents, key=lambda x: x.filename),
        ):
            self.assertEqual(d1.payload, d2.payload, f"差异: {d1.filename}")

    def test_option_order_preserved(self) -> None:
        """Option order must be preserved (players choose 1/2/3)."""
        # Create plan with two options
        base = dict(_VALID_PLAN)
        base["dialogue"] = dict(base["dialogue"])
        base["dialogue"]["nodes"] = [{
            "id": "start", "text": "选择？",
            "options": [
                {"id": "opt_a", "text": "选项A", "next_node_id": None, "effects": []},
                {"id": "opt_b", "text": "选项B", "next_node_id": None, "effects": []},
            ],
        }]
        plan_a = validate_adaptation_plan(base)
        p1 = compile_micro_pack(_canon_draft(), plan_a)
        # Reverse options
        base["dialogue"]["nodes"][0]["options"].reverse()
        plan_b = validate_adaptation_plan(base)
        p2 = compile_micro_pack(_canon_draft(), plan_b)
        d1 = [d for d in p1.documents if d.filename == "dialogues.json"][0]
        d2 = [d for d in p2.documents if d.filename == "dialogues.json"][0]
        self.assertNotEqual(d1.payload, d2.payload)
        # Verify order in output
        arr_a = json.loads(d1.payload)
        arr_b = json.loads(d2.payload)
        self.assertEqual(arr_a[0]["nodes"][0]["options"][0]["id"], "opt_a")
        self.assertEqual(arr_b[0]["nodes"][0]["options"][0]["id"], "opt_b")


# ── write_micro_pack ─────────────────────────────────────────────────────

class WriteTests(unittest.TestCase):
    def test_write_success(self) -> None:
        pack = compile_micro_pack(_canon_draft(), _plan())
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "output_micro")
            result = write_micro_pack(pack, out)
            self.assertTrue(os.path.isdir(result))
            self.assertTrue(os.path.isfile(os.path.join(result, "pack.json")))
            self.assertTrue(os.path.isfile(os.path.join(result, "adaptation_manifest.json")))

    def test_write_output_exists_rejected(self) -> None:
        pack = compile_micro_pack(_canon_draft(), _plan())
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "existing")
            os.mkdir(out)
            with open(os.path.join(out, "dummy.txt"), "w") as f:
                f.write("x")
            with self.assertRaises(FileExistsError):
                write_micro_pack(pack, out)

    def test_write_failure_cleans_temp(self) -> None:
        """Broken manifest (mismatch after re-read) must clean up temp."""
        pack = compile_micro_pack(_canon_draft(), _plan())
        from pipeline.adaptation import ManifestSource, ManifestPack, ManifestBinding, ManifestGameOnly, ManifestOmission
        bad_manifest = type(pack.manifest)(
            format_version=1, adaptation_id=pack.manifest.adaptation_id,
            source=ManifestSource(
                promotion_id="WRONG_MISMATCH",
                chapter_id=pack.manifest.source.chapter_id,
                chapter_sha256=pack.manifest.source.chapter_sha256,
            ),
            pack=pack.manifest.pack,
            bindings=pack.manifest.bindings,
            omissions=pack.manifest.omissions,
            game_only=pack.manifest.game_only,
        )
        bad_pack = MicroContentPack(documents=pack.documents, manifest=bad_manifest)
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "output")
            with self.assertRaises(Exception):
                write_micro_pack(bad_pack, out)
            self.assertFalse(os.path.exists(out))
            leftovers = [f for f in os.listdir(td) if f.startswith(".l2w_adaptation_")]
            self.assertEqual(len(leftovers), 0)

    def test_preexisting_same_prefix_not_deleted(self) -> None:
        pack = compile_micro_pack(_canon_draft(), _plan())
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "output")
            # Create a pre-existing temp-like dir
            preexisting = os.path.join(td, ".l2w_adaptation_preexisting")
            os.mkdir(preexisting)
            with open(os.path.join(preexisting, "dummy.txt"), "w") as f:
                f.write("keep")
            write_micro_pack(pack, out)
            # Preexisting dir must survive
            self.assertTrue(os.path.isdir(preexisting))
            self.assertTrue(os.path.isfile(os.path.join(preexisting, "dummy.txt")))


# ── Schema structure ───────────────────────────────────────────────────────

class SchemaTests(unittest.TestCase):
    def test_plan_schema_no_external_coverage(self) -> None:
        """Schema must NOT claim to validate external CanonDraft references."""
        schema_path = REPO / "schemas" / "adaptation_plan.schema.json"
        with open(schema_path, encoding="utf-8") as f:
            schema = json.load(f)
        raw = json.dumps(schema)
        # Schema should not reference CanonDraft
        self.assertNotIn("canon_ref", raw)
        self.assertNotIn("source_chapter", schema.get("if", {}))


if __name__ == "__main__":
    unittest.main()
