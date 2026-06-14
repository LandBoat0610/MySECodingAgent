# 这里组装各个拆分出来的模块生成核心的生命周期图
import json
import os
import re
import uuid
import traceback
from typing import Any, Dict, List, Optional

try:
    from langgraph.graph import StateGraph, END
    LANGGRAPH_AVAILABLE = True
except Exception:
    LANGGRAPH_AVAILABLE = False
    StateGraph = None
    END = "__end__"

from agent.backend.state import AgentState
from agent.backend.config import (
    get_effective_model,
    MAX_STEP_ITERATIONS,
    MAX_REFLECTIONS,
    STEP_ITERATIONS_BY_DIFFICULTY,
)
from agent.backend.utils import log_state, parse_json_object, safe_trim, save_memory, tool_result
from agent.backend.runtime_metrics import record_llm_usage, record_tool_call
from agent.backend.llm import (
    client,
    build_system_prompt,
    build_executor_prompt,
    build_final_summary,
    create_plan,
    infer_coding_targets,
    extract_code_context,
)
from agent.backend.tools import tools, available_functions, parse_tool_arguments
import agent.backend.tools as tools_module
from agent.backend.session_manager import (
    get_memory_context,
    generate_and_save_session_summary,
    save_project_memory,
)
import time
from agent.backend.database import get_connection


def _is_cross_session_enabled() -> bool:
    """检查当前用户是否启用了跨对话知识共享。"""
    try:
        from agent.backend.platform_settings import get_agent_config

        return bool(get_agent_config().get("cross_session_enabled", True))
    except Exception:
        return True  # 默认启用，避免因读取失败而误关闭


TEXT_FILE_EXTENSIONS = (
    ".py", ".js", ".ts", ".tsx", ".vue", ".json", ".md", ".txt",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".html", ".css",
    ".scss", ".sh", ".bat", ".sql",
)

IGNORED_CONTEXT_DIRS = {
    ".git", ".venv", "venv", "node_modules", "dist", "build",
    "__pycache__", ".pytest_cache", ".mypy_cache", "agent/eval_storage",
}


def wait_for_plan_approval(session_id: str) -> str:
    timeout = 300
    start_time = time.time()

    while time.time() - start_time < timeout:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT status FROM sessions WHERE id = ?",
                (session_id,)
            ).fetchone()

            if row:
                status = row["status"]
                if status == "approved":
                    return "approved"
                if status == "stopped":
                    return "stopped"
                if status == "refining":
                    return "refining"
                if status == "skipped":
                    return "skipped"

        time.sleep(2)

    return "timeout"


def _normalize_step_objects(steps: List[Any]) -> List[Dict[str, Any]]:
    normalized = []
    for idx, step in enumerate(steps or [], 1):
        if isinstance(step, dict):
            goal = str(step.get("goal") or step.get("description") or step.get("step") or "").strip()
            action = str(step.get("action") or "execute").strip()
            expected_result = str(step.get("expected_result") or "").strip()
            verification = str(step.get("verification") or expected_result or "").strip()
            files = step.get("files_to_inspect") or step.get("files") or []
            if isinstance(files, str):
                files = [files]
        else:
            goal = str(step or "").strip()
            action = "execute"
            expected_result = ""
            verification = ""
            files = []
        normalized.append({
            "id": idx,
            "goal": goal or f"完成第 {idx} 个步骤",
            "action": action,
            "files_to_inspect": files if isinstance(files, list) else [],
            "verification": verification,
            "expected_result": expected_result if isinstance(step, dict) else "",
            "status": "pending",
        })
    return normalized


def _classify_task_type(task: str) -> str:
    text = (task or "").lower()
    if any(k in text for k in ("测试", "pytest", "test", "失败", "报错", "error", "bug", "修复", "fix")):
        return "bug_fix"
    if any(k in text for k in ("新增", "添加", "实现", "feature", "add", "create")):
        return "feature"
    if any(k in text for k in ("解释", "说明", "怎么", "如何", "review", "检查")):
        return "analysis"
    return "coding"


def _infer_acceptance_criteria(state: AgentState) -> List[str]:
    criteria = []
    task_type = state.get("task_type", "coding")
    if task_type == "analysis":
        criteria.append("回答覆盖用户问题并指出关键代码位置。")
    else:
        criteria.extend([
            "修改范围与用户需求一致，避免无关改动。",
            "关键工具调用成功或失败原因已解释。",
        ])
    if state.get("run_command"):
        criteria.append(f"可通过验证命令检查结果: {state.get('run_command')}")
    if state.get("target_file"):
        criteria.append(f"主要目标文件已检查: {state.get('target_file')}")
    return criteria


def _safe_relpath(path: str, root: str) -> str:
    try:
        return os.path.relpath(path, root).replace("\\", "/")
    except Exception:
        return path.replace("\\", "/")


def _is_ignored_context_path(rel_path: str) -> bool:
    parts = set(rel_path.replace("\\", "/").split("/"))
    return any(ignored in parts or rel_path.startswith(ignored + "/") for ignored in IGNORED_CONTEXT_DIRS)


def _collect_workspace_files(workspace_dir: str, limit: int = 120) -> List[str]:
    files: List[str] = []
    try:
        for root, dirs, names in os.walk(workspace_dir):
            rel_root = _safe_relpath(root, workspace_dir)
            dirs[:] = [
                d for d in dirs
                if not _is_ignored_context_path(d)
                and not _is_ignored_context_path(f"{rel_root}/{d}".strip("./"))
            ]
            for name in names:
                rel = _safe_relpath(os.path.join(root, name), workspace_dir)
                if _is_ignored_context_path(rel):
                    continue
                if name.endswith(TEXT_FILE_EXTENSIONS):
                    files.append(rel)
                if len(files) >= limit:
                    return files
    except Exception:
        return files
    return files


def _extract_task_keywords(task: str) -> List[str]:
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}|[\u4e00-\u9fff]{2,}", task or "")
    stop = {"帮我", "完成", "修改", "现在", "这个", "那个", "项目", "代码", "功能", "如何", "怎么"}
    keywords = []
    for word in words:
        if word in stop:
            continue
        if word not in keywords:
            keywords.append(word)
        if len(keywords) >= 8:
            break
    return keywords


def _find_relevant_files(workspace_dir: str, task: str, target_file: str = "") -> List[str]:
    files = _collect_workspace_files(workspace_dir)
    relevant: List[str] = []
    if target_file:
        relevant.append(target_file)
    keywords = _extract_task_keywords(task)
    for rel in files:
        basename = os.path.basename(rel).lower()
        if any(k.lower() in basename for k in keywords):
            relevant.append(rel)
    if len(relevant) < 8 and keywords:
        for rel in files:
            if rel in relevant:
                continue
            path = os.path.join(workspace_dir, rel)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    sample = f.read(4000)
                if any(re.search(re.escape(k), sample, re.I) for k in keywords):
                    relevant.append(rel)
            except Exception:
                continue
            if len(relevant) >= 8:
                break
    seen = set()
    return [f for f in relevant if not (f in seen or seen.add(f))][:8]


def _build_retrieved_context(workspace_dir: str, relevant_files: List[str]) -> List[Dict[str, Any]]:
    contexts = []
    for rel in relevant_files[:5]:
        try:
            path = os.path.join(workspace_dir, rel)
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = safe_trim(f.read(), 1800)
            contexts.append({"source": rel, "content": content})
        except Exception as e:
            contexts.append({"source": rel, "error": str(e)})
    return contexts


def _legacy_mojibake_task_should_use_rag(task: str, step_task: str = "") -> bool:
    text = f"{task or ''}\n{step_task or ''}".lower()
    rag_markers = (
        "rag_search",
        "rag",
        "knowledge base",
        "project knowledge",
        "internal docs",
        "existing materials",
        "readme",
        "docs",
        "release command",
        "知识库",
        "项目文档",
        "已有资料",
        "内部资料",
        "内部代码",
        "发布口令",
        "发布命令",
        "根据项目",
        "根据知识",
        "文档",
    )
    simple_math = re.fullmatch(
        r"[\s\d\+\-\*/×xX÷\(\)\.，,。只返回直接计算calculate算一下请]+",
        text,
    )
    return any(marker in text for marker in rag_markers) and not bool(simple_math)


def _task_should_use_rag(task: str, step_task: str = "") -> bool:
    text = f"{task or ''}\n{step_task or ''}".lower()
    rag_markers = (
        "rag_search",
        "rag",
        "knowledge base",
        "project knowledge",
        "internal docs",
        "existing materials",
        "readme",
        "docs",
        "release command",
        "\u77e5\u8bc6\u5e93",        # 知识库
        "\u9879\u76ee\u6587\u6863",  # 项目文档
        "\u5df2\u6709\u8d44\u6599",  # 已有资料
        "\u5185\u90e8\u8d44\u6599",  # 内部资料
        "\u5185\u90e8\u4ee3\u7801",  # 内部代码
        "\u53d1\u5e03\u53e3\u4ee4",  # 发布口令
        "\u53d1\u5e03\u547d\u4ee4",  # 发布命令
        "\u6839\u636e\u9879\u76ee",  # 根据项目
        "\u6839\u636e\u77e5\u8bc6",  # 根据知识
        "\u6587\u6863",              # 文档
    )
    simple_math = re.fullmatch(
        r"[\s\d\+\-\*/\u00d7xX\u00f7\(\)\.,，。\u53ea\u8fd4\u56de"
        r"\u76f4\u63a5\u8ba1\u7b97calculate\u7b97\u4e00\u4e0b\u8bf7]+",
        text,
    )
    return any(marker in text for marker in rag_markers) and not bool(simple_math)


def _append_rag_results_to_state(state: AgentState, parsed_result: Dict[str, Any]) -> None:
    try:
        payload = json.loads(parsed_result.get("output") or "{}")
    except Exception:
        payload = {}
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list):
        return

    context = state.setdefault("retrieved_context", [])
    if not isinstance(context, list):
        context = []
        state["retrieved_context"] = context
    sources = state.setdefault("rag_sources", [])
    if not isinstance(sources, list):
        sources = []
        state["rag_sources"] = sources

    for item in results:
        if not isinstance(item, dict):
            continue
        entry = {
            "source": item.get("source", "unknown"),
            "content": item.get("content", ""),
            "score": item.get("score"),
        }
        context.append(entry)
        sources.append(entry)


def _infer_test_commands(state: AgentState) -> List[str]:
    commands = []
    run_command = str(state.get("run_command") or "").strip()
    if run_command:
        commands.append(run_command)
    workspace_dir = state.get("workspace_dir", "")
    try:
        has_pytest_config = os.path.exists(os.path.join(workspace_dir, "pytest.ini"))
        has_tests_dir = os.path.isdir(os.path.join(workspace_dir, "tests"))
        if has_pytest_config or has_tests_dir:
            commands.append("pytest -q")
        if os.path.exists(os.path.join(workspace_dir, "agent", "frontend", "package.json")):
            commands.append("cd agent/frontend && npm run test")
    except Exception:
        pass
    seen = set()
    return [cmd for cmd in commands if not (cmd in seen or seen.add(cmd))][:4]


def planner_node(state: AgentState) -> AgentState:
    trace = state["trace"]
    session_id = state.get("session_id")

    if _check_cancel(state):
        return state

    steps = create_plan(state["task"], state.get("memory", ""), trace, state)
    targets = infer_coding_targets(state["task"], state["workspace_dir"], trace, state)

    state["task_list"] = steps
    state["current_plan"] = _normalize_step_objects(state.get("_structured_steps") or steps)
    state["current_task_index"] = 0
    state["current_task"] = steps[0] if steps else state["task"]
    state["target_file"] = targets["target_file"]
    state["run_command"] = targets["run_command"]
    state["code_context"] = extract_code_context(state["target_file"], state["workspace_dir"])

    # 将计划写入数据库
    if session_id:
        import uuid
        from datetime import datetime
        round_id = state.get("current_round_id") or ""
        try:
            with get_connection() as conn:
                for step in steps:
                    conn.execute(
                        "INSERT INTO plans "
                        "(id, session_id, project_id, round_id, content, status, created_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (uuid.uuid4().hex[:8], session_id, state["project_id"],
                         round_id, step, "pending", datetime.now().isoformat())
                    )
        except Exception as e:
            print(f"Error saving plans to DB: {e}")

    if session_id:
        from agent.backend.utils import update_session_state
        state["status"] = "awaiting_approval"
        update_session_state(session_id, state, status="awaiting_approval")

        log_state(trace, "planner", "计划已生成，等待用户确认...", session_id=session_id, state=state)

        approval_result = wait_for_plan_approval(session_id)

        if approval_result == "approved":
            state["status"] = "running"
            update_session_state(session_id, state, status="running")
            log_state(trace, "planner", "用户已确认，开始执行计划。", session_id=session_id, state=state)
        elif approval_result == "refining":
            state["status"] = "running"
            update_session_state(session_id, state, status="running")
            log_state(trace, "planner", "用户要求再优化，重新生成计划...", session_id=session_id, state=state)
            steps = create_plan(state["task"], state.get("memory", ""), trace, state)
            targets = infer_coding_targets(state["task"], state["workspace_dir"], trace, state)
            state["task_list"] = steps
            state["current_plan"] = _normalize_step_objects(state.get("_structured_steps") or steps)
            state["current_task_index"] = 0
            state["current_task"] = steps[0] if steps else state["task"]
            state["target_file"] = targets["target_file"]
            state["run_command"] = targets["run_command"]
            if session_id:
                round_id = state.get("current_round_id") or ""
                try:
                    with get_connection() as conn:
                        conn.execute(
                            "UPDATE plans SET status = 'skipped' WHERE session_id = ? AND status = 'pending'",
                            (session_id,)
                        )
                        for step in steps:
                            conn.execute(
                                "INSERT INTO plans "
                                "(id, session_id, project_id, round_id, content, status, created_at) "
                                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                                (uuid.uuid4().hex[:8], session_id, state["project_id"],
                                 round_id, step, "pending", datetime.now().isoformat())
                            )
                except Exception as e:
                    print(f"Error saving refined plans to DB: {e}")
            state["status"] = "awaiting_approval"
            update_session_state(session_id, state, status="awaiting_approval")
            log_state(trace, "planner", "优化后的计划已生成，等待用户确认...", session_id=session_id, state=state)
            approval_result_2 = wait_for_plan_approval(session_id)
            if approval_result_2 == "approved":
                state["status"] = "running"
                update_session_state(session_id, state, status="running")
                log_state(trace, "planner", "用户已确认优化后的计划，开始执行。", session_id=session_id, state=state)
            else:
                state["status"] = "stopped"
                update_session_state(session_id, state, status="stopped")
                log_state(trace, "planner", f"优化计划终止: {approval_result_2}", session_id=session_id, state=state)
        else:
            state["status"] = "stopped"
            update_session_state(session_id, state, status="stopped")
            log_state(trace, "planner", f"执行终止: {approval_result}", session_id=session_id, state=state)

    return state


def context_builder_node(state: AgentState) -> AgentState:
    if state.get("status") == "stopped":
        return state
    if _check_cancel(state):
        return state

    trace = state["trace"]
    session_id = state.get("session_id")
    workspace_dir = state["workspace_dir"]
    task = state.get("task", "")

    task_type = state.get("task_type") or _classify_task_type(task)
    state["task_type"] = task_type
    state["current_plan"] = state.get("current_plan") or _normalize_step_objects(state.get("task_list", []))
    if state["current_plan"]:
        current_idx = state.get("current_task_index", 0) + 1
        for step in state["current_plan"]:
            if isinstance(step, dict) and step.get("id") == current_idx and step.get("status") == "pending":
                step["status"] = "current"

    relevant_files = _find_relevant_files(workspace_dir, task, state.get("target_file", ""))
    state["relevant_files"] = relevant_files
    state["retrieved_context"] = _build_retrieved_context(workspace_dir, relevant_files)
    state["acceptance_criteria"] = state.get("acceptance_criteria") or _infer_acceptance_criteria(state)
    state["test_commands"] = state.get("test_commands") or _infer_test_commands(state)
    state.setdefault("tool_history", [])
    state.setdefault("verification_results", [])
    state.setdefault("patch_history", [])
    state.setdefault("retry_count", 0)
    state.setdefault("failure_reason", "")

    workspace_files = _collect_workspace_files(workspace_dir, limit=40)

    # 跨对话记忆与上下文工程
    project_id = state.get("project_id", "")
    if project_id and _is_cross_session_enabled():
        memory_ctx = get_memory_context(project_id, session_id)
        state["session_summary"] = str(memory_ctx.get("session_summary", ""))
        state["project_memory"] = str(memory_ctx.get("project_memory", ""))
        state["user_preferences"] = str(memory_ctx.get("user_preferences", ""))
        state["relevant_history"] = memory_ctx.get("relevant_history", [])
        state["context_budget"] = int(memory_ctx.get("context_budget", 12000))
    else:
        state.setdefault("session_summary", "")
        state.setdefault("project_memory", "")
        state.setdefault("user_preferences", "")
        state.setdefault("relevant_history", [])
        state.setdefault("context_budget", 12000)

    state["codebase_summary"] = (
        f"Task type: {task_type}\n"
        f"Relevant files: {', '.join(relevant_files) if relevant_files else 'not found'}\n"
        f"Candidate test commands: {', '.join(state.get('test_commands', [])) or 'none'}\n"
        f"Workspace sample files: {', '.join(workspace_files[:20])}"
    )

    log_payload = {
        "task_type": task_type,
        "relevant_files": relevant_files,
        "test_commands": state.get("test_commands", []),
        "acceptance_criteria": state.get("acceptance_criteria", []),
    }
    log_state(
        trace,
        "context_builder",
        json.dumps(log_payload, ensure_ascii=False),
        session_id=session_id,
        state=state,
    )
    if session_id:
        from agent.backend.utils import update_session_state
        update_session_state(session_id, state)
    return state


def _check_cancel(state: AgentState) -> bool:
    cancel_event = state.get("_cancel_event")
    if cancel_event and cancel_event.is_set():
        state["status"] = "stopped"
        session_id = state.get("session_id")
        trace = state.get("trace", [])
        if session_id:
            from agent.backend.utils import update_session_state
            update_session_state(session_id, state, status="stopped")
        if trace:
            from agent.backend.utils import log_state as _log
            _log(trace, "cancelled", "Agent execution cancelled by user", session_id=session_id, state=state)
        return True
    return False


def _await_bash_approval(session_id: str, function_args: Dict[str, Any], state: AgentState) -> Optional[str]:
    from agent.backend.utils import update_session_state, tool_result
    from agent.backend.database import get_connection
    from agent.backend.config import BLOCKED_BASH_PATTERNS as _BLOCKED

    command = function_args.get("command", "")
    if not command.strip():
        return tool_result("error", "Empty bash command", error_type="validation")

    risk_level = "low"
    if any(re.search(p, command) for p in _BLOCKED):
        risk_level = "high"

    approval_id = uuid.uuid4().hex[:10]
    purpose = state.get("current_task", "") or "执行命令"

    pending = {
        "id": approval_id,
        "tool": "execute_bash",
        "command": command,
        "purpose": purpose,
        "risk_level": risk_level,
        "status": "pending",
        "feedback": "",
    }
    state["pending_tool_approval"] = pending
    state["status"] = "awaiting_tool_approval"

    trace = state.get("trace", [])
    log_state(trace, "tool_approval", f"等待确认: {command}",
              meta={"pending_tool_approval": pending}, session_id=session_id, state=state)
    update_session_state(session_id, state, status="awaiting_tool_approval")

    timeout = 60
    start_time = time.time()
    while time.time() - start_time < timeout:
        time.sleep(2)
        with get_connection() as conn:
            row = conn.execute(
                "SELECT state_snapshot FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if not row:
                continue
            snap = json.loads(row["state_snapshot"] or "{}")
            pending_now = snap.get("pending_tool_approval") or {}
            st = pending_now.get("status", "")

            if st == "approved":
                state.pop("pending_tool_approval", None)
                update_session_state(session_id, state, status="running")
                log_state(trace, "bash_approval", "用户已确认,执行命令", session_id=session_id, state=state)
                return None
            if st == "rejected":
                feedback = pending_now.get("feedback", "")
                state.pop("pending_tool_approval", None)
                update_session_state(session_id, state, status="running")
                log_state(trace, "bash_approval", "用户拒绝,跳过命令", session_id=session_id, state=state)
                msg = f"用户拒绝: {command}"
                if feedback:
                    msg += f" ({feedback})"
                return tool_result("error", msg, error_type="rejected", summary=msg)
            if st == "revision_requested":
                feedback = pending_now.get("feedback", "")
                state.pop("pending_tool_approval", None)
                update_session_state(session_id, state, status="running")
                log_state(trace, "bash_approval", f"用户要求修改: {feedback}", session_id=session_id, state=state)
                return tool_result("error", f"用户要求修改: {feedback}", error_type="revision_requested",
                                   summary=f"用户要求修改: {feedback}")
            if st == "stopped":
                state.pop("pending_tool_approval", None)
                update_session_state(session_id, state, status="stopped")
                return tool_result("error", "Session stopped", error_type="stopped", summary="会话已终止")

    state.pop("pending_tool_approval", None)
    update_session_state(session_id, state, status="running")
    log_state(trace, "bash_approval", "确认超时,跳过命令", session_id=session_id, state=state)
    return tool_result("error", f"Approval timeout for command: {command}", error_type="timeout",
                       summary=f"命令确认超时: {command}")


def wait_for_loop_approval(session_id: str, approval_id: str) -> str:
    from agent.backend.database import get_connection
    timeout = 300
    start_time = time.time()
    while time.time() - start_time < timeout:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT status, state_snapshot FROM sessions WHERE id = ?",
                (session_id,)
            ).fetchone()
        if row:
            if row["status"] == "stopped":
                return "stopped"
            try:
                snapshot = json.loads(row["state_snapshot"] or "{}")
            except json.JSONDecodeError:
                snapshot = {}
            pending = snapshot.get("pending_loop_approval") or {}
            if pending.get("id") == approval_id:
                status = pending.get("status")
                if status in ("continued", "stopped"):
                    return status
        time.sleep(0.5)
    return "timeout"


def executor_node(state: AgentState) -> AgentState:
    if state.get("status") == "stopped":
        return state
    if _check_cancel(state):
        return state

    trace = state["trace"]
    session_id = state.get("session_id")
    messages = state["messages"]
    step_task = state.get("current_task", state["task"])
    # 组装完整记忆上下文：旧记忆 + 跨对话记忆
    full_memory_parts = [state.get("memory", "")]
    if state.get("project_memory"):
        full_memory_parts.append(f"【项目记忆】\n{state['project_memory']}")
    if state.get("session_summary"):
        full_memory_parts.append(f"【会话摘要】\n{state['session_summary']}")
    if state.get("user_preferences"):
        full_memory_parts.append(f"【用户偏好】\n{state['user_preferences']}")
    if state.get("context_budget"):
        full_memory_parts.append(f"【上下文预算】当前可用 {state['context_budget']} tokens")
    system_prompt = build_system_prompt("\n\n".join(filter(None, full_memory_parts)), state["workspace_dir"])
    tools_module.CURRENT_WORKSPACE_DIR = state["workspace_dir"]

    messages.append({"role": "system", "content": system_prompt})
    # 使用结构化 Executor 提示词（来自 prompts.yaml executor_prompt）
    current_step = {"goal": step_task, "verification": ""}
    plan = state.get("current_plan", [])
    step_idx = state.get("current_task_index", 0)
    if isinstance(plan, list) and step_idx < len(plan) and isinstance(plan[step_idx], dict):
        current_step = plan[step_idx]
    step_context = build_executor_prompt(current_step, step_idx + 1, len(plan), state)
    messages.append({"role": "user", "content": step_context})
    action_log: List[Dict[str, Any]] = []

    step_iteration_limit = STEP_ITERATIONS_BY_DIFFICULTY.get(
        str(state.get("task_difficulty") or "").lower(),
        MAX_STEP_ITERATIONS,
    )

    iteration = 0
    current_iteration_limit = step_iteration_limit
    should_force_initial_rag = (
        _task_should_use_rag(state.get("task", ""), step_task)
        and "rag_search" not in state.get("used_tools", [])
    )
    while True:
        if iteration >= current_iteration_limit:
            if not session_id:
                break
            approval_id = uuid.uuid4().hex[:8]
            state["pending_loop_approval"] = {
                "id": approval_id,
                "status": "pending",
                "current_iteration": iteration,
                "current_limit": current_iteration_limit,
                "additional_iterations": step_iteration_limit,
                "difficulty": state.get("task_difficulty", "unknown"),
                "current_task": step_task,
            }
            state["status"] = "awaiting_continue_approval"
            log_state(
                trace,
                "continue_approval",
                (
                    f"当前步骤已达到 {current_iteration_limit} 轮工具调用上限。"
                    f"如需继续处理步骤 [{step_task}]，请确认继续。"
                ),
                session_id=session_id,
                state=state,
            )
            approval_result = wait_for_loop_approval(session_id, approval_id)
            if approval_result == "continued":
                state["status"] = "running"
                state["pending_loop_approval"] = None
                current_iteration_limit += step_iteration_limit
                log_state(
                    trace,
                    "continue_approval",
                    f"用户确认继续，当前步骤工具调用上限扩展到 {current_iteration_limit} 轮。",
                    session_id=session_id,
                    state=state,
                )
            else:
                state["pending_loop_approval"] = None
                if approval_result == "stopped":
                    state["status"] = "stopped"
                    return state
                state["last_tool_result"] = {
                    "status": "error",
                    "output": (
                        "Max iterations reached before step completion. "
                        f"limit={current_iteration_limit}, difficulty={state.get('task_difficulty', 'unknown')}, "
                        f"approval={approval_result}"
                    ),
                    "returncode": None,
                    "action_log": action_log,
                }
                state.setdefault("errors", []).append(state["last_tool_result"])
                if session_id:
                    from agent.backend.utils import update_session_state
                    update_session_state(session_id, state)
                return state

        if _check_cancel(state):
            return state
        log_state(trace, "reason", f"Step '{step_task}' iteration {iteration + 1}", session_id=session_id, state=state)
        iteration += 1
        try:
            request_args = {"model": get_effective_model(), "messages": messages, "tools": tools}
            if should_force_initial_rag:
                request_args["tool_choice"] = {"type": "function", "function": {"name": "rag_search"}}
                should_force_initial_rag = False
            response = client.chat.completions.create(**request_args)
            record_llm_usage(state, response)
        except Exception as e:
            state["last_tool_result"] = {"status": "error", "output": f"LLM call failed: {e}", "returncode": None}
            state.setdefault("errors", []).append(state["last_tool_result"])
            if session_id:
                from agent.backend.utils import update_session_state
                update_session_state(session_id, state)
            return state

        message = response.choices[0].message
        msg_dict = {"role": message.role, "content": message.content}
        if message.tool_calls:
            msg_dict["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in message.tool_calls
            ]
        messages.append(msg_dict)

        if not message.tool_calls:
            content = message.content or ""
            log_state(trace, "finish_step", content, session_id=session_id, state=state)
            state["last_tool_result"] = {"status": "success", "output": content, "returncode": 0}
            state.setdefault("result_history", []).append(content)
            if session_id:
                from agent.backend.utils import update_session_state
                update_session_state(session_id, state)
            return state

        for tool_call in message.tool_calls:
            function_payload = getattr(tool_call, "function", None)
            if function_payload is None:
                continue

            function_name = str(getattr(function_payload, "name", ""))
            raw_arguments = str(getattr(function_payload, "arguments", ""))
            function_args = parse_tool_arguments(raw_arguments)
            log_state(trace, "act", f"{function_name}({function_args})", session_id=session_id, state=state)

            # 如果工具是写文件，就把它的路径记录下来
            if function_name == "write_file" and "path" in function_args:
                state.setdefault("modified_files", []).append(function_args["path"])

            if "_argument_error" in function_args:
                result_text = tool_result("error", function_args["_argument_error"])
                parsed_result = parse_json_object(result_text)
                record_tool_call(state, function_name, False, 0.0)
            else:
                func = available_functions.get(function_name)
                if func is None:
                    result_text = tool_result("error", f"Unknown tool: {function_name}")
                    parsed_result = parse_json_object(result_text)
                    record_tool_call(state, function_name, False, 0.0)
                else:
                    t0 = time.monotonic()
                    try:
                        if function_name == "execute_bash":
                            from agent.backend.config import BASH_APPROVAL_REQUIRED
                            if BASH_APPROVAL_REQUIRED and session_id and "_approved" not in function_args:
                                result_text = _await_bash_approval(session_id, function_args, state)
                                if result_text is not None:
                                    pass
                                else:
                                    result_text = func(**function_args)
                            else:
                                result_text = func(**function_args)
                        else:
                            result_text = func(**function_args)
                    except Exception as e:
                        result_text = tool_result("error", f"Tool exception: {e}\n{traceback.format_exc()}")
                    elapsed_ms = (time.monotonic() - t0) * 1000.0
                    parsed_result = parse_json_object(result_text)
                    ok = parsed_result.get("status") != "error"
                    record_tool_call(state, function_name, ok, elapsed_ms)

            action_log.append({"tool": function_name, "args": function_args, "result": parsed_result})
            state.setdefault("tool_history", []).append({
                "step_index": state.get("current_task_index", 0),
                "step": step_task,
                "tool": function_name,
                "args": function_args,
                "result": parsed_result,
            })
            state.setdefault("used_tools", []).append(function_name)
            for modified in parsed_result.get("modified_files") or []:
                if modified not in state.setdefault("modified_files", []):
                    state["modified_files"].append(modified)
            if function_name == "apply_patch":
                state.setdefault("patch_history", []).append({
                    "target": function_args.get("target"),
                    "status": parsed_result.get("status"),
                    "summary": parsed_result.get("summary") or parsed_result.get("output"),
                })
            if function_name == "rag_search" and parsed_result.get("status") != "error":
                _append_rag_results_to_state(state, parsed_result)
            messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": result_text})
            log_state(trace, "observe", result_text, session_id=session_id, state=state)
            state["last_tool_result"] = parsed_result

            if function_name == "execute_bash":
                state["last_execution"] = parsed_result

            if parsed_result.get("status") == "error":
                import copy
                error_result = copy.deepcopy(parsed_result)
                error_result["action_log"] = copy.deepcopy(action_log)
                state.setdefault("errors", []).append(error_result)
                state["last_tool_result"] = error_result
                if session_id:
                    from agent.backend.utils import update_session_state
                    update_session_state(session_id, state)
                return state

    state["last_tool_result"] = {
        "status": "error",
        "output": "Max iterations reached before step completion.",
        "returncode": None,
        "action_log": action_log,
    }
    state.setdefault("errors", []).append(state["last_tool_result"])
    if session_id:
        from agent.backend.utils import update_session_state
        update_session_state(session_id, state)
    return state


def verifier_node(state: AgentState) -> AgentState:
    if state.get("status") == "stopped":
        return state
    if _check_cancel(state):
        return state
    trace = state["trace"]
    session_id = state.get("session_id")
    result = state.get("last_tool_result", {}) or {}
    execution = state.get("last_execution", {}) or {}
    tool_history = state.get("tool_history", []) or []

    result_output = str(result.get("output") or "")
    execution_output = str(execution.get("output") or "")
    combined_output = (result_output + "\n" + execution_output).lower()

    returncode = execution.get("returncode")
    if returncode is None:
        returncode = result.get("returncode")

    stderr_text = execution_output.lower()

    error_signals = [
        "traceback", "syntaxerror", "nameerror", "typeerror",
        "zerodivisionerror", "modulenotfounderror", "filenotfounderror",
        "permissionerror", "assertionerror",
    ]

    failed = False
    reason = "Result passed verifier checks"
    evidence: List[str] = []

    if execution:
        if isinstance(returncode, int) and returncode != 0:
            failed = True
            reason = "Execution returned non-zero exit code"
            evidence.append(f"returncode={returncode}")
        elif result.get("status") == "error":
            failed = True
            reason = f"Execution failed: {result.get('error_type') or result.get('summary', 'unknown error')}"
            evidence.append(str(result.get("summary") or result.get("output") or ""))
        elif any(token in stderr_text for token in error_signals):
            failed = True
            reason = "Execution stderr contains real error signals"
            evidence.append(safe_trim(execution_output, 500))
        else:
            failed = False
            reason = "Execution succeeded"
            evidence.append("last execution succeeded")
    else:
        if result.get("status") == "error":
            failed = True
            error_label = result.get("error_type") or result.get("summary") or "unknown"
            reason = f"Last tool returned error status: {error_label}"
            evidence.append(str(result.get("summary") or result.get("output") or ""))
        elif any(token in combined_output for token in error_signals):
            failed = True
            reason = "Output contains real error signals"
            evidence.append(safe_trim(result_output, 500))

    failed_tool_events = [
        item for item in tool_history
        if isinstance(item, dict)
        and isinstance(item.get("result"), dict)
        and item["result"].get("status") == "error"
    ]
    if failed_tool_events and not failed:
        failed = True
        latest = failed_tool_events[-1]["result"]
        reason = f"Tool failure detected: {latest.get('error_type') or latest.get('summary') or 'unknown'}"
        evidence.append(str(latest.get("summary") or latest.get("output") or ""))

    modified_files = state.get("modified_files", []) or []
    acceptance_criteria = state.get("acceptance_criteria", []) or []
    if not failed and state.get("task_type") != "analysis":
        if modified_files:
            evidence.append(f"modified_files={modified_files[-5:]}")
        elif not result_history_indicates_done(state):
            evidence.append("no modified files recorded for a coding task")

    review = {
        "failed": failed,
        "reason": reason,
        "returncode": returncode,
        "step_index": state.get("current_task_index", 0),
        "step": state.get("current_task", ""),
        "acceptance_criteria": acceptance_criteria,
        "modified_files": modified_files[-8:],
        "evidence": [safe_trim(str(item), 600) for item in evidence if item],
    }
    state["status"] = "needs_fix" if failed else "step_ok"
    state["last_review"] = review
    state.setdefault("verification_results", []).append(review)
    if failed:
        state["failure_reason"] = reason
    else:
        state["failure_reason"] = ""
    log_state(trace, "verifier", json.dumps(review, ensure_ascii=False), session_id=session_id, state=state)

    if not failed and result.get("status") == "success" and not execution:
        result_text = str(result.get("output", "")).lower()
        completion_signals = ["task complete", "done", "finished", "already exist", "no changes needed"]
        if any(sig in result_text for sig in completion_signals):
            state["status"] = "step_ok"
            state["_task_fully_done"] = True
            log_state(trace, "check_result", "Task appears fully complete, skipping remaining steps",
                      session_id=session_id, state=state)

    return state


def result_history_indicates_done(state: AgentState) -> bool:
    text = "\n".join(state.get("result_history", [])[-3:]).lower()
    done_signals = ("no changes needed", "already done", "already exists", "无需修改", "不需要修改")
    return any(signal in text for signal in done_signals)


def check_result_node(state: AgentState) -> AgentState:
    return verifier_node(state)


def modify_code_node(state: AgentState) -> AgentState:
    if _check_cancel(state):
        return state
    trace = state["trace"]
    session_id = state.get("session_id")
    state["reflections"] = state.get("reflections", 0) + 1
    target_file = state.get("target_file", "main.py")
    workspace_dir = state["workspace_dir"]
    from agent.backend.llm import extract_code_context
    code_context = extract_code_context(target_file, workspace_dir)
    state["code_context"] = code_context
    errors = state.get("errors") or []
    last_error = errors[-1] if errors else {
        "status": "error",
        "output": state.get("last_review", {}).get("reason", "Unknown failure"),
        "returncode": state.get("last_execution", {}).get("returncode"),
    }
    run_command = state.get("run_command", f"python {target_file}")

    log_state(trace, "modify_code", f"Attempting repair for {target_file}", session_id=session_id, state=state)

    try:
        from agent.backend.llm import llm_json
        from agent.backend.utils import safe_trim
        data = llm_json(
            (
                "You are a code repair module. Return JSON with keys: diagnosis, updated_code, summary. "
                "updated_code must be the FULL corrected file content only, not a diff."
            ),
            (
                f"Task:\n{state['task']}\n\n"
                f"Current step:\n{state.get('current_task', '')}\n\n"
                f"Target file:\n{target_file}\n\n"
                f"Run command:\n{run_command}\n\n"
                f"Current code:\n{code_context}\n\n"
                f"Latest error:\n{json.dumps(last_error, ensure_ascii=False, indent=2)}"
            ),
            state,
        )
        updated_code = data.get("updated_code", "")
        diagnosis = data.get("diagnosis", "")
        summary = data.get("summary", "")
        if not isinstance(updated_code, str) or not updated_code.strip():
            raise ValueError("Model did not return updated_code")

        from agent.backend.utils import resolve_workspace_path as _rwp
        safe_path = _rwp(workspace_dir, target_file)
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(updated_code)
        state.setdefault("modified_files", []).append(target_file)
        state["code_context"] = safe_trim(updated_code, 6000)
        state["last_tool_result"] = {
            "status": "success",
            "output": f"Code repaired. Diagnosis: {diagnosis}\nSummary: {summary}",
            "path": safe_path,
            "returncode": 0,
        }
    except Exception as e:
        err = {"status": "error", "output": f"modify_code failed: {e}", "returncode": None}
        state.setdefault("errors", []).append(err)
        state["last_tool_result"] = err

    log_state(trace, "repair_written", state["last_tool_result"]["output"], session_id=session_id, state=state)
    return state


def repair_node(state: AgentState) -> AgentState:
    state["retry_count"] = state.get("retry_count", 0) + 1
    trace = state.get("trace", [])
    session_id = state.get("session_id")
    log_state(
        trace,
        "repair",
        (
            f"开始第 {state['retry_count']} 次修复。"
            f"原因: {state.get('failure_reason') or state.get('last_review', {}).get('reason', 'unknown')}"
        ),
        session_id=session_id,
        state=state,
    )
    return modify_code_node(state)


def finalize_node(state: AgentState) -> AgentState:
    trace = state["trace"]
    session_id = state.get("session_id")
    state["final_answer"] = build_final_summary(state)
    final_summary = state["final_answer"]
    log_state(trace, "final", final_summary, session_id=session_id, state=state)
    if not state.get("eval_mode"):
        save_memory(state["task"], final_summary)
        # 跨对话记忆：保存会话摘要和项目记忆（仅在启用时）
        if _is_cross_session_enabled():
            project_id = state.get("project_id", "")
            if project_id and session_id:
                try:
                    generate_and_save_session_summary(
                        session_id, project_id, state["task"], final_summary
                    )
                    # 自动提取并保存项目级关键信息
                    _auto_extract_project_memory(state, project_id)
                except Exception:
                    pass

    if session_id:
        from agent.backend.utils import update_session_state
        final_status = state.get("status", "completed")
        if final_status not in ("stopped", "skipped"):
            final_status = "completed"
        update_session_state(session_id, state, status=final_status)

    return state

# Routing


def route_after_check(state: AgentState) -> str:
    if state.get("status") == "stopped":
        return "finalize"
    if state.get("_task_fully_done"):
        return "finalize"
    if state.get("status") == "needs_fix" and state.get("reflections", 0) < MAX_REFLECTIONS:
        return "modify_code"

    current_index = state.get("current_task_index", 0)
    tasks = state.get("task_list", [])
    if state.get("status") == "step_ok" and current_index + 1 < len(tasks):
        return "next_step"
    return "finalize"


def next_step_node(state: AgentState) -> AgentState:
    idx = state.get("current_task_index", 0) + 1
    state["current_task_index"] = idx
    tasks = state.get("task_list", [])
    state["current_task"] = tasks[idx] if idx < len(tasks) else state["task"]
    state["last_tool_result"] = {}
    state["last_execution"] = {}
    state["status"] = "next_step"
    plan = state.get("current_plan") or []
    for step in plan:
        if isinstance(step, dict):
            if step.get("id") == idx:
                step["status"] = "done"
            if step.get("id") == idx + 1:
                step["status"] = "current"
    return state

# Graph execution


def _auto_extract_project_memory(state: AgentState, project_id: str) -> None:
    """自动从 Agent 执行结果中提取项目级关键信息并保存。

    提取内容：成功的测试命令、启动命令、已知问题。
    """
    try:
        # 提取测试命令
        test_commands = state.get("test_commands", [])
        if test_commands:
            for cmd in test_commands[:3]:
                save_project_memory(
                    project_id, f"test_cmd_{cmd[:30]}", cmd, "commands"
                )

        # 提取使用的工具列表作为项目能力记录
        used_tools = state.get("used_tools", [])
        if used_tools:
            save_project_memory(
                project_id,
                "agent_capabilities",
                f"Agent supports: {', '.join(sorted(set(used_tools)))}",
                "capabilities",
            )

        # 提取验证结果
        verification = state.get("verification_results", [])
        if verification:
            latest = verification[-1]
            if isinstance(latest, dict):
                if latest.get("status") == "error":
                    save_project_memory(
                        project_id,
                        "last_known_issue",
                        json.dumps(latest, ensure_ascii=False)[:500],
                        "known_issues",
                    )
    except Exception:
        pass


def build_graph():
    if not LANGGRAPH_AVAILABLE:
        return None

    graph = StateGraph(AgentState)
    graph.add_node("planner", planner_node)
    graph.add_node("context_builder", context_builder_node)
    graph.add_node("executor", executor_node)
    graph.add_node("verifier", verifier_node)
    graph.add_node("repair", repair_node)
    graph.add_node("next_step", next_step_node)
    graph.add_node("finalize", finalize_node)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "context_builder")
    graph.add_edge("context_builder", "executor")
    graph.add_edge("executor", "verifier")
    graph.add_conditional_edges(
        "verifier",
        route_after_check,
        {
            "modify_code": "repair",
            "next_step": "next_step",
            "finalize": "finalize",
        },
    )
    graph.add_edge("repair", "context_builder")
    graph.add_edge("next_step", "executor")
    graph.add_edge("finalize", END)
    return graph.compile()


def run_manual_fallback(state: AgentState) -> AgentState:
    state = planner_node(state)
    if state.get("status") == "stopped":
        return finalize_node(state)
    state = context_builder_node(state)
    while True:
        if _check_cancel(state):
            break
        state = executor_node(state)
        if state.get("status") == "stopped":
            break
        state = verifier_node(state)
        route = route_after_check(state)
        if route == "modify_code":
            state = repair_node(state)
            state = context_builder_node(state)
            continue
        if route == "next_step":
            state = next_step_node(state)
            continue
        break
    return finalize_node(state)
