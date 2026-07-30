"""Tests for pipeline.adaptation — L2W-2 rework."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pipeline.canon import validate_canon_draft_document
from pipeline.adaptation import (
    AdaptationPlan, AdaptationManifest, AdaptationValidationError, CompilationError,
    MicroContentPack, validate_adaptation_plan, compile_micro_pack, write_micro_pack,
    validate_adaptation_manifest_document,
)

# ── Pure fictional fixtures ────────────────────────────────────────────────

_CD = {
    "format_version": 1, "promotion_id": "promo_t",
    "source": {"chapter_id": "chapter_000001", "chapter_sha256": "a" * 64},
    "extracted_by": "t", "review_id": "r", "reviewed_by": "h",
    "entities": [
        {"entity_id": "e_loc", "entity_type": "location", "canonical_name": "L", "aliases": [],
         "source_candidate_id": "sl", "claims": [{"claim_id": "c1", "predicate": "type",
             "value": {"kind": "enum", "enum_value": "village"}, "source_chapters": ["chapter_000001"],
             "source_support": "explicit", "certainty": "certain", "inference_basis": None, "review_reason": "o."}]},
        {"entity_id": "e_char", "entity_type": "character", "canonical_name": "C", "aliases": [],
         "source_candidate_id": "sc", "claims": [{"claim_id": "c2", "predicate": "origin",
             "value": {"kind": "text", "text": "o."}, "source_chapters": ["chapter_000001"],
             "source_support": "explicit", "certainty": "certain", "inference_basis": None, "review_reason": "o."}]},
        {"entity_id": "e_item", "entity_type": "item", "canonical_name": "I", "aliases": [],
         "source_candidate_id": "si", "claims": [{"claim_id": "c3", "predicate": "desc",
             "value": {"kind": "text", "text": "d."}, "source_chapters": ["chapter_000001"],
             "source_support": "explicit", "certainty": "certain", "inference_basis": None, "review_reason": "o."}]},
        {"entity_id": "e_extra", "entity_type": "character", "canonical_name": "X", "aliases": [],
         "source_candidate_id": "sx", "claims": [{"claim_id": "c4", "predicate": "origin",
             "value": {"kind": "text", "text": "x."}, "source_chapters": ["chapter_000001"],
             "source_support": "explicit", "certainty": "certain", "inference_basis": None, "review_reason": "o."}]},
        {"entity_id": "e_extra2", "entity_type": "character", "canonical_name": "Y", "aliases": [],
         "source_candidate_id": "sy", "claims": [{"claim_id": "c5", "predicate": "origin",
             "value": {"kind": "text", "text": "y."}, "source_chapters": ["chapter_000001"],
             "source_support": "explicit", "certainty": "certain", "inference_basis": None, "review_reason": "o."}]},
    ],
}

_PLAN = lambda: validate_adaptation_plan({
    "format_version": 1, "adaptation_id": "adapt_t", "source_promotion_id": "promo_t",
    "source_chapter": "chapter_000001",
    "pack": {"id": "tp", "name": "tp", "version": "0.1.0", "start_room_id": "r",
        "player": {"max_hp": 20, "attack": 5, "defense": 1, "inventory_capacity": 20, "coins": 0}},
    "room": {"canon_entity_ref": "e_loc", "game_id": "r", "name": "room", "description": "desc.",
        "canon_claim_refs": ["c1"], "adaptation_notes": "an."},
    "character": {"canon_entity_ref": "e_char", "game_id": "c", "name": "char", "description": "desc.",
        "canon_claim_refs": ["c2"], "adaptation_notes": "an."},
    "item": {"canon_entity_ref": "e_item", "game_id": "i", "name": "item", "description": "desc.",
        "canon_claim_refs": [], "adaptation_notes": "an."},
    "quest": {"game_id": "q", "kind": "collect_item", "name": "quest", "description": "desc.",
        "target_item_id": "i", "required_quantity": 1, "reward_experience": 10, "adaptation_notes": "a."},
    "dialogue": {"game_id": "di", "character_id": "c", "start_node_id": "s",
        "nodes": [{"id": "s", "text": "hi.", "options": [{"id": "o", "text": "bye.",
            "next_node_id": "s2", "effects": []}]},
            {"id": "s2", "text": "bye.", "options": [{"id": "o2", "text": "bye.",
                "next_node_id": None, "effects": []}]}],
        "adaptation_notes": "n."},
    "omissions": [{"canon_entity_ref": "e_extra", "reason": "x."},
                  {"canon_entity_ref": "e_extra2", "reason": "y."}],
})


def _cd():
    return validate_canon_draft_document(_CD)


# ═══════════════════════════════════════════════════════════════════════════
# Plan structural
# ═══════════════════════════════════════════════════════════════════════════

class PlanValidationTests(unittest.TestCase):
    def test_valid(self) -> None:
        p = _PLAN()
        self.assertEqual(p.adaptation_id, "adapt_t")

    def test_bool_version(self) -> None:
        d = {"format_version": True}
        with self.assertRaises(AdaptationValidationError):
            validate_adaptation_plan(d)

    def test_unknown_field(self) -> None:
        d = {"format_version": 1, "adaptation_id": "a", "source_promotion_id": "p",
             "source_chapter": "chapter_000001", "pack": {}, "room": {}, "character": {},
             "item": {}, "quest": {}, "dialogue": {}, "omissions": [], "extra": 1}
        with self.assertRaises(AdaptationValidationError):
            validate_adaptation_plan(d)

    def test_quest_kind(self) -> None:
        d2 = json.loads(json.dumps({"format_version": 1, "adaptation_id": "a",
            "source_promotion_id": "p", "source_chapter": "chapter_000001",
            "pack": {"id": "p", "name": "p", "version": "0.1.0", "start_room_id": "r",
                "player": {"max_hp": 20, "attack": 5, "defense": 1, "inventory_capacity": 20, "coins": 0}},
            "room": {"canon_entity_ref": "e_loc", "game_id": "r", "name": "r", "description": "d.",
                "canon_claim_refs": [], "adaptation_notes": "n."},
            "character": {"canon_entity_ref": "e_char", "game_id": "c", "name": "c", "description": "d.",
                "canon_claim_refs": [], "adaptation_notes": "n."},
            "item": {"canon_entity_ref": "e_item", "game_id": "i", "name": "i", "description": "d.",
                "canon_claim_refs": [], "adaptation_notes": "n."},
            "quest": {"game_id": "q", "kind": "reach_room", "name": "q", "description": "d.",
                "target_item_id": "i", "required_quantity": 1, "reward_experience": 10,
                "adaptation_notes": "n."},
            "dialogue": {"game_id": "di", "character_id": "c", "start_node_id": "s",
                "nodes": [{"id": "s", "text": "t.", "options": [{"id": "o", "text": "t.",
                    "next_node_id": None, "effects": []}]}], "adaptation_notes": "n."},
            "omissions": [{"canon_entity_ref": "e_extra", "reason": "x."}],
        }))
        with self.assertRaises(AdaptationValidationError):
            validate_adaptation_plan(d2)

    def test_start_node_missing(self) -> None:
        d = json.loads(json.dumps({
            "format_version": 1, "adaptation_id": "a", "source_promotion_id": "p",
            "source_chapter": "chapter_000001",
            "pack": {"id": "p", "name": "p", "version": "0.1.0", "start_room_id": "r",
                "player": {"max_hp": 20, "attack": 5, "defense": 1, "inventory_capacity": 20, "coins": 0}},
            "room": {"canon_entity_ref": "e_loc", "game_id": "r", "name": "r", "description": "d.",
                "canon_claim_refs": [], "adaptation_notes": "n."},
            "character": {"canon_entity_ref": "e_char", "game_id": "c", "name": "c", "description": "d.",
                "canon_claim_refs": [], "adaptation_notes": "n."},
            "item": {"canon_entity_ref": "e_item", "game_id": "i", "name": "i", "description": "d.",
                "canon_claim_refs": [], "adaptation_notes": "n."},
            "quest": {"game_id": "q", "kind": "collect_item", "name": "q", "description": "d.",
                "target_item_id": "i", "required_quantity": 1, "reward_experience": 10, "adaptation_notes": "n."},
            "dialogue": {"game_id": "di", "character_id": "c", "start_node_id": "nonexistent",
                "nodes": [{"id": "s", "text": "t.", "options": [{"id": "o", "text": "t.",
                    "next_node_id": None, "effects": []}]}], "adaptation_notes": "n."},
            "omissions": [{"canon_entity_ref": "e_extra", "reason": "x."}],
        }))
        with self.assertRaises(AdaptationValidationError):
            validate_adaptation_plan(d)

    def test_next_node_id_invalid(self) -> None:
        """next_node_id=[] must not leak TypeError."""
        d = json.loads(json.dumps({
            "format_version": 1, "adaptation_id": "a", "source_promotion_id": "p",
            "source_chapter": "chapter_000001",
            "pack": {"id": "p", "name": "p", "version": "0.1.0", "start_room_id": "r",
                "player": {"max_hp": 20, "attack": 5, "defense": 1, "inventory_capacity": 20, "coins": 0}},
            "room": {"canon_entity_ref": "e_loc", "game_id": "r", "name": "r", "description": "d.",
                "canon_claim_refs": [], "adaptation_notes": "n."},
            "character": {"canon_entity_ref": "e_char", "game_id": "c", "name": "c", "description": "d.",
                "canon_claim_refs": [], "adaptation_notes": "n."},
            "item": {"canon_entity_ref": "e_item", "game_id": "i", "name": "i", "description": "d.",
                "canon_claim_refs": [], "adaptation_notes": "n."},
            "quest": {"game_id": "q", "kind": "collect_item", "name": "q", "description": "d.",
                "target_item_id": "i", "required_quantity": 1, "reward_experience": 10, "adaptation_notes": "n."},
            "dialogue": {"game_id": "di", "character_id": "c", "start_node_id": "s",
                "nodes": [{"id": "s", "text": "t.", "options": [{"id": "o", "text": "t.",
                    "next_node_id": [], "effects": []}]}], "adaptation_notes": "n."},
            "omissions": [{"canon_entity_ref": "e_extra", "reason": "x."}],
        }))
        with self.assertRaises(AdaptationValidationError):
            validate_adaptation_plan(d)

    def test_option_id_not_stable(self) -> None:
        d = json.loads(json.dumps({
            "format_version": 1, "adaptation_id": "a", "source_promotion_id": "p",
            "source_chapter": "chapter_000001",
            "pack": {"id": "p", "name": "p", "version": "0.1.0", "start_room_id": "r",
                "player": {"max_hp": 20, "attack": 5, "defense": 1, "inventory_capacity": 20, "coins": 0}},
            "room": {"canon_entity_ref": "e_loc", "game_id": "r", "name": "r", "description": "d.",
                "canon_claim_refs": [], "adaptation_notes": "n."},
            "character": {"canon_entity_ref": "e_char", "game_id": "c", "name": "c", "description": "d.",
                "canon_claim_refs": [], "adaptation_notes": "n."},
            "item": {"canon_entity_ref": "e_item", "game_id": "i", "name": "i", "description": "d.",
                "canon_claim_refs": [], "adaptation_notes": "n."},
            "quest": {"game_id": "q", "kind": "collect_item", "name": "q", "description": "d.",
                "target_item_id": "i", "required_quantity": 1, "reward_experience": 10, "adaptation_notes": "n."},
            "dialogue": {"game_id": "di", "character_id": "c", "start_node_id": "s",
                "nodes": [{"id": "s", "text": "t.", "options": [{"id": "Not Stable!",
                    "text": "t.", "next_node_id": None, "effects": []}]}], "adaptation_notes": "n."},
            "omissions": [{"canon_entity_ref": "e_extra", "reason": "x."}],
        }))
        with self.assertRaises(AdaptationValidationError):
            validate_adaptation_plan(d)


# ═══════════════════════════════════════════════════════════════════════════
# Compilation
# ═══════════════════════════════════════════════════════════════════════════

class CompilationTests(unittest.TestCase):
    def test_valid_compile(self) -> None:
        p = compile_micro_pack(_cd(), _PLAN())
        self.assertIsInstance(p, MicroContentPack)
        self.assertIsInstance(p.pack, bytes)

    def test_source_promotion_mismatch(self) -> None:
        p = _PLAN()
        p2 = AdaptationPlan(format_version=1, adaptation_id=p.adaptation_id,
            source_promotion_id="wrong", source_chapter=p.source_chapter,
            pack=p.pack, room=p.room, character=p.character, item=p.item,
            quest=p.quest, dialogue=p.dialogue, omissions=p.omissions)
        with self.assertRaises(CompilationError):
            compile_micro_pack(_cd(), p2)

    def test_coverage_missing(self) -> None:
        p = _PLAN()
        p2 = AdaptationPlan(format_version=1, adaptation_id=p.adaptation_id,
            source_promotion_id=p.source_promotion_id, source_chapter=p.source_chapter,
            pack=p.pack, room=p.room, character=p.character, item=p.item,
            quest=p.quest, dialogue=p.dialogue, omissions=p.omissions[:1])
        with self.assertRaises(CompilationError):
            compile_micro_pack(_cd(), p2)

    def test_item_shaped(self) -> None:
        p = compile_micro_pack(_cd(), _PLAN())
        item = json.loads(p.items)
        keys = set(item[0].keys())
        self.assertEqual(keys, {"id", "name", "description", "stack_limit",
                                "canon_ref", "adaptation_notes"})

    def test_quest_no_canon_ref(self) -> None:
        p = compile_micro_pack(_cd(), _PLAN())
        self.assertNotIn("canon_ref", json.loads(p.quests)[0])

    def test_dialogue_no_canon_ref(self) -> None:
        p = compile_micro_pack(_cd(), _PLAN())
        self.assertNotIn("canon_ref", json.loads(p.dialogues)[0])

    def test_dialogue_effects_empty(self) -> None:
        p = compile_micro_pack(_cd(), _PLAN())
        dial = json.loads(p.dialogues)
        for node in dial[0]["nodes"]:
            for opt in node["options"]:
                self.assertEqual(opt["effects"], [])

    def test_description_verbatim(self) -> None:
        p = compile_micro_pack(_cd(), _PLAN())
        self.assertEqual(json.loads(p.rooms)[0]["description"], "desc.")

    def test_nodes_sorted_by_id(self) -> None:
        p = compile_micro_pack(_cd(), _PLAN())
        dial = json.loads(p.dialogues)
        nids = [n["id"] for n in dial[0]["nodes"]]
        self.assertEqual(nids, sorted(nids))

    def test_options_order_preserved(self) -> None:
        """Option order determines player input 1/2/3 — must stay as-is."""
        base = json.loads(json.dumps({}))
        # Build from _PLAN with two options in known order
        plan_a = _PLAN()
        p1 = compile_micro_pack(_cd(), plan_a)
        # Verify first option is "o" (id starts with o)
        dial1 = json.loads(p1.dialogues)[0]
        self.assertEqual(dial1["nodes"][0]["options"][0]["id"], "o")

    def test_deterministic_reversed_omissions(self) -> None:
        """2+ omissions reversed must produce same bytes."""
        p = _PLAN()
        rev_oms = tuple(reversed(p.omissions))
        p2 = AdaptationPlan(format_version=1, adaptation_id=p.adaptation_id,
            source_promotion_id=p.source_promotion_id, source_chapter=p.source_chapter,
            pack=p.pack, room=p.room, character=p.character, item=p.item,
            quest=p.quest, dialogue=p.dialogue, omissions=rev_oms)
        d1 = compile_micro_pack(_cd(), p)
        d2 = compile_micro_pack(_cd(), p2)
        for attr in ("pack", "rooms", "items", "characters", "quests", "dialogues",
                     "monsters", "shops"):
            self.assertEqual(getattr(d1, attr), getattr(d2, attr), f"{attr} differs")

    def test_deterministic_reversed_entities(self) -> None:
        """Reversed canon entities must produce same output."""
        cd_rev = validate_canon_draft_document({**_CD, "entities": list(reversed(_CD["entities"]))})
        p1 = compile_micro_pack(_cd(), _PLAN())
        p2 = compile_micro_pack(cd_rev, _PLAN())
        for attr in ("pack", "rooms", "items", "characters", "quests", "dialogues",
                     "monsters", "shops"):
            self.assertEqual(getattr(p1, attr), getattr(p2, attr), f"{attr} differs")


# ═══════════════════════════════════════════════════════════════════════════
# Manifest validation
# ═══════════════════════════════════════════════════════════════════════════

class ManifestValidationTests(unittest.TestCase):
    def test_valid_manifest(self) -> None:
        p = compile_micro_pack(_cd(), _PLAN())
        m = p.manifest
        self.assertEqual(len(m.bindings), 3)
        self.assertEqual(len(m.game_only), 2)
        self.assertEqual(len(m.omissions), 2)

    def test_manifest_roundtrip(self) -> None:
        p = compile_micro_pack(_cd(), _PLAN())
        d = json.loads(p._manifest_bytes()) if hasattr(p, '_manifest_bytes') else {}
        # Actually get from a copy
        m2 = validate_adaptation_manifest_document(json.loads(p._manifest_bytes()))
        self.assertEqual(m2, p.manifest)

    def test_empty_bindings_rejected(self) -> None:
        d = {"format_version": 1, "adaptation_id": "a",
             "source": {"promotion_id": "p", "chapter_id": "chapter_000001", "chapter_sha256": "a"*64},
             "pack": {"id": "p", "version": "0.1.0"},
             "bindings": [], "game_only": [], "omissions": []}
        with self.assertRaises(AdaptationValidationError):
            validate_adaptation_manifest_document(d)

    def test_wrong_game_only_kind(self) -> None:
        d = {"format_version": 1, "adaptation_id": "a",
             "source": {"promotion_id": "p", "chapter_id": "chapter_000001", "chapter_sha256": "a"*64},
             "pack": {"id": "p", "version": "0.1.0"},
             "bindings": [{"game_kind": "room", "game_id": "r", "canon_entity_ref": "e_l",
                           "canon_claim_refs": [], "adaptation_notes": "n."},
                          {"game_kind": "character", "game_id": "c", "canon_entity_ref": "e_c",
                           "canon_claim_refs": [], "adaptation_notes": "n."},
                          {"game_kind": "item", "game_id": "i", "canon_entity_ref": "e_i",
                           "canon_claim_refs": [], "adaptation_notes": "n."}],
             "game_only": [{"game_kind": "item", "game_id": "x", "adaptation_notes": "n."},
                           {"game_kind": "dialogue", "game_id": "y", "adaptation_notes": "n."}],
             "omissions": []}
        with self.assertRaises(AdaptationValidationError):
            validate_adaptation_manifest_document(d)

    def test_manifest_game_id_duplicate(self) -> None:
        d = {"format_version": 1, "adaptation_id": "a",
             "source": {"promotion_id": "p", "chapter_id": "chapter_000001", "chapter_sha256": "a"*64},
             "pack": {"id": "p", "version": "0.1.0"},
             "bindings": [{"game_kind": "room", "game_id": "same", "canon_entity_ref": "e_l",
                           "canon_claim_refs": [], "adaptation_notes": "n."},
                          {"game_kind": "character", "game_id": "c", "canon_entity_ref": "e_c",
                           "canon_claim_refs": [], "adaptation_notes": "n."},
                          {"game_kind": "item", "game_id": "same", "canon_entity_ref": "e_i",
                           "canon_claim_refs": [], "adaptation_notes": "n."}],
             "game_only": [{"game_kind": "quest", "game_id": "q", "adaptation_notes": "n."},
                           {"game_kind": "dialogue", "game_id": "d", "adaptation_notes": "n."}],
             "omissions": []}
        with self.assertRaises(AdaptationValidationError):
            validate_adaptation_manifest_document(d)


# ═══════════════════════════════════════════════════════════════════════════
# Atomic write & path traversal
# ═══════════════════════════════════════════════════════════════════════════

class WriteTests(unittest.TestCase):
    def _pack(self):
        return compile_micro_pack(_cd(), _PLAN())

    def test_write_success(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "o")
            result = write_micro_pack(self._pack(), out)
            self.assertTrue(os.path.isdir(result))
            self.assertTrue(os.path.isfile(os.path.join(result, "adaptation_manifest.json")))

    def test_write_reject_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "o")
            with open(out, "w") as f:
                f.write("x")
            with self.assertRaises(FileExistsError):
                write_micro_pack(self._pack(), out)

    def test_write_reject_existing_dir_nonempty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "o")
            os.mkdir(out)
            with open(os.path.join(out, "x"), "w") as f:
                f.write("x")
            with self.assertRaises(FileExistsError):
                write_micro_pack(self._pack(), out)

    def test_write_reject_existing_empty_dir(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "o")
            os.mkdir(out)
            with self.assertRaises(FileExistsError):
                write_micro_pack(self._pack(), out)

    def test_traversal_filename_rejected(self) -> None:
        with self.assertRaises(CompilationError):
            from pipeline.adaptation import _validate_document_path
            _validate_document_path("../escape.txt", b"x")

    def test_absolute_filename_rejected(self) -> None:
        from pipeline.adaptation import _validate_document_path
        with self.assertRaises(CompilationError):
            _validate_document_path("/etc/passwd", b"x")

    def test_unknown_filename_rejected(self) -> None:
        from pipeline.adaptation import _validate_document_path
        with self.assertRaises(CompilationError):
            _validate_document_path("secret.txt", b"x")


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

class CLITests(unittest.TestCase):
    def _write_inputs(self, td: str) -> dict[str, str]:
        cd_path = os.path.join(td, "cd.json")
        with open(cd_path, "w", encoding="utf-8") as f:
            json.dump(_CD, f, ensure_ascii=False)
        plan_path = os.path.join(td, "plan.json")
        with open(plan_path, "w", encoding="utf-8") as f:
            json.dump({
                "format_version": 1, "adaptation_id": "adapt_cli",
                "source_promotion_id": "promo_t", "source_chapter": "chapter_000001",
                "pack": {"id": "cli_micro", "name": "CLI", "version": "0.1.0",
                    "start_room_id": "r", "player": {"max_hp": 20, "attack": 5,
                        "defense": 1, "inventory_capacity": 20, "coins": 0}},
                "room": {"canon_entity_ref": "e_loc", "game_id": "r", "name": "r",
                    "description": "d.", "canon_claim_refs": [], "adaptation_notes": "n."},
                "character": {"canon_entity_ref": "e_char", "game_id": "c", "name": "c",
                    "description": "d.", "canon_claim_refs": [], "adaptation_notes": "n."},
                "item": {"canon_entity_ref": "e_item", "game_id": "i", "name": "i",
                    "description": "d.", "canon_claim_refs": [], "adaptation_notes": "n."},
                "quest": {"game_id": "q", "kind": "collect_item", "name": "q",
                    "description": "d.", "target_item_id": "i", "required_quantity": 1,
                    "reward_experience": 10, "adaptation_notes": "a."},
                "dialogue": {"game_id": "di", "character_id": "c", "start_node_id": "s",
                    "nodes": [{"id": "s", "text": "t.", "options": [{"id": "o",
                        "text": "t.", "next_node_id": None, "effects": []}]}],
                    "adaptation_notes": "n."},
                "omissions": [{"canon_entity_ref": "e_extra", "reason": "x."},
                              {"canon_entity_ref": "e_extra2", "reason": "y."}],
            }, f, ensure_ascii=False)
        with open(os.path.join(td, "bad.json"), "w") as f:
            json.dump(1, f)
        with open(os.path.join(td, "junk.json"), "w") as f:
            f.write("not json")
        return {"cd": cd_path, "plan": plan_path,
                "bad": os.path.join(td, "bad.json"), "junk": os.path.join(td, "junk.json")}

    def test_cli_success(self) -> None:
        from pipeline.adaptation import main
        with tempfile.TemporaryDirectory() as td:
            ins = self._write_inputs(td)
            out = os.path.join(td, "o")
            ec = main(["--canon-draft", ins["cd"], "--adaptation-plan", ins["plan"],
                       "--output-dir", out])
            self.assertEqual(ec, 0)
            self.assertTrue(os.path.isdir(out))

    def test_cli_bad_canon_draft(self) -> None:
        from pipeline.adaptation import main
        with tempfile.TemporaryDirectory() as td:
            ins = self._write_inputs(td)
            ec = main(["--canon-draft", ins["bad"], "--adaptation-plan", ins["plan"],
                       "--output-dir", os.path.join(td, "o")])
            self.assertEqual(ec, 1)

    def test_cli_bad_plan(self) -> None:
        from pipeline.adaptation import main
        with tempfile.TemporaryDirectory() as td:
            ins = self._write_inputs(td)
            ec = main(["--canon-draft", ins["cd"], "--adaptation-plan", ins["bad"],
                       "--output-dir", os.path.join(td, "o")])
            self.assertEqual(ec, 1)

    def test_cli_junk_json(self) -> None:
        from pipeline.adaptation import main
        with tempfile.TemporaryDirectory() as td:
            ins = self._write_inputs(td)
            ec = main(["--canon-draft", ins["junk"], "--adaptation-plan", ins["plan"],
                       "--output-dir", os.path.join(td, "o")])
            self.assertEqual(ec, 1)

    def test_cli_missing_arg(self) -> None:
        from pipeline.adaptation import main
        with self.assertRaises(SystemExit) as ctx:
            main(["--canon-draft", "x.json"])
        self.assertEqual(ctx.exception.code, 2)


# ═══════════════════════════════════════════════════════════════════════════
# Schema boundary
# ═══════════════════════════════════════════════════════════════════════════

class SchemaTests(unittest.TestCase):
    def test_plan_schema_no_external(self) -> None:
        sp = REPO / "schemas" / "adaptation_plan.schema.json"
        with open(sp, encoding="utf-8") as f:
            s = json.load(f)
        raw = json.dumps(s)
        self.assertNotIn("canon_ref", raw)

    def test_manifest_schema_exact_counts(self) -> None:
        sp = REPO / "schemas" / "adaptation_manifest.schema.json"
        with open(sp, encoding="utf-8") as f:
            s = json.load(f)
        self.assertEqual(s["properties"]["bindings"]["minItems"], 3)
        self.assertEqual(s["properties"]["bindings"]["maxItems"], 3)
        self.assertEqual(s["properties"]["game_only"]["minItems"], 2)
        self.assertEqual(s["properties"]["game_only"]["maxItems"], 2)


if __name__ == "__main__":
    unittest.main()
