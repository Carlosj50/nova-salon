from __future__ import annotations

from copy import deepcopy

from demo.core.appointment_service import (
    AppointmentServiceError,
    create_customer_appointment,
    update_customer_appointment,
)
from demo.core.repositories import create_appointment, get_appointment, get_or_create_customer

from tests.test_helpers import DemoTestCase


class AppointmentServiceTests(DemoTestCase):
    def test_service_creates_customer_and_appointment_in_one_flow(self) -> None:
        result = create_customer_appointment(
            self.db_path,
            business=self.business,
            customer_name="Ana López",
            customer_phone="600 123 123",
            date="2026-04-20",
            time="17:00",
            service_id="corte_caballero",
            service="Corte caballero",
            status="pendiente",
        )

        self.assertEqual(result["customer"]["telefono"], "600123123")
        self.assertEqual(result["appointment"]["servicio_id"], "corte_caballero")
        self.assertTrue(result["customer_created"])

    def test_service_blocks_overlapping_create(self) -> None:
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

        with self.assertRaises(AppointmentServiceError):
            create_customer_appointment(
                self.db_path,
                business=business,
                customer_name="Ana López",
                customer_phone="600999888",
                date="2026-04-20",
                time="10:00",
                service_id="coloracion",
                service="Coloración",
                status="confirmada",
            )

    def test_service_blocks_overlapping_edit(self) -> None:
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
        second = create_appointment(
            self.db_path,
            customer_id=int(customer["id"]),
            date="2026-04-20",
            time="11:00",
            service_id="coloracion",
            service="Coloración",
            status="confirmada",
            timezone="Atlantic/Canary",
        )

        with self.assertRaises(AppointmentServiceError):
            update_customer_appointment(
                self.db_path,
                business=business,
                appointment_id=int(second["id"]),
                date="2026-04-20",
                time="10:00",
                service_id="coloracion",
                service="Coloración",
                status="confirmada",
            )

        persisted = get_appointment(self.db_path, int(second["id"]))
        self.assertEqual(persisted["hora"], "11:00")
