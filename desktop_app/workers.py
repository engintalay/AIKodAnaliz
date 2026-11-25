"""Background worker threads for project routing and chat streaming."""
import json
from PyQt6.QtCore import QThread, pyqtSignal

from desktop_app.api_client import ApiClient


class ProjectRouterThread(QThread):
    """
    Searches all projects via RAG to find the most relevant one for the query.
    Emits project_found(project_dict, score) when done,
    or fallback_used(project_dict) if no RAG hits.
    """

    project_found = pyqtSignal(dict, float)   # best project, score (0-1)
    error_occurred = pyqtSignal(str)

    def __init__(self, client: ApiClient, projects: list, query: str, parent=None):
        super().__init__(parent)
        self._client = client
        self._projects = projects
        self._query = query

    def run(self):
        try:
            best, score = self._client.find_best_project(self._projects, self._query)
            if best is not None:
                self.project_found.emit(best, score)
            else:
                self.error_occurred.emit("Hiç proje bulunamadı.")
        except Exception as e:
            self.error_occurred.emit(str(e))


class ChatStreamThread(QThread):
    """
    Streams a chat response from the backend via SSE.

    Signals:
        refs_received(list)    – list of referenced function dicts
        token_received(str)    – one streaming token
        error_occurred(str)    – error message
        finished()             – streaming complete
    """

    refs_received = pyqtSignal(list)
    token_received = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(
        self,
        client: ApiClient,
        project_id: int,
        message: str,
        history: list,
        max_tokens: int = 4096,
        parent=None,
    ):
        super().__init__(parent)
        self._client = client
        self._project_id = project_id
        self._message = message
        self._history = history
        self._max_tokens = max_tokens
        self._abort = False

    def abort(self):
        self._abort = True

    def run(self):
        try:
            for event_type, data in self._client.chat_stream(
                self._project_id, self._message, self._history, self._max_tokens
            ):
                if self._abort:
                    break

                if event_type == "done":
                    break
                elif event_type == "refs":
                    try:
                        refs = json.loads(data)
                        self.refs_received.emit(refs)
                    except Exception:
                        pass
                elif event_type == "error":
                    self.error_occurred.emit(data)
                    break
                else:
                    # data token (may be empty string)
                    if data:
                        self.token_received.emit(data)

        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            self.finished.emit()


class ProjectListThread(QThread):
    """Fetches the project list in the background."""

    loaded = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def __init__(self, client: ApiClient, parent=None):
        super().__init__(parent)
        self._client = client

    def run(self):
        try:
            projects = self._client.get_projects()
            self.loaded.emit(projects)
        except Exception as e:
            self.error_occurred.emit(str(e))
