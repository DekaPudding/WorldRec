from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.instance_access_type import to_display_access_type
from app.core.tag_utils import normalize_tag_string, split_tags
from app.models.world_detail_dto import WorldDetail


class WorldDetailDialog(QDialog):
    note_save_requested = Signal(str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("ワールド詳細")
        self.setModal(True)
        self.resize(820, 700)

        self.world_name_value = QLabel("-")
        self.visit_count_value = QLabel("-")
        self.instance_access_type_value = QLabel("-")
        self.capacity_value = QLabel("-")
        self.platforms_value = QLabel("-")
        for value_label in (
            self.world_name_value,
            self.visit_count_value,
            self.instance_access_type_value,
            self.capacity_value,
            self.platforms_value,
        ):
            value_label.setObjectName("detailValueLabel")

        self.description_value = QTextEdit()
        self.description_value.setReadOnly(True)
        description_three_line_height = (
            self.description_value.fontMetrics().lineSpacing() * 3
            + self.description_value.frameWidth() * 2
            + 12
        )
        self.description_value.setFixedHeight(description_three_line_height)
        self.description_value.setObjectName("detailTextArea")

        self.thumbnail_label = QLabel("サムネイル未取得")
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setMinimumSize(340, 200)
        self.thumbnail_label.setObjectName("thumbnailLabel")
        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("タグ（カンマ区切り） 例: 雑談, 夜")
        self.tag_chip_label = QLabel("タグ: なし")
        self.tag_chip_label.setObjectName("tagChipLabel")
        self.memo_input = QTextEdit()
        self.memo_input.setPlaceholderText("メモを入力")
        self.memo_input.setMinimumHeight(72)
        self.memo_input.setMaximumHeight(120)
        self.memo_input.setObjectName("detailTextArea")
        self.note_save_button = QPushButton("メモ/タグを保存")
        self.note_status_label = QLabel("")
        self.note_status_label.setObjectName("noteStatusLabel")
        self.note_save_button.clicked.connect(self._on_note_save_clicked)

        info_section = QFrame()
        info_section.setObjectName("detailCard")
        self.info_notice_label = QLabel("")
        self.info_notice_label.setObjectName("detailInfoNotice")
        self.info_notice_label.hide()
        self.info_content_widget = QWidget()
        info_form = QFormLayout()
        info_form.addRow("ワールド名", self.world_name_value)
        info_form.addRow("総訪問回数", self.visit_count_value)
        info_form.addRow("インスタンスタイプ", self.instance_access_type_value)
        info_form.addRow("ワールド容量", self.capacity_value)
        info_form.addRow("対応Platform", self.platforms_value)
        self.info_content_widget.setLayout(info_form)
        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(8)
        info_layout.addWidget(self.info_notice_label)
        info_layout.addWidget(self.info_content_widget)
        info_section.setLayout(info_layout)

        desc_title = QLabel("説明")
        desc_title.setObjectName("detailSectionTitle")
        note_title = QLabel("メモ / タグ")
        note_title.setObjectName("detailSectionTitle")

        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        left_top = QVBoxLayout()
        left_top.setSpacing(10)
        left_top.addWidget(info_section)

        top_row.addLayout(left_top, 3)
        top_row.addWidget(self.thumbnail_label, 2)

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.addLayout(top_row)
        layout.addWidget(desc_title)
        layout.addWidget(self.description_value)
        layout.addWidget(note_title)
        layout.addWidget(self.tags_input)
        layout.addWidget(self.tag_chip_label)
        layout.addWidget(self.memo_input)
        note_button_row = QHBoxLayout()
        note_button_row.addStretch(1)
        note_button_row.addWidget(self.note_save_button)
        layout.addLayout(note_button_row)
        layout.addWidget(self.note_status_label)
        self.setLayout(layout)
        self._apply_styles()

    def set_loading(
        self,
        world_name: str,
        visit_count: int | None,
        instance_access_type: str | None = None,
    ) -> None:
        self.info_content_widget.hide()
        self.info_notice_label.show()
        self.info_notice_label.setText("ワールド詳細を取得中...")
        self.world_name_value.setText(world_name or "不明")
        self.visit_count_value.setText("-" if visit_count is None else str(visit_count))
        self.instance_access_type_value.setText(
            to_display_access_type(instance_access_type) if instance_access_type else "不明"
        )
        self.capacity_value.setText("取得中...")
        self.platforms_value.setText("取得中...")
        self.description_value.setPlainText("取得中...")
        self.thumbnail_label.setPixmap(QPixmap())
        self.thumbnail_label.setText("サムネイル取得中...")

    def set_detail(
        self,
        detail: WorldDetail,
        visit_count: int | None,
        instance_access_type: str | None = None,
        warning_message: str | None = None,
    ) -> None:
        self.info_content_widget.show()
        self.world_name_value.setText(detail.world_name or "不明")
        self.visit_count_value.setText("-" if visit_count is None else str(visit_count))
        self.instance_access_type_value.setText(to_display_access_type(instance_access_type))
        self.capacity_value.setText(self._format_capacity(detail.capacity_bytes))
        self.platforms_value.setText(self._format_platforms(detail.platforms))
        self.description_value.setPlainText(detail.description or "取得できませんでした")
        self._set_thumbnail(detail.thumbnail_bytes)

        if warning_message:
            self.info_notice_label.show()
            self.info_notice_label.setText(
                "ワールド詳細の取得に失敗しました。取得できた情報のみ表示しています。"
            )
        else:
            self.info_notice_label.hide()

    def set_note_values(self, memo: str | None, tags: str | None) -> None:
        normalized_tags = normalize_tag_string(tags) or ""
        self.tags_input.setText(normalized_tags)
        self.memo_input.setPlainText(memo or "")
        self._refresh_tag_chips(normalized_tags)
        self.note_status_label.setText("")

    def _set_thumbnail(self, image_bytes: bytes | None) -> None:
        if not image_bytes:
            self.thumbnail_label.setPixmap(QPixmap())
            self.thumbnail_label.setText("取得できませんでした")
            return

        pixmap = QPixmap()
        if not pixmap.loadFromData(image_bytes):
            self.thumbnail_label.setPixmap(QPixmap())
            self.thumbnail_label.setText("取得できませんでした")
            return

        scaled = pixmap.scaled(
            self.thumbnail_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.thumbnail_label.setText("")
        self.thumbnail_label.setPixmap(scaled)

    @staticmethod
    def _format_capacity(capacity_bytes: int | None) -> str:
        if capacity_bytes is None:
            return "不明"
        value = float(capacity_bytes)
        units = ["B", "KB", "MB", "GB", "TB"]
        for unit in units:
            if value < 1024.0 or unit == units[-1]:
                return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
            value /= 1024.0
        return "不明"

    @staticmethod
    def _format_platforms(platforms: list[str] | None) -> str:
        if not platforms:
            return "不明"
        return ", ".join(platforms)

    def _on_note_save_clicked(self) -> None:
        normalized_tags = normalize_tag_string(self.tags_input.text()) or ""
        self.tags_input.setText(normalized_tags)
        self._refresh_tag_chips(normalized_tags)
        self.note_status_label.setText("メモ/タグを保存中...")
        self.note_save_requested.emit(self.memo_input.toPlainText(), normalized_tags)

    def notify_note_saved(self, message: str) -> None:
        self.note_status_label.setText(message)

    def _refresh_tag_chips(self, tags_text: str | None) -> None:
        tags = split_tags(tags_text)
        if not tags:
            self.tag_chip_label.setText("タグ: なし")
            return
        chips = " ".join(f"[{tag}]" for tag in tags[:6])
        suffix = " ..." if len(tags) > 6 else ""
        self.tag_chip_label.setText(f"タグ: {chips}{suffix}")

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QDialog {
                background-color: #0f1622;
            }
            QFrame#detailCard {
                background-color: #172334;
                border: 1px solid #2d4363;
                border-radius: 10px;
                padding: 8px;
            }
            QLabel#detailInfoNotice {
                color: #d7e8ff;
                padding: 2px 2px 6px 2px;
                font-weight: 700;
            }
            QLabel#detailValueLabel {
                color: #e5f0ff;
                font-weight: 600;
            }
            QLabel#detailSectionTitle {
                color: #9fc8ff;
                font-size: 13px;
                font-weight: 700;
                padding-top: 4px;
            }
            QLabel#thumbnailLabel {
                border: 1px solid #31425b;
                border-radius: 8px;
                background-color: #101721;
                color: #9bb0cf;
                padding: 6px;
            }
            QTextEdit#detailTextArea, QLineEdit {
                border: 1px solid #3a4a62;
                border-radius: 8px;
                padding: 6px 8px;
                background: #121a26;
                color: #dce7fa;
            }
            QLabel#tagChipLabel {
                color: #bcd3f5;
                background-color: #18273a;
                border: 1px solid #2c4465;
                border-radius: 8px;
                padding: 6px 8px;
            }
            QLabel#noteStatusLabel {
                color: #8fb9ff;
                font-weight: 600;
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
            """
        )
