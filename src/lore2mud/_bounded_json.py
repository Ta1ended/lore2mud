"""Bound untrusted UTF-8 JSON reads before domain validation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import math
from pathlib import Path
from typing import TypeAlias


JsonValue: TypeAlias = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]


class JsonReadErrorCode(str, Enum):
    NOT_FOUND = "not_found"
    IO_ERROR = "io_error"
    TOO_LARGE = "too_large"
    INVALID_UTF8 = "invalid_utf8"
    INVALID_JSON = "invalid_json"
    TOO_COMPLEX = "too_complex"


class BoundedJsonError(ValueError):
    def __init__(
        self,
        code: JsonReadErrorCode,
        *,
        detail: str | None = None,
        line: int | None = None,
    ) -> None:
        super().__init__(code.value)
        self.code = code
        self.detail = detail
        self.line = line


@dataclass(frozen=True, slots=True)
class JsonReadLimits:
    max_bytes: int
    max_depth: int
    max_nodes: int
    max_string_chars: int
    max_integer_digits: int


DEFAULT_JSON_READ_LIMITS = JsonReadLimits(
    max_bytes=8 * 1024 * 1024,
    max_depth=64,
    max_nodes=200_000,
    max_string_chars=1_000_000,
    max_integer_digits=64,
)


def read_bounded_json(
    path: Path,
    limits: JsonReadLimits,
    *,
    reject_duplicate_members: bool = False,
) -> JsonValue:
    """Read one regular JSON file without unbounded allocation or recursion."""
    try:
        with path.open("rb") as stream:
            raw = stream.read(limits.max_bytes + 1)
    except FileNotFoundError:
        raise BoundedJsonError(JsonReadErrorCode.NOT_FOUND) from None
    except OSError as exc:
        raise BoundedJsonError(
            JsonReadErrorCode.IO_ERROR,
            detail=str(exc),
        ) from exc

    return parse_bounded_json(
        raw,
        limits,
        reject_duplicate_members=reject_duplicate_members,
    )


def parse_bounded_json(
    raw: bytes,
    limits: JsonReadLimits,
    *,
    reject_duplicate_members: bool = False,
) -> JsonValue:
    """Decode one in-memory UTF-8 JSON payload under the shared read limits."""
    if type(raw) is not bytes:
        raise BoundedJsonError(JsonReadErrorCode.INVALID_JSON)

    if len(raw) > limits.max_bytes:
        raise BoundedJsonError(JsonReadErrorCode.TOO_LARGE)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise BoundedJsonError(JsonReadErrorCode.INVALID_UTF8) from None

    def parse_int(value: str) -> int:
        digits = value[1:] if value.startswith("-") else value
        if len(digits) > limits.max_integer_digits:
            raise ValueError("JSON integer exceeds the digit limit")
        return int(value)

    def reject_constant(value: str) -> None:
        raise ValueError(f"invalid JSON constant: {value}")

    def unique_object_members(
        pairs: list[tuple[str, object]],
    ) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON object member")
            result[key] = value
        return result

    try:
        decoded: object = json.loads(
            text,
            parse_int=parse_int,
            parse_constant=reject_constant,
            object_pairs_hook=(unique_object_members if reject_duplicate_members else dict),
        )
    except json.JSONDecodeError as exc:
        raise BoundedJsonError(
            JsonReadErrorCode.INVALID_JSON,
            detail=exc.msg,
            line=exc.lineno,
        ) from None
    except (ValueError, RecursionError):
        raise BoundedJsonError(JsonReadErrorCode.INVALID_JSON) from None

    _validate_shape(decoded, limits)
    return decoded  # type: ignore[return-value]


def _validate_shape(value: object, limits: JsonReadLimits) -> None:
    stack: list[tuple[object, int]] = [(value, 0)]
    nodes = 0
    while stack:
        current, depth = stack.pop()
        nodes += 1
        if nodes > limits.max_nodes or depth > limits.max_depth:
            raise BoundedJsonError(JsonReadErrorCode.TOO_COMPLEX)
        if current is None or type(current) in {bool, int}:
            continue
        if type(current) is float:
            if not math.isfinite(current):
                raise BoundedJsonError(JsonReadErrorCode.INVALID_JSON)
            continue
        if type(current) is str:
            _validate_string(current, limits)
            continue
        if type(current) is list:
            stack.extend((child, depth + 1) for child in current)
            continue
        if type(current) is dict:
            nodes += len(current)
            if nodes > limits.max_nodes:
                raise BoundedJsonError(JsonReadErrorCode.TOO_COMPLEX)
            for key, child in current.items():
                if type(key) is not str:
                    raise BoundedJsonError(JsonReadErrorCode.INVALID_JSON)
                _validate_string(key, limits)
                stack.append((child, depth + 1))
            continue
        raise BoundedJsonError(JsonReadErrorCode.INVALID_JSON)


def _validate_string(value: str, limits: JsonReadLimits) -> None:
    if len(value) > limits.max_string_chars or any(
        0xD800 <= ord(character) <= 0xDFFF for character in value
    ):
        raise BoundedJsonError(JsonReadErrorCode.TOO_COMPLEX)
