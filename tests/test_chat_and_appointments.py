from __future__ import annotations

from datetime import date
from unittest.mock import patch

from demo.core.bot_logic import ConversationState, handle_message
from demo.core.repositories import list_active_appointments_on_date

from tests.test_helpers import DemoTestCase


class ChatAndAppointmentTests(DemoTestCase):
    @patch("demo.core.datetime_parser.today_for_timezone", return_value=date(2026, 4, 18))
    def test_chat_short_clarification_resolves_service(self, _mock_today) -> None:
        state = ConversationState()

        first_reply = handle_message("Quiero un corte", self.business, state, self.db_path)
        self.assertEqual(first_reply["intent"], "services")
        self.assertIn("caballero", first_reply["reply"].lower())

        second_reply = handle_message("hombre", self.business, state, self.db_path)
        self.assertEqual(second_reply["intent"], "services")
        self.assertIn("Corte caballero", second_reply["reply"])

    @patch("demo.core.datetime_parser.today_for_timezone", return_value=date(2026, 4, 18))
    def test_chat_creates_appointment_with_data_given_across_turns(self, _mock_today) -> None:
        state = ConversationState()

        reply_1 = handle_message(
            "Quiero cita el lunes a las 17 para corte caballero",
            self.business,
            state,
            self.db_path,
        )
        self.assertEqual(reply_1["intent"], "appointment_capture")
        self.assertEqual(reply_1["missing_field"], "phone")

        reply_2 = handle_message("600 123 123", self.business, state, self.db_path)
        self.assertEqual(reply_2["intent"], "appointment_capture")
        self.assertEqual(reply_2["missing_field"], "name")

        reply_3 = handle_message("Ana López", self.business, state, self.db_path)
        self.assertTrue(reply_3["appointment_created"])
        self.assertEqual(reply_3["intent"], "appointment_created")

        appointments = list_active_appointments_on_date(self.db_path, date="2026-04-20")
        self.assertEqual(len(appointments), 1)
        self.assertEqual(appointments[0]["hora"], "17:00")
        self.assertEqual(appointments[0]["servicio"], "Corte caballero")

    @patch("demo.core.datetime_parser.today_for_timezone", return_value=date(2026, 4, 18))
    def test_pending_offer_accepts_affirmative_with_extra_data(self, _mock_today) -> None:
        state = ConversationState()

        reply_1 = handle_message("precio del tinte", self.business, state, self.db_path)
        self.assertEqual(reply_1["intent"], "prices")

        reply_2 = handle_message("sí, soy Ana", self.business, state, self.db_path)
        self.assertEqual(reply_2["intent"], "appointment_capture")
        self.assertEqual(reply_2["missing_field"], "slot")
        self.assertIn("Solo me falta", reply_2["reply"])

    @patch("demo.core.datetime_parser.today_for_timezone", return_value=date(2026, 4, 18))
    def test_pending_offer_uses_service_signal_without_repeating_offer_flow(self, _mock_today) -> None:
        state = ConversationState()

        reply_1 = handle_message("¿Dónde estáis?", self.business, state, self.db_path)
        self.assertEqual(reply_1["intent"], "location")

        reply_2 = handle_message("mechas mañana por la tarde", self.business, state, self.db_path)
        self.assertEqual(reply_2["intent"], "appointment_capture")
        self.assertEqual(reply_2["missing_field"], "time")
        self.assertIn("dime una hora", reply_2["reply"].lower())
