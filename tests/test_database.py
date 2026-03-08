from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.db.database import Database


class DatabasePathFallbackTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_falls_back_to_default_when_preferred_path_is_not_writable(self) -> None:
        preferred = self.root / "preferred.db"
        fallback = self.root / "fallback.db"

        with patch.object(Database, "default_db_path", return_value=str(fallback)):
            with patch.object(Database, "_is_writable_db_target", side_effect=[False, True]):
                database = Database(str(preferred))

        self.assertEqual(database.db_path, str(fallback))

    def test_keeps_preferred_when_writable(self) -> None:
        preferred = self.root / "preferred.db"
        database = Database(str(preferred))
        self.assertEqual(Path(database.db_path), preferred)


if __name__ == "__main__":
    unittest.main()
