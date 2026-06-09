# tests/test_config.py
import agent.backend.config as config
import os
import sys
import re
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestConfig:
    """验证 config.py 中所有常量的存在性与类型"""

    def test_model_is_string(self):
        assert isinstance(config.MODEL, str)
        assert len(config.MODEL) > 0

    def test_model_uses_env_or_default(self, monkeypatch):
        monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
        # Re-import to get the fresh value
        import importlib
        import agent.backend.config as cfg
        importlib.reload(cfg)
        expected = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        assert cfg.MODEL == expected

    def test_memory_file_is_string(self):
        assert isinstance(config.MEMORY_FILE, str)

    def test_trace_json_is_string(self):
        assert isinstance(config.TRACE_JSON, str)

    def test_trace_mermaid_is_string(self):
        assert isinstance(config.TRACE_MERMAID, str)

    def test_max_tool_output_positive_int(self):
        assert isinstance(config.MAX_TOOL_OUTPUT, int)
        assert config.MAX_TOOL_OUTPUT > 0

    def test_max_step_iterations_positive_int(self):
        assert isinstance(config.MAX_STEP_ITERATIONS, int)
        assert config.MAX_STEP_ITERATIONS > 0

    def test_max_reflections_positive_int(self):
        assert isinstance(config.MAX_REFLECTIONS, int)
        assert config.MAX_REFLECTIONS > 0

    def test_default_workspace_prefix_non_empty(self):
        assert isinstance(config.DEFAULT_WORKSPACE_PREFIX, str)
        assert len(config.DEFAULT_WORKSPACE_PREFIX) > 0

    def test_blocked_bash_patterns_is_list_of_strings(self):
        assert isinstance(config.BLOCKED_BASH_PATTERNS, list)
        for pattern in config.BLOCKED_BASH_PATTERNS:
            assert isinstance(pattern, str)
            # 简单检查是否可编译为正则
            try:
                re.compile(pattern)
            except re.error:
                pytest.fail(f"Invalid regex: {pattern}")

    def test_blocked_patterns_non_empty(self):
        assert len(config.BLOCKED_BASH_PATTERNS) > 0

    # ---------- get_effective_model ----------
    def test_get_effective_model_uses_env_default(self, monkeypatch):
        """无覆盖、无平台设置时回退到 MODEL"""
        from agent.backend.config import get_effective_model, _eval_model_override

        # Reset eval model override
        monkeypatch.setattr(
            "agent.backend.config._eval_model_override",
            type(_eval_model_override)("eval_model_override", default=None),
        )
        monkeypatch.setattr("agent.backend.config.MODEL", "gpt-4o-mini")
        # Mock the platform_settings.get_agent_config which is lazily imported
        monkeypatch.setattr(
            "agent.backend.platform_settings.get_agent_config",
            lambda: {"model": "", "version_label": ""},
        )
        result = get_effective_model()
        assert result == "gpt-4o-mini"

    def test_eval_model_context_sets_and_resets(self):
        from agent.backend.config import eval_model_context, _eval_model_override

        assert _eval_model_override.get() is None
        with eval_model_context("gpt-4-turbo"):
            assert _eval_model_override.get() == "gpt-4-turbo"
        assert _eval_model_override.get() is None

    def test_eval_model_context_empty_string_is_noop(self):
        from agent.backend.config import eval_model_context, _eval_model_override

        assert _eval_model_override.get() is None
        with eval_model_context(""):
            assert _eval_model_override.get() is None
        assert _eval_model_override.get() is None

    def test_eval_model_context_none_is_noop(self):
        from agent.backend.config import eval_model_context, _eval_model_override

        assert _eval_model_override.get() is None
        with eval_model_context(None):
            assert _eval_model_override.get() is None
        assert _eval_model_override.get() is None

    def test_get_effective_model_platform_settings_error(self, monkeypatch):
        """平台设置抛出异常时回退到 MODEL。"""
        from agent.backend.config import get_effective_model, _eval_model_override

        monkeypatch.setattr(
            "agent.backend.config._eval_model_override",
            type(_eval_model_override)("eval_model_override", default=None),
        )
        monkeypatch.setattr("agent.backend.config.MODEL", "gpt-4o-mini")
        monkeypatch.setattr(
            "agent.backend.platform_settings.get_agent_config",
            lambda: (_ for _ in ()).throw(Exception("oops")),
        )
        result = get_effective_model()
        assert result == "gpt-4o-mini"

    def test_get_effective_model_with_platform_setting(self, monkeypatch):
        """平台设置提供有效模型时使用平台设置。"""
        from agent.backend.config import get_effective_model, _eval_model_override

        monkeypatch.setattr(
            "agent.backend.config._eval_model_override",
            type(_eval_model_override)("eval_model_override", default=None),
        )
        monkeypatch.setattr(
            "agent.backend.platform_settings.get_agent_config",
            lambda: {"model": "platform-model", "version_label": "v3"},
        )
        result = get_effective_model()
        assert result == "platform-model"

    def test_get_effective_model_eval_override_takes_priority(self, monkeypatch):
        """评测覆盖优先于平台设置。"""
        from agent.backend.config import get_effective_model, eval_model_context

        monkeypatch.setattr(
            "agent.backend.platform_settings.get_agent_config",
            lambda: {"model": "platform-model", "version_label": "v3"},
        )
        with eval_model_context("eval-override-model"):
            result = get_effective_model()
            assert result == "eval-override-model"
