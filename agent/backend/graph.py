# 这里组装各个拆分出来的模块生成核心的生命周期图
import json
import traceback
import uuid
from typing import Any, Dict, List

try:
    from langgraph.graph import StateGraph, END
    LANGGRAPH_AVAILABLE = True
except Exception:
    LANGGRAPH_AVAILABLE = False
    StateGraph = None
    END = "__end__"

from agent.backend.state import AgentState
from agent.backend.config import get_effective_model, MAX_STEP_ITERATIONS, MAX_REFLECTIONS, STEP_ITERATIONS_BY_DIFFICULTY
from agent.backend.utils import log_state, parse_json_object, safe_trim, save_memory, tool_result
from agent.backend.runtime_metrics import record_llm_usage, record_tool_call
from agent.backend.llm import client, build_system_prompt, create_plan, infer_coding_targets, extract_code_context
from agent.backend.tools import tools, available_functions, parse_tool_arguments
import agent.backend.tools as tools_module
from agent.backend.platform_settings import get_tool_settings, is_tool_enabled

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


def wait_for_tool_approval(session_id: str, approval_id: str) -> Dict[str, Any]:
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
                return {"status": "stopped", "feedback": ""}
            try:
                snapshot = json.loads(row["state_snapshot"] or "{}")
            except json.JSONDecodeError:
                snapshot = {}
            pending = snapshot.get("pending_tool_approval") or {}
            if pending.get("id") == approval_id:
                status = pending.get("status")
                if status in ("approved", "rejected", "revision_requested"):
                    return {"status": status, "feedback": pending.get("feedback") or ""}

        time.sleep(0.5)

    return {"status": "timeout", "feedback": ""}


def wait_for_loop_approval(session_id: str, approval_id: str) -> str:
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


def _refresh_plan_feedback(state: AgentState) -> None:
    session_id = state.get("session_id")
    if not session_id:
        return
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT state_snapshot FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        if not row:
            return
        snapshot = json.loads(row["state_snapshot"] or "{}")
        feedback = snapshot.get("plan_feedback", "")
        if feedback:
            state["plan_feedback"] = feedback
    except Exception:
        return


def planner_node(state: AgentState) -> AgentState:
    trace = state["trace"]
    session_id = state.get("session_id")

    if _check_cancel(state):
        return state

    steps = create_plan(state["task"], state.get("memory", ""), trace, state)
    if _check_cancel(state):
        return state
    targets = infer_coding_targets(state["task"], state["workspace_dir"], trace, state)
    if _check_cancel(state):
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
                        "INSERT INTO plans "
                        "(id, session_id, project_id, round_id, content, status, created_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (uuid.uuid4().hex[:8], session_id, state["project_id"], state.get("current_round_id", ""),
                         step, "pending", datetime.now().isoformat())
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
            _refresh_plan_feedback(state)
            steps = create_plan(state["task"], state.get("memory", ""), trace, state)
            if _check_cancel(state):
                return state
            targets = infer_coding_targets(state["task"], state["workspace_dir"], trace, state)
            if _check_cancel(state):
                return state
            state["task_list"] = steps
            state["current_task_index"] = 0
            state["current_task"] = steps[0] if steps else state["task"]
            state["target_file"] = targets["target_file"]
            state["run_command"] = targets["run_command"]
            if session_id:
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
                                (uuid.uuid4().hex[:8], session_id, state["project_id"], state.get("current_round_id", ""),
                                 step, "pending", datetime.now().isoformat())
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


def _check_cancel(state: AgentState) -> bool:
    cancel_event = state.get("_cancel_event")
    session_id = state.get("session_id")
    cancelled = bool(cancel_event and cancel_event.is_set())
    if not cancelled and session_id:
        try:
            with get_connection() as conn:
                row = conn.execute("SELECT status FROM sessions WHERE id = ?", (session_id,)).fetchone()
                cancelled = bool(row and row["status"] == "stopped")
        except Exception:
            cancelled = False

    if cancelled:
        if cancel_event:
            cancel_event.set()
        state["status"] = "stopped"
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
    tools_module.CURRENT_CANCEL_EVENT = state.get("_cancel_event")
    enabled_tools = get_tool_settings()
    active_tools = [tool for tool in tools if enabled_tools.get(tool["function"]["name"], True)]

    messages.append({"role": "system", "content": system_prompt})
    step_context = (
        f"Current step: {step_task}\n\n"
        f"IMPORTANT: Execute ONLY the minimum actions needed for this step. "
        f"If the step is already done (e.g. the file already exists and works), "
        f"just respond with a brief summary without calling any tools. "
        f"Do NOT create extra files or do extra work beyond this step. "
        f"When this step is complete, stop calling tools and give a short text summary."
    )
    messages.append({"role": "user", "content": step_context})
    action_log: List[Dict[str, Any]] = []

    step_iteration_limit = STEP_ITERATIONS_BY_DIFFICULTY.get(
        str(state.get("task_difficulty") or "").lower(),
        MAX_STEP_ITERATIONS,
    )

    iteration = 0
    current_iteration_limit = step_iteration_limit
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
                    f"如需继续处理步骤“{step_task}”，请确认继续。"
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
            kwargs = {"model": get_effective_model(), "messages": messages}
            if active_tools:
                kwargs["tools"] = active_tools
            response = client.chat.completions.create(**kwargs)
            record_llm_usage(state, response)
        except Exception as e:
            state["last_tool_result"] = {"status": "error", "output": f"LLM call failed: {e}", "returncode": None}
            state.setdefault("errors", []).append(state["last_tool_result"])
            if session_id:
                from agent.backend.utils import update_session_state
            update_session_state(session_id, state)
            return state
        if _check_cancel(state):
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
            if _check_cancel(state):
                return state
            function_payload = getattr(tool_call, "function", None)
            if function_payload is None:
                continue

            function_name = str(getattr(function_payload, "name", ""))
            raw_arguments = str(getattr(function_payload, "arguments", ""))
            function_args = parse_tool_arguments(raw_arguments)
            log_state(
                trace,
                "act",
                f"{function_name}({function_args})",
                meta={"tool": function_name, "args": function_args},
                session_id=session_id,
                state=state,
            )

            # 如果工具是写文件，就把它的路径记录下来
            if function_name == "write_file" and "path" in function_args:
                state.setdefault("modified_files", []).append(function_args["path"])

            if "_argument_error" in function_args:
                result_text = tool_result("error", function_args["_argument_error"])
                parsed_result = parse_json_object(result_text)
                record_tool_call(state, function_name, False, 0.0)
            else:
                func = available_functions.get(function_name)
                if not is_tool_enabled(function_name):
                    result_text = tool_result("error", f"Tool disabled: {function_name}")
                    parsed_result = parse_json_object(result_text)
                    record_tool_call(state, function_name, False, 0.0)
                elif func is None:
                    result_text = tool_result("error", f"Unknown tool: {function_name}")
                    parsed_result = parse_json_object(result_text)
                    record_tool_call(state, function_name, False, 0.0)
                else:
                    if _check_cancel(state):
                        return state
                    t0 = time.monotonic()
                    try:
                        if function_name == "execute_bash" and session_id:
                            approval_id = uuid.uuid4().hex[:8]
                            command = str(function_args.get("command") or "")
                            purpose = str(function_args.get("purpose") or "").strip()
                            if not purpose:
                                purpose = "Agent 请求执行该命令以完成当前步骤。"
                            state["pending_tool_approval"] = {
                                "id": approval_id,
                                "tool": function_name,
                                "command": command,
                                "purpose": purpose,
                                "status": "pending",
                            }
                            state["status"] = "awaiting_tool_approval"
                            log_state(
                                trace,
                                "tool_approval",
                                f"等待用户确认命令: {command}\n作用: {purpose}",
                                meta={"pending_tool_approval": state["pending_tool_approval"]},
                                session_id=session_id,
                                state=state,
                            )
                            approval = wait_for_tool_approval(session_id, approval_id)
                            approval_result = approval.get("status", "timeout")
                            approval_feedback = str(approval.get("feedback") or "").strip()
                            if approval_result == "approved":
                                state["status"] = "running"
                                state["pending_tool_approval"]["status"] = "approved"
                                log_state(trace, "tool_approval", "用户已确认，开始执行命令。", session_id=session_id, state=state)
                                result_text = func(**function_args)
                                state["pending_tool_approval"] = None
                            elif approval_result == "rejected":
                                state["status"] = "running"
                                output = (
                                    "User rejected this command before execution. "
                                    f"Command was not executed: {command}\n"
                                    "React to this feedback: choose a safer/different command, explain why no command is needed, "
                                    "or skip the command if appropriate."
                                )
                                if approval_feedback:
                                    output += f"\nUser feedback: {approval_feedback}"
                                result_text = tool_result(
                                    "success",
                                    output,
                                    returncode=0,
                                    meta={"executed": False, "rejected": True, "feedback": approval_feedback},
                                )
                                state["pending_tool_approval"] = None
                            elif approval_result == "revision_requested":
                                state["status"] = "running"
                                result_text = tool_result(
                                    "success",
                                    (
                                        "User requested changes to the command before execution. "
                                        f"Original command was not executed: {command}\n"
                                        f"User modification request: {approval_feedback or 'No specific suggestion provided.'}\n"
                                        "React to this feedback by proposing a revised execute_bash command with a clear purpose, "
                                        "or skip command execution if it is no longer necessary."
                                    ),
                                    returncode=0,
                                    meta={"executed": False, "revision_requested": True, "feedback": approval_feedback},
                                )
                                state["pending_tool_approval"] = None
                            elif approval_result == "stopped":
                                state["status"] = "stopped"
                                result_text = tool_result("error", "Command approval stopped by user", returncode=130)
                            else:
                                state["status"] = "running"
                                result_text = tool_result("error", f"Command approval timed out: {command}", returncode=124)
                                state["pending_tool_approval"] = None
                        else:
                            result_text = func(**function_args)
                    except Exception as e:
                        result_text = tool_result("error", f"Tool exception: {e}\n{traceback.format_exc()}")
                    elapsed_ms = (time.monotonic() - t0) * 1000.0
                    parsed_result = parse_json_object(result_text)
                    ok = parsed_result.get("status") != "error"
                    record_tool_call(state, function_name, ok, elapsed_ms)
                    if _check_cancel(state):
                        return state

            action_log.append({"tool": function_name, "args": function_args, "result": parsed_result})
            state.setdefault("used_tools", []).append(function_name)
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
        "output": f"Max iterations reached before step completion. limit={current_iteration_limit}, difficulty={state.get('task_difficulty', 'unknown')}",
        "returncode": None,
        "action_log": action_log,
    }
    state.setdefault("errors", []).append(state["last_tool_result"])
    if session_id:
        from agent.backend.utils import update_session_state
        update_session_state(session_id, state)
    return state


def check_result_node(state: AgentState) -> AgentState:
    if state.get("status") == "stopped":
        return state
    if _check_cancel(state):
        return state
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

    if not failed and result.get("status") == "success" and not execution:
        result_text = str(result.get("output", "")).lower()
        completion_signals = ["task complete", "done", "finished", "already exist", "no changes needed"]
        if any(sig in result_text for sig in completion_signals):
            state["status"] = "step_ok"
            state["_task_fully_done"] = True
            log_state(trace, "check_result", "Task appears fully complete, skipping remaining steps",
                      session_id=session_id, state=state)

    return state


def modify_code_node(state: AgentState) -> AgentState:
    if state.get("status") == "stopped":
        return state
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
        if _check_cancel(state):
            return state
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
    if state.get("status") == "stopped":
        final_summary = (
            f"Overall task: {state['task']}\n\n"
            "Execution was stopped by the user. No further agent steps will be run.\n\n"
            f"Step results:\n{safe_trim(result_history, 5000)}\n\n"
            "Final status: stopped"
        )
    else:
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
    if not state.get("eval_mode") and state.get("status") != "stopped":
        save_memory(state["task"], final_summary)

    if session_id:
        from agent.backend.utils import update_session_state
        final_status = state.get("status", "completed")
        if final_status not in ("stopped", "skipped"):
            final_status = "completed"
        update_session_state(session_id, state, status=final_status)
        round_id = state.get("current_round_id")
        if round_id:
            try:
                from datetime import datetime
                with get_connection() as conn:
                    conn.execute(
                        """UPDATE conversation_rounds
                           SET status = ?, finished_at = ?, final_answer = ?, trace_json = ?, runtime_metrics_json = ?
                           WHERE id = ?""",
                        (
                            final_status,
                            datetime.now().isoformat(),
                            final_summary,
                            json.dumps(state.get("trace") or [], ensure_ascii=False),
                            json.dumps(state.get("runtime_metrics") or {}, ensure_ascii=False),
                            round_id,
                        ),
                    )
            except Exception as e:
                print(f"Error finalizing conversation round: {e}")

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


def route_after_planner(state: AgentState) -> str:
    if state.get("status") == "stopped":
        return "finalize"
    return "executor"


def route_after_executor(state: AgentState) -> str:
    if state.get("status") == "stopped":
        return "finalize"
    return "check_result"


def route_after_modify(state: AgentState) -> str:
    if state.get("status") == "stopped":
        return "finalize"
    return "executor"


def next_step_node(state: AgentState) -> AgentState:
    if _check_cancel(state):
        return state
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
    graph.add_conditional_edges("planner", route_after_planner, {"executor": "executor", "finalize": "finalize"})
    graph.add_conditional_edges("executor", route_after_executor, {"check_result": "check_result", "finalize": "finalize"})
    graph.add_conditional_edges(
        "check_result",
        route_after_check,
        {
            "modify_code": "modify_code",
            "next_step": "next_step",
            "finalize": "finalize",
        },
    )
    graph.add_conditional_edges("modify_code", route_after_modify, {"executor": "executor", "finalize": "finalize"})
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
