from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import Optional
from math import isfinite
from uuid import uuid4


MAX_RETRY_ATTEMPTS = 3
LATE_FEE_RATE = 0.015  # 1.5% per day overdue


@dataclass
class SubscriptionPlan:
    plan_id: str
    name: str
    price_per_cycle: float
    cycle_days: int
    features: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not isfinite(self.cycle_days) or self.cycle_days <= 0:
            raise ValueError("cycle_days must be finite and greater than zero")
        if not isfinite(self.price_per_cycle) or self.price_per_cycle < 0:
            raise ValueError("price_per_cycle must be finite and nonnegative")


@dataclass
class Subscription:
    subscription_id: str
    user_id: str
    plan: SubscriptionPlan
    start_date: datetime
    current_period_start: datetime
    current_period_end: datetime
    status: str  # "active", "past_due", "canceled"
    payment_method_id: str
    failed_attempts: int = 0
    metadata: dict = field(default_factory=dict)


def _as_utc(value: datetime) -> datetime:
    """Normalize dates to UTC, treating legacy naive dates as UTC."""
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def process_renewal(subscription: Subscription) -> dict:
    """Process a subscription renewal at the end of its billing cycle."""
    now = datetime.now(timezone.utc)

    if subscription.status == "canceled":
        raise ValueError(
            f"Cannot renew canceled subscription {subscription.subscription_id}"
        )

    days_overdue = (now - _as_utc(subscription.current_period_end)).days

    is_overdue = days_overdue > 0

    late_fee = 0.0
    if is_overdue and days_overdue > 0:
        late_fee = round(
            subscription.plan.price_per_cycle * LATE_FEE_RATE * days_overdue, 2
        )

    amount_due = round(subscription.plan.price_per_cycle + late_fee, 2)

    next_period_start = subscription.current_period_end
    next_period_end = next_period_start + timedelta(days=subscription.plan.cycle_days)

    return {
        "subscription_id": subscription.subscription_id,
        "user_id": subscription.user_id,
        "amount_due": amount_due,
        "late_fee": late_fee,
        "is_overdue": is_overdue,
        "days_overdue": days_overdue,
        "next_period_start": next_period_start,
        "next_period_end": next_period_end,
        "plan_id": subscription.plan.plan_id,
    }


def retry_failed_payment(subscription: Subscription, attempt: int) -> dict:
    """
    Determine retry timing using exponential backoff.
    Returns a dict describing when to retry and whether to cancel.
    """
    if attempt > MAX_RETRY_ATTEMPTS:
        return {
            "subscription_id": subscription.subscription_id,
            "should_cancel": True,
            "retry_at": None,
            "attempt": attempt,
        }

    backoff_hours = 2 ** (attempt - 1)
    retry_at = datetime.utcnow() + timedelta(hours=backoff_hours)

    return {
        "subscription_id": subscription.subscription_id,
        "should_cancel": False,
        "retry_at": retry_at,
        "attempt": attempt,
        "backoff_hours": backoff_hours,
    }


def generate_invoice(
    subscription: Subscription,
    line_items: Optional[list[dict]] = None,
) -> dict:
    """Generate an invoice dict for the subscription's current billing period."""
    issued_at = datetime.now(timezone.utc).isoformat()

    items: list[dict] = [
        {
            "description": (
                f"{subscription.plan.name} — "
                f"{subscription.plan.cycle_days}-day subscription"
            ),
            "quantity": 1,
            "unit_price": subscription.plan.price_per_cycle,
            "total": subscription.plan.price_per_cycle,
        }
    ]

    if line_items:
        items.extend(line_items)

    subtotal = sum(item["total"] for item in items)
    tax_rate = 0.08
    tax = round(subtotal * tax_rate, 2)
    total = round(subtotal + tax, 2)

    return {
        "invoice_id": (
            f"inv_{subscription.subscription_id}"
            f"_{uuid4().hex}"
        ),
        "subscription_id": subscription.subscription_id,
        "user_id": subscription.user_id,
        "period_start": subscription.current_period_start.isoformat(),
        "period_end": subscription.current_period_end.isoformat(),
        "line_items": items,
        "subtotal": round(subtotal, 2),
        "tax": tax,
        "total": total,
        "issued_at": issued_at,
        "last_invoice_date": issued_at,
        "status": "draft",
    }


def compute_churn_risk(
    subscription: Subscription,
    payment_history: list[dict],
) -> float:
    """
    Return a churn risk score in [0.0, 1.0].

    Higher scores mean higher likelihood of churn based on payment failure rate
    and subscription age.
    """
    if not payment_history:
        return 0.5

    failed = sum(1 for p in payment_history if p.get("status") == "failed")
    total = len(payment_history)
    failure_rate = failed / total

    age_days = (datetime.now(timezone.utc) - _as_utc(subscription.start_date)).days
    age_factor = max(0.0, 1.0 - (age_days / 365))

    score = ((failure_rate * 0.6) + (age_factor * 0.3)) / (0.6 + 0.3)

    return round(min(max(score, 0.0), 1.0), 4)
