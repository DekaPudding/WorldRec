from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from app.models.dto import FilterCriteria


@dataclass(slots=True)
class FilterBuildResult:
    criteria: FilterCriteria
    state_label: str


class HistoryFilterService:
    @staticmethod
    def build_for_single_date(target_date: date) -> FilterBuildResult:
        start_dt = datetime.combine(target_date, time.min)
        end_dt = datetime.combine(target_date, time.max.replace(microsecond=0))
        return FilterBuildResult(
            criteria=FilterCriteria(start_datetime=start_dt, end_datetime=end_dt),
            state_label=target_date.isoformat(),
        )

    @staticmethod
    def build_for_range(
        start_dt: datetime | None,
        end_dt: datetime | None,
    ) -> FilterBuildResult:
        if start_dt and end_dt and start_dt > end_dt:
            raise ValueError("開始日時は終了日時以前を指定してください")

        if start_dt is None and end_dt is None:
            return FilterBuildResult(criteria=FilterCriteria(), state_label="全件")

        start_text = start_dt.isoformat(sep=" ", timespec="minutes") if start_dt else "-∞"
        end_text = end_dt.isoformat(sep=" ", timespec="minutes") if end_dt else "+∞"
        label = f"{start_text} ～ {end_text}"
        return FilterBuildResult(
            criteria=FilterCriteria(start_datetime=start_dt, end_datetime=end_dt),
            state_label=label,
        )

    @staticmethod
    def today() -> FilterBuildResult:
        return HistoryFilterService.build_for_single_date(datetime.now().date())

    @staticmethod
    def yesterday() -> FilterBuildResult:
        return HistoryFilterService.build_for_single_date((datetime.now() - timedelta(days=1)).date())
