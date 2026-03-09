#!/usr/bin/env python3
"""
Database Reset Tool - AIKodAnaliz
Veritabanını sıfırdan oluşturur.
"""

import sys
import os
import sqlite3

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from config.config import DATABASE_PATH
from logger import logger


def reset_database():
    """Reset database to initial state - drop all tables and recreate"""
    db_dir = os.path.dirname(DATABASE_PATH)
    os.makedirs(db_dir, exist_ok=True)
    
    # Remove database and WAL files
    for ext in ['', '-wal', '-shm']:
        path = DATABASE_PATH + ext
        if os.path.exists(path):
            os.remove(path)
            logger.info(f"  Silindi: {path}")
    
    # Create fresh database with schema
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'analyzer',
            full_name TEXT,
            email TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Projects table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            admin_id INTEGER,
            FOREIGN KEY (admin_id) REFERENCES users(id)
        )
    ''')
    
    # Source files table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS source_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            language TEXT,
            content TEXT,
            hash TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            UNIQUE(project_id, file_path)
        )
    ''')
    
    # Functions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS functions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            file_id INTEGER NOT NULL,
            function_name TEXT NOT NULL,
            function_type TEXT,
            start_line INTEGER,
            end_line INTEGER,
            signature TEXT,
            parameters TEXT,
            return_type TEXT,
            description TEXT,
            ai_summary TEXT,
            class_name TEXT,
            package_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (file_id) REFERENCES source_files(id)
        )
    ''')
    
    # Function calls/dependencies table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS function_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            caller_function_id INTEGER NOT NULL,
            callee_function_id INTEGER NOT NULL,
            call_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (caller_function_id) REFERENCES functions(id),
            FOREIGN KEY (callee_function_id) REFERENCES functions(id)
        )
    ''')
    
    # Entry points table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS entry_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            function_id INTEGER NOT NULL,
            entry_type TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (function_id) REFERENCES functions(id)
        )
    ''')
    
    # User comments/marks table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_marks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            function_id INTEGER,
            user_id INTEGER NOT NULL,
            mark_type TEXT,
            comment TEXT,
            status TEXT DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (function_id) REFERENCES functions(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Version history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS version_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            version INTEGER,
            content TEXT,
            changes_summary TEXT,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (file_id) REFERENCES source_files(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')
    
    # AI settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            setting_name TEXT UNIQUE NOT NULL,
            setting_value TEXT,
            data_type TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Project Permissions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS project_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            permission_level TEXT DEFAULT 'read',
            read_only BOOLEAN DEFAULT 1,
            granted_by INTEGER,
            granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (granted_by) REFERENCES users(id),
            UNIQUE(project_id, user_id)
        )
    ''')
    
    # User Settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            theme TEXT DEFAULT 'light',
            notifications_enabled BOOLEAN DEFAULT 1,
            items_per_page INTEGER DEFAULT 20,
            default_filter TEXT,
            ai_api_url TEXT,
            preferences TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    conn.commit()
    conn.close()
    
    # Initialize with demo data
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Create demo users if not exist
    cursor.execute("SELECT COUNT(*) FROM users WHERE username = ?", ("admin",))
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO users (username, password, role, full_name, email, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ("admin", "admin123", "admin", "Admin Kullanıcı", "admin@aikodanaliz.local", 1))
        
        cursor.execute('''
            INSERT INTO users (username, password, role, full_name, email, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ("developer", "dev123", "developer", "Geliştirici Kullanıcı", "dev@aikodanaliz.local", 1))
        
        cursor.execute('''
            INSERT INTO users (username, password, role, full_name, email, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ("analyzer", "analyzer123", "analyzer", "Analizci Kullanıcı", "analyzer@aikodanaliz.local", 1))
        
        # Create default settings for demo users
        for username in ["admin", "developer", "analyzer"]:
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            user_id = cursor.fetchone()[0]
            cursor.execute('''
                INSERT INTO user_settings (user_id, theme, notifications_enabled, items_per_page)
                VALUES (?, ?, ?, ?)
            ''', (user_id, "light", 1, 20))
        
        # Initialize AI settings
        default_settings = [
            ('api_url', 'http://localhost:1234/v1', 'string'),
            ('temperature', '0.7', 'float'),
            ('top_p', '0.9', 'float'),
            ('max_tokens', '1000', 'integer'),
            ('timeout', '30', 'integer'),
            ('frequency_penalty', '0', 'float'),
            ('presence_penalty', '0', 'float'),
            ('retry_count', '3', 'integer'),
        ]
        for setting_name, setting_value, data_type in default_settings:
            cursor.execute('''
                INSERT OR IGNORE INTO ai_settings (setting_name, setting_value, data_type)
                VALUES (?, ?, ?)
            ''', (setting_name, setting_value, data_type))
    
    conn.commit()
    conn.close()


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
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
