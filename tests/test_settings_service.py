from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.core.settings_service import SettingsService
from app.models.settings import AppSettings


class SettingsServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.settings_path = self.root / "settings.json"
        self.db_path = self.root / "worldrec.db"
        self.service = SettingsService(settings_path=str(self.settings_path))

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_load_creates_default_file_when_missing(self) -> None:
        settings = self.service.load()
        self.assertTrue(self.settings_path.exists())
        self.assertGreater(settings.batch_flush_seconds, 0.0)
        self.assertGreater(settings.batch_max_events, 0)

    def test_save_and_load_roundtrip(self) -> None:
        settings = AppSettings(
            theme="light",
            font_size="large",
            startup_filter="all",
            log_dir=str(self.root / "logs"),
            db_path=str(self.db_path),
            batch_flush_seconds=5.5,
            batch_max_events=42,
            vrchat_autostart_enabled=True,
        )
        self.service.save(settings)

        loaded = self.service.load()
        self.assertEqual(loaded.theme, "light")
        self.assertEqual(loaded.font_size, "large")
        self.assertEqual(loaded.startup_filter, "all")
        self.assertEqual(loaded.batch_flush_seconds, 5.5)
        self.assertEqual(loaded.batch_max_events, 42)
        self.assertTrue(loaded.vrchat_autostart_enabled)

    def test_backup_and_restore_restores_settings_and_db(self) -> None:
        first = AppSettings(
            theme="dark",
            log_dir=str(self.root / "logs"),
            db_path=str(self.db_path),
            batch_flush_seconds=3.0,
            batch_max_events=10,
        )
        self.service.save(first)
        self.db_path.write_bytes(b"original-db")

        backup_path = self.root / "backup.zip"
        self.service.create_backup(str(backup_path), str(self.db_path))
        self.assertTrue(backup_path.exists())

        self.service.save(AppSettings(theme="light", db_path=str(self.db_path), log_dir=str(self.root / "other")))
        self.db_path.write_bytes(b"changed-db")

        self.service.restore_backup(str(backup_path), str(self.db_path))
        restored = self.service.load()
        self.assertEqual(restored.theme, "dark")
        self.assertEqual(self.db_path.read_bytes(), b"original-db")

    def test_load_resolves_relative_db_path_from_settings_directory(self) -> None:
        self.settings_path.write_text(
            '{"db_path":"worldrec.db","log_dir":"logs"}\n',
            encoding="utf-8",
        )

        loaded = self.service.load()
        self.assertEqual(loaded.db_path, str((self.root / "worldrec.db").resolve()))


if __name__ == "__main__":
    unittest.main()
