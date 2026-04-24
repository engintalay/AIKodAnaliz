"""Login dialog for AIKodAnaliz Desktop App."""
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QSizePolicy, QMessageBox,
)
from PyQt6.QtGui import QKeyEvent

from desktop_app.api_client import ApiClient, ApiError
from desktop_app.theme_config import COLOR_ACCENT_LIGHT, COLOR_TEXT_MUTED, COLOR_TEXT_SECONDARY


class _LoginThread(QThread):
    success = pyqtSignal(dict)   # user info
    failure = pyqtSignal(str)    # error message

    def __init__(self, client: ApiClient, username: str, password: str):
        super().__init__()
        self.client = client
        self.username = username
        self.password = password

    def run(self):
        try:
            user = self.client.login(self.username, self.password)
            self.success.emit(user)
        except ApiError as e:
            self.failure.emit(str(e))
        except Exception as e:
            self.failure.emit(f"Beklenmeyen hata: {e}")


class LoginDialog(QDialog):
    """Shown at startup. Emits accepted() with user info on success."""

    def __init__(self, api_client: ApiClient, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self._user_info: dict = {}
        self._thread: _LoginThread | None = None
        self._last_error = ""
        self.close_btn: QPushButton | None = None

        self.setObjectName("loginDialog")
        self.setWindowTitle("AIKodAnaliz – Giriş")
        self.setFixedSize(540, 680)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._build_ui()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 28, 28, 28)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("loginCard")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(44, 48, 44, 40)
        card_layout.setSpacing(20)

        # Logo / icon
        icon_label = QLabel("⬡")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(
            f"font-size: 52px; color: {COLOR_ACCENT_LIGHT}; margin-bottom: 6px;"
        )
        card_layout.addWidget(icon_label)

        # Title
        title = QLabel("AIKodAnaliz")
        title.setObjectName("loginTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(title)

        subtitle = QLabel("Çoklu Proje AI Asistanı")
        subtitle.setObjectName("loginSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        card_layout.addWidget(subtitle)

        card_layout.addSpacing(12)

        # Server URL
        srv_label = QLabel("Sunucu Adresi")
        srv_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 12px;")
        card_layout.addWidget(srv_label)

        import os
        flask_host = os.getenv('FLASK_HOST', 'localhost')
        flask_port = os.getenv('FLASK_PORT', '5000')
        default_server = f"http://{flask_host}:{flask_port}"
        
        self.server_edit = QLineEdit(default_server)
        self.server_edit.setObjectName("loginServerField")
        self.server_edit.setPlaceholderText(default_server)
        self.server_edit.setMinimumHeight(52)
        card_layout.addWidget(self.server_edit)

        # Username
        user_label = QLabel("Kullanıcı Adı")
        user_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 12px;")
        card_layout.addWidget(user_label)

        self.username_edit = QLineEdit()
        self.username_edit.setObjectName("loginField")
        self.username_edit.setPlaceholderText("kullanıcı adı")
        self.username_edit.setMinimumHeight(54)
        self.username_edit.returnPressed.connect(self._attempt_login)
        card_layout.addWidget(self.username_edit)

        # Password
        pass_label = QLabel("Şifre")
        pass_label.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 12px;")
        card_layout.addWidget(pass_label)

        self.password_edit = QLineEdit()
        self.password_edit.setObjectName("loginField")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("••••••••")
        self.password_edit.setMinimumHeight(54)
        self.password_edit.returnPressed.connect(self._attempt_login)
        card_layout.addWidget(self.password_edit)

        # Error label
        self.error_label = QLabel("")
        self.error_label.setObjectName("loginError")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        card_layout.addWidget(self.error_label)

        # Login button
        self.login_btn = QPushButton("Giriş Yap")
        self.login_btn.setObjectName("loginButton")
        self.login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_btn.setMinimumHeight(56)
        self.login_btn.clicked.connect(self._attempt_login)
        card_layout.addWidget(self.login_btn)
        card_layout.addStretch(1)

        # Close button (top-right)
        close_row = QHBoxLayout()
        close_row.addStretch()
        self.close_btn = QPushButton("✕")
        self.close_btn.setStyleSheet(
            f"background: transparent; border: none; color: {COLOR_TEXT_MUTED}; font-size: 16px;"
        )
        self.close_btn.setFixedSize(32, 32)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.reject)
        close_row.addWidget(self.close_btn)

        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addLayout(close_row)
        outer_layout.addWidget(card)

        outer.addLayout(outer_layout)

    # ------------------------------------------------------------------
    # Drag to move (frameless)
    # ------------------------------------------------------------------

    def _drag_offset(self):
        return getattr(self, "_drag_pos", None)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_offset():
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    # ------------------------------------------------------------------
    # Login logic
    # ------------------------------------------------------------------

    @property
    def user_info(self) -> dict:
        return self._user_info

    @property
    def last_error(self) -> str:
        return self._last_error

    def _attempt_login(self):
        server_url = self.server_edit.text().strip() or "http://localhost:5000"
        username = self.username_edit.text().strip()
        password = self.password_edit.text()

        if not username:
            self._show_error("Kullanıcı adı boş olamaz.")
            return
        if not password:
            self._show_error("Şifre boş olamaz.")
            return

        self.api_client.base_url = server_url.rstrip("/")

        self._last_error = ""
        self._set_loading(True)
        self.error_label.hide()

        self._thread = _LoginThread(self.api_client, username, password)
        self._thread.success.connect(self._on_login_success)
        self._thread.failure.connect(self._on_login_failure)
        self._thread.start()

    def _on_login_success(self, user: dict):
        self._user_info = user
        self._last_error = ""
        self._set_loading(False)
        self.accept()

    def _on_login_failure(self, error: str):
        self._set_loading(False)
        self._show_error(error)
        self._show_error_dialog(error)

    def _show_error(self, msg: str):
        self._last_error = msg
        self.error_label.setText(msg)
        self.error_label.show()

    def _show_error_dialog(self, msg: str):
        QMessageBox.critical(
            self,
            "Giriş Başarısız",
            f"Sunucuya giriş yapılamadı.\n\nDetay:\n{msg}",
        )

    def _set_loading(self, loading: bool):
        self.login_btn.setEnabled(not loading)
        self.username_edit.setEnabled(not loading)
        self.password_edit.setEnabled(not loading)
        self.server_edit.setEnabled(not loading)
        if self.close_btn:
            self.close_btn.setEnabled(not loading)
        if loading:
            self.login_btn.setText("Giriş yapılıyor...")
        else:
            self.login_btn.setText("Giriş Yap")

    def reject(self):
        if self._thread and self._thread.isRunning():
            self._show_error("Giriş işlemi devam ediyor. Lütfen sonucu bekleyin.")
            return
        super().reject()

    def closeEvent(self, event):
        if self._thread and self._thread.isRunning():
            self._show_error("Giriş işlemi devam ediyor. Lütfen sonucu bekleyin.")
            event.ignore()
            return
        super().closeEvent(event)
