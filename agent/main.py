import sys

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv() #读.env 文件并注入环境变量

from agent.backend.utils import (
    ensure_workspace, prepare_workspace, load_memory, 
    log_state, sync_workspace_file_back, save_trace
)
from agent.backend.state import AgentState
from agent.backend.graph import build_graph, run_manual_fallback
from agent.backend.config import TRACE_JSON, TRACE_MERMAID



def run_agent_plus(task: str) -> str:
    workspace_dir = ensure_workspace()
    sync_info = prepare_workspace(workspace_dir)

    initial_state: AgentState = {
        "task": task,
        "messages": [],
        "task_list": [],
        "current_task_index": 0,
        "current_task": task,
        "code_context": "",
        "errors": [],
        "reflections": 0,
        "trace": [],
        "memory": load_memory(),
        "workspace_dir": workspace_dir,
        "final_answer": "",
        "status": "initialized",
        "used_tools": [],
        "result_history": [],
        "last_tool_result": {},
        "last_execution": {},
        "original_target_path": sync_info.get("original_target_path", ""),
        "should_sync_back": sync_info.get("should_sync_back", False),
        #
        "project_root": sync_info.get("project_root", ""),
        "modified_files": [],
    }

    log_state(initial_state["trace"], "start", f"Task: {task}")
    graph = build_graph()
    
    if graph is not None:
        final_state = graph.invoke(initial_state)
    else:
        log_state(initial_state["trace"], "fallback", "LangGraph not available, using manual state machine fallback")
        final_state = run_manual_fallback(initial_state)

    sync_workspace_file_back(final_state)
    save_trace(final_state["trace"])
    return final_state.get("final_answer", "")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python main.py 'your task here'")
        print()
        print("Output files:")
        print(f"  - {TRACE_JSON}     structured state trace")
        print(f"  - {TRACE_MERMAID}  mermaid state diagram")
        sys.exit(1)

    task = " ".join(sys.argv[1:])
    result = run_agent_plus(task)
    print("\n" + "=" * 60)
    print("FINAL RESULT")
    print("=" * 60)
    print(result)