"""Dependency-free loopback HTTP server for the local browser player."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from lore2mud.content.loader import load_content_pack
from lore2mud.engine.save import SaveLoadService
from lore2mud.web.app import PlayerSession


_MAX_ACTION_BYTES = 32 * 1024
_STATIC_ROOT = Path(__file__).with_name("static")
_STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/static/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/static/styles.css": ("styles.css", "text/css; charset=utf-8"),
}


class LocalPlayerServer(ThreadingHTTPServer):
    """HTTP server carrying one in-memory local PlayerSession."""

    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        session: PlayerSession,
    ) -> None:
        self.session = session
        super().__init__(server_address, LocalPlayerHandler)


class LocalPlayerHandler(BaseHTTPRequestHandler):
    """Serve a fixed asset allowlist and the structured local API."""

    server: LocalPlayerServer

    def do_GET(self) -> None:
        if self.path == "/api/snapshot":
            self._send_json(HTTPStatus.OK, self.server.session.snapshot())
            return

        static = _STATIC_FILES.get(self.path)
        if static is None:
            self._send_json(
                HTTPStatus.NOT_FOUND,
                {"ok": False, "error": "资源不存在。"},
            )
            return
        filename, content_type = static
        try:
            body = (_STATIC_ROOT / filename).read_bytes()
        except OSError:
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"ok": False, "error": "本地界面资源不可用。"},
            )
            return
        self._send_bytes(HTTPStatus.OK, body, content_type)

    def do_POST(self) -> None:
        if self.path != "/api/action":
            self._send_json(
                HTTPStatus.NOT_FOUND,
                {"ok": False, "error": "资源不存在。"},
            )
            return
        content_type = self.headers.get_content_type()
        if content_type != "application/json":
            self._send_json(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                {"ok": False, "error": "请求必须使用 application/json。"},
            )
            return
        raw_length = self.headers.get("Content-Length")
        try:
            length = int(raw_length or "")
        except ValueError:
            length = -1
        if length < 0 or length > _MAX_ACTION_BYTES:
            self._send_json(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                {"ok": False, "error": "action 请求大小无效。"},
            )
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "请求不是有效的 UTF-8 JSON。"},
            )
            return
        result = self.server.session.dispatch(payload)
        status = HTTPStatus.OK if result["ok"] else HTTPStatus.UNPROCESSABLE_ENTITY
        self._send_json(status, result)

    def _send_json(self, status: HTTPStatus, value: Any) -> None:
        body = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        self._send_bytes(status, body, "application/json; charset=utf-8")

    def _send_bytes(
        self,
        status: HTTPStatus,
        body: bytes,
        content_type: str,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", _content_security_policy())
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def _content_security_policy() -> str:
    return (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'none'; "
        "frame-ancestors 'none'"
    )


def create_server(
    session: PlayerSession,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> LocalPlayerServer:
    """Build a local player server without starting its blocking loop."""
    return LocalPlayerServer((host, port), session)


def serve(
    content: str | Path,
    save_dir: str | Path,
    *,
    player_name: str = "旅人",
    host: str = "127.0.0.1",
    port: int = 8765,
) -> None:
    """Load one public content pack and serve its local browser player."""
    pack = load_content_pack(content)
    session = PlayerSession(
        pack,
        SaveLoadService(pack, Path(save_dir)),
        player_name=player_name,
    )
    server = create_server(session, host=host, port=port)
    print(f"lore2mud 本地界面：http://{host}:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
