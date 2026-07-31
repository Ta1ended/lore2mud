"""HTTP boundary tests for the local browser player."""

from __future__ import annotations

import json
from http.client import HTTPConnection
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
import zipfile
from importlib.resources import files
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from lore2mud.content.loader import load_content_pack
from lore2mud.engine.save import SaveLoadService
from lore2mud.web.app import PlayerSession
from lore2mud.web.server import (
    _parse_authority,
    _parse_origin,
    _read_static_asset,
    _server_url,
    _validate_bind_host,
    create_server,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = PROJECT_ROOT / "examples" / "original_demo"


class LocalPlayerServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        pack = load_content_pack(DEMO_PATH)
        session = PlayerSession(
            pack,
            SaveLoadService(pack, Path(self.temp_dir.name)),
        )
        self.server = create_server(session, host="127.0.0.1", port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"
        self.addCleanup(self._stop_server)

    def _stop_server(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def get(self, path: str) -> tuple[int, bytes, object]:
        return self.get_with_headers(path, {})

    def get_with_headers(
        self,
        path: str,
        headers: dict[str, str],
    ) -> tuple[int, bytes, object]:
        request = Request(self.base_url + path, headers=headers)
        try:
            with urlopen(request, timeout=2) as response:
                return response.status, response.read(), response.headers
        except HTTPError as exc:
            return exc.code, exc.read(), exc.headers

    def post(
        self,
        path: str,
        body: bytes,
        *,
        content_type: str = "application/json",
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict, object]:
        request_headers = {"Content-Type": content_type}
        request_headers.update(headers or {})
        request = Request(
            self.base_url + path,
            data=body,
            method="POST",
            headers=request_headers,
        )
        try:
            with urlopen(request, timeout=2) as response:
                return response.status, json.loads(response.read()), response.headers
        except HTTPError as exc:
            return exc.code, json.loads(exc.read()), exc.headers

    def raw_request(
        self,
        method: str,
        path: str,
        headers: tuple[tuple[str, str], ...],
        body: bytes | None = None,
        *,
        shutdown_write: bool = False,
    ) -> tuple[int, dict]:
        connection = HTTPConnection(
            "127.0.0.1",
            self.server.server_port,
            timeout=2,
        )
        try:
            connection.putrequest(
                method,
                path,
                skip_host=True,
                skip_accept_encoding=True,
            )
            for name, value in headers:
                connection.putheader(name, value)
            connection.endheaders(body)
            if shutdown_write:
                if connection.sock is None:
                    self.fail("HTTP connection closed before half-close test")
                connection.sock.shutdown(socket.SHUT_WR)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def test_serves_player_assets_with_security_headers(self) -> None:
        for path, content_type in (
            ("/", "text/html"),
            ("/static/app.js", "text/javascript"),
            ("/static/styles.css", "text/css"),
        ):
            with self.subTest(path=path):
                status, body, headers = self.get(path)
                self.assertEqual(status, 200)
                self.assertTrue(body)
                self.assertIn(content_type, headers["Content-Type"])
                self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
                self.assertIn("default-src 'self'", headers["Content-Security-Policy"])

    def test_snapshot_and_action_round_trip(self) -> None:
        status, raw, _ = self.get("/api/snapshot")
        snapshot = json.loads(raw)
        self.assertEqual(status, 200)
        self.assertEqual(snapshot["room"]["id"], "room_ember_wharf")

        status, result, _ = self.post(
            "/api/action",
            json.dumps({"type": "move", "direction": "east"}).encode("utf-8"),
        )
        self.assertEqual(status, 200)
        self.assertTrue(result["ok"])
        self.assertEqual(result["snapshot"]["room"]["id"], "room_glassgrass_path")

    def test_rule_failure_returns_422_with_authoritative_snapshot(self) -> None:
        status, result, _ = self.post(
            "/api/action",
            b'{"type":"move","direction":"west"}',
        )
        self.assertEqual(status, 422)
        self.assertFalse(result["ok"])
        self.assertEqual(result["event"]["type"], "error")
        self.assertEqual(result["snapshot"]["room"]["id"], "room_ember_wharf")

    def test_command_mutation_matrix_returns_structured_422(self) -> None:
        for command in ("go west", "save bad_slot", "load missing"):
            with self.subTest(command=command):
                status, result, _ = self.post(
                    "/api/action",
                    json.dumps({"type": "command", "command": command}).encode(
                        "utf-8"
                    ),
                )
                self.assertEqual(status, 422)
                self.assertFalse(result["ok"])
                self.assertEqual(result["event"]["type"], "error")
                self.assertEqual(
                    result["snapshot"]["room"]["id"],
                    "room_ember_wharf",
                )

    def test_rejects_malformed_media_and_oversized_actions(self) -> None:
        status, result, _ = self.post("/api/action", b"{", content_type="application/json")
        self.assertEqual(status, 400)
        self.assertFalse(result["ok"])

        status, result, _ = self.post("/api/action", b"{}", content_type="text/plain")
        self.assertEqual(status, 415)
        self.assertFalse(result["ok"])

        status, result, _ = self.post(
            "/api/action",
            b" " * (32 * 1024 + 1),
        )
        self.assertEqual(status, 413)
        self.assertFalse(result["ok"])

    def test_rejects_ambiguous_or_incomplete_request_framing(self) -> None:
        authority = f"127.0.0.1:{self.server.server_port}"
        payload = b'{"type":"move","direction":"east"}'
        base_headers = (
            ("Host", authority),
            ("Content-Type", "application/json"),
        )
        cases = (
            (
                base_headers
                + (
                    ("Content-Length", str(len(payload))),
                    ("Content-Length", str(len(payload))),
                ),
                payload,
                False,
            ),
            (
                base_headers
                + (
                    ("Transfer-Encoding", "chunked"),
                    ("Content-Length", str(len(payload))),
                ),
                payload,
                False,
            ),
            (
                base_headers + (("Content-Length", str(len(payload) + 10)),),
                payload,
                True,
            ),
        )
        for headers, body, shutdown_write in cases:
            with self.subTest(headers=headers):
                status, result = self.raw_request(
                    "POST",
                    "/api/action",
                    headers,
                    body,
                    shutdown_write=shutdown_write,
                )
                self.assertEqual(status, 400)
                self.assertFalse(result["ok"])

        status, raw, _ = self.get("/api/snapshot")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)["room"]["id"], "room_ember_wharf")

    def test_static_allowlist_blocks_unknown_and_traversal_paths(self) -> None:
        for path in ("/favicon.ico", "/static/../server.py", "/api/unknown"):
            with self.subTest(path=path):
                status, body, _ = self.get(path)
                self.assertEqual(status, 404)
                self.assertFalse(json.loads(body)["ok"])

    def test_bind_boundary_accepts_only_product_loopback_literals(self) -> None:
        for host in ("127.0.0.1", "::1"):
            with self.subTest(host=host):
                _validate_bind_host(host)

        for host in ("0.0.0.0", "127.0.0.2", "192.168.1.20", "localhost"):
            with self.subTest(host=host):
                with self.assertRaisesRegex(ValueError, "loopback"):
                    _validate_bind_host(host)

        self.assertEqual(_server_url("127.0.0.1", 8765), "http://127.0.0.1:8765/")
        self.assertEqual(_server_url("::1", 8765), "http://[::1]:8765/")
        self.assertEqual(_parse_authority("127.0.0.1"), ("127.0.0.1", 80))
        self.assertEqual(_parse_origin("http://127.0.0.1"), ("127.0.0.1", 80))

    def test_host_header_rejects_dns_rebinding_and_wrong_authority(self) -> None:
        for host in (
            "evil.example:8879",
            "127.0.0.1:1",
            f"127.0.0.2:{self.server.server_port}",
            f"localhost:{self.server.server_port}",
            f"127.0.0.1:{self.server.server_port}/path",
            f"127.0.0.1:{self.server.server_port}?query",
            f"127.0.0.1:{self.server.server_port}#fragment",
        ):
            with self.subTest(host=host):
                status, body, _ = self.get_with_headers(
                    "/api/snapshot", {"Host": host}
                )
                self.assertEqual(status, 421)
                self.assertFalse(json.loads(body)["ok"])

        authority = f"127.0.0.1:{self.server.server_port}"
        status, result = self.raw_request(
            "GET",
            "/api/snapshot",
            (("Host", authority), ("Host", authority)),
        )
        self.assertEqual(status, 421)
        self.assertFalse(result["ok"])

    def test_post_origin_policy_allows_same_origin_or_absent_only(self) -> None:
        payload = b'{"type":"command","command":"status"}'
        same_origin = f"http://127.0.0.1:{self.server.server_port}"
        status, result, _ = self.post(
            "/api/action", payload, headers={"Origin": same_origin}
        )
        self.assertEqual(status, 200)
        self.assertTrue(result["ok"])

        status, result, _ = self.post("/api/action", payload)
        self.assertEqual(status, 200)
        self.assertTrue(result["ok"])

        for origin in (
            "http://evil.example",
            f"http://localhost:{self.server.server_port}",
            f"https://127.0.0.1:{self.server.server_port}",
            f"http://127.0.0.1:{self.server.server_port}/path",
            "null",
        ):
            with self.subTest(origin=origin):
                status, result, _ = self.post(
                    "/api/action", payload, headers={"Origin": origin}
                )
                self.assertEqual(status, 403)
                self.assertFalse(result["ok"])

        authority = f"127.0.0.1:{self.server.server_port}"
        status, result = self.raw_request(
            "POST",
            "/api/action",
            (
                ("Host", authority),
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(payload))),
                ("Origin", same_origin),
                ("Origin", same_origin),
            ),
            payload,
        )
        self.assertEqual(status, 403)
        self.assertFalse(result["ok"])

    def test_json_parser_shape_and_scalar_limits_return_stable_400(self) -> None:
        bodies = (
            b'{"type":"command","value":' + b"9" * 5000 + b"}",
            b"[" * 2000 + b"0" + b"]" * 2000,
            b"[" * 33 + b"0" + b"]" * 33,
            b"[" + b",".join([b"0"] * 2049) + b"]",
            b'{"type":"command","command":NaN}',
            b'{"type":"command","command":"\\ud800"}',
        )
        for body in bodies:
            with self.subTest(size=len(body)):
                status, result, headers = self.post("/api/action", body)
                self.assertEqual(status, 400)
                self.assertFalse(result["ok"])
                self.assertEqual(
                    headers["Content-Type"],
                    "application/json; charset=utf-8",
                )


class StaticPackageResourceTests(unittest.TestCase):
    ASSETS = ("index.html", "styles.css", "app.js")

    def test_all_static_assets_are_read_through_package_traversable(self) -> None:
        static = files("lore2mud.web").joinpath("static")
        for filename in self.ASSETS:
            with self.subTest(filename=filename):
                resource = static.joinpath(filename)
                self.assertTrue(resource.is_file())
                self.assertEqual(_read_static_asset(filename), resource.read_bytes())
                self.assertTrue(resource.read_bytes())

    def test_actual_web_package_resources_load_from_zipimport(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            archive = Path(temp_dir) / "lore2mud-player.zip"
            package_root = PROJECT_ROOT / "src" / "lore2mud"
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
                for path in package_root.rglob("*"):
                    if path.is_file() and "__pycache__" not in path.parts:
                        bundle.write(
                            path,
                            Path("lore2mud") / path.relative_to(package_root),
                        )

            script = (
                "import sys; "
                f"sys.path.insert(0, {str(archive)!r}); "
                "from lore2mud.web.server import _read_static_asset; "
                "assets=('index.html','styles.css','app.js'); "
                "payloads=[_read_static_asset(name) for name in assets]; "
                "assert all(payloads); "
                "assert b'<!doctype html>' in payloads[0]; "
                "assert b':root' in payloads[1]; "
                "assert b'fetchSnapshot' in payloads[2]"
            )
            result = subprocess.run(
                [sys.executable, "-I", "-c", script],
                cwd=temp_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=20,
            )

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
