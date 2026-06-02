import threading
from typing import Callable
import os
import re
import json
import yaml
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Literal

from agent.backend.config import (
    DEFAULT_WORKSPACE_PREFIX, MEMORY_FILE,
    TRACE_JSON, TRACE_MERMAID, MAX_TOOL_OUTPUT
)
from agent.backend.state import AgentState

_PROMPTS_CACHE = None


def load_prompts(config_path="prompts.yaml"):
    """读取并缓存 YAML 配置文件"""
    global _PROMPTS_CACHE
    if _PROMPTS_CACHE is not None:
        return _PROMPTS_CACHE

    # 指向根目录下的 prompts.yaml
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    actual_path = os.path.join(base_dir, config_path)

    if not os.path.exists(actual_path):
        raise FileNotFoundError(f"找不到配置文件: {actual_path}，请检查路径！")

    with open(actual_path, "r", encoding="utf-8") as f:
        _PROMPTS_CACHE = yaml.safe_load(f)  # 使用 safe_load 保证安全性

    return _PROMPTS_CACHE


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
    text = text.strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        pass

    markdown_match = re.search(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        text,
        re.S
    )
    if markdown_match:
        try:
            data = json.loads(markdown_match.group(1))
            return data if isinstance(data, dict) else {}
        except Exception:
            pass

    json_match = re.search(
        r"(\{.*\})",
        text,
        re.S
    )
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            return data if isinstance(data, dict) else {}
        except Exception:
            pass

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
        stdout: str = "",
        stderr: str = "",
        summary: str = "",
        error_type: Optional[str] = None,
        modified_files: Optional[List[str]] = None) -> str:
    return json.dumps({
        "status": status,
        "success": status == "success",
        "output": safe_trim(output),
        "summary": summary,
        "stdout": stdout,
        "stderr": stderr,
        "error_type": error_type,
        "path": path,
        "returncode": returncode,
        "meta": meta or {},
        "modified_files": modified_files or [],
    }, ensure_ascii=False)


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


def _serialize_state(state: Dict[str, Any]) -> str:
    clean = {k: v for k, v in state.items() if k != "_cancel_event"}
    return json.dumps(clean, ensure_ascii=False)


def update_session_state(session_id: str, state: Dict[str, Any], status: Optional[str] = None) -> None:
    from agent.backend.database import get_connection
    try:
        snapshot = _serialize_state(state)
        effective_status = status or state.get("status")
        with get_connection() as conn:
            if effective_status:
                conn.execute(
                    "UPDATE sessions SET state_snapshot = ?, status = ? WHERE id = ?",
                    (snapshot, effective_status, session_id),
                )
            else:
                conn.execute(
                    "UPDATE sessions SET state_snapshot = ? WHERE id = ?",
                    (snapshot, session_id),
                )
    except Exception as e:
        print(f"Error updating session state: {e}")


# 以 session_id 为 key，每个会话最多只有一个活跃回调
# 避免 WebSocket 重连导致回调重复积累（重连 N 次 → N 倍日志的问题）
_LOG_CALLBACKS: Dict[str, Callable] = {}
_LOG_CALLBACKS_LOCK = threading.Lock()


def register_log_callback(callback, session_id: str = "__global__"):
    with _LOG_CALLBACKS_LOCK:
        _LOG_CALLBACKS[session_id] = callback


def unregister_log_callback(callback, session_id: str = "__global__"):
    with _LOG_CALLBACKS_LOCK:
        if _LOG_CALLBACKS.get(session_id) is callback:
            del _LOG_CALLBACKS[session_id]


def _state_outline_for_trace(state: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not state or not isinstance(state, dict):
        return None
    out: Dict[str, Any] = {}
    for k in ("status", "current_task_index", "current_task", "target_file", "run_command", "reflections"):
        if k not in state:
            continue
        v = state[k]
        if v is None or v == "" or v == []:
            continue
        out[k] = v
    mf = state.get("modified_files")
    if isinstance(mf, list) and mf:
        out["modified_files_tail"] = mf[-8:]
    return out or None


def _trace_runtime_meta(state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not state or not isinstance(state.get("runtime_metrics"), dict):
        return {}
    rm = state["runtime_metrics"]
    tok = (rm.get("tokens") or {}).get("total")
    out: Dict[str, Any] = {}
    if tok is not None:
        out["tokens_total"] = int(tok)
    ev = rm.get("tool_calls") or []
    if isinstance(ev, list):
        out["tool_events_count"] = len(ev)
        ok_n = sum(1 for e in ev if isinstance(e, dict) and e.get("ok"))
        out["tool_success_rate"] = round(ok_n / len(ev), 4) if ev else None
        lat_sum = sum(float(e.get("latency_ms") or 0) for e in ev if isinstance(e, dict))
        out["tool_avg_latency_ms"] = round(lat_sum / len(ev), 2) if ev else None
    return out


def log_state(
    trace: List[Dict[str, Any]],
    phase: str,
    content: str,
    meta: Optional[dict] = None,
    session_id: Optional[str] = None,
    state: Optional[Dict[str, Any]] = None,
) -> None:
    merged_meta = dict(meta or {})
    merged_meta.update(_trace_runtime_meta(state))
    item = {
        "time": now_str(),
        "phase": phase,
        "content": safe_trim(content, 1600),
        "meta": merged_meta,
    }
    outline = _state_outline_for_trace(state)
    if outline:
        item["state_outline"] = outline
    if state and isinstance(state, dict) and "status" in state:
        item["session_status"] = state["status"]
    trace.append(item)
    try:
        print(f"[{item['time']}] [{phase.upper()}] {safe_trim(content, 180)}")
    except UnicodeEncodeError:
        pass

    # 如果提供了 session_id 和 state，则同步到数据库
    if session_id and state:
        update_session_state(session_id, state)

    # 调用所有注册的回调（用于 WebSocket 实时推送）
    # 每个 session_id 最多一个回调，避免重连积累导致重复推送
    with _LOG_CALLBACKS_LOCK:
        callbacks_snapshot = list(_LOG_CALLBACKS.items())
    for sid_key, cb in callbacks_snapshot:
        try:
            cb(item)
        except Exception:
            with _LOG_CALLBACKS_LOCK:
                if _LOG_CALLBACKS.get(sid_key) is cb:
                    del _LOG_CALLBACKS[sid_key]


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

# def prepare_workspace_with_target(task: str, workspace_dir: str) -> Dict[str, Any]:
#     match = re.search(r"([a-zA-Z0-9_./-]+\.(?:py|cpp|c|js|java|txt))\b", task)
#     if not match:
#         return {
#             "original_target_path": "",
#             "should_sync_back": False,
#         }

#     candidate = match.group(1)
#     original_path = os.path.abspath(candidate)

#     #如果文件已经存在，将其复制到工作区给 Agent 阅读和修改
#     if os.path.exists(candidate):
#         target = resolve_workspace_path(workspace_dir, os.path.basename(candidate))
#         shutil.copy(candidate, target)

#     # 无论文件之前存不存在，只要有明确的目标文件，统统允许同步
#     return {
#         "original_target_path": original_path,
#         "should_sync_back": True,
#     }


def prepare_workspace(workspace_dir: str) -> Dict[str, Any]:
    # 以当前执行命令所在的目录作为项目的根目录
    project_root = os.path.abspath(os.getcwd())

    # 将整个项目目录拷贝进沙箱
    # 为了防止把 .git 库或虚拟环境之类巨大的文件夹拷进去拖慢速度，加入ignore
    try:
        shutil.copytree(
            project_root,
            workspace_dir,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns('.git', '__pycache__', 'venv', 'node_modules', '.idea', '.vscode')
        )
    except Exception as e:
        print(f"Warning: 复制工作区时发生错误: {e}")

    return {
        "project_root": project_root
    }


def sync_workspace_file_back(state: AgentState) -> None:
    trace = state.get("trace", [])
    session_id = state.get("session_id")

    final_status = state.get("status", "")
    if final_status in ("idle", "awaiting_approval", "running", "needs_fix", "next_step"):
        log_state(trace, "sync_back_skip",
                  f"Skip sync-back because status is {final_status}", session_id=session_id, state=state)
        return

    modified_files = set(state.get("modified_files", []))
    if not modified_files:
        log_state(trace, "sync_back_skip", "Skip sync-back because no files were modified",
                  session_id=session_id, state=state)
        return

    workspace_dir = state.get("workspace_dir", "")
    project_root = state.get("project_root", "")

    if not project_root:
        log_state(trace, "sync_back_skip", "Skip sync-back because project_root is empty",
                  session_id=session_id, state=state)
        return

    for file_path in modified_files:
        try:
            workspace_file = resolve_workspace_path(workspace_dir, file_path)

            if not os.path.exists(workspace_file):
                log_state(trace, "sync_back_skip",
                          f"Workspace file does not exist: {workspace_file}", session_id=session_id, state=state)
                continue

            rel_path = os.path.relpath(workspace_file, workspace_dir)
            dest_file = os.path.join(project_root, rel_path)

            dest_dir = os.path.dirname(dest_file)
            if dest_dir:
                os.makedirs(dest_dir, exist_ok=True)

            _safe_copy_file(workspace_file, dest_file)

            log_state(trace, "sync_back_success",
                      f"Synced back: {rel_path} -> {dest_file}", session_id=session_id, state=state)
        except PermissionError as e:
            log_state(trace, "sync_back_warning",
                      f"File locked, skip sync {file_path}: {e}", session_id=session_id, state=state)
        except Exception as e:
            log_state(trace, "sync_back_error",
                      f"Failed to sync {file_path} back: {e}", session_id=session_id, state=state)


def _safe_copy_file(src: str, dst: str, max_retries: int = 3) -> None:
    """安全复制文件，处理 Windows 文件锁定问题"""
    import time

    for attempt in range(max_retries):
        try:
            shutil.copy2(src, dst)
            return
        except PermissionError:
            if attempt < max_retries - 1:
                time.sleep(0.5 * (attempt + 1))
                continue

            with open(src, 'rb') as f:
                content = f.read()
            with open(dst + '.tmp', 'wb') as f:
                f.write(content)
            try:
                os.replace(dst + '.tmp', dst)
            except PermissionError:
                os.remove(dst + '.tmp')
                raise
