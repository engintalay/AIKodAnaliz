"""Main application window for AIKodAnaliz Desktop App."""
from PyQt6.QtCore import Qt, QTimer, QPoint, pyqtSlot
from PyQt6.QtGui import QKeyEvent, QIcon
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QListWidget,
    QListWidgetItem, QTextEdit, QFrame, QSizePolicy,
    QSplitter, QScrollArea, QMessageBox, QFileDialog,
)

from desktop_app.api_client import ApiClient
from desktop_app.chat_widgets import ChatArea
from desktop_app.workers import ProjectRouterThread, ChatStreamThread, ProjectListThread
from desktop_app.export_import_ui import ExportThread, ImportThread
from desktop_app.styles import (
    C_GREEN, C_RED, C_ORANGE, C_TEXT_MUTED, C_ACCENT_LIGHT
)


class MainWindow(QMainWindow):
    """Primary application window.

    Layout:
        ┌────────────────────────────────────────────────────┐
        │  TitleBar (drag to move, connection status)        │
        ├──────────────┬─────────────────────────────────────┤
        │              │                                     │
        │   Sidebar    │          Chat Area                  │
        │  (projects)  │                                     │
        │              ├─────────────────────────────────────┤
        │              │  Input (QTextEdit + Send button)    │
        └──────────────┴─────────────────────────────────────┘
    """

    def __init__(self, client: ApiClient, user_info: dict):
        super().__init__()
        self._client = client
        self._user_info = user_info
        self._projects: list = []
        self._history: list = []   # [{role, content}, ...]
        self._current_project: dict | None = None
        self._ai_widget = None
        self._stream_thread: ChatStreamThread | None = None
        self._router_thread: ProjectRouterThread | None = None
        self._drag_pos: QPoint | None = None

        self.setWindowTitle("AIKodAnaliz – Çoklu Proje Asistanı")
        self.setMinimumSize(900, 650)
        self.resize(1160, 780)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        self._build_ui()
        self._load_projects()

    # ==================================================================
    # UI Construction
    # ==================================================================

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("mainWidget")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Title bar
        root.addWidget(self._make_title_bar())

        # Body: splitter (sidebar | chat)
        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        body_layout.addWidget(self._make_sidebar(), 0)
        body_layout.addWidget(self._make_chat_panel(), 1)

        root.addWidget(body)

    # ------------------------------------------------------------------
    # Title bar
    # ------------------------------------------------------------------

    def _make_title_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("titleBar")
        bar.setFixedHeight(48)

        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 0, 12, 0)
        lay.setSpacing(10)

        # Logo
        logo = QLabel("⬡")
        logo.setStyleSheet("font-size: 18px; color: #9D5FFF;")
        lay.addWidget(logo)

        # App name
        title = QLabel("AIKodAnaliz")
        title.setObjectName("titleLabel")
        lay.addWidget(title)

        # Connection status
        self._status_lbl = QLabel("● Bağlanıyor...")
        self._status_lbl.setObjectName("statusIndicator")
        lay.addWidget(self._status_lbl)

        lay.addStretch()

        # User name
        username = self._user_info.get("username", "")
        if username:
            usr_lbl = QLabel(f"👤 {username}")
            usr_lbl.setStyleSheet(f"color: {C_TEXT_MUTED}; font-size: 11px;")
            lay.addWidget(usr_lbl)

        # Refresh button
        refresh_btn = QPushButton("⟳ Yenile")
        refresh_btn.setObjectName("refreshButton")
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setToolTip("Proje listesini güncelle")
        refresh_btn.clicked.connect(self._load_projects)
        lay.addWidget(refresh_btn)

        # Window controls
        for label, slot, color in [
            ("─", self.showMinimized, "#94A3B8"),
            ("⬜", self._toggle_maximize, "#94A3B8"),
            ("✕", self.close, "#EF4444"),
        ]:
            btn = QPushButton(label)
            btn.setFixedSize(32, 32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton {{background:transparent; border:none; color:{color}; font-size:13px;}}"
                f"QPushButton:hover {{background:#30363D; border-radius:6px;}}"
            )
            btn.clicked.connect(slot)
            lay.addWidget(btn)

        # Enable drag-to-move via title bar
        bar.mousePressEvent = self._title_bar_press
        bar.mouseMoveEvent = self._title_bar_move
        bar.mouseReleaseEvent = self._title_bar_release

        return bar

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def _title_bar_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def _title_bar_move(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def _title_bar_release(self, event):
        self._drag_pos = None

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------

    def _make_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(260)

        lay = QVBoxLayout(sidebar)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Header
        hdr = QWidget()
        hdr.setStyleSheet("background: transparent;")
        hdr_lay = QVBoxLayout(hdr)
        hdr_lay.setContentsMargins(16, 14, 16, 10)
        hdr_lay.setSpacing(8)

        proj_title = QLabel("PROJELER")
        proj_title.setObjectName("sidebarTitle")
        hdr_lay.addWidget(proj_title)

        # Search filter
        self._search_edit = QLineEdit()
        self._search_edit.setObjectName("serverUrlEdit")
        self._search_edit.setPlaceholderText("🔍  Proje filtrele...")
        self._search_edit.textChanged.connect(self._filter_projects)
        hdr_lay.addWidget(self._search_edit)

        lay.addWidget(hdr)

        # Project list
        self._project_list = QListWidget()
        self._project_list.setObjectName("projectList")
        self._project_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._project_list.itemClicked.connect(self._on_project_clicked)
        lay.addWidget(self._project_list, 1)

        # Footer
        footer = QWidget()
        footer.setStyleSheet(
            "background: transparent; border-top: 1px solid #30363D;"
        )
        foot_lay = QVBoxLayout(footer)
        foot_lay.setContentsMargins(12, 10, 12, 12)
        foot_lay.setSpacing(6)

        self._server_url_lbl = QLabel(self._client.base_url)
        self._server_url_lbl.setStyleSheet(
            f"color: {C_TEXT_MUTED}; font-size: 10px;"
        )
        self._server_url_lbl.setWordWrap(True)
        foot_lay.addWidget(self._server_url_lbl)

        # Server URL editable
        self._server_edit = QLineEdit(self._client.base_url)
        self._server_edit.setObjectName("serverUrlEdit")
        self._server_edit.setPlaceholderText("http://localhost:5000")
        self._server_edit.setToolTip("Sunucu adresini değiştirmek için düzenle")
        self._server_edit.returnPressed.connect(self._change_server)
        foot_lay.addWidget(self._server_edit)

        # Export / Import buttons
        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(6)

        export_btn = QPushButton("📤 Dışa Aktar")
        export_btn.setObjectName("exportButton")
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.setToolTip("Seçili projeyi dışa aktar")
        export_btn.clicked.connect(self._on_export_clicked)
        buttons_row.addWidget(export_btn)

        import_btn = QPushButton("📥 İçe Aktar")
        import_btn.setObjectName("importButton")
        import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        import_btn.setToolTip("Proje dosyasını içe aktar")
        import_btn.clicked.connect(self._on_import_clicked)
        buttons_row.addWidget(import_btn)

        foot_lay.addLayout(buttons_row)

        lay.addWidget(footer)

        return sidebar

    def _filter_projects(self, text: str):
        q = text.strip().lower()
        for i in range(self._project_list.count()):
            item = self._project_list.item(i)
            item.setHidden(q not in item.text().lower())

    def _on_project_clicked(self, item: QListWidgetItem):
        proj_id = item.data(Qt.ItemDataRole.UserRole)
        for p in self._projects:
            if p["id"] == proj_id:
                self._current_project = p
                self._add_sys_message(
                    f"📁 Proje değiştirildi: {p['name']} — sonraki sorular bu proje üzerinden yanıtlanacak."
                )
                break

    # ------------------------------------------------------------------
    # Chat panel
    # ------------------------------------------------------------------

    def _make_chat_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("chatPanel")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Chat area
        self._chat_area = ChatArea()
        lay.addWidget(self._chat_area, 1)

        # Input area
        lay.addWidget(self._make_input_area())

        return panel

    def _make_input_area(self) -> QWidget:
        area = QFrame()
        area.setObjectName("inputArea")

        outer = QVBoxLayout(area)
        outer.setContentsMargins(12, 10, 12, 12)
        outer.setSpacing(6)

        # Optional: refs bar (hidden by default)
        self._refs_bar = QLabel("")
        self._refs_bar.setStyleSheet(
            f"color: {C_ACCENT_LIGHT}; font-size: 10px; padding: 2px 4px;"
        )
        self._refs_bar.setWordWrap(True)
        self._refs_bar.hide()
        outer.addWidget(self._refs_bar)

        # Input row
        row = QHBoxLayout()
        row.setSpacing(8)

        self._input = QTextEdit()
        self._input.setObjectName("messageInput")
        self._input.setPlaceholderText("Sorunuzu yazın…  (Enter = gönder,  Shift+Enter = yeni satır)")
        self._input.setFixedHeight(82)
        self._input.setAcceptRichText(False)
        self._input.installEventFilter(self)
        row.addWidget(self._input, 1)

        btn_col = QVBoxLayout()
        btn_col.setSpacing(4)

        self._send_btn = QPushButton("➤  Gönder")
        self._send_btn.setObjectName("sendButton")
        self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_btn.clicked.connect(self._send_message)
        self._send_btn.setFixedHeight(40)
        btn_col.addWidget(self._send_btn)

        clear_btn = QPushButton("🗑 Temizle")
        clear_btn.setObjectName("clearButton")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self._clear_chat)
        clear_btn.setFixedHeight(30)
        btn_col.addWidget(clear_btn)

        row.addLayout(btn_col)
        outer.addLayout(row)

        # Bottom note
        note = QLabel(f"🤖 Yanıt için en uygun proje otomatik seçilir  ·  max_tokens: 4096")
        note.setStyleSheet(f"color: {C_TEXT_MUTED}; font-size: 10px;")
        outer.addWidget(note)

        return area

    # ==================================================================
    # Key filter (Enter = send, Shift+Enter = newline)
    # ==================================================================

    def eventFilter(self, obj, event):
        if obj is self._input and event.type() == event.Type.KeyPress:
            if (
                event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            ):
                self._send_message()
                return True
        return super().eventFilter(obj, event)

    # ==================================================================
    # Project loading
    # ==================================================================

    def _load_projects(self):
        self._set_status("⟳", C_ORANGE, "Yükleniyor...")
        self._project_list.clear()
        t = ProjectListThread(self._client, self)
        t.loaded.connect(self._on_projects_loaded)
        t.error_occurred.connect(self._on_projects_error)
        t.finished.connect(t.deleteLater)
        t.start()

    @pyqtSlot(list)
    def _on_projects_loaded(self, projects: list):
        self._projects = projects
        self._project_list.clear()
        for p in projects:
            name = p.get("name", f"Proje {p['id']}")
            item = QListWidgetItem(f"  {name}")
            item.setData(Qt.ItemDataRole.UserRole, p["id"])
            item.setToolTip(p.get("description") or "")
            self._project_list.addItem(item)

        count = len(projects)
        self._set_status("●", C_GREEN, f"Bağlı  ·  {count} proje")

    @pyqtSlot(str)
    def _on_projects_error(self, msg: str):
        self._set_status("●", C_RED, "Bağlantı hatası")
        self._add_sys_message(f"⚠️  Proje listesi alınamadı: {msg}")

    def _set_status(self, dot: str, color: str, text: str):
        self._status_lbl.setText(f"<span style='color:{color}'>{dot}</span>  {text}")

    # ==================================================================
    # Send message
    # ==================================================================

    def _send_message(self):
        text = self._input.toPlainText().strip()
        if not text:
            return

        if self._stream_thread and self._stream_thread.isRunning():
            self._stream_thread.abort()
            self._stream_thread.wait(1000)

        self._input.clear()
        self._input.setEnabled(False)
        self._send_btn.setEnabled(False)
        self._refs_bar.hide()

        self._chat_area.add_user_message(text)

        if self._current_project:
            # User has manually selected a project — skip routing
            self._start_chat(text, self._current_project)
        else:
            # Auto-route
            if not self._projects:
                self._add_sys_message("⚠️  Projeler henüz yüklenmedi. Yenilemeyi deneyin.")
                self._set_input_enabled(True)
                return

            self._add_sys_message("🔍  En uygun proje aranıyor...")
            self._router_thread = ProjectRouterThread(self._client, self._projects, text, self)
            self._router_thread.project_found.connect(self._on_project_routed)
            self._router_thread.error_occurred.connect(self._on_routing_error)
            self._router_thread.finished.connect(self._router_thread.deleteLater)
            self._router_thread.start()
            self._pending_message = text

    @pyqtSlot(dict, float)
    def _on_project_routed(self, project: dict, score: float):
        score_pct = int(score * 100)
        name = project.get("name", "?")
        if score_pct > 0:
            self._add_sys_message(
                f"📁  <b>{name}</b> projesi seçildi  "
                f"<span style='color:{C_TEXT_MUTED}'>({score_pct}% eşleşme)</span>"
            )
        else:
            self._add_sys_message(
                f"📁  <b>{name}</b> projesi seçildi (varsayılan)"
            )
        msg = getattr(self, "_pending_message", "")
        self._start_chat(msg, project)

    @pyqtSlot(str)
    def _on_routing_error(self, msg: str):
        self._add_sys_message(f"⚠️  Proje seçilemedi: {msg}")
        self._set_input_enabled(True)

    def _start_chat(self, text: str, project: dict):
        project_name = project.get("name", "")
        project_id = project["id"]

        # Create streaming AI widget
        self._ai_widget = self._chat_area.start_ai_message(project_name)

        # Append user message to history
        self._history.append({"role": "user", "content": text})

        # Start streaming thread
        self._stream_thread = ChatStreamThread(
            self._client, project_id, text, self._history[:-1],
            max_tokens=4096, parent=self,
        )
        self._stream_thread.token_received.connect(self._on_token)
        self._stream_thread.refs_received.connect(self._on_refs)
        self._stream_thread.error_occurred.connect(self._on_stream_error)
        self._stream_thread.finished.connect(self._on_stream_done)
        self._stream_thread.start()

    @pyqtSlot(str)
    def _on_token(self, token: str):
        if self._ai_widget:
            self._ai_widget.append_chunk(token)
            self._chat_area._scroll_to_bottom()

    @pyqtSlot(list)
    def _on_refs(self, refs: list):
        if not refs:
            return
        names = ", ".join(r.get("name", "") for r in refs[:6] if r.get("name"))
        if names:
            self._refs_bar.setText(f"📎  {names}")
            self._refs_bar.show()

    @pyqtSlot(str)
    def _on_stream_error(self, msg: str):
        if self._ai_widget:
            self._ai_widget.append_chunk(f"\n\n⚠️ **Hata:** {msg}")
        else:
            self._add_sys_message(f"⚠️ {msg}")

    @pyqtSlot()
    def _on_stream_done(self):
        # Record assistant response in history
        if self._ai_widget:
            ai_text = self._ai_widget._raw_text
            if ai_text:
                self._history.append({"role": "assistant", "content": ai_text})
        self._chat_area.finalize_ai_message()
        self._ai_widget = None
        self._set_input_enabled(True)

    def _set_input_enabled(self, enabled: bool):
        self._input.setEnabled(enabled)
        self._send_btn.setEnabled(enabled)
        if enabled:
            self._input.setFocus()

    # ==================================================================
    # Misc helpers
    # ==================================================================

    def _add_sys_message(self, text: str):
        self._chat_area.add_sys_message(text)

    def _clear_chat(self):
        self._history.clear()
        self._current_project = None
        self._chat_area.clear_messages()
        self._refs_bar.hide()
        for i in range(self._project_list.count()):
            self._project_list.item(i).setSelected(False)

    def _change_server(self):
        url = self._server_edit.text().strip()
        if url:
            self._client.base_url = url.rstrip("/")
            self._server_url_lbl.setText(self._client.base_url)
            self._load_projects()

    # ------------------------------------------------------------------
    # Export / Import
    # ------------------------------------------------------------------

    def _on_export_clicked(self):
        if not self._current_project:
            QMessageBox.warning(self, "Uyarı", "Lütfen dışa aktarmak için bir proje seçin.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Proje Dışa Aktar", "", "AIKodAnaliz Dosyası (*.aikodanaliz);;Tüm Dosyalar (*.*)"
        )

        if not path:
            return

        def _on_success(output_path: str):
            QMessageBox.information(
                self, "Başarılı", f"Proje başarıyla dışa aktarıldı:\n{output_path}"
            )

        def _on_error(error_msg: str):
            QMessageBox.critical(self, "Hata", f"Dışa aktarma başarısız:\n{error_msg}")

        thread = ExportThread(self._client, self._current_project["id"], path)
        thread.success.connect(_on_success)
        thread.error.connect(_on_error)
        thread.start()

    def _on_import_clicked(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Proje İçe Aktar", "", "AIKodAnaliz Dosyası (*.aikodanaliz);;Tüm Dosyalar (*.*)"
        )

        if not path:
            return

        def _on_success(new_project: dict):
            QMessageBox.information(
                self, "Başarılı", f"Proje başarıyla içe aktarıldı:\n{new_project.get('name', 'Bilinmiyor')}"
            )
            self._load_projects()

        def _on_error(error_msg: str):
            QMessageBox.critical(self, "Hata", f"İçe aktarma başarısız:\n{error_msg}")

        thread = ImportThread(self._client, path)
        thread.success.connect(_on_success)
        thread.error.connect(_on_error)
        thread.start()

        # ==================================================================
        # Close
        # ==================================================================

        def closeEvent(self, event):
            # Stop streaming thread
            if self._stream_thread and self._stream_thread.isRunning():
                self._stream_thread.abort()
                self._stream_thread.wait(2000)
            # Stop router thread
            if self._router_thread and self._router_thread.isRunning():
                self._router_thread.wait(2000)
            event.accept()
