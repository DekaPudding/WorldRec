from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from app.db.database import Database
from app.db.history_repository import HistoryRepository
from app.models.dto import FilterCriteria


class HistoryRepositoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tempdir.name) / "worldrec-test.db")
        self.database = Database(self.db_path)
        self.database.initialize()
        self.repository = HistoryRepository(self.database)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_list_visits_with_extended_filters(self) -> None:
        self.repository.add_visit(
            visited_at=datetime(2026, 2, 23, 12, 0, 0),
            world_name="Bar Night",
            world_id="wrld_1",
            instance_access_type="hidden",
            source_log_file="output_log_a.txt",
        )
        self.repository.add_visit(
            visited_at=datetime(2026, 2, 23, 13, 0, 0),
            world_name="Friends Lounge",
            world_id="wrld_2",
            instance_access_type="friends",
            source_log_file="output_log_b.txt",
        )
        self.repository.update_notes_for_visit_group(
            visited_at="2026-02-23T12:00:00",
            world_name="Bar Night",
            world_id="wrld_1",
            memo="夜に落ち着く",
            tags="雑談, 夜",
        )

        by_name = self.repository.list_visits(FilterCriteria(world_name_query="bar"))
        self.assertEqual(len(by_name), 1)
        self.assertEqual(by_name[0].world_name, "Bar Night")

        by_tag = self.repository.list_visits(FilterCriteria(tags_query="夜"))
        self.assertEqual(len(by_tag), 1)
        self.assertEqual(by_tag[0].world_name, "Bar Night")

        by_type = self.repository.list_visits(FilterCriteria(instance_access_type="hidden"))
        self.assertEqual(len(by_type), 1)
        self.assertEqual(by_type[0].world_name, "Bar Night")

    def test_update_notes_normalizes_tag_duplicates(self) -> None:
        self.repository.add_visit(
            visited_at=datetime(2026, 2, 23, 12, 0, 0),
            world_name="Tag World",
            world_id="wrld_tag",
            source_log_file="output_log_tags.txt",
        )

        updated = self.repository.update_notes_for_visit_group(
            visited_at="2026-02-23T12:00:00",
            world_name="Tag World",
            world_id="wrld_tag",
            memo="memo",
            tags="雑談, 夜, 雑談",
        )
        self.assertGreater(updated, 0)

        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT tags FROM visit_histories WHERE world_id = 'wrld_tag' LIMIT 1"
        ).fetchone()
        conn.close()
        assert row is not None
        self.assertEqual(row[0], "雑談, 夜")

    def test_backfill_visit_metadata_updates_empty_row(self) -> None:
        visited_at = datetime(2026, 2, 23, 13, 58, 20)
        source_file = "C:\\Users\\kyuko\\AppData\\LocalLow\\VRChat\\VRChat\\output_log_x.txt"
        self.repository.add_visit(
            visited_at=visited_at,
            world_name="Bar 夜更けの語らい",
            world_id=None,
            source_log_file=source_file,
        )

        updated = self.repository.backfill_visit_metadata(
            [
                (
                    visited_at,
                    "Bar 夜更けの語らい",
                    "wrld_36e600ac-3b08-4736-b0c0-5d0fd4edb0d7",
                    "02641~hidden(usr_1)~region(jp)",
                    "hidden",
                    None,
                    "~hidden(usr_1)~region(jp)",
                    None,
                    "/mnt/c/Users/kyuko/AppData/LocalLow/VRChat/VRChat/output_log_x.txt",
                )
            ]
        )
        self.assertGreater(updated, 0)

        rows = self.repository.list_visits(FilterCriteria(world_name_query="夜更け"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].instance_access_type, "hidden")
        self.assertEqual(rows[0].world_id, "wrld_36e600ac-3b08-4736-b0c0-5d0fd4edb0d7")

    def test_count_visits_ignores_duplicate_rows_same_event(self) -> None:
        visited_at = datetime(2026, 2, 23, 13, 58, 20)
        self.repository.add_visit(
            visited_at=visited_at,
            world_name="Bar 夜更けの語らい",
            world_id="wrld_dup",
            instance_id=None,
            source_log_file="output_log_dup.txt",
        )
        self.repository.add_visit(
            visited_at=visited_at,
            world_name="Bar 夜更けの語らい",
            world_id="wrld_dup",
            instance_id="02641~hidden(usr_1)",
            source_log_file="output_log_dup.txt",
        )

        total = self.repository.count_visits_for_world("wrld_dup", "Bar 夜更けの語らい")
        self.assertEqual(total, 1)

    def test_add_visits_if_missing_ignores_duplicates_in_same_batch(self) -> None:
        visited_at = datetime(2026, 2, 23, 14, 0, 0)
        row = (
            visited_at,
            "Duplicate World",
            "wrld_dup_batch",
            "001",
            "public",
            None,
            "~public",
            None,
            "output_log_dup_batch.txt",
        )

        inserted = self.repository.add_visits_if_missing([row, row])
        self.assertEqual(inserted, 1)

        conn = sqlite3.connect(self.db_path)
        count = conn.execute(
            """
            SELECT COUNT(*)
            FROM visit_histories
            WHERE visited_at = ?
              AND world_name = ?
              AND world_id = ?
              AND instance_id = ?
              AND source_log_file = ?
            """,
            (
                visited_at.isoformat(timespec="seconds"),
                "Duplicate World",
                "wrld_dup_batch",
                "001",
                "output_log_dup_batch.txt",
            ),
        ).fetchone()
        conn.close()
        assert count is not None
        self.assertEqual(int(count[0]), 1)

    def test_backfill_visit_metadata_skips_row_that_would_violate_unique_index(self) -> None:
        visited_at = datetime(2026, 2, 23, 15, 0, 0)
        source = "output_log_conflict.txt"
        self.repository.add_visit(
            visited_at=visited_at,
            world_name="Conflict World",
            world_id=None,
            instance_id=None,
            source_log_file=source,
        )
        self.repository.add_visit(
            visited_at=visited_at,
            world_name="Conflict World",
            world_id="wrld_conflict",
            instance_id="001",
            source_log_file=source,
        )

        updated = self.repository.backfill_visit_metadata(
            [
                (
                    visited_at,
                    "Conflict World",
                    "wrld_conflict",
                    "001",
                    "public",
                    None,
                    "~public",
                    None,
                    source,
                )
            ]
        )
        self.assertGreaterEqual(updated, 0)

        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            """
            SELECT world_id, instance_id
            FROM visit_histories
            WHERE visited_at = ?
              AND world_name = ?
              AND source_log_file = ?
            ORDER BY id
            """,
            (visited_at.isoformat(timespec="seconds"), "Conflict World", source),
        ).fetchall()
        conn.close()
        self.assertEqual(len(rows), 2)


if __name__ == "__main__":
    unittest.main()
