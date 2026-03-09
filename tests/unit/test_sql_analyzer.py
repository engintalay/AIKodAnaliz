import unittest

from backend.analyzers.code_analyzer import CodeAnalyzer


class TestSQLAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = CodeAnalyzer()

    def test_sql_create_procedure_extraction(self):
        content = """
CREATE PROCEDURE GetUserById(IN userId INT)
BEGIN
    SELECT * FROM users WHERE id = userId;
END;
"""
        result = self.analyzer.analyze("proc.sql", content, "sql")
        
        self.assertEqual(len(result["functions"]), 1)
        self.assertEqual(result["functions"][0]["name"].upper(), "GETUSERBYID")
        self.assertEqual(result["functions"][0]["type"], "procedure")

    def test_sql_create_function_extraction(self):
        content = """
CREATE FUNCTION CalculateTotal(price DECIMAL, quantity INT)
RETURNS DECIMAL
BEGIN
    RETURN price * quantity;
END;
"""
        result = self.analyzer.analyze("func.sql", content, "sql")
        
        self.assertEqual(len(result["functions"]), 1)
        self.assertEqual(result["functions"][0]["name"].upper(), "CALCULATETOTAL")
        self.assertEqual(result["functions"][0]["type"], "function")

    def test_sql_create_view_extraction(self):
        content = """
CREATE VIEW ActiveUsers AS
SELECT id, name, email 
FROM users 
WHERE status = 'active';
"""
        result = self.analyzer.analyze("view.sql", content, "sql")
        
        self.assertEqual(len(result["functions"]), 1)
        self.assertEqual(result["functions"][0]["name"].upper(), "ACTIVEUSERS")
        self.assertEqual(result["functions"][0]["type"], "view")

    def test_sql_create_trigger_extraction(self):
        content = """
CREATE TRIGGER UpdateTimestamp
AFTER UPDATE ON users
FOR EACH ROW
BEGIN
    SET NEW.updated_at = NOW();
END;
"""
        result = self.analyzer.analyze("trigger.sql", content, "sql")
        
        self.assertEqual(len(result["functions"]), 1)
        self.assertEqual(result["functions"][0]["name"].upper(), "UPDATETIMESTAMP")
        self.assertEqual(result["functions"][0]["type"], "trigger")
        self.assertTrue(result["functions"][0]["is_entry"])

    def test_sql_dependencies_extraction(self):
        content = """
SELECT u.name, o.total
FROM users u
JOIN orders o ON u.id = o.user_id
WHERE o.status = 'completed';
"""
        result = self.analyzer.analyze("query.sql", content, "sql")
        
        self.assertIn("users", result["dependencies"])
        self.assertIn("orders", result["dependencies"])


if __name__ == "__main__":
    unittest.main()
