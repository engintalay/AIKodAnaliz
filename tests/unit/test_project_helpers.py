import os
import tempfile
import unittest

from backend.routes import project


class TestProjectHelpers(unittest.TestCase):
    def test_detect_language_aliases(self):
        self.assertEqual(project._detect_language("app.js"), "javascript")
        self.assertEqual(project._detect_language("app.tsx"), "typescript")
        self.assertEqual(project._detect_language("index.java"), "java")
        self.assertEqual(project._detect_language("README"), "unknown")

    def test_binary_file_detection(self):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"\x00\x01\x02\x03")
            tmp_path = tmp.name

        try:
            self.assertTrue(project._is_binary_file(tmp_path))
        finally:
            os.remove(tmp_path)

    def test_should_index_file_rules(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".py") as tmp:
            tmp.write("print('ok')\n")
            text_path = tmp.name

        try:
            self.assertTrue(project._should_index_file("ok.py", text_path, is_war=False))
            self.assertFalse(project._should_index_file("archive.jar", text_path, is_war=False))
            self.assertTrue(project._should_index_file("ok.py", text_path, is_war=True))
            self.assertFalse(project._should_index_file("image.png", text_path, is_war=True))
        finally:
            os.remove(text_path)


if __name__ == "__main__":
    unittest.main()
