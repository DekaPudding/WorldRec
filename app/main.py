from __future__ import annotations

import argparse
import logging
import sys

from PySide6.QtWidgets import QApplication

from app.core.app_logging import install_qt_message_logging, setup_logging
from app.core.recommendation_service import RecommendationService
from app.core.settings_service import SettingsService
from app.core.vrchat_api_client import VrchatApiClient
from app.core.world_detail_service import WorldDetailService
from app.db.database import Database
from app.db.history_repository import HistoryRepository
from app.gui.main_window import MainWindow


def main() -> int:
    log_path = setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Application starting")
    logger.info("Arguments: %s", sys.argv[1:])
    logger.info("Log file: %s", log_path)

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--start-minimized", action="store_true")
    parsed_args, qt_args = parser.parse_known_args(sys.argv[1:])

    app_argv = [sys.argv[0], *qt_args]
    app = QApplication(app_argv)
    install_qt_message_logging()
    app.aboutToQuit.connect(lambda: logger.info("QApplication aboutToQuit received"))

    settings_service = SettingsService()
    app_settings = settings_service.load()
    logger.info("Loaded settings")

    database = Database(app_settings.db_path)
    database.initialize()
    logger.info("Database initialized: %s", database.db_path)

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

    exit_code = app.exec()
    logger.info("Application exiting with code %s", exit_code)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
