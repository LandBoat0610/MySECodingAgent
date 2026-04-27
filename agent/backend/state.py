from typing import Any, Dict, List, TypedDict


# State 核心状态定义
class AgentState(TypedDict, total=False):
    task: str
    messages: List[Dict[str, Any]]
    task_list: List[str]
    current_task_index: int
    current_task: str
    code_context: str
    target_file: str
    run_command: str
    last_tool_result: Dict[str, Any]
    last_execution: Dict[str, Any]
    errors: List[Dict[str, Any]]
    reflections: int
    trace: List[Dict[str, Any]]
    memory: str
    workspace_dir: str
    final_answer: str
    status: str
    used_tools: List[str]
    result_history: List[str]
    original_target_path: str
    should_sync_back: bool
    #
    project_root: str
    modified_files: List[str]