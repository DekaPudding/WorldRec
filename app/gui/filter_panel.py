from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QDate, QDateTime, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCalendarWidget,
    QComboBox,
    QDateTimeEdit,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.core.instance_access_type import get_access_type_options, normalize_access_type_query


class FilterPanel(QWidget):
    apply_single_date = Signal(object)
    apply_range = Signal(object, object)
    clear_clicked = Signal()
    today_clicked = Signal()
    yesterday_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("filterPanel")

        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.calendar.setMinimumHeight(230)
        self.calendar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.title_label = QLabel("履歴の絞り込み")
        self.title_label.setObjectName("filterTitleLabel")
        self.description_label = QLabel("表示する日時範囲を指定します")
        self.description_label.setObjectName("filterDescriptionLabel")

        self.start_edit = QDateTimeEdit()
        self.start_edit.setCalendarPopup(True)
        self.start_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self._unset_datetime = QDateTime(2000, 1, 1, 0, 0, 0)
        self.start_edit.setMinimumDateTime(self._unset_datetime)
        self.start_edit.setSpecialValueText("未指定")
        self.start_edit.setDateTime(self._unset_datetime)

        self.end_edit = QDateTimeEdit()
        self.end_edit.setCalendarPopup(True)
        self.end_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.end_edit.setMinimumDateTime(self._unset_datetime)
        self.end_edit.setSpecialValueText("未指定")
        self.end_edit.setDateTime(self._unset_datetime)
        self.start_label = QLabel("開始日時 [期間のみ]")
        self.start_label.setObjectName("filterFieldLabel")
        self.end_label = QLabel("終了日時 [期間のみ]")
        self.end_label.setObjectName("filterFieldLabel")

        self.world_name_input = QLineEdit()
        self.world_name_input.setPlaceholderText("ワールド名を含む")
        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("タグ（カンマ区切り）")
        self.access_type_combo = QComboBox()
        for label, value in get_access_type_options():
            self.access_type_combo.addItem(label, value)

        self.state_label = QLabel("絞り込み: 全件")
        self.state_label.setObjectName("filterStateLabel")
        self.mode_hint_label = QLabel("ヒント: カレンダーはダブルクリックで即反映")
        self.mode_hint_label.setObjectName("filterHintLabel")
        self.error_label = QLabel("")
        self.error_label.setObjectName("filterErrorLabel")

        self.single_mode_radio = QRadioButton("単日")
        self.range_mode_radio = QRadioButton("期間")
        self.single_mode_radio.setChecked(True)

        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.single_mode_radio)
        self.mode_group.addButton(self.range_mode_radio)
        self.single_mode_radio.toggled.connect(self._update_mode_state)

        self.apply_button = QPushButton("適用")
        self.clear_button = QPushButton("クリア")
        self.today_button = QPushButton("今日")
        self.yesterday_button = QPushButton("昨日")

        self.apply_button.clicked.connect(self._on_apply)
        self.clear_button.clicked.connect(self.clear_clicked.emit)
        self.today_button.clicked.connect(self.today_clicked.emit)
        self.yesterday_button.clicked.connect(self.yesterday_clicked.emit)
        self.calendar.activated.connect(self._on_calendar_activated)

        form = QFormLayout()
        form.addRow(self.start_label, self.start_edit)
        form.addRow(self.end_label, self.end_edit)
        form.addRow("ワールド名", self.world_name_input)
        form.addRow("タグ", self.tags_input)
        form.addRow("インスタンスタイプ", self.access_type_combo)

        mode_title = QLabel("絞り込み方法")
        mode_title.setObjectName("filterSubTitleLabel")

        mode_row = QHBoxLayout()
        mode_row.addWidget(self.single_mode_radio)
        mode_row.addWidget(self.range_mode_radio)
        mode_row.addStretch(1)

        buttons = QHBoxLayout()
        buttons.addWidget(self.today_button)
        buttons.addWidget(self.yesterday_button)
        buttons.addWidget(self.apply_button)
        buttons.addWidget(self.clear_button)

        layout = QVBoxLayout()
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.addWidget(self.title_label)
        layout.addWidget(self.description_label)
        layout.addWidget(self.state_label)
        layout.addWidget(mode_title)
        layout.addLayout(mode_row)
        layout.addWidget(self.calendar)
        layout.addLayout(form)
        layout.addLayout(buttons)
        layout.addWidget(self.mode_hint_label)
        layout.addWidget(self.error_label)
        self.setLayout(layout)
        self._update_mode_state()

    def _on_apply(self) -> None:
        self.error_label.setText("")
        selected_date = self.calendar.selectedDate()
        start_dt = self._read_optional_datetime(self.start_edit)
        end_dt = self._read_optional_datetime(self.end_edit)

        if self.single_mode_radio.isChecked():
            self.apply_single_date.emit(selected_date.toPython())
            return

        self.apply_range.emit(start_dt, end_dt)

    def _on_calendar_activated(self, selected_date: QDate) -> None:
        self.error_label.setText("")
        self.apply_single_date.emit(selected_date.toPython())

    def _read_optional_datetime(self, dt_edit: QDateTimeEdit) -> datetime | None:
        dt = dt_edit.dateTime()
        if dt == self._unset_datetime:
            return None
        return dt.toPython()

    def _update_mode_state(self) -> None:
        range_enabled = self.range_mode_radio.isChecked()
        self.start_edit.setEnabled(range_enabled)
        self.end_edit.setEnabled(range_enabled)
        self.start_label.setEnabled(range_enabled)
        self.end_label.setEnabled(range_enabled)
        self.calendar.setEnabled(not range_enabled)
        if range_enabled:
            self.mode_hint_label.setText("ヒント: 開始/終了を未指定にすると片側のみ絞り込みできます")
        else:
            self.mode_hint_label.setText("ヒント: カレンダーはダブルクリックで即反映")

    def set_filter_state(self, text: str) -> None:
        self.state_label.setText(f"絞り込み: {text}")

    def set_error(self, text: str) -> None:
        self.error_label.setText(text)

    def clear_error(self) -> None:
        self.error_label.setText("")

    def set_single_date(self, target: datetime) -> None:
        self.calendar.setSelectedDate(QDate(target.year, target.month, target.day))

    def get_extra_filters(self) -> tuple[str | None, str | None, str | None]:
        world_name = self.world_name_input.text().strip() or None
        tags = self.tags_input.text().strip() or None
        access_type = normalize_access_type_query(self.access_type_combo.currentData())
        return (world_name, tags, access_type)

    def clear_extra_filters(self) -> None:
        self.world_name_input.clear()
        self.tags_input.clear()
        self.access_type_combo.setCurrentIndex(0)
