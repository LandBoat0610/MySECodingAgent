import os
import re
import json
import sys
import html
import shutil
import traceback
import subprocess
import urllib.parse
import urllib.request
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict, Literal

from openai import OpenAI

try:
    from langgraph.graph import StateGraph, END
    LANGGRAPH_AVAILABLE = True
except Exception:
    LANGGRAPH_AVAILABLE = False
    StateGraph = None  # type: ignore
    END = "__end__"  # type: ignore

# =========================
# Config
# =========================
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
MEMORY_FILE = "agent_memory.md"
TRACE_JSON = "agent_trace.json"
TRACE_MERMAID = "agent_trace.mmd"
MAX_TOOL_OUTPUT = 4000
MAX_STEP_ITERATIONS = 6
MAX_REFLECTIONS = 3
DEFAULT_WORKSPACE_PREFIX = "zizhiagent_workspace_"

client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    base_url=os.environ.get("OPENAI_BASE_URL")
)

# =========================
# State
# =========================
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


# =========================
# Utilities
# =========================
def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def safe_trim(text: Optional[str], max_len: int = MAX_TOOL_OUTPUT) -> str:
    if text is None:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"\n...[truncated {len(text) - max_len} chars]"


def parse_json_object(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def ensure_workspace() -> str:
    base = os.environ.get("ZIZHI_AGENT_WORKSPACE")
    if base:
        os.makedirs(base, exist_ok=True)
        return os.path.abspath(base)
    return tempfile.mkdtemp(prefix=DEFAULT_WORKSPACE_PREFIX)


def resolve_workspace_path(workspace_dir: str, path: str) -> str:
    raw = Path(path)
    if not raw.is_absolute():
        raw = Path(workspace_dir) / raw
    normalized = raw.resolve()
    workspace = Path(workspace_dir).resolve()
    if not str(normalized).startswith(str(workspace)):
        raise PermissionError(f"Path escapes workspace: {path}")
    return str(normalized)


def tool_result(
    status: Literal["success", "error"],
    output: str,
    path: Optional[str] = None,
    returncode: Optional[int] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> str:
    return json.dumps(
        {
            "status": status,
            "output": safe_trim(output),
            "path": path,
            "returncode": returncode,
            "meta": meta or {},
        },
        ensure_ascii=False,
    )


def load_memory() -> str:
    if not os.path.exists(MEMORY_FILE):
        return ""
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        lines = content.splitlines()
        return "\n".join(lines[-80:]) if len(lines) > 80 else content
    except Exception:
        return ""


def save_memory(task: str, result: str) -> None:
    entry = (
        f"\n## {now_str()}\n"
        f"**Task:** {task}\n"
        f"**Result:**\n{result}\n"
    )
    try:
        with open(MEMORY_FILE, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        pass


def log_state(trace: List[Dict[str, Any]], phase: str, content: str, meta: Optional[dict] = None) -> None:
    item = {
        "time": now_str(),
        "phase": phase,
        "content": safe_trim(content, 1600),
        "meta": meta or {}
    }
    trace.append(item)
    print(f"[{item['time']}] [{phase.upper()}] {safe_trim(content, 180)}")


def save_trace(trace: List[Dict[str, Any]]) -> None:
    with open(TRACE_JSON, "w", encoding="utf-8") as f:
        json.dump(trace, f, ensure_ascii=False, indent=2)

    mermaid_lines = ["flowchart TD", "    A0([Start])"]
    prev = "A0"
    for i, item in enumerate(trace, start=1):
        node_id = f"A{i}"
        label = f"{item['phase']}\\n{item['time']}"
        mermaid_lines.append(f'    {node_id}["{label}"]')
        mermaid_lines.append(f"    {prev} --> {node_id}")
        prev = node_id
    mermaid_lines.append(f"    {prev} --> END([Finish])")

    with open(TRACE_MERMAID, "w", encoding="utf-8") as f:
        f.write("\n".join(mermaid_lines))


# =========================
# Tool definitions
# =========================
tools = [
    {
        "type": "function",
        "function": {
            "name": "execute_bash",
            "description": "Execute a bash command within the workspace for development and validation tasks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The bash command to execute"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read contents of a local file inside the workspace",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Path to the file"}},
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a local file inside the workspace",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file"},
                    "content": {"type": "string", "description": "Content to write"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for external information relevant to the task",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Search query"}},
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "Fetch text content from a webpage URL",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string", "description": "The URL to fetch"}},
                "required": ["url"]
            }
        }
    }
]

BLOCKED_BASH_PATTERNS = [
    r"\brm\s+-rf\s+/\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r":\(\)\{:\|:&\};:",
    r"\bdd\s+if=",
    r"\bmkfs\b",
    r"\bchmod\s+-R\s+777\s+/\b",
]

CURRENT_WORKSPACE_DIR = None


def parse_tool_arguments(raw_arguments: str) -> Dict[str, Any]:
    if not raw_arguments:
        return {}
    try:
        parsed = json.loads(raw_arguments)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError as error:
        return {"_argument_error": f"Invalid JSON arguments: {error}"}


def execute_bash(command: str) -> str:
    try:
        workspace_dir = CURRENT_WORKSPACE_DIR or ensure_workspace()
        for pattern in BLOCKED_BASH_PATTERNS:
            if re.search(pattern, command):
                return tool_result("error", f"Blocked potentially dangerous command: {command}")

        result = subprocess.run(
            command,
            shell=True,
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            timeout=20,
        )
        combined = f"STDOUT:\n{safe_trim(result.stdout)}\n\nSTDERR:\n{safe_trim(result.stderr)}"
        return tool_result(
            "success" if result.returncode == 0 else "error",
            combined,
            path=workspace_dir,
            returncode=result.returncode,
            meta={"command": command},
        )
    except subprocess.TimeoutExpired:
        return tool_result("error", "Command timed out", path=CURRENT_WORKSPACE_DIR, returncode=124)
    except Exception as e:
        return tool_result("error", str(e), path=CURRENT_WORKSPACE_DIR)


def read_file(path: str) -> str:
    try:
        workspace_dir = CURRENT_WORKSPACE_DIR or ensure_workspace()
        safe_path = resolve_workspace_path(workspace_dir, path)
        with open(safe_path, "r", encoding="utf-8") as f:
            content = f.read()
        return tool_result("success", content, path=safe_path)
    except Exception as e:
        return tool_result("error", str(e), path=path)


def write_file(path: str, content: str) -> str:
    try:
        workspace_dir = CURRENT_WORKSPACE_DIR or ensure_workspace()
        safe_path = resolve_workspace_path(workspace_dir, path)
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(content)
        return tool_result("success", f"Successfully wrote to {safe_path}", path=safe_path)
    except Exception as e:
        return tool_result("error", str(e), path=path)


def web_search(query: str) -> str:
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://duckduckgo.com/html/?q={encoded}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw_html = resp.read().decode("utf-8", errors="ignore")

        results = []
        for m in re.finditer(r'<a[^>]*class="result__a"[^>]*href="(.*?)"[^>]*>(.*?)</a>', raw_html, re.I | re.S):
            href = html.unescape(m.group(1))
            title = re.sub(r"<.*?>", "", m.group(2))
            title = html.unescape(title).strip()
            if title and href:
                results.append({"title": title, "url": href})
            if len(results) >= 5:
                break

        return tool_result("success", json.dumps({"query": query, "results": results}, ensure_ascii=False))
    except Exception as e:
        return tool_result("error", str(e))


def fetch_url(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read().decode("utf-8", errors="ignore")

        text = re.sub(r"<script.*?>.*?</script>", " ", raw, flags=re.S | re.I)
        text = re.sub(r"<style.*?>.*?</style>", " ", text, flags=re.S | re.I)
        text = re.sub(r"<.*?>", " ", text, flags=re.S)
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()

        return tool_result(
            "success",
            text,
            path=url,
            meta={"content_type": content_type},
        )
    except Exception as e:
        return tool_result("error", str(e), path=url)


available_functions = {
    "execute_bash": execute_bash,
    "read_file": read_file,
    "write_file": write_file,
    "web_search": web_search,
    "fetch_url": fetch_url,
}


# =========================
# LLM helpers
# =========================
def llm_json(system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    response = client.chat.completions.create(
        model=MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return parse_json_object(response.choices[0].message.content or "{}")


def build_system_prompt(memory: str, workspace_dir: str) -> str:
    return f"""
You are Agent-Plus, an autonomous coding and research agent.
You must operate in Planner -> Executor -> Reviewer -> ModifyCode style.

Hard rules:
1. Stay inside the workspace: {workspace_dir}
2. When you need code context, read the file first.
3. When execution fails, inspect stderr/returncode before retrying.
4. Prefer precise tool calls.
5. Never pretend a fix worked without validation.
6. Final answers must summarize what changed, what was validated, and remaining risks.

Memory:
{memory}
""".strip()


def create_plan(task: str, memory: str, trace: List[Dict[str, Any]]) -> List[str]:
    log_state(trace, "plan", f"Creating plan for task: {task}")
    try:
        data = llm_json(
            "You are a planner for an autonomous agent. Break the task into 3-6 concrete executable steps. Return JSON object with key 'steps'.",
            f"Task:\n{task}\n\nMemory:\n{memory}",
        )
        steps = data.get("steps", [])
        if not isinstance(steps, list) or not steps:
            return [task]
        result = [str(s).strip() for s in steps if str(s).strip()]
        log_state(trace, "plan_result", "\n".join(f"{i + 1}. {s}" for i, s in enumerate(result)))
        return result or [task]
    except Exception as e:
        log_state(trace, "plan_error", str(e))
        return [task]


def infer_coding_targets(task: str, workspace_dir: str, trace: List[Dict[str, Any]]) -> Dict[str, str]:
    filename_match = re.search(r"([\w./-]+\.py)\b", task)
    target_file = filename_match.group(1) if filename_match else "main.py"
    run_command = f"python {target_file}"

    if "pytest" in task.lower() or "测试" in task:
        run_command = "pytest -q"
    elif "npm test" in task.lower():
        run_command = "npm test"

    try:
        safe_target = resolve_workspace_path(workspace_dir, target_file)
        rel = os.path.relpath(safe_target, workspace_dir)
        target_file = rel
    except Exception:
        pass

    log_state(trace, "infer_targets", f"target_file={target_file}, run_command={run_command}")
    return {"target_file": target_file, "run_command": run_command}


def extract_code_context(target_file: str, workspace_dir: str) -> str:
    try:
        safe_path = resolve_workspace_path(workspace_dir, target_file)
        with open(safe_path, "r", encoding="utf-8") as f:
            return safe_trim(f.read(), 6000)
    except Exception as e:
        return f"[code_context unavailable: {e}]"


# =========================
# Graph nodes
# =========================
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
                state.setdefault("errors", []).append(parsed_result)
                state["last_tool_result"]["action_log"] = action_log
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


# =========================
# Routing
# =========================
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


# =========================
# Graph execution
# =========================
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


def prepare_workspace_with_target(task: str, workspace_dir: str) -> Dict[str, Any]:
    match = re.search(r"([\w./-]+\.py)\b", task)
    if not match:
        return {
            "original_target_path": "",
            "should_sync_back": False,
        }

    candidate = match.group(1)
    original_path = os.path.abspath(candidate)

    if os.path.exists(candidate):
        target = resolve_workspace_path(workspace_dir, os.path.basename(candidate))
        shutil.copy(candidate, target)
        return {
            "original_target_path": original_path,
            "should_sync_back": True,
        }

    return {
        "original_target_path": original_path,
        "should_sync_back": False,
    }


def sync_workspace_file_back(state: AgentState) -> None:
    trace = state["trace"]

    if state.get("status") != "step_ok":
        log_state(trace, "sync_back_skip", "Skip sync-back because final status is not step_ok")
        return

    if not state.get("should_sync_back"):
        log_state(trace, "sync_back_skip", "Skip sync-back because no original file path is available")
        return

    target_file = state.get("target_file", "")
    workspace_dir = state["workspace_dir"]
    original_target_path = state.get("original_target_path", "")

    if not target_file or not original_target_path:
        log_state(trace, "sync_back_skip", "Skip sync-back because target_file/original_target_path is empty")
        return

    try:
        workspace_file = resolve_workspace_path(workspace_dir, target_file)

        if not os.path.exists(workspace_file):
            log_state(trace, "sync_back_skip", f"Workspace file does not exist: {workspace_file}")
            return

        os.makedirs(os.path.dirname(original_target_path), exist_ok=True)
        shutil.copy2(workspace_file, original_target_path)

        log_state(
            trace,
            "sync_back_success",
            f"Synced workspace file back to original path: {original_target_path}",
        )
    except Exception as e:
        log_state(trace, "sync_back_error", f"Failed to sync workspace file back: {e}")


# =========================
# Public API
# =========================
def run_agent_plus(task: str) -> str:
    workspace_dir = ensure_workspace()
    sync_info = prepare_workspace_with_target(task, workspace_dir)

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


# =========================
# CLI
# =========================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python zizhiagent1.2.py 'your task here'")
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
