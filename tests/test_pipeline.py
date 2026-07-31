from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pipeline.split_novel import split_file, split_text


# ── helpers ──────────────────────────────────────────────────────────────────

def _write_bytes(path: Path, data: bytes) -> None:
    path.write_bytes(data)


def _gbk(text: str) -> bytes:
    return text.encode("gbk")


def _gb18030(text: str) -> bytes:
    return text.encode("gb18030")


FIXTURE_GBK = (
    "第一卷 初入江湖\r\n"
    "简介文字\r\n"
    "第一章 少年\r\n"
    "少年正文。\r\n"
    "第二章 出发\r\n"
    "出发正文。\r\n"
    "第二卷 远行\r\n"
    "第三章 山路\r\n"
    "山路正文。\r\n"
)

FIXTURE_DUP = (
    "第一卷 上卷\r\n"
    "第一章 同名章节\r\n"
    "上卷正文一。\r\n"
    "第二章 不同标题\r\n"
    "上卷正文二。\r\n"
    "第二卷 下卷\r\n"
    "第一章 同名章节\r\n"
    "下卷正文一。\r\n"
    "第二章 不同标题\r\n"
    "下卷正文二。\r\n"
)


# ── split_text unit tests ────────────────────────────────────────────────────

class SplitTextTests(unittest.TestCase):
    def test_basic_split(self) -> None:
        source = (
            "前言\r\n"
            "第一章 雾中来客\r\n"
            "正文一。\r\n"
            "第二章 渡台微光\r\n"
            "正文二。\r\n"
        )
        chapters = split_text(source)
        self.assertEqual(len(chapters), 2)
        self.assertEqual(chapters[0].chapter_id, "chapter_000001")
        self.assertEqual(chapters[0].title, "第一章 雾中来客")
        self.assertEqual(chapters[0].source_chapter_label, "第一章")
        self.assertEqual(chapters[0].source_title, "雾中来客")
        self.assertEqual(chapters[1].chapter_id, "chapter_000002")
        self.assertEqual(chapters[1].title, "第二章 渡台微光")

    def test_preserves_full_source(self) -> None:
        source = (
            "简短前言\n"
            "第一章 雾中来客\n"
            "第一章正文。\n"
            "第二章 渡台微光\n"
            "第二章正文。\n"
        )
        chapters = split_text(source)
        self.assertEqual("".join(ch.text for ch in chapters), source)

    def test_no_chapters_raises(self) -> None:
        with self.assertRaises(ValueError):
            split_text("只有正文，没有章节标题。")

    def test_volume_label_not_a_split_point(self) -> None:
        chapters = split_text(FIXTURE_GBK.replace("\r\n", "\n"))
        # 3 chapters, not 5 (volumes don't split)
        self.assertEqual(len(chapters), 3)
        self.assertEqual(chapters[0].title, "第一章 少年")
        self.assertEqual(chapters[1].title, "第二章 出发")
        self.assertEqual(chapters[2].title, "第三章 山路")

    def test_volume_label_propagated(self) -> None:
        chapters = split_text(FIXTURE_GBK.replace("\r\n", "\n"))
        self.assertEqual(chapters[0].volume_label, "第一卷 初入江湖")
        self.assertEqual(chapters[1].volume_label, "第一卷 初入江湖")
        self.assertEqual(chapters[2].volume_label, "第二卷 远行")

    def test_duplicate_chapter_numbers_no_conflict(self) -> None:
        chapters = split_text(FIXTURE_DUP.replace("\r\n", "\n"))
        self.assertEqual(len(chapters), 4)
        ids = [ch.chapter_id for ch in chapters]
        self.assertEqual(len(ids), len(set(ids)), "chapter_ids must be unique")
        # All titles are "第一章 同名章节" or "第二章 不同标题" — duplicates allowed
        self.assertEqual(chapters[0].title, chapters[2].title)

    def test_source_offset_and_line(self) -> None:
        source = "前言\n第一章 标题\n正文\n第二章 标题\n正文\n"
        chapters = split_text(source)
        # chapter 1 starts at offset of "第"
        self.assertEqual(chapters[0].source_offset, source.index("第一章"))
        self.assertEqual(chapters[0].source_line, 2)
        # chapter 2
        self.assertEqual(chapters[1].source_offset, source.index("第二章"))
        self.assertEqual(chapters[1].source_line, 4)

    def test_chapter_without_subtitle(self) -> None:
        source = "第一章\n正文\n第二章 标题\n正文\n"
        chapters = split_text(source)
        self.assertEqual(chapters[0].source_chapter_label, "第一章")
        self.assertEqual(chapters[0].source_title, "")
        self.assertEqual(chapters[0].title, "第一章")


# ── split_file integration tests ─────────────────────────────────────────────

class SplitFileEncodingTests(unittest.TestCase):
    def _run_split(
        self, data: bytes, encoding: str
    ) -> tuple[list[Path], dict]:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.txt"
            _write_bytes(source, data)
            output = root / "chapters"
            paths = split_file(source, output, encoding=encoding)
            manifest = json.loads(
                (output / "manifest.json").read_text(encoding="utf-8")
            )
            return paths, manifest

    def test_gbk_file(self) -> None:
        paths, manifest = self._run_split(_gbk(FIXTURE_GBK), "gbk")
        self.assertEqual(len(paths), 3)
        self.assertEqual(manifest["chapter_count"], 3)
        self.assertEqual(manifest["source_encoding"], "gbk")

    def test_gb18030_file(self) -> None:
        paths, manifest = self._run_split(_gb18030(FIXTURE_GBK), "gb18030")
        self.assertEqual(len(paths), 3)
        self.assertEqual(manifest["source_encoding"], "gb18030")

    def test_utf8_file(self) -> None:
        data = FIXTURE_GBK.replace("\r\n", "\n").encode("utf-8")
        paths, manifest = self._run_split(data, "utf-8")
        self.assertEqual(len(paths), 3)
        self.assertEqual(manifest["source_encoding"], "utf-8")

    def test_wrong_encoding_raises(self) -> None:
        # GBK bytes decoded as utf-8 → UnicodeDecodeError
        with self.assertRaises(UnicodeDecodeError):
            self._run_split(_gbk(FIXTURE_GBK), "utf-8")

    def test_unsupported_encoding_raises(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.txt"
            _write_bytes(source, b"hello")
            with self.assertRaises(ValueError):
                split_file(source, root / "out", encoding="latin-1")


class ManifestFieldTests(unittest.TestCase):
    def test_manifest_has_all_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.txt"
            _write_bytes(source, _gbk(FIXTURE_GBK))
            output = root / "chapters"
            split_file(source, output, encoding="gbk")
            manifest = json.loads(
                (output / "manifest.json").read_text(encoding="utf-8")
            )

        self.assertEqual(manifest["format_version"], 2)
        self.assertEqual(manifest["source_encoding"], "gbk")
        self.assertEqual(manifest["chapter_count"], 3)

        required = {
            "chapter_id", "title", "source_chapter_label", "source_title",
            "volume_label", "source_offset", "source_line", "path",
            "character_count", "sha256", "previous_id", "next_id",
        }
        for ch in manifest["chapters"]:
            self.assertTrue(
                required.issubset(ch.keys()),
                f"Missing fields: {required - ch.keys()}",
            )

        # First chapter has no previous
        self.assertIsNone(manifest["chapters"][0]["previous_id"])
        self.assertEqual(manifest["chapters"][0]["next_id"], "chapter_000002")
        # Last chapter has no next
        self.assertIsNone(manifest["chapters"][2]["next_id"])

    def test_manifest_volume_labels(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.txt"
            _write_bytes(source, _gbk(FIXTURE_GBK))
            output = root / "chapters"
            split_file(source, output, encoding="gbk")
            manifest = json.loads(
                (output / "manifest.json").read_text(encoding="utf-8")
            )

        self.assertEqual(manifest["chapters"][0]["volume_label"], "第一卷 初入江湖")
        self.assertEqual(manifest["chapters"][1]["volume_label"], "第一卷 初入江湖")
        self.assertEqual(manifest["chapters"][2]["volume_label"], "第二卷 远行")

    def test_manifest_source_offset_line(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.txt"
            _write_bytes(source, _gbk(FIXTURE_GBK))
            output = root / "chapters"
            split_file(source, output, encoding="gbk")
            manifest = json.loads(
                (output / "manifest.json").read_text(encoding="utf-8")
            )

        ch0 = manifest["chapters"][0]
        ch1 = manifest["chapters"][1]
        # source_offset is the character position of the heading in decoded text
        self.assertGreaterEqual(ch0["source_offset"], 0)
        self.assertGreater(ch1["source_offset"], ch0["source_offset"])
        # source_line should be positive integers in order
        self.assertGreater(ch0["source_line"], 0)
        self.assertGreater(ch1["source_line"], ch0["source_line"])


class ReconstructionTests(unittest.TestCase):
    def test_chapters_concat_equals_source(self) -> None:
        """All chapter texts concatenated must equal the decoded source."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.txt"
            _write_bytes(source, _gbk(FIXTURE_GBK))
            output = root / "chapters"
            split_file(source, output, encoding="gbk")

            reconstructed = ""
            for path in sorted(output.glob("chapter_*.txt")):
                with path.open("r", encoding="utf-8", newline="") as fh:
                    reconstructed += fh.read()

            original = _gbk(FIXTURE_GBK).decode("gbk")
            self.assertEqual(reconstructed, original)

    def test_gb18030_reconstruction(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.txt"
            _write_bytes(source, _gb18030(FIXTURE_GBK))
            output = root / "chapters"
            split_file(source, output, encoding="gb18030")

            reconstructed = ""
            for path in sorted(output.glob("chapter_*.txt")):
                with path.open("r", encoding="utf-8", newline="") as fh:
                    reconstructed += fh.read()

            original = _gb18030(FIXTURE_GBK).decode("gb18030")
            self.assertEqual(reconstructed, original)


class DuplicateChapterTests(unittest.TestCase):
    def test_duplicate_numbers_different_volumes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.txt"
            _write_bytes(source, _gbk(FIXTURE_DUP))
            output = root / "chapters"
            paths = split_file(source, output, encoding="gbk")
            manifest = json.loads(
                (output / "manifest.json").read_text(encoding="utf-8")
            )

        self.assertEqual(len(paths), 4)
        self.assertEqual(manifest["chapter_count"], 4)

        # chapter_ids are sequential, no collision
        ids = [ch["chapter_id"] for ch in manifest["chapters"]]
        self.assertEqual(ids, [
            "chapter_000001", "chapter_000002",
            "chapter_000003", "chapter_000004",
        ])

        # Volume labels differ
        self.assertEqual(manifest["chapters"][0]["volume_label"], "第一卷 上卷")
        self.assertEqual(manifest["chapters"][2]["volume_label"], "第二卷 下卷")


if __name__ == "__main__":
    unittest.main()
