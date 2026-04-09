"""Backend API client for AIKodAnaliz Desktop App.

Handles login, project listing, RAG search, and SSE streaming chat.
"""
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Generator, Iterator

import requests


class ApiError(Exception):
    """Raised when a backend API call fails."""
    pass


class ApiClient:
    """HTTP client for the AIKodAnaliz Flask backend."""

    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.trust_env = False  # ignore OS proxy settings
        self._lock = threading.Lock()

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def login(self, username: str, password: str) -> dict:
        """Login and store session cookie. Returns user dict."""
        try:
            resp = self.session.post(
                self._url("/api/users/login"),
                json={"username": username, "password": password},
                timeout=15,
            )
        except requests.exceptions.ConnectionError:
            raise ApiError(f"Sunucuya bağlanılamadı: {self.base_url}")
        except requests.exceptions.Timeout:
            raise ApiError("Bağlantı zaman aşımına uğradı.")

        if resp.status_code == 200:
            return resp.json().get("user", {})
        elif resp.status_code == 401:
            raise ApiError("Kullanıcı adı veya şifre hatalı.")
        elif resp.status_code == 403:
            raise ApiError("Hesap devre dışı bırakılmış.")
        else:
            try:
                msg = resp.json().get("error", resp.text)
            except Exception:
                msg = resp.text
            raise ApiError(f"Giriş başarısız: {msg}")

    def logout(self) -> None:
        """Send logout request (best-effort)."""
        try:
            self.session.post(self._url("/api/users/logout"), timeout=5)
        except Exception:
            pass
        finally:
            self.session.cookies.clear()

    def check_session(self) -> bool:
        """Returns True if the session is still valid by checking /api/projects/."""
        try:
            resp = self.session.get(self._url("/api/projects/"), timeout=8)
            return resp.status_code == 200
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    def get_projects(self) -> list:
        """Return list of projects dicts."""
        try:
            resp = self.session.get(self._url("/api/projects/"), timeout=15)
        except requests.exceptions.ConnectionError:
            raise ApiError(f"Sunucuya bağlanılamadı: {self.base_url}")
        except requests.exceptions.Timeout:
            raise ApiError("İstek zaman aşımına uğradı.")

        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                return data
            return data.get("projects", [])
        elif resp.status_code in (401, 403):
            raise ApiError("Oturum sona erdi. Lütfen tekrar giriş yapın.")
        else:
            raise ApiError(f"Projeler alınamadı: {resp.status_code}")

    # ------------------------------------------------------------------
    # RAG Search (per project)
    # ------------------------------------------------------------------

    def rag_search(self, project_id: int, query: str, limit: int = 5) -> list:
        """Search a single project RAG index. Returns list of result dicts."""
        try:
            resp = self.session.get(
                self._url(f"/api/rag/project/{project_id}/search"),
                params={"q": query, "limit": limit},
                timeout=20,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("results", data) if isinstance(data, dict) else data
            return []
        except Exception:
            return []

    def find_best_project(self, projects: list, query: str) -> tuple[dict | None, float]:
        """
        Search all projects in parallel and return (best_project, best_score).
        Falls back to first project if no RAG hits found.
        """
        if not projects:
            return None, 0.0

        best_project = None
        best_score = 0.0

        def _search(proj):
            results = self.rag_search(proj["id"], query, limit=3)
            if results:
                score = results[0].get("best_score") or results[0].get("score") or 0.0
                try:
                    score = float(score)
                except (TypeError, ValueError):
                    score = 0.0
                return proj, score
            return proj, 0.0

        max_workers = min(8, len(projects))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_search, p): p for p in projects}
            for future in as_completed(futures):
                try:
                    proj, score = future.result()
                    if score > best_score:
                        best_score = score
                        best_project = proj
                except Exception:
                    pass

        if best_project is None:
            best_project = projects[0]
            best_score = 0.0

        return best_project, best_score

    # ------------------------------------------------------------------
    # Chat Streaming
    # ------------------------------------------------------------------

    def chat_stream(
        self,
        project_id: int,
        message: str,
        history: list,
        max_tokens: int = 4096,
    ) -> Iterator[tuple[str, str]]:
        """
        Stream chat tokens over SSE.

        Yields (event_type, data) tuples where event_type is 'refs', 'data', or 'done'.
        """
        payload = {
            "message": message,
            "history": history,
            "max_tokens": max_tokens,
        }

        try:
            with self.session.post(
                self._url(f"/api/chat/project/{project_id}"),
                json=payload,
                stream=True,
                timeout=600,
            ) as resp:
                if resp.status_code != 200:
                    try:
                        err = resp.json().get("error", resp.text)
                    except Exception:
                        err = resp.text
                    yield "error", f"Sunucu hatası ({resp.status_code}): {err}"
                    yield "done", ""
                    return

                current_event = "data"
                data_lines: list[str] = []

                for raw_line in resp.iter_lines(decode_unicode=True):
                    if raw_line == "":
                        # End of SSE event
                        if data_lines:
                            payload_str = "\n".join(data_lines)
                            if payload_str == "[DONE]":
                                yield "done", ""
                                return
                            yield current_event, payload_str
                        current_event = "data"
                        data_lines = []
                    elif raw_line.startswith("event:"):
                        current_event = raw_line[6:].strip()
                    elif raw_line.startswith("data:"):
                        data_lines.append(raw_line[5:])

        except requests.exceptions.ConnectionError:
            yield "error", f"Sunucu bağlantısı kesildi: {self.base_url}"
            yield "done", ""
        except requests.exceptions.Timeout:
            yield "error", "İstek zaman aşımına uğradı (10 dakika)."
            yield "done", ""
        except Exception as e:
            yield "error", f"Beklenmeyen hata: {e}"
            yield "done", ""
