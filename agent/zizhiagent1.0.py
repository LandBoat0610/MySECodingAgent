import os
import re
import json
import time
import sys
import html
import traceback
import subprocess
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Optional
from openai import OpenAI

# =========================
# Config
# =========================
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
MEMORY_FILE = "agent_memory.md"
TRACE_JSON = "agent_trace.json"
TRACE_MERMAID = "agent_trace.mmd"
MAX_TOOL_OUTPUT = 4000
MAX_STEP_ITERATIONS = 8
MAX_REFLECTIONS = 2

client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    base_url=os.environ.get("OPENAI_BASE_URL")
)

# =========================
# Utilities
# =========================
def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def safe_trim(text: str, max_len: int = MAX_TOOL_OUTPUT) -> str:
    if text is None:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"\n...[truncated {len(text) - max_len} chars]"

def parse_tool_arguments(raw_arguments: str) -> dict[str, Any]:
    if not raw_arguments:
        return {}
    try:
        parsed = json.loads(raw_arguments)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError as error:
        return {"_argument_error": f"Invalid JSON arguments: {error}"}

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
        "content": safe_trim(content, 1500),
        "meta": meta or {}
    }
    trace.append(item)
    print(f"[{item['time']}] [{phase.upper()}] {safe_trim(content, 180)}")

def save_trace(trace: List[Dict[str, Any]]) -> None:
    with open(TRACE_JSON, "w", encoding="utf-8") as f:
        json.dump(trace, f, ensure_ascii=False, indent=2)

    mermaid_lines = [
        "flowchart TD",
        "    A0([Start])"
    ]
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
            "description": "Execute a bash command on the local system for development tasks. Use only when necessary.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The bash command to execute"
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read contents of a local file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a local file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write"
                    }
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
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    }
                },
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
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to fetch"
                    }
                },
                "required": ["url"]
            }
        }
    }
]

# =========================
# Tool implementations
# =========================
BLOCKED_BASH_PATTERNS = [
    r"\brm\s+-rf\s+/\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r":\(\)\{:\|:&\};:",
    r"\bdd\s+if=",
    r"\bmkfs\b",
]

def execute_bash(command: str) -> str:
    try:
        for pattern in BLOCKED_BASH_PATTERNS:
            if re.search(pattern, command):
                return json.dumps({
                    "ok": False,
                    "error": f"Blocked potentially dangerous command: {command}"
                }, ensure_ascii=False)

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=20
        )
        return json.dumps({
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": safe_trim(result.stdout),
            "stderr": safe_trim(result.stderr)
        }, ensure_ascii=False)
    except subprocess.TimeoutExpired:
        return json.dumps({"ok": False, "error": "Command timed out"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

def read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return json.dumps({"ok": True, "content": safe_trim(content)}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

def write_file(path: str, content: str) -> str:
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return json.dumps({"ok": True, "message": f"Successfully wrote to {path}"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

def web_search(query: str) -> str:
    """
    External tool 1:
    Use DuckDuckGo HTML results page to retrieve search result titles and links.
    """
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://duckduckgo.com/html/?q={encoded}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw_html = resp.read().decode("utf-8", errors="ignore")

        results = []
        for m in re.finditer(
            r'<a[^>]*class="result__a"[^>]*href="(.*?)"[^>]*>(.*?)</a>',
            raw_html,
            re.IGNORECASE | re.DOTALL
        ):
            href = html.unescape(m.group(1))
            title = re.sub(r"<.*?>", "", m.group(2))
            title = html.unescape(title).strip()
            if title and href:
                results.append({"title": title, "url": href})
            if len(results) >= 5:
                break

        return json.dumps({
            "ok": True,
            "query": query,
            "results": results
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

def fetch_url(url: str) -> str:
    """
    External tool 2:
    Fetch webpage text for deeper reading.
    """
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read().decode("utf-8", errors="ignore")

        text = re.sub(r"<script.*?>.*?</script>", " ", raw, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style.*?>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<.*?>", " ", text, flags=re.DOTALL)
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()

        return json.dumps({
            "ok": True,
            "url": url,
            "content_type": content_type,
            "content": safe_trim(text, 3000)
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

available_functions = {
    "execute_bash": execute_bash,
    "read_file": read_file,
    "write_file": write_file,
    "web_search": web_search,
    "fetch_url": fetch_url,
}

# =========================
# Planner / Reflection
# =========================
def create_plan(task: str, memory: str, trace: List[Dict[str, Any]]) -> List[str]:
    log_state(trace, "plan", f"Creating plan for task: {task}")
    try:
        response = client.chat.completions.create(
            model=MODEL,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a planner for an autonomous agent. "
                        "Break the task into 3-6 concrete executable steps. "
                        "Return JSON object with key 'steps'. "
                        "Steps must be action-oriented and verifiable."
                    )
                },
                {
                    "role": "user",
                    "content": f"Task:\n{task}\n\nMemory:\n{memory}"
                }
            ]
        )
        data = json.loads(response.choices[0].message.content)
        steps = data.get("steps", [])
        if not isinstance(steps, list) or not steps:
            return [task]
        steps = [str(s).strip() for s in steps if str(s).strip()]
        log_state(trace, "plan_result", "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps)))
        return steps or [task]
    except Exception as e:
        log_state(trace, "plan_error", str(e))
        return [task]

def reflect_and_replan(
    original_task: str,
    current_step: str,
    failed_context: str,
    memory: str,
    trace: List[Dict[str, Any]]
) -> List[str]:
    log_state(trace, "reflect", f"Reflecting after failure on step: {current_step}")
    try:
        response = client.chat.completions.create(
            model=MODEL,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a reflexion module for an autonomous agent. "
                        "Analyze the failure, explain likely cause briefly, then provide a corrected short plan. "
                        "Return JSON with keys: 'diagnosis', 'revised_steps'."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"Original task:\n{original_task}\n\n"
                        f"Current step:\n{current_step}\n\n"
                        f"Failure context:\n{failed_context}\n\n"
                        f"Memory:\n{memory}"
                    )
                }
            ]
        )
        data = json.loads(response.choices[0].message.content)
        diagnosis = data.get("diagnosis", "Unknown")
        revised_steps = data.get("revised_steps", [current_step])
        if not isinstance(revised_steps, list) or not revised_steps:
            revised_steps = [current_step]

        log_state(trace, "reflection_result", f"Diagnosis: {diagnosis}\nRevised: {revised_steps}")
        return [str(s).strip() for s in revised_steps if str(s).strip()] or [current_step]
    except Exception as e:
        log_state(trace, "reflection_error", str(e))
        return [current_step]

# =========================
# Executor (ReAct loop)
# =========================
def build_system_prompt(memory: str) -> str:
    return f"""
You are Agent-Plus, an autonomous agent.

You must operate in a Plan -> Act -> Observe -> Reflect style.

Core behavior rules:
1. Do not jump blindly to a final answer if external verification is needed.
2. Prefer explicit planning and stepwise completion.
3. When a tool fails, analyze why and try an alternative strategy.
4. Be concise but rigorous.
5. For programming or local project tasks, you may use bash/file tools.
6. For external information, use web_search and fetch_url.
7. When enough evidence is collected, produce a final answer clearly.

Memory:
{memory}
""".strip()

def run_agent_step(
    step_task: str,
    messages: List[Dict[str, Any]],
    trace: List[Dict[str, Any]],
    max_iterations: int = MAX_STEP_ITERATIONS
):
    messages.append({"role": "user", "content": f"Current step: {step_task}"})
    action_log = []
    tool_failures = 0

    for iteration in range(max_iterations):
        log_state(trace, "reason", f"Step '{step_task}' iteration {iteration + 1}")

        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=tools
            )
        except Exception as e:
            err = f"LLM call failed: {e}"
            log_state(trace, "llm_error", err)
            return False, err, action_log, messages

        message = response.choices[0].message
        messages.append(message)

        if not message.tool_calls:
            final_content = message.content or ""
            log_state(trace, "finish_step", final_content)
            return True, final_content, action_log, messages

        for tool_call in message.tool_calls:
            function_payload = getattr(tool_call, "function", None)
            if function_payload is None:
                continue

            function_name = str(getattr(function_payload, "name", ""))
            raw_arguments = str(getattr(function_payload, "arguments", ""))
            function_args = parse_tool_arguments(raw_arguments)

            log_state(trace, "act", f"{function_name}({function_args})")

            if "_argument_error" in function_args:
                tool_result = json.dumps({
                    "ok": False,
                    "error": function_args["_argument_error"]
                }, ensure_ascii=False)
            else:
                func = available_functions.get(function_name)
                if func is None:
                    tool_result = json.dumps({
                        "ok": False,
                        "error": f"Unknown tool: {function_name}"
                    }, ensure_ascii=False)
                else:
                    try:
                        tool_result = func(**function_args)
                    except Exception as e:
                        tool_result = json.dumps({
                            "ok": False,
                            "error": f"Tool exception: {str(e)}",
                            "traceback": traceback.format_exc()
                        }, ensure_ascii=False)

            action_log.append({
                "tool": function_name,
                "args": function_args,
                "result": safe_trim(tool_result, 1200)
            })

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_result
            })

            log_state(trace, "observe", tool_result)

            try:
                parsed = json.loads(tool_result)
                if not parsed.get("ok", False):
                    tool_failures += 1
            except Exception:
                tool_failures += 1

            if tool_failures >= 2:
                warn_msg = (
                    "Two tool failures detected. Analyze the failure cause and either "
                    "choose a different tool, simplify the task, or ask for missing input."
                )
                messages.append({"role": "system", "content": warn_msg})
                log_state(trace, "self_correct", warn_msg)

    fail_msg = "Max iterations reached before step completion."
    log_state(trace, "step_timeout", fail_msg)
    return False, fail_msg, action_log, messages

# =========================
# Main orchestration
# =========================
def run_agent_plus(task: str, use_plan: bool = True) -> str:
    trace: List[Dict[str, Any]] = []
    memory = load_memory()
    system_prompt = build_system_prompt(memory)

    log_state(trace, "start", f"Task: {task}")

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt}
    ]

    steps = create_plan(task, memory, trace) if use_plan else [task]

    all_results: List[str] = []
    reflections = 0
    i = 0

    while i < len(steps):
        step = steps[i]
        log_state(trace, "execute_step", f"[{i + 1}/{len(steps)}] {step}")

        ok, result, actions, messages = run_agent_step(step, messages, trace)

        if ok:
            all_results.append(f"### Step {i + 1}: {step}\n{result}")
            i += 1
            continue

        # self-correction / reflexion
        if reflections < MAX_REFLECTIONS:
            reflections += 1
            revised_steps = reflect_and_replan(
                original_task=task,
                current_step=step,
                failed_context=result + "\n\nActions:\n" + json.dumps(actions, ensure_ascii=False, indent=2),
                memory=memory,
                trace=trace
            )

            # replace current step with revised substeps
            steps = steps[:i] + revised_steps + steps[i + 1:]
            log_state(trace, "replan", f"New steps inserted: {revised_steps}")
        else:
            all_results.append(f"### Step {i + 1}: {step}\nFailed: {result}")
            break

    final_prompt = (
        "Summarize the completed work. "
        "Include: overall result, what tools were used, whether self-correction happened, "
        "and any remaining limitations."
    )
    messages.append({"role": "user", "content": final_prompt})

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages
        )
        final_summary = response.choices[0].message.content or "\n".join(all_results)
    except Exception:
        final_summary = "\n\n".join(all_results)

    log_state(trace, "final", final_summary)
    save_memory(task, final_summary)
    save_trace(trace)
    return final_summary

# =========================
# CLI
# =========================
if __name__ == "__main__":
    use_plan = "--no-plan" not in sys.argv
    if "--no-plan" in sys.argv:
        sys.argv.remove("--no-plan")

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python agent-plus.py 'your task here'")
        print("  python agent-plus.py --no-plan 'your task here'")
        print()
        print("Output files:")
        print(f"  - {TRACE_JSON}     structured state trace")
        print(f"  - {TRACE_MERMAID}  mermaid state diagram")
        sys.exit(1)

    task = " ".join(sys.argv[1:])
    result = run_agent_plus(task, use_plan=use_plan)
    print("\n" + "=" * 60)
    print("FINAL RESULT")
    print("=" * 60)
    print(result)