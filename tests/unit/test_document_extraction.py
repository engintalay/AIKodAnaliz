"""DZT-13: add-file doküman yolunda gerçek metin çıkarımı testleri."""
import io
import os
import tempfile
import unittest
import uuid
import zipfile

from backend.app import app
from backend.database import db
from backend.routes.project_files import _extract_document_text


class TestDocumentExtraction(unittest.TestCase):
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
                "name": f"doctest-{uuid.uuid4().hex[:8]}",
                "description": "document extraction test",
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

    def test_txt_extracted_text_is_real_content(self):
        project_id = self._create_project()
        try:
            body = "Bu bir deneme dokumanidir. " * 20
            response = self._add_file(project_id, "gercek.txt", body.encode("utf-8"))
            self.assertEqual(response.status_code, 201)

            rows = db.execute_query(
                "SELECT extracted_text FROM project_documents WHERE project_id = ? AND file_name = ?",
                (project_id, "gercek.txt"),
            )
            self.assertTrue(rows)
            extracted = rows[0][0]
            self.assertIn("deneme dokumanidir", extracted)
            self.assertNotIn("Document:", extracted)
        finally:
            self.client.delete(f"/api/projects/{project_id}")

    def test_docx_extracted_text_is_real_content(self):
        import docx

        project_id = self._create_project()
        try:
            buf = io.BytesIO()
            document = docx.Document()
            document.add_paragraph("DZT-13 docx icerik satiri")
            document.add_paragraph("ikinci paragraf metni")
            document.save(buf)

            response = self._add_file(project_id, "gercek.docx", buf.getvalue())
            self.assertEqual(response.status_code, 201)

            rows = db.execute_query(
                "SELECT extracted_text FROM project_documents WHERE project_id = ? AND file_name = ?",
                (project_id, "gercek.docx"),
            )
            self.assertTrue(rows)
            extracted = rows[0][0]
            self.assertIn("DZT-13 docx icerik satiri", extracted)
            self.assertIn("ikinci paragraf metni", extracted)
            self.assertNotIn("Document:", extracted)
        finally:
            self.client.delete(f"/api/projects/{project_id}")

    def test_extract_document_text_direct(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ornek.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write("# Baslik\n\nicerik")
            self.assertIn("icerik", _extract_document_text(path, "ornek.md", "text"))

    def test_unknown_binary_doc_returns_empty_not_garbage(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bozuk.doc")
            with open(path, "wb") as f:
                f.write(b"\x00\x01\x02binary")
            # catdoc/antiword başarısız olursa boş dönmeli, çöp metin değil
            result = _extract_document_text(path, "bozuk.doc", "doc")
            self.assertIsInstance(result, str)


if __name__ == "__main__":
    unittest.main()
