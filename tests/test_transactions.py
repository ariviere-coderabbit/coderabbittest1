import unittest
from decimal import Decimal

from transactions import VALID_CURRENCIES, validate_transaction


class TransactionValidationTests(unittest.TestCase):
    def test_boolean_amounts_are_rejected(self):
        for amount in (True, False):
            with self.subTest(amount=amount), self.assertRaises(Exception) as error:
                validate_transaction({"amount": amount, "currency": "USD"})
            self.assertEqual(
                str(error.exception),
                "Invalid transaction: Transaction amount must be a number",
            )

    def test_nonfinite_and_nonpositive_amounts_are_rejected(self):
        for amount in (
            float("nan"), float("inf"), float("-inf"),
            "NaN", "Infinity", "-Infinity", "1e309", 0, -1, "0", "-1",
        ):
            with self.subTest(amount=amount), self.assertRaises(Exception) as error:
                validate_transaction({"amount": amount, "currency": "USD"})
            self.assertEqual(
                str(error.exception),
                "Invalid transaction: Transaction amount must be finite and greater than zero",
            )

    def test_valid_amounts_and_currencies_preserve_transaction(self):
        for amount in (1, 1.25, " 2.50 ", Decimal("3.75"), 5e-324):
            for currency in VALID_CURRENCIES:
                with self.subTest(amount=amount, currency=currency):
                    tx = {"amount": amount, "currency": f" {currency.lower()} "}
                    original = tx.copy()
                    self.assertIs(validate_transaction(tx), tx)
                    self.assertEqual(tx, original)

    def test_invalid_numeric_inputs_keep_conversion_error(self):
        for amount in (None, "invalid", [], {}):
            with self.subTest(amount=amount), self.assertRaises(Exception) as error:
                validate_transaction({"amount": amount, "currency": "USD"})
            self.assertEqual(
                str(error.exception),
                "Invalid transaction: Transaction amount must be a number",
            )

    def test_nonstring_currencies_include_original_value(self):
        for currency in (None, True, 123, ["USD"], {"code": "USD"}):
            with self.subTest(currency=currency), self.assertRaises(Exception) as error:
                validate_transaction({"amount": 1, "currency": currency})
            self.assertEqual(
                str(error.exception),
                f"Invalid transaction: Currency must be a string: {currency!r}",
            )

    def test_unsupported_currencies_include_original_value(self):
        for currency in (" jpy ", "", "   ", "US D"):
            with self.subTest(currency=currency), self.assertRaises(Exception) as error:
                validate_transaction({"amount": 1, "currency": currency})
            self.assertEqual(
                str(error.exception),
                f"Invalid transaction: Unsupported currency: {currency!r}",
            )

    def test_missing_fields_keep_transaction_error(self):
        for tx, field in (({}, "amount"), ({"amount": 1}, "currency")):
            with self.subTest(field=field), self.assertRaises(Exception) as error:
                validate_transaction(tx)
            self.assertEqual(
                str(error.exception),
                f"Invalid transaction: Transaction is missing required field: {field}",
            )


if __name__ == "__main__":
    unittest.main()
