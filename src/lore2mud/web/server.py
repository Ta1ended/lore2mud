"""Dependency-free loopback HTTP server for the local browser player."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
from importlib.resources import files
import math
from pathlib import Path
import socket
from typing import Any
from urllib.parse import urlsplit

from lore2mud.content.loader import load_content_pack
from lore2mud.engine.save import SaveLoadService
from lore2mud.web.app import PlayerSession


_MAX_ACTION_BYTES = 32 * 1024
_MAX_JSON_DEPTH = 32
_MAX_JSON_NODES = 2048
_REQUEST_TIMEOUT_SECONDS = 5
_STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/static/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/static/styles.css": ("styles.css", "text/css; charset=utf-8"),
}


class LocalPlayerConfigurationError(ValueError):
    """Raised when an operator tries to expose the single-player server."""


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


class LocalPlayerIPv6Server(LocalPlayerServer):
    """IPv6 loopback variant of the single-player server."""

    address_family = socket.AF_INET6


class LocalPlayerHandler(BaseHTTPRequestHandler):
    """Serve a fixed asset allowlist and the structured local API."""

    server: LocalPlayerServer

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(_REQUEST_TIMEOUT_SECONDS)

    def do_GET(self) -> None:
        if self._request_authority() is None:
            return
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
            body = _read_static_asset(filename)
        except OSError:
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"ok": False, "error": "本地界面资源不可用。"},
            )
            return
        self._send_bytes(HTTPStatus.OK, body, content_type)

    def do_POST(self) -> None:
        authority = self._request_authority()
        if authority is None:
            return
        if not self._origin_allowed(authority):
            self._send_json(
                HTTPStatus.FORBIDDEN,
                {"ok": False, "error": "Origin 必须与本地服务同源。"},
            )
            return
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
        lengths = self.headers.get_all("Content-Length", [])
        transfer_encodings = self.headers.get_all("Transfer-Encoding", [])
        raw_length = lengths[0].strip() if len(lengths) == 1 else ""
        if (
            transfer_encodings
            or not raw_length.isascii()
            or not raw_length.isdigit()
        ):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "action 请求 framing 无效。"},
            )
            return
        length = int(raw_length)
        if length > _MAX_ACTION_BYTES:
            self._send_json(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                {"ok": False, "error": "action 请求大小无效。"},
            )
            return
        try:
            body = self.rfile.read(length)
        except (TimeoutError, socket.timeout):
            self._send_json(
                HTTPStatus.REQUEST_TIMEOUT,
                {"ok": False, "error": "读取 action 请求超时。"},
            )
            return
        if len(body) != length:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "action 请求正文不完整。"},
            )
            return
        try:
            payload = json.loads(
                body.decode("utf-8"),
                parse_constant=_reject_json_constant,
            )
        except (UnicodeDecodeError, ValueError, RecursionError):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "请求不是有效的 UTF-8 JSON。"},
            )
            return
        if not _json_shape_allowed(payload):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"ok": False, "error": "JSON 结构或字符串无效，或超过深度、节点限制。"},
            )
            return
        result = self.server.session.dispatch(payload)
        status = HTTPStatus.OK if result["ok"] else HTTPStatus.UNPROCESSABLE_ENTITY
        self._send_json(status, result)

    def _request_authority(self) -> tuple[str, int] | None:
        hosts = self.headers.get_all("Host", [])
        authority = _parse_authority(hosts[0]) if len(hosts) == 1 else None
        expected = _normalized_loopback(
            str(self.server.server_address[0]), self.server.server_port
        )
        if authority is None or authority != expected:
            self._send_json(
                HTTPStatus.MISDIRECTED_REQUEST,
                {"ok": False, "error": "Host 必须指向当前本地服务。"},
            )
            return None
        return authority

    def _origin_allowed(self, authority: tuple[str, int]) -> bool:
        origins = self.headers.get_all("Origin", [])
        if not origins:
            return True
        if len(origins) != 1:
            return False
        return _parse_origin(origins[0]) == authority

    def _send_json(self, status: HTTPStatus, value: Any) -> None:
        body = json.dumps(
            value,
            ensure_ascii=True,
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


def _read_static_asset(filename: str) -> bytes:
    """Read package data through Traversable for wheels and zipimport."""
    return (
        files("lore2mud.web")
        .joinpath("static")
        .joinpath(filename)
        .read_bytes()
    )


def _reject_json_constant(value: str) -> None:
    """Reject NaN and infinities, which are not valid JSON values."""
    raise ValueError(f"invalid JSON constant: {value}")


def _is_unicode_scalar_string(value: str) -> bool:
    return not any(0xD800 <= ord(character) <= 0xDFFF for character in value)


def _json_shape_allowed(value: object) -> bool:
    """Bound decoded JSON iteratively, independent of interpreter recursion."""
    stack = [(value, 0)]
    nodes = 0
    while stack:
        current, depth = stack.pop()
        nodes += 1
        if nodes > _MAX_JSON_NODES or depth > _MAX_JSON_DEPTH:
            return False
        if isinstance(current, str):
            if not _is_unicode_scalar_string(current):
                return False
        elif isinstance(current, float):
            if not math.isfinite(current):
                return False
        elif isinstance(current, dict):
            if not all(_is_unicode_scalar_string(key) for key in current):
                return False
            stack.extend((child, depth + 1) for child in current.values())
        elif isinstance(current, list):
            stack.extend((child, depth + 1) for child in current)
    return True


def _normalized_loopback(host: str, port: int) -> tuple[str, int] | None:
    normalized = host.casefold()
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return None
    if not address.is_loopback:
        return None
    return address.compressed, port


def _parse_authority(value: str | None) -> tuple[str, int] | None:
    if not value:
        return None
    try:
        parsed = urlsplit(f"//{value}")
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.username is not None
        or parsed.password is not None
        or parsed.hostname is None
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        return None
    return _normalized_loopback(parsed.hostname, port if port is not None else 80)


def _parse_origin(value: str) -> tuple[str, int] | None:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme != "http"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
        or parsed.hostname is None
    ):
        return None
    return _normalized_loopback(parsed.hostname, port if port is not None else 80)


def _validate_bind_host(host: str) -> None:
    normalized = _normalized_loopback(host, 1)
    if normalized is None or normalized[0] not in {"127.0.0.1", "::1"}:
        raise LocalPlayerConfigurationError(
            "本地界面只允许绑定字面量 loopback 地址 "
            "127.0.0.1 或 ::1。"
        )


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


def _server_url(host: str, port: int) -> str:
    authority = f"[{host}]" if ipaddress.ip_address(host).version == 6 else host
    return f"http://{authority}:{port}/"


def create_server(
    session: PlayerSession,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> LocalPlayerServer:
    """Build a local player server without starting its blocking loop."""
    _validate_bind_host(host)
    server_type = (
        LocalPlayerIPv6Server
        if ipaddress.ip_address(host).version == 6
        else LocalPlayerServer
    )
    return server_type((host, port), session)


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
    print(f"lore2mud 本地界面：{_server_url(host, server.server_port)}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
