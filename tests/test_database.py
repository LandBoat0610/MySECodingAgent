# tests/test_database.py
from agent.backend import database
import os
import sys
import sqlite3
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 必须在导入 agent 任何模块之前设置假的环境变量，避免 OpenAI 客户端初始化失败
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("OPENAI_BASE_URL", "https://test.example.com/v1")


@pytest.fixture
def temp_db_path(tmp_path, monkeypatch):
    """替换数据库路径为临时文件，并初始化表结构"""
    db_file = tmp_path / "test_agent.db"
    monkeypatch.setattr(database, "DB_PATH", str(db_file))
    database.init_db()
    return db_file


def test_init_db_creates_tables(temp_db_path):
    """验证 init_db 能成功创建所有表（包含评测相关表）"""
    conn = sqlite3.connect(str(temp_db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    expected = [
        "eval_datasets", "eval_task_results", "eval_tasks",
        "plan_actions", "plans", "platform_settings",
        "projects", "sessions",
    ]
    assert tables == expected


def test_projects_schema(temp_db_path):
    """校验 projects 表结构"""
    conn = sqlite3.connect(str(temp_db_path))
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(projects)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    conn.close()
    assert columns["id"] == "TEXT"
    assert columns["name"] == "TEXT"
    assert columns["workspace_path"] == "TEXT"
    assert columns["created_at"] == "TEXT"
    assert columns["description"] == "TEXT"


def test_sessions_foreign_key(temp_db_path):
    """校验 sessions 表定义了外键引用 projects"""
    conn = sqlite3.connect(str(temp_db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='sessions'")
    create_sql = cursor.fetchone()[0]
    conn.close()
    assert "FOREIGN KEY" in create_sql
    assert "REFERENCES projects" in create_sql


def test_plan_actions_foreign_key(temp_db_path):
    """校验 plan_actions 表定义了外键引用 plans"""
    conn = sqlite3.connect(str(temp_db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='plan_actions'")
    create_sql = cursor.fetchone()[0]
    conn.close()
    assert "FOREIGN KEY" in create_sql
    assert "REFERENCES plans" in create_sql


def test_eval_datasets_schema(temp_db_path):
    """校验 eval_datasets 表结构"""
    conn = sqlite3.connect(str(temp_db_path))
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(eval_datasets)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    conn.close()
    assert columns["id"] == "TEXT"
    assert columns["name"] == "TEXT"
    assert columns["created_at"] == "TEXT"
    assert columns["item_count"] == "INTEGER"
    assert columns["storage_path"] == "TEXT"


def test_eval_tasks_schema(temp_db_path):
    """校验 eval_tasks 表结构"""
    conn = sqlite3.connect(str(temp_db_path))
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(eval_tasks)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    conn.close()
    assert columns["id"] == "TEXT"
    assert columns["name"] == "TEXT"
    assert columns["dataset_id"] == "TEXT"
    assert columns["eval_method"] == "TEXT"
    assert columns["status"] == "TEXT"


def test_eval_task_results_schema(temp_db_path):
    """校验 eval_task_results 表结构"""
    conn = sqlite3.connect(str(temp_db_path))
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(eval_task_results)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    conn.close()
    assert columns["id"] == "TEXT"
    assert columns["task_id"] == "TEXT"
    assert columns["item_index"] == "INTEGER"
    assert columns["status"] == "TEXT"


def test_platform_settings_schema(temp_db_path):
    """校验 platform_settings 表结构"""
    conn = sqlite3.connect(str(temp_db_path))
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(platform_settings)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    conn.close()
    assert columns["key"] == "TEXT"
    assert columns["value"] == "TEXT"


def test_get_connection_commit(temp_db_path):
    """验证 get_connection 在正常退出时能成功提交数据"""
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO projects (id, name, workspace_path, created_at) VALUES (?,?,?,?)",
            ("p1", "test", "/tmp", "2026-01-01")
        )
    # 上下文退出后手动查询，确认已提交
    conn = sqlite3.connect(str(temp_db_path))
    row = conn.execute("SELECT id FROM projects WHERE id='p1'").fetchone()
    conn.close()
    assert row is not None


def test_get_connection_rollback(temp_db_path):
    """验证 get_connection 在异常时执行回滚"""
    with pytest.raises(ValueError):
        with database.get_connection() as conn:
            conn.execute(
                "INSERT INTO projects (id, name, workspace_path, created_at) VALUES (?,?,?,?)",
                ("p2", "rollback-test", "/tmp", "2026-01-01")
            )
            raise ValueError("trigger rollback")
    # 数据不应被写入
    conn = sqlite3.connect(str(temp_db_path))
    row = conn.execute("SELECT id FROM projects WHERE id='p2'").fetchone()
    conn.close()
    assert row is None


def test_row_factory(temp_db_path):
    """验证连接返回的行可以按列名访问"""
    with database.get_connection() as conn:
        conn.execute(
            "INSERT INTO projects (id, name, workspace_path, created_at) VALUES (?,?,?,?)",
            ("p3", "rowtest", "/tmp", "2026-01-01")
        )
        row = conn.execute("SELECT * FROM projects WHERE id='p3'").fetchone()
        assert row["name"] == "rowtest"
