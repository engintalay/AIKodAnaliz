import unittest
from unittest.mock import MagicMock, patch

from backend.routes import analysis


def _class_func(content, start_line=1, end_line=None):
    return {
        'id': 1,
        'function_name': 'Const',
        'file_id': 2,
        'project_id': 3,
        'start_line': start_line,
        'end_line': end_line if end_line is not None else len(content.split('\n')),
        'content': content,
    }


class TestClassSummaryFallback(unittest.TestCase):
    """Metodu olmayan class'lar gövdesi üzerinden özetlenmeli."""

    def test_class_without_methods_summarizes_body(self):
        content = 'public class Const {\n    public static int A = 1;\n}'
        client = MagicMock()
        client.analyze_function.return_value = 'Sabit değerleri tutan sınıf.'

        with patch.object(analysis.db, 'execute_query', return_value=[]):
            result = analysis._generate_class_summary(
                _class_func(content), client, None, 0.2, 0.9, 512, None, None
            )

        self.assertEqual(result, 'Sabit değerleri tutan sınıf.')
        code_arg = client.analyze_function.call_args[0][0]
        self.assertIn('public static int A = 1;', code_arg)
        self.assertIn('Const', code_arg)

    def test_class_without_methods_and_empty_body_returns_warning(self):
        client = MagicMock()

        with patch.object(analysis.db, 'execute_query', return_value=[]):
            result = analysis._generate_class_summary(
                _class_func('', start_line=1, end_line=1), client, None, 0.2, 0.9, 512, None, None
            )

        self.assertIn('metot bulunamadı', result)
        client.analyze_function.assert_not_called()

    def test_class_body_summary_error_returns_warning(self):
        content = 'public class Const {\n    public static int A = 1;\n}'
        client = MagicMock()
        client.analyze_function.return_value = 'Error: model returned 400'

        with patch.object(analysis.db, 'execute_query', return_value=[]):
            result = analysis._generate_class_summary(
                _class_func(content), client, None, 0.2, 0.9, 512, None, None
            )

        self.assertIn('özet oluşturulamadı', result)


if __name__ == '__main__':
    unittest.main()
