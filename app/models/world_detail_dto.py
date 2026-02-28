from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class WorldDetail:
    world_id: str | None
    world_name: str
    description: str | None = None
    thumbnail_url: str | None = None
    thumbnail_bytes: bytes | None = None
    capacity_bytes: int | None = None
    platforms: list[str] | None = None


@dataclass(slots=True)
class WorldDetailResponse:
    detail: WorldDetail
    warning_message: str | None = None
    auth_required: bool = False
