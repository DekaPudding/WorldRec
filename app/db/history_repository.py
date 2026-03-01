from __future__ import annotations

import sqlite3
from datetime import datetime

from app.core.instance_access_type import normalize_access_type_value
from app.core.tag_utils import normalize_tag_string, split_tags
from app.db.database import Database
from app.models.dto import FilterCriteria
from app.models.entities import VisitHistory


class HistoryRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def add_visit(
        self,
        visited_at: datetime,
        world_name: str,
        world_id: str | None = None,
        instance_id: str | None = None,
        instance_access_type: str | None = None,
        instance_nonce: str | None = None,
        instance_raw_tags: str | None = None,
        stay_duration_seconds: int | None = None,
        source_log_file: str | None = None,
    ) -> int:
        now_iso = datetime.now().isoformat(timespec="seconds")
        visited_iso = visited_at.isoformat(timespec="seconds")

        conn = self.database.connect()
        try:
            cursor = conn.execute(
                """
                INSERT INTO visit_histories (
                    visited_at, world_name, world_id, instance_id,
                    instance_access_type, instance_nonce, instance_raw_tags, stay_duration_seconds,
                    memo, tags, source_log_file, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    visited_iso,
                    world_name,
                    world_id,
                    instance_id,
                    self._normalize_access_type(instance_access_type),
                    instance_nonce,
                    instance_raw_tags,
                    stay_duration_seconds,
                    None,
                    None,
                    source_log_file,
                    now_iso,
                    now_iso,
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)
        finally:
            conn.close()

    def add_visits(
        self,
        visits: list[
            tuple[
                datetime,
                str,
                str | None,
                str | None,
                str | None,
                str | None,
                str | None,
                int | None,
                str | None,
            ]
        ],
    ) -> int:
        if not visits:
            return 0

        now_iso = datetime.now().isoformat(timespec="seconds")
        rows = [
            (
                visited_at.isoformat(timespec="seconds"),
                world_name,
                world_id,
                instance_id,
                self._normalize_access_type(instance_access_type),
                instance_nonce,
                instance_raw_tags,
                stay_duration_seconds,
                None,
                None,
                source_log_file,
                now_iso,
                now_iso,
            )
            for (
                visited_at,
                world_name,
                world_id,
                instance_id,
                instance_access_type,
                instance_nonce,
                instance_raw_tags,
                stay_duration_seconds,
                source_log_file,
            ) in visits
        ]

        conn = self.database.connect()
        try:
            conn.executemany(
                """
                INSERT INTO visit_histories (
                    visited_at, world_name, world_id, instance_id,
                    instance_access_type, instance_nonce, instance_raw_tags, stay_duration_seconds,
                    memo, tags, source_log_file, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()
            return len(rows)
        finally:
            conn.close()

    def add_visits_if_missing(
        self,
        visits: list[
            tuple[
                datetime,
                str,
                str | None,
                str | None,
                str | None,
                str | None,
                str | None,
                int | None,
                str | None,
            ]
        ],
    ) -> int:
        if not visits:
            return 0

        now_iso = datetime.now().isoformat(timespec="seconds")
        rows = [
            (
                visited_at.isoformat(timespec="seconds"),
                world_name,
                world_id,
                instance_id,
                self._normalize_access_type(instance_access_type),
                instance_nonce,
                instance_raw_tags,
                stay_duration_seconds,
                None,
                None,
                source_log_file,
                now_iso,
                now_iso,
            )
            for (
                visited_at,
                world_name,
                world_id,
                instance_id,
                instance_access_type,
                instance_nonce,
                instance_raw_tags,
                stay_duration_seconds,
                source_log_file,
            ) in visits
        ]

        conn = self.database.connect()
        try:
            before_changes = conn.total_changes
            conn.executemany(
                """
                INSERT OR IGNORE INTO visit_histories (
                    visited_at, world_name, world_id, instance_id,
                    instance_access_type, instance_nonce, instance_raw_tags, stay_duration_seconds,
                    memo, tags, source_log_file, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()
            return conn.total_changes - before_changes
        finally:
            conn.close()

    def backfill_visit_metadata(
        self,
        visits: list[
            tuple[
                datetime,
                str,
                str | None,
                str | None,
                str | None,
                str | None,
                str | None,
                int | None,
                str | None,
            ]
        ],
    ) -> int:
        if not visits:
            return 0

        now_iso = datetime.now().isoformat(timespec="seconds")
        updated = 0

        conn = self.database.connect()
        try:
            for (
                visited_at,
                world_name,
                world_id,
                instance_id,
                instance_access_type,
                instance_nonce,
                instance_raw_tags,
                _stay_duration_seconds,
                source_log_file,
            ) in visits:
                new_world_id = self._normalize_optional_text(world_id)
                new_instance_id = self._normalize_optional_text(instance_id)
                new_access_type = self._normalize_access_type(instance_access_type)
                new_nonce = self._normalize_optional_text(instance_nonce)
                new_raw_tags = self._normalize_optional_text(instance_raw_tags)
                if not any([new_world_id, new_instance_id, new_access_type, new_nonce, new_raw_tags]):
                    continue

                target_rows = conn.execute(
                    """
                    SELECT id, world_id, instance_id, instance_access_type, instance_nonce, instance_raw_tags, source_log_file
                    FROM visit_histories
                    WHERE visited_at = ?
                      AND LOWER(TRIM(world_name)) = LOWER(TRIM(?))
                    """,
                    (
                        visited_at.isoformat(timespec="seconds"),
                        world_name,
                    ),
                ).fetchall()
                normalized_source_name = self._basename_normalized(source_log_file)
                if normalized_source_name:
                    narrowed_rows = [
                        row
                        for row in target_rows
                        if self._basename_normalized(row["source_log_file"]) == normalized_source_name
                    ]
                    if narrowed_rows:
                        target_rows = narrowed_rows
                for row in target_rows:
                    old_world_id = self._normalize_optional_text(row["world_id"])
                    old_instance_id = self._normalize_optional_text(row["instance_id"])
                    old_access_type = self._normalize_access_type(row["instance_access_type"])
                    old_nonce = self._normalize_optional_text(row["instance_nonce"])
                    old_raw_tags = self._normalize_optional_text(row["instance_raw_tags"])

                    next_world_id = old_world_id or new_world_id
                    next_instance_id = old_instance_id or new_instance_id
                    next_access_type = old_access_type or new_access_type
                    next_nonce = old_nonce or new_nonce
                    next_raw_tags = old_raw_tags or new_raw_tags

                    if (
                        next_world_id == old_world_id
                        and next_instance_id == old_instance_id
                        and next_access_type == old_access_type
                        and next_nonce == old_nonce
                        and next_raw_tags == old_raw_tags
                    ):
                        continue

                    try:
                        conn.execute(
                            """
                            UPDATE visit_histories
                            SET world_id = ?,
                                instance_id = ?,
                                instance_access_type = ?,
                                instance_nonce = ?,
                                instance_raw_tags = ?,
                                updated_at = ?
                            WHERE id = ?
                            """,
                            (
                                next_world_id,
                                next_instance_id,
                                next_access_type,
                                next_nonce,
                                next_raw_tags,
                                now_iso,
                                int(row["id"]),
                            ),
                        )
                        updated += 1
                    except sqlite3.IntegrityError:
                        # Skip rows that would violate the event-level unique index.
                        continue
            conn.commit()
            return updated
        finally:
            conn.close()

    def update_stay_durations_by_event(
        self,
        updates: list[tuple[datetime, str, str | None, str | None, str | None, int]],
    ) -> int:
        if not updates:
            return 0

        now_iso = datetime.now().isoformat(timespec="seconds")
        rows = [
            (
                stay_duration_seconds,
                now_iso,
                visited_at.isoformat(timespec="seconds"),
                world_name,
                world_id,
                instance_id,
                source_log_file,
            )
            for (
                visited_at,
                world_name,
                world_id,
                instance_id,
                source_log_file,
                stay_duration_seconds,
            ) in updates
            if stay_duration_seconds >= 0
        ]

        if not rows:
            return 0

        conn = self.database.connect()
        try:
            before_changes = conn.total_changes
            conn.executemany(
                """
                UPDATE visit_histories
                SET stay_duration_seconds = ?, updated_at = ?
                WHERE id = (
                    SELECT id
                    FROM visit_histories
                    WHERE visited_at = ?
                      AND world_name = ?
                      AND COALESCE(world_id, '') = COALESCE(?, '')
                      AND COALESCE(instance_id, '') = COALESCE(?, '')
                      AND COALESCE(source_log_file, '') = COALESCE(?, '')
                    ORDER BY id DESC
                    LIMIT 1
                )
                """,
                rows,
            )
            conn.commit()
            return conn.total_changes - before_changes
        finally:
            conn.close()

    def count_visits_for_world(self, world_id: str | None, world_name: str) -> int:
        conn = self.database.connect()
        try:
            if world_id and world_id.strip():
                row = conn.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM (
                        SELECT visited_at, LOWER(TRIM(world_name)) AS world_name_key, COALESCE(source_log_file, '') AS source_key
                        FROM visit_histories
                        WHERE world_id = ?
                        GROUP BY visited_at, world_name_key, source_key
                    )
                    """,
                    (world_id.strip(),),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM (
                        SELECT visited_at, LOWER(TRIM(world_name)) AS world_name_key, COALESCE(source_log_file, '') AS source_key
                        FROM visit_histories
                        WHERE LOWER(TRIM(world_name)) = LOWER(TRIM(?))
                        GROUP BY visited_at, world_name_key, source_key
                    )
                    """,
                    (world_name,),
                ).fetchone()

            if row is None:
                return 0
            return int(row["total"])
        finally:
            conn.close()

    def update_notes_for_visit_group(
        self,
        visited_at: str,
        world_name: str,
        world_id: str | None,
        memo: str,
        tags: str,
    ) -> int:
        now_iso = datetime.now().isoformat(timespec="seconds")
        memo_value = self._normalize_optional_text(memo)
        tags_value = normalize_tag_string(tags)

        conn = self.database.connect()
        try:
            if world_id and world_id.strip():
                cursor = conn.execute(
                    """
                    UPDATE visit_histories
                    SET memo = ?, tags = ?, updated_at = ?
                    WHERE world_id = ?
                      AND substr(visited_at, 1, 10) = substr(?, 1, 10)
                    """,
                    (memo_value, tags_value, now_iso, world_id.strip(), visited_at),
                )
            else:
                cursor = conn.execute(
                    """
                    UPDATE visit_histories
                    SET memo = ?, tags = ?, updated_at = ?
                    WHERE LOWER(TRIM(world_name)) = LOWER(TRIM(?))
                      AND substr(visited_at, 1, 10) = substr(?, 1, 10)
                    """,
                    (memo_value, tags_value, now_iso, world_name, visited_at),
                )
            conn.commit()
            return int(cursor.rowcount)
        finally:
            conn.close()

    def list_visits(self, criteria: FilterCriteria | None = None) -> list[VisitHistory]:
        criteria = criteria or FilterCriteria()
        sql = """
            SELECT
                MIN(id) AS id,
                MIN(visited_at) AS visited_at,
                world_name,
                MIN(world_id) AS world_id,
                MIN(instance_id) AS instance_id,
                REPLACE(COALESCE(GROUP_CONCAT(DISTINCT instance_access_type), ''), ',', ', ') AS instance_access_type,
                MIN(instance_nonce) AS instance_nonce,
                MIN(instance_raw_tags) AS instance_raw_tags,
                MAX(stay_duration_seconds) AS stay_duration_seconds,
                MAX(memo) AS memo,
                MAX(tags) AS tags,
                MIN(source_log_file) AS source_log_file,
                MIN(created_at) AS created_at,
                MAX(updated_at) AS updated_at
            FROM visit_histories
        """
        where_clauses: list[str] = [
            "LOWER(TRIM(world_name)) NOT IN ('home', 'ホーム', 'ホームワールド')",
        ]
        params: list[str] = []

        if criteria.start_datetime is not None:
            where_clauses.append("visited_at >= ?")
            params.append(criteria.start_datetime.isoformat(timespec="seconds"))
        if criteria.end_datetime is not None:
            where_clauses.append("visited_at <= ?")
            params.append(criteria.end_datetime.isoformat(timespec="seconds"))
        if criteria.world_name_query:
            where_clauses.append("LOWER(world_name) LIKE ?")
            params.append(f"%{criteria.world_name_query.strip().lower()}%")
        if criteria.instance_access_type:
            where_clauses.append("LOWER(COALESCE(instance_access_type, '')) = ?")
            params.append(criteria.instance_access_type.strip().lower())
        for tag in split_tags(criteria.tags_query):
            where_clauses.append("LOWER(COALESCE(tags, '')) LIKE ?")
            params.append(f"%{tag.lower()}%")

        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)

        sql += " GROUP BY substr(visited_at, 1, 10), world_name"
        sql += " ORDER BY visited_at DESC"

        conn = self.database.connect()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [
                VisitHistory(
                    id=int(row["id"]),
                    visited_at=str(row["visited_at"]),
                    world_name=str(row["world_name"]),
                    world_id=row["world_id"],
                    instance_id=row["instance_id"],
                    instance_access_type=self._normalize_access_type(row["instance_access_type"]),
                    instance_nonce=row["instance_nonce"],
                    instance_raw_tags=row["instance_raw_tags"],
                    stay_duration_seconds=row["stay_duration_seconds"],
                    source_log_file=row["source_log_file"],
                    memo=self._normalize_optional_text(row["memo"]),
                    tags=self._normalize_optional_text(row["tags"]),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in rows
            ]
        finally:
            conn.close()

    def list_tag_candidates(self, limit: int = 200) -> list[str]:
        conn = self.database.connect()
        try:
            rows = conn.execute(
                """
                SELECT tags
                FROM visit_histories
                WHERE tags IS NOT NULL AND TRIM(tags) <> ''
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (max(10, limit),),
            ).fetchall()
        finally:
            conn.close()

        result: list[str] = []
        seen: set[str] = set()
        for row in rows:
            for tag in split_tags(row["tags"]):
                key = tag.casefold()
                if key in seen:
                    continue
                seen.add(key)
                result.append(tag)
        return result[:limit]

    @staticmethod
    def _normalize_optional_text(value) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        if not normalized:
            return None
        return normalized

    @staticmethod
    def _normalize_access_type(value) -> str | None:
        normalized = HistoryRepository._normalize_optional_text(value)
        if normalized is None:
            return None
        canonical = normalize_access_type_value(normalized)
        return canonical or normalized

    @staticmethod
    def _basename_normalized(value) -> str | None:
        normalized = HistoryRepository._normalize_optional_text(value)
        if normalized is None:
            return None
        normalized = normalized.replace("\\", "/")
        if "/" not in normalized:
            return normalized
        return normalized.rsplit("/", 1)[-1]
