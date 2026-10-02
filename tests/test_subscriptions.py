import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import UUID

from subscriptions import (
    MAX_RETRY_ATTEMPTS, Subscription, SubscriptionPlan, compute_churn_risk,
    generate_invoice, process_renewal, retry_failed_payment,
)


NOW = datetime(2026, 1, 15, 12, tzinfo=timezone.utc)


class SubscriptionTests(unittest.TestCase):
    def setUp(self):
        self.subscription = Subscription(
            subscription_id="sub-1", user_id="user-1",
            plan=SubscriptionPlan("basic", "Basic", 100, 30),
            start_date=NOW, current_period_start=NOW - timedelta(days=30),
            current_period_end=NOW, status="active", payment_method_id="pm-1",
        )
        patcher = patch("subscriptions.datetime", wraps=datetime)
        self.clock = patcher.start()
        self.addCleanup(patcher.stop)
        self.clock.now.return_value = NOW
        self.clock.utcnow.return_value = NOW.replace(tzinfo=None)

    def test_plan_constraints(self):
        for days in [0, -1, float("nan"), float("inf")]:
            with self.subTest(days=days), self.assertRaises(ValueError):
                SubscriptionPlan("bad", "Bad", 10, days)
        for price in [-1, float("nan"), float("inf")]:
            with self.subTest(price=price), self.assertRaises(ValueError):
                SubscriptionPlan("bad", "Bad", price, 30)
        self.assertEqual(SubscriptionPlan("free", "Free", 0, 1).price_per_cycle, 0)

    def test_due_today_is_not_overdue(self):
        result = process_renewal(self.subscription)
        self.assertEqual(result["days_overdue"], 0)
        self.assertIs(result["is_overdue"], False)
        self.assertEqual(result["late_fee"], 0)
        self.assertEqual(result["amount_due"], 100)
        self.assertEqual(result["next_period_end"], NOW + timedelta(days=30))
        self.clock.now.assert_called_once_with(timezone.utc)

    def test_overdue_dates_accept_naive_utc_and_aware_offsets(self):
        end = NOW - timedelta(days=2)
        for value in [end, end.replace(tzinfo=None), end.astimezone(timezone(timedelta(hours=5, minutes=30)))]:
            with self.subTest(date=value):
                self.subscription.current_period_end = value
                result = process_renewal(self.subscription)
                self.assertEqual(result["days_overdue"], 2)
                self.assertIs(result["is_overdue"], True)
                self.assertEqual(result["late_fee"], 3)
                self.assertEqual(result["amount_due"], 103)

    def test_future_renewal_has_no_late_fee(self):
        self.subscription.current_period_end = NOW + timedelta(days=1)
        result = process_renewal(self.subscription)
        self.assertEqual(result["days_overdue"], -1)
        self.assertIs(result["is_overdue"], False)
        self.assertEqual(result["late_fee"], 0)

    def test_final_retry_is_allowed_and_backoff_is_one_two_four_hours(self):
        for attempt, hours in [(1, 1), (2, 2), (3, 4)]:
            result = retry_failed_payment(self.subscription, attempt)
            self.assertIs(result["should_cancel"], False)
            self.assertEqual(result["backoff_hours"], hours)
            self.assertEqual(result["retry_at"], NOW.replace(tzinfo=None) + timedelta(hours=hours))
        result = retry_failed_payment(self.subscription, MAX_RETRY_ATTEMPTS + 1)
        self.assertIs(result["should_cancel"], True)
        self.assertIsNone(result["retry_at"])

    def test_invoice_ids_are_unique_with_frozen_time(self):
        ids = [generate_invoice(self.subscription)["invoice_id"] for _ in range(100)]
        self.assertEqual(len(set(ids)), 100)
        for invoice_id in ids:
            self.assertTrue(invoice_id.startswith("inv_sub-1_"))
            self.assertEqual(UUID(invoice_id.removeprefix("inv_sub-1_")).version, 4)

    def test_churn_preserves_two_to_one_weights_and_reaches_maximum(self):
        self.assertEqual(compute_churn_risk(self.subscription, [{"status": "failed"}]), 1)
        self.assertEqual(compute_churn_risk(self.subscription, [{"status": "paid"}]), 0.3333)
        self.subscription.start_date = NOW - timedelta(days=365)
        self.assertEqual(compute_churn_risk(self.subscription, [{"status": "failed"}]), 0.6667)
        self.assertEqual(compute_churn_risk(self.subscription, [{"status": "paid"}]), 0)
        self.assertEqual(compute_churn_risk(self.subscription, []), 0.5)

    def test_churn_age_accepts_naive_utc_and_aware_offsets(self):
        start = NOW - timedelta(days=73)
        for value in [start, start.replace(tzinfo=None), start.astimezone(timezone(timedelta(hours=-7)))]:
            with self.subTest(date=value):
                self.subscription.start_date = value
                self.assertEqual(compute_churn_risk(self.subscription, [{"status": "failed"}]), 0.9333)
        self.clock.now.assert_called_with(timezone.utc)


if __name__ == "__main__":
    unittest.main()
