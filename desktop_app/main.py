"""
AIKodAnaliz Desktop App – Entry Point

Usage:
    python -m desktop_app
  or
    python desktop_app/main.py

Requires: PyQt6, markdown, requests  (all in project venv)
"""
import sys
import os

# Ensure the project root is on PYTHONPATH so we can import desktop_app.*
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from desktop_app.styles import MAIN_STYLE
from desktop_app.api_client import ApiClient
from desktop_app.login_dialog import LoginDialog
from desktop_app.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("AIKodAnaliz")
    app.setApplicationDisplayName("AIKodAnaliz – Çoklu Proje Asistanı")

    try:
        # Apply global stylesheet
        app.setStyleSheet(MAIN_STYLE)

        # Default font
        font = QFont("Segoe UI", 11)
        font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
        app.setFont(font)

        # API client (URL may be overridden in login dialog)
        client = ApiClient("http://localhost:5000")

        # Show login dialog
        dlg = LoginDialog(client)
        dlg.setStyleSheet(MAIN_STYLE)
        if dlg.exec() != LoginDialog.DialogCode.Accepted:
            if dlg.last_error:
                QMessageBox.critical(
                    None,
                    "Uygulama Kapatılıyor",
                    f"Giriş yapılamadığı için uygulama kapatıldı.\n\nDetay:\n{dlg.last_error}",
                )
            sys.exit(1)

        user_info = dlg.user_info

        # Launch main window
        window = MainWindow(client, user_info)
        window.show()

        sys.exit(app.exec())
    except Exception as exc:
        QMessageBox.critical(
            None,
            "Başlatma Hatası",
            f"Uygulama başlatılırken beklenmeyen bir hata oluştu.\n\nDetay:\n{exc}",
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
