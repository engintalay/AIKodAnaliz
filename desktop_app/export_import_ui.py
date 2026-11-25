"""Export/import UI components for GELIS18."""
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QProgressBar, QMessageBox,
)

from desktop_app.api_client import ApiClient, ApiError


class ExportThread(QThread):
    """Background thread for project export."""
    
    progress = pyqtSignal(str)
    success = pyqtSignal(str)   # file path
    error = pyqtSignal(str)

    def __init__(self, client: ApiClient, project_id: int, output_path: str, parent=None):
        super().__init__(parent)
        self._client = client
        self._project_id = project_id
        self._output_path = output_path

    def run(self):
        try:
            self.progress.emit("📤 Proje dışa aktarılıyor...")
            self._client.export_project(self._project_id, self._output_path)
            self.success.emit(self._output_path)
        except ApiError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"Beklenmeyen hata: {e}")


class ImportThread(QThread):
    """Background thread for project import."""
    
    progress = pyqtSignal(str)
    success = pyqtSignal(dict)   # {project_id, name}
    error = pyqtSignal(str)

    def __init__(self, client: ApiClient, file_path: str, parent=None):
        super().__init__(parent)
        self._client = client
        self._file_path = file_path

    def run(self):
        try:
            self.progress.emit("📥 Proje içe aktarılıyor...")
            result = self._client.import_project(self._file_path)
            self.success.emit(result)
        except ApiError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"Beklenmeyen hata: {e}")


class ExportImportDialog(QDialog):
    """Dialog for choosing export or import operation."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Proje Dışa/İçe Aktar")
        self.setFixedSize(350, 150)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        lbl = QLabel("Ne yapmak istersiniz?")
        lbl.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(lbl)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        export_btn = QPushButton("📤 Dışa Aktar")
        export_btn.clicked.connect(lambda: self.done(1))
        btn_layout.addWidget(export_btn)
        
        import_btn = QPushButton("📥 İçe Aktar")
        import_btn.clicked.connect(lambda: self.done(2))
        btn_layout.addWidget(import_btn)
        
        cancel_btn = QPushButton("İptal")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
        self.result_code = 0
    
    def exec(self):
        super().exec()
        return self.result()
