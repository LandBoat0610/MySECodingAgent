# tests/test_state.py
import os
import sys
import pytest
from typing import Dict, Any, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent.backend.state import AgentState


class TestAgentState:
    """验证 AgentState 这个 TypedDict 的结构(运行时为普通 dict)"""

    def test_minimal_state_creation(self):
        state: AgentState = {
            "task": "hello",
            "messages": [],
            "trace": [],
        }
        assert state["task"] == "hello"

    def test_full_state_fields(self):
        state: AgentState = {
            "task": "t",
            "messages": [],
            "task_list": ["a"],
            "current_task_index": 0,
            "current_task": "a",
            "code_context": "",
            "target_file": "main.py",
            "run_command": "python main.py",
            "last_tool_result": {},
            "last_execution": {},
            "errors": [],
            "reflections": 0,
            "trace": [],
            "memory": "",
            "workspace_dir": "/tmp",
            "final_answer": "",
            "status": "init",
            "used_tools": [],
            "result_history": [],
            "original_target_path": "",
            "should_sync_back": False,
            "project_root": "",
            "modified_files": [],
        }
        # 仅验证一些关键字段能正常读取
        assert state["task"] == "t"
        assert isinstance(state["messages"], list)
        assert isinstance(state["modified_files"], list)

    def test_state_is_mutable(self):
        state: AgentState = {"task": "x", "messages": [], "trace": []}
        state["status"] = "ok"
        assert state["status"] == "ok"