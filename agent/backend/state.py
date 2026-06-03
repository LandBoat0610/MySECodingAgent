from typing import Any, Dict, List, TypedDict


# State 核心状态定义
class AgentState(TypedDict, total=False):
    session_id: str
    project_id: str
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
    task_type: str
    task_difficulty: str
    current_plan: List[Dict[str, Any]]
    acceptance_criteria: List[str]
    relevant_files: List[str]
    retrieved_context: List[Dict[str, Any]]
    codebase_summary: str
    test_commands: List[str]
    tool_history: List[Dict[str, Any]]
    verification_results: List[Dict[str, Any]]
    patch_history: List[Dict[str, Any]]
    failure_reason: str
    retry_count: int
    last_review: Dict[str, Any]
    used_tools: List[str]
    result_history: List[str]
    original_target_path: str
    should_sync_back: bool
    #
    project_root: str
    modified_files: List[str]
    eval_mode: bool
    runtime_metrics: Dict[str, Any]
