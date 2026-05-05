# 存储和外界交互的业务核心工具、安全防护及 JSON Schema 的映射层
import os
import re
import json
import html
import subprocess
import urllib.parse
import urllib.request
from typing import Dict, Any

from agent.backend.config import BLOCKED_BASH_PATTERNS
from agent.backend.utils import ensure_workspace, resolve_workspace_path, tool_result, safe_trim

CURRENT_WORKSPACE_DIR = None

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

def parse_tool_arguments(raw_arguments: str) -> Dict[str, Any]:
    if not raw_arguments: return {}
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
            encoding="utf-8",
            errors="replace",
            timeout=20,
            executable=os.environ.get("COMSPEC", None),
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
        if os.path.isabs(path):
            safe_path = path
        else:
            workspace_dir = CURRENT_WORKSPACE_DIR or ensure_workspace()
            safe_path = resolve_workspace_path(workspace_dir, path)
        with open(safe_path, "r", encoding="utf-8") as f: content = f.read()
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
        with open(safe_path, "w", encoding="utf-8") as f: f.write(content)
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
            if len(results) >= 5: break

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