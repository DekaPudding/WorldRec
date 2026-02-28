from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import date, datetime

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QFont, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStatusBar,
    QWidget,
    QVBoxLayout,
)

from app.core.history_filter_service import HistoryFilterService
from app.core.log_watcher import LogWatcher
from app.core.recommendation_service import RecommendationResponse, RecommendationService
from app.core.settings_service import SettingsService
from app.core.tag_utils import normalize_tag_string
from app.core.world_detail_service import WorldDetailService
from app.core.world_event_parser import WorldEventParser, WorldVisitEvent
from app.db.history_repository import HistoryRepository
from app.gui.settings_dialog import SettingsDialog
from app.models.dto import FilterCriteria, RecommendationItem
from app.models.entities import VisitHistory
from app.models.settings import AppSettings
from app.models.world_detail_dto import WorldDetail
from app.gui.chat_panel import ChatPanel
from app.gui.filter_panel import FilterPanel
from app.gui.history_table import HistoryTable
from app.gui.login_dialog import LoginDialog, LoginInput
from app.gui.world_detail_dialog import WorldDetailDialog


class UiBridge(QObject):
    visit_saved = Signal()
    error = Signal(str)
    info = Signal(str)
    recommendation_ready = Signal(str, object)
    world_detail_ready = Signal(int, object, str, bool)
    auth_result_ready = Signal(bool, bool, str, str, object)


@dataclass(slots=True)
class QueuedVisit:
    visited_at: datetime
    world_name: str
    world_id: str | None
    instance_id: str | None
    instance_access_type: str | None
    instance_nonce: str | None
    instance_raw_tags: str | None
    source_log_file: str | None
    stay_duration_seconds: int | None = None


@dataclass(slots=True)
class PendingDurationUpdate:
    visited_at: datetime
    world_name: str
    world_id: str | None
    instance_id: str | None
    source_log_file: str | None
    stay_duration_seconds: int


class MainWindow(QMainWindow):
    _DARK_THEME_STYLESHEET = """
            QMainWindow {
                background-color: #11161f;
            }
            QWidget#filterPanel, QWidget#historyPanel, QWidget#chatPanel {
                background-color: #1a2230;
                border: 1px solid #2a3648;
                border-radius: 10px;
            }
            QLabel#sectionTitle {
                font-size: 16px;
                font-weight: 700;
                color: #dce9ff;
                padding: 2px 2px 6px 2px;
            }
            QLabel#summaryLabel {
                color: #a9b7cd;
                padding-bottom: 4px;
            }
            QLabel#emptyStateLabel {
                color: #8ea1bf;
                font-size: 14px;
                padding: 16px;
            }
            QLabel#filterStateLabel {
                background-color: #243247;
                color: #9fc3ff;
                border-radius: 8px;
                padding: 6px 10px;
                font-weight: 600;
            }
            QLabel#filterTitleLabel {
                font-size: 18px;
                font-weight: 700;
                color: #dce9ff;
            }
            QLabel#filterDescriptionLabel {
                color: #99abc7;
                font-size: 12px;
            }
            QLabel#filterSubTitleLabel {
                color: #bed2f3;
                font-size: 13px;
                font-weight: 600;
                padding-top: 4px;
            }
            QLabel#filterFieldLabel:disabled {
                color: #5f708a;
            }
            QLabel#filterHintLabel {
                color: #8ca0bf;
                font-size: 12px;
            }
            QLabel#filterErrorLabel {
                color: #ff6e87;
                font-weight: 600;
            }
            QLabel#chatStatusLabel {
                color: #8fb9ff;
                font-weight: 600;
                padding: 2px 0 6px 0;
            }
            QTableWidget, QListWidget, QTextEdit, QCalendarWidget {
                border: 1px solid #2d3b50;
                border-radius: 8px;
                background-color: #131b27;
                color: #d6e0f0;
                gridline-color: #2a3648;
            }
            QTableWidget::item:selected, QListWidget::item:selected {
                background-color: #2b3f60;
                color: #e6eeff;
            }
            QHeaderView::section {
                background-color: #1d2a3d;
                color: #c5d5ef;
                border: none;
                border-bottom: 1px solid #31425b;
                padding: 6px;
            }
            QPushButton {
                background-color: #3e7fff;
                color: white;
                border-radius: 8px;
                padding: 6px 12px;
                border: none;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #346ee0;
            }
            QPushButton:disabled {
                background-color: #5a6f93;
                color: #d0d8e5;
            }
            QPushButton#chatOpenButton {
                min-width: 160px;
            }
            QLineEdit, QDateTimeEdit {
                border: 1px solid #3a4a62;
                border-radius: 8px;
                padding: 6px 8px;
                background: #121a26;
                color: #dce7fa;
                selection-background-color: #3b557d;
            }
            QDateTimeEdit:disabled {
                border: 1px solid #314055;
                background: #0f1520;
                color: #72839e;
            }
            QCalendarWidget QToolButton {
                color: #cfe0ff;
                background: transparent;
            }
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background-color: #1c2a3d;
            }
            QCalendarWidget QAbstractItemView:enabled {
                color: #dce7fa;
                selection-background-color: #35507a;
                selection-color: #ffffff;
                background-color: #121a26;
            }
            """

    def __init__(
        self,
        history_repository: HistoryRepository,
        recommendation_service: RecommendationService,
        world_detail_service: WorldDetailService,
        settings_service: SettingsService,
        app_settings: AppSettings,
    ) -> None:
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.setWindowTitle("WorldRec")
        self.resize(1200, 800)

        self.history_repository = history_repository
        self.recommendation_service = recommendation_service
        self.world_detail_service = world_detail_service
        self.settings_service = settings_service
        self.app_settings = app_settings.sanitized()
        self.filter_service = HistoryFilterService()
        self.current_criteria = FilterCriteria()
        self.current_filter_label = "全件"
        self.current_histories: list[VisitHistory] = []
        self._save_queue: list[QueuedVisit] = []
        self._duration_update_queue: list[PendingDurationUpdate] = []
        self._last_visit_for_duration: QueuedVisit | None = None
        self._save_queue_lock = threading.Lock()
        self._save_stop_event = threading.Event()
        self._save_wake_event = threading.Event()
        self._batch_flush_seconds = self.app_settings.batch_flush_seconds
        self._batch_max_events = self.app_settings.batch_max_events
        self._world_detail_dialog: WorldDetailDialog | None = None
        self._latest_detail_request_id = 0
        self._detail_lock = threading.Lock()
        self._pending_detail_visit_count: int | None = None
        self._pending_detail_history: VisitHistory | None = None
        self._pending_two_factor_method: str | None = None
        self._last_login_username = ""

        self.bridge = UiBridge()
        self.bridge.visit_saved.connect(self._reload_history)
        self.bridge.error.connect(self._show_error)
        self.bridge.info.connect(self._show_info)
        self.bridge.recommendation_ready.connect(self._apply_recommendation)
        self.bridge.world_detail_ready.connect(self._apply_world_detail)
        self.bridge.auth_result_ready.connect(self._apply_auth_result)

        self.filter_panel = FilterPanel()
        self.history_table = HistoryTable()
        self.chat_panel = ChatPanel()
        self.chat_open_button = QPushButton("AI検索（未実装）")
        self.chat_open_button.setObjectName("chatOpenButton")
        self.chat_open_button.setEnabled(False)
        self._chat_visible = False

        self._connect_signals()
        self._build_menu()
        self._build_layout()
        self._apply_styles()

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("起動しました")

        self.log_watcher = LogWatcher(
            parser=WorldEventParser(),
            on_event=self._on_log_event,
            on_error=lambda msg: self.bridge.error.emit(msg),
            log_dir=self.app_settings.log_dir,
        )
        self._start_initial_log_import()
        self.log_watcher.start()
        self._start_batch_saver()

        self._apply_startup_filter()
        self._reload_history()
        self.logger.info("MainWindow initialized")

    def _build_layout(self) -> None:
        self.content_splitter = QSplitter()
        self.content_splitter.addWidget(self.history_table)
        self.content_splitter.addWidget(self.chat_panel)
        self.content_splitter.setStretchFactor(0, 3)
        self.content_splitter.setStretchFactor(1, 2)

        central = QWidget()
        layout = QVBoxLayout()
        root_splitter = QSplitter()
        root_splitter.addWidget(self.filter_panel)
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_header = QHBoxLayout()
        right_header.addStretch(1)
        right_header.addWidget(self.chat_open_button)
        right_layout.addLayout(right_header)
        right_layout.addWidget(self.content_splitter)
        right_layout.setStretch(0, 0)
        right_layout.setStretch(1, 1)
        right_panel.setLayout(right_layout)
        root_splitter.addWidget(right_panel)
        root_splitter.setStretchFactor(0, 0)
        root_splitter.setStretchFactor(1, 1)
        root_splitter.setSizes([320, 980])

        self.filter_panel.setMinimumWidth(280)
        self.filter_panel.setMaximumWidth(360)
        self.chat_panel.hide()
        self.content_splitter.setSizes([1200, 0])

        layout.addWidget(root_splitter)
        central.setLayout(layout)
        self.setCentralWidget(central)

    def _connect_signals(self) -> None:
        self.filter_panel.apply_single_date.connect(self._apply_single_date)
        self.filter_panel.apply_range.connect(self._apply_range)
        self.filter_panel.today_clicked.connect(self._apply_today)
        self.filter_panel.yesterday_clicked.connect(self._apply_yesterday)
        self.filter_panel.clear_clicked.connect(self._clear_filter)
        self.chat_panel.submit_query.connect(self._run_recommendation_async)
        self.chat_open_button.clicked.connect(self._toggle_chat_panel)
        self.history_table.history_double_clicked.connect(self._on_history_double_clicked)

    def _build_menu(self) -> None:
        settings_menu = self.menuBar().addMenu("設定")
        open_settings_action = QAction("設定を開く...", self)
        open_settings_action.setShortcut(QKeySequence("Ctrl+,"))
        open_settings_action.triggered.connect(self._open_settings_dialog)
        settings_menu.addAction(open_settings_action)

    def _reload_history(self) -> None:
        try:
            histories = self.history_repository.list_visits(self.current_criteria)
        except Exception as exc:
            self._show_error(f"履歴読み込みエラー: {exc}")
            return

        self.current_histories = histories
        self.history_table.set_title(f"訪問ワールド ({self.current_filter_label})")
        self.history_table.set_rows(histories)
        if histories:
            self.status_bar.showMessage(f"履歴件数: {len(histories)}")
        else:
            self.status_bar.showMessage("該当履歴なし")

    def _apply_single_date(self, target_date: date) -> None:
        try:
            result = self.filter_service.build_for_single_date(target_date)
            self.current_criteria, self.current_filter_label = self._merge_extra_filters(
                result.criteria,
                result.state_label,
            )
            self.filter_panel.set_filter_state(result.state_label)
            self.filter_panel.clear_error()
            self._reload_history()
        except Exception as exc:
            self.filter_panel.set_error(str(exc))

    def _apply_range(self, start_dt: datetime, end_dt: datetime) -> None:
        try:
            result = self.filter_service.build_for_range(start_dt, end_dt)
            self.current_criteria, self.current_filter_label = self._merge_extra_filters(
                result.criteria,
                result.state_label,
            )
            self.filter_panel.set_filter_state(result.state_label)
            self.filter_panel.clear_error()
            self._reload_history()
        except ValueError as exc:
            self.filter_panel.set_error(str(exc))

    def _apply_today(self) -> None:
        result = self.filter_service.today()
        self.current_criteria, self.current_filter_label = self._merge_extra_filters(
            result.criteria,
            result.state_label,
        )
        self.filter_panel.set_filter_state(result.state_label)
        self.filter_panel.clear_error()
        self._reload_history()

    def _apply_yesterday(self) -> None:
        result = self.filter_service.yesterday()
        self.current_criteria, self.current_filter_label = self._merge_extra_filters(
            result.criteria,
            result.state_label,
        )
        self.filter_panel.set_filter_state(result.state_label)
        self.filter_panel.clear_error()
        self._reload_history()

    def _clear_filter(self) -> None:
        self.current_criteria = FilterCriteria()
        self.current_filter_label = "全件"
        self.filter_panel.clear_extra_filters()
        self.filter_panel.set_filter_state("全件")
        self.filter_panel.clear_error()
        self._reload_history()

    def _apply_startup_filter(self) -> None:
        if self.app_settings.startup_filter == "yesterday":
            result = self.filter_service.yesterday()
        elif self.app_settings.startup_filter == "all":
            self.current_criteria = FilterCriteria()
            self.current_filter_label = "全件"
            self.filter_panel.set_filter_state("全件")
            return
        else:
            result = self.filter_service.today()

        self.current_criteria, self.current_filter_label = self._merge_extra_filters(
            result.criteria,
            result.state_label,
        )
        self.filter_panel.set_filter_state(result.state_label)

    def _on_log_event(self, event: WorldVisitEvent, source_file: str) -> None:
        queue_size = 0
        current_visit = QueuedVisit(
            visited_at=event.visited_at,
            world_name=event.world_name,
            world_id=event.world_id,
            instance_id=event.instance_id,
            instance_access_type=event.instance_access_type,
            instance_nonce=event.instance_nonce,
            instance_raw_tags=event.instance_raw_tags,
            source_log_file=source_file,
        )

        with self._save_queue_lock:
            previous = self._last_visit_for_duration
            if previous is not None:
                stay_duration_seconds = int(
                    (current_visit.visited_at - previous.visited_at).total_seconds()
                )
                if stay_duration_seconds >= 0:
                    self._duration_update_queue.append(
                        PendingDurationUpdate(
                            visited_at=previous.visited_at,
                            world_name=previous.world_name,
                            world_id=previous.world_id,
                            instance_id=previous.instance_id,
                            source_log_file=previous.source_log_file,
                            stay_duration_seconds=stay_duration_seconds,
                        )
                    )

            self._last_visit_for_duration = current_visit
            self._save_queue.append(current_visit)
            queue_size = len(self._save_queue)

        if queue_size >= self._batch_max_events:
            self._save_wake_event.set()

    def _start_batch_saver(self) -> None:
        self._save_stop_event.clear()
        self._save_wake_event.clear()

        def run() -> None:
            while not self._save_stop_event.is_set():
                self._save_wake_event.wait(timeout=self._batch_flush_seconds)
                self._save_wake_event.clear()
                if self._save_stop_event.is_set():
                    break
                self._flush_save_queue()

        threading.Thread(target=run, daemon=True).start()

    def _start_initial_log_import(self) -> None:
        def run() -> None:
            chunk: list[QueuedVisit] = []
            inserted_total = 0
            parsed_total = 0
            chunk_size = 500
            previous_event: QueuedVisit | None = None

            try:
                for event, source_file in self.log_watcher.iter_all_log_events():
                    current_event = QueuedVisit(
                        visited_at=event.visited_at,
                        world_name=event.world_name,
                        world_id=event.world_id,
                        instance_id=event.instance_id,
                        instance_access_type=event.instance_access_type,
                        instance_nonce=event.instance_nonce,
                        instance_raw_tags=event.instance_raw_tags,
                        source_log_file=source_file,
                    )
                    parsed_total += 1

                    if previous_event is not None:
                        stay_duration_seconds = int(
                            (current_event.visited_at - previous_event.visited_at).total_seconds()
                        )
                        if stay_duration_seconds >= 0:
                            previous_event.stay_duration_seconds = stay_duration_seconds
                        chunk.append(previous_event)

                    previous_event = current_event
                    if len(chunk) >= chunk_size:
                        self.history_repository.backfill_visit_metadata(
                            [self._to_visit_row(item) for item in chunk]
                        )
                        inserted_total += self.history_repository.add_visits_if_missing(
                            [self._to_visit_row(item) for item in chunk]
                        )
                        chunk = []

                if previous_event is not None:
                    chunk.append(previous_event)

                if chunk:
                    self.history_repository.backfill_visit_metadata(
                        [self._to_visit_row(item) for item in chunk]
                    )
                    inserted_total += self.history_repository.add_visits_if_missing(
                        [self._to_visit_row(item) for item in chunk]
                    )

                if inserted_total > 0:
                    self.bridge.visit_saved.emit()
                self.bridge.info.emit(
                    f"起動時ログ取込: 解析 {parsed_total} 件 / 追加 {inserted_total} 件"
                )
            except Exception as exc:
                self.bridge.error.emit(f"起動時ログ取込エラー: {exc}")

        threading.Thread(target=run, daemon=True).start()

    def _flush_save_queue(self) -> None:
        batch: list[QueuedVisit] = []
        stay_updates: list[PendingDurationUpdate] = []
        with self._save_queue_lock:
            if self._save_queue:
                batch = self._save_queue
                self._save_queue = []
            if self._duration_update_queue:
                stay_updates = self._duration_update_queue
                self._duration_update_queue = []

        if not batch and not stay_updates:
            return

        try:
            inserted_count = 0
            updated_count = 0
            if batch:
                updated_count += self.history_repository.backfill_visit_metadata(
                    [self._to_visit_row(item) for item in batch]
                )
                inserted_count = self.history_repository.add_visits_if_missing(
                    [self._to_visit_row(item) for item in batch]
                )
            if stay_updates:
                updated_count += self.history_repository.update_stay_durations_by_event(
                    [
                        (
                            item.visited_at,
                            item.world_name,
                            item.world_id,
                            item.instance_id,
                            item.source_log_file,
                            item.stay_duration_seconds,
                        )
                        for item in stay_updates
                    ]
                )

            if inserted_count > 0 or updated_count > 0:
                self.bridge.visit_saved.emit()
        except Exception as exc:
            self.bridge.error.emit(f"履歴保存エラー: {exc}")

    @staticmethod
    def _to_visit_row(
        visit: QueuedVisit,
    ) -> tuple[
        datetime,
        str,
        str | None,
        str | None,
        str | None,
        str | None,
        str | None,
        int | None,
        str | None,
    ]:
        return (
            visit.visited_at,
            visit.world_name,
            visit.world_id,
            visit.instance_id,
            visit.instance_access_type,
            visit.instance_nonce,
            visit.instance_raw_tags,
            visit.stay_duration_seconds,
            visit.source_log_file,
        )

    def _run_recommendation_async(self, query: str) -> None:
        self.chat_panel.set_loading(True)

        def task() -> None:
            try:
                response = self.recommendation_service.recommend(query, self.current_histories)
                message = self._format_response_message(response)
                self.bridge.recommendation_ready.emit(message, response.items)
            except Exception as exc:
                self.bridge.recommendation_ready.emit(f"推薦エラー: {exc}", [])

        threading.Thread(target=task, daemon=True).start()

    def _on_history_double_clicked(self, history: VisitHistory) -> None:
        if not history.world_name:
            self._show_error("ワールド情報が不足しているため詳細を表示できません。")
            return

        visit_count: int | None = None
        try:
            visit_count = self.history_repository.count_visits_for_world(
                history.world_id,
                history.world_name,
            )
        except Exception as exc:
            self._show_error(f"総訪問回数の集計に失敗しました: {exc}")

        if self._world_detail_dialog is None:
            self._world_detail_dialog = WorldDetailDialog(self)
            self._world_detail_dialog.note_save_requested.connect(self._on_detail_note_save_requested)

        self._pending_detail_history = history
        self._pending_detail_visit_count = visit_count
        self._world_detail_dialog.set_loading(
            history.world_name,
            visit_count,
            history.instance_access_type,
        )
        self._world_detail_dialog.set_note_values(history.memo, history.tags)
        self._world_detail_dialog.show()
        self._world_detail_dialog.raise_()
        self._world_detail_dialog.activateWindow()

        with self._detail_lock:
            self._latest_detail_request_id += 1
            request_id = self._latest_detail_request_id

        self._fetch_world_detail_async(request_id, history)

    def _fetch_world_detail_async(self, request_id: int, history: VisitHistory) -> None:
        def task() -> None:
            response = self.world_detail_service.fetch_detail(history.world_id, history.world_name)
            self.bridge.world_detail_ready.emit(
                request_id,
                response.detail,
                response.warning_message or "",
                response.auth_required,
            )

        threading.Thread(target=task, daemon=True).start()

    def _apply_world_detail(
        self,
        request_id: int,
        detail: WorldDetail,
        warning_message: str,
        auth_required: bool,
    ) -> None:
        with self._detail_lock:
            if request_id != self._latest_detail_request_id:
                return

        if self._world_detail_dialog is None:
            return

        message = warning_message or None
        if auth_required:
            self._show_error("VRChat API の認証が必要です。取得できた情報のみ表示します。")
            if self._pending_detail_history is not None:
                self._open_login_dialog(self._pending_detail_history, requires_two_factor=False)
        elif message:
            self._show_error(message)

        self._world_detail_dialog.set_detail(
            detail,
            self._pending_detail_visit_count,
            self._pending_detail_history.instance_access_type if self._pending_detail_history else None,
            message,
        )

    def _on_detail_note_save_requested(self, memo: str, tags: str) -> None:
        history = self._pending_detail_history
        if history is None:
            self._show_error("保存対象の履歴が選択されていません。")
            if self._world_detail_dialog is not None:
                self._world_detail_dialog.notify_note_saved("保存対象が見つかりません。")
            return
        normalized_tags = normalize_tag_string(tags) or ""
        try:
            updated = self.history_repository.update_notes_for_visit_group(
                visited_at=history.visited_at,
                world_name=history.world_name,
                world_id=history.world_id,
                memo=memo,
                tags=normalized_tags,
            )
        except Exception as exc:
            self._show_error(f"メモ/タグ保存エラー: {exc}")
            if self._world_detail_dialog is not None:
                self._world_detail_dialog.notify_note_saved("保存に失敗しました。")
            return

        if updated <= 0:
            self._show_error("保存対象が見つからなかったため、メモ/タグを更新できませんでした。")
            if self._world_detail_dialog is not None:
                self._world_detail_dialog.notify_note_saved("保存対象が見つかりませんでした。")
            return

        self._show_info(f"メモ/タグを保存しました（{updated}件更新）")
        if self._world_detail_dialog is not None:
            self._world_detail_dialog.notify_note_saved("メモ/タグを保存しました。")
        self._reload_history()

    def _merge_extra_filters(
        self,
        criteria: FilterCriteria,
        state_label: str,
    ) -> tuple[FilterCriteria, str]:
        world_name, tags, access_type = self.filter_panel.get_extra_filters()
        merged = FilterCriteria(
            start_datetime=criteria.start_datetime,
            end_datetime=criteria.end_datetime,
            world_name_query=world_name,
            tags_query=tags,
            instance_access_type=access_type,
        )

        details: list[str] = []
        if world_name:
            details.append(f"name:{world_name}")
        if tags:
            details.append(f"tags:{tags}")
        if access_type:
            details.append(f"type:{access_type}")
        if not details:
            return (merged, state_label)
        return (merged, f"{state_label} / {' | '.join(details)}")

    def _open_login_dialog(self, history: VisitHistory, requires_two_factor: bool) -> None:
        dialog = LoginDialog(
            self,
            requires_two_factor=requires_two_factor,
            default_username=self._last_login_username,
        )
        if requires_two_factor:
            dialog.setWindowTitle("VRChat API 2FA認証")
            dialog.info_label.setText("2段階認証が必要です。メールに届いた認証コードを入力してください。")

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        login_input = dialog.get_input()
        if requires_two_factor:
            self._complete_two_factor_async(history, login_input.two_factor_code)
            return
        self._last_login_username = login_input.username
        self._authenticate_with_password_async(history, login_input)

    def _authenticate_with_password_async(self, history: VisitHistory, login_input: LoginInput) -> None:
        def task() -> None:
            result = self.world_detail_service.authenticate_with_password(
                username=login_input.username,
                password=login_input.password,
            )
            self.bridge.auth_result_ready.emit(
                result.success,
                result.requires_two_factor,
                result.message,
                result.two_factor_method or "",
                history,
            )

        threading.Thread(target=task, daemon=True).start()

    def _complete_two_factor_async(self, history: VisitHistory, code: str) -> None:
        method = self._pending_two_factor_method
        if not method:
            self._show_error("2段階認証方式を特定できません。再度ログインしてください。")
            self._open_login_dialog(history, requires_two_factor=False)
            return

        def task() -> None:
            result = self.world_detail_service.complete_two_factor(method, code)
            self.bridge.auth_result_ready.emit(
                result.success,
                result.requires_two_factor,
                result.message,
                result.two_factor_method or method,
                history,
            )

        threading.Thread(target=task, daemon=True).start()

    def _apply_auth_result(
        self,
        success: bool,
        requires_two_factor: bool,
        message: str,
        two_factor_method: str,
        history: VisitHistory,
    ) -> None:
        if success:
            self._pending_two_factor_method = None
            if message:
                self._show_info(message)
            self._on_history_double_clicked(history)
            return

        self._pending_two_factor_method = two_factor_method or self._pending_two_factor_method
        if message:
            self._show_error(message)
        if requires_two_factor:
            self._open_login_dialog(history, requires_two_factor=True)

    def _apply_recommendation(self, message: str, items: list[RecommendationItem]) -> None:
        self.chat_panel.set_loading(False)
        self.chat_panel.set_result(message, items)

    @staticmethod
    def _format_response_message(response: RecommendationResponse) -> str:
        if not response.items:
            return "AI検索機能は現在未実装です。"
        return "AI検索機能は現在未実装です。"

    def _show_error(self, message: str) -> None:
        self.logger.error(message)
        self.filter_panel.set_error(message)
        self.status_bar.showMessage(message, 8000)

    def _show_info(self, message: str) -> None:
        self.logger.info(message)
        self.status_bar.showMessage(message, 8000)

    def _toggle_chat_panel(self) -> None:
        self._show_info("AI検索機能は現在未実装です。")

    def _open_settings_dialog(self) -> None:
        dialog = SettingsDialog(self.settings_service, self.app_settings, self)
        dialog.settings_applied.connect(self._apply_settings)
        dialog.exec()

    def _apply_settings(self, settings: AppSettings) -> None:
        previous = self.app_settings
        self.app_settings = settings.sanitized()
        self._batch_flush_seconds = self.app_settings.batch_flush_seconds
        self._batch_max_events = self.app_settings.batch_max_events
        self._apply_styles()

        if previous.log_dir != self.app_settings.log_dir:
            self.log_watcher.stop()
            self.log_watcher = LogWatcher(
                parser=WorldEventParser(),
                on_event=self._on_log_event,
                on_error=lambda msg: self.bridge.error.emit(msg),
                log_dir=self.app_settings.log_dir,
            )
            self.log_watcher.start()
            self._show_info("ログ監視フォルダ設定を反映しました。")
            if not self.log_watcher.log_dir.exists():
                self._show_error("設定したログフォルダが見つかりません。パスを確認してください。")

        if previous.db_path != self.app_settings.db_path:
            self._show_info("データベース保存先は次回起動時に反映されます。")

        if previous.startup_filter != self.app_settings.startup_filter:
            self._show_info("起動時の表示期間は次回起動時に反映されます。")

    def _apply_styles(self) -> None:
        theme = self.app_settings.theme
        if theme == "light":
            self.setStyleSheet("")
        else:
            self.setStyleSheet(self._DARK_THEME_STYLESHEET)

        app = QApplication.instance()
        if app is not None:
            font_size = 12 if self.app_settings.font_size == "large" else 10
            app_font = QFont(app.font())
            app_font.setPointSize(font_size)
            app.setFont(app_font)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.logger.info("MainWindow close requested")
        self._save_stop_event.set()
        self._save_wake_event.set()
        self._flush_save_queue()
        self.log_watcher.stop()
        self.logger.info("MainWindow close completed")
        super().closeEvent(event)
