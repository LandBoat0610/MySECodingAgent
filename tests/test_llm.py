# tests/test_llm.py
from agent.backend.llm import (
    build_system_prompt,
    create_plan,
    infer_coding_targets,
    extract_code_context,
)
import os
import sys
from pathlib import Path
import pytest
from unittest.mock import MagicMock

# 必须在导入 agent 任何模块之前设置假的环境变量，避免 OpenAI 客户端初始化失败
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("OPENAI_BASE_URL", "https://test.example.com/v1")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


# ---------- Fixtures ----------
@pytest.fixture
def mock_prompts_config():
    """模拟 prompts.yaml 内容，避免读取真实文件"""
    return {
        "system_prompt": {
            "role": "You are a test agent.",
            "principles": "Be helpful.",
            "constraints": "Stay in sandbox.",
        },
        "infer_targets_prompt": {
            "system": "Infer targets.",
            "template": "Task:\n{user_task}",
        },
    }


@pytest.fixture
def mock_openai_response():
    """创建一个模拟的 OpenAI 聊天补全响应"""
    mock_resp = MagicMock()
    mock_choice = MagicMock()
    mock_message = MagicMock()
    mock_message.content = '{"key": "value"}'
    mock_choice.message = mock_message
    mock_resp.choices = [mock_choice]
    return mock_resp


# ---------- Tests ----------
class TestBuildSystemPrompt:
    def test_build_with_valid_prompts(self, monkeypatch, mock_prompts_config):
        monkeypatch.setattr("agent.backend.llm.load_prompts", lambda: mock_prompts_config)
        result = build_system_prompt("memory text", "/workspace")
        assert "You are a test agent." in result
        assert "Be helpful." in result
        assert "/workspace" in result
        assert "memory text" in result

    def test_build_with_failed_load(self, monkeypatch):
        def fake_load():
            raise FileNotFoundError("no file")
        monkeypatch.setattr("agent.backend.llm.load_prompts", fake_load)
        result = build_system_prompt("mem", "/ws")
        assert "Agent-Plus" in result or "coding agent" in result.lower()
        assert "/ws" in result


class TestCreatePlan:
    def test_normal_plan(self, monkeypatch):
        def mock_llm_json(system, user, state=None):
            return {"steps": ["Step 1", "Step 2"]}
        monkeypatch.setattr("agent.backend.llm.llm_json", mock_llm_json)
        steps = create_plan("task", "memory", [], {})
        assert steps == ["Step 1", "Step 2"]

    def test_plan_clamps_to_max_steps(self, monkeypatch):
        def mock_llm_json(system, user, state=None):
            return {"difficulty": "hard", "steps": [f"Step {i}" for i in range(1, 22)]}
        monkeypatch.setattr("agent.backend.llm.llm_json", mock_llm_json)
        state = {}
        steps = create_plan("task", "", [], state)
        assert steps == [f"Step {i}" for i in range(1, 21)]
        assert state["task_difficulty"] == "hard"

    def test_empty_steps_fallback(self, monkeypatch):
        def mock_llm_json(system, user, state=None):
            return {"steps": []}
        monkeypatch.setattr("agent.backend.llm.llm_json", mock_llm_json)
        steps = create_plan("task", "", [], {})
        assert steps == ["task"]

    def test_llm_error_fallback(self, monkeypatch):
        def mock_llm_json(system, user, state=None):
            raise Exception("API down")
        monkeypatch.setattr("agent.backend.llm.llm_json", mock_llm_json)
        steps = create_plan("task", "", [], {})
        assert steps == ["task"]


class TestInferCodingTargets:
    def test_normal_inference(self, tmp_path, monkeypatch):
        workspace = str(tmp_path)

        def mock_llm_json(system, user, state=None):
            return {"target_file": "src/app.py", "run_command": "python src/app.py"}

        monkeypatch.setattr("agent.backend.llm.llm_json", mock_llm_json)
        result = infer_coding_targets("build a web app", workspace, [], {})
        # 跨平台比较路径（在 Windows 下可能会转换成反斜杠）
        assert Path(result["target_file"]) == Path("src/app.py")
        assert result["run_command"] == "python src/app.py"

    def test_prompt_load_failure(self, tmp_path, monkeypatch):
        workspace = str(tmp_path)

        def mock_llm_json(system, user, state=None):
            return {"target_file": "fallback.py", "run_command": "python fallback.py"}

        monkeypatch.setattr("agent.backend.llm.llm_json", mock_llm_json)
        monkeypatch.setattr("agent.backend.llm.load_prompts", MagicMock(side_effect=Exception("no config")))
        result = infer_coding_targets("task", workspace, [], {})
        assert Path(result["target_file"]) == Path("fallback.py")

    def test_llm_error_uses_fallback(self, tmp_path, monkeypatch):
        workspace = str(tmp_path)

        def mock_llm_json(system, user, state=None):
            raise Exception("fail")

        monkeypatch.setattr("agent.backend.llm.llm_json", mock_llm_json)
        result = infer_coding_targets("task", workspace, [], {})
        assert Path(result["target_file"]) == Path("main.py")
        assert result["run_command"] == "python main.py"


class TestExtractCodeContext:
    def test_existing_file(self, tmp_path, monkeypatch):
        workspace = str(tmp_path)
        file_path = tmp_path / "code.py"
        file_path.write_text("print('hello')", encoding="utf-8")
        monkeypatch.setattr("agent.backend.llm.resolve_workspace_path", lambda ws, p: str(file_path))
        result = extract_code_context("code.py", workspace)
        assert "print('hello')" in result

    def test_missing_file(self, tmp_path):
        workspace = str(tmp_path)
        result = extract_code_context("missing.py", workspace)
        assert "unavailable" in result or "error" in result.lower()

class TestBuildExecutorPrompt:
    def test_build_with_step_info(self, monkeypatch):
        monkeypatch.setattr("agent.backend.llm.load_prompts", lambda: {
            "executor_prompt": {
                "system": "Executor system.",
                "template": "STEP {step_id}/{total_steps}\nGoal: {step_goal}\nType: {task_type}",
            }
        })
        state = {
            "task_type": "bug_fix", "task_difficulty": "medium",
            "acceptance_criteria": ["Test passes"],
            "codebase_summary": "Project", "retrieved_context": [], "tool_history": [],
        }
        current_step = {"goal": "Fix the bug", "verification": "Run pytest"}
        from agent.backend.llm import build_executor_prompt
        result = build_executor_prompt(current_step, 1, 3, state)
        assert "Fix the bug" in result
        assert "bug_fix" in result

class TestBuildVerifierPrompt:
    def test_build_verifier_prompt(self, monkeypatch):
        monkeypatch.setattr("agent.backend.llm.load_prompts", lambda: {
            "verifier_prompt": {
                "system": "Verifier system.",
                "template": "Step: {step_goal}\nStatus: {tool_status}",
            }
        })
        state = {
            "task_type": "bug_fix", "task_difficulty": "medium",
            "acceptance_criteria": ["Test passes"],
            "current_task_index": 1, "modified_files": ["main.py"],
            "last_tool_result": {"status": "success"},
            "last_execution": {"returncode": 0},
        }
        from agent.backend.llm import build_verifier_prompt
        result = build_verifier_prompt({"goal": "Fix bug"}, state)
        assert "Fix bug" in result

class TestBuildFinalSummary:
    def test_fallback_summary(self):
        from agent.backend.llm import _fallback_summary
        state = {"task": "Fix bug", "task_type": "bug_fix", "status": "completed",
                 "modified_files": ["main.py"], "used_tools": ["read_file"]}
        result = _fallback_summary(state)
        assert "bug_fix" in result

    def test_build_final_summary_llm_error(self, monkeypatch):
        monkeypatch.setattr("agent.backend.llm.load_prompts", lambda: {
            "final_summary_prompt": {"system": "S", "template": "Task: {task}"}
        })
        monkeypatch.setattr("agent.backend.llm._get_client", __import__("unittest").mock.MagicMock(side_effect=Exception("API error")))
        from agent.backend.llm import build_final_summary
        state = {"task": "Fix bug", "task_type": "bug_fix", "status": "completed",
                 "modified_files": ["main.py"], "used_tools": ["read_file"],
                 "trace": [], "current_plan": [{"status": "done"}],
                 "verification_results": [], "result_history": []}
        result = build_final_summary(state)
        assert "bug_fix" in result or "main.py" in result
