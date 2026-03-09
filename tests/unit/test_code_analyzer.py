import unittest

from backend.analyzers.code_analyzer import CodeAnalyzer


class TestCodeAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = CodeAnalyzer()

    def test_python_analysis_extracts_functions_and_entry_points(self):
        content = """
import os

def helper(x, y):
    return x + y

def main():
    return helper(1, 2)
"""
        result = self.analyzer.analyze("sample/module.py", content, "python")
        names = {f["name"] for f in result["functions"]}

        self.assertIn("helper", names)
        self.assertIn("main", names)
        self.assertTrue(any(f["name"] == "main" for f in result["entry_points"]))
        self.assertIn("os", result["dependencies"])

    def test_java_like_analysis_extracts_class_and_methods(self):
        content = """
package com.example;

public class Demo {
    public static void main(String[] args) {
        run();
    }

    private void run() {
    }
}
"""
        result = self.analyzer.analyze("Demo.java", content, "java")
        names = {f["name"] for f in result["functions"]}

        self.assertIn("main", names)
        self.assertIn("run", names)
        self.assertTrue(any(f["is_entry"] for f in result["functions"]))

    def test_php_analysis_extracts_namespace_and_functions(self):
        content = """
<?php
namespace App\\Service;

class UserService {
    public function index($id) {
        return $id;
    }
}
"""
        result = self.analyzer.analyze("UserService.php", content, "php")

        self.assertEqual(len(result["functions"]), 1)
        self.assertEqual(result["functions"][0]["name"], "index")
        self.assertEqual(result["functions"][0]["package_name"], "App\\Service")
        self.assertEqual(len(result["entry_points"]), 1)

    def test_markup_analysis_returns_empty_collections(self):
        result = self.analyzer.analyze("index.html", "<html></html>", "html")
        self.assertEqual(result["functions"], [])
        self.assertEqual(result["entry_points"], [])
        self.assertEqual(result["dependencies"], [])

    def test_generic_analysis_detects_function_like_patterns(self):
        content = """
func hello(name) {
    return name;
}
"""
        result = self.analyzer.analyze("x.unknown", content, "unknown")
        self.assertEqual(len(result["functions"]), 1)
        self.assertEqual(result["functions"][0]["name"], "hello")


if __name__ == "__main__":
    unittest.main()
