from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.check_repo_safety import inspect_candidate, scan_repository


class RepositorySafetyTests(unittest.TestCase):
    def test_private_novel_directory_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            relative = Path("novel/raw/chapter_001.txt")
            path = root / relative
            path.parent.mkdir(parents=True)
            path.write_text("private text", encoding="utf-8")

            violations = inspect_candidate(root, relative)
            self.assertTrue(
                any("私有内容目录" in item.reason for item in violations)
            )

    def test_ebook_and_large_file_are_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ebook = Path("reference/book.epub")
            ebook_path = root / ebook
            ebook_path.parent.mkdir(parents=True)
            ebook_path.write_bytes(b"1234")
            large = Path("assets/large.bin")
            large_path = root / large
            large_path.parent.mkdir(parents=True)
            large_path.write_bytes(b"x" * 20)

            ebook_violations = inspect_candidate(root, ebook, max_size=10)
            large_violations = inspect_candidate(root, large, max_size=10)
            self.assertTrue(
                any("文件类型" in item.reason for item in ebook_violations)
            )
            self.assertTrue(
                any("超过限制" in item.reason for item in large_violations)
            )

    def test_safe_candidates_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            safe = Path("src/example.py")
            path = root / safe
            path.parent.mkdir(parents=True)
            path.write_text("print('safe')\n", encoding="utf-8")
            self.assertEqual(
                scan_repository(root, candidates=[safe]),
                [],
            )


if __name__ == "__main__":
    unittest.main()
