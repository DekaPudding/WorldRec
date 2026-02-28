from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.models.dto import RecommendationItem


class ChatPanel(QWidget):
    submit_query = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("chatPanel")

        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("AI検索機能は現在未実装です")
        self.query_input.setEnabled(False)
        self.send_button = QPushButton("検索（未実装）")
        self.send_button.setEnabled(False)
        self.clear_button = QPushButton("入力クリア")
        self.clear_button.setEnabled(False)
        self.chat_list = QListWidget()
        self.status_label = QLabel("未実装")
        self.status_label.setObjectName("chatStatusLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._loading_item: QListWidgetItem | None = None

        self.chat_list.setAlternatingRowColors(False)
        self.chat_list.setWordWrap(True)

        self.send_button.clicked.connect(self._emit_query)
        self.query_input.returnPressed.connect(self._emit_query)
        self.clear_button.clicked.connect(self._clear_query)

        QShortcut(QKeySequence("Escape"), self.query_input, activated=self._clear_query)

        input_row = QHBoxLayout()
        input_row.addWidget(self.query_input)
        input_row.addWidget(self.send_button)
        input_row.addWidget(self.clear_button)

        layout = QVBoxLayout()
        title = QLabel("AIチャット検索（未実装）")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        layout.addLayout(input_row)
        layout.addWidget(self.status_label)
        layout.addWidget(self.chat_list)
        self.setLayout(layout)
        self._append_ai_message("AI検索機能は現在準備中です。")

    def _emit_query(self) -> None:
        query = self.query_input.text().strip()
        if query:
            self._append_user_message(query)
            self.submit_query.emit(query)
            self.query_input.clear()

    def _clear_query(self) -> None:
        self.query_input.clear()
        self.query_input.setFocus()

    def set_loading(self, loading: bool) -> None:
        self.send_button.setEnabled(not loading)
        self.clear_button.setEnabled(not loading)
        self.query_input.setEnabled(not loading)
        if loading:
            self.status_label.setText("検索中...")
            self._set_loading_message("WorldRec AI", "検索中...")
        else:
            self.status_label.setText("待機中")
            self._clear_loading_message()

    def set_result(self, response_text: str, items: list[RecommendationItem]) -> None:
        self._clear_loading_message()
        lines = [response_text]
        if items:
            lines.append("")
            lines.append("候補:")
            for idx, item in enumerate(items, start=1):
                lines.append(
                    f"{idx}. {item.world_name} ({self._format_time(item.visited_at)}) - {item.reason}"
                )
        self._append_ai_message("\n".join(lines))
        self.status_label.setText(f"候補 {len(items)}件")

    def _append_user_message(self, message: str) -> None:
        item = QListWidgetItem(f"あなた:\n{message}")
        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.chat_list.addItem(item)
        self.chat_list.scrollToBottom()

    def _append_ai_message(self, message: str) -> None:
        item = QListWidgetItem(f"WorldRec AI:\n{message}")
        item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.chat_list.addItem(item)
        self.chat_list.scrollToBottom()

    def _set_loading_message(self, role: str, message: str) -> None:
        self._clear_loading_message()
        self._loading_item = QListWidgetItem(f"{role}:\n{message}")
        self._loading_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.chat_list.addItem(self._loading_item)
        self.chat_list.scrollToBottom()

    def _clear_loading_message(self) -> None:
        if self._loading_item is None:
            return
        row = self.chat_list.row(self._loading_item)
        if row >= 0:
            self.chat_list.takeItem(row)
        self._loading_item = None

    @staticmethod
    def _format_time(visited_at: str) -> str:
        try:
            return datetime.fromisoformat(visited_at).strftime("%H:%M:%S")
        except ValueError:
            return visited_at
