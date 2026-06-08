# tests/test_platform_settings.py
"""测试 platform_settings 模块：Agent 配置的读写与合并逻辑。"""
from agent.backend.platform_settings import (
    get_agent_config,
    get_skills,
    get_tool_settings,
    set_agent_config,
)
import json
import os
import sqlite3
import sys
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 必须在导入 agent 任何模块之前设置假的环境变量
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("OPENAI_BASE_URL", "https://test.example.com/v1")


class TestGetAgentConfig:
    def test_returns_default_when_no_stored_value(self, monkeypatch):
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = None
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        monkeypatch.setattr(
            "agent.backend.platform_settings.get_connection", lambda: mock_conn
        )
        cfg = get_agent_config()
        assert "model" in cfg
        assert "version_label" in cfg

    def test_merges_stored_value(self, monkeypatch):
        stored = json.dumps({"model": "gpt-4o", "version_label": "v2"})
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"value": stored}
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        monkeypatch.setattr(
            "agent.backend.platform_settings.get_connection", lambda: mock_conn
        )
        cfg = get_agent_config()
        assert cfg["model"] == "gpt-4o"
        assert cfg["version_label"] == "v2"

    def test_handles_invalid_json_gracefully(self, monkeypatch):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"value": "not valid json!!!"}
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        monkeypatch.setattr(
            "agent.backend.platform_settings.get_connection", lambda: mock_conn
        )
        cfg = get_agent_config()
        assert "model" in cfg  # still returns defaults


class TestMissingPlatformSettingsTable:
    def test_reads_use_defaults_before_database_initialization(self, monkeypatch):
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = sqlite3.OperationalError("no such table: platform_settings")
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        monkeypatch.setattr(
            "agent.backend.platform_settings.get_connection", lambda: mock_conn
        )

        assert "model" in get_agent_config()
        assert all(get_tool_settings().values())
        assert get_skills() == []

    def test_other_database_errors_are_not_hidden(self, monkeypatch):
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = sqlite3.OperationalError("database is locked")
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        monkeypatch.setattr(
            "agent.backend.platform_settings.get_connection", lambda: mock_conn
        )

        with pytest.raises(sqlite3.OperationalError, match="database is locked"):
            get_tool_settings()


class TestSetAgentConfig:
    def test_sets_model(self, monkeypatch):
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = None
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        monkeypatch.setattr(
            "agent.backend.platform_settings.get_connection", lambda: mock_conn
        )
        result = set_agent_config({"model": "gpt-4-turbo"})
        assert result["model"] == "gpt-4-turbo"

    def test_sets_version_label(self, monkeypatch):
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = None
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        monkeypatch.setattr(
            "agent.backend.platform_settings.get_connection", lambda: mock_conn
        )
        result = set_agent_config({"version_label": "stable-v1"})
        assert result["version_label"] == "stable-v1"

    def test_merges_with_existing(self, monkeypatch):
        stored = json.dumps({"model": "gpt-4o", "version_label": "old"})
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"value": stored}
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        monkeypatch.setattr(
            "agent.backend.platform_settings.get_connection", lambda: mock_conn
        )
        result = set_agent_config({"model": "gpt-4-turbo"})
        assert result["model"] == "gpt-4-turbo"
        assert result["version_label"] == "old"

    def test_ignores_none_values(self, monkeypatch):
        stored = json.dumps({"model": "base", "version_label": "v1"})
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"value": stored}
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        monkeypatch.setattr(
            "agent.backend.platform_settings.get_connection", lambda: mock_conn
        )
        result = set_agent_config({"model": None, "version_label": None})
        assert result["model"] == "base"
        assert result["version_label"] == "v1"


class TestToolSettings:
    """测试 tool_settings 读写。"""

    def test_get_defaults(self, monkeypatch):
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = None
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        monkeypatch.setattr(
            "agent.backend.platform_settings.get_connection", lambda: mock_conn
        )
        tools = get_tool_settings()
        assert isinstance(tools, dict)
        assert tools.get("execute_bash") is True

    def test_merges_stored_tool_settings(self, monkeypatch):
        stored = json.dumps({"execute_bash": False, "read_file": True})
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"value": stored}
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        monkeypatch.setattr(
            "agent.backend.platform_settings.get_connection", lambda: mock_conn
        )
        tools = get_tool_settings()
        assert tools["execute_bash"] is False
        assert tools["read_file"] is True

    def test_invalid_json_returns_defaults(self, monkeypatch):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"value": "not-valid"}
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        monkeypatch.setattr(
            "agent.backend.platform_settings.get_connection", lambda: mock_conn
        )
        from agent.backend.platform_settings import get_tool_settings
        tools = get_tool_settings()
        assert "execute_bash" in tools


class TestSetToolSettings:
    def test_updates_settings(self, monkeypatch):
        mock_conn = MagicMock()
        stored = json.dumps({"execute_bash": True})
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"value": stored}
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        monkeypatch.setattr(
            "agent.backend.platform_settings.get_connection", lambda: mock_conn
        )
        from agent.backend.platform_settings import set_tool_settings
        result = set_tool_settings({"execute_bash": False})
        assert result["execute_bash"] is False

    def test_ignores_unknown_tool_names(self, monkeypatch):
        mock_conn = MagicMock()
        stored = json.dumps({"execute_bash": True})
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"value": stored}
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        monkeypatch.setattr(
            "agent.backend.platform_settings.get_connection", lambda: mock_conn
        )
        from agent.backend.platform_settings import set_tool_settings
        result = set_tool_settings({"unknown_tool": True})
        assert "unknown_tool" not in result


class TestIsToolEnabled:
    def test_enabled_by_default(self, monkeypatch):
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = None
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        monkeypatch.setattr(
            "agent.backend.platform_settings.get_connection", lambda: mock_conn
        )
        from agent.backend.platform_settings import is_tool_enabled
        assert is_tool_enabled("execute_bash") is True

    def test_disabled_tool(self, monkeypatch):
        stored = json.dumps({"execute_bash": False})
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"value": stored}
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        monkeypatch.setattr(
            "agent.backend.platform_settings.get_connection", lambda: mock_conn
        )
        from agent.backend.platform_settings import is_tool_enabled
        assert is_tool_enabled("execute_bash") is False

    def test_unknown_tool_returns_false(self, monkeypatch):
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = None
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        monkeypatch.setattr(
            "agent.backend.platform_settings.get_connection", lambda: mock_conn
        )
        from agent.backend.platform_settings import is_tool_enabled
        assert is_tool_enabled("nonexistent_tool") is False


class TestSkillsCRUD:
    def test_get_skills_empty(self, monkeypatch):
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = None
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        monkeypatch.setattr(
            "agent.backend.platform_settings.get_connection", lambda: mock_conn
        )
        from agent.backend.platform_settings import get_skills
        assert get_skills() == []

    def test_get_skills_with_data(self, monkeypatch):
        stored = json.dumps([{"id": "abc", "name": "test-skill", "content": "do something", "enabled": True}])
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"value": stored}
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        monkeypatch.setattr(
            "agent.backend.platform_settings.get_connection", lambda: mock_conn
        )
        from agent.backend.platform_settings import get_skills
        skills = get_skills()
        assert len(skills) == 1
        assert skills[0]["name"] == "test-skill"

    def test_get_skills_invalid_json(self, monkeypatch):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"value": "not-json"}
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        monkeypatch.setattr(
            "agent.backend.platform_settings.get_connection", lambda: mock_conn
        )
        from agent.backend.platform_settings import get_skills
        assert get_skills() == []

    def test_get_skills_not_list(self, monkeypatch):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"value": '{"not": "list"}'}
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        monkeypatch.setattr(
            "agent.backend.platform_settings.get_connection", lambda: mock_conn
        )
        from agent.backend.platform_settings import get_skills
        assert get_skills() == []

    def test_get_skills_skips_invalid_items(self, monkeypatch):
        stored = json.dumps([
            {"name": "", "content": ""},  # invalid - empty name/content
            "not_a_dict",  # invalid
            {"name": "valid", "content": "valid content"},
        ])
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"value": stored}
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        monkeypatch.setattr(
            "agent.backend.platform_settings.get_connection", lambda: mock_conn
        )
        from agent.backend.platform_settings import get_skills
        skills = get_skills()
        assert len(skills) == 1
        assert skills[0]["name"] == "valid"

    def test_create_skill_success(self, monkeypatch):
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = None
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        monkeypatch.setattr(
            "agent.backend.platform_settings.get_connection", lambda: mock_conn
        )
        from agent.backend.platform_settings import create_skill
        skill = create_skill({"name": "new-skill", "content": "do things", "enabled": True})
        assert skill["name"] == "new-skill"
        assert skill["content"] == "do things"
        assert "id" in skill

    def test_create_skill_empty_name_raises(self, monkeypatch):
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = None
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        monkeypatch.setattr(
            "agent.backend.platform_settings.get_connection", lambda: mock_conn
        )
        from agent.backend.platform_settings import create_skill
        with pytest.raises(ValueError, match="name and content"):
            create_skill({"name": "", "content": "x"})

    def test_create_skill_empty_content_raises(self, monkeypatch):
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = None
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        monkeypatch.setattr(
            "agent.backend.platform_settings.get_connection", lambda: mock_conn
        )
        from agent.backend.platform_settings import create_skill
        with pytest.raises(ValueError, match="name and content"):
            create_skill({"name": "x", "content": ""})

    def test_update_skill_not_found(self, monkeypatch):
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = None
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        monkeypatch.setattr(
            "agent.backend.platform_settings.get_connection", lambda: mock_conn
        )
        from agent.backend.platform_settings import update_skill
        with pytest.raises(KeyError):
            update_skill("nonexistent", {"name": "new-name"})

    def test_update_skill_partial(self, monkeypatch):
        stored = json.dumps([{"id": "sid1", "name": "old", "content": "old-content", "enabled": True}])
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"value": stored}
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        monkeypatch.setattr(
            "agent.backend.platform_settings.get_connection", lambda: mock_conn
        )
        from agent.backend.platform_settings import update_skill
        updated = update_skill("sid1", {"enabled": False})
        assert updated["enabled"] is False
        assert updated["name"] == "old"

    def test_update_skill_empty_name_raises(self, monkeypatch):
        stored = json.dumps([{"id": "sid1", "name": "old", "content": "c"}])
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"value": stored}
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        monkeypatch.setattr(
            "agent.backend.platform_settings.get_connection", lambda: mock_conn
        )
        from agent.backend.platform_settings import update_skill
        with pytest.raises(ValueError, match="name"):
            update_skill("sid1", {"name": ""})

    def test_delete_skill_not_found(self, monkeypatch):
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = None
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        monkeypatch.setattr(
            "agent.backend.platform_settings.get_connection", lambda: mock_conn
        )
        from agent.backend.platform_settings import delete_skill
        with pytest.raises(KeyError):
            delete_skill("nonexistent")

    def test_get_enabled_skills(self, monkeypatch):
        stored = json.dumps([
            {"id": "a", "name": "enabled1", "content": "c1", "enabled": True},
            {"id": "b", "name": "disabled1", "content": "c2", "enabled": False},
        ])
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"value": stored}
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.__exit__.return_value = None
        monkeypatch.setattr(
            "agent.backend.platform_settings.get_connection", lambda: mock_conn
        )
        from agent.backend.platform_settings import get_enabled_skills
        enabled = get_enabled_skills()
        assert len(enabled) == 1
        assert enabled[0]["name"] == "enabled1"
