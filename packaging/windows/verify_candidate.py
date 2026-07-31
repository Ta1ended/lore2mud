"""Verify a Windows candidate and cold-start it outside the repository."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

MAX_UNCOMPRESSED_SIZE = 64 * 1024 * 1024
VERSION_PATTERN = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._-]*$")
PACKAGE_SUFFIXES = frozenset({
    ".py", ".html", ".css", ".js", ".svg",
    ".png", ".jpg", ".jpeg", ".webp", ".woff2",
})
CONTENT_MEMBERS = frozenset({
    "original_demo/README.md",
    "original_demo/characters.json",
    "original_demo/dialogues.json",
    "original_demo/items.json",
    "original_demo/monsters.json",
    "original_demo/pack.json",
    "original_demo/quests.json",
    "original_demo/rooms.json",
    "original_demo/shops.json",
})
WINDOWS_RESERVED_NAMES = frozenset({
    "con", "prn", "aux", "nul",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
})


class VerificationError(RuntimeError):
    pass


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _safe_members(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    members: dict[str, zipfile.ZipInfo] = {}
    casefolded: set[str] = set()
    total_size = 0
    for info in archive.infolist():
        path = PurePosixPath(info.filename)
        unsafe_component = any(
            not part
            or ":" in part
            or part.endswith((".", " "))
            or any(ord(character) < 32 for character in part)
            or part.split(".", 1)[0].casefold() in WINDOWS_RESERVED_NAMES
            for part in path.parts
        )
        if (
            path.is_absolute()
            or not path.parts
            or ".." in path.parts
            or "\\" in info.filename
            or info.is_dir()
            or unsafe_component
        ):
            raise VerificationError(f"unsafe archive path: {info.filename}")
        if info.filename in members:
            raise VerificationError(f"duplicate archive path: {info.filename}")
        folded = info.filename.casefold()
        if folded in casefolded:
            raise VerificationError(f"case-colliding archive path: {info.filename}")
        file_type = (info.external_attr >> 16) & 0o170000
        if file_type not in (0, 0o100000):
            raise VerificationError(f"special files are not allowed: {info.filename}")
        total_size += info.file_size
        if total_size > MAX_UNCOMPRESSED_SIZE:
            raise VerificationError("archive exceeds the uncompressed size limit")
        members[info.filename] = info
        casefolded.add(folded)
    return members


def _verify_pyz(content: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as app:
            members = _safe_members(app)
            if "__main__.py" not in members:
                raise VerificationError("zipapp entry point is missing")
            unexpected = sorted(
                name for name in members
                if name != "__main__.py"
                and not (
                    name.startswith("lore2mud/")
                    and PurePosixPath(name).suffix.casefold() in PACKAGE_SUFFIXES
                )
            )
            if unexpected:
                raise VerificationError(f"unexpected zipapp member: {unexpected[0]}")
    except zipfile.BadZipFile as exc:
        raise VerificationError(f"invalid lore2mud.pyz: {exc}") from exc


def verify_contents(artifact: Path) -> dict[str, object]:
    if not artifact.is_file():
        raise VerificationError(f"candidate does not exist: {artifact}")
    try:
        with zipfile.ZipFile(artifact) as archive:
            members = _safe_members(archive)
            required = {
                "bundle.json", "lore2mud.pyz", "launcher.ps1", "Start Lore2MUD.cmd",
                *CONTENT_MEMBERS,
            }
            missing = sorted(required - members.keys())
            if missing:
                raise VerificationError(f"candidate is missing: {', '.join(missing)}")
            unexpected = sorted(
                name for name in members
                if name not in required
                and name not in CONTENT_MEMBERS
            )
            if unexpected:
                raise VerificationError(f"unexpected candidate member: {unexpected[0]}")
            metadata = json.loads(archive.read("bundle.json"))
            if metadata.get("format") != 1 or metadata.get("product") != "lore2mud":
                raise VerificationError("unsupported bundle metadata")
            app_version = metadata.get("version")
            content_version = metadata.get("content_pack_version")
            if not isinstance(app_version, str) or not VERSION_PATTERN.fullmatch(app_version):
                raise VerificationError("invalid application version in bundle metadata")
            if not isinstance(content_version, str) or not VERSION_PATTERN.fullmatch(content_version):
                raise VerificationError("invalid content-pack version in bundle metadata")
            declared = metadata.get("files")
            if not isinstance(declared, dict):
                raise VerificationError("bundle files manifest must be an object")
            actual_names = set(members) - {"bundle.json"}
            if set(declared) != actual_names:
                raise VerificationError("bundle files manifest does not match archive members")
            for name, expected in declared.items():
                actual = _sha256_bytes(archive.read(name))
                if actual != expected:
                    raise VerificationError(f"sha256 mismatch: {name}")
            pack = json.loads(archive.read("original_demo/pack.json"))
            if pack.get("version") != content_version:
                raise VerificationError("content-pack version does not match bundle metadata")
            expected_name = f"lore2mud-windows-{app_version}-content-{content_version}.zip"
            if artifact.name != expected_name:
                raise VerificationError(f"candidate filename must be {expected_name}")
            _verify_pyz(archive.read("lore2mud.pyz"))
            return metadata
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot read candidate: {exc}") from exc


def verify_sidecar(artifact: Path) -> None:
    sidecar = artifact.with_suffix(artifact.suffix + ".sha256")
    if not sidecar.exists():
        return
    try:
        fields = sidecar.read_text(encoding="ascii").strip().split()
    except OSError as exc:
        raise VerificationError(f"cannot read sha256 sidecar: {exc}") from exc
    if len(fields) != 2 or fields[1] != artifact.name:
        raise VerificationError("invalid sha256 sidecar format")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    if fields[0] != digest:
        raise VerificationError("candidate sha256 sidecar mismatch")


def cold_start(artifact: Path, *, timeout: int = 30) -> subprocess.CompletedProcess[bytes]:
    if os.name != "nt":
        raise VerificationError("cold-start smoke requires Windows")
    with tempfile.TemporaryDirectory(prefix="lore2mud-cold-start-") as temp:
        root = Path(temp)
        bundle = root / "bundle"
        data = root / "user-data"
        with zipfile.ZipFile(artifact) as archive:
            _safe_members(archive)
            archive.extractall(bundle)
        metadata = json.loads((bundle / "bundle.json").read_text(encoding="utf-8"))
        content_version = str(metadata["content_pack_version"])
        legacy_save = data / "saves" / "legacy.json"
        legacy_save.parent.mkdir(parents=True)
        legacy_save.write_bytes(b"{}\n")
        older_save = data / "saves" / "content-older" / "default.json"
        older_save.parent.mkdir()
        older_save.write_bytes(b"old\n")
        env = os.environ.copy()
        env.update({
            "LORE2MUD_DATA_DIR": str(data),
            "LORE2MUD_PYTHON": sys.executable,
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
        })
        diagnostic = subprocess.run(
            ["cmd.exe", "/d", "/c", str(bundle / "Start Lore2MUD.cmd"), "--diagnose"],
            cwd=root,
            capture_output=True,
            env=env,
            timeout=timeout,
        )
        if (
            diagnostic.returncode != 0
            or b"Data directory:" not in diagnostic.stdout
            or b"Content pack version:" not in diagnostic.stdout
            or b"[WARN] Legacy saves remain" not in diagnostic.stdout
            or b"[WARN] Other content-version saves remain" not in diagnostic.stdout
        ):
            stderr = diagnostic.stderr.decode("utf-8", errors="replace")
            stdout = diagnostic.stdout.decode("utf-8", errors="replace")
            raise VerificationError(f"diagnostics failed ({diagnostic.returncode})\n{stdout}\n{stderr}")
        completed = subprocess.run(
            ["cmd.exe", "/d", "/c", str(bundle / "Start Lore2MUD.cmd"), "--smoke"],
            cwd=root,
            input=b"quit\n",
            capture_output=True,
            env=env,
            timeout=timeout,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.decode("utf-8", errors="replace")
            stdout = completed.stdout.decode("utf-8", errors="replace")
            raise VerificationError(f"cold start failed ({completed.returncode})\n{stdout}\n{stderr}")
        if (bundle / "saves").exists():
            raise VerificationError("cold start wrote saves inside the bundle")
        versioned_saves = data / "saves" / f"content-{content_version}"
        if not versioned_saves.is_dir():
            raise VerificationError("launcher did not create the versioned save directory")
        if legacy_save.read_bytes() != b"{}\n":
            raise VerificationError("launcher modified a legacy save")
        if older_save.read_bytes() != b"old\n":
            raise VerificationError("launcher modified an older content-version save")
        return completed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--skip-smoke", action="store_true")
    args = parser.parse_args()
    try:
        verify_sidecar(args.artifact)
        metadata = verify_contents(args.artifact)
        print(f"[OK] manifest {metadata['product']} {metadata['version']}")
        if args.skip_smoke:
            print("[SKIP] cold-start smoke")
        else:
            cold_start(args.artifact)
            print("[OK] repository-external cold start")
    except VerificationError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
