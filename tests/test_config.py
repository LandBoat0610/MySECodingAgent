# tests/test_config.py
import os
import sys
import re
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import agent.backend.config as config


class TestConfig:
    """验证 config.py 中所有常量的存在性与类型"""

    def test_model_default_value(self):
        assert config.MODEL == os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

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