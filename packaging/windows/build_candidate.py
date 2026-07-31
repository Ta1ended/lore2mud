"""Build a deterministic Windows candidate for the public original demo."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
ASSETS = Path(__file__).resolve().parent / "assets"
ZIP_EPOCH = (2024, 1, 1, 0, 0, 0)
BUNDLE_FORMAT = 2
PYINSTALLER_SOURCE_DATE_EPOCH = "1704067200"
WEB_ASSETS = ("index.html", "styles.css", "app.js")
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
    "narrative_state.json",
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


def _pyinstaller_version() -> str:
    try:
        return importlib.metadata.version("PyInstaller")
    except importlib.metadata.PackageNotFoundError as exc:
        raise SystemExit(
            "PyInstaller metadata is unavailable; install the pinned Windows "
            "build requirements"
        ) from exc


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


def _tracked_pyinstaller_web_data() -> frozenset[str]:
    tracked = _tracked_paths("src/lore2mud/web")
    data = frozenset(
        f"_internal/{PurePosixPath(*repository_path.parts[1:]).as_posix()}"
        for repository_path in tracked
        if repository_path.suffix.casefold() in PACKAGE_SUFFIXES
        and repository_path.suffix.casefold() != ".py"
    )
    required = frozenset(
        f"_internal/lore2mud/web/static/{asset_name}"
        for asset_name in WEB_ASSETS
    )
    if not required.issubset(data):
        missing = ", ".join(sorted(required - data))
        raise SystemExit(f"tracked Web assets are missing: {missing}")
    return data


def _build_pyinstaller_runtime(destination: Path, work_root: Path) -> None:
    environment = os.environ.copy()
    python_path = [str(ROOT / "src")]
    if environment.get("PYTHONPATH"):
        python_path.append(environment["PYTHONPATH"])
    environment.update({
        "PYTHONHASHSEED": "0",
        "PYTHONPATH": os.pathsep.join(python_path),
        "SOURCE_DATE_EPOCH": PYINSTALLER_SOURCE_DATE_EPOCH,
    })
    dist_path = work_root / "dist"
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--console",
        "--noupx",
        "--name",
        "lore2mud",
        "--paths",
        str(ROOT / "src"),
        "--collect-data",
        "lore2mud.web",
        "--distpath",
        str(dist_path),
        "--workpath",
        str(work_root / "work"),
        "--specpath",
        str(work_root / "spec"),
        str(ROOT / "src" / "lore2mud" / "__main__.py"),
    ]
    try:
        subprocess.run(command, cwd=ROOT, env=environment, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(
            "PyInstaller build failed; install the pinned Windows build "
            "requirements before building a standalone candidate"
        ) from exc

    source = dist_path / "lore2mud"
    executable = source / "lore2mud.exe"
    _require_regular_file(executable, label="PyInstaller lore2mud.exe")
    runtime_files = {
        path.relative_to(source).as_posix(): path
        for path in source.rglob("*")
        if path.is_file()
    }
    expected_web_data = _tracked_pyinstaller_web_data()
    actual_web_data = frozenset(
        name for name in runtime_files
        if name.startswith("_internal/lore2mud/web/")
    )
    if actual_web_data != expected_web_data:
        missing = sorted(expected_web_data - actual_web_data)
        unexpected = sorted(actual_web_data - expected_web_data)
        details = []
        if missing:
            details.append(f"missing: {', '.join(missing)}")
        if unexpected:
            details.append(f"unexpected: {', '.join(unexpected)}")
        raise SystemExit(
            "PyInstaller Web data differs from tracked public resources; "
            + "; ".join(details)
        )
    shutil.copytree(source, destination)


def build(
    output_dir: Path,
    *,
    allow_dirty: bool = False,
    runtime: str = "pyinstaller",
) -> Path:
    if runtime not in {"zipapp", "pyinstaller"}:
        raise ValueError(f"unsupported Windows runtime: {runtime}")
    version = _version()
    content_pack_version = _content_pack_version()
    commit = _git_commit(allow_dirty=allow_dirty)
    bundled_python_version = (
        ".".join(str(part) for part in sys.version_info[:3])
        if runtime == "pyinstaller"
        else None
    )
    pyinstaller_version = _pyinstaller_version() if runtime == "pyinstaller" else None
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lore2mud-windows-") as temp:
        temp_root = Path(temp)
        stage = temp_root / "bundle"
        stage.mkdir()
        if runtime == "zipapp":
            _build_pyz(stage / "lore2mud.pyz")
        else:
            _build_pyinstaller_runtime(
                stage / "runtime",
                temp_root / "pyinstaller",
            )
        _copy_content_pack(stage / "original_demo")
        delivery_files = (
            ASSETS / "launcher.ps1",
            ASSETS / "Start Lore2MUD.cmd",
            ROOT / "LICENSE",
        )
        for asset in delivery_files:
            _require_regular_file(asset, label=asset.relative_to(ROOT).as_posix())
            shutil.copy2(asset, stage / asset.name)

        files = {
            str(path.relative_to(stage)).replace("\\", "/"): path
            for path in sorted(stage.rglob("*"))
            if path.is_file()
        }
        manifest = {
            "format": BUNDLE_FORMAT,
            "product": "lore2mud",
            "version": version,
            "content_pack_version": content_pack_version,
            "bundled_python_version": bundled_python_version,
            "source_commit": commit,
            "runtime": runtime,
            "default_mode": "web",
            "python_requires": ">=3.11" if runtime == "zipapp" else None,
            "pyinstaller_version": pyinstaller_version,
            "files": {name: _sha256(path) for name, path in sorted(files.items())},
        }
        (stage / "bundle.json").write_text(
            json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        files["bundle.json"] = stage / "bundle.json"
        artifact = output_dir / (
            f"lore2mud-windows-{runtime}-{version}-content-"
            f"{content_pack_version}.zip"
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
    parser.add_argument(
        "--runtime",
        choices=("pyinstaller", "zipapp"),
        default="pyinstaller",
        help="candidate runtime (default: dependency-free target runtime)",
    )
    args = parser.parse_args()
    artifact = build(
        args.output_dir,
        allow_dirty=args.allow_dirty,
        runtime=args.runtime,
    )
    print(f"[OK] built {artifact}")
    print(f"[OK] sha256 {_sha256(artifact)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
