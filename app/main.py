from __future__ import annotations

import argparse
import sys

from PySide6.QtWidgets import QApplication

from app.core.recommendation_service import RecommendationService
from app.core.settings_service import SettingsService
from app.core.vrchat_api_client import VrchatApiClient
from app.core.world_detail_service import WorldDetailService
from app.db.database import Database
from app.db.history_repository import HistoryRepository
from app.gui.main_window import MainWindow


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--start-minimized", action="store_true")
    parsed_args, qt_args = parser.parse_known_args(sys.argv[1:])

    app_argv = [sys.argv[0], *qt_args]
    app = QApplication(app_argv)

    settings_service = SettingsService()
    app_settings = settings_service.load()

    database = Database(app_settings.db_path)
    database.initialize()

    repository = HistoryRepository(database)
    recommendation_service = RecommendationService()
    vrchat_client = VrchatApiClient()
    world_detail_service = WorldDetailService(vrchat_client)

    window = MainWindow(
        repository,
        recommendation_service,
        world_detail_service,
        settings_service,
        app_settings,
    )
    if parsed_args.start_minimized:
        window.showMinimized()
    else:
        window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
