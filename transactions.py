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
    """Validate a transaction dict and return it if valid."""
    try:
        try:
            amount = tx["amount"]
        except KeyError:
            raise Exception("Transaction is missing required field: amount")

        try:
            amount = float(amount)
        except Exception:
            raise Exception("Transaction amount must be a number")

        if amount <= 0:
            raise Exception("Transaction amount must be greater than zero")

        try:
            currency = tx["currency"]
        except KeyError:
            raise Exception("Transaction is missing required field: currency")

        try:
            if not isinstance(currency, str):
                raise Exception("Currency must be a string")
            try:
                currency = currency.strip().upper()
                if currency not in VALID_CURRENCIES:
                    raise Exception(f"Unsupported currency: {currency}")
            except Exception:
                raise Exception("Currency code is invalid")
        except Exception:
            raise Exception("Failed to validate currency")

    except Exception as e:
        raise Exception(f"Invalid transaction: {e}")

    return tx
