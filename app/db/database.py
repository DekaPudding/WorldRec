from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path


class Database:
    _REQUIRED_VISIT_COLUMNS: dict[str, str] = {
        "instance_access_type": "TEXT NULL",
        "instance_nonce": "TEXT NULL",
        "instance_raw_tags": "TEXT NULL",
        "stay_duration_seconds": "INTEGER NULL",
        "memo": "TEXT NULL",
        "tags": "TEXT NULL",
    }

    def __init__(self, db_path: str | None = None) -> None:
        preferred = Path(db_path).expanduser() if db_path else Path(self.default_db_path())
        self.db_path = str(preferred)
        self._ensure_writable_path()

    @staticmethod
    def default_db_path() -> str:
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return str(Path(local_app_data) / "WorldRec" / "worldrec.db")
        return str(Path.home() / ".local" / "share" / "WorldRec" / "worldrec.db")

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_writable_path(self) -> None:
        primary = Path(self.db_path)
        if self._is_writable_db_target(primary):
            self.db_path = str(primary)
            return

        fallback = Path(self.default_db_path())
        if self._is_writable_db_target(fallback):
            self.db_path = str(fallback)
            return

        raise PermissionError(f"Database path is not writable: {self.db_path}")

    @staticmethod
    def _is_writable_db_target(path: Path) -> bool:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("ab"):
                pass
            return True
        except OSError:
            return False

    def initialize(self) -> None:
        conn = self.connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS visit_histories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    visited_at TEXT NOT NULL,
                    world_name TEXT NOT NULL,
                    world_id TEXT NULL,
                    instance_id TEXT NULL,
                    instance_access_type TEXT NULL,
                    instance_nonce TEXT NULL,
                    instance_raw_tags TEXT NULL,
                    stay_duration_seconds INTEGER NULL,
                    memo TEXT NULL,
                    tags TEXT NULL,
                    source_log_file TEXT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._ensure_columns(conn, "visit_histories", self._REQUIRED_VISIT_COLUMNS)
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_visit_histories_visited_at
                ON visit_histories (visited_at)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_visit_histories_world_name
                ON visit_histories (world_name)
                """
            )
            self._deduplicate_visit_rows(conn)
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_visit_histories_event
                ON visit_histories (
                    visited_at,
                    world_name,
                    COALESCE(world_id, ''),
                    COALESCE(instance_id, ''),
                    COALESCE(source_log_file, '')
                )
                """
            )
            self._backfill_instance_metadata(conn)
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _ensure_columns(
        conn: sqlite3.Connection,
        table_name: str,
        required_columns: dict[str, str],
    ) -> None:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        existing = {str(row["name"]) for row in rows}
        for column_name, column_type in required_columns.items():
            if column_name in existing:
                continue
            conn.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
            )

    @staticmethod
    def _backfill_instance_metadata(conn: sqlite3.Connection) -> None:
        # 既存データで instance_id にタグが残っている場合、instance_raw_tags を補完する。
        now_iso = datetime.now().isoformat(timespec="seconds")
        conn.execute(
            """
            UPDATE visit_histories
            SET instance_raw_tags = substr(instance_id, instr(instance_id, '~')),
                updated_at = ?
            WHERE (instance_raw_tags IS NULL OR TRIM(instance_raw_tags) = '')
              AND instance_id IS NOT NULL
              AND instr(instance_id, '~') > 0
            """,
            (now_iso,),
        )

        access_type_expr = """
            CASE
                WHEN lower(%FIELD%) LIKE '%~friends+%' THEN 'friends+'
                WHEN lower(%FIELD%) LIKE '%~invite+%' THEN 'invite+'
                WHEN lower(%FIELD%) LIKE '%~public%' THEN 'public'
                WHEN lower(%FIELD%) LIKE '%~friends%' THEN 'friends'
                WHEN lower(%FIELD%) LIKE '%~invite%' THEN 'invite'
                WHEN lower(%FIELD%) LIKE '%~group%' THEN 'group'
                WHEN lower(%FIELD%) LIKE '%~hidden%' THEN 'hidden'
                WHEN lower(%FIELD%) LIKE '%~private%' THEN 'private'
                WHEN lower(%FIELD%) LIKE '%~offline%' THEN 'offline'
                ELSE NULL
            END
        """
        access_from_raw_tags = access_type_expr.replace("%FIELD%", "instance_raw_tags")
        access_from_instance_id = access_type_expr.replace("%FIELD%", "instance_id")

        conn.execute(
            f"""
            UPDATE visit_histories
            SET instance_access_type = {access_from_raw_tags},
                updated_at = ?
            WHERE (instance_access_type IS NULL OR TRIM(instance_access_type) = '')
              AND instance_raw_tags IS NOT NULL
              AND TRIM(instance_raw_tags) <> ''
            """,
            (now_iso,),
        )
        conn.execute(
            f"""
            UPDATE visit_histories
            SET instance_access_type = {access_from_instance_id},
                updated_at = ?
            WHERE (instance_access_type IS NULL OR TRIM(instance_access_type) = '')
              AND instance_id IS NOT NULL
              AND TRIM(instance_id) <> ''
            """,
            (now_iso,),
        )

    @staticmethod
    def _deduplicate_visit_rows(conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            DELETE FROM visit_histories
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM visit_histories
                GROUP BY
                    visited_at,
                    world_name,
                    COALESCE(world_id, ''),
                    COALESCE(instance_id, ''),
                    COALESCE(source_log_file, '')
            )
            """
        )
