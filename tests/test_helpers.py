from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from demo.core.config import initialize_business_runtime_data, load_business_config
from demo.core.db import init_db


CONFIG_PATH = Path(__file__).resolve().parents[1] / "demo" / "data" / "negocio.json"


class DemoTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = TemporaryDirectory()
        self.db_path = Path(self._tmpdir.name) / "negocio.db"
        init_db(self.db_path)
        initialize_business_runtime_data(CONFIG_PATH, self.db_path)
        self.business = load_business_config(CONFIG_PATH, self.db_path)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def reload_business(self) -> dict:
        self.business = load_business_config(CONFIG_PATH, self.db_path)
        return self.business
