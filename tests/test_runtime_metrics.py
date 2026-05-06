# tests/test_runtime_metrics.py
"""测试 runtime_metrics 模块：Token、工具调用统计与归一化。"""
import os
import sys
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent.backend.runtime_metrics import (
    ensure_runtime_metrics,
    record_llm_usage,
    record_tool_call,
    summarize_runtime_metrics,
    radar_tool_success_norm,
    radar_token_efficiency_norm,
)


class TestEnsureRuntimeMetrics:
    def test_empty_state_initialized(self):
        # ensure_runtime_metrics checks `if not state: return`, so empty
        # dict is skipped. Using a state with at least one key to trigger init.
        state = {"_dummy": True}
        ensure_runtime_metrics(state)
        assert "runtime_metrics" in state
        assert state["runtime_metrics"]["tokens"]["total"] == 0
        assert state["runtime_metrics"]["llm_calls"] == 0
        assert state["runtime_metrics"]["tool_calls"] == []

    def test_existing_metrics_preserved(self):
        state = {"runtime_metrics": {"tokens": {"total": 100}, "custom": "data"}}
        ensure_runtime_metrics(state)
        assert state["runtime_metrics"]["tokens"]["total"] == 100
        assert state["runtime_metrics"]["custom"] == "data"

    def test_none_state_does_nothing(self):
        ensure_runtime_metrics(None)  # should not raise


class TestRecordLlmUsage:
    def test_records_token_usage(self):
        state = {"_dummy": True}
        # Use a simple object with attributes instead of MagicMock
        class Usage:
            prompt_tokens = 50
            completion_tokens = 30
            total_tokens = 80
        class Response:
            usage = Usage()
        mock_resp = Response()

        record_llm_usage(state, mock_resp)
        rm = state["runtime_metrics"]
        assert rm["tokens"]["prompt"] == 50
        assert rm["tokens"]["completion"] == 30
        assert rm["tokens"]["total"] == 80
        assert rm["llm_calls"] == 1

    def test_multiple_calls_accumulate(self):
        state = {"_dummy": True}
        class Usage:
            prompt_tokens = 10
            completion_tokens = 5
            total_tokens = 15
        class Response:
            usage = Usage()
        mock_resp = Response()

        record_llm_usage(state, mock_resp)
        record_llm_usage(state, mock_resp)
        rm = state["runtime_metrics"]
        assert rm["tokens"]["total"] == 30
        assert rm["llm_calls"] == 2

    def test_no_usage_does_nothing(self):
        state = {"_dummy": True}
        class Response:
            usage = None
        mock_resp = Response()
        record_llm_usage(state, mock_resp)
        rm = state["runtime_metrics"]
        assert rm["tokens"]["total"] == 0
        assert rm["llm_calls"] == 0

    def test_none_state_does_nothing(self):
        record_llm_usage(None, MagicMock())  # should not raise


class TestRecordToolCall:
    def test_records_successful_tool_call(self):
        state = {"_dummy": True}
        record_tool_call(state, "execute_bash", True, 123.456)
        tc = state["runtime_metrics"]["tool_calls"]
        assert len(tc) == 1
        assert tc[0]["name"] == "execute_bash"
        assert tc[0]["ok"] is True
        assert tc[0]["latency_ms"] == 123.456

    def test_records_failed_tool_call(self):
        state = {"_dummy": True}
        record_tool_call(state, "read_file", False, 50.0)
        tc = state["runtime_metrics"]["tool_calls"]
        assert tc[0]["ok"] is False
        assert tc[0]["latency_ms"] == 50.0

    def test_multiple_tool_calls_accumulate(self):
        state = {"_dummy": True}
        record_tool_call(state, "write_file", True, 10)
        record_tool_call(state, "execute_bash", False, 20)
        assert len(state["runtime_metrics"]["tool_calls"]) == 2

    def test_none_state_does_nothing(self):
        record_tool_call(None, "tool", True, 1.0)  # should not raise


class TestSummarizeRuntimeMetrics:
    def test_empty_metrics(self):
        result = summarize_runtime_metrics({})
        assert result["tokens_total"] == 0
        assert result["llm_calls"] == 0
        assert result["tool_success_rate"] is None
        assert result["tool_avg_latency_ms"] is None

    def test_none_input(self):
        result = summarize_runtime_metrics(None)
        assert result["tokens_total"] == 0

    def test_full_summary(self):
        blob = {
            "tokens": {"prompt": 100, "completion": 50, "total": 150},
            "llm_calls": 3,
            "tool_calls": [
                {"name": "read_file", "ok": True, "latency_ms": 100},
                {"name": "write_file", "ok": True, "latency_ms": 200},
                {"name": "execute_bash", "ok": False, "latency_ms": 50},
            ],
        }
        result = summarize_runtime_metrics(blob)
        assert result["tokens_total"] == 150
        assert result["tokens_prompt"] == 100
        assert result["tokens_completion"] == 50
        assert result["llm_calls"] == 3
        assert result["tool_success_rate"] == pytest.approx(2 / 3)
        assert result["tool_avg_latency_ms"] == pytest.approx(350 / 3)
        assert result["tool_events_count"] == 3
        assert len(result["tool_counts_by_name"]) == 3

    def test_tool_counts_by_name(self):
        blob = {
            "tokens": {"total": 100},
            "llm_calls": 1,
            "tool_calls": [
                {"name": "read_file", "ok": True, "latency_ms": 10},
                {"name": "read_file", "ok": False, "latency_ms": 20},
            ],
        }
        result = summarize_runtime_metrics(blob)
        counts = result["tool_counts_by_name"]
        assert counts["read_file"]["count"] == 2
        assert counts["read_file"]["ok"] == 1


class TestRadarNormFunctions:
    def test_radar_tool_success_norm_perfect(self):
        assert radar_tool_success_norm({"tool_success_rate": 1.0}) == 1.0

    def test_radar_tool_success_norm_failure(self):
        assert radar_tool_success_norm({"tool_success_rate": 0.0}) == 0.0

    def test_radar_tool_success_norm_none_defaults_to_1(self):
        assert radar_tool_success_norm({}) == 1.0

    def test_radar_token_efficiency_norm_zero_tokens(self):
        assert radar_token_efficiency_norm({"tokens_total": 0}) == 1.0

    def test_radar_token_efficiency_norm_some_tokens(self):
        val = radar_token_efficiency_norm({"tokens_total": 2000})
        assert 0.0 <= val <= 1.0

    def test_radar_token_efficiency_norm_high_tokens(self):
        val = radar_token_efficiency_norm({"tokens_total": 50000})
        assert val < 1.0
