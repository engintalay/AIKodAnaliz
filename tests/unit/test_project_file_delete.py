"""Tests for document / DALMap delete endpoints (GELIS9)."""
import io
import unittest
import uuid
import zipfile

from backend.app import app
from backend.database import db


DALMAP_XML = b"""<?xml version="1.0"?>
<DALMAP>
  <PROXYTABLES>
    <PT name="ptest" table="TEST_TABLE" db="TESTDB">
      <FIELD id="oid" type="string" column="OID" dbType="VARCHAR"/>
    </PT>
  </PROXYTABLES>
</DALMAP>
"""


class TestProjectFileDelete(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()
        cls.client.post(
            "/api/users/login",
            json={"username": "admin", "password": "admin123"},
        )

    def _create_project(self):
        zb = io.BytesIO()
        with zipfile.ZipFile(zb, "w") as zf:
            zf.writestr("src/app.py", "def hello():\n    return 'ok'\n")
        zb.seek(0)
        response = self.client.post(
            "/api/projects/upload",
            data={
                "name": f"deltest-{uuid.uuid4().hex[:8]}",
                "description": "delete endpoint test",
                "file": (zb, "sample.zip"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 201)
        return response.get_json()["project_id"]

    def _add_file(self, project_id, name, content):
        return self.client.post(
            f"/api/projects/{project_id}/add-file",
            data={"file": (io.BytesIO(content), name)},
            content_type="multipart/form-data",
        )

    def test_delete_document_removes_rows_and_file(self):
        project_id = self._create_project()
        try:
            response = self._add_file(
                project_id, "test_doc.txt", b"deneme metni " * 30
            )
            self.assertEqual(response.status_code, 201)

            rows = db.execute_query(
                "SELECT file_path FROM project_documents WHERE project_id = ? AND file_name = ?",
                (project_id, "test_doc.txt"),
            )
            self.assertTrue(rows)

            response = self.client.delete(
                f"/api/projects/{project_id}/docs/file/test_doc.txt"
            )
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertGreater(payload["deleted_chunks"], 0)
            self.assertTrue(payload["file_deleted"])

            self.assertFalse(
                db.execute_query(
                    "SELECT id FROM project_documents WHERE project_id = ? AND file_name = ?",
                    (project_id, "test_doc.txt"),
                )
            )
            self.assertFalse(
                db.execute_query(
                    "SELECT id FROM doc_chunks WHERE project_id = ? AND file_name = ?",
                    (project_id, "test_doc.txt"),
                )
            )
        finally:
            self.client.delete(f"/api/projects/{project_id}")

    def test_delete_dalmap_removes_rows_and_file(self):
        project_id = self._create_project()
        try:
            response = self._add_file(
                project_id, "dalMapConfig_TEST.xml", DALMAP_XML
            )
            self.assertEqual(response.status_code, 201)

            rows = db.execute_query(
                "SELECT id FROM dalmap_files WHERE project_id = ? AND file_name = ?",
                (project_id, "dalMapConfig_TEST.xml"),
            )
            self.assertTrue(rows)
            dalmap_id = rows[0][0]

            response = self.client.delete(
                f"/api/projects/{project_id}/dalmaps/{dalmap_id}"
            )
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertGreater(payload["deleted_chunks"], 0)
            self.assertTrue(payload["file_deleted"])

            self.assertFalse(
                db.execute_query(
                    "SELECT id FROM dalmap_files WHERE project_id = ? AND file_name = ?",
                    (project_id, "dalMapConfig_TEST.xml"),
                )
            )
            self.assertFalse(
                db.execute_query(
                    "SELECT id FROM doc_chunks WHERE project_id = ? AND file_name = ?",
                    (project_id, "dalMapConfig_TEST.xml"),
                )
            )
        finally:
            self.client.delete(f"/api/projects/{project_id}")

    def test_delete_missing_document_returns_404(self):
        project_id = self._create_project()
        try:
            response = self.client.delete(
                f"/api/projects/{project_id}/docs/file/does_not_exist.txt"
            )
            self.assertEqual(response.status_code, 404)
        finally:
            self.client.delete(f"/api/projects/{project_id}")

    def test_delete_missing_dalmap_returns_404(self):
        project_id = self._create_project()
        try:
            response = self.client.delete(
                f"/api/projects/{project_id}/dalmaps/999999"
            )
            self.assertEqual(response.status_code, 404)
        finally:
            self.client.delete(f"/api/projects/{project_id}")


if __name__ == "__main__":
    unittest.main()
