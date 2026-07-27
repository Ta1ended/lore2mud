"""Split a local Chinese plain-text novel into chapter files.

The source file is read-only.  Output should normally be an ignored local path
such as ``novel/chapters``.

Supported encodings: utf-8-sig, utf-8, gbk, gb18030.
Only "第X章" headings create chapter files; "第X卷" headings update volume
metadata but do not split.
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

# Only "第X章" lines are chapter split-points.
CHAPTER_RE = re.compile(
    r"(?m)^[ \t]*"
    r"(第[0-9零〇一二三四五六七八九十百千万两]+章)"
    r"(?:[ \t]+([^\r\n]*?))?"
    r"[ \t]*\r?$"
)

# "第X卷" lines update volume metadata only.
VOLUME_RE = re.compile(
    r"(?m)^[ \t]*"
    r"(第[0-9零〇一二三四五六七八九十百千万两]+卷"
    r"(?:[ \t]+[^\r\n]*)?)"
    r"[ \t]*\r?$"
)

SUPPORTED_ENCODINGS = frozenset({"utf-8-sig", "utf-8", "gbk", "gb18030"})


@dataclass(frozen=True, slots=True)
class Chapter:
    chapter_id: str
    title: str
    source_chapter_label: str
    source_title: str
    volume_label: str | None
    source_offset: int
    source_line: int
    text: str


def _line_number(text: str, offset: int) -> int:
    """Return 1-based line number for *offset* in *text*."""
    return text.count("\n", 0, offset) + 1


def split_text(
    text: str,
    *,
    source_encoding: str = "utf-8-sig",
) -> list[Chapter]:
    """Split decoded text into chapters.

    Raises :class:`ValueError` when no chapter headings are found.
    """
    chapter_matches = list(CHAPTER_RE.finditer(text))
    if not chapter_matches:
        raise ValueError("未识别到章节标题（第X章）；请检查标题格式或调整正则表达式")

    # Pre-scan volume labels keyed by character offset.
    volume_at: dict[int, str] = {}
    for vol_m in VOLUME_RE.finditer(text):
        volume_at[vol_m.start()] = vol_m.group(1).strip()

    chapters: list[Chapter] = []
    current_volume: str | None = None

    for index, match in enumerate(chapter_matches):
        # Update volume to the latest one appearing before this chapter.
        for vol_offset, vol_label in sorted(volume_at.items()):
            if vol_offset < match.start():
                current_volume = vol_label
            else:
                break

        # First chapter includes any preamble text before the heading.
        start = 0 if index == 0 else match.start()
        end = (
            chapter_matches[index + 1].start()
            if index + 1 < len(chapter_matches)
            else len(text)
        )
        chapter_text = text[start:end]

        label = match.group(1).strip()  # "第一章"
        raw_title = match.group(2)      # "雾岭小村" or None
        source_title = raw_title.strip() if raw_title else ""
        full_title = f"{label} {source_title}".strip() if source_title else label

        chapters.append(
            Chapter(
                chapter_id=f"chapter_{index + 1:06d}",
                title=full_title,
                source_chapter_label=label,
                source_title=source_title,
                volume_label=current_volume,
                source_offset=match.start(),
                source_line=_line_number(text, match.start()),
                text=chapter_text,
            )
        )
    return chapters


def _read_source(source: Path, encoding: str) -> str:
    """Read *source* with the given *encoding* (strict mode).

    Raises :class:`UnicodeDecodeError` on invalid bytes.
    """
    with source.open("rb") as fh:
        raw = fh.read()
    return raw.decode(encoding)


def split_file(
    source: Path,
    output_dir: Path,
    *,
    encoding: str = "utf-8-sig",
) -> list[Path]:
    """Read *source* with *encoding*, split, and write chapters + manifest.

    The source file is never modified.  *output_dir* must be empty or absent.
    """
    encoding = encoding.lower().strip()
    if encoding not in SUPPORTED_ENCODINGS:
        raise ValueError(
            f"不支持的编码 {encoding!r}，可选：{', '.join(sorted(SUPPORTED_ENCODINGS))}"
        )

    source = source.resolve()
    output_dir = output_dir.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"原文文件不存在：{source}")
    if output_dir == source.parent or source in output_dir.parents:
        raise ValueError("输出目录不得覆盖或包含原文文件")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"输出目录不是空目录：{output_dir}")

    text = _read_source(source, encoding)
    chapters = split_text(text, source_encoding=encoding)

    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for chapter in chapters:
        path = output_dir / f"{chapter.chapter_id}.txt"
        with path.open("w", encoding="utf-8", newline="") as stream:
            stream.write(chapter.text)
        written.append(path)

    write_manifest(
        output_dir,
        chapters=chapters,
        source_encoding=encoding,
    )
    return written


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="本地小说原文（只读）")
    parser.add_argument("output_dir", type=Path, help="章节输出目录")
    parser.add_argument(
        "--encoding",
        default="utf-8-sig",
        choices=sorted(SUPPORTED_ENCODINGS),
        help="源文件编码（默认 utf-8-sig）",
    )
    args = parser.parse_args(argv)
    try:
        written = split_file(
            args.source, args.output_dir, encoding=args.encoding
        )
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        parser.exit(2, f"拆章失败：{exc}\n")
    print(f"已拆分 {len(written)} 章，输出：{args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
