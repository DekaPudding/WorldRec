from __future__ import annotations

import json
import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from app.core.log_watcher import LogWatcher
from app.db.database import Database
from app.models.settings import AppSettings


class SettingsService:
    def __init__(self, settings_path: str | None = None) -> None:
        self.settings_path = Path(settings_path) if settings_path else self.default_settings_path()
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def default_settings_path() -> Path:
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "WorldRec" / "settings.json"
        return Path.home() / ".local" / "share" / "WorldRec" / "settings.json"

    @staticmethod
    def default_settings() -> AppSettings:
        return AppSettings(
            log_dir=str(LogWatcher.default_log_dir()),
            db_path=Database.default_db_path(),
        ).sanitized()

    def load(self) -> AppSettings:
        if not self.settings_path.exists():
            default = self.default_settings()
            self.save(default)
            return default

        try:
            payload = json.loads(self.settings_path.read_text(encoding="utf-8"))
            settings = AppSettings.from_dict(payload)
            merged = self._merge_with_defaults(settings)
            return merged
        except Exception:
            default = self.default_settings()
            self.save(default)
            return default

    def save(self, settings: AppSettings) -> AppSettings:
        normalized = self._merge_with_defaults(settings.sanitized())
        content = json.dumps(normalized.to_dict(), ensure_ascii=False, indent=2)
        self.settings_path.write_text(content + "\n", encoding="utf-8")
        return normalized

    def reset_to_default(self) -> AppSettings:
        default = self.default_settings()
        return self.save(default)

    def create_backup(self, output_zip_path: str, db_path: str) -> None:
        output_path = Path(output_zip_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
            if self.settings_path.exists():
                archive.write(self.settings_path, arcname="settings.json")
            db_file = Path(db_path)
            if db_file.exists():
                archive.write(db_file, arcname="worldrec.db")

    def restore_backup(self, backup_zip_path: str, db_path: str) -> None:
        backup = Path(backup_zip_path)
        if not backup.exists():
            raise FileNotFoundError("バックアップファイルが見つかりません。")
        with zipfile.ZipFile(backup, "r") as archive:
            members = set(archive.namelist())
            if "settings.json" in members:
                extracted = archive.read("settings.json")
                self.settings_path.parent.mkdir(parents=True, exist_ok=True)
                self.settings_path.write_bytes(extracted)
            if "worldrec.db" in members:
                db_file = Path(db_path)
                db_file.parent.mkdir(parents=True, exist_ok=True)
                temp_path = db_file.parent / f"{db_file.name}.restore-{datetime.now().timestamp()}"
                temp_path.write_bytes(archive.read("worldrec.db"))
                shutil.move(str(temp_path), str(db_file))

    def _merge_with_defaults(self, settings: AppSettings) -> AppSettings:
        defaults = self.default_settings()
        log_dir = settings.log_dir or defaults.log_dir
        db_path = settings.db_path or defaults.db_path
        return AppSettings(
            schema_version=settings.schema_version,
            theme=settings.theme,
            font_size=settings.font_size,
            startup_filter=settings.startup_filter,
            log_dir=log_dir,
            db_path=db_path,
            batch_flush_seconds=settings.batch_flush_seconds,
            batch_max_events=settings.batch_max_events,
            vrchat_autostart_enabled=settings.vrchat_autostart_enabled,
        ).sanitized()
