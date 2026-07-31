"""Pure evaluation for the bounded narrative condition AST."""

from __future__ import annotations

from lore2mud.narrative.models import (
    AllCondition,
    AnyCondition,
    AtLocationCondition,
    ConditionContext,
    HasItemCondition,
    NarrativeCondition,
    NotCondition,
    QuestStatusCondition,
    StateCompareCondition,
    StateEqualsCondition,
)


def evaluate_condition(
    condition: NarrativeCondition,
    context: ConditionContext,
) -> bool:
    """Evaluate a validated condition without changing its context."""
    if isinstance(condition, StateEqualsCondition):
        current = context.state_values[condition.state_id]
        return type(current) is type(condition.value) and current == condition.value
    if isinstance(condition, StateCompareCondition):
        current = context.state_values[condition.state_id]
        if not isinstance(current, int) or isinstance(current, bool):
            raise TypeError("state_compare requires an integer state")
        comparisons = {
            "lt": current < condition.value,
            "lte": current <= condition.value,
            "gt": current > condition.value,
            "gte": current >= condition.value,
        }
        return comparisons[condition.operator]
    if isinstance(condition, HasItemCondition):
        return context.inventory_quantities.get(condition.item_id, 0) >= condition.quantity
    if isinstance(condition, AtLocationCondition):
        return context.location_id == condition.location_id
    if isinstance(condition, QuestStatusCondition):
        return context.quest_statuses.get(condition.quest_id, "not_accepted") == condition.status
    if isinstance(condition, AllCondition):
        return all(evaluate_condition(child, context) for child in condition.conditions)
    if isinstance(condition, AnyCondition):
        return any(evaluate_condition(child, context) for child in condition.conditions)
    if isinstance(condition, NotCondition):
        return not evaluate_condition(condition.condition, context)
    raise TypeError(f"unsupported narrative condition: {type(condition).__name__}")
