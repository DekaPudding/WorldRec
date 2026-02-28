from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)


@dataclass(slots=True)
class LoginInput:
    username: str
    password: str
    two_factor_code: str


class LoginDialog(QDialog):
    def __init__(
        self,
        parent=None,
        requires_two_factor: bool = False,
        default_username: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("VRChat APIログイン")
        self.setModal(True)
        self.resize(440, 260)

        self.info_label = QLabel(
            "VRChat APIの認証が必要です。ログイン情報を入力してください。"
        )
        self.username_label = QLabel("ユーザー名")
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("ユーザー名")
        self.username_edit.setText(default_username)
        self.password_label = QLabel("パスワード")
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("パスワード")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)

        self.two_factor_code_label = QLabel("2FAコード")
        self.two_factor_code = QLineEdit()
        self.two_factor_code.setPlaceholderText("メールに届いた認証コード")
        self.two_factor_code.setVisible(requires_two_factor)
        self._requires_two_factor = requires_two_factor

        form = QFormLayout()
        form.addRow(self.username_label, self.username_edit)
        form.addRow(self.password_label, self.password_edit)
        form.addRow(self.two_factor_code_label, self.two_factor_code)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(self.info_label)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.setLayout(layout)
        self._sync_two_factor_visibility()

    def set_requires_two_factor(self, required: bool) -> None:
        self._requires_two_factor = required
        self._sync_two_factor_visibility()

    def get_input(self) -> LoginInput:
        return LoginInput(
            username=self.username_edit.text().strip(),
            password=self.password_edit.text(),
            two_factor_code=self.two_factor_code.text().strip(),
        )

    def _sync_two_factor_visibility(self) -> None:
        show_two_factor = self._requires_two_factor
        self.two_factor_code_label.setVisible(show_two_factor)
        self.two_factor_code.setVisible(show_two_factor)
        self.username_label.setVisible(not show_two_factor)
        self.username_edit.setVisible(not show_two_factor)
        self.password_label.setVisible(not show_two_factor)
        self.password_edit.setVisible(not show_two_factor)
