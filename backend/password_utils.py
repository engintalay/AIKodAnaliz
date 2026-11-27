"""Password hashing helpers (DZT-12).

Werkzeug tabanlı hash üretimi ve doğrulaması. Eski düz metin kayıtları da
doğrulanabilir; `migrate_plaintext_passwords` ile bir kez hash'e çevrilir.
"""
from werkzeug.security import generate_password_hash, check_password_hash

# Werkzeug'un ürettiği hash formatları
_HASH_PREFIXES = ('pbkdf2:', 'scrypt:', 'argon2:')


def is_password_hash(value):
    """Değer daha önce hash'lenmiş mi?"""
    return isinstance(value, str) and value.startswith(_HASH_PREFIXES)


def hash_password(password):
    """Parolayı güvenli biçimde hash'le."""
    return generate_password_hash(password)


def verify_password(stored, password):
    """Hash veya eski düz metin kaydı doğrula."""
    if not stored or password is None:
        return False
    if is_password_hash(stored):
        try:
            return check_password_hash(stored, password)
        except (ValueError, TypeError):
            return False
    # Geriye dönük uyumluluk: eski düz metin kayıt
    return stored == password


def migrate_plaintext_passwords(cursor):
    """Tüm düz metin parolaları hash'e çevir. Idempotenttir.

    Returns: hash'lenen kayıt sayısı.
    """
    cursor.execute("SELECT id, password FROM users")
    rows = cursor.fetchall()
    migrated = 0
    for user_id, stored in rows:
        if stored and not is_password_hash(stored):
            cursor.execute(
                "UPDATE users SET password = ? WHERE id = ?",
                (hash_password(stored), user_id),
            )
            migrated += 1
    return migrated
