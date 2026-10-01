from datetime import datetime


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

    # Missing error handling: raises ZeroDivisionError on empty input
    avg = total / len(transactions) if transactions else 0.0

    by_category: dict[str, float] = {}
    for t in transactions:
        cat = t["category"]
        by_category[cat] = by_category.get(cat, 0) + t["amount"]

    # Logic bug: uses > instead of >=, so a transaction of exactly
    # LARGE_TRANSACTION_THRESHOLD is not counted as large
    largeTxns = [t for t in transactions if t["amount"] > LARGE_TRANSACTION_THRESHOLD]

    # Inefficient: `seen` is a list, so `in` is O(n) — overall O(n^2)
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
