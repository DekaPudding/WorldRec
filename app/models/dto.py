from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(slots=True)
class FilterCriteria:
    single_date: date | None = None
    start_datetime: datetime | None = None
    end_datetime: datetime | None = None
    world_name_query: str | None = None
    tags_query: str | None = None
    instance_access_type: str | None = None


@dataclass(slots=True)
class RecommendationItem:
    world_name: str
    visited_at: str
    reason: str
