from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class AppSettings:
    schema_version: int = 1
    theme: str = "system"
    font_size: str = "standard"
    startup_filter: str = "today"
    log_dir: str = ""
    db_path: str = ""
    batch_flush_seconds: float = 2.0
    batch_max_events: int = 20
    vrchat_autostart_enabled: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> AppSettings:
        if not isinstance(data, dict):
            return cls()

        raw = cls(
            schema_version=cls._to_int(data.get("schema_version"), 1),
            theme=cls._to_str(data.get("theme"), "system"),
            font_size=cls._to_str(data.get("font_size"), "standard"),
            startup_filter=cls._to_str(data.get("startup_filter"), "today"),
            log_dir=cls._to_str(data.get("log_dir"), ""),
            db_path=cls._to_str(data.get("db_path"), ""),
            batch_flush_seconds=cls._to_float(data.get("batch_flush_seconds"), 2.0),
            batch_max_events=cls._to_int(data.get("batch_max_events"), 20),
            vrchat_autostart_enabled=bool(data.get("vrchat_autostart_enabled", False)),
        )
        return raw.sanitized()

    def sanitized(self) -> AppSettings:
        theme = self.theme if self.theme in {"system", "light", "dark"} else "system"
        font_size = self.font_size if self.font_size in {"standard", "large"} else "standard"
        startup_filter = (
            self.startup_filter
            if self.startup_filter in {"today", "yesterday", "all"}
            else "today"
        )
        flush_seconds = max(0.5, min(float(self.batch_flush_seconds), 600.0))
        max_events = max(1, min(int(self.batch_max_events), 500))
        return AppSettings(
            schema_version=max(1, int(self.schema_version)),
            theme=theme,
            font_size=font_size,
            startup_filter=startup_filter,
            log_dir=self.log_dir.strip(),
            db_path=self.db_path.strip(),
            batch_flush_seconds=flush_seconds,
            batch_max_events=max_events,
            vrchat_autostart_enabled=bool(self.vrchat_autostart_enabled),
        )

    @staticmethod
    def _to_str(value, default: str) -> str:
        if value is None:
            return default
        return str(value)

    @staticmethod
    def _to_int(value, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _to_float(value, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
