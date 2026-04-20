from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from demo.core.config import (
    hash_admin_password,
    initialize_business_runtime_data,
    load_auth_config,
    load_business_config,
    upsert_auth_overrides,
    verify_admin_password,
)
from demo.core.db import init_db


CONFIG_PATH = Path(__file__).resolve().parents[1] / "demo" / "data" / "negocio.json"


class ConfigLoadingTests(TestCase):
    def setUp(self) -> None:
        self._tmpdir = TemporaryDirectory()
        self.db_path = Path(self._tmpdir.name) / "negocio.db"
        init_db(self.db_path)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_load_business_config_is_read_only(self) -> None:
        with patch("demo.core.config.seed_operational_data") as seed_mock, patch(
            "demo.core.config.backfill_appointment_service_ids"
        ) as backfill_mock:
            business = load_business_config(CONFIG_PATH, self.db_path)

        seed_mock.assert_not_called()
        backfill_mock.assert_not_called()
        self.assertEqual(business["name"], "Peluquería Nova")

    def test_initialize_business_runtime_data_runs_seed_and_backfill(self) -> None:
        with patch("demo.core.config.seed_operational_data") as seed_mock, patch(
            "demo.core.config.backfill_appointment_service_ids"
        ) as backfill_mock:
            initialize_business_runtime_data(CONFIG_PATH, self.db_path)

        seed_mock.assert_called_once()
        backfill_mock.assert_called_once_with(self.db_path)

    def test_partial_environment_bootstrap_is_ignored(self) -> None:
        upsert_auth_overrides(
            self.db_path,
            {
                "admin_username": "panel-admin",
                "admin_password_hash": hash_admin_password("panel-pass-123"),
            },
        )

        with patch.dict(os.environ, {"APP_ADMIN_USERNAME": "env-admin"}, clear=False):
            auth = load_auth_config(CONFIG_PATH, self.db_path)

        self.assertEqual(auth["admin_username"], "panel-admin")
        self.assertEqual(auth["admin_source"], "panel")
        self.assertFalse(auth["managed_by_env"])
        self.assertTrue(verify_admin_password("panel-pass-123", auth["admin_password"]))

    def test_environment_bootstrap_requires_both_credentials(self) -> None:
        upsert_auth_overrides(
            self.db_path,
            {
                "admin_username": "panel-admin",
                "admin_password_hash": hash_admin_password("panel-pass-123"),
            },
        )

        with patch.dict(
            os.environ,
            {
                "APP_ADMIN_USERNAME": "env-admin",
                "APP_ADMIN_PASSWORD": "env-pass-123",
            },
            clear=False,
        ):
            auth = load_auth_config(CONFIG_PATH, self.db_path)

        self.assertEqual(auth["admin_username"], "env-admin")
        self.assertEqual(auth["admin_password"], "env-pass-123")
        self.assertEqual(auth["admin_source"], "environment")
        self.assertTrue(auth["managed_by_env"])
