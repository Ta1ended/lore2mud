"""Verify a Windows candidate and cold-start it outside the repository."""

from __future__ import annotations

import argparse
import hashlib
from http.client import HTTPConnection, HTTPException
import io
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
BUNDLE_FORMAT = 2
MAX_UNCOMPRESSED_SIZE = 64 * 1024 * 1024
MAX_MEMBER_COUNT = 4096
VERSION_PATTERN = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._-]*$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SOURCE_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}(?:-dirty)?$")
RUNTIMES = frozenset({"pyinstaller", "zipapp"})
WEB_READY_FILE_ENV = "LORE2MUD_WEB_READY_FILE"
METADATA_FIELDS = frozenset({
    "bundled_python_version",
    "content_pack_version",
    "default_mode",
    "files",
    "format",
    "product",
    "python_requires",
    "pyinstaller_version",
    "runtime",
    "source_commit",
    "version",
})
WEB_ASSETS = {
    "/": ("index.html", "text/html"),
    "/static/styles.css": ("styles.css", "text/css"),
    "/static/app.js": ("app.js", "text/javascript"),
}
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
    "original_demo/narrative_state.json",
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
    if archive.comment:
        raise VerificationError("archive comments are not allowed")
    infos = archive.infolist()
    if len(infos) > MAX_MEMBER_COUNT:
        raise VerificationError("archive exceeds the member-count limit")
    for info in infos:
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
            or path.as_posix() != info.filename
            or "\\" in info.filename
            or info.is_dir()
            or info.flag_bits & 0x1
            or info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
            or bool(info.comment)
            or bool(info.extra)
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


def _no_duplicate_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise VerificationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json(content: bytes, *, label: str) -> object:
    try:
        return json.loads(
            content.decode("utf-8"),
            object_pairs_hook=_no_duplicate_object,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise VerificationError(f"invalid {label}: {exc}") from exc


def _verify_pyz(content: bytes) -> dict[str, bytes]:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as app:
            members = _safe_members(app)
            required = {
                "__main__.py",
                *(f"lore2mud/web/static/{name}" for name, _ in WEB_ASSETS.values()),
            }
            missing = sorted(required - members.keys())
            if missing:
                raise VerificationError(
                    f"zipapp is missing packaged Web data: {', '.join(missing)}"
                )
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
            return {
                route: app.read(f"lore2mud/web/static/{name}")
                for route, (name, _) in WEB_ASSETS.items()
            }
    except zipfile.BadZipFile as exc:
        raise VerificationError(f"invalid lore2mud.pyz: {exc}") from exc


def _verify_pyinstaller(
    archive: zipfile.ZipFile,
    members: dict[str, zipfile.ZipInfo],
) -> dict[str, bytes]:
    executable = "runtime/lore2mud.exe"
    if executable not in members:
        raise VerificationError("candidate is missing: runtime/lore2mud.exe")
    with archive.open(executable) as handle:
        if handle.read(2) != b"MZ":
            raise VerificationError("runtime/lore2mud.exe is not a Windows executable")

    expected_web_members = {
        f"runtime/_internal/lore2mud/web/static/{asset_name}"
        for asset_name, _ in WEB_ASSETS.values()
    }
    actual_web_members = {
        name for name in members
        if name.startswith("runtime/_internal/lore2mud/web/")
    }
    missing_web_members = expected_web_members - actual_web_members
    unsupported_web_members = {
        name for name in actual_web_members - expected_web_members
        if (
            not name.startswith("runtime/_internal/lore2mud/web/static/")
            or PurePosixPath(name).suffix.casefold() not in PACKAGE_SUFFIXES
            or PurePosixPath(name).suffix.casefold() == ".py"
        )
    }
    if missing_web_members or unsupported_web_members:
        raise VerificationError(
            "PyInstaller Web data is missing or contains an unsupported resource"
        )

    assets: dict[str, bytes] = {}
    for route, (asset_name, _) in WEB_ASSETS.items():
        expected = f"runtime/_internal/lore2mud/web/static/{asset_name}"
        assets[route] = archive.read(expected)
    return assets


def _validate_metadata(metadata: object) -> tuple[dict[str, object], str, str, str]:
    if not isinstance(metadata, dict):
        raise VerificationError("bundle metadata must be an object")
    if set(metadata) != METADATA_FIELDS:
        raise VerificationError("bundle metadata fields do not match format 2")
    if metadata.get("format") != BUNDLE_FORMAT or metadata.get("product") != "lore2mud":
        raise VerificationError("unsupported bundle metadata")
    runtime = metadata.get("runtime")
    if not isinstance(runtime, str) or runtime not in RUNTIMES:
        raise VerificationError("invalid runtime in bundle metadata")
    if metadata.get("default_mode") != "web":
        raise VerificationError("bundle default mode must be web")
    app_version = metadata.get("version")
    content_version = metadata.get("content_pack_version")
    if not isinstance(app_version, str) or not VERSION_PATTERN.fullmatch(app_version):
        raise VerificationError("invalid application version in bundle metadata")
    if not isinstance(content_version, str) or not VERSION_PATTERN.fullmatch(content_version):
        raise VerificationError("invalid content-pack version in bundle metadata")
    source_commit = metadata.get("source_commit")
    if not isinstance(source_commit, str) or not SOURCE_COMMIT_PATTERN.fullmatch(source_commit):
        raise VerificationError("invalid source commit in bundle metadata")
    expected_python = ">=3.11" if runtime == "zipapp" else None
    if metadata.get("python_requires") != expected_python:
        raise VerificationError("bundle Python requirement does not match its runtime")
    bundled_python = metadata.get("bundled_python_version")
    pyinstaller_version = metadata.get("pyinstaller_version")
    if runtime == "pyinstaller":
        if (
            not isinstance(bundled_python, str)
            or not VERSION_PATTERN.fullmatch(bundled_python)
            or not isinstance(pyinstaller_version, str)
            or not VERSION_PATTERN.fullmatch(pyinstaller_version)
        ):
            raise VerificationError("invalid bundled runtime versions")
    elif bundled_python is not None or pyinstaller_version is not None:
        raise VerificationError("zipapp must not declare bundled runtime versions")
    return metadata, runtime, app_version, content_version


def verify_contents(artifact: Path) -> dict[str, object]:
    if not artifact.is_file():
        raise VerificationError(f"candidate does not exist: {artifact}")
    try:
        with zipfile.ZipFile(artifact) as archive:
            members = _safe_members(archive)
            base_required = {
                "bundle.json", "launcher.ps1", "Start Lore2MUD.cmd", "LICENSE",
                *CONTENT_MEMBERS,
            }
            missing = sorted(base_required - members.keys())
            if missing:
                raise VerificationError(f"candidate is missing: {', '.join(missing)}")

            metadata, runtime, app_version, content_version = _validate_metadata(
                _read_json(archive.read("bundle.json"), label="bundle.json")
            )
            runtime_required = {"lore2mud.pyz"} if runtime == "zipapp" else {"runtime/lore2mud.exe"}
            missing = sorted(runtime_required - members.keys())
            if missing:
                raise VerificationError(f"candidate is missing: {', '.join(missing)}")
            allowed_exact = base_required | runtime_required
            unexpected = sorted(
                name for name in members
                if name not in allowed_exact
                and not (runtime == "pyinstaller" and name.startswith("runtime/"))
            )
            if unexpected:
                raise VerificationError(f"unexpected candidate member: {unexpected[0]}")

            declared = metadata.get("files")
            if not isinstance(declared, dict):
                raise VerificationError("bundle files manifest must be an object")
            if not all(
                isinstance(name, str)
                and isinstance(digest, str)
                and SHA256_PATTERN.fullmatch(digest)
                for name, digest in declared.items()
            ):
                raise VerificationError("bundle files manifest contains an invalid entry")
            actual_names = set(members) - {"bundle.json"}
            if set(declared) != actual_names:
                raise VerificationError("bundle files manifest does not match archive members")
            for name, expected in declared.items():
                actual = _sha256_bytes(archive.read(name))
                if actual != expected:
                    raise VerificationError(f"sha256 mismatch: {name}")

            pack = _read_json(
                archive.read("original_demo/pack.json"),
                label="original_demo/pack.json",
            )
            if not isinstance(pack, dict) or pack.get("version") != content_version:
                raise VerificationError("content-pack version does not match bundle metadata")
            expected_name = (
                f"lore2mud-windows-{runtime}-{app_version}-content-"
                f"{content_version}.zip"
            )
            if artifact.name != expected_name:
                raise VerificationError(f"candidate filename must be {expected_name}")

            if runtime == "zipapp":
                assets = _verify_pyz(archive.read("lore2mud.pyz"))
            else:
                assets = _verify_pyinstaller(archive, members)
            if any(not content for content in assets.values()):
                raise VerificationError("packaged Web assets must not be empty")
            return metadata
    except (OSError, zipfile.BadZipFile) as exc:
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


def _packaged_web_assets(artifact: Path, runtime: str) -> dict[str, bytes]:
    with zipfile.ZipFile(artifact) as archive:
        members = _safe_members(archive)
        if runtime == "zipapp":
            return _verify_pyz(archive.read("lore2mud.pyz"))
        return _verify_pyinstaller(archive, members)


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _http_request(
    port: int,
    method: str,
    path: str,
    *,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, bytes, str]:
    connection = HTTPConnection("127.0.0.1", port, timeout=2)
    try:
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        return response.status, response.read(), response.getheader("Content-Type", "")
    finally:
        connection.close()


def _nested_value(value: object, *keys: str) -> object:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _process_output(process: subprocess.Popen[bytes]) -> tuple[str, str]:
    try:
        stdout, stderr = process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate(timeout=5)
    return (
        stdout.decode("utf-8", errors="replace"),
        stderr.decode("utf-8", errors="replace"),
    )


def _terminate_process_tree(process: subprocess.Popen[bytes]) -> tuple[str, str]:
    if process.poll() is None:
        subprocess.run(
            ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            check=False,
            timeout=10,
        )
    return _process_output(process)


def _wait_for_web_ready(
    process: subprocess.Popen[bytes],
    *,
    port: int,
    timeout: int,
    ready_file: Path,
    ready_url: str,
) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    snapshot: dict[str, object] | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stdout, stderr = _process_output(process)
            raise VerificationError(
                "Web launcher exited before readiness "
                f"({process.returncode})\n{stdout}\n{stderr}"
            )
        if snapshot is None:
            try:
                status, raw_snapshot, content_type = _http_request(
                    port, "GET", "/api/snapshot"
                )
                if status == 200 and "application/json" in content_type:
                    value = json.loads(raw_snapshot)
                    if isinstance(value, dict):
                        snapshot = value
            except (OSError, HTTPException, json.JSONDecodeError):
                pass
        try:
            readiness_reported = ready_file.read_text(encoding="utf-8").strip() == ready_url
        except (OSError, UnicodeError):
            readiness_reported = False
        if snapshot is not None and readiness_reported:
            return snapshot
        time.sleep(0.1)

    if snapshot is None:
        raise VerificationError("Web candidate did not become healthy")
    raise VerificationError("launcher did not report expected Web readiness")


def _restricted_windows_path() -> str:
    windows = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    return os.pathsep.join((
        str(windows / "System32"),
        str(windows / "System32" / "WindowsPowerShell" / "v1.0"),
    ))


def _run_launcher(
    launcher: Path,
    mode: str,
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: int,
    input_bytes: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["cmd.exe", "/d", "/c", str(launcher), mode],
        cwd=cwd,
        input=input_bytes,
        capture_output=True,
        env=env,
        timeout=timeout,
    )


def cold_start(artifact: Path, *, timeout: int = 45) -> subprocess.CompletedProcess[bytes]:
    if os.name != "nt":
        raise VerificationError("cold-start smoke requires Windows")
    metadata = verify_contents(artifact)
    runtime = str(metadata["runtime"])
    expected_assets = _packaged_web_assets(artifact, runtime)

    with tempfile.TemporaryDirectory(prefix="lore2mud cold start ") as temp:
        root = Path(temp).resolve()
        try:
            root.relative_to(ROOT.resolve())
        except ValueError:
            pass
        else:
            raise VerificationError("cold-start directory must be outside the repository")

        bundle = root / "bundle with spaces"
        data = root / "user data"
        with zipfile.ZipFile(artifact) as archive:
            _safe_members(archive)
            archive.extractall(bundle)

        content_version = str(metadata["content_pack_version"])
        legacy_save = data / "saves" / "legacy.json"
        legacy_save.parent.mkdir(parents=True)
        legacy_save.write_bytes(b"{}\n")
        older_save = data / "saves" / "content-0.8.0" / "default.json"
        older_save.parent.mkdir()
        older_save.write_bytes(b"old\n")
        env = os.environ.copy()
        env.update({
            "LORE2MUD_DATA_DIR": str(data),
            "LORE2MUD_NO_BROWSER": "1",
            "PATH": _restricted_windows_path(),
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
        })
        env["LORE2MUD_PYTHON"] = (
            sys.executable
            if runtime == "zipapp"
            else str(root / "python-must-not-be-required.exe")
        )
        launcher = bundle / "Start Lore2MUD.cmd"

        diagnostic = _run_launcher(
            launcher,
            "--diagnose",
            cwd=root,
            env=env,
            timeout=timeout,
        )
        required_diagnostics = (
            b"Bundle format: 2",
            f"Bundle runtime: {runtime}".encode("ascii"),
            f"Content pack version: {content_version}".encode("ascii"),
            b"Data directory:",
            b"Save directory:",
            b"[WARN] Legacy saves remain",
            b"[WARN] Other content-version saves remain",
        )
        if runtime == "pyinstaller":
            required_diagnostics += (
                f"Bundled Python version: {metadata['bundled_python_version']}".encode("ascii"),
                f"PyInstaller version: {metadata['pyinstaller_version']}".encode("ascii"),
            )
        if diagnostic.returncode != 0 or any(
            marker not in diagnostic.stdout for marker in required_diagnostics
        ):
            stdout = diagnostic.stdout.decode("utf-8", errors="replace")
            stderr = diagnostic.stderr.decode("utf-8", errors="replace")
            raise VerificationError(
                f"diagnostics failed ({diagnostic.returncode})\n{stdout}\n{stderr}"
            )

        console = _run_launcher(
            launcher,
            "--console",
            cwd=root,
            env=env,
            timeout=timeout,
            input_bytes=b"quit\n",
        )
        if console.returncode != 0:
            stdout = console.stdout.decode("utf-8", errors="replace")
            stderr = console.stderr.decode("utf-8", errors="replace")
            raise VerificationError(
                f"console fallback failed ({console.returncode})\n{stdout}\n{stderr}"
            )

        port = _free_loopback_port()
        env["LORE2MUD_WEB_PORT"] = str(port)
        ready_file = root / "web-ready.txt"
        ready_url = f"http://127.0.0.1:{port}/"
        env[WEB_READY_FILE_ENV] = str(ready_file)
        web_process = subprocess.Popen(
            ["cmd.exe", "/d", "/c", str(launcher), "--smoke-web"],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        web_stdout = ""
        web_stderr = ""
        try:
            snapshot = _wait_for_web_ready(
                web_process,
                port=port,
                timeout=timeout,
                ready_file=ready_file,
                ready_url=ready_url,
            )
            if (
                _nested_value(snapshot, "pack", "id") != "original_demo"
                or _nested_value(snapshot, "pack", "version") != content_version
                or _nested_value(snapshot, "room", "id") != "room_ember_wharf"
            ):
                raise VerificationError("Web snapshot does not describe the bundled demo")

            for route, expected in expected_assets.items():
                status, body, content_type = _http_request(port, "GET", route)
                expected_type = WEB_ASSETS[route][1]
                if status != 200 or body != expected or expected_type not in content_type:
                    raise VerificationError(f"packaged Web response mismatch: {route}")

            action_body = b'{"type":"move","direction":"east"}'
            status, raw_result, content_type = _http_request(
                port,
                "POST",
                "/api/action",
                body=action_body,
                headers={
                    "Content-Type": "application/json",
                    "Origin": f"http://127.0.0.1:{port}",
                },
            )
            try:
                result = json.loads(raw_result)
            except (json.JSONDecodeError, RecursionError) as exc:
                raise VerificationError("Web action response is not valid JSON") from exc
            if (
                status != 200
                or "application/json" not in content_type
                or not isinstance(result, dict)
                or result.get("ok") is not True
                or _nested_value(result, "snapshot", "room", "id")
                != "room_glassgrass_path"
            ):
                raise VerificationError("packaged Web action round trip failed")
        finally:
            if web_process.poll() is None:
                web_stdout, web_stderr = _terminate_process_tree(web_process)
            elif not web_stdout and not web_stderr:
                web_stdout, web_stderr = _process_output(web_process)

        if web_process.poll() is None:
            raise VerificationError("Web candidate process tree did not stop")
        try:
            reported_ready_url = ready_file.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError) as exc:
            raise VerificationError(
                f"launcher readiness file is unavailable\n{web_stdout}\n{web_stderr}"
            ) from exc
        if reported_ready_url != ready_url:
            raise VerificationError("launcher readiness file contains an unexpected URL")
        if (bundle / "saves").exists():
            raise VerificationError("cold start wrote saves inside the bundle")
        versioned_saves = data / "saves" / f"content-{content_version}"
        if not versioned_saves.is_dir():
            raise VerificationError("launcher did not create the versioned save directory")
        if legacy_save.read_bytes() != b"{}\n":
            raise VerificationError("launcher modified a legacy save")
        if older_save.read_bytes() != b"old\n":
            raise VerificationError("launcher modified an older content-version save")
        return console


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--skip-smoke", action="store_true")
    args = parser.parse_args()
    try:
        verify_sidecar(args.artifact)
        metadata = verify_contents(args.artifact)
        print(
            f"[OK] manifest {metadata['product']} {metadata['version']} "
            f"({metadata['runtime']}, content {metadata['content_pack_version']})"
        )
        if args.skip_smoke:
            print("[SKIP] cold-start smoke")
        else:
            cold_start(args.artifact)
            print("[OK] repository-external Web and console cold start")
    except VerificationError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
