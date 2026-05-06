# tests/test_eval_quality.py
"""测试 eval_quality 模块的纯函数：radar_vector、mean_radar、evaluation_result_to_dict 等。"""
import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent.backend.eval_quality import (
    build_radar_vector,
    mean_radar,
    _evaluation_result_to_dict,
    build_contexts_for_ragas,
    compute_ragas_scores,
    compute_judge_scores,
)


# ========== build_radar_vector ==========
class TestBuildRadarVector:
    def test_all_values_present(self):
        ragas = {"answer_relevancy": 0.8, "faithfulness": 0.9}
        judge = {"reasoning_quality": 8, "hallucination_severity": 2}
        runtime = {"tokens_total": 1000, "tool_success_rate": 0.95}
        security = {"risk_score": 3}

        vec = build_radar_vector(ragas, judge, runtime, security)

        assert vec["answer_relevancy"] == pytest.approx(0.8)
        assert vec["faithfulness"] == pytest.approx(0.9)
        assert vec["reasoning_quality"] == pytest.approx(0.8)  # 8/10
        assert vec["anti_hallucination"] == pytest.approx(1.0 - (2 - 1) / 9.0)
        assert vec["security_hygiene"] == pytest.approx(1.0 - 3 / 10.0)
        assert "tool_success" in vec
        assert "token_efficiency" in vec

    def test_all_none_values_returns_zeros(self):
        vec = build_radar_vector({}, {}, {"tokens_total": 0}, None)
        assert vec["answer_relevancy"] == 0.0
        assert vec["faithfulness"] == 0.0
        assert vec["reasoning_quality"] == 0.0
        assert vec["anti_hallucination"] == 0.0
        assert vec["security_hygiene"] == 1.0  # no risk → full score

    def test_security_high_risk(self):
        vec = build_radar_vector({}, {}, {"tokens_total": 0}, {"risk_score": 10})
        assert vec["security_hygiene"] == pytest.approx(0.0)

    def test_security_low_risk(self):
        vec = build_radar_vector({}, {}, {"tokens_total": 0}, {"risk_score": 1})
        assert vec["security_hygiene"] == pytest.approx(0.9)

    def test_hallucination_max_severity(self):
        judge = {"reasoning_quality": 5, "hallucination_severity": 10}
        vec = build_radar_vector({}, judge, {"tokens_total": 0}, None)
        assert vec["anti_hallucination"] == pytest.approx(0.0)

    def test_hallucination_min_severity(self):
        judge = {"reasoning_quality": 5, "hallucination_severity": 1}
        vec = build_radar_vector({}, judge, {"tokens_total": 0}, None)
        assert vec["anti_hallucination"] == pytest.approx(1.0)

    def test_security_not_dict(self):
        vec = build_radar_vector({}, {}, {"tokens_total": 0}, "not-dict")
        assert vec["security_hygiene"] == pytest.approx(1.0)

    def test_clamp_values_to_01(self):
        ragas = {"answer_relevancy": 2.5, "faithfulness": -0.5}
        vec = build_radar_vector(ragas, {}, {"tokens_total": 0}, None)
        assert 0.0 <= vec["answer_relevancy"] <= 1.0
        assert 0.0 <= vec["faithfulness"] <= 1.0


# ========== mean_radar ==========
class TestMeanRadar:
    def test_empty_vectors(self):
        assert mean_radar([]) == {}

    def test_single_vector(self):
        vectors = [{"a": 0.5, "b": 0.8}]
        result = mean_radar(vectors)
        assert result["a"] == pytest.approx(0.5)
        assert result["b"] == pytest.approx(0.8)

    def test_multiple_vectors(self):
        vectors = [
            {"a": 0.2, "b": 0.4},
            {"a": 0.8, "b": 1.0},
            {"a": 0.5, "b": 0.7},
        ]
        result = mean_radar(vectors)
        assert result["a"] == pytest.approx(0.5)
        assert result["b"] == pytest.approx(0.7)

    def test_missing_keys(self):
        vectors = [
            {"a": 1.0, "b": 0.5},
            {"a": 0.0},  # missing b
        ]
        result = mean_radar(vectors)
        assert result["a"] == pytest.approx(0.5)
        assert result["b"] == pytest.approx(0.5)  # only one value

    def test_with_key_order(self):
        vectors = [
            {"z": 1.0, "a": 0.5, "m": 0.3},
            {"a": 0.7, "z": 0.2},
        ]
        result = mean_radar(vectors, key_order=["a", "z", "m"])
        assert list(result.keys()) == ["a", "z", "m"]
        assert result["a"] == pytest.approx(0.6)
        assert result["z"] == pytest.approx(0.6)
        assert result["m"] == pytest.approx(0.3)


# ========== _evaluation_result_to_dict ==========
class TestEvaluationResultToDict:
    def test_dict_input(self):
        d = {"answer_relevancy": 0.5, "faithfulness": 0.8}
        assert _evaluation_result_to_dict(d) == d

    def test_object_with_scores_dict(self):
        class FakeResult:
            scores = {"answer_relevancy": 0.6}
        result = _evaluation_result_to_dict(FakeResult())
        assert result["answer_relevancy"] == 0.6

    def test_fallback_returns_empty(self):
        result = _evaluation_result_to_dict("nonsense")
        assert result == {}


# ========== build_contexts_for_ragas ==========
class TestBuildContextsForRagas:
    def test_returns_fallback_when_no_context(self):
        ctxs = build_contexts_for_ragas({}, "/fake/ws")
        assert len(ctxs) == 1
        assert "无可用的本地上下文" in ctxs[0]

    def test_includes_code_context(self):
        state = {"code_context": "def foo(): pass"}
        ctxs = build_contexts_for_ragas(state, "/fake/ws")
        assert "def foo(): pass" in ctxs[0]

    def test_strips_whitespace_code_context(self):
        state = {"code_context": "   "}
        ctxs = build_contexts_for_ragas(state, "/fake/ws")
        # whitespace-only → treated as empty → fallback
        assert any("无可用的本地上下文" in c for c in ctxs)


# ========== compute_ragas_scores (error paths only, no API) ==========
class TestComputeRagasScoresErrorPaths:
    def test_empty_question_or_answer(self):
        result = compute_ragas_scores("", "answer", ["ctx"])
        assert result["error"] == "empty_question_or_answer"

        result = compute_ragas_scores("question", "", ["ctx"])
        assert result["error"] == "empty_question_or_answer"

    def test_empty_contexts_still_works(self, monkeypatch):
        """Without API key, should return error before trying ragas."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        result = compute_ragas_scores("q", "a", [""])
        assert result["error"] is not None


# ========== compute_judge_scores (error paths only, no API) ==========
class TestComputeJudgeScoresErrorPaths:
    def test_missing_api_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        result = compute_judge_scores("task desc", "answer", ["ctx"])
        assert result["error"] == "OPENAI_API_KEY missing"

    def test_default_values(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        result = compute_judge_scores("task", "answer", [])
        assert result["reasoning_quality"] is None
        assert result["hallucination_severity"] is None
        assert result["comment"] == ""
