"""SQL nesne çıkarımı testleri (tablo, index, prosedür, view, trigger).

Gerçek ağ/veritabanı kullanılmaz; ``backend.analyzers.sql_objects`` doğrudan
test edilir.
"""
import unittest

from backend.analyzers.sql_objects import analyze_sql, normalize_identifier


class TestNormalizeIdentifier(unittest.TestCase):
    def test_bracket_quoted_name(self):
        self.assertEqual(normalize_identifier('[dbo].[ANATAKIP]'), 'dbo.ANATAKIP')

    def test_double_quoted_name(self):
        self.assertEqual(normalize_identifier('"dbo"."PROC"'), 'dbo.PROC')

    def test_plain_name(self):
        self.assertEqual(normalize_identifier('dbo.Tablo'), 'dbo.Tablo')

    def test_empty_name(self):
        self.assertEqual(normalize_identifier(''), '')


class TestAnalyzeSqlTables(unittest.TestCase):
    def test_create_table_columns(self):
        content = """
CREATE TABLE "dbo"."ANATAKIP" (
    "OID" char(14) NOT NULL,
    "ORGOID" char(14) NOT NULL,
    "TUTAR" decimal(10,2) DEFAULT 0
)
LOCK DATAROWS
GO
"""
        result = analyze_sql('tablo.sql', content)

        self.assertIsNone(result.get('error'))
        self.assertEqual(len(result['functions']), 1)
        table = result['functions'][0]
        self.assertEqual(table['type'], 'table')
        self.assertEqual(table['name'], 'dbo.ANATAKIP')
        self.assertEqual(table['parameters'], ['OID', 'ORGOID', 'TUTAR'])
        self.assertIn('3 kolon', table['signature'])

    def test_create_table_if_not_exists_and_constraints(self):
        content = """
CREATE TABLE IF NOT EXISTS [dbo].[Kisi] (
    [Id] INT NOT NULL,
    [Ad] NVARCHAR(50),
    CONSTRAINT PK_Kisi PRIMARY KEY ([Id], [Ad]),
    CONSTRAINT FK_Kisi FOREIGN KEY (Id) REFERENCES Diger(Id)
);
"""
        result = analyze_sql('kisi.sql', content)

        self.assertEqual(len(result['functions']), 1)
        table = result['functions'][0]
        self.assertEqual(table['name'], 'dbo.Kisi')
        self.assertEqual(table['parameters'], ['Id', 'Ad'])
        self.assertIn('PK: Id, Ad', table['signature'])

    def test_create_index(self):
        content = """
CREATE UNIQUE NONCLUSTERED INDEX [IX_Kisi_Ad] ON [dbo].[Kisi] ([Ad], [Id]);
"""
        result = analyze_sql('index.sql', content)

        self.assertEqual(len(result['functions']), 1)
        index = result['functions'][0]
        self.assertEqual(index['type'], 'index')
        self.assertEqual(index['name'], 'IX_Kisi_Ad')
        self.assertEqual(index['parameters'], ['Ad', 'Id'])
        self.assertIn('ON dbo.Kisi', index['signature'])
        self.assertIn('UNIQUE NONCLUSTERED', index['signature'])

    def test_alter_table_is_not_a_new_object(self):
        content = """
ALTER TABLE dbo.Kisi ADD Email NVARCHAR(100);
"""
        result = analyze_sql('alter.sql', content)

        self.assertEqual(result['functions'], [])

    def test_comments_are_ignored(self):
        content = """
-- CREATE TABLE fake (x int);
/* CREATE INDEX fake_idx ON fake (x); */
CREATE TABLE real_table (id INT);
"""
        result = analyze_sql('yorum.sql', content)

        self.assertEqual(len(result['functions']), 1)
        self.assertEqual(result['functions'][0]['name'], 'real_table')


class TestAnalyzeSqlRoutines(unittest.TestCase):
    def test_create_or_alter_procedure(self):
        content = """
CREATE OR ALTER PROCEDURE [dbo].[sp_Test] (@a INT, @b VARCHAR(10)) AS
BEGIN
    SELECT * FROM dbo.Kisi;
END
GO
"""
        result = analyze_sql('proc.sql', content)

        self.assertEqual(len(result['functions']), 1)
        proc = result['functions'][0]
        self.assertEqual(proc['type'], 'procedure')
        self.assertEqual(proc['name'], 'dbo.sp_Test')
        self.assertEqual(proc['parameters'], ['@a', '@b'])

    def test_create_or_replace_view(self):
        content = """
CREATE OR REPLACE VIEW "dbo"."vKisi" AS SELECT Id FROM dbo.Kisi;
"""
        result = analyze_sql('view.sql', content)

        self.assertEqual(len(result['functions']), 1)
        view = result['functions'][0]
        self.assertEqual(view['type'], 'view')
        self.assertEqual(view['name'], 'dbo.vKisi')

    def test_trigger_is_entry_point(self):
        content = """
CREATE TRIGGER trgKisi ON dbo.Kisi AFTER INSERT AS SELECT 1;
"""
        result = analyze_sql('trigger.sql', content)

        self.assertEqual(len(result['functions']), 1)
        trigger = result['functions'][0]
        self.assertEqual(trigger['type'], 'trigger')
        self.assertTrue(trigger['is_entry'])
        self.assertEqual(len(result['entry_points']), 1)

    def test_line_numbers_use_increasing_cursor(self):
        content = """
CREATE TABLE a (id INT);
GO
CREATE TABLE b (id INT);
GO
CREATE TABLE c (id INT);
"""
        result = analyze_sql('lines.sql', content)
        starts = [f['start_line'] for f in result['functions']]

        self.assertEqual(len(starts), 3)
        self.assertEqual(starts, sorted(starts))
        self.assertEqual(len(set(starts)), 3)


if __name__ == '__main__':
    unittest.main()
