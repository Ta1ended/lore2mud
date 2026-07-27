"""Build a deterministic manifest for already-split chapter text files.

Accepts pre-parsed ``Chapter`` objects from ``split_novel`` so the manifest
reflects the actual split metadata rather than re-scanning files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pipeline.split_novel import Chapter


def build_manifest(
    chapter_dir: Path,
    *,
    chapters: Sequence[Chapter] | None = None,
    source_encoding: str = "utf-8-sig",
) -> dict[str, object]:
    """Return manifest dict.

    When *chapters* is provided the metadata comes from the split pass.
    Otherwise the directory is scanned (legacy fallback, limited fields).
    """
    if chapters is not None:
        return _build_from_chapters(chapter_dir, chapters, source_encoding)
    return _build_from_scan(chapter_dir)


# ------------------------------------------------------------------
# Primary path: metadata from split_novel.Chapter objects
# ------------------------------------------------------------------

def _build_from_chapters(
    chapter_dir: Path,
    chapters: Sequence[Chapter],
    source_encoding: str,
) -> dict[str, object]:
    entries: list[dict[str, object]] = []
    for index, ch in enumerate(chapters):
        path = chapter_dir / f"{ch.chapter_id}.txt"
        if path.exists():
            with path.open("r", encoding="utf-8", newline="") as fh:
                text = fh.read()
        else:
            text = ch.text
        entries.append(
            {
                "chapter_id": ch.chapter_id,
                "title": ch.title,
                "source_chapter_label": ch.source_chapter_label,
                "source_title": ch.source_title,
                "volume_label": ch.volume_label,
                "source_offset": ch.source_offset,
                "source_line": ch.source_line,
                "path": f"{ch.chapter_id}.txt",
                "character_count": len(text),
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "previous_id": chapters[index - 1].chapter_id if index > 0 else None,
                "next_id": (
                    chapters[index + 1].chapter_id
                    if index + 1 < len(chapters)
                    else None
                ),
            }
        )
    return {
        "format_version": 2,
        "source_encoding": source_encoding,
        "chapter_count": len(entries),
        "chapters": entries,
    }


# ------------------------------------------------------------------
# Legacy fallback: scan chapter_*.txt files in a directory
# ------------------------------------------------------------------

def _build_from_scan(chapter_dir: Path) -> dict[str, object]:
    files = sorted(chapter_dir.glob("chapter_*.txt"))
    entries: list[dict[str, object]] = []
    for index, path in enumerate(files):
        with path.open("r", encoding="utf-8", newline="") as fh:
            text = fh.read()
        first_line = next(
            (line.strip() for line in text.splitlines() if line.strip()),
            path.stem,
        )
        entries.append(
            {
                "chapter_id": path.stem,
                "title": first_line,
                "source_chapter_label": None,
                "source_title": None,
                "volume_label": None,
                "source_offset": None,
                "source_line": None,
                "path": path.name,
                "character_count": len(text),
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "previous_id": files[index - 1].stem if index > 0 else None,
                "next_id": (
                    files[index + 1].stem if index + 1 < len(files) else None
                ),
            }
        )
    return {
        "format_version": 2,
        "source_encoding": None,
        "chapter_count": len(entries),
        "chapters": entries,
    }


# ------------------------------------------------------------------
# JSON I/O
# ------------------------------------------------------------------

def write_manifest(
    chapter_dir: Path,
    *,
    chapters: Sequence[Chapter] | None = None,
    source_encoding: str = "utf-8-sig",
) -> Path:
    manifest = build_manifest(
        chapter_dir, chapters=chapters, source_encoding=source_encoding
    )
    output = chapter_dir / "manifest.json"
    output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("chapter_dir", type=Path)
    args = parser.parse_args(argv)
    if not args.chapter_dir.is_dir():
        parser.error(f"章节目录不存在：{args.chapter_dir}")
    output = write_manifest(args.chapter_dir)
    print(f"已生成：{output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
