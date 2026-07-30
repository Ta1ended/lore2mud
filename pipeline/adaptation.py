"""Validate adaptation plans, compile canon drafts to micro content packs.

Public API::

    validate_adaptation_plan(data) -> AdaptationPlan
    compile_micro_pack(canon_draft, plan) -> MicroContentPack
    write_micro_pack(micro_pack, output_dir) -> Path
    validate_adaptation_manifest_document(data) -> AdaptationManifest
    main(argv) -> int
"""

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
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from pipeline.canon import CanonDraft, validate_canon_draft_document

# ── regex ──────────────────────────────────────────────────────────────────

_STABLE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_CHAPTER_ID_RE = re.compile(r"^chapter_[0-9]{6}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# ── exceptions ─────────────────────────────────────────────────────────────


class AdaptationValidationError(ValueError):
    """Plan or manifest structural validation failure."""

    def __init__(self, issues: tuple[str, ...]) -> None:
        self.issues = issues
        super().__init__("\n".join(f"- {i}" for i in issues))


class CompilationError(ValueError):
    """Binding, coverage, or cross-object validation failure."""

    def __init__(self, issues: tuple[str, ...]) -> None:
        self.issues = issues
        super().__init__("\n".join(f"- {i}" for i in issues))


# ── AdaptationPlan data models ──────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class PlayerSub:
    max_hp: int = 20
    attack: int = 5
    defense: int = 1
    inventory_capacity: int = 20
    coins: int = 0


@dataclass(frozen=True, slots=True)
class PackProfile:
    id: str
    name: str
    version: str
    start_room_id: str
    player: PlayerSub


@dataclass(frozen=True, slots=True)
class RoomAdaptation:
    canon_entity_ref: str
    game_id: str
    name: str
    description: str
    canon_claim_refs: tuple[str, ...]
    adaptation_notes: str


@dataclass(frozen=True, slots=True)
class CharacterAdaptation:
    canon_entity_ref: str
    game_id: str
    name: str
    description: str
    canon_claim_refs: tuple[str, ...]
    adaptation_notes: str


@dataclass(frozen=True, slots=True)
class ItemAdaptation:
    canon_entity_ref: str
    game_id: str
    name: str
    description: str
    canon_claim_refs: tuple[str, ...]
    adaptation_notes: str


@dataclass(frozen=True, slots=True)
class QuestAdaptation:
    game_id: str
    kind: Literal["collect_item"]
    name: str
    description: str
    target_item_id: str
    required_quantity: int
    reward_experience: int
    adaptation_notes: str


@dataclass(frozen=True, slots=True)
class DialogueOptionDef:
    id: str
    text: str
    next_node_id: str | None


@dataclass(frozen=True, slots=True)
class DialogueNodeDef:
    id: str
    text: str
    options: tuple[DialogueOptionDef, ...]


@dataclass(frozen=True, slots=True)
class DialogueAdaptation:
    game_id: str
    character_id: str
    start_node_id: str
    nodes: tuple[DialogueNodeDef, ...]
    adaptation_notes: str


@dataclass(frozen=True, slots=True)
class OmissionEntry:
    canon_entity_ref: str
    reason: str


@dataclass(frozen=True, slots=True)
class AdaptationPlan:
    format_version: int
    adaptation_id: str
    source_promotion_id: str
    source_chapter: str
    pack: PackProfile
    room: RoomAdaptation
    character: CharacterAdaptation
    item: ItemAdaptation
    quest: QuestAdaptation
    dialogue: DialogueAdaptation
    omissions: tuple[OmissionEntry, ...]


# ── AdaptationManifest data models ──────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ManifestSource:
    promotion_id: str
    chapter_id: str
    chapter_sha256: str


@dataclass(frozen=True, slots=True)
class ManifestPack:
    id: str
    version: str


@dataclass(frozen=True, slots=True)
class ManifestBinding:
    game_kind: str
    game_id: str
    canon_entity_ref: str
    canon_claim_refs: tuple[str, ...]
    adaptation_notes: str


@dataclass(frozen=True, slots=True)
class ManifestOmission:
    canon_entity_ref: str
    reason: str


@dataclass(frozen=True, slots=True)
class ManifestGameOnly:
    game_kind: str
    game_id: str
    adaptation_notes: str


@dataclass(frozen=True, slots=True)
class AdaptationManifest:
    format_version: int
    adaptation_id: str
    source: ManifestSource
    pack: ManifestPack
    bindings: tuple[ManifestBinding, ...]
    omissions: tuple[ManifestOmission, ...]
    game_only: tuple[ManifestGameOnly, ...]


# ── MicroContentPack ────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class CompiledDocument:
    filename: str
    payload: bytes


@dataclass(frozen=True, slots=True)
class MicroContentPack:
    documents: tuple[CompiledDocument, ...]
    manifest: AdaptationManifest


# ── internal helpers ────────────────────────────────────────────────────────


def _norm_key(s: str) -> str:
    return unicodedata.normalize("NFKC", s).casefold().strip()


def _text(obj: dict, key: str, loc: str, issues: list) -> str:
    v = obj.get(key)
    if not isinstance(v, str) or not v.strip():
        issues.append(f"{loc}.{key} 必须是非空字符串")
        return ""
    return v


def _int(obj: dict, key: str, loc: str, issues: list,
         *, minimum: int = 0, default: int = 0) -> int:
    if key not in obj:
        issues.append(f"{loc}.{key} 是必填字段")
        return default
    v = obj.get(key)
    if isinstance(v, bool) or not isinstance(v, int) or v < minimum:
        issues.append(f"{loc}.{key} 必须是 >= {minimum} 的整数")
        return default
    return v


def _stable(s: str, loc: str, issues: list) -> None:
    if s and not _STABLE_ID_RE.fullmatch(s):
        issues.append(f"{loc} 必须匹配稳定 ID 格式")


def _unknown(obj: dict, allowed: frozenset, loc: str, issues: list) -> None:
    for k in sorted(set(obj) - allowed):
        issues.append(f"{loc} 包含未知字段：{k!r}")


def _str_array(raw: Any, loc: str, issues: list) -> tuple[str, ...]:
    if not isinstance(raw, list):
        issues.append(f"{loc} 必须是数组")
        return ()
    seen: set[str] = set()
    result: list[str] = []
    for vi, v in enumerate(raw):
        if not isinstance(v, str) or not v.strip():
            issues.append(f"{loc}[{vi}] 必须是非空字符串")
            continue
        _stable(v, f"{loc}[{vi}]", issues)
        nk = _norm_key(v)
        if nk in seen:
            issues.append(f"{loc}[{vi}] 存在规范化后重复：{v!r}")
        seen.add(nk)
        result.append(v)
    return tuple(result)


# ── structural: validate_adaptation_plan ────────────────────────────────────


def validate_adaptation_plan(data: object) -> AdaptationPlan:
    issues: list[str] = []

    if not isinstance(data, dict):
        raise AdaptationValidationError(("根对象必须是 JSON 对象",))

    allowed = frozenset({
        "format_version", "adaptation_id", "source_promotion_id",
        "source_chapter", "pack", "room", "character", "item",
        "quest", "dialogue", "omissions",
    })
    _unknown(data, allowed, "根对象", issues)

    # format_version, ids, source
    fv = data.get("format_version")
    if fv is None or isinstance(fv, bool) or not isinstance(fv, int) or fv != 1:
        issues.append("format_version 必须是 1")
    aid = _text(data, "adaptation_id", "根对象", issues)
    _stable(aid, "adaptation_id", issues)
    spi = _text(data, "source_promotion_id", "根对象", issues)
    _stable(spi, "source_promotion_id", issues)
    sc = _text(data, "source_chapter", "根对象", issues)
    if sc and not _CHAPTER_ID_RE.fullmatch(sc):
        issues.append(f"source_chapter 必须匹配 ^chapter_[0-9]{{6}}$")

    # pack
    rp = data.get("pack")
    if not isinstance(rp, dict):
        issues.append("pack 必须是对象")
    else:
        _unknown(rp, frozenset({"id", "name", "version", "start_room_id", "player"}), "pack", issues)

    # room / character / item
    for kind in ("room", "character", "item"):
        rv = data.get(kind)
        if not isinstance(rv, dict):
            issues.append(f"{kind} 必须是对象")
            continue
        _unknown(rv, frozenset({
            "canon_entity_ref", "game_id", "name", "description",
            "canon_claim_refs", "adaptation_notes",
        }), kind, issues)

    # quest
    rq = data.get("quest")
    if not isinstance(rq, dict):
        issues.append("quest 必须是对象")
    else:
        _unknown(rq, frozenset({
            "game_id", "kind", "name", "description", "target_item_id",
            "required_quantity", "reward_experience", "adaptation_notes",
        }), "quest", issues)

    # dialogue
    rd = data.get("dialogue")
    if not isinstance(rd, dict):
        issues.append("dialogue 必须是对象")
    else:
        _unknown(rd, frozenset({
            "game_id", "character_id", "start_node_id", "nodes", "adaptation_notes",
        }), "dialogue", issues)

    # omissions
    rom = data.get("omissions")
    if not isinstance(rom, list):
        issues.append("omissions 必须是数组")

    if issues:
        raise AdaptationValidationError(tuple(issues))

    # ── parse pack ──────────────────────────────────────────────────────────
    pid = _text(rp, "id", "pack", issues)
    _stable(pid, "pack.id", issues)
    pname = _text(rp, "name", "pack", issues)
    pver = _text(rp, "version", "pack", issues)
    srid = _text(rp, "start_room_id", "pack", issues)
    _stable(srid, "pack.start_room_id", issues)

    raw_ply = rp.get("player")
    if not isinstance(raw_ply, dict):
        issues.append("pack.player 必须是对象")
        player = PlayerSub()
    else:
        _unknown(raw_ply, frozenset({"max_hp", "attack", "defense", "inventory_capacity", "coins"}), "pack.player", issues)
        mhp = _int(raw_ply, "max_hp", "pack.player", issues, minimum=1, default=20)
        atk = _int(raw_ply, "attack", "pack.player", issues, minimum=1, default=5)
        dfs = _int(raw_ply, "defense", "pack.player", issues, minimum=0, default=1)
        ic = _int(raw_ply, "inventory_capacity", "pack.player", issues, minimum=1, default=20)
        coins = _int(raw_ply, "coins", "pack.player", issues, minimum=0, default=0)
        player = PlayerSub(max_hp=mhp, attack=atk, defense=dfs, inventory_capacity=ic, coins=coins)

    pack = PackProfile(id=pid, name=pname, version=pver, start_room_id=srid, player=player)

    # ── parse room ──────────────────────────────────────────────────────────
    rr = data["room"]
    r_cer = _text(rr, "canon_entity_ref", "room", issues)
    _stable(r_cer, "room.canon_entity_ref", issues)
    r_gid = _text(rr, "game_id", "room", issues)
    _stable(r_gid, "room.game_id", issues)
    r_name = _text(rr, "name", "room", issues)
    r_desc = _text(rr, "description", "room", issues)
    r_an = _text(rr, "adaptation_notes", "room", issues)
    r_ccr = _str_array(rr.get("canon_claim_refs"), "room.canon_claim_refs", issues)
    room = RoomAdaptation(canon_entity_ref=r_cer, game_id=r_gid, name=r_name,
                          description=r_desc, adaptation_notes=r_an,
                          canon_claim_refs=r_ccr)

    # ── parse character ─────────────────────────────────────────────────────
    rc = data["character"]
    c_cer = _text(rc, "canon_entity_ref", "character", issues)
    _stable(c_cer, "character.canon_entity_ref", issues)
    c_gid = _text(rc, "game_id", "character", issues)
    _stable(c_gid, "character.game_id", issues)
    c_name = _text(rc, "name", "character", issues)
    c_desc = _text(rc, "description", "character", issues)
    c_an = _text(rc, "adaptation_notes", "character", issues)
    c_ccr = _str_array(rc.get("canon_claim_refs"), "character.canon_claim_refs", issues)
    character = CharacterAdaptation(canon_entity_ref=c_cer, game_id=c_gid,
                                    name=c_name, description=c_desc,
                                    adaptation_notes=c_an, canon_claim_refs=c_ccr)

    # ── parse item ──────────────────────────────────────────────────────────
    ri = data["item"]
    i_cer = _text(ri, "canon_entity_ref", "item", issues)
    _stable(i_cer, "item.canon_entity_ref", issues)
    i_gid = _text(ri, "game_id", "item", issues)
    _stable(i_gid, "item.game_id", issues)
    i_name = _text(ri, "name", "item", issues)
    i_desc = _text(ri, "description", "item", issues)
    i_an = _text(ri, "adaptation_notes", "item", issues)
    i_ccr = _str_array(ri.get("canon_claim_refs"), "item.canon_claim_refs", issues)
    item = ItemAdaptation(canon_entity_ref=i_cer, game_id=i_gid, name=i_name,
                          description=i_desc, adaptation_notes=i_an,
                          canon_claim_refs=i_ccr)

    # ── parse quest ─────────────────────────────────────────────────────────
    ra = data["quest"]
    q_gid = _text(ra, "game_id", "quest", issues)
    _stable(q_gid, "quest.game_id", issues)
    q_kind = ra.get("kind")
    if q_kind != "collect_item":
        issues.append("quest.kind 必须为 collect_item")
    q_name = _text(ra, "name", "quest", issues)
    q_desc = _text(ra, "description", "quest", issues)
    q_tid = _text(ra, "target_item_id", "quest", issues)
    _stable(q_tid, "quest.target_item_id", issues)
    q_rq = _int(ra, "required_quantity", "quest", issues, minimum=1, default=1)
    q_re = _int(ra, "reward_experience", "quest", issues, minimum=1, default=10)
    q_an = _text(ra, "adaptation_notes", "quest", issues)
    quest = QuestAdaptation(game_id=q_gid, kind="collect_item", name=q_name,
                            description=q_desc, target_item_id=q_tid,
                            required_quantity=q_rq, reward_experience=q_re,
                            adaptation_notes=q_an)

    # ── parse dialogue ──────────────────────────────────────────────────────
    rv = data["dialogue"]
    d_gid = _text(rv, "game_id", "dialogue", issues)
    _stable(d_gid, "dialogue.game_id", issues)
    d_cid = _text(rv, "character_id", "dialogue", issues)
    _stable(d_cid, "dialogue.character_id", issues)
    d_start = _text(rv, "start_node_id", "dialogue", issues)
    d_an = _text(rv, "adaptation_notes", "dialogue", issues)

    raw_nodes = rv.get("nodes")
    if not isinstance(raw_nodes, list) or len(raw_nodes) == 0:
        issues.append("dialogue.nodes 必须是非空数组")
        raw_nodes = []
    nids: set[str] = set()
    all_next: set[str] = set()
    parsed_nodes: list[DialogueNodeDef] = []
    for ni, rn in enumerate(raw_nodes):
        nloc = f"dialogue.nodes[{ni}]"
        if not isinstance(rn, dict):
            issues.append(f"{nloc} 必须是对象")
            continue
        _unknown(rn, frozenset({"id", "text", "options"}), nloc, issues)
        nid = _text(rn, "id", nloc, issues)
        _stable(nid, f"{nloc}.id", issues)
        if nid in nids:
            issues.append(f"{nloc}.id 重复：{nid}")
        nids.add(nid)
        ntext = _text(rn, "text", nloc, issues)
        raw_opts = rn.get("options")
        if not isinstance(raw_opts, list) or len(raw_opts) == 0:
            issues.append(f"{nloc}.options 必须是非空数组")
            continue
        oids: set[str] = set()
        parsed_opts: list[DialogueOptionDef] = []
        for oi, ro in enumerate(raw_opts):
            oloc = f"{nloc}.options[{oi}]"
            if not isinstance(ro, dict):
                issues.append(f"{oloc} 必须是对象")
                continue
            _unknown(ro, frozenset({"id", "text", "next_node_id", "effects"}), oloc, issues)
            oid = _text(ro, "id", oloc, issues)
            if oid in oids:
                issues.append(f"{oloc}.id 重复：{oid}")
            oids.add(oid)
            otext = _text(ro, "text", oloc, issues)
            rnid = ro.get("next_node_id")
            if rnid is not None and (not isinstance(rnid, str) or not rnid.strip()):
                issues.append(f"{oloc}.next_node_id 必须是非空字符串或 null")
            if rnid is not None:
                all_next.add(rnid)
            raw_eff = ro.get("effects")
            if not isinstance(raw_eff, list) or len(raw_eff) > 0:
                issues.append(f"{oloc}.effects 必须为空数组（[]）")
            parsed_opts.append(DialogueOptionDef(id=oid, text=otext, next_node_id=rnid))
        parsed_nodes.append(DialogueNodeDef(id=nid, text=ntext, options=tuple(parsed_opts)))

    if d_start not in nids:
        issues.append(f"start_node_id {d_start!r} 不在 nodes 中")
    for nid_ref in sorted(all_next - nids):
        issues.append(f"next_node_id {nid_ref!r} 引用了不存在的节点")

    dialogue = DialogueAdaptation(
        game_id=d_gid, character_id=d_cid, start_node_id=d_start,
        nodes=tuple(parsed_nodes), adaptation_notes=d_an,
    )

    # ── parse omissions ────────────────────────────────────────────────────
    om_cers: set[str] = set()
    parsed_oms: list[OmissionEntry] = []
    for oi, ro in enumerate(data["omissions"]):
        oloc = f"omissions[{oi}]"
        if not isinstance(ro, dict):
            issues.append(f"{oloc} 必须是对象")
            continue
        _unknown(ro, frozenset({"canon_entity_ref", "reason"}), oloc, issues)
        o_cer = _text(ro, "canon_entity_ref", oloc, issues)
        _stable(o_cer, f"{oloc}.canon_entity_ref", issues)
        if o_cer in om_cers:
            issues.append(f"{oloc}.canon_entity_ref 重复：{o_cer}")
        om_cers.add(o_cer)
        o_reason = _text(ro, "reason", oloc, issues)
        parsed_oms.append(OmissionEntry(canon_entity_ref=o_cer, reason=o_reason))

    if issues:
        raise AdaptationValidationError(tuple(issues))

    return AdaptationPlan(
        format_version=1, adaptation_id=aid,
        source_promotion_id=spi, source_chapter=sc,
        pack=pack, room=room, character=character, item=item,
        quest=quest, dialogue=dialogue,
        omissions=tuple(parsed_oms),
    )


# ── compile_micro_pack ──────────────────────────────────────────────────────


def _canon_entity_map(draft: CanonDraft) -> dict[str, Any]:
    return {e.entity_id: e for e in draft.entities}


def compile_micro_pack(
    canon_draft: CanonDraft,
    plan: AdaptationPlan,
) -> MicroContentPack:
    """Deterministically compile a MicroContentPack from a CanonDraft and
    AdaptationPlan.  All binding, coverage, and reference validation happens
    here."""

    issues: list[str] = []
    entities = _canon_entity_map(canon_draft)

    # 1. Source binding
    if plan.source_promotion_id != canon_draft.promotion_id:
        issues.append(
            f"source_promotion_id ({plan.source_promotion_id}) 必须等于 "
            f"canon_draft.promotion_id ({canon_draft.promotion_id})"
        )
    if plan.source_chapter != canon_draft.source.chapter_id:
        issues.append(
            f"source_chapter ({plan.source_chapter}) 必须等于 "
            f"canon_draft.source.chapter_id ({canon_draft.source.chapter_id})"
        )

    # 2. Build adapted set + coverage validation
    adapted: dict[str, str] = {}  # canon_entity_ref → kind
    claim_refs: dict[str, list[str]] = {}  # canon_entity_ref → list of claim_refs

    for kind, entry in [("room", plan.room), ("character", plan.character), ("item", plan.item)]:
        cer = entry.canon_entity_ref
        if cer in adapted:
            issues.append(f"{kind}.canon_entity_ref {cer!r} 已被 {adapted[cer]} 使用")
        adapted[cer] = kind
        claim_refs[cer] = list(entry.canon_claim_refs)

        if cer not in entities:
            issues.append(f"{kind}.canon_entity_ref {cer!r} 不存在于 CanonDraft 中")
            continue
        entity = entities[cer]
        expected_type = {"room": "location", "character": "character", "item": "item"}[kind]
        if entity.entity_type != expected_type:
            issues.append(
                f"{kind}.canon_entity_ref {cer!r} 类型为 {entity.entity_type}，"
                f"期望 {expected_type}"
            )

        # validate canon_claim_refs belong to this entity
        entity_claim_ids = {c.claim_id for c in entity.claims}
        for cref in entry.canon_claim_refs:
            if cref not in entity_claim_ids:
                issues.append(
                    f"{kind}.canon_claim_refs 中的 {cref!r} 不属"
                    f"于 entity {cer!r}"
                )

    # 3. Omissions validation
    omitted: set[str] = set()
    for om in plan.omissions:
        cer = om.canon_entity_ref
        if cer not in entities:
            issues.append(f"omissions 引用了不存在的 entity {cer!r}")
            continue
        if cer in adapted:
            issues.append(f"omissions 引用了已适配的 entity {cer!r}")
        omitted.add(cer)

    # 4. Exact coverage
    all_entity_ids = set(entities.keys())
    covered = set(adapted.keys()) | omitted
    extra = covered - all_entity_ids
    missing = all_entity_ids - covered
    if extra or missing:
        msgs = []
        if missing:
            msgs.append(f"以下 entity 未被 adaptations 或 omissions 覆盖：{sorted(missing)}")
        if extra:
            msgs.append(f"adaptations/omissions 引用了不存在的 entity：{sorted(extra)}")
        issues.extend(msgs)

    # 5. Cross-type game ID uniqueness
    all_gids: set[str] = set()
    gid_source: dict[str, str] = {}
    for kind, entry in [("room", plan.room), ("character", plan.character), ("item", plan.item),
                        ("quest", plan.quest), ("dialogue", plan.dialogue)]:
        gid = entry.game_id
        if gid in all_gids:
            issues.append(f"game_id {gid!r} 在 {kind} 中与 {gid_source.get(gid)} 重复")
        all_gids.add(gid)
        gid_source[gid] = kind

    # 6. Fixed references between plan objects
    if plan.pack.start_room_id != plan.room.game_id:
        issues.append(
            f"pack.start_room_id ({plan.pack.start_room_id}) 必须等于 "
            f"room.game_id ({plan.room.game_id})"
        )
    if plan.dialogue.character_id != plan.character.game_id:
        issues.append(
            f"dialogue.character_id ({plan.dialogue.character_id}) 必须等于 "
            f"character.game_id ({plan.character.game_id})"
        )
    if plan.quest.target_item_id != plan.item.game_id:
        issues.append(
            f"quest.target_item_id ({plan.quest.target_item_id}) 必须等于 "
            f"item.game_id ({plan.item.game_id})"
        )
    if plan.quest.kind != "collect_item":
        issues.append("quest.kind 必须是 collect_item")
    if plan.quest.required_quantity != 1:
        issues.append("quest.required_quantity 必须为 1")

    if issues:
        raise CompilationError(tuple(issues))

    # ── Build output documents ──────────────────────────────────────────────
    scid = canon_draft.source.chapter_id
    source_chapters = (scid,)

    def _json_bytes(data: Any) -> bytes:
        return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"

    def _ensure_stable(s: str) -> str:
        return s

    # ── pack.json ───────────────────────────────────────────────────────────
    pack_json = {
        "id": plan.pack.id,
        "name": plan.pack.name,
        "version": plan.pack.version,
        "start_room_id": plan.pack.start_room_id,
        "player": {
            "max_hp": plan.pack.player.max_hp,
            "attack": plan.pack.player.attack,
            "defense": plan.pack.player.defense,
            "inventory_capacity": plan.pack.player.inventory_capacity,
            "coins": plan.pack.player.coins,
        },
        "extensions": {
            "canon_provider": {
                "kind": "adaptation_manifest",
                "format_version": 1,
                "path": "adaptation_manifest.json",
            },
        },
    }

    # ── rooms.json ──────────────────────────────────────────────────────────
    rooms_json = [{
        "id": plan.room.game_id,
        "name": plan.room.name,
        "description": plan.room.description,
        "exits": {},
        "item_stacks": [{"item_id": plan.item.game_id, "quantity": 1}],
        "monster_ids": [],
        "canon_ref": {"entity_id": plan.room.canon_entity_ref, "source_chapters": list(source_chapters)},
        "adaptation_notes": plan.room.adaptation_notes,
    }]

    # ── items.json ──────────────────────────────────────────────────────────
    items_json = [{
        "id": plan.item.game_id,
        "name": plan.item.name,
        "description": plan.item.description,
        "stack_limit": 1,
        "canon_ref": {"entity_id": plan.item.canon_entity_ref, "source_chapters": list(source_chapters)},
        "adaptation_notes": plan.item.adaptation_notes,
    }]

    # ── characters.json ─────────────────────────────────────────────────────
    characters_json = [{
        "id": plan.character.game_id,
        "name": plan.character.name,
        "description": plan.character.description,
        "room_id": plan.pack.start_room_id,
        "canon_ref": {"entity_id": plan.character.canon_entity_ref, "source_chapters": list(source_chapters)},
        "adaptation_notes": plan.character.adaptation_notes,
    }]

    # ── quests.json ─────────────────────────────────────────────────────────
    # Note: canon_ref completely omitted per contract
    quests_json = [{
        "id": plan.quest.game_id,
        "kind": "collect_item",
        "name": plan.quest.name,
        "description": plan.quest.description,
        "trigger_room_id": plan.pack.start_room_id,
        "target_item_id": plan.quest.target_item_id,
        "required_quantity": 1,
        "reward_experience": plan.quest.reward_experience,
        "adaptation_notes": plan.quest.adaptation_notes,
    }]

    # ── dialogues.json ──────────────────────────────────────────────────────
    # Note: canon_ref completely omitted per contract
    dialogue_nodes = []
    for node in plan.dialogue.nodes:
        options_out = []
        for opt in node.options:
            opt_out = {
                "id": opt.id,
                "text": opt.text,
                "next_node_id": opt.next_node_id,
                "effects": [],
            }
            options_out.append(opt_out)
        dialogue_nodes.append({
            "id": node.id,
            "text": node.text,
            "options": options_out,
        })

    dialogues_json = [{
        "id": plan.dialogue.game_id,
        "character_id": plan.dialogue.character_id,
        "start_node_id": plan.dialogue.start_node_id,
        "nodes": dialogue_nodes,
        "adaptation_notes": plan.dialogue.adaptation_notes,
    }]

    # ── monsters.json / shops.json ──────────────────────────────────────────
    empty_list = []

    # ── Manifest ────────────────────────────────────────────────────────────
    def _make_binding(kind: str, entry: Any) -> ManifestBinding:
        return ManifestBinding(
            game_kind=kind, game_id=entry.game_id,
            canon_entity_ref=entry.canon_entity_ref,
            canon_claim_refs=tuple(sorted(entry.canon_claim_refs, key=lambda x: _norm_key(x))),
            adaptation_notes=entry.adaptation_notes,
        )

    bindings = [
        _make_binding("room", plan.room),
        _make_binding("character", plan.character),
        _make_binding("item", plan.item),
    ]

    game_only = [
        ManifestGameOnly(
            game_kind="quest", game_id=plan.quest.game_id,
            adaptation_notes=plan.quest.adaptation_notes,
        ),
        ManifestGameOnly(
            game_kind="dialogue", game_id=plan.dialogue.game_id,
            adaptation_notes=plan.dialogue.adaptation_notes,
        ),
    ]

    manifest_omissions = tuple(
        ManifestOmission(canon_entity_ref=o.canon_entity_ref, reason=o.reason)
        for o in plan.omissions
    )

    manifest = AdaptationManifest(
        format_version=1,
        adaptation_id=plan.adaptation_id,
        source=ManifestSource(
            promotion_id=canon_draft.promotion_id,
            chapter_id=canon_draft.source.chapter_id,
            chapter_sha256=canon_draft.source.chapter_sha256,
        ),
        pack=ManifestPack(id=plan.pack.id, version=plan.pack.version),
        bindings=tuple(sorted(bindings, key=lambda b: (b.game_kind, _norm_key(b.game_id)))),
        omissions=tuple(sorted(manifest_omissions, key=lambda o: _norm_key(o.canon_entity_ref))),
        game_only=tuple(sorted(game_only, key=lambda g: (g.game_kind, _norm_key(g.game_id)))),
    )

    # Serialize manifest for the output
    manifest_json = {
        "format_version": 1,
        "adaptation_id": manifest.adaptation_id,
        "source": {
            "promotion_id": manifest.source.promotion_id,
            "chapter_id": manifest.source.chapter_id,
            "chapter_sha256": manifest.source.chapter_sha256,
        },
        "pack": {"id": manifest.pack.id, "version": manifest.pack.version},
        "bindings": [
            {
                "game_kind": b.game_kind,
                "game_id": b.game_id,
                "canon_entity_ref": b.canon_entity_ref,
                "canon_claim_refs": list(b.canon_claim_refs),
                "adaptation_notes": b.adaptation_notes,
            }
            for b in manifest.bindings
        ],
        "omissions": [
            {"canon_entity_ref": o.canon_entity_ref, "reason": o.reason}
            for o in manifest.omissions
        ],
        "game_only": [
            {"game_kind": g.game_kind, "game_id": g.game_id, "adaptation_notes": g.adaptation_notes}
            for g in manifest.game_only
        ],
    }

    documents: list[CompiledDocument] = [
        CompiledDocument("pack.json", _json_bytes(pack_json)),
        CompiledDocument("rooms.json", _json_bytes(rooms_json)),
        CompiledDocument("items.json", _json_bytes(items_json)),
        CompiledDocument("characters.json", _json_bytes(characters_json)),
        CompiledDocument("quests.json", _json_bytes(quests_json)),
        CompiledDocument("dialogues.json", _json_bytes(dialogues_json)),
        CompiledDocument("monsters.json", _json_bytes(empty_list)),
        CompiledDocument("shops.json", _json_bytes(empty_list)),
        CompiledDocument("adaptation_manifest.json", _json_bytes(manifest_json)),
    ]

    # Basic consistency: 9 documents, no duplicate filenames
    fns = [d.filename for d in documents]
    if len(fns) != len(set(fns)):
        raise CompilationError(("compiled documents 包含重复文件名",))

    pack = MicroContentPack(documents=tuple(documents), manifest=manifest)
    return pack


# ── write_micro_pack ────────────────────────────────────────────────────────


def write_micro_pack(
    micro_pack: MicroContentPack,
    output_dir: str | Path,
) -> Path:
    """Write a MicroContentPack to a directory atomically.

    Raises OSError on I/O failure, ContentValidationError if the staged pack
    does not load, or AdaptationValidationError if the staged manifest does
    not re-validate.
    """

    output = Path(output_dir).resolve()

    # 1. Verify parent exists
    parent = output.parent
    if not parent.is_dir():
        raise FileNotFoundError(f"output 父目录不存在：{parent}")

    # 2. Reject if output already exists
    if os.path.lexists(str(output)):
        raise FileExistsError(f"output_dir 已存在（拒绝覆盖）：{output}")

    # 3. Create temp dir
    tmp_dir = Path(tempfile.mkdtemp(
        dir=parent, prefix=".l2w_adaptation_",
    ))
    try:
        # 4. Write all documents
        for doc in micro_pack.documents:
            dst = tmp_dir / doc.filename
            with open(dst, "wb") as f:
                f.write(doc.payload)
                f.flush()
                os.fsync(f.fileno())

        # 5. Validate with existing loader
        from lore2mud.content.loader import load_content_pack
        load_content_pack(tmp_dir)

        # 6. Re-validate manifest
        manifest_path = tmp_dir / "adaptation_manifest.json"
        with open(manifest_path, "r", encoding="utf-8") as f:
            raw_manifest = json.load(f)
        re_validated = validate_adaptation_manifest_document(raw_manifest)

        # Manifest must match
        if re_validated != micro_pack.manifest:
            raise AdaptationValidationError((
                "staged manifest 与 micro_pack.manifest 不一致",
            ))

        # 7. Atomic publish
        os.replace(str(tmp_dir), str(output))

    except BaseException:
        # Clean up temp dir on any failure
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise

    return output


# ── validate_adaptation_manifest_document ────────────────────────────────────


def validate_adaptation_manifest_document(data: object) -> AdaptationManifest:
    issues: list[str] = []
    if not isinstance(data, dict):
        raise AdaptationValidationError(("根对象必须是 JSON 对象",))

    allowed = frozenset({
        "format_version", "adaptation_id", "source",
        "pack", "bindings", "omissions", "game_only",
    })
    _unknown(data, allowed, "根对象", issues)

    fv = data.get("format_version")
    if fv is None or isinstance(fv, bool) or not isinstance(fv, int) or fv != 1:
        issues.append("format_version 必须是 1")

    aid = _text(data, "adaptation_id", "根对象", issues)
    _stable(aid, "adaptation_id", issues)

    raw_source = data.get("source")
    if not isinstance(raw_source, dict):
        issues.append("source 必须是对象")
    else:
        _unknown(raw_source, frozenset({"promotion_id", "chapter_id", "chapter_sha256"}), "source", issues)
        m_pid = _text(raw_source, "promotion_id", "source", issues)
        _stable(m_pid, "source.promotion_id", issues)
        m_cid = _text(raw_source, "chapter_id", "source", issues)
        if m_cid and not _CHAPTER_ID_RE.fullmatch(m_cid):
            issues.append("source.chapter_id 必须匹配 chapter_NNNNNN")
        m_sha = raw_source.get("chapter_sha256")
        if not isinstance(m_sha, str) or not _SHA256_RE.fullmatch(m_sha):
            issues.append("source.chapter_sha256 必须是 64 位小写 hex")

    raw_pack = data.get("pack")
    if not isinstance(raw_pack, dict):
        issues.append("pack 必须是对象")
    else:
        _unknown(raw_pack, frozenset({"id", "version"}), "pack", issues)
        m_pid2 = _text(raw_pack, "id", "pack", issues)
        _stable(m_pid2, "pack.id", issues)
        _text(raw_pack, "version", "pack", issues)

    # bindings: exactly 3 (room, character, item)
    raw_bindings = data.get("bindings")
    if not isinstance(raw_bindings, list):
        issues.append("bindings 必须是数组")
    else:
        kinds_seen: set[str] = set()
        gids_seen: set[str] = set()
        allowed_kinds = frozenset({"room", "character", "item"})
        for bi, rb in enumerate(raw_bindings):
            bloc = f"bindings[{bi}]"
            if not isinstance(rb, dict):
                issues.append(f"{bloc} 必须是对象")
                continue
            _unknown(rb, frozenset({
                "game_kind", "game_id", "canon_entity_ref",
                "canon_claim_refs", "adaptation_notes",
            }), bloc, issues)
            gk = rb.get("game_kind")
            if gk not in allowed_kinds:
                issues.append(f"{bloc}.game_kind 必须是 room|character|item")
            if gk in kinds_seen:
                issues.append(f"{bloc}.game_kind {gk!r} 重复")
            kinds_seen.add(gk)
            gid = _text(rb, "game_id", bloc, issues)
            if gid in gids_seen:
                issues.append(f"{bloc}.game_id {gid!r} 重复")
            gids_seen.add(gid)
            _text(rb, "canon_entity_ref", bloc, issues)
            _str_array(rb.get("canon_claim_refs"), f"{bloc}.canon_claim_refs", issues)
            _text(rb, "adaptation_notes", bloc, issues)

    # game_only: exactly 2 (quest, dialogue)
    raw_game_only = data.get("game_only")
    if not isinstance(raw_game_only, list):
        issues.append("game_only 必须是数组")
    else:
        go_kinds_seen: set[str] = set()
        go_gids_seen: set[str] = set()
        allowed_go = frozenset({"quest", "dialogue"})
        for gi, rg in enumerate(raw_game_only):
            gloc = f"game_only[{gi}]"
            if not isinstance(rg, dict):
                issues.append(f"{gloc} 必须是对象")
                continue
            _unknown(rg, frozenset({"game_kind", "game_id", "adaptation_notes"}), gloc, issues)
            gk = rg.get("game_kind")
            if gk not in allowed_go:
                issues.append(f"{gloc}.game_kind 必须是 quest|dialogue")
            if gk in go_kinds_seen:
                issues.append(f"{gloc}.game_kind {gk!r} 重复")
            go_kinds_seen.add(gk)
            gid = _text(rg, "game_id", gloc, issues)
            if gid in go_gids_seen:
                issues.append(f"{gloc}.game_id {gid!r} 重复")
            go_gids_seen.add(gid)
            _text(rg, "adaptation_notes", gloc, issues)

    # omissions
    raw_oms = data.get("omissions")
    if not isinstance(raw_oms, list):
        issues.append("omissions 必须是数组")
    else:
        om_cers: set[str] = set()
        for oi, ro in enumerate(raw_oms):
            oloc = f"omissions[{oi}]"
            if not isinstance(ro, dict):
                issues.append(f"{oloc} 必须是对象")
                continue
            _unknown(ro, frozenset({"canon_entity_ref", "reason"}), oloc, issues)
            o_cer = _text(ro, "canon_entity_ref", oloc, issues)
            if o_cer in om_cers:
                issues.append(f"{oloc}.canon_entity_ref 重复")
            om_cers.add(o_cer)
            _text(ro, "reason", oloc, issues)

    if issues:
        raise AdaptationValidationError(tuple(issues))

    # Build and return
    s = data["source"]
    source = ManifestSource(
        promotion_id=s.get("promotion_id", ""),
        chapter_id=s.get("chapter_id", ""),
        chapter_sha256=s.get("chapter_sha256", ""),
    )
    pk = data["pack"]
    pack = ManifestPack(
        id=pk.get("id", ""),
        version=pk.get("version", ""),
    )
    bindings = tuple(
        ManifestBinding(
            game_kind=b.get("game_kind", ""),
            game_id=b.get("game_id", ""),
            canon_entity_ref=b.get("canon_entity_ref", ""),
            canon_claim_refs=_str_array(b.get("canon_claim_refs"), f"bindings[{i}].canon_claim_refs", []),
            adaptation_notes=b.get("adaptation_notes", ""),
        )
        for i, b in enumerate(data.get("bindings", []))
    )
    game_only = tuple(
        ManifestGameOnly(
            game_kind=g.get("game_kind", ""),
            game_id=g.get("game_id", ""),
            adaptation_notes=g.get("adaptation_notes", ""),
        )
        for g in data.get("game_only", [])
    )
    omissions = tuple(
        ManifestOmission(
            canon_entity_ref=o.get("canon_entity_ref", ""),
            reason=o.get("reason", ""),
        )
        for o in data.get("omissions", [])
    )
    return AdaptationManifest(
        format_version=1, adaptation_id=data.get("adaptation_id", ""),
        source=source, pack=pack, bindings=bindings,
        omissions=omissions, game_only=game_only,
    )


# ── CLI ─────────────────────────────────────────────────────────────────────


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compile a micro content pack from canon draft + adaptation plan.",
    )
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
        print(f"JSON 解析错误：{exc}", file=sys.stderr)
        return 1
    except (
        AdaptationValidationError,
        CompilationError,
        OSError,
    ) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
