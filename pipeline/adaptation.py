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
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Any, Literal

from pipeline.canon import CanonDraft, validate_canon_draft_document

# ── regex ──────────────────────────────────────────────────────────────────

_STABLE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_CHAPTER_ID_RE = re.compile(r"^chapter_[0-9]{6}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# ── allowed filenames ──────────────────────────────────────────────────────

_ALLOWED_FILES = frozenset({
    "pack.json", "rooms.json", "items.json", "characters.json",
    "quests.json", "dialogues.json", "monsters.json", "shops.json",
    "adaptation_manifest.json",
})

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


# ── MicroContentPack (fixed 9-field model) ─────────────────────────────────


@dataclass(frozen=True, slots=True)
class MicroContentPack:
    pack: bytes
    rooms: bytes
    items: bytes
    characters: bytes
    quests: bytes
    dialogues: bytes
    monsters: bytes
    shops: bytes
    manifest: AdaptationManifest

    def __post_init__(self) -> None:
        _valid_files = {
            "pack.json", "rooms.json", "items.json", "characters.json",
            "quests.json", "dialogues.json", "monsters.json", "shops.json",
            "adaptation_manifest.json",
        }
        for attr in ("pack", "rooms", "items", "characters", "quests",
                     "dialogues", "monsters", "shops"):
            val = getattr(self, attr)
            if not isinstance(val, bytes):
                raise TypeError(f"{attr} 必须是 bytes，收到 {type(val).__name__}")
        if not isinstance(self.manifest, AdaptationManifest):
            raise TypeError("manifest 必须是 AdaptationManifest")

    _FILE_ORDER = (
        "pack.json", "rooms.json", "items.json", "characters.json",
        "quests.json", "dialogues.json", "monsters.json", "shops.json",
        "adaptation_manifest.json",
    )

    def _documents(self) -> list[tuple[str, bytes]]:
        return [
            ("pack.json", self.pack),
            ("rooms.json", self.rooms),
            ("items.json", self.items),
            ("characters.json", self.characters),
            ("quests.json", self.quests),
            ("dialogues.json", self.dialogues),
            ("monsters.json", self.monsters),
            ("shops.json", self.shops),
            ("adaptation_manifest.json", self._manifest_bytes()),
        ]

    def _manifest_bytes(self) -> bytes:
        return _json_bytes(_manifest_to_dict(self.manifest))


# ── internal helpers ────────────────────────────────────────────────────────


def _norm_key(s: str) -> str:
    return unicodedata.normalize("NFKC", s).casefold().strip()


def _text(obj: dict, key: str, loc: str, issues: list) -> str:
    v = obj.get(key)
    if not isinstance(v, str) or not v.strip():
        issues.append(f"{loc}.{key} 必须是非空字符串")
        return ""
    return v


def _int_or(obj: dict, key: str, loc: str, issues: list,
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
        if not isinstance(v, str):
            issues.append(f"{loc}[{vi}] 必须是字符串")
            continue
        if not v.strip():
            issues.append(f"{loc}[{vi}] 必须是非空字符串")
            continue
        _stable(v, f"{loc}[{vi}]", issues)
        nk = _norm_key(v)
        if nk in seen:
            issues.append(f"{loc}[{vi}] 存在规范化后重复：{v!r}")
        seen.add(nk)
        result.append(v)
    return tuple(result)


def _json_bytes(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"


def _manifest_to_dict(manifest: AdaptationManifest) -> dict[str, Any]:
    return {
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
                "game_kind": b.game_kind, "game_id": b.game_id,
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

    rp = data.get("pack")
    if not isinstance(rp, dict):
        issues.append("pack 必须是对象")
    for kind in ("room", "character", "item"):
        rv = data.get(kind)
        if not isinstance(rv, dict):
            issues.append(f"{kind} 必须是对象")
    rq = data.get("quest")
    if not isinstance(rq, dict):
        issues.append("quest 必须是对象")
    rd = data.get("dialogue")
    if not isinstance(rd, dict):
        issues.append("dialogue 必须是对象")
    rom = data.get("omissions")
    if not isinstance(rom, list):
        issues.append("omissions 必须是数组")

    if issues:
        raise AdaptationValidationError(tuple(issues))

    # ── parse pack ──────────────────────────────────────────────────────
    _unknown(rp, frozenset({"id", "name", "version", "start_room_id", "player"}), "pack", issues)
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
        player = PlayerSub(
            max_hp=_int_or(raw_ply, "max_hp", "pack.player", issues, minimum=1, default=20),
            attack=_int_or(raw_ply, "attack", "pack.player", issues, minimum=1, default=5),
            defense=_int_or(raw_ply, "defense", "pack.player", issues, minimum=0, default=1),
            inventory_capacity=_int_or(raw_ply, "inventory_capacity", "pack.player", issues, minimum=1, default=20),
            coins=_int_or(raw_ply, "coins", "pack.player", issues, minimum=0, default=0),
        )
    pack = PackProfile(id=pid, name=pname, version=pver, start_room_id=srid, player=player)

    # ── parse canon-entity adapters ─────────────────────────────────────
    def _parse_adapter(kind: str) -> tuple:
        raw = data[kind]
        _unknown(raw, frozenset({"canon_entity_ref", "game_id", "name", "description",
                                 "canon_claim_refs", "adaptation_notes"}), kind, issues)
        cer = _text(raw, "canon_entity_ref", kind, issues)
        _stable(cer, f"{kind}.canon_entity_ref", issues)
        gid = _text(raw, "game_id", kind, issues)
        _stable(gid, f"{kind}.game_id", issues)
        name = _text(raw, "name", kind, issues)
        desc = _text(raw, "description", kind, issues)
        an = _text(raw, "adaptation_notes", kind, issues)
        ccr = _str_array(raw.get("canon_claim_refs"), f"{kind}.canon_claim_refs", issues)
        return cer, gid, name, desc, an, ccr

    r_cer, r_gid, r_name, r_desc, r_an, r_ccr = _parse_adapter("room")
    room = RoomAdaptation(canon_entity_ref=r_cer, game_id=r_gid, name=r_name,
                          description=r_desc, adaptation_notes=r_an, canon_claim_refs=r_ccr)
    c_cer, c_gid, c_name, c_desc, c_an, c_ccr = _parse_adapter("character")
    character = CharacterAdaptation(canon_entity_ref=c_cer, game_id=c_gid, name=c_name,
                                    description=c_desc, adaptation_notes=c_an,
                                    canon_claim_refs=c_ccr)
    i_cer, i_gid, i_name, i_desc, i_an, i_ccr = _parse_adapter("item")
    item = ItemAdaptation(canon_entity_ref=i_cer, game_id=i_gid, name=i_name,
                          description=i_desc, adaptation_notes=i_an, canon_claim_refs=i_ccr)

    # ── parse quest ─────────────────────────────────────────────────────
    ra = data["quest"]
    _unknown(ra, frozenset({"game_id", "kind", "name", "description", "target_item_id",
                            "required_quantity", "reward_experience", "adaptation_notes"}), "quest", issues)
    q_gid = _text(ra, "game_id", "quest", issues)
    _stable(q_gid, "quest.game_id", issues)
    q_kind = ra.get("kind")
    if q_kind != "collect_item":
        issues.append("quest.kind 必须为 collect_item")
    q_name = _text(ra, "name", "quest", issues)
    q_desc = _text(ra, "description", "quest", issues)
    q_tid = _text(ra, "target_item_id", "quest", issues)
    _stable(q_tid, "quest.target_item_id", issues)
    q_rq = _int_or(ra, "required_quantity", "quest", issues, minimum=1, default=1)
    q_re = _int_or(ra, "reward_experience", "quest", issues, minimum=1, default=10)
    q_an = _text(ra, "adaptation_notes", "quest", issues)
    quest = QuestAdaptation(game_id=q_gid, kind="collect_item", name=q_name,
                            description=q_desc, target_item_id=q_tid,
                            required_quantity=q_rq, reward_experience=q_re,
                            adaptation_notes=q_an)

    # ── parse dialogue ──────────────────────────────────────────────────
    rv = data["dialogue"]
    _unknown(rv, frozenset({"game_id", "character_id", "start_node_id", "nodes",
                            "adaptation_notes"}), "dialogue", issues)
    d_gid = _text(rv, "game_id", "dialogue", issues)
    _stable(d_gid, "dialogue.game_id", issues)
    d_cid = _text(rv, "character_id", "dialogue", issues)
    _stable(d_cid, "dialogue.character_id", issues)
    d_start = _text(rv, "start_node_id", "dialogue", issues)
    _stable(d_start, "dialogue.start_node_id", issues)
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
            _stable(oid, f"{oloc}.id", issues)
            if oid in oids:
                issues.append(f"{oloc}.id 重复：{oid}")
            oids.add(oid)
            otext = _text(ro, "text", oloc, issues)
            rnid = ro.get("next_node_id")
            # Type-safe: reject non-string-or-null
            if rnid is not None:
                if isinstance(rnid, str) and rnid.strip():
                    _stable(rnid, f"{oloc}.next_node_id", issues)
                    all_next.add(rnid)
                else:
                    issues.append(f"{oloc}.next_node_id 必须是非空字符串或 null")
                    rnid = None
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

    # ── parse omissions ─────────────────────────────────────────────────
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


def compile_micro_pack(canon_draft: CanonDraft, plan: AdaptationPlan) -> MicroContentPack:
    issues: list[str] = []
    entities = _canon_entity_map(canon_draft)

    # 1. Source binding
    if plan.source_promotion_id != canon_draft.promotion_id:
        issues.append(f"source_promotion_id ({plan.source_promotion_id}) 必须等于 "
                      f"canon_draft.promotion_id ({canon_draft.promotion_id})")
    if plan.source_chapter != canon_draft.source.chapter_id:
        issues.append(f"source_chapter ({plan.source_chapter}) 必须等于 "
                      f"canon_draft.source.chapter_id ({canon_draft.source.chapter_id})")

    # 2. Adaptations + coverage
    adapted: dict[str, str] = {}
    for kind, entry in [("room", plan.room), ("character", plan.character), ("item", plan.item)]:
        cer = entry.canon_entity_ref
        if cer in adapted:
            issues.append(f"{kind}.canon_entity_ref {cer!r} 已被 {adapted[cer]} 使用")
        adapted[cer] = kind
        if cer not in entities:
            issues.append(f"{kind}.canon_entity_ref {cer!r} 不存在于 CanonDraft 中")
            continue
        entity = entities[cer]
        et_map = {"room": "location", "character": "character", "item": "item"}
        if entity.entity_type != et_map[kind]:
            issues.append(f"{kind}.canon_entity_ref {cer!r} 类型为 {entity.entity_type}，期望 {et_map[kind]}")
        entity_claim_ids = {c.claim_id for c in entity.claims}
        for cref in entry.canon_claim_refs:
            if cref not in entity_claim_ids:
                issues.append(f"{kind}.canon_claim_refs 中的 {cref!r} 不属于 entity {cer!r}")

    # 3. Omissions
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
    all_ids = set(entities.keys())
    covered = set(adapted.keys()) | omitted
    extra = covered - all_ids
    missing = all_ids - covered
    if extra or missing:
        if missing:
            issues.append(f"entity 未被覆盖：{sorted(missing)}")
        if extra:
            issues.append(f"adaptations/omissions 引用不存在 entity：{sorted(extra)}")

    # 5. Game ID uniqueness
    all_gids: set[str] = set()
    gid_src: dict[str, str] = {}
    for kind, entry in [("room", plan.room), ("character", plan.character), ("item", plan.item),
                        ("quest", plan.quest), ("dialogue", plan.dialogue)]:
        gid = entry.game_id
        if gid in all_gids:
            issues.append(f"game_id {gid!r} 重复（{kind} 与 {gid_src.get(gid)}）")
        all_gids.add(gid)
        gid_src[gid] = kind

    # 6. Fixed references
    if plan.pack.start_room_id != plan.room.game_id:
        issues.append(f"pack.start_room_id 必须等于 room.game_id")
    if plan.dialogue.character_id != plan.character.game_id:
        issues.append(f"dialogue.character_id 必须等于 character.game_id")
    if plan.quest.target_item_id != plan.item.game_id:
        issues.append(f"quest.target_item_id 必须等于 item.game_id")
    if plan.quest.kind != "collect_item":
        issues.append("quest.kind 必须是 collect_item")
    if plan.quest.required_quantity != 1:
        issues.append("quest.required_quantity 必须为 1")

    if issues:
        raise CompilationError(tuple(issues))

    # ── Build bytes ─────────────────────────────────────────────────────
    scid = canon_draft.source.chapter_id
    src_ch = (scid,)

    def _json(d: Any) -> bytes:
        return json.dumps(d, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"

    # pack
    pack_bytes = _json({
        "id": plan.pack.id, "name": plan.pack.name, "version": plan.pack.version,
        "start_room_id": plan.pack.start_room_id,
        "player": {"max_hp": plan.pack.player.max_hp, "attack": plan.pack.player.attack,
                   "defense": plan.pack.player.defense,
                   "inventory_capacity": plan.pack.player.inventory_capacity,
                   "coins": plan.pack.player.coins},
        "extensions": {
            "canon_provider": {
                "kind": "adaptation_manifest", "format_version": 1,
                "path": "adaptation_manifest.json",
            },
        },
    })

    # rooms
    rooms_bytes = _json([{
        "id": plan.room.game_id, "name": plan.room.name, "description": plan.room.description,
        "exits": {},
        "item_stacks": [{"item_id": plan.item.game_id, "quantity": 1}],
        "monster_ids": [],
        "canon_ref": {"entity_id": plan.room.canon_entity_ref, "source_chapters": list(src_ch)},
        "adaptation_notes": plan.room.adaptation_notes,
    }])

    # items
    items_bytes = _json([{
        "id": plan.item.game_id, "name": plan.item.name, "description": plan.item.description,
        "stack_limit": 1,
        "canon_ref": {"entity_id": plan.item.canon_entity_ref, "source_chapters": list(src_ch)},
        "adaptation_notes": plan.item.adaptation_notes,
    }])

    # characters
    chars_bytes = _json([{
        "id": plan.character.game_id, "name": plan.character.name,
        "description": plan.character.description,
        "room_id": plan.pack.start_room_id,
        "canon_ref": {"entity_id": plan.character.canon_entity_ref, "source_chapters": list(src_ch)},
        "adaptation_notes": plan.character.adaptation_notes,
    }])

    # quests — no canon_ref
    quests_bytes = _json([{
        "id": plan.quest.game_id, "kind": "collect_item",
        "name": plan.quest.name, "description": plan.quest.description,
        "trigger_room_id": plan.pack.start_room_id,
        "target_item_id": plan.quest.target_item_id,
        "required_quantity": 1,
        "reward_experience": plan.quest.reward_experience,
        "adaptation_notes": plan.quest.adaptation_notes,
    }])

    # dialogues — no canon_ref, nodes sorted by node.id deterministically, options preserved
    nodes_out = []
    for node in sorted(plan.dialogue.nodes, key=lambda n: _norm_key(n.id)):
        nodes_out.append({
            "id": node.id, "text": node.text,
            "options": [
                {"id": o.id, "text": o.text, "next_node_id": o.next_node_id, "effects": []}
                for o in node.options
            ],
        })
    dialogs_bytes = _json([{
        "id": plan.dialogue.game_id, "character_id": plan.dialogue.character_id,
        "start_node_id": plan.dialogue.start_node_id,
        "nodes": nodes_out,
        "adaptation_notes": plan.dialogue.adaptation_notes,
    }])

    empty_bytes = _json([])

    # Manifest
    bindings_list = [
        ManifestBinding(game_kind="room", game_id=plan.room.game_id,
                        canon_entity_ref=plan.room.canon_entity_ref,
                        canon_claim_refs=tuple(sorted(plan.room.canon_claim_refs, key=_norm_key)),
                        adaptation_notes=plan.room.adaptation_notes),
        ManifestBinding(game_kind="character", game_id=plan.character.game_id,
                        canon_entity_ref=plan.character.canon_entity_ref,
                        canon_claim_refs=tuple(sorted(plan.character.canon_claim_refs, key=_norm_key)),
                        adaptation_notes=plan.character.adaptation_notes),
        ManifestBinding(game_kind="item", game_id=plan.item.game_id,
                        canon_entity_ref=plan.item.canon_entity_ref,
                        canon_claim_refs=tuple(sorted(plan.item.canon_claim_refs, key=_norm_key)),
                        adaptation_notes=plan.item.adaptation_notes),
    ]
    go_list = [
        ManifestGameOnly(game_kind="quest", game_id=plan.quest.game_id, adaptation_notes=plan.quest.adaptation_notes),
        ManifestGameOnly(game_kind="dialogue", game_id=plan.dialogue.game_id, adaptation_notes=plan.dialogue.adaptation_notes),
    ]
    om_list = [ManifestOmission(canon_entity_ref=o.canon_entity_ref, reason=o.reason) for o in plan.omissions]

    manifest = AdaptationManifest(
        format_version=1, adaptation_id=plan.adaptation_id,
        source=ManifestSource(promotion_id=canon_draft.promotion_id,
                              chapter_id=canon_draft.source.chapter_id,
                              chapter_sha256=canon_draft.source.chapter_sha256),
        pack=ManifestPack(id=plan.pack.id, version=plan.pack.version),
        bindings=tuple(sorted(bindings_list, key=lambda b: (b.game_kind, _norm_key(b.game_id)))),
        omissions=tuple(sorted(om_list, key=lambda o: _norm_key(o.canon_entity_ref))),
        game_only=tuple(sorted(go_list, key=lambda g: (g.game_kind, _norm_key(g.game_id)))),
    )

    return MicroContentPack(
        pack=pack_bytes, rooms=rooms_bytes, items=items_bytes,
        characters=chars_bytes, quests=quests_bytes, dialogues=dialogs_bytes,
        monsters=empty_bytes, shops=empty_bytes, manifest=manifest,
    )


# ── write_micro_pack ────────────────────────────────────────────────────────


def write_micro_pack(micro_pack: MicroContentPack, output_dir: str | Path) -> Path:
    output = Path(output_dir)
    output_str = str(output.resolve())

    # P1-2: lexists before resolve on the leaf (use lexical path for lexists)
    output_lexical = str(Path(os.path.normcase(str(output))).resolve() if os.path.sep == "\\"
                         else Path(str(output)).resolve())

    # First lexists check — use the raw path for the leaf check
    if os.path.lexists(str(output)):
        raise FileExistsError(f"output_dir ({output}) 已存在，拒绝覆盖")

    # Verify parent exists
    parent = output.resolve().parent
    if not parent.is_dir():
        raise FileNotFoundError(f"父目录不存在：{parent}")

    # Race window: re-check lexists
    if os.path.lexists(str(output)):
        raise FileExistsError(f"output_dir ({output}) 在执行期间被创建，拒绝覆盖")

    # Temp dir
    tmp_dir = Path(tempfile.mkdtemp(dir=parent, prefix=".l2w_adaptation_"))
    try:
        for filename, payload in micro_pack._documents():
            _validate_document_path(filename, payload)
            dst = tmp_dir / filename
            with open(dst, "wb") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())

        # Validate with existing loader
        from lore2mud.content.loader import load_content_pack
        load_content_pack(tmp_dir)

        # Re-validate manifest
        with open(tmp_dir / "adaptation_manifest.json", "r", encoding="utf-8") as f:
            re_validated = validate_adaptation_manifest_document(json.load(f))
        if re_validated != micro_pack.manifest:
            raise AdaptationValidationError(("staged manifest 与 micro_pack.manifest 不一致",))

        os.replace(str(tmp_dir), str(output))

    except BaseException:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise

    return Path(output)


def _validate_document_path(filename: str, payload: bytes) -> None:
    """Reject non-allowed, traversal, absolute, or non-bytes documents."""
    if not isinstance(filename, str) or not isinstance(payload, bytes):
        raise CompilationError(("document filename 必须是 str，payload 必须是 bytes",))
    p = PurePath(filename)
    if p.is_absolute():
        raise CompilationError((f"document 文件名是绝对路径：{filename}",))
    if p.as_posix().count("/") > 0 or p.as_posix().count("..") > 0:
        raise CompilationError((f"document 文件名包含路径分隔符或 ..：{filename}",))
    if filename not in _ALLOWED_FILES:
        raise CompilationError((f"document 文件名 {filename!r} 不在允许列表中",))


# ── validate_adaptation_manifest_document ────────────────────────────────────


def validate_adaptation_manifest_document(data: object) -> AdaptationManifest:
    issues: list[str] = []

    if not isinstance(data, dict):
        raise AdaptationValidationError(("根对象必须是 JSON 对象",))

    _unknown(data, frozenset({"format_version", "adaptation_id", "source",
                              "pack", "bindings", "omissions", "game_only"}), "根对象", issues)

    fv = data.get("format_version")
    if fv is None or isinstance(fv, bool) or not isinstance(fv, int) or fv != 1:
        issues.append("format_version 必须是 1")
    aid = _text(data, "adaptation_id", "根对象", issues)
    _stable(aid, "adaptation_id", issues)

    # source
    rs = data.get("source")
    if not isinstance(rs, dict):
        issues.append("source 必须是对象")
    else:
        _unknown(rs, frozenset({"promotion_id", "chapter_id", "chapter_sha256"}), "source", issues)
        m_pid = _text(rs, "promotion_id", "source", issues)
        _stable(m_pid, "source.promotion_id", issues)
        m_cid = _text(rs, "chapter_id", "source", issues)
        if m_cid and not _CHAPTER_ID_RE.fullmatch(m_cid):
            issues.append("source.chapter_id 必须匹配 chapter_NNNNNN")
        m_sha = rs.get("chapter_sha256")
        if not isinstance(m_sha, str) or not _SHA256_RE.fullmatch(m_sha):
            issues.append("source.chapter_sha256 必须是 64 位小写 hex")

    # pack
    rpk = data.get("pack")
    if not isinstance(rpk, dict):
        issues.append("pack 必须是对象")
    else:
        _unknown(rpk, frozenset({"id", "version"}), "pack", issues)
        _stable(_text(rpk, "id", "pack", issues), "pack.id", issues)
        _text(rpk, "version", "pack", issues)

    # ── bindings: exactly 3, kinds = {room, character, item} ────────────
    raw_bindings = data.get("bindings")
    if not isinstance(raw_bindings, list):
        issues.append("bindings 必须是数组")
    else:
        if len(raw_bindings) != 3:
            issues.append(f"bindings 必须恰好 3 项，收到 {len(raw_bindings)}")
        kinds_seen: set[str] = set()
        gids_seen: set[str] = set()
        for bi, rb in enumerate(raw_bindings):
            bloc = f"bindings[{bi}]"
            if not isinstance(rb, dict):
                issues.append(f"{bloc} 必须是对象")
                continue
            _unknown(rb, frozenset({"game_kind", "game_id", "canon_entity_ref",
                                    "canon_claim_refs", "adaptation_notes"}), bloc, issues)
            gk = rb.get("game_kind")
            if gk not in ("room", "character", "item"):
                issues.append(f"{bloc}.game_kind 必须是 room|character|item")
            if gk in kinds_seen:
                issues.append(f"{bloc}.game_kind {gk!r} 重复")
            kinds_seen.add(gk)
            gid = _text(rb, "game_id", bloc, issues)
            _stable(gid, f"{bloc}.game_id", issues)
            if gid in gids_seen:
                issues.append(f"{bloc}.game_id {gid!r} 重复")
            gids_seen.add(gid)
            cer = _text(rb, "canon_entity_ref", bloc, issues)
            _stable(cer, f"{bloc}.canon_entity_ref", issues)
            _str_array(rb.get("canon_claim_refs"), f"{bloc}.canon_claim_refs", issues)
            _text(rb, "adaptation_notes", bloc, issues)

    # ── game_only: exactly 2, kinds = {quest, dialogue} ─────────────────
    raw_go = data.get("game_only")
    if not isinstance(raw_go, list):
        issues.append("game_only 必须是数组")
    else:
        if len(raw_go) != 2:
            issues.append(f"game_only 必须恰好 2 项，收到 {len(raw_go)}")
        go_kinds: set[str] = set()
        go_gids: set[str] = set()
        for gi, rg in enumerate(raw_go):
            gloc = f"game_only[{gi}]"
            if not isinstance(rg, dict):
                issues.append(f"{gloc} 必须是对象")
                continue
            _unknown(rg, frozenset({"game_kind", "game_id", "adaptation_notes"}), gloc, issues)
            gk = rg.get("game_kind")
            if gk not in ("quest", "dialogue"):
                issues.append(f"{gloc}.game_kind 必须是 quest|dialogue")
            if gk in go_kinds:
                issues.append(f"{gloc}.game_kind {gk!r} 重复")
            go_kinds.add(gk)
            gid = _text(rg, "game_id", gloc, issues)
            _stable(gid, f"{gloc}.game_id", issues)
            if gid in go_gids:
                issues.append(f"{gloc}.game_id {gid!r} 重复")
            go_gids.add(gid)
            _text(rg, "adaptation_notes", gloc, issues)

        # Global game ID uniqueness: bindings + game_only
        all_go_gids = gids_seen | go_gids if isinstance(raw_bindings, list) else go_gids
        # already tracked separately

    # ── omissions ───────────────────────────────────────────────────────
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
            _stable(o_cer, f"{oloc}.canon_entity_ref", issues)
            if o_cer in om_cers:
                issues.append(f"{oloc}.canon_entity_ref 重复")
            om_cers.add(o_cer)
            _text(ro, "reason", oloc, issues)

    if issues:
        raise AdaptationValidationError(tuple(issues))

    # Build return value
    s = data["source"]
    source = ManifestSource(promotion_id=s.get("promotion_id", ""),
                            chapter_id=s.get("chapter_id", ""),
                            chapter_sha256=s.get("chapter_sha256", ""))
    pk = data["pack"]
    mp = ManifestPack(id=pk.get("id", ""), version=pk.get("version", ""))
    bindings = tuple(
        ManifestBinding(game_kind=b.get("game_kind", ""), game_id=b.get("game_id", ""),
                        canon_entity_ref=b.get("canon_entity_ref", ""),
                        canon_claim_refs=_str_array(b.get("canon_claim_refs"), f"bindings[{i}].canon_claim_refs", []),
                        adaptation_notes=b.get("adaptation_notes", ""))
        for i, b in enumerate(data.get("bindings", []))
    )
    game_only = tuple(
        ManifestGameOnly(game_kind=g.get("game_kind", ""), game_id=g.get("game_id", ""),
                         adaptation_notes=g.get("adaptation_notes", ""))
        for g in data.get("game_only", [])
    )
    omissions = tuple(
        ManifestOmission(canon_entity_ref=o.get("canon_entity_ref", ""), reason=o.get("reason", ""))
        for o in data.get("omissions", [])
    )
    return AdaptationManifest(
        format_version=1, adaptation_id=data.get("adaptation_id", ""),
        source=source, pack=mp, bindings=bindings, omissions=omissions,
        game_only=game_only,
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
    except UnicodeDecodeError as exc:
        print(f"UTF-8 解码错误：{exc}", file=sys.stderr)
        return 1
    except (
        AdaptationValidationError,
        CompilationError,
        FileExistsError,
        FileNotFoundError,
        OSError,
    ) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        # Catch remaining data errors (CanonDraftValidationError etc.)
        print(f"错误：{exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
