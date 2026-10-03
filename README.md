# coderabbittest1

A billing and subscription management library with Python and TypeScript modules.

## Modules

| File | Language | Purpose |
|------|----------|---------|
| `subscriptions.py` | Python | Subscription renewal, invoice generation, churn risk scoring, payment retry |
| `transactions.py` | Python | Transaction parsing, validation, and summarization |
| `src/billing.ts` | TypeScript | Billing cycle summaries, late fee calculation, anomaly detection |
| `src/payments.ts` | TypeScript | Pro-rated refunds and discount application |
| `src/inventory.py` | Python | Inventory restock and discount helpers |

## Setup

```bash
# Python (requires 3.11+)
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt   # if present

# TypeScript
npm install
```

## Running tests

```bash
# Python tests
python -m pytest tests/

# TypeScript tests
node --test tests/billing.test.js
node --test tests/payments.test.ts
```

## Key concepts

- **BillingCycle** — represents one paid period for a subscription plan
- **SubscriptionPlan** — defines price, cycle length, and features
- **Subscription** — a user's active plan with period tracking and payment state
- **Invoice** — generated per renewal with line items, tax, and status
