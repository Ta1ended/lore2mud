"""Build a deterministic manifest for already split chapter text files."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path


def build_manifest(
    chapter_dir: Path,
    *,
    titles: dict[str, str] | None = None,
) -> dict[str, object]:
    files = sorted(chapter_dir.glob("chapter_*.txt"))
    chapters: list[dict[str, object]] = []
    for index, path in enumerate(files):
        with path.open("r", encoding="utf-8", newline="") as stream:
            text = stream.read()
        first_line = next(
            (line.strip() for line in text.splitlines() if line.strip()),
            path.stem,
        )
        chapters.append(
            {
                "chapter_id": path.stem,
                "title": (titles or {}).get(path.stem, first_line),
                "path": path.name,
                "character_count": len(text),
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "previous_id": files[index - 1].stem if index > 0 else None,
                "next_id": (
                    files[index + 1].stem
                    if index + 1 < len(files)
                    else None
                ),
            }
        )
    return {
        "format_version": 1,
        "chapter_count": len(chapters),
        "chapters": chapters,
    }


def write_manifest(
    chapter_dir: Path,
    *,
    titles: dict[str, str] | None = None,
) -> Path:
    manifest = build_manifest(chapter_dir, titles=titles)
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
