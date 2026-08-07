"""Opaque story, scene, and resume anchors with explicit migrations."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import TypeVar, cast

from lore2mud.authoring.provenance import is_opaque_public_id
from lore2mud.authoring.serialization import (
    canonical_json_bytes,
    sha256_bytes,
)


_MAX_COLLECTION = 4096
_MAX_TEXT = 256
_EnumT = TypeVar("_EnumT", bound=Enum)


class AnchorKind(str, Enum):
    STORY = "story"
    SCENE = "scene"
    RESUME = "resume"


@dataclass(frozen=True, slots=True)
class StoryAnchor:
    anchor_id: str
    kind: AnchorKind
    project_element_id: str
    package_element_id: str


@dataclass(frozen=True, slots=True)
class AnchorMigration:
    migration_id: str
    from_anchor_id: str
    to_anchor_ids: tuple[str, ...]
    decision_id: str


@dataclass(frozen=True, slots=True)
class AnchorResolution:
    anchor_id: str
    resolved_anchor_ids: tuple[str, ...]
    migrated: bool


@dataclass(frozen=True, slots=True)
class AnchorMigrationReport:
    format_version: int
    required_anchor_ids: tuple[str, ...]
    resolutions: tuple[AnchorResolution, ...]
    migrations: tuple[AnchorMigration, ...] = ()
    previous_anchors: tuple[StoryAnchor, ...] = ()


class AnchorValidationError(ValueError):
    """Raised when anchors or an incremental migration are not resolvable."""

    def __init__(self, issues: Sequence[str]) -> None:
        self.issues = tuple(issues)
        super().__init__("; ".join(self.issues))


def story_anchor_to_document(value: StoryAnchor) -> dict[str, object]:
    return {
        "anchor_id": value.anchor_id,
        "kind": value.kind.value,
        "project_element_id": value.project_element_id,
        "package_element_id": value.package_element_id,
    }


def anchor_migration_to_document(value: AnchorMigration) -> dict[str, object]:
    return {
        "migration_id": value.migration_id,
        "from_anchor_id": value.from_anchor_id,
        "to_anchor_ids": list(value.to_anchor_ids),
        "decision_id": value.decision_id,
    }


def anchor_migration_report_to_document(
    value: AnchorMigrationReport,
) -> dict[str, object]:
    return {
        "format_version": value.format_version,
        "required_anchor_ids": sorted(value.required_anchor_ids),
        "resolutions": [
            {
                "anchor_id": item.anchor_id,
                "resolved_anchor_ids": list(item.resolved_anchor_ids),
                "migrated": item.migrated,
            }
            for item in sorted(value.resolutions, key=lambda item: item.anchor_id)
        ],
        "migrations": [
            anchor_migration_to_document(item)
            for item in sorted(value.migrations, key=lambda item: item.migration_id)
        ],
        "previous_anchors": [
            story_anchor_to_document(item)
            for item in sorted(value.previous_anchors, key=lambda item: item.anchor_id)
        ],
    }


def anchor_migration_report_bytes(value: AnchorMigrationReport) -> bytes:
    return canonical_json_bytes(anchor_migration_report_to_document(value))


def anchor_migration_report_sha256(value: AnchorMigrationReport) -> str:
    return sha256_bytes(anchor_migration_report_bytes(value))


def story_anchor_set_sha256(anchors: Sequence[StoryAnchor]) -> str:
    normalized = validate_anchor_set(anchors)
    return sha256_bytes(
        canonical_json_bytes([story_anchor_to_document(item) for item in normalized])
    )


def load_story_anchor_document(document: object, *, location: str = "anchor") -> StoryAnchor:
    issues: list[str] = []
    data = _mapping(document, location, issues)
    _keys(data, {"anchor_id", "kind", "project_element_id", "package_element_id"}, location, issues)
    anchor = StoryAnchor(
        anchor_id=_stable_id(data.get("anchor_id"), f"{location}.anchor_id", issues),
        kind=_enum(AnchorKind, data.get("kind"), f"{location}.kind", issues, AnchorKind.SCENE),
        project_element_id=_stable_id(
            data.get("project_element_id"), f"{location}.project_element_id", issues
        ),
        package_element_id=_stable_id(
            data.get("package_element_id"), f"{location}.package_element_id", issues
        ),
    )
    if issues:
        raise AnchorValidationError(issues)
    return anchor


def load_anchor_migration_document(
    document: object,
    *,
    location: str = "migration",
) -> AnchorMigration:
    issues: list[str] = []
    data = _mapping(document, location, issues)
    _keys(
        data, {"migration_id", "from_anchor_id", "to_anchor_ids", "decision_id"}, location, issues
    )
    migration = AnchorMigration(
        migration_id=_stable_id(data.get("migration_id"), f"{location}.migration_id", issues),
        from_anchor_id=_stable_id(data.get("from_anchor_id"), f"{location}.from_anchor_id", issues),
        to_anchor_ids=_stable_id_set(
            data.get("to_anchor_ids"), f"{location}.to_anchor_ids", issues
        ),
        decision_id=_stable_id(data.get("decision_id"), f"{location}.decision_id", issues),
    )
    if not migration.to_anchor_ids:
        issues.append(f"{location}.to_anchor_ids must not be empty")
    if migration.from_anchor_id in migration.to_anchor_ids:
        issues.append(f"{location} cannot migrate an anchor to itself")
    if issues:
        raise AnchorValidationError(issues)
    return migration


def validate_anchor_set(anchors: Sequence[StoryAnchor]) -> tuple[StoryAnchor, ...]:
    if type(anchors) not in {tuple, list} or len(anchors) > _MAX_COLLECTION:
        raise AnchorValidationError((f"anchors must contain at most {_MAX_COLLECTION} entries",))
    normalized: list[StoryAnchor] = []
    seen: set[str] = set()
    for index, anchor in enumerate(anchors):
        try:
            value = load_story_anchor_document(
                story_anchor_to_document(anchor), location=f"anchors[{index}]"
            )
        except (AttributeError, TypeError, ValueError) as exc:
            if isinstance(exc, AnchorValidationError):
                raise
            raise AnchorValidationError(("typed anchor is invalid",)) from exc
        if value.anchor_id in seen:
            raise AnchorValidationError(("anchor IDs must be unique",))
        seen.add(value.anchor_id)
        normalized.append(value)
    return tuple(sorted(normalized, key=lambda item: item.anchor_id))


def validate_anchor_migrations(
    previous_anchors: Sequence[StoryAnchor],
    current_anchors: Sequence[StoryAnchor],
    migrations: Sequence[AnchorMigration],
) -> AnchorMigrationReport:
    """Resolve every previous anchor against the current anchor set."""
    if type(migrations) not in {tuple, list} or len(migrations) > _MAX_COLLECTION:
        raise AnchorValidationError((f"migrations must contain at most {_MAX_COLLECTION} entries",))
    previous = validate_anchor_set(previous_anchors)
    current = validate_anchor_set(current_anchors)
    previous_by_id = {item.anchor_id: item for item in previous}
    current_by_id = {item.anchor_id: item for item in current}
    previous_ids = {item.anchor_id for item in previous}
    current_ids = {item.anchor_id for item in current}

    normalized_migrations: list[AnchorMigration] = []
    seen_migrations: set[str] = set()
    from_ids: set[str] = set()
    issues: list[str] = []
    for anchor_id in sorted(previous_ids & current_ids):
        if previous_by_id[anchor_id] != current_by_id[anchor_id]:
            issues.append("a preserved anchor changed its binding without migration")
    for index, migration in enumerate(migrations):
        try:
            value = load_anchor_migration_document(
                anchor_migration_to_document(migration), location=f"migrations[{index}]"
            )
        except AnchorValidationError as exc:
            issues.extend(exc.issues)
            continue
        if value.migration_id in seen_migrations:
            issues.append("migration IDs must be unique")
        if value.from_anchor_id in from_ids:
            issues.append("an anchor may have only one explicit migration record")
        if value.from_anchor_id not in previous_ids:
            issues.append("migration references an unknown previous anchor")
        if value.from_anchor_id in current_ids:
            issues.append("migration source already exists in the current anchor set")
        if any(
            target not in current_ids and target not in previous_ids
            for target in value.to_anchor_ids
        ):
            issues.append("migration target is not in the current or previous anchor set")
        source_kind = previous_by_id.get(value.from_anchor_id)
        target_kinds: set[AnchorKind] = set()
        for target in value.to_anchor_ids:
            target_anchor = current_by_id.get(target)
            if target_anchor is None:
                target_anchor = previous_by_id.get(target)
            if target_anchor is not None:
                target_kinds.add(target_anchor.kind)
        if source_kind is not None and any(kind is not source_kind.kind for kind in target_kinds):
            issues.append("anchor migration cannot change anchor kind")
        seen_migrations.add(value.migration_id)
        from_ids.add(value.from_anchor_id)
        normalized_migrations.append(value)
    if issues:
        raise AnchorValidationError(issues)

    migration_map = {value.from_anchor_id: value.to_anchor_ids for value in normalized_migrations}
    required = tuple(sorted(previous_ids))

    resolutions: list[AnchorResolution] = []
    resolved_cache: dict[str, frozenset[str]] = {}
    for anchor_id in required:
        resolved, migrated = _resolve_anchor(
            anchor_id,
            current_ids,
            migration_map,
            resolved_cache,
        )
        resolutions.append(
            AnchorResolution(
                anchor_id=anchor_id,
                resolved_anchor_ids=tuple(sorted(resolved)),
                migrated=migrated,
            )
        )
    return AnchorMigrationReport(
        format_version=1,
        required_anchor_ids=required,
        resolutions=tuple(resolutions),
        migrations=tuple(sorted(normalized_migrations, key=lambda item: item.migration_id)),
        previous_anchors=previous,
    )


def load_anchor_migration_report_document(document: object) -> AnchorMigrationReport:
    issues: list[str] = []
    data = _mapping(document, "anchor_report", issues)
    _keys(
        data,
        {
            "format_version",
            "required_anchor_ids",
            "resolutions",
            "migrations",
            "previous_anchors",
        },
        "anchor_report",
        issues,
    )
    if _integer(data.get("format_version"), "anchor_report.format_version", issues) != 1:
        issues.append("anchor_report.format_version must be 1")
    previous: list[StoryAnchor] = []
    for index, raw in enumerate(
        _bounded_list(data.get("previous_anchors"), "anchor_report.previous_anchors", issues)
    ):
        try:
            previous.append(
                load_story_anchor_document(raw, location=f"anchor_report.previous_anchors[{index}]")
            )
        except AnchorValidationError as exc:
            issues.extend(exc.issues)
    try:
        normalized_previous = validate_anchor_set(previous)
    except AnchorValidationError as exc:
        issues.extend(exc.issues)
        normalized_previous = tuple(previous)
    required = _stable_id_set(
        data.get("required_anchor_ids"), "anchor_report.required_anchor_ids", issues
    )
    resolutions: list[AnchorResolution] = []
    for index, raw in enumerate(
        _bounded_list(data.get("resolutions"), "anchor_report.resolutions", issues)
    ):
        location = f"anchor_report.resolutions[{index}]"
        item = _mapping(raw, location, issues)
        _keys(item, {"anchor_id", "resolved_anchor_ids", "migrated"}, location, issues)
        resolutions.append(
            AnchorResolution(
                anchor_id=_stable_id(item.get("anchor_id"), f"{location}.anchor_id", issues),
                resolved_anchor_ids=_stable_id_set(
                    item.get("resolved_anchor_ids"),
                    f"{location}.resolved_anchor_ids",
                    issues,
                ),
                migrated=_boolean(item.get("migrated"), f"{location}.migrated", issues),
            )
        )
    migrations: list[AnchorMigration] = []
    for index, raw in enumerate(
        _bounded_list(data.get("migrations"), "anchor_report.migrations", issues)
    ):
        try:
            migrations.append(
                load_anchor_migration_document(raw, location=f"anchor_report.migrations[{index}]")
            )
        except AnchorValidationError as exc:
            issues.extend(exc.issues)
    resolution_ids = [item.anchor_id for item in resolutions]
    if len(set(resolution_ids)) != len(resolution_ids):
        issues.append("anchor_report.resolutions contains duplicate IDs")
    if set(resolution_ids) != set(required):
        issues.append("anchor_report.resolutions must cover required_anchor_ids")
    if set(required) != {item.anchor_id for item in normalized_previous}:
        issues.append("anchor_report must require every previous anchor")
    if any(not item.resolved_anchor_ids for item in resolutions):
        issues.append("anchor_report.resolutions must resolve to at least one anchor")
    if issues:
        raise AnchorValidationError(issues)
    return AnchorMigrationReport(
        format_version=1,
        required_anchor_ids=required,
        resolutions=tuple(sorted(resolutions, key=lambda item: item.anchor_id)),
        migrations=tuple(sorted(migrations, key=lambda item: item.migration_id)),
        previous_anchors=normalized_previous,
    )


def _resolve_anchor(
    anchor_id: str,
    current_ids: set[str],
    migration_map: dict[str, tuple[str, ...]],
    resolved_cache: dict[str, frozenset[str]],
) -> tuple[set[str], bool]:
    if anchor_id in current_ids:
        return {anchor_id}, False
    if anchor_id in resolved_cache:
        return set(resolved_cache[anchor_id]), True

    # Use an explicit post-order stack so a valid long migration chain cannot
    # escape the public contract as a Python RecursionError.
    active: set[str] = set()
    stack: list[tuple[str, bool]] = [(anchor_id, False)]
    while stack:
        identifier, completed = stack.pop()
        if identifier in current_ids:
            resolved_cache.setdefault(identifier, frozenset((identifier,)))
            continue
        if identifier in resolved_cache:
            continue
        if completed:
            targets = migration_map[identifier]
            resolved: set[str] = set()
            for target in targets:
                values = resolved_cache.get(target)
                if values is None:
                    raise AnchorValidationError(("unresolved anchor migration",))
                resolved.update(values)
            if not resolved:
                raise AnchorValidationError(("anchor migration resolves to no current anchor",))
            active.remove(identifier)
            resolved_cache[identifier] = frozenset(resolved)
            continue
        if identifier in active:
            raise AnchorValidationError(("anchor migrations contain a cycle",))
        targets = migration_map.get(identifier)
        if targets is None:
            raise AnchorValidationError(("unresolved anchor migration",))
        active.add(identifier)
        stack.append((identifier, True))
        for target in reversed(targets):
            if target in active:
                raise AnchorValidationError(("anchor migrations contain a cycle",))
            if target not in resolved_cache:
                stack.append((target, False))

    values = resolved_cache.get(anchor_id)
    if values is None:
        raise AnchorValidationError(("unresolved anchor migration",))
    return set(values), True


def _mapping(value: object, location: str, issues: list[str]) -> dict[str, object]:
    if type(value) is not dict:
        issues.append(f"{location} must be an object")
        return {}
    if not all(type(key) is str for key in value):
        issues.append(f"{location} keys must be strings")
        return {}
    return cast(dict[str, object], value)


def _keys(data: dict[str, object], expected: set[str], location: str, issues: list[str]) -> None:
    if set(data) != expected:
        issues.append(f"{location} fields are invalid")


def _bounded_list(value: object, location: str, issues: list[str]) -> list[object]:
    if type(value) is not list:
        issues.append(f"{location} must be an array")
        return []
    values = cast(list[object], value)
    if len(values) > _MAX_COLLECTION:
        issues.append(f"{location} exceeds {_MAX_COLLECTION} entries")
        return values[:_MAX_COLLECTION]
    return values


def _stable_id(value: object, location: str, issues: list[str]) -> str:
    if not is_opaque_public_id(value):
        issues.append(f"{location} must be an opaque public-safe ID")
        return "invalid_id"
    assert isinstance(value, str)
    return value


def _stable_id_set(value: object, location: str, issues: list[str]) -> tuple[str, ...]:
    values = _bounded_list(value, location, issues)
    identifiers = [
        _stable_id(item, f"{location}[{index}]", issues) for index, item in enumerate(values)
    ]
    if len(set(identifiers)) != len(identifiers):
        issues.append(f"{location} contains duplicate IDs")
    return tuple(sorted(set(identifiers)))


def _integer(value: object, location: str, issues: list[str]) -> int:
    if type(value) is not int:
        issues.append(f"{location} must be an integer")
        return 0
    return value


def _boolean(value: object, location: str, issues: list[str]) -> bool:
    if type(value) is not bool:
        issues.append(f"{location} must be a boolean")
        return False
    return value


def _enum(
    enum_type: type[_EnumT],
    value: object,
    location: str,
    issues: list[str],
    fallback: _EnumT,
) -> _EnumT:
    if type(value) is not str:
        issues.append(f"{location} must be a supported value")
        return fallback
    try:
        return enum_type(value)
    except ValueError:
        issues.append(f"{location} must be a supported value")
        return fallback
