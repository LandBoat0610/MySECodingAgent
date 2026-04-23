#这里组装各个拆分出来的模块生成核心的生命周期图
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

from backend.state import AgentState
from backend.config import MODEL, MAX_STEP_ITERATIONS, MAX_REFLECTIONS
from backend.utils import log_state, parse_json_object, safe_trim, save_memory, resolve_workspace_path, tool_result
from backend.llm import client, build_system_prompt, create_plan, infer_coding_targets, extract_code_context, llm_json
from backend.tools import tools, available_functions, parse_tool_arguments
import backend.tools as tools_module

def planner_node(state: AgentState) -> AgentState:
    trace = state["trace"]
    steps = create_plan(state["task"], state.get("memory", ""), trace)
    targets = infer_coding_targets(state["task"], state["workspace_dir"], trace)
    state["task_list"] = steps
    state["current_task_index"] = 0
    state["current_task"] = steps[0] if steps else state["task"]
    state["target_file"] = targets["target_file"]
    state["run_command"] = targets["run_command"]
    state["code_context"] = extract_code_context(state["target_file"], state["workspace_dir"])
    return state


def executor_node(state: AgentState) -> AgentState:
    trace = state["trace"]
    messages = state["messages"]
    step_task = state.get("current_task", state["task"])
    system_prompt = build_system_prompt(state.get("memory", ""), state["workspace_dir"])
    global CURRENT_WORKSPACE_DIR
    CURRENT_WORKSPACE_DIR = state["workspace_dir"]

    messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": f"Current step: {step_task}"})
    action_log: List[Dict[str, Any]] = []

    for iteration in range(MAX_STEP_ITERATIONS):
        log_state(trace, "reason", f"Step '{step_task}' iteration {iteration + 1}")
        try:
            response = client.chat.completions.create(model=MODEL, messages=messages, tools=tools)
        except Exception as e:
            state["last_tool_result"] = {"status": "error", "output": f"LLM call failed: {e}", "returncode": None}
            state.setdefault("errors", []).append(state["last_tool_result"])
            return state

        message = response.choices[0].message
        messages.append(message)

        if not message.tool_calls:
            content = message.content or ""
            log_state(trace, "finish_step", content)
            state["last_tool_result"] = {"status": "success", "output": content, "returncode": 0}
            state.setdefault("result_history", []).append(content)
            return state

        for tool_call in message.tool_calls:
            function_payload = getattr(tool_call, "function", None)
            if function_payload is None:
                continue

            function_name = str(getattr(function_payload, "name", ""))
            raw_arguments = str(getattr(function_payload, "arguments", ""))
            function_args = parse_tool_arguments(raw_arguments)
            log_state(trace, "act", f"{function_name}({function_args})")

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
            log_state(trace, "observe", result_text)
            state["last_tool_result"] = parsed_result

            if function_name == "execute_bash":
                state["last_execution"] = parsed_result

            if parsed_result.get("status") == "error":
                # 使用浅拷贝打断循环引用，防止 json.dumps 崩溃
                error_result = dict(parsed_result) 
                error_result["action_log"] = action_log
                state.setdefault("errors", []).append(error_result)
                state["last_tool_result"] = error_result
                return state

    state["last_tool_result"] = {
        "status": "error",
        "output": "Max iterations reached before step completion.",
        "returncode": None,
        "action_log": action_log,
    }
    state.setdefault("errors", []).append(state["last_tool_result"])
    return state


def check_result_node(state: AgentState) -> AgentState:
    trace = state["trace"]
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
        "traceback",
        "syntaxerror",
        "nameerror",
        "typeerror",
        "zerodivisionerror",
        "modulenotfounderror",
        "filenotfounderror",
        "permissionerror",
        "assertionerror",
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

    review = {
        "failed": failed,
        "reason": reason,
        "returncode": returncode,
    }
    state["status"] = "needs_fix" if failed else "step_ok"
    state["last_review"] = review
    log_state(trace, "check_result", json.dumps(review, ensure_ascii=False))
    return state


def modify_code_node(state: AgentState) -> AgentState:
    trace = state["trace"]
    state["reflections"] = state.get("reflections", 0) + 1
    target_file = state.get("target_file", "main.py")
    workspace_dir = state["workspace_dir"]
    code_context = extract_code_context(target_file, workspace_dir)
    state["code_context"] = code_context
    errors = state.get("errors") or []
    last_error = errors[-1] if errors else {
        "status": "error",
        "output": state.get("last_review", {}).get("reason", "Unknown failure"),
        "returncode": state.get("last_execution", {}).get("returncode"),
    }
    run_command = state.get("run_command", f"python {target_file}")

    log_state(trace, "modify_code", f"Attempting repair for {target_file}")

    try:
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

        safe_path = resolve_workspace_path(workspace_dir, target_file)
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
        log_state(trace, "repair_written", state["last_tool_result"]["output"])
    except Exception as e:
        err = {"status": "error", "output": f"modify_code failed: {e}", "returncode": None}
        state.setdefault("errors", []).append(err)
        state["last_tool_result"] = err
        log_state(trace, "repair_error", err["output"])
    return state


def finalize_node(state: AgentState) -> AgentState:
    trace = state["trace"]
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
    log_state(trace, "final", final_summary)
    save_memory(state["task"], final_summary)
    return state

# Routing
def route_after_check(state: AgentState) -> str:
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
    while True:
        state = executor_node(state)
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