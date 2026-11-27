"""DZT-12: parola hash'leme ve düz metin migrasyonu testleri."""
import sqlite3
import unittest

from backend.password_utils import (
    hash_password,
    is_password_hash,
    migrate_plaintext_passwords,
    verify_password,
)


class TestPasswordUtils(unittest.TestCase):
    def test_hash_is_not_plaintext(self):
        hashed = hash_password("gizli123")
        self.assertNotEqual(hashed, "gizli123")
        self.assertTrue(is_password_hash(hashed))

    def test_verify_hashed_password(self):
        hashed = hash_password("gizli123")
        self.assertTrue(verify_password(hashed, "gizli123"))
        self.assertFalse(verify_password(hashed, "yanlis"))

    def test_verify_legacy_plaintext(self):
        self.assertTrue(verify_password("admin123", "admin123"))
        self.assertFalse(verify_password("admin123", "baska"))

    def test_verify_empty(self):
        self.assertFalse(verify_password("", "x"))
        self.assertFalse(verify_password(None, "x"))
        self.assertFalse(verify_password("x", None))

    def test_migrate_plaintext_passwords(self):
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, password TEXT)")
        cursor.executemany(
            "INSERT INTO users (id, password) VALUES (?, ?)",
            [(1, "duzmetin"), (2, hash_password("zatenhash"))],
        )
        migrated = migrate_plaintext_passwords(cursor)
        conn.commit()
        self.assertEqual(migrated, 1)

        cursor.execute("SELECT password FROM users WHERE id = 1")
        stored = cursor.fetchone()[0]
        self.assertTrue(is_password_hash(stored))
        self.assertTrue(verify_password(stored, "duzmetin"))

        # Idempotent: ikinci çalıştırma hiçbir şey değiştirmez
        self.assertEqual(migrate_plaintext_passwords(cursor), 0)
        conn.close()


if __name__ == "__main__":
    unittest.main()
