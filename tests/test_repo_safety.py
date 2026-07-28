from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.check_repo_safety import inspect_candidate, scan_history, scan_repository


class RepositorySafetyTests(unittest.TestCase):
    def test_private_directories_and_extensions_are_blocked(self) -> None:
        blocked = (
            "novel/raw/chapter.txt",
            "novel/chapters/chapter.txt",
            "novel/summaries/chapter.json",
            "novel/canon/entities.json",
            "novel/extractions/chapter.json",
            "private_content/pack.json",
            "generated_content/pack.json",
            "saves/slot.json",
            "models/model.bin",
            "vector_store/index.bin",
            "rag_index/index.bin",
            "faiss_index/index.bin",
            "chroma/index.bin",
            "logs/game.log",
            "config/local.toml",
            "state.sqlite3",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for raw_path in blocked:
                relative = Path(raw_path)
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("private text", encoding="utf-8")
                self.assertTrue(inspect_candidate(root, relative), raw_path)

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

            self.assertTrue(inspect_candidate(root, ebook, max_size=10))
            self.assertTrue(inspect_candidate(root, large, max_size=10))

    def test_likely_credential_patterns_are_blocked(self) -> None:
        samples = (
            b"-----BEGIN " + b"PRIVATE KEY-----",
            b"gh" + b"p_" + b"abcdefghijklmnopqrstuvwxyz0123456789AB",
            b"AK" + b"IA" + b"ABCDEFGHIJKLMNOP",
            b"aws_" + b"secret_access_key" + b" = abcdefghijklmnopqrstuvwxyz0123456789ABCD",
            b"xox" + b"b-" + b"1234567890-abcdefghijklmnop",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for index, sample in enumerate(samples):
                relative = Path(f"src/sample_{index}.txt")
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(sample)
                self.assertTrue(inspect_candidate(root, relative), sample)

    def test_force_added_ignored_file_is_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._run_git(root, "init")
            (root / ".gitignore").write_text("saves/\n", encoding="utf-8")
            path = root / "saves" / "slot.json"
            path.parent.mkdir()
            path.write_text("{}", encoding="utf-8")
            self._run_git(root, "add", "-f", "saves/slot.json")

            violations = scan_repository(root)

            self.assertTrue(any(item.path == "saves/slot.json" for item in violations))

    def test_history_scans_old_paths_and_blob_contents(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._run_git(root, "init")
            old = root / "novel" / "raw" / "chapter.txt"
            old.parent.mkdir(parents=True)
            old.write_text("historic", encoding="utf-8")
            self._run_git(root, "add", ".")
            self._commit(root, "unsafe")
            old.unlink()
            safe = root / "src" / "safe.txt"
            safe.parent.mkdir()
            safe.write_bytes(b"-----BEGIN " + b"PRIVATE KEY-----")
            self._run_git(root, "add", "-A")
            self._commit(root, "renamed")

            violations = scan_history(root)

            self.assertTrue(any(item.path == "novel/raw/chapter.txt" for item in violations))
            self.assertTrue(any("私钥" in item.reason for item in violations))

    def test_safe_candidates_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            safe = Path("src/example.py")
            path = root / safe
            path.parent.mkdir(parents=True)
            path.write_text("print('safe')\n", encoding="utf-8")
            self.assertEqual(scan_repository(root, candidates=[safe]), [])

    @staticmethod
    def _run_git(root: Path, *arguments: str) -> None:
        subprocess.run(
            ["git", *arguments], cwd=root, check=True, capture_output=True
        )

    @classmethod
    def _commit(cls, root: Path, message: str) -> None:
        cls._run_git(
            root,
            "-c",
            "user.name=Safety Test",
            "-c",
            "user.email=safety@example.invalid",
            "commit",
            "-m",
            message,
        )


if __name__ == "__main__":
    unittest.main()
