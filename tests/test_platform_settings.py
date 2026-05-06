# tests/test_platform_settings.py
"""测试 platform_settings 模块：Agent 配置的读写与合并逻辑。"""
import json
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 必须在导入 agent 任何模块之前设置假的环境变量
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("OPENAI_BASE_URL", "https://test.example.com/v1")

from agent.backend.platform_settings import (
    get_agent_config,
    set_agent_config,
    AGENT_CONFIG_KEY,
)


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
