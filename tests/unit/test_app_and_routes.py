import io
import unittest
import uuid
import zipfile

from backend.app import app


class TestAppAndRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

    def test_health_endpoint(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("status", payload)

    def test_static_js_cache_headers(self):
        response = self.client.get("/static/js/main.js")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Cache-Control"), "no-cache, no-store, must-revalidate")

    def test_upload_without_file_returns_400(self):
        response = self.client.post("/api/projects/upload", data={}, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    def test_upload_with_unsupported_extension_returns_400(self):
        data = {
            "name": "bad-upload",
            "description": "test",
            "file": (io.BytesIO(b"plain text"), "bad.txt"),
        }
        response = self.client.post("/api/projects/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    def test_upload_valid_zip_returns_created(self):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("src/app.py", "def hello():\n    return 'ok'\n")
        zip_buffer.seek(0)

        data = {
            "name": f"unit-{uuid.uuid4().hex[:8]}",
            "description": "unit test upload",
            "file": (zip_buffer, "sample.zip"),
        }

        response = self.client.post("/api/projects/upload", data=data, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertIn("project_id", payload)
        self.assertIn("task_id", payload)

        project_id = payload["project_id"]
        delete_resp = self.client.delete(f"/api/projects/{project_id}")
        self.assertEqual(delete_resp.status_code, 200)

    def test_progress_unknown_task_returns_terminal_failed(self):
        response = self.client.get("/api/projects/progress/task-does-not-exist")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload.get("status"), "failed")
        self.assertFalse(payload.get("task_exists"))


if __name__ == "__main__":
    unittest.main()
