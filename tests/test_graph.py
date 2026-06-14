# tests/test_graph.py
from agent.backend.state import AgentState
from agent.backend.graph import (
    planner_node,
    executor_node,
    check_result_node,
    modify_code_node,
    finalize_node,
    next_step_node,
    route_after_check,
    build_graph,
)
import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 必须在导入 agent 任何模块之前设置假的环境变量，避免 OpenAI 客户端初始化失败
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("OPENAI_BASE_URL", "https://test.example.com/v1")


# ================== Fixtures ==================
@pytest.fixture
def base_state() -> AgentState:
    """提供一个最小可用的状态字典"""
    return {
        "task": "test task",
        "messages": [],
        "task_list": ["step1", "step2"],
        "current_task_index": 0,
        "current_task": "step1",
        "code_context": "print('ok')",
        "target_file": "main.py",
        "run_command": "python main.py",
        "last_tool_result": {},
        "last_execution": {},
        "errors": [],
        "reflections": 0,
        "trace": [],
        "memory": "",
        "workspace_dir": "/fake/workspace",
        "final_answer": "",
        "status": "init",
        "used_tools": [],
        "result_history": [],
        "project_root": "",
        "modified_files": [],
    }


# ================== Planner Node ==================
class TestPlannerNode:
    def test_planner_normal(self, monkeypatch, base_state):
        # mock create_plan, infer_coding_targets, extract_code_context
        def mock_create_plan(task, memory, trace, state=None):
            return ["step_a", "step_b"]

        def mock_infer_targets(task, ws, trace, state=None):
            return {"target_file": "t.py", "run_command": "python t.py"}

        def mock_extract(target, ws):
            return "code"
        monkeypatch.setattr("agent.backend.graph.create_plan", mock_create_plan)
        monkeypatch.setattr("agent.backend.graph.infer_coding_targets", mock_infer_targets)
        monkeypatch.setattr("agent.backend.graph.extract_code_context", mock_extract)

        new_state = planner_node(base_state)
        assert new_state["task_list"] == ["step_a", "step_b"]
        assert new_state["current_task"] == "step_a"
        assert new_state["target_file"] == "t.py"
        assert new_state["run_command"] == "python t.py"
        assert new_state["code_context"] == "code"


# ================== Executor Node ==================
class TestExecutorNode:
    def test_rag_trigger_detects_chinese_knowledge_base_task(self):
        from agent.backend.graph import _task_should_use_rag

        assert _task_should_use_rag("根据项目知识库回答：唯一发布口令是什么？") is True

    def test_rag_trigger_skips_simple_math(self):
        from agent.backend.graph import _task_should_use_rag

        assert _task_should_use_rag("请直接计算 12 × 13，只返回结果。") is False

    def test_executor_no_tool_calls(self, monkeypatch, base_state):
        """当 LLM 返回纯文本（不调用工具）时，直接结束步骤"""
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Step completed."
        mock_message.tool_calls = None
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        monkeypatch.setattr("agent.backend.graph.client", mock_client)
        monkeypatch.setattr("agent.backend.graph.build_system_prompt", lambda mem, ws: "sys")
        monkeypatch.setattr("agent.backend.graph.tools_module", MagicMock())

        state = base_state.copy()
        new_state = executor_node(state)
        assert new_state["last_tool_result"]["status"] == "success"
        assert "Step completed." in new_state["last_tool_result"]["output"]

    def test_executor_with_tool_call_write_file(self, monkeypatch, base_state):
        """模拟调用 write_file 工具并记录 modified_files（仅执行一次）"""
        # 第一次 LLM 响应：包含一个 write_file 工具调用
        tool_call = MagicMock()
        tool_call.id = "call_1"
        tool_func = MagicMock()
        tool_func.name = "write_file"
        tool_func.arguments = '{"path": "test.py", "content": "x=1"}'
        tool_call.function = tool_func

        mock_message_tool = MagicMock()
        mock_message_tool.tool_calls = [tool_call]
        mock_message_tool.content = None

        # 第二次 LLM 响应：纯文本，无工具调用，表示步骤完成
        mock_message_text = MagicMock()
        mock_message_text.tool_calls = None
        mock_message_text.content = "Step finished."

        mock_choice1 = MagicMock()
        mock_choice1.message = mock_message_tool
        mock_response1 = MagicMock()
        mock_response1.choices = [mock_choice1]

        mock_choice2 = MagicMock()
        mock_choice2.message = mock_message_text
        mock_response2 = MagicMock()
        mock_response2.choices = [mock_choice2]

        mock_client = MagicMock()
        # side_effect 依次返回两次不同的响应
        mock_client.chat.completions.create.side_effect = [mock_response1, mock_response2]

        monkeypatch.setattr("agent.backend.graph.client", mock_client)
        monkeypatch.setattr("agent.backend.graph.build_system_prompt", lambda mem, ws: "sys")

        def mock_write_file(path, content):
            return json.dumps({"status": "success", "output": "written", "path": path})
        monkeypatch.setattr("agent.backend.graph.available_functions", {"write_file": mock_write_file})
        monkeypatch.setattr("agent.backend.graph.parse_tool_arguments", lambda raw: json.loads(raw))

        state = base_state.copy()
        new_state = executor_node(state)

        # 应该只记录了一次文件修改
        assert new_state["modified_files"] == ["test.py"]
        # 最终 last_tool_result 应该是纯文本内容输出（来自第二轮）
        assert new_state["last_tool_result"]["status"] == "success"
        assert "Step finished." in new_state["last_tool_result"]["output"]

    def test_executor_tool_error_stops(self, monkeypatch, base_state):
        """工具返回 error 时，executor 应中断并记录错误"""
        tool_call = MagicMock()
        tool_call.id = "call_2"
        tool_func = MagicMock()
        tool_func.name = "execute_bash"
        tool_func.arguments = '{"command": "fail"}'
        tool_call.function = tool_func

        mock_message = MagicMock()
        mock_message.tool_calls = [tool_call]
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        monkeypatch.setattr("agent.backend.graph.client", mock_client)
        monkeypatch.setattr("agent.backend.graph.build_system_prompt", lambda mem, ws: "sys")

        def mock_bash(command):
            return json.dumps({"status": "error", "output": "failed", "returncode": 1})
        monkeypatch.setattr("agent.backend.graph.available_functions", {"execute_bash": mock_bash})
        monkeypatch.setattr("agent.backend.graph.parse_tool_arguments", lambda raw: json.loads(raw))

        state = base_state.copy()
        new_state = executor_node(state)
        assert len(new_state["errors"]) == 1
        assert new_state["errors"][0]["status"] == "error"

    def test_executor_hard_task_uses_dynamic_iteration_limit(self, monkeypatch, base_state):
        """hard 任务应允许超过默认 5 轮工具循环"""
        tool_call = MagicMock()
        tool_call.id = "call_hard"
        tool_func = MagicMock()
        tool_func.name = "read_file"
        tool_func.arguments = '{"path": "a.py"}'
        tool_call.function = tool_func

        mock_message_tool = MagicMock()
        mock_message_tool.tool_calls = [tool_call]
        mock_message_tool.content = None

        mock_message_text = MagicMock()
        mock_message_text.tool_calls = None
        mock_message_text.content = "Finished after many reads."

        tool_response = MagicMock()
        tool_response.choices = [MagicMock(message=mock_message_tool)]
        text_response = MagicMock()
        text_response.choices = [MagicMock(message=mock_message_text)]

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [tool_response] * 6 + [text_response]
        monkeypatch.setattr("agent.backend.graph.client", mock_client)
        monkeypatch.setattr("agent.backend.graph.build_system_prompt", lambda mem, ws: "sys")
        monkeypatch.setattr(
            "agent.backend.graph.available_functions",
            {"read_file": lambda path: json.dumps({"status": "success", "output": "content", "path": path})},
        )
        monkeypatch.setattr("agent.backend.graph.parse_tool_arguments", lambda raw: json.loads(raw))

        state = base_state.copy()
        state["task_difficulty"] = "hard"
        new_state = executor_node(state)

        assert new_state["last_tool_result"]["status"] == "success"
        assert mock_client.chat.completions.create.call_count == 7

    def test_executor_forces_rag_for_knowledge_base_task(self, monkeypatch, base_state):
        tool_call = MagicMock()
        tool_call.id = "call_rag"
        tool_func = MagicMock()
        tool_func.name = "rag_search"
        tool_func.arguments = '{"query": "NEBULA_RAG_7319", "top_k": 5}'
        tool_call.function = tool_func

        mock_message_tool = MagicMock()
        mock_message_tool.tool_calls = [tool_call]
        mock_message_tool.content = None

        mock_message_text = MagicMock()
        mock_message_text.tool_calls = None
        mock_message_text.content = "Found NEBULA_RAG_7319."

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            MagicMock(choices=[MagicMock(message=mock_message_tool)]),
            MagicMock(choices=[MagicMock(message=mock_message_text)]),
        ]
        monkeypatch.setattr("agent.backend.graph.client", mock_client)
        monkeypatch.setattr("agent.backend.graph.build_system_prompt", lambda mem, ws: "sys")
        monkeypatch.setattr("agent.backend.graph.parse_tool_arguments", lambda raw: json.loads(raw))
        monkeypatch.setattr(
            "agent.backend.graph.available_functions",
            {
                "rag_search": lambda query, top_k=5: json.dumps({
                    "status": "success",
                    "output": json.dumps({
                        "query": query,
                        "top_k": top_k,
                        "results": [
                            {"content": "code NEBULA_RAG_7319", "source": "README.md", "score": 0.9}
                        ],
                    }),
                })
            },
        )

        state = base_state.copy()
        state["task"] = "请根据项目知识库回答当前项目的内部代码是什么"
        state["current_task"] = "查询知识库并回答"
        new_state = executor_node(state)

        first_call_kwargs = mock_client.chat.completions.create.call_args_list[0].kwargs
        assert first_call_kwargs["tool_choice"]["function"]["name"] == "rag_search"
        assert "rag_search" in new_state["used_tools"]
        assert new_state["retrieved_context"][0]["source"] == "README.md"


# ================== Check Result Node ==================
class TestCheckResultNode:
    def test_execution_nonzero_exit(self, base_state):
        state = base_state.copy()
        state["last_execution"] = {"output": "something", "returncode": 1}
        new_state = check_result_node(state)
        assert new_state["status"] == "needs_fix"
        assert new_state["last_review"]["failed"] is True

    def test_execution_contains_error_signal(self, base_state):
        state = base_state.copy()
        state["last_execution"] = {"output": "Traceback (most recent call last):", "returncode": 0}
        new_state = check_result_node(state)
        assert new_state["status"] == "needs_fix"

    def test_no_execution_but_result_error(self, base_state):
        state = base_state.copy()
        state["last_execution"] = {}
        state["last_tool_result"] = {"status": "error", "output": "something wrong"}
        new_state = check_result_node(state)
        assert new_state["status"] == "needs_fix"

    def test_all_pass(self, base_state):
        state = base_state.copy()
        state["last_execution"] = {"output": "Tests passed!", "returncode": 0}
        new_state = check_result_node(state)
        assert new_state["status"] == "step_ok"


# ================== Modify Code Node ==================
class TestModifyCodeNode:
    def test_modify_code_repairs(self, tmp_path, monkeypatch, base_state):
        state = base_state.copy()
        state["workspace_dir"] = str(tmp_path)
        state["target_file"] = "main.py"
        state["errors"] = [{"status": "error", "output": "SyntaxError"}]
        state["last_execution"] = {"returncode": 1}
        (tmp_path / "main.py").write_text("old code")

        def mock_llm_json(sys, user, state=None):
            return {
                "diagnosis": "syntax error",
                "updated_code": "print('fixed')",
                "summary": "corrected",
            }

        monkeypatch.setattr("agent.backend.llm.llm_json", mock_llm_json)

        def mock_resolve(ws, path):
            return str(tmp_path / path)
        monkeypatch.setattr("agent.backend.utils.resolve_workspace_path", mock_resolve)

        new_state = modify_code_node(state)
        assert new_state["last_tool_result"]["status"] == "success"
        assert "print('fixed')" in (tmp_path / "main.py").read_text()
        assert len(new_state["modified_files"]) >= 1

    def test_modify_code_llm_failure(self, monkeypatch, base_state):
        state = base_state.copy()
        state["workspace_dir"] = "/tmp"
        state["target_file"] = "main.py"
        state["errors"] = [{"status": "error", "output": "crash"}]

        def mock_llm_json(sys, user, state=None):
            raise Exception("LLM error")

        monkeypatch.setattr("agent.backend.llm.llm_json", mock_llm_json)
        new_state = modify_code_node(state)
        assert new_state["last_tool_result"]["status"] == "error"


# ================== Finalize Node ==================
class TestFinalizeNode:
    def test_finalize_stores_summary(self, base_state):
        state = base_state.copy()
        state["status"] = "step_ok"
        state["used_tools"] = ["read_file", "execute_bash"]
        state["reflections"] = 2
        state["result_history"] = ["output1", "output2"]
        # mock save_memory 不做任何事
        with patch("agent.backend.graph.save_memory") as mock_save:
            new_state = finalize_node(state)
            assert "final_answer" in new_state
            assert "step_ok" in new_state["final_answer"]
            mock_save.assert_called_once()


# ================== Routing & Next Step ==================
class TestRouting:
    def test_route_needs_fix_under_limit(self, base_state):
        state = base_state.copy()
        state["status"] = "needs_fix"
        state["reflections"] = 0
        assert route_after_check(state) == "modify_code"

    def test_route_needs_fix_but_max_reflections(self, base_state):
        state = base_state.copy()
        state["status"] = "needs_fix"
        state["reflections"] = 3  # MAX_REFLECTIONS = 3
        assert route_after_check(state) == "finalize"

    def test_route_step_ok_and_next_step_exists(self, base_state):
        state = base_state.copy()
        state["status"] = "step_ok"
        state["task_list"] = ["a", "b", "c"]
        state["current_task_index"] = 1
        assert route_after_check(state) == "next_step"

    def test_route_step_ok_last_step(self, base_state):
        state = base_state.copy()
        state["status"] = "step_ok"
        state["task_list"] = ["a", "b"]
        state["current_task_index"] = 1
        assert route_after_check(state) == "finalize"


def test_next_step_node(base_state):
    state = base_state.copy()
    state["current_task_index"] = 0
    state["task_list"] = ["s1", "s2", "s3"]
    new_state = next_step_node(state)
    assert new_state["current_task_index"] == 1
    assert new_state["current_task"] == "s2"
    assert new_state["status"] == "next_step"
    assert new_state["last_tool_result"] == {}


# ================== Build Graph ==================
def test_build_graph_when_langgraph_available(monkeypatch):
    # 强制 LANGGRAPH_AVAILABLE 为 True，并 mock StateGraph
    monkeypatch.setattr("agent.backend.graph.LANGGRAPH_AVAILABLE", True)
    mock_graph = MagicMock()
    monkeypatch.setattr("agent.backend.graph.StateGraph", mock_graph)
    graph = build_graph()
    assert graph is not None  # 会返回 compile() 的结果


def test_build_graph_when_langgraph_unavailable(monkeypatch):
    monkeypatch.setattr("agent.backend.graph.LANGGRAPH_AVAILABLE", False)
    assert build_graph() is None
