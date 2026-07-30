"""Validate v2 chapter manifests and fact-candidate source bindings.

Public API::

    validate_chapter_manifest(data) -> ChapterManifest
    validate_fact_candidate_sources(manifest, documents) -> tuple[FactCandidateDocument, ...]

No file I/O, no path arguments, no private-data access.
Standard library only.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pipeline.fact_candidates import FactCandidateDocument

# ── public exceptions ───────────────────────────────────────────────────────


class ChapterManifestValidationError(ValueError):
    """Raised when a chapter manifest fails structural validation."""

    def __init__(self, issues: tuple[str, ...]) -> None:
        self.issues = issues
        super().__init__("\n".join(f"- {i}" for i in issues))


class FactCandidateSourceValidationError(ValueError):
    """Raised when fact-candidate documents reference chapters not in the manifest."""

    def __init__(self, issues: tuple[str, ...]) -> None:
        self.issues = issues
        super().__init__("\n".join(f"- {i}" for i in issues))


# ── frozen data models ──────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ChapterManifestEntry:
    chapter_id: str
    title: str
    source_chapter_label: str | None
    source_title: str | None
    volume_label: str | None
    source_offset: int | None
    source_line: int | None
    path: str
    character_count: int
    sha256: str
    previous_id: str | None
    next_id: str | None


@dataclass(frozen=True, slots=True)
class ChapterManifest:
    format_version: int
    source_encoding: str | None
    chapter_count: int
    chapters: tuple[ChapterManifestEntry, ...]


# ── constants ───────────────────────────────────────────────────────────────

_CHAPTER_ID_RE = re.compile(r"^chapter_[0-9]{6}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SOURCE_ENCODINGS = frozenset({"utf-8-sig", "utf-8", "gbk", "gb18030"})

_ENTRY_ALLOWED_KEYS = frozenset({
    "chapter_id", "title", "source_chapter_label", "source_title",
    "volume_label", "source_offset", "source_line", "path",
    "character_count", "sha256", "previous_id", "next_id",
})

_ROOT_ALLOWED_KEYS = frozenset({
    "format_version", "source_encoding", "chapter_count", "chapters",
})


# ── internal helpers ────────────────────────────────────────────────────────


def _check_unknown_keys(
    obj: dict[str, Any], allowed: frozenset[str], loc: str, issues: list[str]
) -> None:
    for key in sorted(set(obj) - allowed):
        issues.append(f"{loc} 包含未知字段：{key}")


def _require_int(
    obj: dict[str, Any], key: str, loc: str, issues: list[str],
    *, minimum: int = 0,
) -> int | None:
    value = obj.get(key)
    if value is None:
        issues.append(f"{loc}.{key} 是必填字段")
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        issues.append(f"{loc}.{key} 必须是真正 int（bool 拒绝）")
        return None
    if value < minimum:
        issues.append(f"{loc}.{key} 必须 >= {minimum}，收到 {value}")
        return None
    return value


def _require_positive_int(
    obj: dict[str, Any], key: str, loc: str, issues: list[str],
) -> int | None:
    value = obj.get(key)
    if value is None:
        issues.append(f"{loc}.{key} 是必填字段")
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        issues.append(f"{loc}.{key} 必须是真正 int（bool 拒绝）")
        return None
    if value < 1:
        issues.append(f"{loc}.{key} 必须 >= 1，收到 {value}")
        return None
    return value


def _require_text(
    obj: dict[str, Any], key: str, loc: str, issues: list[str],
) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        issues.append(f"{loc}.{key} 必须是非空白字符串")
        return ""
    return value


def _require_string(
    obj: dict[str, Any], key: str, loc: str, issues: list[str],
) -> str:
    """Require a string value (allows empty)."""
    value = obj.get(key)
    if not isinstance(value, str):
        issues.append(f"{loc}.{key} 必须是字符串")
        return ""
    return value


def _optional_text_nullable(
    obj: dict[str, Any], key: str, loc: str, issues: list[str],
) -> str | None:
    if key not in obj:
        issues.append(f"{loc}.{key} 是必填字段（可为 null）")
        return None
    value = obj[key]
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        issues.append(f"{loc}.{key} 非 null 时必须是非空白字符串")
        return None
    return value


def _optional_int_nullable(
    obj: dict[str, Any], key: str, loc: str, issues: list[str],
    *, minimum: int = 0,
) -> int | None:
    if key not in obj:
        issues.append(f"{loc}.{key} 是必填字段（可为 null）")
        return None
    value = obj[key]
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        issues.append(f"{loc}.{key} 非 null 时必须是真正 int（bool 拒绝）")
        return None
    if value < minimum:
        issues.append(f"{loc}.{key} 非 null 时必须 >= {minimum}，收到 {value}")
        return None
    return value


# ── public entry point: manifest validation ─────────────────────────────────


def validate_chapter_manifest(data: object) -> ChapterManifest:
    """Validate a parsed JSON object as a v2 chapter manifest.

    Returns a frozen :class:`ChapterManifest` on success.
    Raises :class:`ChapterManifestValidationError` on failure.
    """

    issues: list[str] = []

    # ── root must be object ──────────────────────────────────────────────
    if not isinstance(data, dict):
        raise ChapterManifestValidationError(("根对象必须是 JSON 对象",))

    _check_unknown_keys(data, _ROOT_ALLOWED_KEYS, "根对象", issues)

    # format_version
    fv = data.get("format_version")
    if fv is None:
        issues.append("format_version 是必填字段")
    elif isinstance(fv, bool) or not isinstance(fv, int):
        issues.append("format_version 必须是真正 int（bool 拒绝）")
    elif fv != 2:
        issues.append(f"format_version 必须为 2，收到 {fv}")

    # source_encoding — must be explicitly present
    raw_se = data.get("source_encoding")
    if "source_encoding" not in data:
        issues.append("source_encoding 是必填字段（可为 null）")
        is_scan = False
    elif raw_se is None:
        is_scan = True
    elif not isinstance(raw_se, str):
        issues.append("source_encoding 必须是字符串或 null")
        is_scan = False
    elif raw_se not in _SOURCE_ENCODINGS:
        issues.append(
            f"source_encoding 必须是 utf-8-sig|utf-8|gbk|gb18030|null，"
            f"收到 {raw_se!r}"
        )
        is_scan = False
    else:
        is_scan = False

    # chapter_count
    chapter_count = _require_int(data, "chapter_count", "根对象", issues, minimum=0)

    # chapters
    raw_chapters = data.get("chapters")
    if not isinstance(raw_chapters, list):
        issues.append("chapters 必须是数组")
        raw_chapters = []

    # chapter_count must equal chapters length
    if chapter_count is not None and isinstance(raw_chapters, list):
        if chapter_count != len(raw_chapters):
            issues.append(
                f"chapter_count ({chapter_count}) 必须等于 "
                f"chapters 数组长度 ({len(raw_chapters)})"
            )

    # ── parse each entry ─────────────────────────────────────────────────
    parsed_entries: list[ChapterManifestEntry] = []
    seen_ids: set[str] = set()
    prev_offset: int | None = None
    prev_line: int | None = None

    for ei, raw_entry in enumerate(raw_chapters):
        eloc = f"chapters[{ei}]"
        if not isinstance(raw_entry, dict):
            issues.append(f"{eloc} 必须是对象")
            continue

        _check_unknown_keys(raw_entry, _ENTRY_ALLOWED_KEYS, eloc, issues)

        # chapter_id
        cid = raw_entry.get("chapter_id")
        if not isinstance(cid, str):
            issues.append(f"{eloc}.chapter_id 必须是字符串")
        elif not _CHAPTER_ID_RE.fullmatch(cid):
            issues.append(
                f"{eloc}.chapter_id 必须匹配 ^chapter_[0-9]{{6}}$，收到 {cid!r}"
            )
        else:
            # uniqueness
            if cid in seen_ids:
                issues.append(f"{eloc}.chapter_id 重复：{cid}")
            seen_ids.add(cid)
            # consecutive: must be chapter_{ei+1:06d}
            expected_id = f"chapter_{ei + 1:06d}"
            if cid != expected_id:
                issues.append(
                    f"{eloc}.chapter_id 应为 {expected_id}（连续递增），收到 {cid!r}"
                )

        # title
        _require_text(raw_entry, "title", eloc, issues)

        # path
        raw_path = raw_entry.get("path")
        if not isinstance(raw_path, str):
            issues.append(f"{eloc}.path 必须是字符串")
        else:
            # must equal <chapter_id>.txt
            if isinstance(cid, str) and _CHAPTER_ID_RE.fullmatch(cid):
                expected_path = f"{cid}.txt"
                if raw_path != expected_path:
                    issues.append(
                        f"{eloc}.path 必须为 {expected_path!r}，收到 {raw_path!r}"
                    )
            # reject directory separators, absolute paths
            if "/" in raw_path or "\\" in raw_path:
                issues.append(f"{eloc}.path 不得包含路径分隔符：{raw_path!r}")
            if raw_path.startswith("/") or raw_path.startswith("\\"):
                issues.append(f"{eloc}.path 不得是绝对路径")
            if ".." in raw_path:
                issues.append(f"{eloc}.path 不得包含路径穿越：{raw_path!r}")

        # character_count
        _require_int(raw_entry, "character_count", eloc, issues, minimum=0)

        # sha256
        raw_sha = raw_entry.get("sha256")
        if not isinstance(raw_sha, str):
            issues.append(f"{eloc}.sha256 必须是字符串")
        elif not _SHA256_RE.fullmatch(raw_sha):
            issues.append(
                f"{eloc}.sha256 必须是 64 位小写十六进制，收到 {raw_sha!r}"
            )

        # previous_id — key must be explicitly present
        if "previous_id" not in raw_entry:
            issues.append(f"{eloc}.previous_id 是必填字段（可为 null）")
            raw_prev = None
        else:
            raw_prev = raw_entry["previous_id"]
        if raw_prev is None:
            if ei != 0:
                issues.append(
                    f"{eloc}.previous_id 非首章节必须非 null"
                )
        elif not isinstance(raw_prev, str):
            issues.append(f"{eloc}.previous_id 必须是字符串或 null")
        elif ei > 0 and isinstance(raw_chapters[ei - 1], dict):
            expected_prev = raw_chapters[ei - 1].get("chapter_id")
            if isinstance(expected_prev, str) and raw_prev != expected_prev:
                issues.append(
                    f"{eloc}.previous_id 应为 {expected_prev!r}，收到 {raw_prev!r}"
                )
        elif ei == 0:
            issues.append(f"{eloc}.previous_id 首章节必须为 null")

        # next_id — key must be explicitly present
        if "next_id" not in raw_entry:
            issues.append(f"{eloc}.next_id 是必填字段（可为 null）")
            raw_next = None
        else:
            raw_next = raw_entry["next_id"]
        if raw_next is None:
            if ei != len(raw_chapters) - 1:
                issues.append(
                    f"{eloc}.next_id 非末章节必须非 null"
                )
        elif not isinstance(raw_next, str):
            issues.append(f"{eloc}.next_id 必须是字符串或 null")
        elif ei < len(raw_chapters) - 1 and isinstance(raw_chapters[ei + 1], dict):
            expected_next = raw_chapters[ei + 1].get("chapter_id")
            if isinstance(expected_next, str) and raw_next != expected_next:
                issues.append(
                    f"{eloc}.next_id 应为 {expected_next!r}，收到 {raw_next!r}"
                )
        elif ei == len(raw_chapters) - 1:
            issues.append(f"{eloc}.next_id 末章节必须为 null")

        # ── primary vs scan conditional fields ───────────────────────────
        if is_scan:
            # scan path: these 5 must be null
            for null_field in (
                "source_chapter_label", "source_title", "volume_label",
                "source_offset", "source_line",
            ):
                if null_field not in raw_entry or raw_entry[null_field] is not None:
                    issues.append(
                        f"{eloc}.{null_field} 在 source_encoding=null "
                        "(scan 路径) 时必须为 null"
                    )
        else:
            # primary path
            _require_text(raw_entry, "source_chapter_label", eloc, issues)

            # source_title: string, allows empty
            _require_string(raw_entry, "source_title", eloc, issues)

            # volume_label: non-blank string or null
            _optional_text_nullable(raw_entry, "volume_label", eloc, issues)

            # source_offset: non-negative int (required in primary)
            raw_offset = _require_int(
                raw_entry, "source_offset", eloc, issues, minimum=0
            )

            # source_line: positive int (required in primary)
            raw_line = _require_positive_int(
                raw_entry, "source_line", eloc, issues
            )

            # offset monotonic increase
            if raw_offset is not None and prev_offset is not None:
                if raw_offset <= prev_offset:
                    issues.append(
                        f"{eloc}.source_offset ({raw_offset}) 必须严格大于 "
                        f"前一章节的 offset ({prev_offset})"
                    )
            if raw_offset is not None:
                prev_offset = raw_offset

            # line monotonic increase
            if raw_line is not None and prev_line is not None:
                if raw_line <= prev_line:
                    issues.append(
                        f"{eloc}.source_line ({raw_line}) 必须严格大于 "
                        f"前一章节的 line ({prev_line})"
                    )
            if raw_line is not None:
                prev_line = raw_line

        # build entry only if critical fields present
        if (
            isinstance(cid, str) and _CHAPTER_ID_RE.fullmatch(cid)
            and isinstance(raw_path, str)
            and isinstance(raw_sha, str) and _SHA256_RE.fullmatch(raw_sha)
        ):
            cc_val = raw_entry.get("character_count")
            cc = cc_val if (isinstance(cc_val, int) and not isinstance(cc_val, bool) and cc_val >= 0) else 0

            parsed_entries.append(ChapterManifestEntry(
                chapter_id=cid,
                title=raw_entry.get("title", "") if isinstance(raw_entry.get("title"), str) else "",
                source_chapter_label=raw_entry.get("source_chapter_label") if isinstance(raw_entry.get("source_chapter_label"), str) else None,
                source_title=raw_entry.get("source_title") if isinstance(raw_entry.get("source_title"), str) else None,
                volume_label=raw_entry.get("volume_label") if isinstance(raw_entry.get("volume_label"), str) and raw_entry.get("volume_label", "").strip() else None,
                source_offset=raw_entry.get("source_offset") if isinstance(raw_entry.get("source_offset"), int) and not isinstance(raw_entry.get("source_offset"), bool) else None,
                source_line=raw_entry.get("source_line") if isinstance(raw_entry.get("source_line"), int) and not isinstance(raw_entry.get("source_line"), bool) else None,
                path=raw_path,
                character_count=cc,
                sha256=raw_sha,
                previous_id=raw_entry.get("previous_id") if isinstance(raw_entry.get("previous_id"), str) else None,
                next_id=raw_entry.get("next_id") if isinstance(raw_entry.get("next_id"), str) else None,
            ))

    if issues:
        raise ChapterManifestValidationError(tuple(issues))

    return ChapterManifest(
        format_version=2,
        source_encoding=raw_se if isinstance(raw_se, str) else None,
        chapter_count=chapter_count if chapter_count is not None else 0,
        chapters=tuple(parsed_entries),
    )


# ── public entry point: source binding ──────────────────────────────────────


def validate_fact_candidate_sources(
    manifest: ChapterManifest,
    documents: Sequence[object],
) -> tuple[FactCandidateDocument, ...]:
    """Validate that each document's source_chapter exists in the manifest.

    Returns a tuple of the validated documents in input order.
    Raises :class:`FactCandidateSourceValidationError` on failure.
    Empty documents sequence is valid.
    """

    issues: list[str] = []
    manifest_ids = {entry.chapter_id for entry in manifest.chapters}
    result: list[FactCandidateDocument] = []

    for di, doc in enumerate(documents):
        if not isinstance(doc, FactCandidateDocument):
            issues.append(
                f"documents[{di}] 必须是 FactCandidateDocument 实例，"
                f"收到 {type(doc).__name__}"
            )
            continue
        if doc.source_chapter not in manifest_ids:
            issues.append(
                f"documents[{di}].source_chapter ({doc.source_chapter}) "
                f"不存在于 manifest 的 chapter_id 集合中"
            )
        result.append(doc)

    if issues:
        raise FactCandidateSourceValidationError(tuple(issues))

    return tuple(result)
