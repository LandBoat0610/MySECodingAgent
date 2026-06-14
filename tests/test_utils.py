from agent.backend.utils import (
    parse_json_object,
    safe_trim,
    resolve_workspace_path,
    tool_result,
    now_str
)
import os
import sys
import re
import json
import tempfile
from pathlib import Path
import pytest

# 导入 agent 模块
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestUtils:
    """针对 utils.py 中工具函数的单元测试"""

    # ==================== parse_json_object ====================
    def test_parse_json_object_standard(self):
        """标准 JSON 字符串"""
        text = '{"action": "read_file", "path": "main.py"}'
        result = parse_json_object(text)
        assert result == {"action": "read_file", "path": "main.py"}

    def test_parse_json_object_markdown_with_lang(self):
        """markdown 代码块带 json 标记"""
        text = '''```json
{"name": "test", "value": 123}
```'''
        result = parse_json_object(text)
        assert result == {"name": "test", "value": 123}

    def test_parse_json_object_markdown_no_lang(self):
        """markdown 代码块无语言标记"""
        text = '''```
{"status": "ok"}
```'''
        result = parse_json_object(text)
        assert result == {"status": "ok"}

    def test_parse_json_object_bare_braces(self):
        """文本中混杂 JSON 对象（非代码块）"""
        text = '这是一些描述 {"result": "pass", "score": 100} 后面内容'
        result = parse_json_object(text)
        assert result == {"result": "pass", "score": 100}

    def test_parse_json_object_no_json(self):
        """完全不包含 JSON 的文本"""
        text = "只是一段普通文字"
        result = parse_json_object(text)
        assert result == {}

    def test_parse_json_object_empty_string(self):
        """空字符串"""
        result = parse_json_object("")
        assert result == {}

    def test_parse_json_object_invalid_json(self):
        """包含非法 JSON（缺少引号等）应返回空字典"""
        text = '{invalid json}'
        result = parse_json_object(text)
        assert result == {}

    # ==================== safe_trim ====================
    def test_safe_trim_no_truncate(self):
        """长度未超限，原样返回"""
        text = "Hello World"
        result = safe_trim(text, max_len=20)
        assert result == text

    def test_safe_trim_truncate(self):
        """长度超限，应截断并附带提示（后缀会增加总长度）"""
        text = "A" * 120
        max_len = 100
        result = safe_trim(text, max_len=max_len)
        # 开头一定是原内容的前 max_len 个字符
        assert result.startswith("A" * max_len)
        # 包含截断提示
        assert "[truncated" in result
        # 提示中注明被截去的字符数（120 - 100 = 20）
        assert "20 chars]" in result

    def test_safe_trim_none(self):
        """输入为 None 应返回空字符串"""
        result = safe_trim(None, max_len=50)
        assert result == ""

    def test_safe_trim_exact_length(self):
        """长度恰好等于 max_len"""
        text = "B" * 50
        result = safe_trim(text, max_len=50)
        assert result == text

    # ==================== resolve_workspace_path ====================
    def test_resolve_relative_path(self):
        """相对路径应正确解析到工作区内"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_in_ws = os.path.join(tmpdir, "sub", "file.txt")
            os.makedirs(os.path.dirname(file_in_ws), exist_ok=True)
            Path(file_in_ws).touch()
            resolved = resolve_workspace_path(tmpdir, "sub/file.txt")
            assert resolved == str(Path(file_in_ws).resolve())

    def test_resolve_absolute_path_inside_workspace(self):
        """绝对路径在工作区内部应正常返回"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_abs = os.path.join(tmpdir, "test.py")
            Path(file_abs).touch()
            resolved = resolve_workspace_path(tmpdir, file_abs)
            assert resolved == str(Path(file_abs).resolve())

    def test_resolve_escape_path_raises(self):
        """尝试越权访问工作区外的文件应抛出 PermissionError"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(PermissionError, match="escapes workspace"):
                resolve_workspace_path(tmpdir, "../secret.txt")

    def test_resolve_escape_with_absolute_outside(self):
        """绝对路径指到工作区外部也应报错"""
        with tempfile.TemporaryDirectory() as tmpdir:
            outside = "/etc/passwd"   # 在 Windows 上不会报找不到文件，只会报离开工作区
            with pytest.raises(PermissionError, match="escapes workspace"):
                resolve_workspace_path(tmpdir, outside)

    # ==================== tool_result ====================
    def test_tool_result_success(self):
        """成功状态的基本返回"""
        ret = tool_result("success", "文件已读取", path="/a/b.txt")
        data = json.loads(ret)
        assert data["status"] == "success"
        assert data["output"] == "文件已读取"
        assert data["path"] == "/a/b.txt"
        assert data["returncode"] is None
        assert data["meta"] == {}

    def test_tool_result_error(self):
        """错误状态"""
        ret = tool_result("error", "命令执行失败", returncode=1)
        data = json.loads(ret)
        assert data["status"] == "error"
        assert data["returncode"] == 1

    def test_tool_result_trims_output(self):
        from agent.backend.config import MAX_TOOL_OUTPUT
        long_msg = "X" * (MAX_TOOL_OUTPUT + 100)
        ret = tool_result("success", long_msg)
        data = json.loads(ret)
        output = data["output"]
        assert output.startswith("X" * MAX_TOOL_OUTPUT)
        assert "[truncated" in output
        assert "100 chars]" in output

    def test_tool_result_with_meta(self):
        """包含额外元数据"""
        ret = tool_result("success", "done", meta={"lines": 10})
        data = json.loads(ret)
        assert data["meta"] == {"lines": 10}

    # ==================== now_str ====================
    def test_now_str_format(self):
        """now_str 返回格式为 YYYY-MM-DD HH:MM:SS"""
        result = now_str()
        pattern = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$"
        assert re.match(pattern, result), f"格式不匹配: {result}"


# ==================== load_memory / save_memory ====================
class TestMemoryFunctions:
    def test_load_memory_file_not_exists(self, tmp_path, monkeypatch):
        from agent.backend.utils import load_memory
        monkeypatch.setattr("agent.backend.utils.MEMORY_FILE", str(tmp_path / "nonexistent.md"))
        assert load_memory() == ""

    def test_load_memory_file_with_content(self, tmp_path, monkeypatch):
        from agent.backend.utils import load_memory
        mem_file = tmp_path / "memory.md"
        mem_file.write_text("line1\nline2\nline3\n", encoding="utf-8")
        monkeypatch.setattr("agent.backend.utils.MEMORY_FILE", str(mem_file))
        content = load_memory()
        assert "line1" in content

    def test_save_and_load_memory(self, tmp_path, monkeypatch):
        from agent.backend.utils import save_memory, load_memory
        mem_file = tmp_path / "memory.md"
        monkeypatch.setattr("agent.backend.utils.MEMORY_FILE", str(mem_file))
        save_memory("task1", "result1")
        content = load_memory()
        assert "task1" in content
        assert "result1" in content


# ==================== _serialize_state ====================
class TestSerializeState:
    def test_removes_cancel_event(self):
        from agent.backend.utils import _serialize_state
        state = {"task": "hello", "_cancel_event": object(), "status": "ok"}
        result = _serialize_state(state)
        parsed = json.loads(result)
        assert "task" in parsed
        assert "status" in parsed
        assert "_cancel_event" not in parsed


# ==================== _state_outline_for_trace ====================
class TestStateOutlineForTrace:
    def test_none_input(self):
        from agent.backend.utils import _state_outline_for_trace
        assert _state_outline_for_trace(None) is None

    def test_empty_dict(self):
        from agent.backend.utils import _state_outline_for_trace
        assert _state_outline_for_trace({}) is None

    def test_filters_relevant_keys(self):
        from agent.backend.utils import _state_outline_for_trace
        state = {
            "status": "running",
            "current_task_index": 2,
            "current_task": "step",
            "target_file": "",
            "run_command": None,
            "reflections": 0,
            "unrelated": "ignored"
        }
        outline = _state_outline_for_trace(state)
        assert outline is not None
        assert outline["status"] == "running"
        assert outline["current_task_index"] == 2
        assert "unrelated" not in outline

    def test_includes_modified_files_tail(self):
        from agent.backend.utils import _state_outline_for_trace
        state = {"modified_files": ["a.py", "b.py", "c.py", "d.py", "e.py", "f.py", "g.py", "h.py", "i.py"]}
        outline = _state_outline_for_trace(state)
        assert "modified_files_tail" in outline
        assert len(outline["modified_files_tail"]) == 8


# ==================== _trace_runtime_meta ====================
class TestTraceRuntimeMeta:
    def test_no_runtime_metrics(self):
        from agent.backend.utils import _trace_runtime_meta
        assert _trace_runtime_meta({}) == {}
        assert _trace_runtime_meta(None) == {}

    def test_extracts_token_total(self):
        from agent.backend.utils import _trace_runtime_meta
        state = {"runtime_metrics": {"tokens": {"total": 1234}}}
        meta = _trace_runtime_meta(state)
        assert meta["tokens_total"] == 1234

    def test_extracts_tool_stats(self):
        from agent.backend.utils import _trace_runtime_meta
        state = {
            "runtime_metrics": {
                "tokens": {},
                "tool_calls": [
                    {"name": "read_file", "ok": True, "latency_ms": 100},
                    {"name": "write_file", "ok": False, "latency_ms": 200},
                ]
            }
        }
        meta = _trace_runtime_meta(state)
        assert meta["tool_events_count"] == 2
        assert meta["tool_success_rate"] == pytest.approx(0.5)
        assert meta["tool_avg_latency_ms"] == pytest.approx(150.0)


# ==================== register / unregister callbacks ====================
class TestCallbacks:
    def test_register_and_unregister(self):
        from agent.backend.utils import register_log_callback, unregister_log_callback, _LOG_CALLBACKS

        calls = []

        def cb(item):
            calls.append(item)

        register_log_callback(cb)
        assert cb in _LOG_CALLBACKS.values()

        unregister_log_callback(cb)
        assert cb not in _LOG_CALLBACKS.values()

    def test_unregister_nonexistent_no_error(self):
        from agent.backend.utils import unregister_log_callback
        def cb(x): pass
        unregister_log_callback(cb)  # should not raise


# ==================== save_trace ====================
class TestSaveTrace:
    def test_saves_json_and_mermaid(self, tmp_path, monkeypatch):
        from agent.backend.utils import save_trace
        json_path = tmp_path / "trace.json"
        mmd_path = tmp_path / "trace.mmd"
        monkeypatch.setattr("agent.backend.utils.TRACE_JSON", str(json_path))
        monkeypatch.setattr("agent.backend.utils.TRACE_MERMAID", str(mmd_path))

        trace = [
            {"time": "2026-01-01 00:00:00", "phase": "planner", "content": "step1", "meta": {}},
            {"time": "2026-01-01 00:00:01", "phase": "executor", "content": "step2", "meta": {}},
        ]
        save_trace(trace)

        assert json_path.exists()
        assert mmd_path.exists()

        with open(json_path, encoding="utf-8") as f:
            saved = json.load(f)
        assert len(saved) == 2
        assert saved[0]["phase"] == "planner"

        with open(mmd_path, encoding="utf-8") as f:
            mmd = f.read()
        assert "flowchart TD" in mmd
        assert "planner" in mmd
        assert "executor" in mmd


# ==================== ensure_workspace / prepare_workspace ====================
class TestEnsureWorkspace:
    def test_uses_env_var(self, tmp_path, monkeypatch):
        """设置环境变量时使用指定路径。"""
        from agent.backend.utils import ensure_workspace
        ws = str(tmp_path / "env_ws")
        monkeypatch.setenv("ZIZHI_AGENT_WORKSPACE", ws)
        result = ensure_workspace()
        assert os.path.isdir(result)
        assert result == os.path.abspath(ws)

    def test_creates_temp_dir_without_env(self, monkeypatch):
        """无环境变量时创建临时目录。"""
        from agent.backend.utils import ensure_workspace
        monkeypatch.delenv("ZIZHI_AGENT_WORKSPACE", raising=False)
        result = ensure_workspace()
        assert os.path.isdir(result)
        assert "zizhiagent_workspace_" in result


# ==================== load_prompts ====================
class TestLoadPrompts:
    def test_loads_from_default_path(self, monkeypatch):
        """从默认路径加载 prompts.yaml。"""
        from agent.backend.utils import load_prompts
        # 清除缓存
        monkeypatch.setattr("agent.backend.utils._PROMPTS_CACHE", None)
        result = load_prompts()
        assert isinstance(result, dict)
        assert "system_prompt" in result

    def test_uses_cache_on_second_call(self, monkeypatch):
        """第二次调用使用缓存。"""
        from agent.backend.utils import load_prompts
        monkeypatch.setattr("agent.backend.utils._PROMPTS_CACHE", None)
        result1 = load_prompts()
        result2 = load_prompts()
        assert result1 is result2  # same cached object

    def test_file_not_found_raises(self, monkeypatch):
        """文件不存在时抛出 FileNotFoundError。"""
        from agent.backend.utils import load_prompts
        monkeypatch.setattr("agent.backend.utils._PROMPTS_CACHE", None)
        with pytest.raises(FileNotFoundError):
            load_prompts("nonexistent_config.yaml")


# ==================== log_state ====================
class TestLogState:
    def test_appends_to_trace(self):
        from agent.backend.utils import log_state
        trace = []
        log_state(trace, "test_phase", "test content")
        assert len(trace) == 1
        assert trace[0]["phase"] == "test_phase"
        assert "time" in trace[0]
        assert "meta" in trace[0]

    def test_includes_state_outline(self):
        from agent.backend.utils import log_state
        trace = []
        state = {"status": "running", "task": "hello"}
        log_state(trace, "phase", "content", state=state)
        assert "state_outline" in trace[0]
        assert trace[0]["state_outline"]["status"] == "running"

    def test_session_status_in_trace(self):
        from agent.backend.utils import log_state
        trace = []
        state = {"status": "running"}
        log_state(trace, "phase", "content", state=state)
        assert trace[0]["session_status"] == "running"


# ==================== sync_workspace_file_back ====================
class TestSyncWorkspaceBack:
    def test_skips_when_idle_status(self):
        from agent.backend.utils import sync_workspace_file_back
        state = {
            "status": "idle",
            "trace": [],
            "session_id": "s1",
            "modified_files": ["test.py"],
            "workspace_dir": "/tmp",
            "project_root": "/tmp",
        }
        sync_workspace_file_back(state)
        # Should skip and log

    def test_skips_when_no_modified_files(self):
        from agent.backend.utils import sync_workspace_file_back
        state = {
            "status": "completed",
            "trace": [],
            "session_id": "s1",
            "modified_files": [],
            "workspace_dir": "/tmp",
            "project_root": "/tmp",
        }
        sync_workspace_file_back(state)

    def test_skips_when_no_project_root(self):
        from agent.backend.utils import sync_workspace_file_back
        state = {
            "status": "completed",
            "trace": [],
            "session_id": "s1",
            "modified_files": ["test.py"],
            "workspace_dir": "/tmp",
            "project_root": "",
        }
        sync_workspace_file_back(state)


# ==================== _safe_copy_file ====================
class TestSafeCopyFile:
    def test_copies_successfully(self, tmp_path):
        from agent.backend.utils import _safe_copy_file
        src = tmp_path / "src.txt"
        dst = tmp_path / "dst.txt"
        src.write_text("hello", encoding="utf-8")
        _safe_copy_file(str(src), str(dst))
        assert dst.exists()
        assert dst.read_text(encoding="utf-8") == "hello"

    def test_retries_on_permission_error(self, tmp_path, monkeypatch):
        from agent.backend.utils import _safe_copy_file
        import shutil
        src = tmp_path / "src2.txt"
        dst = tmp_path / "dst2.txt"
        src.write_text("retry-test", encoding="utf-8")

        call_count = [0]
        original_copy2 = shutil.copy2

        def mock_copy2(s, d):
            call_count[0] += 1
            if call_count[0] < 3:
                raise PermissionError("locked")
            return original_copy2(s, d)

        monkeypatch.setattr("shutil.copy2", mock_copy2)
        _safe_copy_file(str(src), str(dst))
        assert dst.exists()
        assert call_count[0] == 3
