"""Tests for the Windows candidate build and repository-external launcher."""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
PYINSTALLER_AVAILABLE = importlib.util.find_spec("PyInstaller") is not None


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILD = _load("windows_build_candidate", ROOT / "packaging/windows/build_candidate.py")
VERIFY = _load("windows_verify_candidate", ROOT / "packaging/windows/verify_candidate.py")


class WindowsPackagingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.artifact = BUILD.build(
            self.root / "first",
            allow_dirty=True,
            runtime="zipapp",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_build_is_byte_reproducible(self) -> None:
        second = BUILD.build(
            self.root / "second",
            allow_dirty=True,
            runtime="zipapp",
        )
        self.assertEqual(self.artifact.read_bytes(), second.read_bytes())

    def test_manifest_covers_only_public_runtime_files(self) -> None:
        metadata = VERIFY.verify_contents(self.artifact)
        expected_version = json.loads(
            (ROOT / "examples/original_demo/pack.json").read_text(encoding="utf-8")
        )["version"]
        self.assertEqual(expected_version, "0.9.0")
        self.assertEqual(metadata["format"], 2)
        self.assertEqual(metadata["runtime"], "zipapp")
        self.assertEqual(metadata["default_mode"], "web")
        self.assertEqual(metadata["python_requires"], ">=3.11")
        self.assertIsNone(metadata["bundled_python_version"])
        self.assertIsNone(metadata["pyinstaller_version"])
        self.assertEqual(metadata["content_pack_version"], expected_version)
        self.assertIn("-windows-zipapp-", self.artifact.name)
        self.assertIn(f"-content-{expected_version}", self.artifact.name)
        names = set(metadata["files"])
        self.assertIn("lore2mud.pyz", names)
        self.assertIn("original_demo/pack.json", names)
        self.assertIn("Start Lore2MUD.cmd", names)
        self.assertIn("LICENSE", names)
        self.assertFalse(any("pyinstaller" in name.casefold() for name in names))
        self.assertFalse(any(name.startswith(("tests/", "pipeline/", "novel/")) for name in names))
        self.assertFalse(any("private" in name.casefold() for name in names))

        with zipfile.ZipFile(self.artifact) as candidate:
            with zipfile.ZipFile(candidate.open("lore2mud.pyz")) as app:
                app_names = set(app.namelist())
                for asset_name in BUILD.WEB_ASSETS:
                    packaged = app.read(f"lore2mud/web/static/{asset_name}")
                    source = (
                        ROOT / "src" / "lore2mud" / "web" / "static" / asset_name
                    ).read_bytes()
                    self.assertEqual(packaged, source)
        self.assertIn("lore2mud/cli.py", app_names)
        self.assertNotIn("pipeline/__init__.py", app_names)

    def test_zipapp_preserves_web_resource_types(self) -> None:
        source_root = self.root / "resource-source"
        static = source_root / "src" / "lore2mud" / "web" / "static"
        static.mkdir(parents=True)
        resources = {
            "index.html": "<main>demo</main>\n",
            "styles.css": "main { display: block; }\n",
            "app.js": "console.log('demo');\n",
            "scene.svg": "<svg xmlns=\"http://www.w3.org/2000/svg\"></svg>\n",
        }
        for name, content in resources.items():
            (static / name).write_text(content, encoding="utf-8")
        (source_root / "src" / "lore2mud" / "__init__.py").write_text(
            "\n", encoding="utf-8"
        )
        (source_root / "src" / "lore2mud" / "cli.py").write_text(
            "def main():\n    return 0\n", encoding="utf-8"
        )
        app = self.root / "resources.pyz"
        tracked = frozenset(
            BUILD.PurePosixPath(f"src/lore2mud/web/static/{name}")
            for name in resources
        ) | {
            BUILD.PurePosixPath("src/lore2mud/__init__.py"),
            BUILD.PurePosixPath("src/lore2mud/cli.py"),
        }
        with (
            mock.patch.object(BUILD, "ROOT", source_root),
            mock.patch.object(BUILD, "_tracked_paths", return_value=tracked),
        ):
            BUILD._build_pyz(app)

        VERIFY._verify_pyz(app.read_bytes())
        with zipfile.ZipFile(app) as archive:
            names = set(archive.namelist())
        self.assertTrue(
            {
                f"lore2mud/web/static/{name}"
                for name in resources
            }.issubset(names)
        )

    def test_zipapp_omits_untracked_package_files(self) -> None:
        source_root = self.root / "tracked-source"
        package = source_root / "src" / "lore2mud"
        package.mkdir(parents=True)
        (package / "cli.py").write_text("tracked = True\n", encoding="utf-8")
        (package / "ignored_secret.py").write_text("secret = True\n", encoding="utf-8")
        app = self.root / "tracked.pyz"
        tracked = frozenset({BUILD.PurePosixPath("src/lore2mud/cli.py")})
        with (
            mock.patch.object(BUILD, "ROOT", source_root),
            mock.patch.object(BUILD, "_tracked_paths", return_value=tracked),
        ):
            BUILD._build_pyz(app)
        with zipfile.ZipFile(app) as archive:
            self.assertIn("lore2mud/cli.py", archive.namelist())
            self.assertNotIn("lore2mud/ignored_secret.py", archive.namelist())

    def test_pyinstaller_web_data_uses_only_tracked_public_resources(self) -> None:
        tracked = frozenset({
            BUILD.PurePosixPath("src/lore2mud/web/__init__.py"),
            BUILD.PurePosixPath("src/lore2mud/web/static/index.html"),
            BUILD.PurePosixPath("src/lore2mud/web/static/styles.css"),
            BUILD.PurePosixPath("src/lore2mud/web/static/app.js"),
            BUILD.PurePosixPath("src/lore2mud/web/static/future.svg"),
        })
        with mock.patch.object(BUILD, "_tracked_paths", return_value=tracked):
            data = BUILD._tracked_pyinstaller_web_data()
        self.assertEqual(data, {
            "_internal/lore2mud/web/static/index.html",
            "_internal/lore2mud/web/static/styles.css",
            "_internal/lore2mud/web/static/app.js",
            "_internal/lore2mud/web/static/future.svg",
        })

    def test_sidecar_matches_candidate(self) -> None:
        VERIFY.verify_sidecar(self.artifact)
        sidecar = self.artifact.with_suffix(self.artifact.suffix + ".sha256")
        sidecar.write_text("0" * 64 + f"  {self.artifact.name}\n", encoding="ascii")
        with self.assertRaisesRegex(VERIFY.VerificationError, "sidecar mismatch"):
            VERIFY.verify_sidecar(self.artifact)

    def test_manifest_rejects_tampered_file(self) -> None:
        tampered = self.root / "tampered" / self.artifact.name
        tampered.parent.mkdir()
        with zipfile.ZipFile(self.artifact) as source, zipfile.ZipFile(tampered, "w") as output:
            for info in source.infolist():
                content = b"tampered" if info.filename == "lore2mud.pyz" else source.read(info)
                output.writestr(info, content)
        with self.assertRaisesRegex(VERIFY.VerificationError, "sha256 mismatch"):
            VERIFY.verify_contents(tampered)

    def test_rejects_archive_path_traversal(self) -> None:
        unsafe = self.root / "unsafe.zip"
        with zipfile.ZipFile(unsafe, "w") as archive:
            archive.writestr("../outside.txt", b"no")
        with self.assertRaisesRegex(VERIFY.VerificationError, "unsafe archive path"):
            VERIFY.verify_contents(unsafe)

    def test_rejects_noncanonical_archive_paths(self) -> None:
        for name in ("folder/./file.txt", "folder//file.txt"):
            with self.subTest(name=name):
                unsafe = self.root / (str(abs(hash(name))) + ".zip")
                with zipfile.ZipFile(unsafe, "w") as archive:
                    archive.writestr(name, b"no")
                with self.assertRaisesRegex(
                    VERIFY.VerificationError,
                    "unsafe archive path",
                ):
                    VERIFY.verify_contents(unsafe)

    def test_rejects_windows_special_archive_paths(self) -> None:
        for name in ("C:relative.txt", "folder/file.txt:stream", "NUL.txt", "trailing. "):
            with self.subTest(name=name):
                unsafe = self.root / (str(abs(hash(name))) + ".zip")
                with zipfile.ZipFile(unsafe, "w") as archive:
                    archive.writestr(name, b"no")
                with self.assertRaisesRegex(VERIFY.VerificationError, "unsafe archive path"):
                    VERIFY.verify_contents(unsafe)

    def test_rejects_case_colliding_paths(self) -> None:
        unsafe = self.root / "collision.zip"
        with zipfile.ZipFile(unsafe, "w") as archive:
            archive.writestr("file.txt", b"one")
            archive.writestr("FILE.txt", b"two")
        with self.assertRaisesRegex(VERIFY.VerificationError, "case-colliding"):
            VERIFY.verify_contents(unsafe)

    @unittest.skipUnless(os.name == "nt", "Windows launcher smoke")
    def test_repository_external_cold_start(self) -> None:
        completed = VERIFY.cold_start(self.artifact)
        self.assertEqual(completed.returncode, 0)

    @unittest.skipUnless(
        os.name == "nt" and PYINSTALLER_AVAILABLE,
        "PyInstaller Windows build toolchain is not installed",
    )
    def test_pyinstaller_candidate_resources_and_cold_start(self) -> None:
        artifact = BUILD.build(
            self.root / "pyinstaller",
            allow_dirty=True,
            runtime="pyinstaller",
        )
        metadata = VERIFY.verify_contents(artifact)
        self.assertEqual(metadata["runtime"], "pyinstaller")
        self.assertEqual(metadata["default_mode"], "web")
        self.assertIsNone(metadata["python_requires"])
        self.assertEqual(
            metadata["bundled_python_version"],
            ".".join(str(part) for part in BUILD.sys.version_info[:3]),
        )
        self.assertEqual(metadata["pyinstaller_version"], "6.21.0")
        self.assertEqual(metadata["content_pack_version"], "0.9.0")
        self.assertIn("-windows-pyinstaller-", artifact.name)

        with zipfile.ZipFile(artifact) as candidate:
            self.assertEqual(candidate.read("runtime/lore2mud.exe")[:2], b"MZ")
            for asset_name in BUILD.WEB_ASSETS:
                packaged = candidate.read(
                    f"runtime/_internal/lore2mud/web/static/{asset_name}"
                )
                source = (
                    ROOT / "src" / "lore2mud" / "web" / "static" / asset_name
                ).read_bytes()
                self.assertEqual(packaged, source)

        completed = VERIFY.cold_start(artifact)
        self.assertEqual(completed.returncode, 0)


if __name__ == "__main__":
    unittest.main()
