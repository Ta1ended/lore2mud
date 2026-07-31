"""HTTP boundary tests for the local browser player."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from lore2mud.content.loader import load_content_pack
from lore2mud.engine.save import SaveLoadService
from lore2mud.web.app import PlayerSession
from lore2mud.web.server import create_server


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
        try:
            with urlopen(self.base_url + path, timeout=2) as response:
                return response.status, response.read(), response.headers
        except HTTPError as exc:
            return exc.code, exc.read(), exc.headers

    def post(
        self,
        path: str,
        body: bytes,
        *,
        content_type: str = "application/json",
    ) -> tuple[int, dict, object]:
        request = Request(
            self.base_url + path,
            data=body,
            method="POST",
            headers={"Content-Type": content_type},
        )
        try:
            with urlopen(request, timeout=2) as response:
                return response.status, json.loads(response.read()), response.headers
        except HTTPError as exc:
            return exc.code, json.loads(exc.read()), exc.headers

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

    def test_static_allowlist_blocks_unknown_and_traversal_paths(self) -> None:
        for path in ("/favicon.ico", "/static/../server.py", "/api/unknown"):
            with self.subTest(path=path):
                status, body, _ = self.get(path)
                self.assertEqual(status, 404)
                self.assertFalse(json.loads(body)["ok"])


if __name__ == "__main__":
    unittest.main()
