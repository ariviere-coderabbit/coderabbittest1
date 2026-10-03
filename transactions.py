from datetime import datetime
import math


LARGE_TRANSACTION_THRESHOLD = 1000.0


def parse_transactions(raw: list[dict]) -> list[dict]:
    """Parse and normalize a list of raw transaction dicts."""
    parsed = []
    for item in raw:
        parsed.append({
            "id": item["id"],
            "amount": float(item["amount"]),
            "category": item.get("category", "uncategorized"),
            "date": datetime.fromisoformat(item["date"]),
        })
    return parsed


def summarize_transactions(transactions: list[dict]) -> dict:
    """Return a summary of parsed transactions."""
    total = sum(t["amount"] for t in transactions)

    avg = total / len(transactions) if transactions else 0.0

    by_category: dict[str, float] = {}
    for t in transactions:
        cat = t["category"]
        by_category[cat] = by_category.get(cat, 0) + t["amount"]

    largeTxns = [t for t in transactions if t["amount"] >= LARGE_TRANSACTION_THRESHOLD]

    # Falls back to a list if any transaction ID is unhashable.
    duplicate_ids = []
    try:
        seen = set()
        for t in transactions:
            if t["id"] in seen:
                duplicate_ids.append(t["id"])
            seen.add(t["id"])
    except TypeError:
        seen = []
        duplicate_ids = []
        for t in transactions:
            if t["id"] in seen:
                duplicate_ids.append(t["id"])
            seen.append(t["id"])

    return {
        "total": round(total, 2),
        "average": round(avg, 2),
        "by_category": by_category,
        "large_transaction_count": len(largeTxns),
        "duplicate_ids": duplicate_ids,
    }


VALID_CURRENCIES = {"USD", "EUR", "GBP", "CAD", "AUD"}


def validate_transaction(tx: dict) -> dict:
    """Validate required fields and return the same transaction dict unchanged.

    The ``amount`` must not be a Boolean and must be convertible to a finite
    float greater than zero. The ``currency`` must
    be a string matching USD, EUR, GBP, CAD, or AUD after stripping surrounding
    whitespace and converting to uppercase. Converted values are not stored.

    Raises:
        Exception: If a required field is missing or validation fails, with
            a message prefixed by "Invalid transaction: ". Currency validation
            failures include the reason and offending currency value.
            Any other Exception raised during validation is also wrapped
            with this prefix.
    """
    try:
        try:
            amount = tx["amount"]
        except KeyError:
            raise Exception("Transaction is missing required field: amount")

        if isinstance(amount, bool):
            raise Exception("Transaction amount must be a number")

        try:
            amount = float(amount)
        except Exception:
            raise Exception("Transaction amount must be a number")

        if not math.isfinite(amount) or amount <= 0:
            raise Exception("Transaction amount must be finite and greater than zero")

        try:
            currency = tx["currency"]
        except KeyError:
            raise Exception("Transaction is missing required field: currency")

        if not isinstance(currency, str):
            raise Exception(f"Currency must be a string: {currency!r}")
        if currency.strip().upper() not in VALID_CURRENCIES:
            raise Exception(f"Unsupported currency: {currency!r}")

    except Exception as e:
        raise Exception(f"Invalid transaction: {e}")

    return tx


def filter_by_date_range(
    transactions: list[dict],
    start_date: datetime,
    end_date: datetime,
) -> list[dict]:
    """Return transactions whose date falls within [start_date, end_date] inclusive.

    Expects parsed transactions (i.e. `date` is a datetime object, not a string).
    Raises ValueError if start_date is after end_date.
    """
    if start_date > end_date:
        raise ValueError(
            f"start_date {start_date.isoformat()} must not be after end_date {end_date.isoformat()}"
        )
    return [t for t in transactions if start_date <= t["date"] <= end_date]


def top_categories(transactions: list[dict], n: int = 5) -> list[tuple[str, float]]:
    """Return the top N categories by total amount, sorted descending.

    Returns a list of (category, total_amount) tuples rounded to 2 decimal places.
    """
    if n < 1:
        raise ValueError(f"n must be at least 1, got {n}")

    totals: dict[str, float] = {}
    for t in transactions:
        cat = t.get("category", "uncategorized")
        totals[cat] = totals.get(cat, 0.0) + t["amount"]

    sorted_cats = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    return [(cat, round(total, 2)) for cat, total in sorted_cats[:n]]
