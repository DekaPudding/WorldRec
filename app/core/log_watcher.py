from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Callable, Iterator, TextIO

from app.core.world_event_parser import WorldEventParser, WorldVisitEvent

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    _WATCHDOG_AVAILABLE = True
except Exception:
    FileSystemEventHandler = object  # type: ignore[assignment]
    Observer = None  # type: ignore[assignment]
    _WATCHDOG_AVAILABLE = False


class _LogDirEventHandler(FileSystemEventHandler):
    def __init__(self, wake: threading.Event) -> None:
        super().__init__()
        self.wake = wake

    def on_modified(self, event) -> None:  # type: ignore[override]
        self.wake.set()

    def on_created(self, event) -> None:  # type: ignore[override]
        self.wake.set()

    def on_moved(self, event) -> None:  # type: ignore[override]
        self.wake.set()


class LogWatcher:
    def __init__(
        self,
        parser: WorldEventParser,
        on_event: Callable[[WorldVisitEvent, str], None],
        on_error: Callable[[str], None],
        log_dir: str | None = None,
        poll_seconds: float = 1.0,
    ) -> None:
        self.parser = parser
        self.on_event = on_event
        self.on_error = on_error
        self.poll_seconds = poll_seconds
        self.log_dir = Path(log_dir) if log_dir else self.default_log_dir()

        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()

        self._active_file: Path | None = None
        self._active_fp: TextIO | None = None
        self._file_position = 0
        self._bootstrap_bytes = 1024 * 1024

    @staticmethod
    def default_log_dir() -> Path:
        user_profile = os.environ.get("USERPROFILE")
        if user_profile:
            return Path(user_profile) / "AppData" / "LocalLow" / "VRChat" / "VRChat"
        return Path.home() / "AppData" / "LocalLow" / "VRChat" / "VRChat"

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._wake_event.clear()
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._wake_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._close_active_file()

    def _watch_loop(self) -> None:
        observer = None
        try:
            if _WATCHDOG_AVAILABLE and self.log_dir.exists():
                event_handler = _LogDirEventHandler(self._wake_event)
                observer = Observer()
                observer.schedule(event_handler, str(self.log_dir), recursive=False)
                observer.start()

            while not self._stop_event.is_set():
                try:
                    self._refresh_active_log_file()
                    self._read_available_lines()
                except Exception as exc:
                    self.on_error(f"ログ監視エラー: {exc}")

                if observer is not None:
                    self._wake_event.wait(timeout=self.poll_seconds)
                    self._wake_event.clear()
                else:
                    time.sleep(self.poll_seconds)
        finally:
            if observer is not None:
                observer.stop()
                observer.join(timeout=2)
            self._close_active_file()

    def _refresh_active_log_file(self) -> None:
        latest = self._find_latest_log_file()
        if latest is None:
            self._close_active_file()
            self._active_file = None
            self._file_position = 0
            return

        switched = self._active_file != latest
        if switched:
            self._open_active_file(latest)
            return

        if self._active_fp is None:
            self._open_active_file(latest)
            return

        try:
            size = latest.stat().st_size
            if size < self._file_position:
                self._active_fp.seek(0)
                self._file_position = 0
        except OSError:
            self._open_active_file(latest)

    def _open_active_file(self, file_path: Path) -> None:
        self._close_active_file()
        self._active_file = file_path
        fp = file_path.open("r", encoding="utf-8", errors="ignore")
        size = file_path.stat().st_size
        self._file_position = max(0, size - self._bootstrap_bytes)
        fp.seek(self._file_position)
        self._active_fp = fp

    def _read_available_lines(self) -> None:
        if self._active_fp is None or self._active_file is None:
            return

        while True:
            line = self._active_fp.readline()
            if not line:
                break
            self._file_position = self._active_fp.tell()
            event = self.parser.parse_line(line)
            if event:
                self.on_event(event, str(self._active_file))

    def _close_active_file(self) -> None:
        if self._active_fp is not None:
            self._active_fp.close()
        self._active_fp = None

    def iter_all_log_events(self) -> Iterator[tuple[WorldVisitEvent, str]]:
        if not self.log_dir.exists():
            return

        # リアルタイム監視とは独立した文脈で解析し、pending context の混線を防ぐ。
        parser = WorldEventParser()
        logs = sorted(self.log_dir.glob("output_log_*.txt"), key=lambda p: p.stat().st_mtime)
        for log_file in logs:
            try:
                with log_file.open("r", encoding="utf-8", errors="ignore") as fp:
                    for line in fp:
                        event = parser.parse_line(line)
                        if event:
                            yield (event, str(log_file))
            except Exception as exc:
                self.on_error(f"起動時ログ取込エラー({log_file.name}): {exc}")

    def _find_latest_log_file(self) -> Path | None:
        if not self.log_dir.exists():
            return None

        logs = list(self.log_dir.glob("output_log_*.txt"))
        if not logs:
            return None

        return max(logs, key=lambda p: p.stat().st_mtime)
