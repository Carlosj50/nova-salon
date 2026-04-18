from __future__ import annotations

from datetime import date
from unittest.mock import patch

from demo.core.datetime_parser import parse_datetime
from demo.core.service_catalog import analyze_service_request

from tests.test_helpers import DemoTestCase


class DateTimeAndServiceTests(DemoTestCase):
    @patch("demo.core.datetime_parser.today_for_timezone", return_value=date(2026, 4, 18))
    def test_parse_datetime_captures_date_time_and_part_of_day(self, _mock_today) -> None:
        parsed = parse_datetime("Quiero cita mañana a las 17", timezone="Atlantic/Canary")
        self.assertEqual(parsed.date_value, "2026-04-19")
        self.assertEqual(parsed.time_value, "17:00")

        parsed_part_of_day = parse_datetime("Quiero cita mañana por la tarde", timezone="Atlantic/Canary")
        self.assertEqual(parsed_part_of_day.date_value, "2026-04-19")
        self.assertEqual(parsed_part_of_day.part_of_day, "tarde")
        self.assertIsNone(parsed_part_of_day.time_value)

    def test_service_matching_uses_modifiers_and_asks_when_generic(self) -> None:
        result = analyze_service_request("Quiero un corte de pelo. Soy hombre", self.business)
        self.assertEqual(result.status, "matched")
        self.assertEqual(result.matched_service["name"], "Corte caballero")

        ambiguous = analyze_service_request("Quiero un corte", self.business)
        self.assertTrue(ambiguous.needs_clarification)
        names = {service["name"] for service in ambiguous.matches}
        self.assertIn("Corte caballero", names)
        self.assertIn("Corte mujer", names)
        self.assertIn("Corte infantil", names)
