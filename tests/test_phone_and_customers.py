from __future__ import annotations

from demo.core.repositories import get_or_create_customer, is_valid_phone, normalize_phone

from tests.test_helpers import DemoTestCase


class PhoneAndCustomerTests(DemoTestCase):
    def test_normalize_phone_variants(self) -> None:
        self.assertEqual(normalize_phone("+34 600 123 123"), "600123123")
        self.assertEqual(normalize_phone("0034-600-123-123"), "600123123")
        self.assertEqual(normalize_phone("600 123 123"), "600123123")
        self.assertTrue(is_valid_phone("+34 600 123 123"))
        self.assertFalse(is_valid_phone("12345"))

    def test_get_or_create_customer_reuses_existing_phone(self) -> None:
        first_customer, created_first = get_or_create_customer(
            self.db_path,
            name="Ana",
            phone="+34 600 123 123",
            timezone="Atlantic/Canary",
        )
        second_customer, created_second = get_or_create_customer(
            self.db_path,
            name="Ana María",
            phone="600123123",
            timezone="Atlantic/Canary",
        )

        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first_customer["id"], second_customer["id"])
