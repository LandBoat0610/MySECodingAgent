"""
跨对话记忆与上下文工程模块测试。
"""

import os
import pytest

os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("OPENAI_BASE_URL", "https://test.example.com/v1")

from agent.backend import database  # noqa: E402
from agent.backend.database import init_db  # noqa: E402


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """替换数据库路径为临时文件，并初始化表结构。"""
    db_file = tmp_path / "test_session_manager.db"
    monkeypatch.setattr(database, "DB_PATH", str(db_file))
    init_db()
    return db_file


class TestContextFormat:
    """测试 get_memory_context 返回标准格式。"""

    def test_returns_standard_keys(self, temp_db):
        from agent.backend.session_manager import get_memory_context
        ctx = get_memory_context("proj_test", "sess_test")
        assert isinstance(ctx, dict)
        for key in (
            "session_summary",
            "project_memory",
            "user_preferences",
            "relevant_history",
            "context_budget",
        ):
            assert key in ctx
        assert ctx["context_budget"] > 0

    def test_no_project_returns_empty(self, temp_db):
        from agent.backend.session_manager import get_memory_context
        ctx = get_memory_context("nonexistent_project")
        assert ctx["session_summary"] == ""
        assert ctx["project_memory"] == ""
        assert ctx["user_preferences"] == ""
        assert isinstance(ctx["relevant_history"], list)


class TestProjectMemory:
    """测试项目记忆读写。"""

    def test_save_and_read(self, temp_db):
        from agent.backend.session_manager import save_project_memory, get_project_memory
        save_project_memory("proj_1", "start_cmd", "uvicorn agent.main:app", "commands")
        mem = get_project_memory("proj_1")
        assert "start_cmd" in mem

    def test_update_existing(self, temp_db):
        from agent.backend.session_manager import save_project_memory, get_project_memory
        save_project_memory("proj_1", "test_cmd", "pytest -v", "commands")
        save_project_memory("proj_1", "test_cmd", "pytest -q", "commands")
        mem = get_project_memory("proj_1")
        assert "pytest -q" in mem

    def test_multiple_entries(self, temp_db):
        from agent.backend.session_manager import save_project_memory, list_project_memory
        save_project_memory("proj_2", "entry_a", "value_a")
        save_project_memory("proj_2", "entry_b", "value_b", "known_issues")
        entries = list_project_memory("proj_2")
        assert len(entries) >= 2

    def test_list_empty_project(self, temp_db):
        from agent.backend.session_manager import list_project_memory
        entries = list_project_memory("empty_proj_123")
        assert isinstance(entries, list)


class TestUserPreferences:
    """测试用户偏好读写。"""

    def test_save_and_read(self, temp_db):
        from agent.backend.session_manager import save_user_preference, get_user_preferences
        save_user_preference("confirm_commands", "true")
        prefs = get_user_preferences()
        assert "confirm_commands" in prefs

    def test_list_formatted(self, temp_db):
        from agent.backend.session_manager import save_user_preference, list_user_preferences
        save_user_preference("code_style", "PEP8")
        prefs_list = list_user_preferences()
        assert any(p["key"] == "code_style" for p in prefs_list)


class TestSessionSummary:
    """测试会话摘要功能。"""

    def test_empty_session(self, temp_db):
        from agent.backend.session_manager import get_session_summary
        summary = get_session_summary("nonexistent_session")
        assert summary == ""


class TestRelevantHistory:
    """测试历史对话检索。"""

    def test_empty_history(self, temp_db):
        from agent.backend.session_manager import get_relevant_history
        history = get_relevant_history("proj_no_history")
        assert isinstance(history, list)

    def test_with_query(self, temp_db):
        from agent.backend.session_manager import get_relevant_history
        history = get_relevant_history("proj_test", "前端")
        assert isinstance(history, list)


class TestHelpers:
    """测试内部辅助函数（不需要数据库）。"""

    def test_shorten_short_text(self):
        from agent.backend.session_manager import _shorten
        result = _shorten("短文本", 100)
        assert result == "短文本"

    def test_shorten_long_text(self):
        from agent.backend.session_manager import _shorten
        long_text = "这是一段很长的文本。" * 20
        result = _shorten(long_text, 100)
        assert len(result) <= 103

    def test_keyword_score_full_match(self):
        from agent.backend.session_manager import _keyword_score
        score = _keyword_score("前端 bug", "这个前端有一个 bug 需要修复")
        assert score == 1.0

    def test_keyword_score_no_match(self):
        from agent.backend.session_manager import _keyword_score
        score = _keyword_score("数据库", "这是一个前端问题")
        assert score == 0.0

    def test_keyword_score_partial(self):
        from agent.backend.session_manager import _keyword_score
        score = _keyword_score("前端 后端", "这是一个前端问题")
        assert 0.0 < score < 1.0


class TestBackwardCompat:
    """测试对现有数据库的兼容性。"""

    def test_init_db_idempotent(self, temp_db):
        init_db()
        init_db()
        init_db()  # 三次调用验证幂等性

    def test_new_tables_exist(self, temp_db):
        import sqlite3
        conn = sqlite3.connect(str(temp_db))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        assert "project_memory" in tables
        assert "user_preferences" in tables
