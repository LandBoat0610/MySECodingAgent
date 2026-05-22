# 存储和外界交互的业务核心工具、安全防护及 JSON Schema 的映射层
import os
import re
import json
import html
import signal
import subprocess
import time
import urllib.parse
import urllib.request
from typing import Dict, Any

from agent.backend.config import BLOCKED_BASH_PATTERNS
from agent.backend.utils import ensure_workspace, resolve_workspace_path, tool_result, safe_trim

CURRENT_WORKSPACE_DIR = None
CURRENT_CANCEL_EVENT = None

tools = [
    {
        "type": "function",
        "function": {
            "name": "execute_bash",
            "description": (
                "Propose a bash command and its purpose. The command will only execute after user approval. "
                "If the user rejects it or requests changes, react to that feedback and choose another command or skip it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The bash command to execute"},
                    "purpose": {"type": "string", "description": "A concise user-facing explanation of what this command does and why it is needed"}
                },
                "required": ["command", "purpose"]
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


def parse_tool_arguments(raw_arguments: str) -> Dict[str, Any]:
    if not raw_arguments:
        return {}
    try:
        parsed = json.loads(raw_arguments)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError as error:
        return {"_argument_error": f"Invalid JSON arguments: {error}"}


def execute_bash(command: str, purpose: str = "") -> str:
    try:
        workspace_dir = CURRENT_WORKSPACE_DIR or ensure_workspace()
        for pattern in BLOCKED_BASH_PATTERNS:
            if re.search(pattern, command):
                return tool_result("error", f"Blocked potentially dangerous command: {command}")

        cancel_event = CURRENT_CANCEL_EVENT
        if cancel_event and cancel_event.is_set():
            return tool_result("error", "Command cancelled by user", path=workspace_dir, returncode=130)

        if not cancel_event:
            completed = subprocess.run(
                command,
                shell=True,
                cwd=workspace_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                executable=os.environ.get("COMSPEC", None),
                timeout=20,
            )
            combined = f"STDOUT:\n{safe_trim(completed.stdout)}\n\nSTDERR:\n{safe_trim(completed.stderr)}"
            return tool_result(
                "success" if completed.returncode == 0 else "error",
                combined,
                path=workspace_dir,
                returncode=completed.returncode,
                meta={"command": command},
            )

        proc = subprocess.Popen(
            command,
            shell=True,
            cwd=workspace_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            executable=os.environ.get("COMSPEC", None),
            start_new_session=True,
        )
        deadline = time.monotonic() + 20
        while proc.poll() is None:
            if cancel_event and cancel_event.is_set():
                _terminate_process(proc)
                stdout, stderr = proc.communicate(timeout=2)
                combined = f"STDOUT:\n{safe_trim(stdout)}\n\nSTDERR:\n{safe_trim(stderr)}"
                return tool_result("error", f"Command cancelled by user\n\n{combined}", path=workspace_dir, returncode=130)
            if time.monotonic() > deadline:
                _terminate_process(proc)
                stdout, stderr = proc.communicate(timeout=2)
                combined = f"STDOUT:\n{safe_trim(stdout)}\n\nSTDERR:\n{safe_trim(stderr)}"
                return tool_result("error", f"Command timed out\n\n{combined}", path=workspace_dir, returncode=124)
            time.sleep(0.2)

        stdout, stderr = proc.communicate()
        returncode = proc.returncode
        combined = f"STDOUT:\n{safe_trim(stdout)}\n\nSTDERR:\n{safe_trim(stderr)}"
        return tool_result(
            "success" if returncode == 0 else "error",
            combined,
            path=workspace_dir,
            returncode=returncode,
            meta={"command": command},
        )
    except subprocess.TimeoutExpired as e:
        return tool_result("error", f"Command timed out: {e}", path=CURRENT_WORKSPACE_DIR)
    except Exception as e:
        return tool_result("error", str(e), path=CURRENT_WORKSPACE_DIR)


def _terminate_process(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except Exception:
        try:
            proc.terminate()
        except Exception:
            pass
    try:
        proc.wait(timeout=1)
    except Exception:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def read_file(path: str) -> str:
    try:
        if os.path.isabs(path):
            safe_path = path
        else:
            workspace_dir = CURRENT_WORKSPACE_DIR or ensure_workspace()
            safe_path = resolve_workspace_path(workspace_dir, path)
        with open(safe_path, "r", encoding="utf-8") as f:
            content = f.read()
        return tool_result("success", content, path=safe_path)
    except Exception as e:
        return tool_result("error", str(e), path=path)


def write_file(path: str, content: str) -> str:
    try:
        if os.path.isabs(path):
            safe_path = path
        else:
            workspace_dir = CURRENT_WORKSPACE_DIR or ensure_workspace()
            safe_path = resolve_workspace_path(workspace_dir, path)
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(content)
        return tool_result("success", f"Successfully wrote to {safe_path}", path=safe_path)
    except Exception as e:
        return tool_result("error", str(e), path=path)


_WEB_SEARCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
}


def _do_web_search(query: str, timeout: int) -> list:
    """返回搜索结果列表，最多 5 条。"""
    encoded = urllib.parse.quote(query)
    url = f"https://duckduckgo.com/html/?q={encoded}"
    req = urllib.request.Request(url, headers=_WEB_SEARCH_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw_html = resp.read().decode("utf-8", errors="ignore")

    results = []
    for m in re.finditer(
        r'<a[^>]*class="result__a"[^>]*href="(.*?)"[^>]*>(.*?)</a>',
        raw_html, re.I | re.S
    ):
        href = html.unescape(m.group(1))
        title = re.sub(r"<.*?>", "", m.group(2))
        title = html.unescape(title).strip()
        if title and href:
            results.append({"title": title, "url": href})
        if len(results) >= 5:
            break
    return results


def web_search(query: str) -> str:
    last_err = None
    # 两次尝试：第一次 20s，超时后自动重试一次 30s
    for timeout in (20, 30):
        try:
            results = _do_web_search(query, timeout)
            return tool_result(
                "success",
                json.dumps({"query": query, "results": results}, ensure_ascii=False),
            )
        except Exception as e:
            last_err = e

    return tool_result(
        "error",
        f"Web search failed after retries: {last_err}. "
        "Tip: use fetch_url with a direct URL as an alternative.",
    )


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
