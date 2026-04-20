from __future__ import annotations

import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

import demo.app as demo_app
import demo.web.context as web_context
import demo.web.routes_config as config_routes
import demo.web.view_helpers as view_helpers
from demo.core.appointment_service import create_customer_appointment
from demo.core.config import load_auth_config
from demo.core.internal_users import create_internal_user
from demo.core.repositories import (
    find_customer_by_phone,
    get_appointment,
    list_staff_members,
    set_staff_active,
    update_category_capacities,
)

from tests.test_helpers import CONFIG_PATH, DemoTestCase


class WebAuthAndRoutesTests(DemoTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.auth = load_auth_config(CONFIG_PATH)
        self._branding_tmpdir = TemporaryDirectory()
        self.branding_dir = Path(self._branding_tmpdir.name) / "branding"
        self.branding_dir.mkdir(parents=True, exist_ok=True)
        self._patches = [
            patch.object(demo_app, "DB_PATH", self.db_path),
            patch.object(config_routes, "BRANDING_DIR", self.branding_dir),
            patch.object(web_context, "DB_PATH", self.db_path),
            patch.object(view_helpers, "DB_PATH", self.db_path),
        ]
        for patcher in self._patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(self._branding_tmpdir.cleanup)
        web_context.conversations.clear()
        self.client = TestClient(demo_app.app)

    def login_admin(self, next_path: str = "/agenda") -> None:
        login_page = self.client.get("/login", params={"next": next_path})
        csrf_token = self.extract_csrf_token(login_page.text)
        response = self.client.post(
            "/login",
            data={
                "csrf_token": csrf_token,
                "username": self.auth["admin_username"],
                "password": self.auth["admin_password"],
                "next": next_path,
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], next_path)

    def login_user(self, username: str, password: str, next_path: str = "/agenda") -> None:
        login_page = self.client.get("/login", params={"next": next_path})
        csrf_token = self.extract_csrf_token(login_page.text)
        response = self.client.post(
            "/login",
            data={
                "csrf_token": csrf_token,
                "username": username,
                "password": password,
                "next": next_path,
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], next_path)

    def extract_csrf_token(self, html: str) -> str:
        match = re.search(r'name="csrf_token" value="([^"]+)"', html)
        self.assertIsNotNone(match)
        return str(match.group(1))

    def get_csrf_token(self, path: str) -> str:
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        return self.extract_csrf_token(response.text)

    def test_internal_route_redirects_to_login_when_not_authenticated(self) -> None:
        response = self.client.get("/agenda", follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertIn("/login?next=%2Fagenda", response.headers["location"])

    def test_staff_user_can_access_operational_pages_but_not_admin_areas(self) -> None:
        created = create_customer_appointment(
            self.db_path,
            business=self.business,
            customer_name="Lucía",
            customer_phone="600111222",
            date="2099-04-20",
            time="10:00",
            service_id="corte_caballero",
            service="Corte caballero",
            status="confirmada",
        )
        appointment_id = int(created["appointment"]["id"])
        customer_id = int(created["customer"]["id"])
        create_internal_user(
            self.db_path,
            username="maria",
            password="clave-staff-123",
            role="staff",
        )
        self.login_user("maria", "clave-staff-123", "/agenda")

        agenda = self.client.get("/agenda")
        self.assertEqual(agenda.status_code, 200)
        self.assertIn("Agenda", agenda.text)

        customers = self.client.get("/clientes")
        self.assertEqual(customers.status_code, 200)
        self.assertIn("Clientes", customers.text)

        customer_detail = self.client.get(f"/clientes/{customer_id}")
        self.assertEqual(customer_detail.status_code, 200)
        self.assertIn("Lucía", customer_detail.text)

        new_appointment = self.client.get("/citas/nueva")
        self.assertEqual(new_appointment.status_code, 200)
        self.assertIn("Nueva cita", new_appointment.text)

        edit_appointment = self.client.get(f"/citas/{appointment_id}/editar")
        self.assertEqual(edit_appointment.status_code, 200)
        self.assertIn("Editar cita", edit_appointment.text)

        config = self.client.get("/config", follow_redirects=False)
        self.assertEqual(config.status_code, 303)
        self.assertIn("/agenda?forbidden=1", config.headers["location"])

        access = self.client.get("/config/acceso", follow_redirects=False)
        self.assertEqual(access.status_code, 303)
        self.assertIn("/agenda?forbidden=1", access.headers["location"])

        services = self.client.get("/servicios", follow_redirects=False)
        self.assertEqual(services.status_code, 303)
        self.assertIn("/agenda?forbidden=1", services.headers["location"])

    def test_admin_internal_user_can_access_admin_configuration(self) -> None:
        create_internal_user(
            self.db_path,
            username="encargada",
            password="clave-admin-123",
            role="admin",
        )
        self.login_user("encargada", "clave-admin-123", "/config")

        response = self.client.get("/config")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Centro de configuración", response.text)

    def test_login_and_logout_control_internal_panel(self) -> None:
        login_page = self.client.get("/login", params={"next": "/agenda"})
        csrf_token = self.extract_csrf_token(login_page.text)
        failed = self.client.post(
            "/login",
            data={"csrf_token": csrf_token, "username": "admin", "password": "mal", "next": "/agenda"},
            follow_redirects=False,
        )
        self.assertEqual(failed.status_code, 400)
        self.assertIn("Revisa usuario y contraseña", failed.text)

        self.login_admin("/agenda")

        agenda = self.client.get("/agenda")
        self.assertEqual(agenda.status_code, 200)
        self.assertIn("Agenda", agenda.text)

        logout = self.client.get("/logout", follow_redirects=False)
        self.assertEqual(logout.status_code, 303)
        self.assertIn("/login?logged_out=1", logout.headers["location"])

        locked_again = self.client.get("/clientes", follow_redirects=False)
        self.assertEqual(locked_again.status_code, 303)
        self.assertIn("/login?next=%2Fclientes", locked_again.headers["location"])

    def test_manual_appointment_create_route_creates_customer_and_appointment(self) -> None:
        self.login_admin("/citas/nueva")
        csrf_token = self.get_csrf_token("/citas/nueva")

        response = self.client.post(
            "/citas/nueva",
            data={
                "csrf_token": csrf_token,
                "customer_id": "",
                "fecha": "2099-04-20",
                "hora": "17:00",
                "servicio_id": "corte_caballero",
                "estado": "confirmada",
                "notas": "Cliente de mostrador",
                "nombre": "Ana López",
                "telefono": "600 123 123",
                "return_to": "/agenda",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/agenda?saved=1")

        customer = find_customer_by_phone(self.db_path, "600 123 123")
        self.assertIsNotNone(customer)
        appointment = get_appointment(self.db_path, 1)
        self.assertIsNotNone(appointment)
        self.assertEqual(appointment["cliente_id"], customer["id"])
        self.assertEqual(appointment["servicio_id"], "corte_caballero")
        self.assertEqual(appointment["hora"], "17:00")

    def test_manual_appointment_create_route_rejects_overlap(self) -> None:
        update_category_capacities(self.db_path, {"color": 1})
        for member in list_staff_members(self.db_path):
            set_staff_active(self.db_path, member["id"], member["id"] == "ana")
        self.reload_business()

        create_customer_appointment(
            self.db_path,
            business=self.business,
            customer_name="Lucía",
            customer_phone="600999888",
            date="2099-04-20",
            time="10:00",
            service_id="coloracion",
            service="Coloración",
            status="confirmada",
        )
        self.login_admin("/citas/nueva")
        csrf_token = self.get_csrf_token("/citas/nueva")

        response = self.client.post(
            "/citas/nueva",
            data={
                "csrf_token": csrf_token,
                "customer_id": "",
                "fecha": "2099-04-20",
                "hora": "10:00",
                "servicio_id": "coloracion",
                "estado": "confirmada",
                "notas": "",
                "nombre": "Ana López",
                "telefono": "600 123 123",
                "return_to": "/agenda",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("No puedo confirmar esa hora", response.text)

    def test_edit_appointment_route_updates_existing_appointment(self) -> None:
        created = create_customer_appointment(
            self.db_path,
            business=self.business,
            customer_name="Ana López",
            customer_phone="600123123",
            date="2099-04-20",
            time="17:00",
            service_id="corte_caballero",
            service="Corte caballero",
            status="confirmada",
        )
        appointment_id = int(created["appointment"]["id"])
        customer_id = int(created["customer"]["id"])

        self.login_admin(f"/citas/{appointment_id}/editar")
        csrf_token = self.get_csrf_token(f"/citas/{appointment_id}/editar")

        response = self.client.post(
            f"/citas/{appointment_id}/editar",
            data={
                "csrf_token": csrf_token,
                "customer_id": str(customer_id),
                "fecha": "2099-04-20",
                "hora": "16:00",
                "servicio_id": "mechas",
                "estado": "pendiente",
                "notas": "Cambio de servicio",
                "return_to": "/agenda",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/agenda?saved=1")

        appointment = get_appointment(self.db_path, appointment_id)
        self.assertEqual(appointment["hora"], "16:00")
        self.assertEqual(appointment["servicio_id"], "mechas")
        self.assertEqual(appointment["estado"], "pendiente")
        self.assertEqual(appointment["notas"], "Cambio de servicio")

    def test_repeat_flow_prefills_reasonable_date_for_repeat_customer(self) -> None:
        created = create_customer_appointment(
            self.db_path,
            business=self.business,
            customer_name="Ana López",
            customer_phone="600123123",
            date="2099-04-20",
            time="17:00",
            service_id="manicura",
            service="Manicura",
            status="confirmada",
        )
        customer_id = int(created["customer"]["id"])

        self.login_admin(f"/clientes/{customer_id}")

        response = self.client.get(
            f"/citas/nueva?customer_id={customer_id}&servicio_id=manicura&hora=17:00&repeat_from=2099-04-20&return_to=/clientes/{customer_id}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Siguiente cita sugerida", response.text)
        self.assertIn("Ya he dejado cargados", response.text)
        self.assertIn("17:00", response.text)
        self.assertIn("+20 días", response.text)
        self.assertIn("2099-05-10", response.text)

    def test_new_appointment_page_shows_lightweight_customer_lookup(self) -> None:
        create_customer_appointment(
            self.db_path,
            business=self.business,
            customer_name="Ana López",
            customer_phone="600123123",
            date="2099-04-20",
            time="17:00",
            service_id="corte_caballero",
            service="Corte caballero",
            status="confirmada",
        )
        self.login_admin("/citas/nueva")

        response = self.client.get("/citas/nueva")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Localizar clienta", response.text)
        self.assertIn("customer-lookup", response.text)
        self.assertIn("Ana López", response.text)

    def test_quick_reschedule_route_moves_appointment(self) -> None:
        created = create_customer_appointment(
            self.db_path,
            business=self.business,
            customer_name="Ana López",
            customer_phone="600123123",
            date="2099-04-20",
            time="17:00",
            service_id="corte_caballero",
            service="Corte caballero",
            status="confirmada",
        )
        appointment_id = int(created["appointment"]["id"])

        self.login_admin("/agenda")

        response = self.client.post(
            f"/citas/{appointment_id}/reprogramar?move=1d&return_to=/agenda",
            data={"csrf_token": self.get_csrf_token("/agenda")},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/agenda?moved=1")

        appointment = get_appointment(self.db_path, appointment_id)
        self.assertEqual(appointment["fecha"], "2099-04-21")
        self.assertEqual(appointment["hora"], "17:00")

    def test_quick_reschedule_route_keeps_availability_rules(self) -> None:
        update_category_capacities(self.db_path, {"corte_peinado": 1})
        for member in list_staff_members(self.db_path):
            set_staff_active(self.db_path, member["id"], member["id"] == "ana")
        self.reload_business()

        create_customer_appointment(
            self.db_path,
            business=self.business,
            customer_name="Lucía",
            customer_phone="600999888",
            date="2099-04-20",
            time="11:00",
            service_id="corte_caballero",
            service="Corte caballero",
            status="confirmada",
        )
        second = create_customer_appointment(
            self.db_path,
            business=self.business,
            customer_name="Ana López",
            customer_phone="600123123",
            date="2099-04-20",
            time="10:30",
            service_id="corte_caballero",
            service="Corte caballero",
            status="confirmada",
        )

        self.login_admin("/agenda")

        response = self.client.post(
            f"/citas/{int(second['appointment']['id'])}/reprogramar?move=30m&return_to=/agenda",
            data={"csrf_token": self.get_csrf_token("/agenda")},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)
        self.assertIn("/agenda?error_move=", response.headers["location"])

        appointment = get_appointment(self.db_path, int(second["appointment"]["id"]))
        self.assertEqual(appointment["hora"], "10:30")

    def test_business_config_allows_uploading_logo(self) -> None:
        self.login_admin("/config/negocio")
        csrf_token = self.get_csrf_token("/config/negocio")

        response = self.client.post(
            "/config/negocio",
            data={
                "csrf_token": csrf_token,
                "name": "Salón Nova",
                "sector": "peluquería y estética",
                "phone": "600123123",
                "address": "Calle Principal 24",
                "hours_summary": "lunes a viernes de 9:30 a 19:30 y sábados de 10:00 a 14:00",
                "hours_monday_friday": "09:30-19:30",
                "hours_saturday": "10:00-14:00",
                "hours_sunday": "cerrado",
                "welcome_message": "Hola, te ayudo con tu próxima cita.",
                "fallback_message": "Puedo ayudarte con horarios, servicios y citas.",
            },
            files={"logo_file": ("logo.png", b"\x89PNG\r\n\x1a\nlogo-demo", "image/png")},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/config/negocio?saved=1")

        business = self.reload_business()
        self.assertTrue(str(business.get("logo_path") or "").startswith("/media/branding/logo-"))
        stored_logo = self.branding_dir / Path(business["logo_path"]).name
        self.assertTrue(stored_logo.exists())

    def test_business_config_allows_removing_logo(self) -> None:
        self.login_admin("/config/negocio")
        csrf_token = self.get_csrf_token("/config/negocio")
        first = self.client.post(
            "/config/negocio",
            data={
                "csrf_token": csrf_token,
                "name": "Salón Nova",
                "sector": "peluquería y estética",
                "phone": "600123123",
                "address": "Calle Principal 24",
                "hours_summary": "lunes a viernes de 9:30 a 19:30 y sábados de 10:00 a 14:00",
                "hours_monday_friday": "09:30-19:30",
                "hours_saturday": "10:00-14:00",
                "hours_sunday": "cerrado",
                "welcome_message": "Hola, te ayudo con tu próxima cita.",
                "fallback_message": "Puedo ayudarte con horarios, servicios y citas.",
            },
            files={"logo_file": ("logo.png", b"\x89PNG\r\n\x1a\nlogo-demo", "image/png")},
            follow_redirects=False,
        )
        self.assertEqual(first.status_code, 303)

        business = self.reload_business()
        stored_logo = self.branding_dir / Path(business["logo_path"]).name
        self.assertTrue(stored_logo.exists())
        csrf_token = self.get_csrf_token("/config/negocio")

        removed = self.client.post(
            "/config/negocio",
            data={
                "csrf_token": csrf_token,
                "name": "Salón Nova",
                "sector": "peluquería y estética",
                "phone": "600123123",
                "address": "Calle Principal 24",
                "hours_summary": "lunes a viernes de 9:30 a 19:30 y sábados de 10:00 a 14:00",
                "hours_monday_friday": "09:30-19:30",
                "hours_saturday": "10:00-14:00",
                "hours_sunday": "cerrado",
                "welcome_message": "Hola, te ayudo con tu próxima cita.",
                "fallback_message": "Puedo ayudarte con horarios, servicios y citas.",
                "remove_logo": "1",
            },
            follow_redirects=False,
        )
        self.assertEqual(removed.status_code, 303)
        self.assertEqual(removed.headers["location"], "/config/negocio?saved=1")

        business = self.reload_business()
        self.assertEqual(str(business.get("logo_path") or ""), "")
        self.assertFalse(stored_logo.exists())

    def test_login_rejects_missing_csrf_token(self) -> None:
        response = self.client.post(
            "/login",
            data={
                "username": self.auth["admin_username"],
                "password": self.auth["admin_password"],
                "next": "/agenda",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("No he podido validar el formulario", response.text)

    def test_internal_post_rejects_missing_csrf_token(self) -> None:
        self.login_admin("/agenda")
        response = self.client.post(
            "/personal/capacidad",
            data={"capacity_color": "2"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("No he podido validar el formulario", response.text)

    def test_business_config_rejects_svg_logo(self) -> None:
        self.login_admin("/config/negocio")
        csrf_token = self.get_csrf_token("/config/negocio")

        response = self.client.post(
            "/config/negocio",
            data={
                "csrf_token": csrf_token,
                "name": "Salón Nova",
                "sector": "peluquería y estética",
                "phone": "600123123",
                "address": "Calle Principal 24",
                "hours_summary": "lunes a viernes de 9:30 a 19:30 y sábados de 10:00 a 14:00",
                "hours_monday_friday": "09:30-19:30",
                "hours_saturday": "10:00-14:00",
                "hours_sunday": "cerrado",
                "welcome_message": "Hola, te ayudo con tu próxima cita.",
                "fallback_message": "Puedo ayudarte con horarios, servicios y citas.",
            },
            files={"logo_file": ("logo.svg", b"<svg xmlns='http://www.w3.org/2000/svg'></svg>", "image/svg+xml")},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("El logo debe ser PNG, JPG/JPEG o WEBP", response.text)

    def test_access_config_updates_admin_username_and_password(self) -> None:
        self.login_admin("/config/acceso")
        csrf_token = self.get_csrf_token("/config/acceso")

        response = self.client.post(
            "/config/acceso",
            data={
                "csrf_token": csrf_token,
                "username": "encargada",
                "current_password": self.auth["admin_password"],
                "new_password": "clave-nueva-123",
                "confirm_password": "clave-nueva-123",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/config/acceso?saved=1")

        self.client.get("/logout", follow_redirects=False)
        login_page = self.client.get("/login", params={"next": "/agenda"})
        csrf_token = self.extract_csrf_token(login_page.text)
        relogin = self.client.post(
            "/login",
            data={
                "csrf_token": csrf_token,
                "username": "encargada",
                "password": "clave-nueva-123",
                "next": "/agenda",
            },
            follow_redirects=False,
        )
        self.assertEqual(relogin.status_code, 303)
        self.assertEqual(relogin.headers["location"], "/agenda")

    def test_access_config_rejects_wrong_current_password(self) -> None:
        self.login_admin("/config/acceso")
        csrf_token = self.get_csrf_token("/config/acceso")

        response = self.client.post(
            "/config/acceso",
            data={
                "csrf_token": csrf_token,
                "username": "admin",
                "current_password": "mal",
                "new_password": "clave-nueva-123",
                "confirm_password": "clave-nueva-123",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("La contraseña actual no coincide", response.text)

    def test_access_config_is_blocked_when_admin_environment_override_is_active(self) -> None:
        self.login_admin("/config/acceso")
        with patch.dict(
            os.environ,
            {
                "APP_ADMIN_USERNAME": "env-admin",
                "APP_ADMIN_PASSWORD": "env-pass-123",
            },
            clear=False,
        ):
            response = self.client.get("/config/acceso")
            self.assertEqual(response.status_code, 200)
            self.assertIn("gestionado por variables de entorno", response.text)

    def test_admin_can_create_internal_staff_user_from_panel(self) -> None:
        create_internal_user(
            self.db_path,
            username="encargada",
            password="clave-admin-123",
            role="admin",
        )
        self.login_admin("/config/usuarios/nuevo")
        csrf_token = self.get_csrf_token("/config/usuarios/nuevo")

        response = self.client.post(
            "/config/usuarios/nuevo",
            data={
                "csrf_token": csrf_token,
                "username": "recepcion",
                "role": "staff",
                "active": "on",
                "new_password": "clave-staff-123",
                "confirm_password": "clave-staff-123",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/config/usuarios?saved=1")

        self.client.get("/logout", follow_redirects=False)
        self.login_user("recepcion", "clave-staff-123", "/agenda")

    def test_cannot_deactivate_last_active_internal_admin(self) -> None:
        admin_user = create_internal_user(
            self.db_path,
            username="encargada",
            password="clave-admin-123",
            role="admin",
        )
        self.login_admin(f"/config/usuarios/{int(admin_user['id'])}/editar")
        csrf_token = self.get_csrf_token(f"/config/usuarios/{int(admin_user['id'])}/editar")

        response = self.client.post(
            f"/config/usuarios/{int(admin_user['id'])}/editar",
            data={
                "csrf_token": csrf_token,
                "username": "encargada",
                "role": "admin",
                "new_password": "",
                "confirm_password": "",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("al menos un admin interno activo", response.text)

    def test_cannot_change_last_active_internal_admin_to_staff(self) -> None:
        admin_user = create_internal_user(
            self.db_path,
            username="encargada",
            password="clave-admin-123",
            role="admin",
        )
        self.login_admin(f"/config/usuarios/{int(admin_user['id'])}/editar")
        csrf_token = self.get_csrf_token(f"/config/usuarios/{int(admin_user['id'])}/editar")

        response = self.client.post(
            f"/config/usuarios/{int(admin_user['id'])}/editar",
            data={
                "csrf_token": csrf_token,
                "username": "encargada",
                "role": "staff",
                "active": "on",
                "new_password": "",
                "confirm_password": "",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("al menos un admin interno activo", response.text)

    def test_first_internal_user_must_be_active_admin(self) -> None:
        self.login_admin("/config/usuarios/nuevo")
        csrf_token = self.get_csrf_token("/config/usuarios/nuevo")

        response = self.client.post(
            "/config/usuarios/nuevo",
            data={
                "csrf_token": csrf_token,
                "username": "recepcion",
                "role": "staff",
                "active": "on",
                "new_password": "clave-staff-123",
                "confirm_password": "clave-staff-123",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("al menos un admin interno activo", response.text)

    def test_cannot_use_bootstrap_username_for_internal_user(self) -> None:
        self.login_admin("/config/usuarios/nuevo")
        csrf_token = self.get_csrf_token("/config/usuarios/nuevo")

        response = self.client.post(
            "/config/usuarios/nuevo",
            data={
                "csrf_token": csrf_token,
                "username": self.auth["admin_username"],
                "role": "admin",
                "active": "on",
                "new_password": "clave-admin-123",
                "confirm_password": "clave-admin-123",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("reservado por el acceso admin actual", response.text)
