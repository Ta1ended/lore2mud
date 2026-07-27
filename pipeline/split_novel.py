"""Split a local Chinese plain-text novel into chapter files.

The source file is read-only. Output should normally be an ignored local path
such as ``novel/chapters``.
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

try:
    from pipeline.build_manifest import write_manifest
except ModuleNotFoundError:
    from build_manifest import write_manifest


CHAPTER_HEADING = re.compile(
    r"(?m)^[ \t]*"
    r"(第[0-9零〇一二三四五六七八九十百千万两]+"
    r"[章节回卷集部](?:[ \t]+[^\r\n]*)?)"
    r"[ \t]*\r?$"
)


@dataclass(frozen=True, slots=True)
class Chapter:
    chapter_id: str
    title: str
    text: str


def split_text(text: str) -> list[Chapter]:
    matches = list(CHAPTER_HEADING.finditer(text))
    if not matches:
        raise ValueError("未识别到章节标题；请检查标题格式或调整正则表达式")

    chapters: list[Chapter] = []
    for index, match in enumerate(matches):
        start = 0 if index == 0 else match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        chapter_text = text[start:end]
        chapters.append(
            Chapter(
                chapter_id=f"chapter_{index + 1:06d}",
                title=match.group(1).strip(),
                text=chapter_text,
            )
        )
    return chapters


def split_file(source: Path, output_dir: Path) -> list[Path]:
    source = source.resolve()
    output_dir = output_dir.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"原文文件不存在：{source}")
    if output_dir == source.parent or source in output_dir.parents:
        raise ValueError("输出目录不得覆盖或包含原文文件")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"输出目录不是空目录：{output_dir}")

    with source.open("r", encoding="utf-8-sig", newline="") as stream:
        text = stream.read()
    chapters = split_text(text)
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for chapter in chapters:
        path = output_dir / f"{chapter.chapter_id}.txt"
        with path.open("w", encoding="utf-8", newline="") as stream:
            stream.write(chapter.text)
        written.append(path)
    write_manifest(
        output_dir,
        titles={
            chapter.chapter_id: chapter.title
            for chapter in chapters
        },
    )
    return written


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="本地 UTF-8/TXT 小说原文")
    parser.add_argument("output_dir", type=Path, help="章节输出目录")
    args = parser.parse_args(argv)
    try:
        written = split_file(args.source, args.output_dir)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"拆章失败：{exc}\n")
    print(f"已拆分 {len(written)} 章，输出：{args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
