# tests/test_eval_scoring.py
"""测试 eval_scoring 模块：结果导向/过程导向评分判定与评测 prompt 构建。"""
from agent.backend.eval_scoring import (
    evaluate_result_oriented,
    evaluate_process_oriented,
    evaluate_combined,
    decide_passed,
    build_eval_prompt,
)
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestEvaluateResultOriented:
    def test_empty_answer_fails_when_expected_output_present(self):
        item = {"expected_output": "hello"}
        passed, detail = evaluate_result_oriented("", item)
        assert passed is False
        assert detail["expected_output_match"] is False

    def test_answer_contains_expected_output_case_insensitive(self):
        item = {"expected_output": "Hello World"}
        passed, detail = evaluate_result_oriented("say hello world everyone", item)
        assert passed is True
        assert detail["expected_output_match"] is True

    def test_answer_missing_expected_output(self):
        item = {"expected_output": "SUCCESS"}
        passed, detail = evaluate_result_oriented("some other text", item)
        assert passed is False
        assert detail["expected_output_match"] is False

    def test_no_expected_output_no_test_cases_passes(self):
        item = {}
        passed, detail = evaluate_result_oriented("anything", item)
        assert passed is True
        assert detail == {}

    def test_test_cases_all_pass(self):
        item = {
            "test_cases": [
                {"input": "", "expected": "foo"},
                {"input": "", "expected": "bar"},
            ]
        }
        passed, detail = evaluate_result_oriented("some foo and bar here", item)
        assert passed is True
        assert detail["test_case_0"] is True
        assert detail["test_case_1"] is True

    def test_test_cases_one_fails(self):
        item = {
            "test_cases": [
                {"input": "", "expected": "foo"},
                {"input": "", "expected": "missing"},
            ]
        }
        passed, detail = evaluate_result_oriented("only foo here", item)
        assert passed is False
        assert detail["test_case_0"] is True
        assert detail["test_case_1"] is False

    def test_test_case_empty_expected_skipped(self):
        item = {
            "test_cases": [
                {"input": "", "expected": ""},
            ]
        }
        passed, detail = evaluate_result_oriented("text", item)
        assert passed is True

    def test_expected_output_pass_then_test_case_fails(self):
        # expected_output matches, but test_case expects "missing" which is NOT in answer
        item = {
            "expected_output": "ok",
            "test_cases": [{"input": "", "expected": "not_present"}],
        }
        passed, detail = evaluate_result_oriented("ok is here", item)
        assert passed is False
        assert detail["expected_output_match"] is True
        assert detail["test_case_0"] is False

    def test_none_answer_treated_as_empty(self):
        item = {"expected_output": "x"}
        passed, detail = evaluate_result_oriented(None, item)
        assert passed is False


class TestEvaluateProcessOriented:
    def test_errors_present_fails(self):
        errors = [{"status": "error"}]
        trace = [{"phase": "planner"}, {"phase": "executor"}, {"phase": "reviewer"}]
        passed, detail = evaluate_process_oriented("answer", {}, errors, trace)
        assert passed is False
        assert detail["errors_count"] == 1

    def test_few_trace_steps_fails(self):
        passed, detail = evaluate_process_oriented("answer", {}, [], [{"phase": "planner"}])
        assert passed is False
        assert detail["trace_steps"] == 1

    def test_minimal_trace_no_errors_no_expected_passes(self):
        trace = [{"phase": "planner"}, {"phase": "executor"}]
        passed, detail = evaluate_process_oriented("answer", {}, [], trace)
        assert passed is True
        assert detail["trace_steps"] == 2
        assert detail["errors_count"] == 0

    def test_with_expected_output_present_correctly(self):
        trace = [{"phase": "planner"}, {"phase": "executor"}, {"phase": "reviewer"}]
        item = {"expected_output": "CORRECT"}
        passed, detail = evaluate_process_oriented("this is correct", item, [], trace)
        assert passed is True
        assert detail["errors_count"] == 0
        assert detail["trace_steps"] == 3
        assert "result_subcheck" in detail

    def test_with_expected_output_missing(self):
        trace = [{"phase": "planner"}, {"phase": "executor"}]
        item = {"expected_output": "MISSING_OUTPUT"}
        passed, detail = evaluate_process_oriented("none", item, [], trace)
        assert passed is False
        assert detail["result_subcheck"]["expected_output_match"] is False


class TestDecidePassed:
    def test_result_method_delegates(self):
        item = {"expected_output": "yes"}
        passed, detail = decide_passed("result", "yes indeed", item, [], [])
        assert passed is True
        assert detail["expected_output_match"] is True

    def test_process_method_delegates(self):
        trace = [{"phase": "p"}, {"phase": "e"}]
        passed, detail = decide_passed("process", "", {}, [], trace)
        assert passed is True
        assert detail["trace_steps"] == 2

    def test_unknown_method_defaults_to_result(self):
        item = {"expected_output": "x"}
        passed, _ = decide_passed("unknown_method", "x", item, [], [])
        assert passed is True


class TestBuildEvalPrompt:
    def test_basic_description(self):
        item = {"description": "Write a sort function"}
        prompt = build_eval_prompt(item)
        assert "Write a sort function" in prompt

    def test_with_expected_output(self):
        item = {"description": "Task", "expected_output": "sorted list"}
        prompt = build_eval_prompt(item)
        assert "Task" in prompt
        assert "sorted list" in prompt
        assert "评测说明" in prompt

    def test_with_test_cases(self):
        item = {
            "description": "Test task",
            "test_cases": [
                {"input": "3 numbers", "expected": "correct output"},
                {"input": "0 numbers", "expected": "empty result"},
            ],
        }
        prompt = build_eval_prompt(item)
        assert "Test task" in prompt
        assert "测试要点" in prompt
        assert "3 numbers" in prompt
        assert "correct output" in prompt
        assert "empty result" in prompt

    def test_full_item(self):
        item = {
            "description": "Build an API",
            "expected_output": "REST endpoints",
            "test_cases": [{"input": "GET /users", "expected": "200 OK"}],
        }
        prompt = build_eval_prompt(item)
        assert "Build an API" in prompt
        assert "REST endpoints" in prompt
        assert "GET /users" in prompt
        assert "200 OK" in prompt


class TestEvaluateCombined:
    """测试 combined 模式（结果+过程联合评估）。"""

    def test_both_pass(self):
        item = {"expected_output": "SUCCESS"}
        trace = [{"phase": "planner"}, {"phase": "executor"}]
        passed, detail = evaluate_combined("SUCCESS output", item, [], trace)
        assert passed is True
        assert detail["result_passed"] is True
        assert detail["process_passed"] is True

    def test_result_fails_process_passes(self):
        # Process passes when no expected_output and no errors and >= 2 trace steps
        trace = [{"phase": "planner"}, {"phase": "executor"}]
        passed, detail = evaluate_combined("any answer", {}, [], trace)
        assert passed is True
        assert detail["result_passed"] is True  # no expected_output → result passes
        assert detail["process_passed"] is True

    def test_result_passes_process_fails(self):
        item = {"expected_output": "found"}
        trace = [{"phase": "planner"}]  # only 1 step → process fails
        passed, detail = evaluate_combined("found", item, [], trace)
        assert passed is False
        assert detail["result_passed"] is True
        assert detail["process_passed"] is False

    def test_both_fail(self):
        item = {"expected_output": "X"}
        trace = [{"phase": "planner"}]
        passed, detail = evaluate_combined("Y", item, [{"error": True}], trace)
        assert passed is False
        assert detail["result_passed"] is False
        assert detail["process_passed"] is False


class TestDecidePassedCombined:
    """测试 decide_passed 分发到 combined 模式。"""

    def test_combined_method_delegates(self):
        item = {"expected_output": "yes"}
        trace = [{"phase": "p"}, {"phase": "e"}]
        passed, detail = decide_passed("combined", "yes answer", item, [], trace)
        assert passed is True
        assert "result_check" in detail
        assert "process_check" in detail

    def test_combined_method_fails(self):
        item = {"expected_output": "no_match"}
        trace = [{"phase": "p"}]
        passed, detail = decide_passed("combined", "nope", item, [{"error": "x"}], trace)
        assert passed is False
