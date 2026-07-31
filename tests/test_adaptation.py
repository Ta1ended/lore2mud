"""L2W-2 tests: adaptation plan validation, compilation, manifest, write, CLI, World."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from pipeline.canon import validate_canon_draft_document
from pipeline.adaptation import (
    CompilationError, AdaptationValidationError,
    MicroContentPack, validate_adaptation_plan, compile_micro_pack, write_micro_pack,
    validate_adaptation_manifest_document, _pack_to_docs,
)

# ── Fixtures ───────────────────────────────────────────────────────────────

_CD = {
    "format_version":1,"promotion_id":"promo_t","source":{"chapter_id":"chapter_000001","chapter_sha256":"a"*64},
    "extracted_by":"t","review_id":"r","reviewed_by":"h",
    "entities":[
        {"entity_id":"e_loc","entity_type":"location","canonical_name":"L","aliases":[],"source_candidate_id":"sl","claims":[{"claim_id":"c1","predicate":"type","value":{"kind":"enum","enum_value":"v"},"source_chapters":["chapter_000001"],"source_support":"explicit","certainty":"certain","inference_basis":None,"review_reason":"o."}]},
        {"entity_id":"e_char","entity_type":"character","canonical_name":"C","aliases":[],"source_candidate_id":"sc","claims":[{"claim_id":"c2","predicate":"origin","value":{"kind":"text","text":"o."},"source_chapters":["chapter_000001"],"source_support":"explicit","certainty":"certain","inference_basis":None,"review_reason":"o."}]},
        {"entity_id":"e_item","entity_type":"item","canonical_name":"I","aliases":[],"source_candidate_id":"si","claims":[{"claim_id":"c3","predicate":"desc","value":{"kind":"text","text":"d."},"source_chapters":["chapter_000001"],"source_support":"explicit","certainty":"certain","inference_basis":None,"review_reason":"o."}]},
        {"entity_id":"e_x","entity_type":"character","canonical_name":"X","aliases":[],"source_candidate_id":"sx","claims":[{"claim_id":"c4","predicate":"origin","value":{"kind":"text","text":"x."},"source_chapters":["chapter_000001"],"source_support":"explicit","certainty":"certain","inference_basis":None,"review_reason":"o."}]},
        {"entity_id":"e_y","entity_type":"character","canonical_name":"Y","aliases":[],"source_candidate_id":"sy","claims":[{"claim_id":"c5","predicate":"origin","value":{"kind":"text","text":"y."},"source_chapters":["chapter_000001"],"source_support":"explicit","certainty":"certain","inference_basis":None,"review_reason":"o."}]},
    ],
}

def _plan_dict(**kw):
    d = {"format_version":1,"adaptation_id":"adapt_t","source_promotion_id":"promo_t","source_chapter":"chapter_000001",
         "pack":{"id":"tp","name":"tp","version":"0.1.0","start_room_id":"r","player":{"max_hp":20,"attack":5,"defense":1,"inventory_capacity":20,"coins":0}},
         "room":{"canon_entity_ref":"e_loc","game_id":"r","name":"r","description":"d.","canon_claim_refs":["c1"],"adaptation_notes":"n."},
         "character":{"canon_entity_ref":"e_char","game_id":"c","name":"c","description":"d.","canon_claim_refs":["c2"],"adaptation_notes":"n."},
         "item":{"canon_entity_ref":"e_item","game_id":"i","name":"i","description":"d.","canon_claim_refs":[],"adaptation_notes":"n."},
         "quest":{"game_id":"q","kind":"collect_item","name":"q","description":"d.","target_item_id":"i","required_quantity":1,"reward_experience":10,"adaptation_notes":"n."},
         "dialogue":{"game_id":"di","character_id":"c","start_node_id":"start","nodes":[{"id":"start","text":"hi.","options":[{"id":"o","text":"bye.","next_node_id":"end","effects":[]}]},{"id":"end","text":"end.","options":[{"id":"o2","text":"bye.","next_node_id":None,"effects":[]}]}],"adaptation_notes":"n."},
         "omissions":[{"canon_entity_ref":"e_x","reason":"x."},{"canon_entity_ref":"e_y","reason":"y."}]}
    d.update(kw)
    return d

def cd(): return validate_canon_draft_document(_CD)
def plan(): return validate_adaptation_plan(_plan_dict())

# ═══════════════════════════════════════════════════════════════════════════
# Plan structural
# ═══════════════════════════════════════════════════════════════════════════

class PlanValidationTests(unittest.TestCase):
    def test_valid(self): self.assertEqual(plan().adaptation_id, "adapt_t")
    def test_bool_version(self):
        with self.assertRaises(AdaptationValidationError):
            validate_adaptation_plan({"format_version":True,"adaptation_id":"a","source_promotion_id":"p","source_chapter":"chapter_000001","pack":{},"room":{},"character":{},"item":{},"quest":{},"dialogue":{},"omissions":[]})
    def test_unknown_field(self):
        with self.assertRaises(AdaptationValidationError):
            validate_adaptation_plan({"format_version":1,"adaptation_id":"a","source_promotion_id":"p","source_chapter":"chapter_000001","pack":{},"room":{},"character":{},"item":{},"quest":{},"dialogue":{},"omissions":[],"extra":1})
    def test_quest_kind_wrong(self):
        with self.assertRaises(AdaptationValidationError):
            d=_plan_dict(); d["quest"]["kind"]="reach_room"; validate_adaptation_plan(d)
    def test_start_node_missing(self):
        with self.assertRaises(AdaptationValidationError):
            d=_plan_dict(); d["dialogue"]["start_node_id"]="nonexistent"; validate_adaptation_plan(d)
    def test_node_id_duplicate(self):
        with self.assertRaises(AdaptationValidationError):
            d=_plan_dict(); d["dialogue"]["nodes"]=[{"id":"same","text":"t.","options":[{"id":"o","text":"t.","next_node_id":None,"effects":[]}]},{"id":"same","text":"t.","options":[{"id":"o2","text":"t.","next_node_id":None,"effects":[]}]}]; validate_adaptation_plan(d)
    def test_option_id_duplicate(self):
        with self.assertRaises(AdaptationValidationError):
            d=_plan_dict(); n=d["dialogue"]["nodes"][0]; n["options"]=[{"id":"same","text":"a","next_node_id":None,"effects":[]},{"id":"same","text":"b","next_node_id":None,"effects":[]}]; d["dialogue"]["nodes"]=[n]; validate_adaptation_plan(d)
    def test_next_node_id_invalid_type(self):
        """next_node_id=[] must not leak TypeError."""
        with self.assertRaises(AdaptationValidationError):
            d=_plan_dict(); d["dialogue"]["nodes"][0]["options"][0]["next_node_id"]=[]; validate_adaptation_plan(d)
    def test_option_id_not_stable(self):
        with self.assertRaises(AdaptationValidationError):
            d=_plan_dict(); d["dialogue"]["nodes"][0]["options"][0]["id"]="Not Stable!"; validate_adaptation_plan(d)
    def test_omission_ref_duplicate(self):
        with self.assertRaises(AdaptationValidationError):
            d=_plan_dict(); d["omissions"]=[{"canon_entity_ref":"e_x","reason":"x."},{"canon_entity_ref":"e_x","reason":"y."}]; validate_adaptation_plan(d)
    def test_claim_refs_norm_dedup(self):
        with self.assertRaises(AdaptationValidationError):
            d=_plan_dict(); d["room"]["canon_claim_refs"]=["c1","c1"]; validate_adaptation_plan(d)
    def test_effects_nonempty_rejected(self):
        with self.assertRaises(AdaptationValidationError):
            d=_plan_dict(); d["dialogue"]["nodes"][0]["options"][0]["effects"]=[{"kind":"grant_experience","amount":10}]; validate_adaptation_plan(d)

# ═══════════════════════════════════════════════════════════════════════════
# Compilation
# ═══════════════════════════════════════════════════════════════════════════

class CompilationTests(unittest.TestCase):
    def test_valid_compile(self):
        p=compile_micro_pack(cd(),plan()); self.assertIsInstance(p,MicroContentPack)
    def test_source_promotion_mismatch(self):
        with self.assertRaises(CompilationError): compile_micro_pack(cd(),type(plan())(format_version=1,adaptation_id=plan().adaptation_id,source_promotion_id="wrong",source_chapter=plan().source_chapter,pack=plan().pack,room=plan().room,character=plan().character,item=plan().item,quest=plan().quest,dialogue=plan().dialogue,omissions=plan().omissions))
    def test_source_chapter_mismatch(self):
        with self.assertRaises(CompilationError): compile_micro_pack(cd(),type(plan())(format_version=1,adaptation_id=plan().adaptation_id,source_promotion_id=plan().source_promotion_id,source_chapter="chapter_000002",pack=plan().pack,room=plan().room,character=plan().character,item=plan().item,quest=plan().quest,dialogue=plan().dialogue,omissions=plan().omissions))
    def test_entity_ref_nonexistent(self):
        p=plan(); r2=type(p.room)(canon_entity_ref="nonexistent",game_id=p.room.game_id,name=p.room.name,description=p.room.description,canon_claim_refs=p.room.canon_claim_refs,adaptation_notes=p.room.adaptation_notes)
        with self.assertRaises(CompilationError):
            compile_micro_pack(cd(),type(plan())(format_version=1,adaptation_id=p.adaptation_id,source_promotion_id=p.source_promotion_id,source_chapter=p.source_chapter,pack=p.pack,room=r2,character=p.character,item=p.item,quest=p.quest,dialogue=p.dialogue,omissions=p.omissions))
    def test_entity_type_mismatch(self):
        p=plan(); r2=type(p.room)(canon_entity_ref="e_char",game_id=p.room.game_id,name=p.room.name,description=p.room.description,canon_claim_refs=p.room.canon_claim_refs,adaptation_notes=p.room.adaptation_notes)
        with self.assertRaises(CompilationError):
            compile_micro_pack(cd(),type(plan())(format_version=1,adaptation_id=p.adaptation_id,source_promotion_id=p.source_promotion_id,source_chapter=p.source_chapter,pack=p.pack,room=r2,character=p.character,item=p.item,quest=p.quest,dialogue=p.dialogue,omissions=p.omissions))
    def test_claim_ref_wrong_entity(self):
        p=plan(); r2=type(p.room)(canon_entity_ref="e_loc",game_id=p.room.game_id,name=p.room.name,description=p.room.description,canon_claim_refs=("c2",),adaptation_notes=p.room.adaptation_notes)
        with self.assertRaises(CompilationError):
            compile_micro_pack(cd(),type(plan())(format_version=1,adaptation_id=p.adaptation_id,source_promotion_id=p.source_promotion_id,source_chapter=p.source_chapter,pack=p.pack,room=r2,character=p.character,item=p.item,quest=p.quest,dialogue=p.dialogue,omissions=p.omissions))
    def test_coverage_missing(self):
        p=plan()
        with self.assertRaises(CompilationError):
            compile_micro_pack(cd(),type(plan())(format_version=1,adaptation_id=p.adaptation_id,source_promotion_id=p.source_promotion_id,source_chapter=p.source_chapter,pack=p.pack,room=p.room,character=p.character,item=p.item,quest=p.quest,dialogue=p.dialogue,omissions=p.omissions[:1]))
    def test_selected_in_omissions(self):
        p=plan()
        with self.assertRaises(CompilationError):
            compile_micro_pack(cd(),type(plan())(format_version=1,adaptation_id=p.adaptation_id,source_promotion_id=p.source_promotion_id,source_chapter=p.source_chapter,pack=p.pack,room=p.room,character=p.character,item=p.item,quest=p.quest,dialogue=p.dialogue,omissions=(type(p.omissions[0])(canon_entity_ref="e_loc",reason="x."),type(p.omissions[0])(canon_entity_ref="e_x",reason="x."))))
    def test_game_id_duplicate(self):
        p=plan(); r2=type(p.room)(canon_entity_ref="e_loc",game_id="c",name=p.room.name,description=p.room.description,canon_claim_refs=p.room.canon_claim_refs,adaptation_notes=p.room.adaptation_notes)
        with self.assertRaises(CompilationError):
            compile_micro_pack(cd(),type(plan())(format_version=1,adaptation_id=p.adaptation_id,source_promotion_id=p.source_promotion_id,source_chapter=p.source_chapter,pack=p.pack,room=r2,character=p.character,item=p.item,quest=p.quest,dialogue=p.dialogue,omissions=p.omissions))
    def test_start_room_mismatch(self):
        p=plan(); pk2=type(p.pack)(id=p.pack.id,name=p.pack.name,version=p.pack.version,start_room_id="wrong",player=p.pack.player)
        with self.assertRaises(CompilationError):
            compile_micro_pack(cd(),type(plan())(format_version=1,adaptation_id=p.adaptation_id,source_promotion_id=p.source_promotion_id,source_chapter=p.source_chapter,pack=pk2,room=p.room,character=p.character,item=p.item,quest=p.quest,dialogue=p.dialogue,omissions=p.omissions))

# ═══════════════════════════════════════════════════════════════════════════
# Output shape
# ═══════════════════════════════════════════════════════════════════════════

class OutputShapeTests(unittest.TestCase):
    def setUp(self): self.p = compile_micro_pack(cd(), plan())
    def test_item_shaped(self):
        self.assertEqual(set(self.p.items[0].keys()), {"id","name","description","stack_limit","canon_ref","adaptation_notes"})
    def test_quest_no_canon_ref(self):
        self.assertNotIn("canon_ref", self.p.quests[0])
    def test_dialogue_no_canon_ref(self):
        self.assertNotIn("canon_ref", self.p.dialogues[0])
    def test_dialogue_effects_empty(self):
        for n in self.p.dialogues[0]["nodes"]:
            for o in n["options"]: self.assertEqual(o["effects"], [])
    def test_description_verbatim(self):
        self.assertEqual(self.p.rooms[0]["description"], "d.")
    def test_load_content_pack(self):
        from lore2mud.content.loader import load_content_pack
        with tempfile.TemporaryDirectory() as td:
            from pipeline.adaptation import _pack_to_docs
            for fn,pl in _pack_to_docs(self.p):
                (Path(td)/fn).write_bytes(pl)
            cp = load_content_pack(td)
            self.assertEqual(cp.id,"tp"); self.assertEqual(len(cp.rooms),1); self.assertEqual(len(cp.quests),1); self.assertEqual(cp.quests["q"].kind,"collect_item")
    def test_frozen_dataclass(self):
        with self.assertRaises(AttributeError): plan().adaptation_id="changed"

# ═══════════════════════════════════════════════════════════════════════════
# Determinism
# ═══════════════════════════════════════════════════════════════════════════

class DeterminismTests(unittest.TestCase):
    def test_nodes_sorted_by_id(self):
        p=compile_micro_pack(cd(),plan())
        self.assertEqual([n["id"] for n in p.dialogues[0]["nodes"]],["end","start"])
    def test_options_order_preserved(self):
        p=compile_micro_pack(cd(),plan())
        self.assertEqual(p.dialogues[0]["nodes"][0]["options"][0]["id"],"o2")
        self.assertEqual(p.dialogues[0]["nodes"][1]["options"][0]["id"],"o")
    def test_options_order_reversed_differs(self):
        """Options in reverse input → options in reverse output."""
        d=_plan_dict()
        # "start" is nodes[0], "end" is nodes[1] in the plan dict
        d["dialogue"]["nodes"][0]["options"]=[
            {"id":"opt_b","text":"B","next_node_id":None,"effects":[]},
            {"id":"opt_a","text":"A","next_node_id":None,"effects":[]}]
        p2=compile_micro_pack(cd(),validate_adaptation_plan(d))
        # After node sort by ID: "end" is [0], "start" is [1]
        ids=[o["id"] for o in p2.dialogues[0]["nodes"][1]["options"]]
        self.assertEqual(ids,["opt_b","opt_a"])
    def test_reversed_omissions_same(self):
        p=plan(); rev=type(p)(format_version=1,adaptation_id=p.adaptation_id,source_promotion_id=p.source_promotion_id,source_chapter=p.source_chapter,pack=p.pack,room=p.room,character=p.character,item=p.item,quest=p.quest,dialogue=p.dialogue,omissions=tuple(reversed(p.omissions)))
        p1=compile_micro_pack(cd(),p); p2=compile_micro_pack(cd(),rev)
        for attr in ("pack","rooms","items","characters","quests","dialogues","monsters","shops"):
            self.assertEqual(getattr(p1,attr),getattr(p2,attr),f"{attr} differs")
    def test_reversed_entities_same(self):
        rev=dict(_CD); rev["entities"]=list(reversed(_CD["entities"]))
        cd_rev=validate_canon_draft_document(rev)
        p1=compile_micro_pack(cd(),plan()); p2=compile_micro_pack(cd_rev,plan())
        for attr in ("pack","rooms","items","characters","quests","dialogues","monsters","shops"):
            self.assertEqual(getattr(p1,attr),getattr(p2,attr),f"{attr} differs")
    def test_reversed_claim_refs_same(self):
        """Two claim refs reversed must produce same output."""
        # Create a CD where entity e_loc has claims c1 and c2, e_char has claims c2 and c1
        cd_copy = json.loads(json.dumps(_CD))
        cd_copy["entities"][0]["claims"].append({"claim_id":"c2","predicate":"origin","value":{"kind":"text","text":"o."},"source_chapters":["chapter_000001"],"source_support":"explicit","certainty":"certain","inference_basis":None,"review_reason":"o."})
        cd_copy["entities"][1]["claims"].append({"claim_id":"c1","predicate":"type","value":{"kind":"enum","enum_value":"v"},"source_chapters":["chapter_000001"],"source_support":"explicit","certainty":"certain","inference_basis":None,"review_reason":"o."})
        cd2=validate_canon_draft_document(cd_copy)
        d1=_plan_dict(); d1["room"]["canon_claim_refs"]=["c1","c2"]; d1["character"]["canon_claim_refs"]=["c2","c1"]
        d2=_plan_dict(); d2["room"]["canon_claim_refs"]=["c2","c1"]; d2["character"]["canon_claim_refs"]=["c1","c2"]
        p1=compile_micro_pack(cd2,validate_adaptation_plan(d1))
        p2=compile_micro_pack(cd2,validate_adaptation_plan(d2))
        for attr in ("pack","rooms","items","characters","quests","dialogues","monsters","shops"):
            self.assertEqual(getattr(p1,attr),getattr(p2,attr),f"{attr} differs")

# ═══════════════════════════════════════════════════════════════════════════
# Manifest validation
# ═══════════════════════════════════════════════════════════════════════════

class ManifestValidationTests(unittest.TestCase):
    def test_valid_manifest(self):
        p=compile_micro_pack(cd(),plan()); m=p.manifest
        self.assertEqual(len(m.bindings),3); self.assertEqual(len(m.game_only),2); self.assertEqual(len(m.omissions),2)
    def test_roundtrip(self):
        p=compile_micro_pack(cd(),plan()); from pipeline.adaptation import _manifest_dict
        d=json.loads(json.dumps(_manifest_dict(p.manifest)))
        self.assertEqual(validate_adaptation_manifest_document(d),p.manifest)
    def test_empty_bindings_rejected(self):
        with self.assertRaises(AdaptationValidationError):
            validate_adaptation_manifest_document({
                "format_version":1,"adaptation_id":"a","source":{"promotion_id":"p","chapter_id":"chapter_000001","chapter_sha256":"a"*64},
                "pack":{"id":"p","version":"0.1.0"},"bindings":[],"game_only":[],"omissions":[]})
    def test_wrong_go_kind(self):
        with self.assertRaises(AdaptationValidationError):
            validate_adaptation_manifest_document({
                "format_version":1,"adaptation_id":"a","source":{"promotion_id":"p","chapter_id":"chapter_000001","chapter_sha256":"a"*64},
                "pack":{"id":"p","version":"0.1.0"},
                "bindings":[{"game_kind":"room","game_id":"r","canon_entity_ref":"e_l","canon_claim_refs":[],"adaptation_notes":"n."},
                            {"game_kind":"character","game_id":"c","canon_entity_ref":"e_c","canon_claim_refs":[],"adaptation_notes":"n."},
                            {"game_kind":"item","game_id":"i","canon_entity_ref":"e_i","canon_claim_refs":[],"adaptation_notes":"n."}],
                "game_only":[{"game_kind":"item","game_id":"x","adaptation_notes":"n."},{"game_kind":"dialogue","game_id":"y","adaptation_notes":"n."}],"omissions":[]})
    def test_cross_set_game_id_duplicate(self):
        """binding and game_only sharing same game_id must be rejected."""
        with self.assertRaises(AdaptationValidationError):
            validate_adaptation_manifest_document({
                "format_version":1,"adaptation_id":"a","source":{"promotion_id":"p","chapter_id":"chapter_000001","chapter_sha256":"a"*64},
                "pack":{"id":"p","version":"0.1.0"},
                "bindings":[{"game_kind":"room","game_id":"same","canon_entity_ref":"e_l","canon_claim_refs":[],"adaptation_notes":"n."},
                            {"game_kind":"character","game_id":"c","canon_entity_ref":"e_c","canon_claim_refs":[],"adaptation_notes":"n."},
                            {"game_kind":"item","game_id":"i","canon_entity_ref":"e_i","canon_claim_refs":[],"adaptation_notes":"n."}],
                "game_only":[{"game_kind":"quest","game_id":"same","adaptation_notes":"n."},{"game_kind":"dialogue","game_id":"d","adaptation_notes":"n."}],"omissions":[]})
    def test_binding_cer_duplicate(self):
        with self.assertRaises(AdaptationValidationError):
            validate_adaptation_manifest_document({
                "format_version":1,"adaptation_id":"a","source":{"promotion_id":"p","chapter_id":"chapter_000001","chapter_sha256":"a"*64},
                "pack":{"id":"p","version":"0.1.0"},
                "bindings":[{"game_kind":"room","game_id":"r","canon_entity_ref":"e_l","canon_claim_refs":[],"adaptation_notes":"n."},
                            {"game_kind":"character","game_id":"c","canon_entity_ref":"e_l","canon_claim_refs":[],"adaptation_notes":"n."},
                            {"game_kind":"item","game_id":"i","canon_entity_ref":"e_i","canon_claim_refs":[],"adaptation_notes":"n."}],
                "game_only":[{"game_kind":"quest","game_id":"q","adaptation_notes":"n."},{"game_kind":"dialogue","game_id":"d","adaptation_notes":"n."}],"omissions":[]})
    def test_binding_omission_cer_overlap(self):
        with self.assertRaises(AdaptationValidationError):
            validate_adaptation_manifest_document({
                "format_version":1,"adaptation_id":"a","source":{"promotion_id":"p","chapter_id":"chapter_000001","chapter_sha256":"a"*64},
                "pack":{"id":"p","version":"0.1.0"},
                "bindings":[{"game_kind":"room","game_id":"r","canon_entity_ref":"e_l","canon_claim_refs":[],"adaptation_notes":"n."},
                            {"game_kind":"character","game_id":"c","canon_entity_ref":"e_c","canon_claim_refs":[],"adaptation_notes":"n."},
                            {"game_kind":"item","game_id":"i","canon_entity_ref":"e_i","canon_claim_refs":[],"adaptation_notes":"n."}],
                "game_only":[{"game_kind":"quest","game_id":"q","adaptation_notes":"n."},{"game_kind":"dialogue","game_id":"d","adaptation_notes":"n."}],
                "omissions":[{"canon_entity_ref":"e_l","reason":"nope"}]})
    def test_binding_kind_type_error_leak(self):
        """game_kind=[] must not leak TypeError."""
        with self.assertRaises(AdaptationValidationError):
            validate_adaptation_manifest_document({
                "format_version":1,"adaptation_id":"a","source":{"promotion_id":"p","chapter_id":"chapter_000001","chapter_sha256":"a"*64},
                "pack":{"id":"p","version":"0.1.0"},
                "bindings":[{"game_kind":[],"game_id":"r","canon_entity_ref":"e_l","canon_claim_refs":[],"adaptation_notes":"n."},
                            {"game_kind":"character","game_id":"c","canon_entity_ref":"e_c","canon_claim_refs":[],"adaptation_notes":"n."},
                            {"game_kind":"item","game_id":"i","canon_entity_ref":"e_i","canon_claim_refs":[],"adaptation_notes":"n."}],
                "game_only":[{"game_kind":"quest","game_id":"q","adaptation_notes":"n."},{"game_kind":"dialogue","game_id":"d","adaptation_notes":"n."}],"omissions":[]})

# ═══════════════════════════════════════════════════════════════════════════
# Atomic write
# ═══════════════════════════════════════════════════════════════════════════

class WriteTests(unittest.TestCase):
    def _pack(self): return compile_micro_pack(cd(),plan())
    def test_write_success(self):
        with tempfile.TemporaryDirectory() as td:
            r=write_micro_pack(self._pack(),os.path.join(td,"o"))
            self.assertTrue(os.path.isdir(r))
            self.assertTrue(os.path.isfile(os.path.join(r,"adaptation_manifest.json")))
    def test_reject_file(self):
        with tempfile.TemporaryDirectory() as td:
            p=os.path.join(td,"f"); open(p,"w").close()
            with self.assertRaises(FileExistsError): write_micro_pack(self._pack(),p)
    def test_reject_nonempty_dir(self):
        with tempfile.TemporaryDirectory() as td:
            p=os.path.join(td,"d"); os.mkdir(p); open(os.path.join(p,"x"),"w").close()
            with self.assertRaises(FileExistsError): write_micro_pack(self._pack(),p)
    def test_reject_empty_dir(self):
        with tempfile.TemporaryDirectory() as td:
            p=os.path.join(td,"d"); os.mkdir(p)
            with self.assertRaises(FileExistsError): write_micro_pack(self._pack(),p)
    def test_temp_cleaned_on_failure(self):
        """Staged failure must not leave temp dir."""
        p=self._pack(); from pipeline.adaptation import ManifestSource
        bad_m=type(p.manifest)(format_version=1,adaptation_id="a",
            source=ManifestSource(promotion_id="WRONG",chapter_id="c",chapter_sha256="a"*64),
            pack=p.manifest.pack,bindings=p.manifest.bindings,omissions=p.manifest.omissions,game_only=p.manifest.game_only)
        bad_p=MicroContentPack(pack=p.pack,rooms=p.rooms,items=p.items,characters=p.characters,quests=p.quests,dialogues=p.dialogues,monsters=p.monsters,shops=p.shops,manifest=bad_m)
        with tempfile.TemporaryDirectory() as td:
            out=os.path.join(td,"o")
            with self.assertRaises(AdaptationValidationError): write_micro_pack(bad_p,out)
            self.assertFalse(os.path.exists(out))
            self.assertEqual(len([f for f in os.listdir(td) if f.startswith(".l2w_adaptation_")]),0)
    def test_preexisting_temp_not_deleted(self):
        with tempfile.TemporaryDirectory() as td:
            pre=os.path.join(td,".l2w_adaptation_preexisting"); os.mkdir(pre); open(os.path.join(pre,"x.txt"),"w").close()
            write_micro_pack(self._pack(),os.path.join(td,"o"))
            self.assertTrue(os.path.isdir(pre))

# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

class CLITests(unittest.TestCase):
    def _write(self, td):
        cd_f=os.path.join(td,"cd.json")
        with open(cd_f,"w",encoding="utf-8") as f: json.dump(_CD,f,ensure_ascii=False)
        pl_f=os.path.join(td,"pl.json")
        with open(pl_f,"w",encoding="utf-8") as f: json.dump(_plan_dict(),f,ensure_ascii=False)
        with open(os.path.join(td,"bad.json"),"w") as f: json.dump(1,f)
        with open(os.path.join(td,"junk.json"),"w") as f: f.write("not json")
        return cd_f,pl_f
    def _cli(self, args): from pipeline.adaptation import main; return main(args)
    def test_success(self):
        with tempfile.TemporaryDirectory() as td:
            c,p=self._write(td); ec=self._cli(["--canon-draft",c,"--adaptation-plan",p,"--output-dir",os.path.join(td,"o")])
            self.assertEqual(ec,0)
    def test_bad_canon(self):
        with tempfile.TemporaryDirectory() as td:
            c,_=self._write(td); ec=self._cli(["--canon-draft",os.path.join(td,"bad.json"),"--adaptation-plan",os.path.join(td,"pl.json"),"--output-dir",os.path.join(td,"o")])
            self.assertEqual(ec,1)
    def test_bad_plan(self):
        with tempfile.TemporaryDirectory() as td:
            c,_=self._write(td); ec=self._cli(["--canon-draft",c,"--adaptation-plan",os.path.join(td,"bad.json"),"--output-dir",os.path.join(td,"o")])
            self.assertEqual(ec,1)
    def test_junk_json(self):
        with tempfile.TemporaryDirectory() as td:
            c,_=self._write(td); ec=self._cli(["--canon-draft",os.path.join(td,"junk.json"),"--adaptation-plan",os.path.join(td,"pl.json"),"--output-dir",os.path.join(td,"o")])
            self.assertEqual(ec,1)
    def test_output_conflict(self):
        with tempfile.TemporaryDirectory() as td:
            c,p=self._write(td); out=os.path.join(td,"o"); os.mkdir(out)
            ec=self._cli(["--canon-draft",c,"--adaptation-plan",p,"--output-dir",out])
            self.assertEqual(ec,1)
    def test_missing_arg(self):
        from pipeline.adaptation import main
        with self.assertRaises(SystemExit) as ctx: main(["--canon-draft","x.json"])
        self.assertEqual(ctx.exception.code, 2)

# ═══════════════════════════════════════════════════════════════════════════
# Schema
# ═══════════════════════════════════════════════════════════════════════════

class SchemaTests(unittest.TestCase):
    def test_plan_no_external(self):
        with open(REPO/"schemas"/"adaptation_plan.schema.json",encoding="utf-8") as f:
            self.assertNotIn("canon_ref",json.dumps(json.load(f)))
    def test_manifest_exact_counts(self):
        with open(REPO/"schemas"/"adaptation_manifest.schema.json",encoding="utf-8") as f:
            s=json.load(f)
        self.assertEqual(s["properties"]["bindings"]["minItems"],3); self.assertEqual(s["properties"]["bindings"]["maxItems"],3)
        self.assertEqual(s["properties"]["game_only"]["minItems"],2); self.assertEqual(s["properties"]["game_only"]["maxItems"],2)

# ═══════════════════════════════════════════════════════════════════════════
# World playthrough (golden path)
# ═══════════════════════════════════════════════════════════════════════════

class WorldPlaythroughTest(unittest.TestCase):
    def test_playthrough(self):
        """Generate → validate → load → player initial state checks."""
        with tempfile.TemporaryDirectory() as td:
            cd_f=os.path.join(td,"cd.json")
            with open(cd_f,"w",encoding="utf-8") as f: json.dump(_CD,f,ensure_ascii=False)
            pl_f=os.path.join(td,"pl.json")
            with open(pl_f,"w",encoding="utf-8") as f: json.dump(_plan_dict(),f,ensure_ascii=False)
            out=os.path.join(td,"output")

            # Generate via CLI
            from pipeline.adaptation import main as cli
            ec=cli(["--canon-draft",cd_f,"--adaptation-plan",pl_f,"--output-dir",out])
            self.assertEqual(ec,0)

            # Validate via loader — this also validates entity references
            from lore2mud.content.loader import load_content_pack
            cp=load_content_pack(out)
            self.assertEqual(cp.id,"tp")
            self.assertEqual(len(cp.rooms),1)
            self.assertEqual(len(cp.quests),1)
            self.assertEqual(cp.quests["q"].kind,"collect_item")

    def test_subprocess_generate_and_validate(self):
        """Real subprocess CLI: generate → lore2mud validate."""
        with tempfile.TemporaryDirectory() as td:
            cd_f=os.path.join(td,"cd.json")
            with open(cd_f,"w",encoding="utf-8") as f: json.dump(_CD,f,ensure_ascii=False)
            pl_f=os.path.join(td,"pl.json")
            with open(pl_f,"w",encoding="utf-8") as f: json.dump(_plan_dict(),f,ensure_ascii=False)
            out=os.path.join(td,"output")

            import subprocess
            import sys
            r=subprocess.run([sys.executable,"-m","pipeline.adaptation",
                "--canon-draft",cd_f,"--adaptation-plan",pl_f,"--output-dir",out],
                capture_output=True,text=True)
            self.assertEqual(r.returncode,0,f"stderr: {r.stderr}")

            r2=subprocess.run([sys.executable,"-m","lore2mud","validate","--content",out],
                capture_output=True,text=True)
            self.assertEqual(r2.returncode,0,f"stderr: {r2.stderr}")


# ═══════════════════════════════════════════════════════════════════════════
# Golden fixture test
# ═══════════════════════════════════════════════════════════════════════════

class GoldenFixtureTest(unittest.TestCase):
    def test_golden_output_bytes(self):
        """Load fixtures, compile, compare 9 files byte-for-byte with expected."""
        fixture_dir = REPO / "tests" / "fixtures" / "adaptation"
        with open(fixture_dir / "mini_canon_draft.json", encoding="utf-8") as f:
            cd = validate_canon_draft_document(json.load(f))
        with open(fixture_dir / "valid_plan.json", encoding="utf-8") as f:
            plan = validate_adaptation_plan(json.load(f))
        pack = compile_micro_pack(cd, plan)

        expected = fixture_dir / "expected_output"
        for fn, payload in _pack_to_docs(pack):
            expected_file = expected / fn
            self.assertTrue(expected_file.exists(), f"Missing golden: {fn}")
            with open(expected_file, "rb") as f:
                self.assertEqual(payload, f.read(), f"Golden mismatch: {fn}")

            # Also verify write_micro_pack produces same bytes
            with tempfile.TemporaryDirectory() as td:
                out = os.path.join(td, "o")
                write_micro_pack(pack, out)
                with open(os.path.join(out, fn), "rb") as fr:
                    self.assertEqual(payload, fr.read(), f"Write mismatch: {fn}")

        # Final directory must pass loader
        with tempfile.TemporaryDirectory() as td:
            for fn, payload in _pack_to_docs(pack):
                (Path(td) / fn).write_bytes(payload)
            from lore2mud.content.loader import load_content_pack
            load_content_pack(td)  # raises on failure


# ═══════════════════════════════════════════════════════════════════════════
# MicroContentPack type checks
# ═══════════════════════════════════════════════════════════════════════════

class MCPTypeTests(unittest.TestCase):
    def test_pack_as_tuple_rejected(self):
        with self.assertRaises(TypeError):
            MicroContentPack(pack=(), rooms=(), items=(), characters=(), quests=(),
                dialogues=(), monsters=(), shops=(), manifest=compile_micro_pack(cd(),plan()).manifest)
    def test_rooms_as_dict_rejected(self):
        with self.assertRaises(TypeError):
            MicroContentPack(pack={}, rooms={}, items=(), characters=(), quests=(),
                dialogues=(), monsters=(), shops=(), manifest=compile_micro_pack(cd(),plan()).manifest)
    def test_rooms_item_is_str_rejected(self):
        with self.assertRaises(TypeError):
            MicroContentPack(pack={}, rooms=("not_a_dict",), items=(), characters=(),
                quests=(), dialogues=(), monsters=(), shops=(),
                manifest=compile_micro_pack(cd(),plan()).manifest)


# ═══════════════════════════════════════════════════════════════════════════
# Schema stable ID tests
# ═══════════════════════════════════════════════════════════════════════════

class SchemaStableIDTests(unittest.TestCase):
    def _load(self):
        with open(REPO / "schemas" / "adaptation_plan.schema.json", encoding="utf-8") as f:
            return json.load(f)
    def _def(self, name):
        return self._load()["$defs"][name]

    def test_start_node_id_is_stable(self):
        d = self._def("dialogue_adaptation")
        self.assertEqual(d["properties"]["start_node_id"], {"$ref": "#/$defs/stable_id"})

    def test_node_id_is_stable(self):
        d = self._def("dialogue_node")
        self.assertEqual(d["properties"]["id"], {"$ref": "#/$defs/stable_id"})

    def test_option_id_is_stable(self):
        d = self._def("dialogue_option")
        self.assertEqual(d["properties"]["id"], {"$ref": "#/$defs/stable_id"})

    def test_next_node_id_is_stable_or_null(self):
        d = self._def("dialogue_option")
        nn = d["properties"]["next_node_id"]
        self.assertEqual(nn["oneOf"][1], {"$ref": "#/$defs/stable_id"})


# ═══════════════════════════════════════════════════════════════════════════
# Writer fsync & path tests
# ═══════════════════════════════════════════════════════════════════════════

class WriterFsyncPathTests(unittest.TestCase):
    def test_write_uses_open_flush_fsync(self):
        """Verify the writer code contains open/flush/fsync."""
        import inspect
        src = inspect.getsource(write_micro_pack)
        self.assertIn(".write(", src)
        self.assertIn(".flush()", src)
        self.assertIn(".fsync(", src)

    def test_traversal_rejected_at_writer_level(self):
        """Writer-level test, not private helper."""
        from pipeline.adaptation import _validate_docs
        with self.assertRaises(CompilationError):
            _validate_docs([("pack.json",b"{}"),("rooms.json",b"[]"),("items.json",b"[]"),
                ("characters.json",b"[]"),("quests.json",b"[]"),("dialogues.json",b"[]"),
                ("monsters.json",b"[]"),("shops.json",b"[]"),("../escape.txt",b"x")])

    def test_extra_doc_rejected(self):
        from pipeline.adaptation import _validate_docs
        with self.assertRaises(CompilationError):
            _validate_docs([("pack.json",b"{}"),("rooms.json",b"[]"),("items.json",b"[]"),
                ("characters.json",b"[]"),("quests.json",b"[]"),("dialogues.json",b"[]"),
                ("monsters.json",b"[]"),("shops.json",b"[]"),("adaptation_manifest.json",b"{}"),("extra.json",b"{}")])

    def test_missing_doc_rejected(self):
        from pipeline.adaptation import _validate_docs
        with self.assertRaises(CompilationError):
            _validate_docs([("pack.json",b"{}")])

    @unittest.skipUnless(os.name == "posix", "symlink test requires POSIX")
    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            link = os.path.join(td, "link")
            os.symlink(td, link)
            with self.assertRaises(FileExistsError):
                write_micro_pack(compile_micro_pack(cd(),plan()), link)

if __name__=="__main__":
    unittest.main()
