from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class VisitHistory:
    id: int
    visited_at: str
    world_name: str
    world_id: str | None = None
    instance_id: str | None = None
    instance_access_type: str | None = None
    instance_nonce: str | None = None
    instance_raw_tags: str | None = None
    stay_duration_seconds: int | None = None
    source_log_file: str | None = None
    memo: str | None = None
    tags: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
