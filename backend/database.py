import sqlite3
import os
from datetime import datetime
from config.config import DATABASE_PATH

class Database:
    def __init__(self):
        self.db_path = DATABASE_PATH
        self.connection_timeout = 30
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _connect(self):
        """Create a configured sqlite connection for better concurrency handling."""
        conn = sqlite3.connect(self.db_path, timeout=self.connection_timeout)
        self._apply_pragmas(conn)
        return conn

    def _apply_pragmas(self, conn):
        """Apply SQLite pragmas to reduce locking and improve write concurrency."""
        cursor = conn.cursor()
        cursor.execute('PRAGMA journal_mode = WAL')
        cursor.execute('PRAGMA busy_timeout = 30000')
        cursor.execute('PRAGMA synchronous = NORMAL')
        cursor.execute('PRAGMA foreign_keys = ON')
    
    def _init_db(self):
        """Initialize database schema"""
        with self._connect() as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    role TEXT DEFAULT 'viewer',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            
            # Create demo users if not exist
            cursor.execute("SELECT COUNT(*) FROM users WHERE username = ?", ("admin",))
            if cursor.fetchone()[0] == 0:
                # Admin user
                cursor.execute('''
                    INSERT INTO users (username, password, role)
                    VALUES (?, ?, ?)
                ''', ("admin", "admin123", "admin"))
                
                # Demo viewer user
                cursor.execute('''
                    INSERT INTO users (username, password, role)
                    VALUES (?, ?, ?)
                ''', ("user", "user123", "viewer"))
            
            conn.commit()
    
    def get_connection(self):
        """Get database connection"""
        conn = self._connect()
        conn.row_factory = sqlite3.Row
        return conn
    
    def execute_query(self, query, params=None):
        """Execute SELECT query"""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor.fetchall()
    
    def execute_insert(self, query, params=None):
        """Execute INSERT query"""
        with self._connect() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            conn.commit()
            return cursor.lastrowid
    
    def execute_update(self, query, params=None):
        """Execute UPDATE query"""
        with self._connect() as conn:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            conn.commit()
            return cursor.rowcount
    
    def execute_many(self, query, params_list):
        """Execute INSERT/UPDATE with multiple parameter sets (batch operation)"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            conn.commit()
            return cursor.rowcount

# Initialize database
db = Database()
