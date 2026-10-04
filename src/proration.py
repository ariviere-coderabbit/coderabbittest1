"""
Subscription plan-change proration.

When a user upgrades or downgrades mid-cycle, they are credited for the
unused portion of their current plan and charged for the remainder of the
new plan at the new daily rate.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from subscriptions import Subscription, SubscriptionPlan


@dataclass(frozen=True)
class ProrationCalculation:
    """Immutable result of a proration calculation."""
    old_plan_credit: float       # Amount refunded for unused days on the old plan
    new_plan_charge: float       # Amount charged for remaining days on the new plan
    net_amount: float            # new_plan_charge - old_plan_credit (positive = owed)
    effective_date: datetime     # When the plan change takes effect
    days_remaining: float        # Days left in the current billing period
    old_daily_rate: float        # Old plan price / cycle_days
    new_daily_rate: float        # New plan price / cycle_days


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None or dt.utcoffset() is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def calculate_proration(
    subscription: "Subscription",
    new_plan: "SubscriptionPlan",
    change_date: datetime,
) -> ProrationCalculation:
    """Compute proration when switching from subscription's current plan to new_plan.

    Args:
        subscription: The active subscription being changed.
        new_plan:     The plan the user is switching to.
        change_date:  The date the change takes effect (usually now).

    Returns:
        ProrationCalculation with credit, charge, and net amounts.

    Raises:
        ValueError: If the subscription is canceled, or change_date is outside
                    the current billing period.
    """
    if subscription.status == "canceled":
        raise ValueError(
            f"Cannot prorate a canceled subscription {subscription.subscription_id}"
        )

    period_end = _as_utc(subscription.current_period_end)
    period_start = _as_utc(subscription.current_period_start)
    effective = _as_utc(change_date)

    if effective < period_start or effective > period_end:
        raise ValueError(
            f"change_date {effective.isoformat()} is outside the current billing period "
            f"[{period_start.isoformat()}, {period_end.isoformat()}]"
        )

    actual_period_days = (period_end - period_start).total_seconds() / 86400
    days_remaining = max((period_end - effective).total_seconds() / 86400, 0.0)

    old_daily_rate = subscription.plan.price_per_cycle / actual_period_days
    new_daily_rate = new_plan.price_per_cycle / new_plan.cycle_days

    old_plan_credit = round(old_daily_rate * days_remaining, 2)
    new_plan_charge = round(new_daily_rate * days_remaining, 2)
    net_amount = round(new_plan_charge - old_plan_credit, 2)

    return ProrationCalculation(
        old_plan_credit=old_plan_credit,
        new_plan_charge=new_plan_charge,
        net_amount=net_amount,
        effective_date=effective,
        days_remaining=days_remaining,
        old_daily_rate=round(old_daily_rate, 6),
        new_daily_rate=round(new_daily_rate, 6),
    )


def apply_plan_change(
    subscription: "Subscription",
    new_plan: "SubscriptionPlan",
    change_date: datetime,
) -> "Subscription":
    """Return a new Subscription reflecting the plan change.

    The new subscription keeps the same period boundaries but switches to
    new_plan immediately. The proration adjustment is recorded in metadata.
    The original subscription object is never modified.
    """
    from dataclasses import replace

    proration = calculate_proration(subscription, new_plan, change_date)
    effective = _as_utc(change_date)

    updated_metadata = {
        **subscription.metadata,
        "proration_adjustment": proration.net_amount,
        "plan_changed_at": effective.isoformat(),
        "previous_plan_id": subscription.plan.plan_id,
    }

    return replace(
        subscription,
        plan=new_plan,
        metadata=updated_metadata,
    )


_DAYS_PER_YEAR = 365


def estimate_annual_savings(
    current_plan: "SubscriptionPlan",
    new_plan: "SubscriptionPlan",
) -> dict:
    """Compare the annual cost of two plans.

    Each plan is normalized to a 365-day year via its own cycle_days so plans
    with different cycle lengths (e.g. monthly vs. annual) are compared fairly.

    Args:
        current_plan:   The plan the user is currently on.
        new_plan:       The plan being considered.

    Returns:
        Dict with annual_cost_current, annual_cost_new, savings (positive = cheaper),
        and savings_percent.
    """
    annual_current = round(current_plan.price_per_cycle / current_plan.cycle_days * _DAYS_PER_YEAR, 2)
    annual_new = round(new_plan.price_per_cycle / new_plan.cycle_days * _DAYS_PER_YEAR, 2)
    savings = round(annual_current - annual_new, 2)
    savings_percent = round((savings / annual_current * 100), 2) if annual_current > 0 else 0.0

    old_daily_rate = current_plan.price_per_cycle / current_plan.cycle_days
    new_daily_rate = new_plan.price_per_cycle / new_plan.cycle_days

    return {
        "annual_cost_current": annual_current,
        "annual_cost_new": annual_new,
        "savings": savings,
        "savings_percent": savings_percent,
        "is_upgrade": new_daily_rate > old_daily_rate,
    }
