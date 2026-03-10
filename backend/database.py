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
            
            # Project Permissions table - Developer/Analyzer access to projects
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

            # Audit logs table - tracks all user actions
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    username TEXT,
                    action TEXT NOT NULL,
                    resource_type TEXT,
                    resource_id INTEGER,
                    details TEXT,
                    ip_address TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')

            # FTS5 full-text search index for functions (GELIS4)
            cursor.execute('''
                CREATE VIRTUAL TABLE IF NOT EXISTS fts_functions
                USING fts5(
                    function_id UNINDEXED,
                    function_name,
                    class_name,
                    package_name,
                    ai_summary,
                    file_name,
                    tokenize = "unicode61"
                )
            ''')

            # Embedding vectors table for semantic search (GELIS4)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS function_embeddings (
                    function_id  INTEGER PRIMARY KEY,
                    project_id   INTEGER NOT NULL,
                    embedding    TEXT NOT NULL,
                    model_name   TEXT,
                    indexed_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (function_id) REFERENCES functions(id) ON DELETE CASCADE,
                    FOREIGN KEY (project_id)  REFERENCES projects(id)  ON DELETE CASCADE
                )
            ''')

            # Document RAG chunks table for PDF/DOCX files (GELIS8)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS doc_chunks (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id  INTEGER NOT NULL,
                    file_name   TEXT,
                    chunk_index INTEGER DEFAULT 0,
                    content     TEXT NOT NULL,
                    embedding   TEXT,
                    model_name  TEXT,
                    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
                )
            ''')


            # Backward-compatible migration for existing databases
            cursor.execute("PRAGMA table_info(user_settings)")
            existing_columns = {row[1] for row in cursor.fetchall()}
            if 'ai_api_url' not in existing_columns:
                cursor.execute('ALTER TABLE user_settings ADD COLUMN ai_api_url TEXT')
            
            # Create demo users if not exist
            cursor.execute("SELECT COUNT(*) FROM users WHERE username = ?", ("admin",))
            if cursor.fetchone()[0] == 0:
                # Admin user
                cursor.execute('''
                    INSERT INTO users (username, password, role, full_name, email, is_active)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', ("admin", "admin123", "admin", "Admin Kullanıcı", "admin@aikodanaliz.local", 1))
                
                # Demo developer user
                cursor.execute('''
                    INSERT INTO users (username, password, role, full_name, email, is_active)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', ("developer", "dev123", "developer", "Geliştirici Kullanıcı", "dev@aikodanaliz.local", 1))
                
                # Demo analyzer user  
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
                
                # Initialize AI settings with default values
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
# Initialize database
db = Database()


def reset_database():
    """Reset database to initial state - drop all tables and recreate"""
    import os
    
    # Close any existing connections
    if os.path.exists(Database().db_path):
        os.remove(Database().db_path)
    
    # Remove WAL files
    db_path = Database().db_path
    wal_path = db_path + "-wal"
    shm_path = db_path + "-shm"
    
    for path in [wal_path, shm_path]:
        if os.path.exists(path):
            os.remove(path)
    
    # Reinitialize database
    Database()
