"""Chat message widgets and the main chat area."""
import datetime
import re

import markdown as md_lib

from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QTextOption, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextBrowser,
    QScrollArea, QFrame, QSizePolicy,
)

from desktop_app.styles import MESSAGE_HTML_STYLE, C_ACCENT_LIGHT, C_TEXT_MUTED


def _now_str() -> str:
    return datetime.datetime.now().strftime("%H:%M")


def _md_to_html(text: str) -> str:
    """Convert markdown text to HTML string (body only)."""
    extensions = ["fenced_code", "tables", "nl2br", "sane_lists"]
    try:
        converter = md_lib.Markdown(extensions=extensions)
        html = converter.convert(text)
        return html
    except Exception:
        # Fallback: plain text with line breaks
        safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f"<pre style='white-space:pre-wrap'>{safe}</pre>"


class _AdaptiveTextBrowser(QTextBrowser):
    """A QTextBrowser that resizes to fit its content (no internal scrollbar)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setOpenExternalLinks(True)
        self.setReadOnly(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.document().setDocumentMargin(0)
        self.document().contentsChanged.connect(self._refit)

    def _refit(self):
        h = int(self.document().size().height()) + 4
        self.setFixedHeight(max(h, 20))

    def sizeHint(self) -> QSize:
        h = int(self.document().size().height()) + 4
        return QSize(self.width(), max(h, 20))


# ─────────────────────────────────────────────────────────────
# User message widget
# ─────────────────────────────────────────────────────────────

class UserMessageWidget(QWidget):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self._build(text)

    def _build(self, text: str):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(60, 4, 12, 4)
        outer.setSpacing(8)
        outer.addStretch()

        bubble = QFrame()
        bubble.setObjectName("userBubble")
        b_layout = QVBoxLayout(bubble)
        b_layout.setContentsMargins(14, 10, 14, 10)
        b_layout.setSpacing(4)

        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        lbl.setStyleSheet("color: #E2E8F0; font-size: 13px;")
        b_layout.addWidget(lbl)

        time_lbl = QLabel(_now_str())
        time_lbl.setObjectName("messageTime")
        time_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        b_layout.addWidget(time_lbl)

        outer.addWidget(bubble)

        # Avatar
        avatar = QLabel("U")
        avatar.setObjectName("userAvatarLabel")
        avatar.setFixedSize(28, 28)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(avatar, 0, Qt.AlignmentFlag.AlignTop)


# ─────────────────────────────────────────────────────────────
# AI message widget
# ─────────────────────────────────────────────────────────────

class AIMessageWidget(QWidget):
    def __init__(self, project_name: str = "", parent=None):
        super().__init__(parent)
        self._raw_text = ""
        self._project_name = project_name
        self._build()

    def _build(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(12, 4, 60, 4)
        outer.setSpacing(8)

        # Avatar
        avatar = QLabel("AI")
        avatar.setObjectName("aiAvatarLabel")
        avatar.setFixedSize(28, 28)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(avatar, 0, Qt.AlignmentFlag.AlignTop)

        # Bubble
        self._bubble = QFrame()
        self._bubble.setObjectName("aiBubble")
        b_layout = QVBoxLayout(self._bubble)
        b_layout.setContentsMargins(14, 10, 14, 10)
        b_layout.setSpacing(6)

        # Project tag + time row
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)

        if self._project_name:
            proj_tag = QLabel(f"📁 {self._project_name}")
            proj_tag.setObjectName("aiProjectTag")
            top_row.addWidget(proj_tag)

        top_row.addStretch()

        self._time_lbl = QLabel(_now_str())
        self._time_lbl.setObjectName("messageTime")
        top_row.addWidget(self._time_lbl)

        b_layout.addLayout(top_row)

        # Content browser (adaptive height)
        self._browser = _AdaptiveTextBrowser()
        self._browser.setStyleSheet(
            "background: transparent; border: none;"
            "color: #E2E8F0; font-size: 13px;"
        )
        b_layout.addWidget(self._browser)

        outer.addWidget(self._bubble)
        outer.addStretch()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def append_chunk(self, chunk: str):
        """Append a streaming token chunk and refresh the display."""
        self._raw_text += chunk
        self._refresh()

    def set_text(self, text: str):
        self._raw_text = text
        self._refresh()

    def _refresh(self):
        html_body = _md_to_html(self._raw_text)
        full_html = MESSAGE_HTML_STYLE + html_body
        self._browser.setHtml(full_html)

    def set_project_name(self, name: str):
        self._project_name = name

    def finalize(self):
        """Called when streaming is complete – nothing extra needed currently."""
        pass


# ─────────────────────────────────────────────────────────────
# System / status message widget
# ─────────────────────────────────────────────────────────────

class SysMessageWidget(QWidget):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 2, 12, 2)
        layout.addStretch()
        lbl = QLabel(text)
        lbl.setObjectName("sysMessageLabel")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)
        layout.addStretch()


# ─────────────────────────────────────────────────────────────
# Typing indicator
# ─────────────────────────────────────────────────────────────

class TypingIndicator(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(50, 4, 60, 4)
        layout.setSpacing(4)

        avatar = QLabel("AI")
        avatar.setObjectName("aiAvatarLabel")
        avatar.setFixedSize(28, 28)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(avatar, 0, Qt.AlignmentFlag.AlignVCenter)

        self._lbl = QLabel("● ● ●")
        self._lbl.setObjectName("typingIndicator")
        layout.addWidget(self._lbl)
        layout.addStretch()

        self._dots = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(500)

    def _tick(self):
        patterns = ["●  ·  ·", "·  ●  ·", "·  ·  ●", "●  ●  ·", "·  ●  ●", "●  ●  ●"]
        self._dots = (self._dots + 1) % len(patterns)
        self._lbl.setText(patterns[self._dots])

    def stop(self):
        self._timer.stop()


# ─────────────────────────────────────────────────────────────
# Chat Area (scroll container)
# ─────────────────────────────────────────────────────────────

class ChatArea(QScrollArea):
    """Scrollable container holding all message widgets."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("chatScrollArea")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self._container = QWidget()
        self._container.setObjectName("chatArea")
        self._layout = QVBoxLayout(self._container)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._layout.setSpacing(6)
        self._layout.setContentsMargins(8, 16, 8, 16)

        self.setWidget(self._container)

        self._typing_widget: TypingIndicator | None = None
        self._active_ai_widget: AIMessageWidget | None = None

        self._show_welcome()

    # ------------------------------------------------------------------
    # Welcome / empty state
    # ------------------------------------------------------------------

    def _show_welcome(self):
        w = QWidget()
        w.setObjectName("welcomeWidget")
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(12)
        lay.setContentsMargins(40, 60, 40, 60)

        icon = QLabel("⬡")
        icon.setStyleSheet("font-size: 52px; color: #7C3AED;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(icon)

        title = QLabel("Tüm Projeler AI Asistanı")
        title.setObjectName("welcomeTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title)

        subtitle = QLabel(
            "Sorularınızı yazın — hangi projeden cevaplayacağına otomatik karar verir."
        )
        subtitle.setObjectName("welcomeSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        lay.addWidget(subtitle)

        hint = QLabel("Örnek: \"Kullanıcı girişi nasıl çalışıyor?\" veya \"Rapor nasıl oluşturuluyor?\"")
        hint.setObjectName("welcomeHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        lay.addWidget(hint)

        self._layout.addWidget(w)
        self._welcome_widget = w

    def _remove_welcome(self):
        if hasattr(self, "_welcome_widget") and self._welcome_widget:
            self._layout.removeWidget(self._welcome_widget)
            self._welcome_widget.deleteLater()
            self._welcome_widget = None

    # ------------------------------------------------------------------
    # Message API
    # ------------------------------------------------------------------

    def add_user_message(self, text: str):
        self._remove_welcome()
        msg = UserMessageWidget(text, self._container)
        self._layout.addWidget(msg)
        self._scroll_to_bottom()

    def add_sys_message(self, text: str):
        msg = SysMessageWidget(text, self._container)
        self._layout.addWidget(msg)
        self._scroll_to_bottom()

    def start_ai_message(self, project_name: str = "") -> AIMessageWidget:
        """Show typing indicator and return the AI widget that will receive text."""
        self._remove_welcome()
        self._stop_typing()

        widget = AIMessageWidget(project_name, self._container)
        self._layout.addWidget(widget)
        self._active_ai_widget = widget
        self._start_typing()
        self._scroll_to_bottom()
        return widget

    def show_typing(self):
        self._start_typing()

    def hide_typing(self):
        self._stop_typing()

    def _start_typing(self):
        if self._typing_widget is None:
            self._typing_widget = TypingIndicator(self._container)
            self._layout.addWidget(self._typing_widget)
            self._scroll_to_bottom()

    def _stop_typing(self):
        if self._typing_widget is not None:
            self._typing_widget.stop()
            self._layout.removeWidget(self._typing_widget)
            self._typing_widget.deleteLater()
            self._typing_widget = None

    def get_active_ai_widget(self) -> AIMessageWidget | None:
        return self._active_ai_widget

    def finalize_ai_message(self):
        self._stop_typing()
        if self._active_ai_widget:
            self._active_ai_widget.finalize()
            self._active_ai_widget = None
        self._scroll_to_bottom()

    def clear_messages(self):
        # Remove all children except the welcome widget setup
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._typing_widget = None
        self._active_ai_widget = None
        self._show_welcome()

    def _scroll_to_bottom(self):
        QTimer.singleShot(50, lambda: self.verticalScrollBar().setValue(
            self.verticalScrollBar().maximum()
        ))
