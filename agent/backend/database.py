import sqlite3
import json
import os
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "agent_platform.db")

def init_db():
    with get_connection() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                workspace_path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                description TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                title TEXT DEFAULT 'New Session',
                created_at TEXT NOT NULL,
                state_snapshot TEXT DEFAULT '{}',
                status TEXT DEFAULT 'idle',
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );
            CREATE TABLE IF NOT EXISTS plans (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                content TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id)
            );
            CREATE TABLE IF NOT EXISTS plan_actions (
                id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(plan_id) REFERENCES plans(id)
            );
        """)
    print("Database initialized.")

@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
