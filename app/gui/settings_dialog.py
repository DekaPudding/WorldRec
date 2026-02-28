from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QDoubleSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.core.settings_service import SettingsService
from app.models.settings import AppSettings


class SettingsDialog(QDialog):
    settings_applied = Signal(object)

    def __init__(
        self,
        settings_service: SettingsService,
        current_settings: AppSettings,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.settings_service = settings_service
        self.current_settings = current_settings

        self.setWindowTitle("設定")
        self.setModal(True)
        self.resize(760, 560)

        self.tabs = QTabWidget()
        self.basic_tab = self._build_basic_tab()
        self.advanced_tab = self._build_advanced_tab()
        self.data_tab = self._build_data_tab()
        self.tabs.addTab(self.basic_tab, "基本設定")
        self.tabs.addTab(self.advanced_tab, "詳細設定")
        self.tabs.addTab(self.data_tab, "データ管理")

        self.status_label = QLabel("")

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.RestoreDefaults
        )
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._on_apply)
        self.button_box.rejected.connect(self.reject)
        self.button_box.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(
            self._on_reset_current_tab
        )

        layout = QVBoxLayout()
        layout.addWidget(self.tabs)
        layout.addWidget(self.status_label)
        layout.addWidget(self.button_box)
        self.setLayout(layout)

        self._set_values(self.current_settings)

    def _build_basic_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout()

        appearance_group = QGroupBox("見た目")
        appearance_form = QFormLayout()
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("システムに合わせる", "system")
        self.theme_combo.addItem("ライト", "light")
        self.theme_combo.addItem("ダーク", "dark")
        self.font_combo = QComboBox()
        self.font_combo.addItem("標準", "standard")
        self.font_combo.addItem("大きめ", "large")
        appearance_form.addRow("テーマ", self.theme_combo)
        appearance_form.addRow("文字サイズ", self.font_combo)
        appearance_group.setLayout(appearance_form)

        startup_group = QGroupBox("起動時の表示")
        startup_form = QFormLayout()
        self.startup_filter_combo = QComboBox()
        self.startup_filter_combo.addItem("今日", "today")
        self.startup_filter_combo.addItem("昨日", "yesterday")
        self.startup_filter_combo.addItem("全件", "all")
        startup_form.addRow("起動時に表示する期間", self.startup_filter_combo)
        startup_group.setLayout(startup_form)

        ai_group = QGroupBox("AI検索")
        ai_layout = QVBoxLayout()
        ai_layout.addWidget(QLabel("AI検索機能は現在未実装です。"))
        ai_group.setLayout(ai_layout)

        layout.addWidget(appearance_group)
        layout.addWidget(startup_group)
        layout.addWidget(ai_group)
        layout.addStretch(1)
        tab.setLayout(layout)
        return tab

    def _build_advanced_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout()

        notice = QLabel("通常は変更不要です。設定を変更すると記録や連携が動かなくなる場合があります。")
        notice.setWordWrap(True)
        layout.addWidget(notice)

        path_group = QGroupBox("パス")
        path_form = QFormLayout()

        self.log_dir_edit = QLineEdit()
        self.db_path_edit = QLineEdit()
        log_row = QHBoxLayout()
        log_row.addWidget(self.log_dir_edit)
        log_browse = QPushButton("参照...")
        log_browse.clicked.connect(self._choose_log_dir)
        log_row.addWidget(log_browse)
        db_row = QHBoxLayout()
        db_row.addWidget(self.db_path_edit)
        db_browse = QPushButton("参照...")
        db_browse.clicked.connect(self._choose_db_path)
        db_row.addWidget(db_browse)

        log_container = QWidget()
        log_container.setLayout(log_row)
        db_container = QWidget()
        db_container.setLayout(db_row)
        path_form.addRow("VRChatログフォルダ", log_container)
        path_form.addRow("データベース保存先", db_container)
        path_group.setLayout(path_form)

        batch_group = QGroupBox("保存")
        batch_form = QFormLayout()
        self.flush_spin = QDoubleSpinBox()
        self.flush_spin.setRange(0.5, 600.0)
        self.flush_spin.setSingleStep(0.5)
        self.flush_spin.setDecimals(1)
        self.max_events_spin = QSpinBox()
        self.max_events_spin.setRange(1, 500)
        batch_form.addRow("保存の間隔（秒）", self.flush_spin)
        batch_form.addRow("まとめて保存する件数", self.max_events_spin)
        batch_group.setLayout(batch_form)

        startup_group = QGroupBox("自動起動")
        startup_layout = QVBoxLayout()
        self.autostart_checkbox = QCheckBox("VRChat連動自動起動を使う")
        buttons_row = QHBoxLayout()
        self.register_task_button = QPushButton("自動起動タスクを登録...")
        self.unregister_task_button = QPushButton("自動起動タスクを解除...")
        self.register_task_button.clicked.connect(self._register_startup_task)
        self.unregister_task_button.clicked.connect(self._unregister_startup_task)
        buttons_row.addWidget(self.register_task_button)
        buttons_row.addWidget(self.unregister_task_button)
        startup_layout.addWidget(self.autostart_checkbox)
        startup_layout.addLayout(buttons_row)
        startup_group.setLayout(startup_layout)

        layout.addWidget(path_group)
        layout.addWidget(batch_group)
        layout.addWidget(startup_group)
        layout.addStretch(1)
        tab.setLayout(layout)
        return tab

    def _build_data_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout()

        backup_group = QGroupBox("バックアップと復元")
        backup_layout = QVBoxLayout()
        backup_button = QPushButton("バックアップを作成...")
        restore_button = QPushButton("バックアップから復元...")
        backup_button.clicked.connect(self._create_backup)
        restore_button.clicked.connect(self._restore_backup)
        backup_layout.addWidget(backup_button)
        backup_layout.addWidget(restore_button)
        backup_group.setLayout(backup_layout)

        reset_group = QGroupBox("設定初期化")
        reset_layout = QVBoxLayout()
        reset_button = QPushButton("設定のみ初期化")
        reset_button.clicked.connect(self._reset_all_settings)
        reset_layout.addWidget(reset_button)
        reset_group.setLayout(reset_layout)

        layout.addWidget(backup_group)
        layout.addWidget(reset_group)
        layout.addStretch(1)
        tab.setLayout(layout)
        return tab

    def _set_values(self, settings: AppSettings) -> None:
        self._set_combo_value(self.theme_combo, settings.theme)
        self._set_combo_value(self.font_combo, settings.font_size)
        self._set_combo_value(self.startup_filter_combo, settings.startup_filter)
        self.log_dir_edit.setText(settings.log_dir)
        self.db_path_edit.setText(settings.db_path)
        self.flush_spin.setValue(settings.batch_flush_seconds)
        self.max_events_spin.setValue(settings.batch_max_events)
        self.autostart_checkbox.setChecked(settings.vrchat_autostart_enabled)

    def _collect_settings(self) -> AppSettings:
        return AppSettings(
            schema_version=self.current_settings.schema_version,
            theme=str(self.theme_combo.currentData()),
            font_size=str(self.font_combo.currentData()),
            startup_filter=str(self.startup_filter_combo.currentData()),
            log_dir=self.log_dir_edit.text().strip(),
            db_path=self.db_path_edit.text().strip(),
            batch_flush_seconds=float(self.flush_spin.value()),
            batch_max_events=int(self.max_events_spin.value()),
            vrchat_autostart_enabled=self.autostart_checkbox.isChecked(),
        ).sanitized()

    def _validate(self, settings: AppSettings) -> str | None:
        if not settings.log_dir:
            return "VRChatログフォルダを入力してください。"
        if not settings.db_path:
            return "データベース保存先を入力してください。"
        return None

    def _on_apply(self) -> None:
        candidate = self._collect_settings()
        error = self._validate(candidate)
        if error:
            self.status_label.setText(error)
            return
        try:
            saved = self.settings_service.save(candidate)
        except Exception as exc:
            self.status_label.setText(f"設定保存に失敗しました: {exc}")
            return

        self.current_settings = saved
        self.settings_applied.emit(saved)
        self.status_label.setText("設定を保存しました。")

    def _on_accept(self) -> None:
        self._on_apply()
        if self.status_label.text().startswith("設定を保存しました"):
            self.accept()

    def _on_reset_current_tab(self) -> None:
        defaults = self.settings_service.default_settings()
        current_tab = self.tabs.currentIndex()
        if current_tab == 0:
            self._set_combo_value(self.theme_combo, defaults.theme)
            self._set_combo_value(self.font_combo, defaults.font_size)
            self._set_combo_value(self.startup_filter_combo, defaults.startup_filter)
        elif current_tab == 1:
            self.log_dir_edit.setText(defaults.log_dir)
            self.db_path_edit.setText(defaults.db_path)
            self.flush_spin.setValue(defaults.batch_flush_seconds)
            self.max_events_spin.setValue(defaults.batch_max_events)
            self.autostart_checkbox.setChecked(defaults.vrchat_autostart_enabled)
        self.status_label.setText("現在のタブを初期値に戻しました。")

    def _reset_all_settings(self) -> None:
        result = QMessageBox.question(
            self,
            "確認",
            "設定を初期化しますか？（履歴データは削除されません）",
        )
        if result != QMessageBox.StandardButton.Yes:
            return
        defaults = self.settings_service.reset_to_default()
        self.current_settings = defaults
        self._set_values(defaults)
        self.settings_applied.emit(defaults)
        self.status_label.setText("設定を初期化しました。")

    def _choose_log_dir(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "VRChatログフォルダを選択", self.log_dir_edit.text())
        if selected:
            self.log_dir_edit.setText(selected)

    def _choose_db_path(self) -> None:
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "データベース保存先を選択",
            self.db_path_edit.text() or "worldrec.db",
            "SQLite DB (*.db);;All Files (*)",
        )
        if selected:
            self.db_path_edit.setText(selected)

    def _create_backup(self) -> None:
        now_suffix = datetime.now().strftime("%Y%m%d-%H%M%S")
        default_name = f"WorldRec-backup-{now_suffix}.zip"
        selected, _ = QFileDialog.getSaveFileName(self, "バックアップ保存先", default_name, "Zip (*.zip)")
        if not selected:
            return
        try:
            db_path = self.db_path_edit.text().strip() or self.current_settings.db_path
            self.settings_service.create_backup(selected, db_path)
            self.status_label.setText("バックアップを作成しました。")
        except Exception as exc:
            self.status_label.setText(f"バックアップ作成に失敗しました: {exc}")

    def _restore_backup(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(self, "バックアップファイルを選択", "", "Zip (*.zip)")
        if not selected:
            return

        result = QMessageBox.question(
            self,
            "確認",
            "バックアップから復元しますか？現在の設定とDBが上書きされます。",
        )
        if result != QMessageBox.StandardButton.Yes:
            return

        try:
            db_path = self.db_path_edit.text().strip() or self.current_settings.db_path
            self.settings_service.restore_backup(selected, db_path)
            loaded = self.settings_service.load()
            self.current_settings = loaded
            self._set_values(loaded)
            self.settings_applied.emit(loaded)
            self.status_label.setText("バックアップを復元しました。")
        except Exception as exc:
            self.status_label.setText(f"バックアップ復元に失敗しました: {exc}")

    def _register_startup_task(self) -> None:
        self._run_startup_script("register-startup-task.ps1", ["-PollSeconds", "60"])

    def _unregister_startup_task(self) -> None:
        self._run_startup_script("unregister-startup-task.ps1", [])

    def _run_startup_script(self, script_name: str, args: list[str]) -> None:
        if os.name != "nt":
            self.status_label.setText("この機能はWindowsでのみ利用できます。")
            return

        app_root = self._resolve_app_root()
        script_path = app_root / "scripts" / script_name
        if not script_path.exists():
            self.status_label.setText(f"スクリプトが見つかりません: {script_path}")
            return

        cmd = [
            "powershell",
            "-ExecutionPolicy",
            "RemoteSigned",
            "-File",
            str(script_path),
            *args,
        ]
        try:
            subprocess.run(cmd, cwd=str(app_root), check=True, capture_output=True, text=True)
            self.status_label.setText("操作が完了しました。")
        except subprocess.CalledProcessError as exc:
            message = (exc.stderr or exc.stdout or "").strip()
            if len(message) > 180:
                message = message[:180] + "..."
            self.status_label.setText(f"操作に失敗しました: {message or '詳細不明'}")

    @staticmethod
    def _resolve_app_root() -> Path:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parents[2]

    @staticmethod
    def _set_combo_value(combo: QComboBox, value: str) -> None:
        for index in range(combo.count()):
            if combo.itemData(index) == value:
                combo.setCurrentIndex(index)
                return
