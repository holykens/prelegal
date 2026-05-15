import os
import sqlite3
import tempfile

import pytest

_tests_dir = os.path.dirname(__file__)
_backend_dir = os.path.dirname(_tests_dir)
_project_root = os.path.dirname(_backend_dir)

# Set before main.py is imported so module-level constants pick these up.
os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "test.db"))
os.environ.setdefault("CATALOG_PATH", os.path.join(_project_root, "catalog.json"))
os.environ.setdefault("TEMPLATES_DIR", os.path.join(_project_root, "templates"))


@pytest.fixture(autouse=True)
def fresh_db():
    """Drop and recreate all tables before every test for a clean slate.

    Production init_db() uses CREATE TABLE IF NOT EXISTS (preserves data across
    restarts), so we do the destructive drop here in the test fixture only.
    """
    from main import DB_PATH as _db_path
    conn = sqlite3.connect(_db_path)
    conn.executescript("""
        DROP TABLE IF EXISTS documents;
        DROP TABLE IF EXISTS users;
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            document_name TEXT NOT NULL,
            fields_json TEXT NOT NULL DEFAULT '{}',
            messages_json TEXT NOT NULL DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()
