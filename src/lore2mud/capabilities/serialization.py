"""Canonical JSON, fingerprints, and a bounded schema subset for capabilities."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
import hashlib
import json
import math
import re
from typing import Mapping, cast

from lore2mud._bounded_json import DEFAULT_JSON_READ_LIMITS, parse_bounded_json
from lore2mud.capabilities.contracts import CanonicalJsonObject
from lore2mud.capabilities.semver import SemanticVersion, VersionRequirement


class CapabilitySerializationError(ValueError):
    """Raised when capability JSON is malformed, unbounded, or non-canonical."""


class CapabilitySchemaError(ValueError):
    """Raised when a schema or value is outside the supported deterministic subset."""


_SCHEMA_KEYS = {
    "type",
    "required",
    "properties",
    "additionalProperties",
    "items",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "minLength",
    "maxLength",
    "pattern",
    "minItems",
    "maxItems",
    "uniqueItems",
    "minProperties",
    "maxProperties",
    "enum",
    "const",
    "title",
    "description",
}
_SCHEMA_TYPES = {"object", "array", "string", "integer", "boolean", "null"}


def _normalize_json(value: object, *, path: str = "$", depth: int = 0) -> object:
    limits = DEFAULT_JSON_READ_LIMITS
    if depth > limits.max_depth:
        raise CapabilitySerializationError("capability JSON exceeds maximum depth")
    if value is None or type(value) in {bool, int}:
        if type(value) is int and not (-(2**63) <= cast(int, value) <= 2**63 - 1):
            raise CapabilitySerializationError(f"{path} integer exceeds signed 64-bit range")
        return value
    if type(value) is float:
        if not math.isfinite(cast(float, value)):
            raise CapabilitySerializationError(f"{path} contains a non-finite number")
        raise CapabilitySerializationError(f"{path} floating-point values are not supported")
    if type(value) is str:
        text = cast(str, value)
        if len(text) > limits.max_string_chars:
            raise CapabilitySerializationError(f"{path} string exceeds maximum length")
        if any(0xD800 <= ord(character) <= 0xDFFF for character in text):
            raise CapabilitySerializationError(f"{path} contains an invalid Unicode surrogate")
        return text
    if type(value) in {list, tuple}:
        values = cast(list[object] | tuple[object, ...], value)
        if len(values) > limits.max_nodes:
            raise CapabilitySerializationError(f"{path} array exceeds maximum length")
        return [
            _normalize_json(item, path=f"{path}/{index}", depth=depth + 1)
            for index, item in enumerate(values)
        ]
    if type(value) is dict:
        mapping = cast(dict[object, object], value)
        if len(mapping) * 2 > limits.max_nodes:
            raise CapabilitySerializationError(f"{path} object exceeds maximum size")
        normalized: dict[str, object] = {}
        for key, item in mapping.items():
            if type(key) is not str:
                raise CapabilitySerializationError(f"{path} object keys must be strings")
            normalized[cast(str, key)] = _normalize_json(
                item,
                path=f"{path}/{_pointer_escape(cast(str, key))}",
                depth=depth + 1,
            )
        return normalized
    raise CapabilitySerializationError(
        f"{path} contains unsupported JSON value type {type(value).__name__}"
    )


def canonical_json_bytes(document: object) -> bytes:
    """Serialize one bounded JSON value with sorted keys, two spaces, UTF-8, and LF."""
    normalized = _normalize_json(document)
    try:
        payload = (
            json.dumps(
                normalized,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (UnicodeEncodeError, ValueError) as exc:
        raise CapabilitySerializationError("capability JSON cannot be encoded") from exc
    if len(payload) > DEFAULT_JSON_READ_LIMITS.max_bytes:
        raise CapabilitySerializationError("capability JSON exceeds maximum encoded size")
    return payload


def parse_canonical_json_bytes(payload: bytes) -> object:
    """Parse bytes only when they are the exact canonical capability encoding."""
    if type(payload) is not bytes:
        raise CapabilitySerializationError("canonical capability JSON must be bytes")
    try:
        document = parse_bounded_json(payload, DEFAULT_JSON_READ_LIMITS)
    except (UnicodeDecodeError, ValueError) as exc:
        raise CapabilitySerializationError("capability JSON is invalid or out of bounds") from exc
    if canonical_json_bytes(document) != payload:
        raise CapabilitySerializationError("capability JSON bytes are not canonical")
    return document


def canonical_json_object(
    document: object,
    *,
    schema: CanonicalJsonObject | None = None,
) -> CanonicalJsonObject:
    normalized = _normalize_json(document)
    if type(normalized) is not dict:
        raise CapabilitySerializationError("capability JSON value must be an object")
    if schema is not None:
        validate_json_schema(normalized, parse_canonical_json_object(schema))
    return CanonicalJsonObject(canonical_json_bytes(normalized))


def parse_canonical_json_object(
    value: CanonicalJsonObject,
    *,
    schema: CanonicalJsonObject | None = None,
) -> dict[str, object]:
    if not isinstance(value, CanonicalJsonObject):
        raise CapabilitySerializationError("expected CanonicalJsonObject")
    document = parse_canonical_json_bytes(value.canonical_bytes)
    if type(document) is not dict:
        raise CapabilitySerializationError("canonical capability value must be an object")
    parsed = cast(dict[str, object], document)
    if schema is not None:
        validate_json_schema(parsed, parse_canonical_json_object(schema))
    return parsed


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def fingerprint_capability_value(value: object) -> str:
    return sha256_bytes(canonical_json_bytes(capability_value_to_document(value)))


def capability_value_to_document(value: object) -> object:
    """Convert capability values without leaking the CanonicalJsonObject byte wrapper."""
    if isinstance(value, CanonicalJsonObject):
        return parse_canonical_json_object(value)
    if isinstance(value, SemanticVersion):
        return str(value)
    if isinstance(value, VersionRequirement):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: capability_value_to_document(getattr(value, field.name))
            for field in fields(value)
        }
    if type(value) is tuple:
        return [capability_value_to_document(item) for item in cast(tuple[object, ...], value)]
    if type(value) is list:
        return [capability_value_to_document(item) for item in cast(list[object], value)]
    if type(value) is dict:
        mapping = cast(dict[object, object], value)
        return {
            cast(str, key): capability_value_to_document(item)
            for key, item in mapping.items()
        }
    if value is None or type(value) in {str, int, bool}:
        return value
    raise CapabilitySerializationError(
        f"unsupported capability contract value {type(value).__name__}"
    )


def validate_schema_contract(schema: CanonicalJsonObject | Mapping[str, object]) -> None:
    document = (
        parse_canonical_json_object(schema)
        if isinstance(schema, CanonicalJsonObject)
        else dict(schema)
    )
    _validate_schema_definition(document, path="$schema")


def validate_json_schema(
    document: object,
    schema: CanonicalJsonObject | Mapping[str, object],
) -> None:
    schema_document = (
        parse_canonical_json_object(schema)
        if isinstance(schema, CanonicalJsonObject)
        else dict(schema)
    )
    _validate_schema_definition(schema_document, path="$schema")
    _validate_schema_value(_normalize_json(document), schema_document, path="$value")


def _validate_schema_definition(schema: object, *, path: str) -> None:
    if type(schema) is not dict:
        raise CapabilitySchemaError(f"{path} must be an object")
    mapping = cast(dict[object, object], schema)
    if any(type(key) is not str for key in mapping):
        raise CapabilitySchemaError(f"{path} keys must be strings")
    string_mapping = cast(dict[str, object], mapping)
    unknown = set(string_mapping).difference(_SCHEMA_KEYS)
    if unknown:
        raise CapabilitySchemaError(f"{path} uses unsupported keywords: {sorted(unknown)!r}")

    schema_type = mapping.get("type")
    if type(schema_type) is not str or schema_type not in _SCHEMA_TYPES:
        raise CapabilitySchemaError(f"{path}.type must be one supported JSON type")
    for keyword in ("title", "description", "pattern"):
        if keyword in mapping and type(mapping[keyword]) is not str:
            raise CapabilitySchemaError(f"{path}.{keyword} must be a string")
    if "pattern" in mapping:
        try:
            re.compile(cast(str, mapping["pattern"]))
        except re.error as exc:
            raise CapabilitySchemaError(f"{path}.pattern is invalid") from exc

    for keyword in (
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
        "minProperties",
        "maxProperties",
    ):
        if keyword in mapping and type(mapping[keyword]) is not int:
            raise CapabilitySchemaError(f"{path}.{keyword} must be an integer")
    for minimum_name, maximum_name in (
        ("minLength", "maxLength"),
        ("minItems", "maxItems"),
        ("minProperties", "maxProperties"),
    ):
        minimum = mapping.get(minimum_name)
        maximum = mapping.get(maximum_name)
        if minimum is not None and cast(int, minimum) < 0:
            raise CapabilitySchemaError(f"{path}.{minimum_name} cannot be negative")
        if maximum is not None and cast(int, maximum) < 0:
            raise CapabilitySchemaError(f"{path}.{maximum_name} cannot be negative")
        if (
            minimum is not None
            and maximum is not None
            and cast(int, minimum) > cast(int, maximum)
        ):
            raise CapabilitySchemaError(f"{path} has inverted bounds")

    if "enum" in mapping:
        enum_values = mapping["enum"]
        if type(enum_values) is not list or not enum_values:
            raise CapabilitySchemaError(f"{path}.enum must be a non-empty array")
        canonical_values = [canonical_json_bytes(item) for item in cast(list[object], enum_values)]
        if len(set(canonical_values)) != len(canonical_values):
            raise CapabilitySchemaError(f"{path}.enum must not contain duplicates")
    if "const" in mapping:
        _normalize_json(mapping["const"], path=f"{path}.const")

    if schema_type == "object":
        properties = mapping.get("properties", {})
        if type(properties) is not dict:
            raise CapabilitySchemaError(f"{path}.properties must be an object")
        for name, child in cast(dict[object, object], properties).items():
            if type(name) is not str:
                raise CapabilitySchemaError(f"{path}.properties keys must be strings")
            _validate_schema_definition(child, path=f"{path}.properties.{name}")
        required = mapping.get("required", [])
        if type(required) is not list or any(type(item) is not str for item in required):
            raise CapabilitySchemaError(f"{path}.required must be an array of strings")
        if len(set(cast(list[str], required))) != len(cast(list[str], required)):
            raise CapabilitySchemaError(f"{path}.required must not contain duplicates")
        if not set(cast(list[str], required)).issubset(set(cast(dict[object, object], properties))):
            raise CapabilitySchemaError(f"{path}.required names must exist in properties")
        additional = mapping.get("additionalProperties", True)
        if type(additional) is not bool:
            raise CapabilitySchemaError(f"{path}.additionalProperties must be boolean")
    elif any(keyword in mapping for keyword in ("properties", "required", "additionalProperties")):
        raise CapabilitySchemaError(f"{path} uses object keywords for a non-object schema")

    if schema_type == "array":
        if "items" not in mapping:
            raise CapabilitySchemaError(f"{path}.items is required for arrays")
        _validate_schema_definition(mapping["items"], path=f"{path}.items")
        if "uniqueItems" in mapping and type(mapping["uniqueItems"]) is not bool:
            raise CapabilitySchemaError(f"{path}.uniqueItems must be boolean")
    elif any(keyword in mapping for keyword in ("items", "minItems", "maxItems", "uniqueItems")):
        raise CapabilitySchemaError(f"{path} uses array keywords for a non-array schema")


def _validate_schema_value(value: object, schema: Mapping[str, object], *, path: str) -> None:
    if "const" in schema and canonical_json_bytes(value) != canonical_json_bytes(schema["const"]):
        raise CapabilitySchemaError(f"{path} does not match const")
    if "enum" in schema:
        candidate = canonical_json_bytes(value)
        allowed = {canonical_json_bytes(item) for item in cast(list[object], schema["enum"])}
        if candidate not in allowed:
            raise CapabilitySchemaError(f"{path} is not in enum")

    schema_type = cast(str, schema["type"])
    type_matches = {
        "object": type(value) is dict,
        "array": type(value) is list,
        "string": type(value) is str,
        "integer": type(value) is int,
        "boolean": type(value) is bool,
        "null": value is None,
    }
    if not type_matches[schema_type]:
        raise CapabilitySchemaError(f"{path} must be {schema_type}")

    if schema_type == "object":
        mapping = cast(dict[str, object], value)
        properties = cast(dict[str, object], schema.get("properties", {}))
        required = cast(list[str], schema.get("required", []))
        missing = [name for name in required if name not in mapping]
        if missing:
            raise CapabilitySchemaError(f"{path} is missing required properties {missing!r}")
        if schema.get("additionalProperties", True) is False:
            extras = set(mapping).difference(properties)
            if extras:
                raise CapabilitySchemaError(f"{path} contains additional properties {sorted(extras)!r}")
        if "minProperties" in schema and len(mapping) < cast(int, schema["minProperties"]):
            raise CapabilitySchemaError(f"{path} has too few properties")
        if "maxProperties" in schema and len(mapping) > cast(int, schema["maxProperties"]):
            raise CapabilitySchemaError(f"{path} has too many properties")
        for name, child_schema in properties.items():
            if name in mapping:
                _validate_schema_value(
                    mapping[name],
                    cast(Mapping[str, object], child_schema),
                    path=f"{path}/{_pointer_escape(name)}",
                )
    elif schema_type == "array":
        values = cast(list[object], value)
        if "minItems" in schema and len(values) < cast(int, schema["minItems"]):
            raise CapabilitySchemaError(f"{path} has too few items")
        if "maxItems" in schema and len(values) > cast(int, schema["maxItems"]):
            raise CapabilitySchemaError(f"{path} has too many items")
        if schema.get("uniqueItems", False):
            encoded = [canonical_json_bytes(item) for item in values]
            if len(set(encoded)) != len(encoded):
                raise CapabilitySchemaError(f"{path} items must be unique")
        item_schema = cast(Mapping[str, object], schema["items"])
        for index, item in enumerate(values):
            _validate_schema_value(item, item_schema, path=f"{path}/{index}")
    elif schema_type == "string":
        text = cast(str, value)
        if "minLength" in schema and len(text) < cast(int, schema["minLength"]):
            raise CapabilitySchemaError(f"{path} is shorter than minLength")
        if "maxLength" in schema and len(text) > cast(int, schema["maxLength"]):
            raise CapabilitySchemaError(f"{path} is longer than maxLength")
        if "pattern" in schema and re.fullmatch(cast(str, schema["pattern"]), text) is None:
            raise CapabilitySchemaError(f"{path} does not match pattern")
    elif schema_type == "integer":
        number = cast(int, value)
        if "minimum" in schema and number < cast(int, schema["minimum"]):
            raise CapabilitySchemaError(f"{path} is below minimum")
        if "maximum" in schema and number > cast(int, schema["maximum"]):
            raise CapabilitySchemaError(f"{path} is above maximum")
        if "exclusiveMinimum" in schema and number <= cast(int, schema["exclusiveMinimum"]):
            raise CapabilitySchemaError(f"{path} is below exclusiveMinimum")
        if "exclusiveMaximum" in schema and number >= cast(int, schema["exclusiveMaximum"]):
            raise CapabilitySchemaError(f"{path} is above exclusiveMaximum")


def _pointer_escape(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")
