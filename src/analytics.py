from datetime import datetime, timezone
from collections import defaultdict


def monthly_revenue_trend(cycles: list[dict]) -> list[dict]:
    """Aggregate paid billing cycles by calendar month.

    Returns a list of {"month": "YYYY-MM", "revenue": float, "count": int}
    sorted chronologically. Only cycles with status == "paid" contribute to
    revenue; all cycles count toward the total.
    """
    monthly: dict[str, dict] = {}

    for cycle in cycles:
        raw_date = cycle.get("startDate") or cycle.get("start_date")
        if not raw_date:
            continue
        try:
            month = raw_date[:7]  # "YYYY-MM" from ISO date string
        except (TypeError, IndexError):
            continue

        if month not in monthly:
            monthly[month] = {"month": month, "revenue": 0.0, "count": 0}

        monthly[month]["count"] += 1
        if cycle.get("status") == "paid":
            monthly[month]["revenue"] += float(cycle.get("amount", 0))

    result = sorted(monthly.values(), key=lambda r: r["month"])
    for row in result:
        row["revenue"] = round(row["revenue"], 2)
    return result


def cohort_retention(subscriptions: list[dict]) -> dict[str, dict]:
    """Group subscriptions by start month and calculate retention by status.

    Returns a dict keyed by cohort month ("YYYY-MM"), where each value is:
        {
            "total": int,
            "active": int,
            "canceled": int,
            "past_due": int,
            "retention_rate": float,  # active / total, 0.0 if total == 0
        }
    """
    cohorts: dict[str, dict] = defaultdict(lambda: {
        "total": 0,
        "active": 0,
        "canceled": 0,
        "past_due": 0,
    })

    for sub in subscriptions:
        raw_start = sub.get("start_date") or sub.get("startDate")
        if not raw_start:
            continue
        try:
            if isinstance(raw_start, datetime):
                month = raw_start.strftime("%Y-%m")
            else:
                month = str(raw_start)[:7]
        except (TypeError, AttributeError):
            continue

        status = sub.get("status", "unknown")
        cohorts[month]["total"] += 1
        if status in ("active", "canceled", "past_due"):
            cohorts[month][status] += 1

    result = {}
    for month in sorted(cohorts):
        data = dict(cohorts[month])
        total = data["total"]
        data["retention_rate"] = round(data["active"] / total, 4) if total > 0 else 0.0
        result[month] = data

    return result


def revenue_per_plan(cycles: list[dict]) -> list[dict]:
    """Summarize paid revenue and cycle count grouped by planId.

    Returns a list of {"plan_id": str, "revenue": float, "count": int}
    sorted by revenue descending.
    """
    plans: dict[str, dict] = {}

    for cycle in cycles:
        if cycle.get("status") != "paid":
            continue
        plan_id = cycle.get("planId") or cycle.get("plan_id", "unknown")
        if plan_id not in plans:
            plans[plan_id] = {"plan_id": plan_id, "revenue": 0.0, "count": 0}
        plans[plan_id]["revenue"] += float(cycle.get("amount", 0))
        plans[plan_id]["count"] += 1

    result = sorted(plans.values(), key=lambda r: r["revenue"], reverse=True)
    for row in result:
        row["revenue"] = round(row["revenue"], 2)
    return result
