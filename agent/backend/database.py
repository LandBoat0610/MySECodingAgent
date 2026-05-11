import sqlite3
import os
from contextlib import contextmanager

from agent.backend.eval_storage import ensure_eval_storage_dirs

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "agent_platform.db")


def _migrate_eval_results_columns(conn: sqlite3.Connection) -> None:
    try:
        cur = conn.execute("PRAGMA table_info(eval_task_results)")
        names = {row[1] for row in cur.fetchall()}
    except sqlite3.OperationalError:
        return
    for col, ddl in [
        ("ragas_json", "TEXT DEFAULT '{}'"),
        ("judge_json", "TEXT DEFAULT '{}'"),
        ("runtime_metrics_json", "TEXT DEFAULT '{}'"),
        ("radar_json", "TEXT DEFAULT '{}'"),
        ("security_json", "TEXT DEFAULT '{}'"),
    ]:
        if col not in names:
            conn.execute(f"ALTER TABLE eval_task_results ADD COLUMN {col} {ddl}")


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
            CREATE TABLE IF NOT EXISTS platform_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS eval_datasets (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                item_count INTEGER NOT NULL DEFAULT 0,
                storage_path TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS eval_tasks (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                dataset_id TEXT NOT NULL,
                eval_method TEXT NOT NULL DEFAULT 'result',
                agent_model_snapshot TEXT NOT NULL DEFAULT '',
                agent_version_label_snapshot TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                error_message TEXT DEFAULT '',
                total_items INTEGER NOT NULL DEFAULT 0,
                completed_items INTEGER NOT NULL DEFAULT 0,
                passed_count INTEGER NOT NULL DEFAULT 0,
                failed_count INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(dataset_id) REFERENCES eval_datasets(id)
            );
            CREATE TABLE IF NOT EXISTS eval_task_results (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                item_index INTEGER NOT NULL,
                item_key TEXT DEFAULT '',
                description_snapshot TEXT,
                status TEXT NOT NULL,
                passed INTEGER,
                score_detail TEXT DEFAULT '{}',
                final_answer TEXT DEFAULT '',
                trace_json TEXT DEFAULT '[]',
                run_error TEXT DEFAULT '',
                ragas_json TEXT DEFAULT '{}',
                judge_json TEXT DEFAULT '{}',
                runtime_metrics_json TEXT DEFAULT '{}',
                radar_json TEXT DEFAULT '{}',
                security_json TEXT DEFAULT '{}',
                started_at TEXT,
                finished_at TEXT,
                FOREIGN KEY(task_id) REFERENCES eval_tasks(id),
                UNIQUE(task_id, item_index)
            );
        """)
        _migrate_eval_results_columns(conn)
    ensure_eval_storage_dirs()
    print("Database initialized.")


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
