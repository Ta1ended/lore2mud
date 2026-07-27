from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pipeline.split_novel import split_file, split_text


class NovelPipelineTests(unittest.TestCase):
    def test_split_text_preserves_full_source(self) -> None:
        source = (
            "简短前言\n"
            "第一章 雾中来客\n"
            "第一章正文。\n"
            "第二章 渡台微光\n"
            "第二章正文。\n"
        )
        chapters = split_text(source)
        self.assertEqual(len(chapters), 2)
        self.assertEqual(chapters[0].chapter_id, "chapter_000001")
        self.assertEqual(chapters[1].title, "第二章 渡台微光")
        self.assertEqual("".join(chapter.text for chapter in chapters), source)

    def test_split_text_requires_recognizable_heading(self) -> None:
        with self.assertRaises(ValueError):
            split_text("只有正文，没有章节标题。")

    def test_split_file_preserves_text_and_manifest_title(self) -> None:
        source_text = (
            "简短前言\r\n"
            "第一章 雾中来客\r\n"
            "正文一。\r\n"
            "第二章 渡台微光\r\n"
            "正文二。\r\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.txt"
            with source.open("w", encoding="utf-8", newline="") as stream:
                stream.write(source_text)
            output = root / "chapters"

            paths = split_file(source, output)
            reconstructed = ""
            for path in paths:
                with path.open("r", encoding="utf-8", newline="") as stream:
                    reconstructed += stream.read()
            manifest = json.loads(
                (output / "manifest.json").read_text(encoding="utf-8")
            )

            self.assertEqual(reconstructed, source_text)
            self.assertEqual(manifest["chapter_count"], 2)
            self.assertEqual(
                manifest["chapters"][0]["title"],
                "第一章 雾中来客",
            )


if __name__ == "__main__":
    unittest.main()
