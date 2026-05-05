# 这里组装各个拆分出来的模块生成核心的生命周期图
import json
import traceback
from typing import Any, Dict, List

try:
    from langgraph.graph import StateGraph, END
    LANGGRAPH_AVAILABLE = True
except Exception:
    LANGGRAPH_AVAILABLE = False
    StateGraph = None
    END = "__end__"

from agent.backend.state import AgentState
from agent.backend.config import MODEL, MAX_STEP_ITERATIONS, MAX_REFLECTIONS
from agent.backend.utils import log_state, parse_json_object, safe_trim, save_memory, resolve_workspace_path, tool_result
from agent.backend.llm import client, build_system_prompt, create_plan, infer_coding_targets, extract_code_context, llm_json
from agent.backend.tools import tools, available_functions, parse_tool_arguments
import agent.backend.tools as tools_module

import time
from agent.backend.database import get_connection

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

def planner_node(state: AgentState) -> AgentState:
    trace = state["trace"]
    session_id = state.get("session_id")
    
    try:
        steps = create_plan(state["task"], state.get("memory", ""), trace)
        targets = infer_coding_targets(state["task"], state["workspace_dir"], trace)
    except Exception as e:
        log_state(trace, "planner_error", f"规划阶段失败: {e}", session_id=session_id, state=state)
        state["task_list"] = [state["task"]]
        state["current_task_index"] = 0
        state["current_task"] = state["task"]
        state["target_file"] = "main.py"
        state["run_command"] = "python main.py"
        state["code_context"] = ""
        if session_id:
            from agent.backend.utils import update_session_state
            state["status"] = "awaiting_approval"
            update_session_state(session_id, state, status="awaiting_approval")
        return state
    
    state["task_list"] = steps
    state["current_task_index"] = 0
    state["current_task"] = steps[0] if steps else state["task"]
    state["target_file"] = targets["target_file"]
    state["run_command"] = targets["run_command"]
    state["code_context"] = extract_code_context(state["target_file"], state["workspace_dir"])
    
    # 将计划写入数据库
    if session_id:
        import uuid
        from datetime import datetime
        try:
            with get_connection() as conn:
                for step in steps:
                    conn.execute(
                        "INSERT INTO plans (id, session_id, project_id, content, status, created_at) VALUES (?, ?, ?, ? , ?, ?)",
                        (uuid.uuid4().hex[:8], session_id, state["project_id"], step, "pending", datetime.now().isoformat())
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
            steps = create_plan(state["task"], state.get("memory", ""), trace)
            state["task_list"] = steps
            state["current_task_index"] = 0
            state["current_task"] = steps[0] if steps else state["task"]
            if session_id:
                try:
                    with get_connection() as conn:
                        for step in steps:
                            conn.execute(
                                "INSERT INTO plans (id, session_id, project_id, content, status, created_at) VALUES (?, ?, ?, ? , ?, ?)",
                                (uuid.uuid4().hex[:8], session_id, state["project_id"], step, "pending", datetime.now().isoformat())
                            )
                except Exception as e:
                    print(f"Error saving refined plans to DB: {e}")
        else:
            state["status"] = "stopped"
            update_session_state(session_id, state, status="stopped")
            log_state(trace, "planner", f"执行终止: {approval_result}", session_id=session_id, state=state)
        
    return state


def task_completed_quick(state: AgentState) -> bool:
    """
    基于结果内容快速判断任务是否已完成。
    仅当最后一步执行成功时才考虑提前完成。
    """
    last_result = state.get("last_tool_result", {}) or {}
    # 如果最后一步是失败的，绝不算完成
    if last_result.get("status") == "error":
        return False
    output = str(last_result.get("output", ""))
    # 1. 明确完成信号
    if any(keyword in output for keyword in ["任务完成", "Task completed", "All steps done"]):
        return True
    # 2. 如果只执行了一步，且输出较长（说明是问答/简单任务）
    if state.get("current_task_index", 0) == 0 and len(output) > 200:
        return True
    # 3. 如果已经执行了最后一步
    tasks = state.get("task_list", [])
    if tasks and state.get("current_task_index", -1) == len(tasks) - 1:
        return True
    return False

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

def executor_node(state: AgentState) -> AgentState:
    if state.get("status") == "stopped":
        return state
    if _check_cancel(state):
        return state

    trace = state["trace"]
    session_id = state.get("session_id")
    messages = state["messages"]
    step_task = state.get("current_task", state["task"])
    system_prompt = build_system_prompt(state.get("memory", ""), state["workspace_dir"])
    tools_module.CURRENT_WORKSPACE_DIR = state["workspace_dir"]

    messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": f"Current step: {step_task}"})
    action_log: List[Dict[str, Any]] = []
    use_tools = True  # 首次尝试使用 tools，失败后回退为文本模式

    for iteration in range(MAX_STEP_ITERATIONS):
        if _check_cancel(state):
            return state
        log_state(trace, "reason", f"Step '{step_task}' iteration {iteration + 1}", session_id=session_id, state=state)
        try:
            if use_tools:
                response = client.chat.completions.create(model=MODEL, messages=messages, tools=tools)
            else:
                raise Exception("tools disabled, using text fallback")
        except Exception as e:
            # 某些第三方 API 不支持 tools/function calling，回退为纯文本模式
            if use_tools:
                err_msg = str(e)
                use_tools = False  # 之后都用文本模式
                log_state(trace, "tools_fallback", f"tools call failed: {err_msg}, switching to text mode for this step", session_id=session_id, state=state)
            try:
                # 构建一个不含 tools 但提示模型用特定格式输出的请求
                fallback_messages = list(messages)
                fallback_messages.append({
                    "role": "user",
                    "content": (
                        "You must choose ONE tool to call from this list to complete the current step:\n"
                        "1. execute_bash(command) - run a shell command\n"
                        "2. read_file(path) - read a file\n"
                        "3. write_file(path, content) - write a file\n"
                        "4. web_search(query) - search the web\n"
                        "5. fetch_url(url) - fetch a web page\n\n"
                        "Respond in JSON format: {\"tool\": \"tool_name\", \"args\": {...}}\n"
                        "If no tool is needed, respond with: {\"tool\": \"none\", \"message\": \"your response\"}"
                    )
                })
                response = client.chat.completions.create(
                    model=MODEL,
                    messages=fallback_messages,
                )
                # Parse the text-based tool call
                content = response.choices[0].message.content or ""
                data = parse_json_object(content)
                tool_name = data.get("tool", "")
                if tool_name and tool_name != "none" and tool_name in available_functions:
                    tool_args = data.get("args", {})
                    # Construct a fake tool_call structure
                    class FakeToolCall:
                        pass
                    fake_tc = FakeToolCall()
                    fake_tc.id = "fallback_0"
                    fake_tc.function = FakeToolCall()
                    fake_tc.function.name = tool_name
                    fake_tc.function.arguments = json.dumps(tool_args, ensure_ascii=False)
                    message = response.choices[0].message
                    message.tool_calls = [fake_tc]
                    message.content = None
                else:
                    # No tool needed, treat as text response
                    message = response.choices[0].message
                    message.tool_calls = None
                    message.content = data.get("message", content)
            except Exception as fallback_e:
                state["last_tool_result"] = {"status": "error", "output": f"LLM call failed in text mode: {fallback_e}", "returncode": None}
                state.setdefault("errors", []).append(state["last_tool_result"])
                if session_id:
                    from agent.backend.utils import update_session_state
                    update_session_state(session_id, state)
                return state

        message = response.choices[0].message
        msg_dict = {"role": message.role, "content": message.content}
        if message.tool_calls:
            msg_dict["tool_calls"] = [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
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
            else:
                func = available_functions.get(function_name)
                if func is None:
                    result_text = tool_result("error", f"Unknown tool: {function_name}")
                else:
                    try:
                        result_text = func(**function_args)
                    except Exception as e:
                        result_text = tool_result("error", f"Tool exception: {e}\n{traceback.format_exc()}")

            parsed_result = parse_json_object(result_text)
            action_log.append({"tool": function_name, "args": function_args, "result": parsed_result})
            state.setdefault("used_tools", []).append(function_name)
            messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": result_text})
            log_state(trace, "observe", result_text, session_id=session_id, state=state)
            state["last_tool_result"] = parsed_result

            if function_name == "execute_bash":
                state["last_execution"] = parsed_result

            if parsed_result.get("status") == "error":
                # 使用浅拷贝打断循环引用，防止 json.dumps 崩溃
                error_result = dict(parsed_result) 
                error_result["action_log"] = action_log
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


def check_result_node(state: AgentState) -> AgentState:
    trace = state["trace"]
    session_id = state.get("session_id")
    result = state.get("last_tool_result", {}) or {}
    execution = state.get("last_execution", {}) or {}

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
    reason = "Result passed basic checks"

    if execution:
        if isinstance(returncode, int) and returncode != 0:
            failed = True
            reason = "Execution returned non-zero exit code"
        elif any(token in stderr_text for token in error_signals):
            failed = True
            reason = "Execution stderr contains real error signals"
        else:
            failed = False
            reason = "Execution succeeded"
    else:
        if result.get("status") == "error":
            failed = True
            reason = "Last tool returned error status"
        elif any(token in combined_output for token in error_signals):
            failed = True
            reason = "Output contains real error signals"

    review = {"failed": failed, "reason": reason, "returncode": returncode}
    state["status"] = "needs_fix" if failed else "step_ok"
    state["last_review"] = review
    log_state(trace, "check_result", json.dumps(review, ensure_ascii=False), session_id=session_id, state=state)
    return state


def modify_code_node(state: AgentState) -> AgentState:
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
        from agent.backend.utils import resolve_workspace_path, safe_trim
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


def finalize_node(state: AgentState) -> AgentState:
    trace = state["trace"]
    session_id = state.get("session_id")
    used_tools = sorted(set(state.get("used_tools", [])))
    result_history = "\n\n".join(state.get("result_history", []))
    final_summary = (
        f"Overall task: {state['task']}\n\n"
        f"Used tools: {', '.join(used_tools) if used_tools else 'none'}\n"
        f"Reflections/self-corrections: {state.get('reflections', 0)}\n"
        f"Target file: {state.get('target_file', '')}\n"
        f"Run command: {state.get('run_command', '')}\n\n"
        f"Step results:\n{safe_trim(result_history, 5000)}\n\n"
        f"Final status: {state.get('status', 'unknown')}"
    )
    state["final_answer"] = final_summary
    log_state(trace, "final", final_summary, session_id=session_id, state=state)
    save_memory(state["task"], final_summary)
    
    if session_id:
        from agent.backend.utils import update_session_state
        update_session_state(session_id, state, status="completed")
        
    return state

# Routing
def route_after_check(state: AgentState) -> str:
    if state.get("status") == "stopped":
        return "finalize"

        # 新增：任务提前完成判断
    if task_completed_quick(state):
        state["status"] = "completed"  # 标记为完成，方便后续记录
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
    return state

# Graph execution
def build_graph():
    if not LANGGRAPH_AVAILABLE:
        return None

    graph = StateGraph(AgentState)
    graph.add_node("planner", planner_node)
    graph.add_node("executor", executor_node)
    graph.add_node("check_result", check_result_node)
    graph.add_node("modify_code", modify_code_node)
    graph.add_node("next_step", next_step_node)
    graph.add_node("finalize", finalize_node)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "executor")
    graph.add_edge("executor", "check_result")
    graph.add_conditional_edges(
        "check_result",
        route_after_check,
        {
            "modify_code": "modify_code",
            "next_step": "next_step",
            "finalize": "finalize",
        },
    )
    graph.add_edge("modify_code", "executor")
    graph.add_edge("next_step", "executor")
    graph.add_edge("finalize", END)
    return graph.compile()


def run_manual_fallback(state: AgentState) -> AgentState:
    state = planner_node(state)
    if state.get("status") == "stopped":
        return finalize_node(state)
    while True:
        if _check_cancel(state):
            break
        state = executor_node(state)
        if state.get("status") == "stopped":
            break
        state = check_result_node(state)
        route = route_after_check(state)
        if route == "modify_code":
            state = modify_code_node(state)
            continue
        if route == "next_step":
            state = next_step_node(state)
            continue
        break
    return finalize_node(state)