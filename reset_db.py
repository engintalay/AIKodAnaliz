#!/usr/bin/env python3
"""
Database Reset Tool - AIKodAnaliz
Veritabanını sıfırdan oluşturur.
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from database import reset_database
from logger import get_logger

logger = get_logger(__name__)


def main():
    logger.info("Veritabanı sıfırlanıyor...")
    
    try:
        reset_database()
        logger.info("✓ Veritabanı başarıyla sıfırlandı!")
        logger.info("  - Admin: admin / admin123")
        logger.info("  - Developer: developer / dev123")
        logger.info("  - Analyzer: analyzer / analyzer123")
    except Exception as e:
        logger.error(f"✗ Hata: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
