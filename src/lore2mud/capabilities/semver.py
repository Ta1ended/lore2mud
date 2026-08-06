"""Strict bounded Semantic Versioning contracts for capability resolution."""

from __future__ import annotations

from dataclasses import dataclass
from functools import total_ordering
import re
from typing import Self


INT64_MAX = 2**63 - 1
_IDENTIFIER_RE = re.compile(r"^[0-9A-Za-z-]+$")
_CORE_NUMBER_RE = re.compile(r"^(?:0|[1-9][0-9]*)$")


class SemanticVersionError(ValueError):
    """Raised when a semantic version or requirement is not canonical."""


def _parse_bounded_number(value: str, *, location: str) -> int:
    if _CORE_NUMBER_RE.fullmatch(value) is None:
        raise SemanticVersionError(f"{location} must be a canonical non-negative integer")
    number = int(value)
    if number > INT64_MAX:
        raise SemanticVersionError(f"{location} exceeds signed 64-bit range")
    return number


def _parse_identifiers(value: str, *, location: str) -> tuple[str, ...]:
    identifiers = tuple(value.split("."))
    if not identifiers or any(not identifier for identifier in identifiers):
        raise SemanticVersionError(f"{location} identifiers must be non-empty")
    for identifier in identifiers:
        if not identifier.isascii() or _IDENTIFIER_RE.fullmatch(identifier) is None:
            raise SemanticVersionError(
                f"{location} identifiers must use ASCII letters, digits, or hyphen"
            )
        if identifier.isdigit():
            _parse_bounded_number(identifier, location=f"{location} identifier")
    return identifiers


def compare_precedence(left: SemanticVersion, right: SemanticVersion) -> int:
    """Compare SemVer precedence while intentionally ignoring build metadata."""
    left_core = (left.major, left.minor, left.patch)
    right_core = (right.major, right.minor, right.patch)
    if left_core < right_core:
        return -1
    if left_core > right_core:
        return 1
    if not left.prerelease and not right.prerelease:
        return 0
    if not left.prerelease:
        return 1
    if not right.prerelease:
        return -1
    for left_identifier, right_identifier in zip(
        left.prerelease,
        right.prerelease,
        strict=False,
    ):
        if left_identifier == right_identifier:
            continue
        left_numeric = left_identifier.isdigit()
        right_numeric = right_identifier.isdigit()
        if left_numeric and right_numeric:
            return -1 if int(left_identifier) < int(right_identifier) else 1
        if left_numeric:
            return -1
        if right_numeric:
            return 1
        return -1 if left_identifier < right_identifier else 1
    if len(left.prerelease) < len(right.prerelease):
        return -1
    if len(left.prerelease) > len(right.prerelease):
        return 1
    return 0


@total_ordering
@dataclass(frozen=True, slots=True)
class SemanticVersion:
    """A canonical SemVer 2.0.0 value with bounded numeric identifiers."""

    major: int
    minor: int
    patch: int
    prerelease: tuple[str, ...] = ()
    build: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name, value in (("major", self.major), ("minor", self.minor), ("patch", self.patch)):
            if type(value) is not int or value < 0 or value > INT64_MAX:
                raise SemanticVersionError(
                    f"{name} must be a non-negative signed 64-bit integer"
                )
        for name, identifiers in (("prerelease", self.prerelease), ("build", self.build)):
            if type(identifiers) is not tuple:
                raise SemanticVersionError(f"{name} identifiers must be tuple-backed")
            for identifier in identifiers:
                if type(identifier) is not str:
                    raise SemanticVersionError(f"{name} identifiers must be strings")
            if identifiers:
                parsed = _parse_identifiers(".".join(identifiers), location=name)
                if parsed != identifiers:
                    raise SemanticVersionError(f"{name} identifiers are not canonical")

    @classmethod
    def parse(cls, value: str) -> Self:
        if type(value) is not str or not value or not value.isascii():
            raise SemanticVersionError("semantic version must be a non-empty ASCII string")
        if value != value.strip():
            raise SemanticVersionError("semantic version must not contain surrounding whitespace")

        core_and_prerelease, separator, build_text = value.partition("+")
        if separator and (not build_text or "+" in build_text):
            raise SemanticVersionError("semantic version build metadata is malformed")
        core_text, prerelease_separator, prerelease_text = core_and_prerelease.partition("-")
        if prerelease_separator and not prerelease_text:
            raise SemanticVersionError("semantic version prerelease is malformed")
        core_parts = core_text.split(".")
        if len(core_parts) != 3:
            raise SemanticVersionError("semantic version core must contain major.minor.patch")

        prerelease = (
            _parse_identifiers(prerelease_text, location="prerelease")
            if prerelease_separator
            else ()
        )
        build = _parse_identifiers(build_text, location="build") if separator else ()
        parsed = cls(
            major=_parse_bounded_number(core_parts[0], location="major"),
            minor=_parse_bounded_number(core_parts[1], location="minor"),
            patch=_parse_bounded_number(core_parts[2], location="patch"),
            prerelease=prerelease,
            build=build,
        )
        if str(parsed) != value:
            raise SemanticVersionError("semantic version is not canonical")
        return parsed

    @property
    def is_prerelease(self) -> bool:
        return bool(self.prerelease)

    def same_precedence(self, other: SemanticVersion) -> bool:
        return compare_precedence(self, other) == 0

    def without_build(self) -> SemanticVersion:
        return SemanticVersion(
            self.major,
            self.minor,
            self.patch,
            self.prerelease,
        )

    def __str__(self) -> str:
        value = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            value += "-" + ".".join(self.prerelease)
        if self.build:
            value += "+" + ".".join(self.build)
        return value

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, SemanticVersion):
            return NotImplemented
        return compare_precedence(self, other) < 0


@dataclass(frozen=True, slots=True)
class VersionComparator:
    operator: str
    version: SemanticVersion

    def __post_init__(self) -> None:
        if self.operator not in {">", ">=", "<", "<=", "="}:
            raise SemanticVersionError("unsupported semantic-version comparator")

    def matches(self, candidate: SemanticVersion) -> bool:
        comparison = compare_precedence(candidate, self.version)
        if self.operator == ">":
            return comparison > 0
        if self.operator == ">=":
            return comparison >= 0
        if self.operator == "<":
            return comparison < 0
        if self.operator == "<=":
            return comparison <= 0
        if self.version.build:
            return candidate == self.version
        return comparison == 0

    def __str__(self) -> str:
        return f"{self.operator}{self.version}"


@dataclass(frozen=True, slots=True)
class VersionRequirement:
    """An exact version or one canonical bounded lower/upper conjunction."""

    exact: SemanticVersion | None = None
    lower: SemanticVersion | None = None
    lower_inclusive: bool = False
    upper: SemanticVersion | None = None
    upper_inclusive: bool = False

    def __post_init__(self) -> None:
        if self.exact is not None:
            if self.lower is not None or self.upper is not None:
                raise SemanticVersionError("exact requirements cannot also contain bounds")
            if self.lower_inclusive or self.upper_inclusive:
                raise SemanticVersionError("exact requirements cannot contain bound flags")
            return
        if self.lower is None or self.upper is None:
            raise SemanticVersionError("bounded requirements need both lower and upper bounds")
        if self.lower.build or self.upper.build:
            raise SemanticVersionError("bounded requirements cannot contain build metadata")
        comparison = compare_precedence(self.lower, self.upper)
        if comparison > 0 or comparison == 0:
            raise SemanticVersionError("bounded requirement must have a non-empty ordered range")

    @classmethod
    def parse(cls, value: str) -> Self:
        if type(value) is not str or not value or not value.isascii():
            raise SemanticVersionError("version requirement must be a non-empty ASCII string")
        if value != value.strip() or any(character.isspace() for character in value):
            raise SemanticVersionError("version requirement must use canonical spacing")
        if not value.startswith((">", "<", "=")):
            return cls(exact=SemanticVersion.parse(value))

        parts = value.split(",")
        if len(parts) != 2:
            raise SemanticVersionError(
                "bounded requirement must contain one lower and one upper comparator"
            )
        lower = cls._parse_comparator(parts[0], allowed=(">=", ">"))
        upper = cls._parse_comparator(parts[1], allowed=("<=", "<"))
        requirement = cls(
            lower=lower.version,
            lower_inclusive=lower.operator == ">=",
            upper=upper.version,
            upper_inclusive=upper.operator == "<=",
        )
        if str(requirement) != value:
            raise SemanticVersionError("version requirement is not canonical")
        return requirement

    @staticmethod
    def _parse_comparator(value: str, *, allowed: tuple[str, ...]) -> VersionComparator:
        operator = next((item for item in allowed if value.startswith(item)), None)
        if operator is None:
            raise SemanticVersionError("version requirement comparator is not canonical")
        version_text = value[len(operator) :]
        return VersionComparator(operator, SemanticVersion.parse(version_text))

    @property
    def comparators(self) -> tuple[VersionComparator, ...]:
        if self.exact is not None:
            return (VersionComparator("=", self.exact),)
        assert self.lower is not None and self.upper is not None
        return (
            VersionComparator(">=" if self.lower_inclusive else ">", self.lower),
            VersionComparator("<=" if self.upper_inclusive else "<", self.upper),
        )

    @property
    def allows_prerelease(self) -> bool:
        versions = (self.exact,) if self.exact is not None else (self.lower, self.upper)
        return any(version is not None and version.is_prerelease for version in versions)

    def matches(self, candidate: SemanticVersion, *, include_prerelease: bool | None = None) -> bool:
        if candidate.is_prerelease:
            allowed = self.allows_prerelease if include_prerelease is None else include_prerelease
            if not allowed:
                return False
        return all(comparator.matches(candidate) for comparator in self.comparators)

    def __str__(self) -> str:
        if self.exact is not None:
            return str(self.exact)
        return ",".join(str(comparator) for comparator in self.comparators)
