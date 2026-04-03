from __future__ import annotations

import importlib
import logging
import tempfile
import unittest
from pathlib import Path

import app.core.app_logging as app_logging


class AppLoggingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.log_dir = Path(self.tempdir.name)
        # Reset module-level state for deterministic tests.
        importlib.reload(app_logging)

    def tearDown(self) -> None:
        root = logging.getLogger()
        for handler in list(root.handlers):
            root.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass
        self.tempdir.cleanup()

    def test_setup_logging_creates_daily_log_file(self) -> None:
        path = app_logging.setup_logging(self.log_dir)
        logging.getLogger("test").info("hello log")

        self.assertTrue(path.exists())
        content = path.read_text(encoding="utf-8")
        self.assertIn("hello log", content)
        self.assertIn("[INFO]", content)


if __name__ == "__main__":
    unittest.main()
