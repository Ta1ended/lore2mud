"""Immutable contracts for typed narrative state and safe conditions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal, TypeAlias


NarrativeValue: TypeAlias = bool | int | str
QuestStatus: TypeAlias = Literal["not_accepted", "active", "completed"]


@dataclass(frozen=True, slots=True)
class BoolStateDefinition:
    id: str
    initial: bool
    kind: Literal["bool"] = field(init=False, default="bool")


@dataclass(frozen=True, slots=True)
class IntStateDefinition:
    id: str
    initial: int
    minimum: int | None = None
    maximum: int | None = None
    kind: Literal["int"] = field(init=False, default="int")


@dataclass(frozen=True, slots=True)
class EnumStateDefinition:
    id: str
    initial: str
    values: tuple[str, ...]
    kind: Literal["enum"] = field(init=False, default="enum")


NarrativeStateDefinition: TypeAlias = (
    BoolStateDefinition | IntStateDefinition | EnumStateDefinition
)


def narrative_value_is_valid(
    definition: NarrativeStateDefinition,
    value: object,
) -> bool:
    """Return whether a runtime value exactly satisfies its declaration."""
    if isinstance(definition, BoolStateDefinition):
        return isinstance(value, bool)
    if isinstance(definition, IntStateDefinition):
        if not isinstance(value, int) or isinstance(value, bool):
            return False
        if definition.minimum is not None and value < definition.minimum:
            return False
        return definition.maximum is None or value <= definition.maximum
    return isinstance(value, str) and value in definition.values


@dataclass(frozen=True, slots=True)
class StateEqualsCondition:
    state_id: str
    value: NarrativeValue
    kind: Literal["state_equals"] = field(init=False, default="state_equals")


@dataclass(frozen=True, slots=True)
class StateCompareCondition:
    state_id: str
    operator: Literal["lt", "lte", "gt", "gte"]
    value: int
    kind: Literal["state_compare"] = field(init=False, default="state_compare")


@dataclass(frozen=True, slots=True)
class HasItemCondition:
    item_id: str
    quantity: int
    kind: Literal["has_item"] = field(init=False, default="has_item")


@dataclass(frozen=True, slots=True)
class AtLocationCondition:
    location_id: str
    kind: Literal["at_location"] = field(init=False, default="at_location")


@dataclass(frozen=True, slots=True)
class QuestStatusCondition:
    quest_id: str
    status: QuestStatus
    kind: Literal["quest_status"] = field(init=False, default="quest_status")


@dataclass(frozen=True, slots=True)
class AllCondition:
    conditions: tuple[NarrativeCondition, ...]
    kind: Literal["all"] = field(init=False, default="all")


@dataclass(frozen=True, slots=True)
class AnyCondition:
    conditions: tuple[NarrativeCondition, ...]
    kind: Literal["any"] = field(init=False, default="any")


@dataclass(frozen=True, slots=True)
class NotCondition:
    condition: NarrativeCondition
    kind: Literal["not"] = field(init=False, default="not")


NarrativeCondition: TypeAlias = (
    StateEqualsCondition
    | StateCompareCondition
    | HasItemCondition
    | AtLocationCondition
    | QuestStatusCondition
    | AllCondition
    | AnyCondition
    | NotCondition
)


@dataclass(frozen=True, slots=True)
class ConditionContext:
    """One immutable-by-contract snapshot consumed by the pure evaluator."""

    state_values: Mapping[str, NarrativeValue]
    inventory_quantities: Mapping[str, int]
    location_id: str
    quest_statuses: Mapping[str, QuestStatus]
