from __future__ import annotations

import logging
import os
import sys
import threading
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOCK = threading.Lock()
_CONFIGURED_LOG_PATH: Path | None = None
_QT_HANDLER_INSTALLED = False


def default_log_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "WorldRec" / "logs"
    return Path.home() / ".local" / "share" / "WorldRec" / "logs"


def setup_logging(log_dir: str | Path | None = None) -> Path:
    global _CONFIGURED_LOG_PATH
    with _LOCK:
        if _CONFIGURED_LOG_PATH is not None:
            return _CONFIGURED_LOG_PATH

        target_dir = Path(log_dir) if log_dir else default_log_dir()
        target_dir.mkdir(parents=True, exist_ok=True)
        filename = datetime.now().strftime("worldrec-%Y%m%d.log")
        log_path = target_dir / filename

        formatter = logging.Formatter(
            fmt="%(asctime)s.%(msecs)03d [%(levelname)s] %(threadName)s %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        root = logging.getLogger()
        root.setLevel(logging.INFO)

        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=2 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

        _install_exception_hooks()

        _CONFIGURED_LOG_PATH = log_path
        logging.getLogger(__name__).info("File logging initialized: %s", log_path)
        return log_path


def install_qt_message_logging() -> None:
    global _QT_HANDLER_INSTALLED
    if _QT_HANDLER_INSTALLED:
        return

    try:
        from PySide6.QtCore import QtMsgType, qInstallMessageHandler
    except Exception:
        logging.getLogger(__name__).warning("Qt message logging disabled: PySide6 unavailable")
        return

    def _handler(msg_type, context, message: str) -> None:
        logger = logging.getLogger("qt")
        if msg_type == QtMsgType.QtDebugMsg:
            logger.debug(message)
        elif msg_type == QtMsgType.QtInfoMsg:
            logger.info(message)
        elif msg_type == QtMsgType.QtWarningMsg:
            logger.warning(message)
        elif msg_type == QtMsgType.QtCriticalMsg:
            logger.error(message)
        else:
            logger.critical(message)

    qInstallMessageHandler(_handler)
    _QT_HANDLER_INSTALLED = True
    logging.getLogger(__name__).info("Qt message logging enabled")


def _install_exception_hooks() -> None:
    def _sys_hook(exc_type, exc_value, exc_traceback) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logging.getLogger("uncaught").critical(
            "Unhandled exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    def _thread_hook(args: threading.ExceptHookArgs) -> None:
        logging.getLogger("uncaught.thread").critical(
            "Unhandled thread exception in %s",
            getattr(args.thread, "name", "<unknown>"),
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = _sys_hook
    threading.excepthook = _thread_hook
