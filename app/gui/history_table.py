from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.instance_access_type import to_display_access_type
from app.models.entities import VisitHistory


class HistoryTable(QWidget):
    history_double_clicked = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("historyPanel")
        self._histories: list[VisitHistory] = []

        self.title_label = QLabel("今日の訪問ワールド")
        self.title_label.setObjectName("sectionTitle")

        self.summary_label = QLabel("0件")
        self.summary_label.setObjectName("summaryLabel")

        self.empty_label = QLabel("該当履歴なし")
        self.empty_label.setObjectName("emptyStateLabel")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.hide()

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["時刻", "ワールド名", "インスタンスタイプ"])
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(False)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        layout = QVBoxLayout()
        layout.addWidget(self.title_label)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.empty_label)
        self.setLayout(layout)

    def set_rows(self, histories: list[VisitHistory]) -> None:
        self._histories = histories
        self.table.setRowCount(len(histories))
        for row, history in enumerate(histories):
            self.table.setItem(row, 0, QTableWidgetItem(self._format_time(history.visited_at)))
            self.table.setItem(row, 1, QTableWidgetItem(history.world_name))
            self.table.setItem(
                row,
                2,
                QTableWidgetItem(to_display_access_type(history.instance_access_type)),
            )

        self.summary_label.setText(f"{len(histories)}件")
        if histories:
            self.empty_label.hide()
        else:
            self.empty_label.show()

    def set_title(self, text: str) -> None:
        self.title_label.setText(text)

    def _on_cell_double_clicked(self, row: int, _column: int) -> None:
        if row < 0 or row >= len(self._histories):
            return
        self.history_double_clicked.emit(self._histories[row])

    @staticmethod
    def _format_time(visited_at: str) -> str:
        try:
            dt = datetime.fromisoformat(visited_at)
            return dt.strftime("%H:%M:%S")
        except ValueError:
            return visited_at
