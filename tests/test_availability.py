from __future__ import annotations

from copy import deepcopy

from demo.core.availability import check_basic_availability
from demo.core.repositories import create_appointment, get_or_create_customer

from tests.test_helpers import DemoTestCase


class AvailabilityTests(DemoTestCase):
    def test_overlapping_appointment_blocks_when_category_capacity_is_full(self) -> None:
        business = deepcopy(self.business)
        business["operational_rules"]["category_capacity"]["color"] = 1
        for member in business["staff"]:
            member["active"] = member["id"] == "ana"

        customer, _ = get_or_create_customer(
            self.db_path,
            name="Laura",
            phone="600123123",
            timezone="Atlantic/Canary",
        )
        create_appointment(
            self.db_path,
            customer_id=int(customer["id"]),
            date="2026-04-20",
            time="10:00",
            service_id="coloracion",
            service="Coloración",
            status="confirmada",
            timezone="Atlantic/Canary",
        )

        decision = check_basic_availability(
            self.db_path,
            business=business,
            date="2026-04-20",
            time="10:30",
            service_id="coloracion",
            service="Coloración",
            suggest_alternatives=False,
        )

        self.assertFalse(decision.available)
        self.assertIsNotNone(decision.reason)
