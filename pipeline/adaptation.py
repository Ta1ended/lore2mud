"""Validate adaptation plans, compile canon drafts to micro content packs."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Any, Literal

from pipeline.canon import CanonDraft, validate_canon_draft_document, CanonDraftValidationError

from lore2mud.content.loader import load_content_pack, ContentValidationError

_STABLE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_CHAPTER_ID_RE = re.compile(r"^chapter_[0-9]{6}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

_ALLOWED_FILES = frozenset({
    "pack.json", "rooms.json", "items.json", "characters.json",
    "quests.json", "dialogues.json", "monsters.json", "shops.json",
    "adaptation_manifest.json",
})

_FILE_FIELDS = ("pack", "rooms", "items", "characters", "quests", "dialogues", "monsters", "shops")


class AdaptationValidationError(ValueError):
    def __init__(self, issues: tuple[str, ...]) -> None:
        self.issues = issues
        super().__init__("\n".join(f"- {i}" for i in issues))


class CompilationError(ValueError):
    def __init__(self, issues: tuple[str, ...]) -> None:
        self.issues = issues
        super().__init__("\n".join(f"- {i}" for i in issues))


# ── Data models ────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class PlayerSub:
    max_hp: int = 20
    attack: int = 5
    defense: int = 1
    inventory_capacity: int = 20
    coins: int = 0

@dataclass(frozen=True, slots=True)
class PackProfile:
    id: str; name: str; version: str; start_room_id: str; player: PlayerSub

@dataclass(frozen=True, slots=True)
class RoomAdaptation:
    canon_entity_ref: str; game_id: str; name: str; description: str
    canon_claim_refs: tuple[str, ...]; adaptation_notes: str

@dataclass(frozen=True, slots=True)
class CharacterAdaptation:
    canon_entity_ref: str; game_id: str; name: str; description: str
    canon_claim_refs: tuple[str, ...]; adaptation_notes: str

@dataclass(frozen=True, slots=True)
class ItemAdaptation:
    canon_entity_ref: str; game_id: str; name: str; description: str
    canon_claim_refs: tuple[str, ...]; adaptation_notes: str

@dataclass(frozen=True, slots=True)
class QuestAdaptation:
    game_id: str; kind: Literal["collect_item"]; name: str; description: str
    target_item_id: str; required_quantity: int; reward_experience: int; adaptation_notes: str

@dataclass(frozen=True, slots=True)
class DialogueOptionDef:
    id: str; text: str; next_node_id: str | None

@dataclass(frozen=True, slots=True)
class DialogueNodeDef:
    id: str; text: str; options: tuple[DialogueOptionDef, ...]

@dataclass(frozen=True, slots=True)
class DialogueAdaptation:
    game_id: str; character_id: str; start_node_id: str
    nodes: tuple[DialogueNodeDef, ...]; adaptation_notes: str

@dataclass(frozen=True, slots=True)
class OmissionEntry:
    canon_entity_ref: str; reason: str

@dataclass(frozen=True, slots=True)
class AdaptationPlan:
    format_version: int; adaptation_id: str; source_promotion_id: str; source_chapter: str
    pack: PackProfile; room: RoomAdaptation; character: CharacterAdaptation; item: ItemAdaptation
    quest: QuestAdaptation; dialogue: DialogueAdaptation; omissions: tuple[OmissionEntry, ...]

# ── Manifest models ────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ManifestSource:
    promotion_id: str; chapter_id: str; chapter_sha256: str

@dataclass(frozen=True, slots=True)
class ManifestPack:
    id: str; version: str

@dataclass(frozen=True, slots=True)
class ManifestBinding:
    game_kind: str; game_id: str; canon_entity_ref: str
    canon_claim_refs: tuple[str, ...]; adaptation_notes: str

@dataclass(frozen=True, slots=True)
class ManifestOmission:
    canon_entity_ref: str; reason: str

@dataclass(frozen=True, slots=True)
class ManifestGameOnly:
    game_kind: str; game_id: str; adaptation_notes: str

@dataclass(frozen=True, slots=True)
class AdaptationManifest:
    format_version: int; adaptation_id: str; source: ManifestSource; pack: ManifestPack
    bindings: tuple[ManifestBinding, ...]; omissions: tuple[ManifestOmission, ...]
    game_only: tuple[ManifestGameOnly, ...]

# ── MicroContentPack (semantic model: dict/tuple, not bytes) ────────────────

@dataclass(frozen=True, slots=True)
class MicroContentPack:
    pack: dict
    rooms: tuple[dict, ...]
    items: tuple[dict, ...]
    characters: tuple[dict, ...]
    quests: tuple[dict, ...]
    dialogues: tuple[dict, ...]
    monsters: tuple[dict, ...]
    shops: tuple[dict, ...]
    manifest: AdaptationManifest

    def __post_init__(self) -> None:
        for attr in _FILE_FIELDS:
            val = getattr(self, attr)
            if not isinstance(val, (dict, tuple)):
                raise TypeError(f"{attr} 必须为 dict 或 tuple")
        if not isinstance(self.manifest, AdaptationManifest):
            raise TypeError("manifest 必须为 AdaptationManifest")

# ── Internal helpers ───────────────────────────────────────────────────────

def _nk(s: str) -> str:
    return unicodedata.normalize("NFKC", s).casefold().strip()

def _txt(obj: dict, key: str, loc: str, issues: list) -> str:
    v = obj.get(key)
    if not isinstance(v, str) or not v.strip():
        issues.append(f"{loc}.{key} 必须为非空字符串")
        return ""
    return v

def _int(obj: dict, key: str, loc: str, issues: list, *, minv: int = 0, dflt: int = 0) -> int:
    if key not in obj:
        issues.append(f"{loc}.{key} 为必填字段")
        return dflt
    v = obj.get(key)
    if isinstance(v, bool) or not isinstance(v, int) or v < minv:
        issues.append(f"{loc}.{key} 必须为 >= {minv} 的整数")
        return dflt
    return v

def _sid(s: str, loc: str, issues: list) -> None:
    if s and not _STABLE_ID_RE.fullmatch(s):
        issues.append(f"{loc} 必须匹配稳定 ID 格式")

def _unk(obj: dict, allowed: frozenset, loc: str, issues: list) -> None:
    for k in sorted(set(obj) - allowed):
        issues.append(f"{loc} 包含未知字段：{k!r}")

def _stra(raw: Any, loc: str, issues: list) -> tuple[str, ...]:
    if not isinstance(raw, list):
        issues.append(f"{loc} 必须为数组")
        return ()
    seen: set[str] = set()
    res: list[str] = []
    for vi, v in enumerate(raw):
        if not isinstance(v, str):
            issues.append(f"{loc}[{vi}] 必须为字符串")
            continue
        if not v.strip():
            issues.append(f"{loc}[{vi}] 必须为非空字符串")
            continue
        _sid(v, f"{loc}[{vi}]", issues)
        nk = _nk(v)
        if nk in seen:
            issues.append(f"{loc}[{vi}] 规范化后重复：{v!r}")
        seen.add(nk)
        res.append(v)
    return tuple(res)


def _json_bytes(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"


# ── Struct validator ───────────────────────────────────────────────────────

def validate_adaptation_plan(data: object) -> AdaptationPlan:
    issues: list[str] = []
    if not isinstance(data, dict):
        raise AdaptationValidationError(("根对象必须为 JSON 对象",))

    _unk(data, frozenset({"format_version","adaptation_id","source_promotion_id",
        "source_chapter","pack","room","character","item","quest","dialogue","omissions"}), "根对象", issues)
    fv = data.get("format_version")
    if fv is None or isinstance(fv, bool) or not isinstance(fv, int) or fv != 1:
        issues.append("format_version 必须为 1")
    aid = _txt(data, "adaptation_id", "根对象", issues); _sid(aid, "adaptation_id", issues)
    spi = _txt(data, "source_promotion_id", "根对象", issues); _sid(spi, "source_promotion_id", issues)
    sc = _txt(data, "source_chapter", "根对象", issues)
    if sc and not _CHAPTER_ID_RE.fullmatch(sc):
        issues.append("source_chapter 必须匹配 ^chapter_[0-9]{6}$")

    rp = data.get("pack")
    if not isinstance(rp, dict): issues.append("pack 必须为对象")
    for k in ("room","character","item"):
        if not isinstance(data.get(k), dict): issues.append(f"{k} 必须为对象")
    if not isinstance(data.get("quest"), dict): issues.append("quest 必须为对象")
    if not isinstance(data.get("dialogue"), dict): issues.append("dialogue 必须为对象")
    if not isinstance(data.get("omissions"), list): issues.append("omissions 必须为数组")
    if issues: raise AdaptationValidationError(tuple(issues))

    # pack
    _unk(rp, frozenset({"id","name","version","start_room_id","player"}), "pack", issues)
    pid = _txt(rp, "id", "pack", issues); _sid(pid, "pack.id", issues)
    pname = _txt(rp, "name", "pack", issues); pver = _txt(rp, "version", "pack", issues)
    srid = _txt(rp, "start_room_id", "pack", issues); _sid(srid, "pack.start_room_id", issues)
    raw_ply = rp.get("player")
    if not isinstance(raw_ply, dict):
        issues.append("pack.player 必须为对象"); player = PlayerSub()
    else:
        _unk(raw_ply, frozenset({"max_hp","attack","defense","inventory_capacity","coins"}), "pack.player", issues)
        player = PlayerSub(max_hp=_int(raw_ply,"max_hp","pack.player",issues,minv=1,dflt=20),
            attack=_int(raw_ply,"attack","pack.player",issues,minv=1,dflt=5),
            defense=_int(raw_ply,"defense","pack.player",issues,minv=0,dflt=1),
            inventory_capacity=_int(raw_ply,"inventory_capacity","pack.player",issues,minv=1,dflt=20),
            coins=_int(raw_ply,"coins","pack.player",issues,minv=0,dflt=0))
    pack = PackProfile(id=pid,name=pname,version=pver,start_room_id=srid,player=player)

    def _adapt(kind: str) -> tuple:
        raw = data[kind]
        _unk(raw, frozenset({"canon_entity_ref","game_id","name","description","canon_claim_refs","adaptation_notes"}), kind, issues)
        cer = _txt(raw, "canon_entity_ref", kind, issues); _sid(cer, f"{kind}.canon_entity_ref", issues)
        gid = _txt(raw, "game_id", kind, issues); _sid(gid, f"{kind}.game_id", issues)
        name = _txt(raw, "name", kind, issues); desc = _txt(raw, "description", kind, issues)
        an = _txt(raw, "adaptation_notes", kind, issues)
        ccr = _stra(raw.get("canon_claim_refs"), f"{kind}.canon_claim_refs", issues)
        return cer, gid, name, desc, an, ccr
    r_cer,r_gid,r_name,r_desc,r_an,r_ccr = _adapt("room")
    room = RoomAdaptation(canon_entity_ref=r_cer,game_id=r_gid,name=r_name,description=r_desc,adaptation_notes=r_an,canon_claim_refs=r_ccr)
    c_cer,c_gid,c_name,c_desc,c_an,c_ccr = _adapt("character")
    character = CharacterAdaptation(canon_entity_ref=c_cer,game_id=c_gid,name=c_name,description=c_desc,adaptation_notes=c_an,canon_claim_refs=c_ccr)
    i_cer,i_gid,i_name,i_desc,i_an,i_ccr = _adapt("item")
    item = ItemAdaptation(canon_entity_ref=i_cer,game_id=i_gid,name=i_name,description=i_desc,adaptation_notes=i_an,canon_claim_refs=i_ccr)

    ra = data["quest"]
    _unk(ra, frozenset({"game_id","kind","name","description","target_item_id","required_quantity","reward_experience","adaptation_notes"}), "quest", issues)
    q_gid = _txt(ra, "game_id", "quest", issues); _sid(q_gid, "quest.game_id", issues)
    if ra.get("kind") != "collect_item": issues.append("quest.kind 必须为 collect_item")
    q_name = _txt(ra, "name", "quest", issues); q_desc = _txt(ra, "description", "quest", issues)
    q_tid = _txt(ra, "target_item_id", "quest", issues); _sid(q_tid, "quest.target_item_id", issues)
    q_rq = _int(ra,"required_quantity","quest",issues,minv=1,dflt=1)
    q_re = _int(ra,"reward_experience","quest",issues,minv=1,dflt=10)
    q_an = _txt(ra, "adaptation_notes", "quest", issues)
    quest = QuestAdaptation(game_id=q_gid,kind="collect_item",name=q_name,description=q_desc,target_item_id=q_tid,required_quantity=q_rq,reward_experience=q_re,adaptation_notes=q_an)

    rv = data["dialogue"]
    _unk(rv, frozenset({"game_id","character_id","start_node_id","nodes","adaptation_notes"}), "dialogue", issues)
    d_gid = _txt(rv, "game_id", "dialogue", issues); _sid(d_gid, "dialogue.game_id", issues)
    d_cid = _txt(rv, "character_id", "dialogue", issues); _sid(d_cid, "dialogue.character_id", issues)
    d_start = _txt(rv, "start_node_id", "dialogue", issues); _sid(d_start, "dialogue.start_node_id", issues)
    d_an = _txt(rv, "adaptation_notes", "dialogue", issues)
    raw_nodes = rv.get("nodes")
    if not isinstance(raw_nodes, list) or len(raw_nodes) == 0:
        issues.append("dialogue.nodes 必须为非空数组"); raw_nodes = []
    nids: set[str] = set(); all_next: set[str] = set(); parsed_nodes: list[DialogueNodeDef] = []
    for ni, rn in enumerate(raw_nodes):
        nloc = f"dialogue.nodes[{ni}]"
        if not isinstance(rn, dict): issues.append(f"{nloc} 必须为对象"); continue
        _unk(rn, frozenset({"id","text","options"}), nloc, issues)
        nid = _txt(rn, "id", nloc, issues); _sid(nid, f"{nloc}.id", issues)
        if nid in nids: issues.append(f"{nloc}.id 重复：{nid}")
        nids.add(nid); ntext = _txt(rn, "text", nloc, issues)
        raw_opts = rn.get("options")
        if not isinstance(raw_opts, list) or len(raw_opts) == 0: issues.append(f"{nloc}.options 必须为非空数组"); continue
        oids: set[str] = set(); parsed_opts: list[DialogueOptionDef] = []
        for oi, ro in enumerate(raw_opts):
            oloc = f"{nloc}.options[{oi}]"
            if not isinstance(ro, dict): issues.append(f"{oloc} 必须为对象"); continue
            _unk(ro, frozenset({"id","text","next_node_id","effects"}), oloc, issues)
            oid = _txt(ro, "id", oloc, issues); _sid(oid, f"{oloc}.id", issues)
            if oid in oids: issues.append(f"{oloc}.id 重复：{oid}")
            oids.add(oid); otext = _txt(ro, "text", oloc, issues)
            rnid = ro.get("next_node_id")
            if rnid is not None:
                if isinstance(rnid, str) and rnid.strip():
                    _sid(rnid, f"{oloc}.next_node_id", issues)
                    all_next.add(rnid)
                else:
                    issues.append(f"{oloc}.next_node_id 必须为非空字符串或 null")
                    rnid = None
            raw_eff = ro.get("effects")
            if not isinstance(raw_eff, list) or len(raw_eff) > 0:
                issues.append(f"{oloc}.effects 必须为空数组（[]）")
            parsed_opts.append(DialogueOptionDef(id=oid,text=otext,next_node_id=rnid))
        parsed_nodes.append(DialogueNodeDef(id=nid,text=ntext,options=tuple(parsed_opts)))
    if d_start not in nids: issues.append(f"start_node_id {d_start!r} 不在 nodes 中")
    for nid_ref in sorted(all_next - nids): issues.append(f"next_node_id {nid_ref!r} 引用了不存在的节点")
    dialogue = DialogueAdaptation(game_id=d_gid,character_id=d_cid,start_node_id=d_start,nodes=tuple(parsed_nodes),adaptation_notes=d_an)

    om_cers: set[str] = set(); parsed_oms: list[OmissionEntry] = []
    for oi, ro in enumerate(data["omissions"]):
        oloc = f"omissions[{oi}]"
        if not isinstance(ro, dict): issues.append(f"{oloc} 必须为对象"); continue
        _unk(ro, frozenset({"canon_entity_ref","reason"}), oloc, issues)
        o_cer = _txt(ro, "canon_entity_ref", oloc, issues); _sid(o_cer, f"{oloc}.canon_entity_ref", issues)
        if o_cer in om_cers: issues.append(f"{oloc}.canon_entity_ref 重复：{o_cer}")
        om_cers.add(o_cer); o_reason = _txt(ro, "reason", oloc, issues)
        parsed_oms.append(OmissionEntry(canon_entity_ref=o_cer, reason=o_reason))
    if issues: raise AdaptationValidationError(tuple(issues))
    return AdaptationPlan(format_version=1,adaptation_id=aid,source_promotion_id=spi,source_chapter=sc,
        pack=pack,room=room,character=character,item=item,quest=quest,dialogue=dialogue,omissions=tuple(parsed_oms))


# ── Compile ────────────────────────────────────────────────────────────────

def compile_micro_pack(canon_draft: CanonDraft, plan: AdaptationPlan) -> MicroContentPack:
    issues: list[str] = []
    entities = {e.entity_id: e for e in canon_draft.entities}

    if plan.source_promotion_id != canon_draft.promotion_id:
        issues.append(f"source_promotion_id ({plan.source_promotion_id}) 必须等于 canon_draft.promotion_id ({canon_draft.promotion_id})")
    if plan.source_chapter != canon_draft.source.chapter_id:
        issues.append(f"source_chapter ({plan.source_chapter}) 必须等于 canon_draft.source.chapter_id ({canon_draft.source.chapter_id})")

    adapted: dict[str, str] = {}
    et_map = {"room": "location", "character": "character", "item": "item"}
    for kind, entry in [("room",plan.room),("character",plan.character),("item",plan.item)]:
        cer = entry.canon_entity_ref
        if cer in adapted: issues.append(f"{kind}.canon_entity_ref {cer!r} 已被 {adapted[cer]} 使用")
        adapted[cer] = kind
        if cer not in entities: issues.append(f"{kind}.canon_entity_ref {cer!r} 不存在于 CanonDraft"); continue
        ent = entities[cer]
        if ent.entity_type != et_map[kind]: issues.append(f"{kind}.canon_entity_ref {cer!r} 类型为 {ent.entity_type}，期望 {et_map[kind]}")
        eids = {c.claim_id for c in ent.claims}
        for cref in entry.canon_claim_refs:
            if cref not in eids: issues.append(f"{kind}.canon_claim_refs 中的 {cref!r} 不属于 entity {cer!r}")

    omitted: set[str] = set()
    for om in plan.omissions:
        cer = om.canon_entity_ref
        if cer not in entities: issues.append(f"omissions 引用了不存在的 entity {cer!r}"); continue
        if cer in adapted: issues.append(f"omissions 引用了已适配的 entity {cer!r}")
        omitted.add(cer)

    all_ids = set(entities.keys()); covered = set(adapted.keys()) | omitted
    missing = all_ids - covered; extra = covered - all_ids
    if missing: issues.append(f"entity 未被覆盖：{sorted(missing)}")
    if extra: issues.append(f"adaptations/omissions 引用不存在 entity：{sorted(extra)}")

    all_gids: set[str] = set(); gid_src: dict[str, str] = {}
    for kind, entry in [("room",plan.room),("character",plan.character),("item",plan.item),("quest",plan.quest),("dialogue",plan.dialogue)]:
        gid = entry.game_id
        if gid in all_gids: issues.append(f"game_id {gid!r} 重复（{kind} 与 {gid_src.get(gid)}）")
        all_gids.add(gid); gid_src[gid] = kind

    if plan.pack.start_room_id != plan.room.game_id: issues.append("pack.start_room_id 必须等于 room.game_id")
    if plan.dialogue.character_id != plan.character.game_id: issues.append("dialogue.character_id 必须等于 character.game_id")
    if plan.quest.target_item_id != plan.item.game_id: issues.append("quest.target_item_id 必须等于 item.game_id")
    if plan.quest.kind != "collect_item": issues.append("quest.kind 必须为 collect_item")
    if plan.quest.required_quantity != 1: issues.append("quest.required_quantity 必须为 1")
    if issues: raise CompilationError(tuple(issues))

    scid = canon_draft.source.chapter_id; src_ch = [scid]

    pack_dict = {
        "id":plan.pack.id,"name":plan.pack.name,"version":plan.pack.version,"start_room_id":plan.pack.start_room_id,
        "player":{"max_hp":plan.pack.player.max_hp,"attack":plan.pack.player.attack,"defense":plan.pack.player.defense,"inventory_capacity":plan.pack.player.inventory_capacity,"coins":plan.pack.player.coins},
        "extensions":{"canon_provider":{"kind":"adaptation_manifest","format_version":1,"path":"adaptation_manifest.json"}}}
    rooms_t = ({"id":plan.room.game_id,"name":plan.room.name,"description":plan.room.description,"exits":{},"item_stacks":[{"item_id":plan.item.game_id,"quantity":1}],"monster_ids":[],"canon_ref":{"entity_id":plan.room.canon_entity_ref,"source_chapters":src_ch},"adaptation_notes":plan.room.adaptation_notes},)
    items_t = ({"id":plan.item.game_id,"name":plan.item.name,"description":plan.item.description,"stack_limit":1,"canon_ref":{"entity_id":plan.item.canon_entity_ref,"source_chapters":src_ch},"adaptation_notes":plan.item.adaptation_notes},)
    chars_t = ({"id":plan.character.game_id,"name":plan.character.name,"description":plan.character.description,"room_id":plan.pack.start_room_id,"canon_ref":{"entity_id":plan.character.canon_entity_ref,"source_chapters":src_ch},"adaptation_notes":plan.character.adaptation_notes},)
    quests_t = ({"id":plan.quest.game_id,"kind":"collect_item","name":plan.quest.name,"description":plan.quest.description,"trigger_room_id":plan.pack.start_room_id,"target_item_id":plan.quest.target_item_id,"required_quantity":1,"reward_experience":plan.quest.reward_experience,"adaptation_notes":plan.quest.adaptation_notes},)
    nodes_out = [{"id":n.id,"text":n.text,"options":[{"id":o.id,"text":o.text,"next_node_id":o.next_node_id,"effects":[]} for o in n.options]} for n in sorted(plan.dialogue.nodes, key=lambda n: _nk(n.id))]
    dials_t = ({"id":plan.dialogue.game_id,"character_id":plan.dialogue.character_id,"start_node_id":plan.dialogue.start_node_id,"nodes":nodes_out,"adaptation_notes":plan.dialogue.adaptation_notes},)
    empty_t = ()

    binds = tuple(sorted([
        ManifestBinding(game_kind="room",game_id=plan.room.game_id,canon_entity_ref=plan.room.canon_entity_ref,canon_claim_refs=tuple(sorted(plan.room.canon_claim_refs,key=_nk)),adaptation_notes=plan.room.adaptation_notes),
        ManifestBinding(game_kind="character",game_id=plan.character.game_id,canon_entity_ref=plan.character.canon_entity_ref,canon_claim_refs=tuple(sorted(plan.character.canon_claim_refs,key=_nk)),adaptation_notes=plan.character.adaptation_notes),
        ManifestBinding(game_kind="item",game_id=plan.item.game_id,canon_entity_ref=plan.item.canon_entity_ref,canon_claim_refs=tuple(sorted(plan.item.canon_claim_refs,key=_nk)),adaptation_notes=plan.item.adaptation_notes),
    ], key=lambda b: (b.game_kind,_nk(b.game_id))))
    gos = tuple(sorted([
        ManifestGameOnly(game_kind="quest",game_id=plan.quest.game_id,adaptation_notes=plan.quest.adaptation_notes),
        ManifestGameOnly(game_kind="dialogue",game_id=plan.dialogue.game_id,adaptation_notes=plan.dialogue.adaptation_notes),
    ], key=lambda g: (g.game_kind,_nk(g.game_id))))
    oms = tuple(sorted([ManifestOmission(canon_entity_ref=o.canon_entity_ref,reason=o.reason) for o in plan.omissions], key=lambda o: _nk(o.canon_entity_ref)))

    manifest = AdaptationManifest(format_version=1,adaptation_id=plan.adaptation_id,
        source=ManifestSource(promotion_id=canon_draft.promotion_id,chapter_id=canon_draft.source.chapter_id,chapter_sha256=canon_draft.source.chapter_sha256),
        pack=ManifestPack(id=plan.pack.id,version=plan.pack.version),
        bindings=binds,omissions=oms,game_only=gos)
    return MicroContentPack(pack=pack_dict,rooms=rooms_t,items=items_t,characters=chars_t,quests=quests_t,dialogues=dials_t,monsters=empty_t,shops=empty_t,manifest=manifest)


# ── Writer ─────────────────────────────────────────────────────────────────

def _pack_to_docs(pack: MicroContentPack) -> list[tuple[str, bytes]]:
    docs = [
        ("pack.json", _json_bytes(pack.pack)),
        ("rooms.json", _json_bytes(list(pack.rooms))),
        ("items.json", _json_bytes(list(pack.items))),
        ("characters.json", _json_bytes(list(pack.characters))),
        ("quests.json", _json_bytes(list(pack.quests))),
        ("dialogues.json", _json_bytes(list(pack.dialogues))),
        ("monsters.json", _json_bytes(list(pack.monsters))),
        ("shops.json", _json_bytes(list(pack.shops))),
        ("adaptation_manifest.json", _json_bytes(_manifest_dict(pack.manifest))),
    ]
    return docs


def _manifest_dict(m: AdaptationManifest) -> dict:
    return {"format_version":1,"adaptation_id":m.adaptation_id,
        "source":{"promotion_id":m.source.promotion_id,"chapter_id":m.source.chapter_id,"chapter_sha256":m.source.chapter_sha256},
        "pack":{"id":m.pack.id,"version":m.pack.version},
        "bindings":[{"game_kind":b.game_kind,"game_id":b.game_id,"canon_entity_ref":b.canon_entity_ref,"canon_claim_refs":list(b.canon_claim_refs),"adaptation_notes":b.adaptation_notes} for b in m.bindings],
        "omissions":[{"canon_entity_ref":o.canon_entity_ref,"reason":o.reason} for o in m.omissions],
        "game_only":[{"game_kind":g.game_kind,"game_id":g.game_id,"adaptation_notes":g.adaptation_notes} for g in m.game_only]}


def write_micro_pack(micro_pack: MicroContentPack, output_dir: str | Path) -> Path:
    output = Path(output_dir)

    # 1. Pre-validate documents (no temp dir yet)
    docs = _pack_to_docs(micro_pack)
    _validate_docs(docs)

    # 2. First lexists
    if os.path.lexists(str(output)):
        raise FileExistsError(f"output ({output}) 已存在，拒绝覆盖")
    parent = output.resolve().parent
    if not parent.is_dir():
        raise FileNotFoundError(f"父目录不存在：{parent}")

    # 3. Create temp dir
    tmp_dir = Path(tempfile.mkdtemp(dir=parent, prefix=".l2w_adaptation_"))
    try:
        for fname, payload in docs:
            (tmp_dir / fname).write_bytes(payload)

        load_content_pack(tmp_dir)

        with open(tmp_dir / "adaptation_manifest.json", "r", encoding="utf-8") as f:
            re_val = validate_adaptation_manifest_document(json.load(f))
        if re_val != micro_pack.manifest:
            raise AdaptationValidationError(("staged manifest 不一致",))

        # 4. Second lexists right before os.replace
        if os.path.lexists(str(output)):
            raise FileExistsError(f"output ({output}) 在发布前被创建，拒绝覆盖")

        os.replace(str(tmp_dir), str(output))

    except BaseException:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise

    return output.resolve()


def _validate_docs(docs: list[tuple[str, bytes]]) -> None:
    fnames = [d[0] for d in docs]
    if len(fnames) != len(set(fnames)):
        raise CompilationError(("documents 包含重复文件名",))
    if set(fnames) != _ALLOWED_FILES:
        missing = _ALLOWED_FILES - set(fnames)
        extra = set(fnames) - _ALLOWED_FILES
        msgs = []
        if missing: msgs.append(f"缺少文件：{sorted(missing)}")
        if extra: msgs.append(f"多余文件：{sorted(extra)}")
        raise CompilationError(tuple(msgs))
    for fname, payload in docs:
        p = PurePath(fname)
        if p.is_absolute() or p.as_posix().count("/") > 0 or p.as_posix().count("..") > 0:
            raise CompilationError((f"文件名包含路径逃逸：{fname}",))
        if not isinstance(payload, bytes):
            raise CompilationError((f"{fname} 的 payload 必须为 bytes",))


# ── Manifest validator ─────────────────────────────────────────────────────

def validate_adaptation_manifest_document(data: object) -> AdaptationManifest:
    issues: list[str] = []
    if not isinstance(data, dict):
        raise AdaptationValidationError(("根对象必须为 JSON 对象",))
    _unk(data, frozenset({"format_version","adaptation_id","source","pack","bindings","omissions","game_only"}), "根对象", issues)
    fv = data.get("format_version")
    if fv is None or isinstance(fv, bool) or not isinstance(fv, int) or fv != 1:
        issues.append("format_version 必须为 1")
    aid = _txt(data, "adaptation_id", "根对象", issues); _sid(aid, "adaptation_id", issues)

    rs = data.get("source")
    if not isinstance(rs, dict): issues.append("source 必须为对象")
    else:
        _unk(rs, frozenset({"promotion_id","chapter_id","chapter_sha256"}), "source", issues)
        m_pid = _txt(rs, "promotion_id", "source", issues); _sid(m_pid, "source.promotion_id", issues)
        m_cid = _txt(rs, "chapter_id", "source", issues)
        if m_cid and not _CHAPTER_ID_RE.fullmatch(m_cid): issues.append("source.chapter_id 必须匹配 chapter_NNNNNN")
        m_sha = rs.get("chapter_sha256")
        if not isinstance(m_sha, str) or not _SHA256_RE.fullmatch(m_sha): issues.append("source.chapter_sha256 必须为 64 位小写 hex")

    rpk = data.get("pack")
    if not isinstance(rpk, dict): issues.append("pack 必须为对象")
    else:
        _unk(rpk, frozenset({"id","version"}), "pack", issues)
        _sid(_txt(rpk,"id","pack",issues), "pack.id", issues); _txt(rpk,"version","pack",issues)

    # ── bindings：exactly 3 ──────────────────────────────────────────────
    bind_game_ids: set[str] = set()
    bind_cers: set[str] = set()
    if not isinstance(data.get("bindings"), list):
        issues.append("bindings 必须为数组")
    else:
        if len(data["bindings"]) != 3: issues.append(f"bindings 必须恰好 3 项，收到 {len(data['bindings'])}")
        allowed_kinds = frozenset({"room","character","item"})
        seen_kinds: set[str] = set()
        for bi, rb in enumerate(data["bindings"]):
            bloc = f"bindings[{bi}]"
            if not isinstance(rb, dict): issues.append(f"{bloc} 必须为对象"); continue
            _unk(rb, frozenset({"game_kind","game_id","canon_entity_ref","canon_claim_refs","adaptation_notes"}), bloc, issues)
            # game_kind: type-check before adding to set
            gk = rb.get("game_kind")
            if isinstance(gk, str) and gk in allowed_kinds:
                if gk in seen_kinds: issues.append(f"{bloc}.game_kind {gk!r} 重复")
                seen_kinds.add(gk)
            else:
                issues.append(f"{bloc}.game_kind 必须为 room|character|item，收到 {type(gk).__name__}")
            gid = _txt(rb, "game_id", bloc, issues); _sid(gid, f"{bloc}.game_id", issues)
            if gid in bind_game_ids: issues.append(f"{bloc}.game_id {gid!r} 重复")
            bind_game_ids.add(gid)
            cer = _txt(rb, "canon_entity_ref", bloc, issues); _sid(cer, f"{bloc}.canon_entity_ref", issues)
            if cer in bind_cers: issues.append(f"{bloc}.canon_entity_ref {cer!r} 重复")
            bind_cers.add(cer)
            _stra(rb.get("canon_claim_refs"), f"{bloc}.canon_claim_refs", issues)
            _txt(rb, "adaptation_notes", bloc, issues)

    # ── game_only：exactly 2 ─────────────────────────────────────────────
    go_game_ids: set[str] = set()
    if not isinstance(data.get("game_only"), list):
        issues.append("game_only 必须为数组")
    else:
        if len(data["game_only"]) != 2: issues.append(f"game_only 必须恰好 2 项，收到 {len(data['game_only'])}")
        allowed_go = frozenset({"quest","dialogue"})
        seen_go: set[str] = set()
        for gi, rg in enumerate(data["game_only"]):
            gloc = f"game_only[{gi}]"
            if not isinstance(rg, dict): issues.append(f"{gloc} 必须为对象"); continue
            _unk(rg, frozenset({"game_kind","game_id","adaptation_notes"}), gloc, issues)
            gk = rg.get("game_kind")
            if isinstance(gk, str) and gk in allowed_go:
                if gk in seen_go: issues.append(f"{gloc}.game_kind {gk!r} 重复")
                seen_go.add(gk)
            else:
                issues.append(f"{gloc}.game_kind 必须为 quest|dialogue，收到 {type(gk).__name__}")
            gid = _txt(rg, "game_id", gloc, issues); _sid(gid, f"{gloc}.game_id", issues)
            if gid in go_game_ids: issues.append(f"{gloc}.game_id {gid!r} 重复")
            go_game_ids.add(gid)
            _txt(rg, "adaptation_notes", gloc, issues)

    # Cross-set uniqueness: binding_game_ids ∩ go_game_ids
    overlap = bind_game_ids & go_game_ids
    if overlap:
        issues.append(f"bindings 与 game_only 的 game_id 重复：{sorted(overlap)}")

    # ── binding CERS ∩ omissions ─────────────────────────────────────────
    om_cers: set[str] = set()
    if not isinstance(data.get("omissions"), list):
        issues.append("omissions 必须为数组")
    else:
        for oi, ro in enumerate(data["omissions"]):
            oloc = f"omissions[{oi}]"
            if not isinstance(ro, dict): issues.append(f"{oloc} 必须为对象"); continue
            _unk(ro, frozenset({"canon_entity_ref","reason"}), oloc, issues)
            o_cer = _txt(ro, "canon_entity_ref", oloc, issues); _sid(o_cer, f"{oloc}.canon_entity_ref", issues)
            if o_cer in om_cers: issues.append(f"{oloc}.canon_entity_ref 重复"); continue
            om_cers.add(o_cer)
            _txt(ro, "reason", oloc, issues)

    bind_om_overlap = bind_cers & om_cers
    if bind_om_overlap:
        issues.append(f"bindings 与 omissions 的 canon_entity_ref 重复：{sorted(bind_om_overlap)}")

    if issues: raise AdaptationValidationError(tuple(issues))

    s = data["source"]; pk = data["pack"]
    source = ManifestSource(promotion_id=s.get("promotion_id",""),chapter_id=s.get("chapter_id",""),chapter_sha256=s.get("chapter_sha256",""))
    mp = ManifestPack(id=pk.get("id",""),version=pk.get("version",""))
    bindings = tuple(sorted([
        ManifestBinding(game_kind=b.get("game_kind",""),game_id=b.get("game_id",""),
            canon_entity_ref=b.get("canon_entity_ref",""),
            canon_claim_refs=_stra(b.get("canon_claim_refs"),f"bindings[{i}].canon_claim_refs",[]),
            adaptation_notes=b.get("adaptation_notes",""))
        for i,b in enumerate(data.get("bindings",[]))
    ], key=lambda b: (b.game_kind,_nk(b.game_id))))
    game_only = tuple(sorted([
        ManifestGameOnly(game_kind=g.get("game_kind",""),game_id=g.get("game_id",""),adaptation_notes=g.get("adaptation_notes",""))
        for g in data.get("game_only",[])
    ], key=lambda g: (g.game_kind,_nk(g.game_id))))
    omissions = tuple(sorted([
        ManifestOmission(canon_entity_ref=o.get("canon_entity_ref",""),reason=o.get("reason",""))
        for o in data.get("omissions",[])
    ], key=lambda o: _nk(o.canon_entity_ref)))
    return AdaptationManifest(format_version=1,adaptation_id=data.get("adaptation_id",""),source=source,pack=mp,bindings=bindings,omissions=omissions,game_only=game_only)


# ── CLI ────────────────────────────────────────────────────────────────────

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile micro content pack from canon draft + adaptation plan.")
    parser.add_argument("--canon-draft", required=True, type=str)
    parser.add_argument("--adaptation-plan", required=True, type=str)
    parser.add_argument("--output-dir", required=True, type=str)
    args = parser.parse_args(argv)

    try:
        with open(args.canon_draft, "r", encoding="utf-8") as f:
            canon_draft = validate_canon_draft_document(json.load(f))
        with open(args.adaptation_plan, "r", encoding="utf-8") as f:
            plan = validate_adaptation_plan(json.load(f))
        pack = compile_micro_pack(canon_draft, plan)
        write_micro_pack(pack, args.output_dir)
    except json.JSONDecodeError as exc:
        print(f"JSON 解析错误：{exc}", file=sys.stderr); return 1
    except UnicodeDecodeError as exc:
        print(f"UTF-8 解码错误：{exc}", file=sys.stderr); return 1
    except CanonDraftValidationError as exc:
        print(f"CanonDraft 错误：{exc}", file=sys.stderr); return 1
    except AdaptationValidationError as exc:
        print(f"Adaptation 错误：{exc}", file=sys.stderr); return 1
    except CompilationError as exc:
        print(f"编译错误：{exc}", file=sys.stderr); return 1
    except ContentValidationError as exc:
        print(f"内容校验错误：{exc}", file=sys.stderr); return 1
    except (FileExistsError, FileNotFoundError, OSError) as exc:
        print(f"I/O 错误：{exc}", file=sys.stderr); return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
