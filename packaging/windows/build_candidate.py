"""Build a deterministic, Python-only Windows candidate bundle.

The bundle is intentionally a zipapp plus the original public demo pack. It
does not install anything and never reads ignored/private project directories.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import subprocess
import tempfile
import tomllib
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
ASSETS = Path(__file__).resolve().parent / "assets"
ZIP_EPOCH = (2024, 1, 1, 0, 0, 0)
PACKAGE_SUFFIXES = frozenset({
    ".py", ".html", ".css", ".js", ".svg",
    ".png", ".jpg", ".jpeg", ".webp", ".woff2",
})
CONTENT_FILES = frozenset({
    "README.md",
    "characters.json",
    "dialogues.json",
    "items.json",
    "monsters.json",
    "pack.json",
    "quests.json",
    "rooms.json",
    "shops.json",
})
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def _version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


def _content_pack_version() -> str:
    pack_path = ROOT / "examples" / "original_demo" / "pack.json"
    try:
        version = json.loads(pack_path.read_text(encoding="utf-8"))["version"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot determine original_demo version: {exc}") from exc
    if not isinstance(version, str) or not version:
        raise SystemExit("original_demo version must be a non-empty string")
    return version


def _git_commit(*, allow_dirty: bool) -> str:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
            capture_output=True, text=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--short"], cwd=ROOT, check=True,
            capture_output=True, text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"cannot determine Git provenance: {exc}") from exc
    if dirty and not allow_dirty:
        raise SystemExit("working tree is dirty; use --allow-dirty for a local candidate")
    return commit + ("-dirty" if dirty else "")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _tracked_paths(prefix: str) -> frozenset[PurePosixPath]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--", prefix],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"cannot enumerate tracked runtime files: {exc}") from exc
    try:
        names = result.stdout.decode("utf-8").split("\0")
    except UnicodeDecodeError as exc:
        raise SystemExit("tracked runtime paths are not valid UTF-8") from exc
    return frozenset(PurePosixPath(name) for name in names if name)


def _require_regular_file(path: Path, *, label: str) -> None:
    try:
        info = path.lstat()
    except OSError as exc:
        raise SystemExit(f"cannot inspect {label}: {exc}") from exc
    attributes = getattr(info, "st_file_attributes", 0)
    if (
        not stat.S_ISREG(info.st_mode)
        or path.is_symlink()
        or attributes & _REPARSE_POINT
        or info.st_nlink != 1
    ):
        raise SystemExit(f"{label} must be one ordinary, unaliased file")


def _zip_write(destination: Path, files: dict[str, Path], extra: dict[str, bytes] | None = None) -> None:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 0
            info.external_attr = 0x20
            archive.writestr(info, files[name].read_bytes())
        for name in sorted(extra or {}):
            info = zipfile.ZipInfo(name, ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 0
            info.external_attr = 0x20
            archive.writestr(info, extra[name])


def _build_pyz(path: Path) -> None:
    files: dict[str, Path] = {}
    tracked = _tracked_paths("src/lore2mud")
    for repository_path in sorted(tracked, key=PurePosixPath.as_posix):
        if repository_path.suffix.casefold() not in PACKAGE_SUFFIXES:
            continue
        source = ROOT.joinpath(*repository_path.parts)
        _require_regular_file(source, label=repository_path.as_posix())
        files[source.relative_to(ROOT / "src").as_posix()] = source
    if PurePosixPath("src/lore2mud/cli.py") not in tracked:
        raise SystemExit("tracked lore2mud CLI is missing")
    entrypoint = b"from lore2mud.cli import main\nraise SystemExit(main())\n"
    _zip_write(path, files, {"__main__.py": entrypoint})


def _copy_content_pack(destination: Path) -> None:
    tracked = _tracked_paths("examples/original_demo")
    expected = frozenset(
        PurePosixPath("examples/original_demo") / name
        for name in CONTENT_FILES
    )
    if tracked != expected:
        missing = sorted(path.as_posix() for path in expected - tracked)
        extra = sorted(path.as_posix() for path in tracked - expected)
        details = []
        if missing:
            details.append(f"missing: {', '.join(missing)}")
        if extra:
            details.append(f"unexpected: {', '.join(extra)}")
        raise SystemExit("original_demo tracked-file set changed; " + "; ".join(details))
    destination.mkdir()
    for repository_path in sorted(expected, key=PurePosixPath.as_posix):
        source = ROOT.joinpath(*repository_path.parts)
        _require_regular_file(source, label=repository_path.as_posix())
        shutil.copy2(source, destination / repository_path.name)


def build(output_dir: Path, *, allow_dirty: bool = False) -> Path:
    version = _version()
    content_pack_version = _content_pack_version()
    commit = _git_commit(allow_dirty=allow_dirty)
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lore2mud-windows-") as temp:
        stage = Path(temp)
        _build_pyz(stage / "lore2mud.pyz")
        _copy_content_pack(stage / "original_demo")
        for asset in (ASSETS / "launcher.ps1", ASSETS / "Start Lore2MUD.cmd"):
            shutil.copy2(asset, stage / asset.name)

        files = {
            str(path.relative_to(stage)).replace("\\", "/"): path
            for path in sorted(stage.rglob("*"))
            if path.is_file()
        }
        manifest = {
            "format": 1,
            "product": "lore2mud",
            "version": version,
            "content_pack_version": content_pack_version,
            "source_commit": commit,
            "python_requires": ">=3.11",
            "files": {name: _sha256(path) for name, path in sorted(files.items())},
        }
        (stage / "bundle.json").write_text(
            json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        files["bundle.json"] = stage / "bundle.json"
        artifact = output_dir / (
            f"lore2mud-windows-{version}-content-{content_pack_version}.zip"
        )
        temporary_artifact = stage / artifact.name
        _zip_write(temporary_artifact, files)
        shutil.copy2(temporary_artifact, artifact)
    artifact.with_suffix(artifact.suffix + ".sha256").write_text(
        f"{_sha256(artifact)}  {artifact.name}\n", encoding="ascii"
    )
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist" / "windows")
    parser.add_argument("--allow-dirty", action="store_true", help="permit a local candidate from a dirty tree")
    args = parser.parse_args()
    artifact = build(args.output_dir, allow_dirty=args.allow_dirty)
    print(f"[OK] built {artifact}")
    print(f"[OK] sha256 {_sha256(artifact)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
