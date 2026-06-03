# tests/test_tools.py
from agent.backend.tools import (
    execute_bash,
    read_file,
    write_file,
    web_search,
    fetch_url,
    parse_tool_arguments,
)
import json
import os
import sys
import subprocess
import urllib.request
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
# 导入 agent 模块
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


# ==================== Fixtures ====================

@pytest.fixture(autouse=True)
def reset_global_workspace(monkeypatch):
    """每个测试前保证 CURRENT_WORKSPACE_DIR 恢复为 None,避免测试间干扰"""
    monkeypatch.setattr("agent.backend.tools.CURRENT_WORKSPACE_DIR", None)


@pytest.fixture
def sandbox_workspace(tmp_path, monkeypatch):
    """提供一个固定的临时工作区目录，并注入到 CURRENT_WORKSPACE_DIR"""
    workspace = str(tmp_path / "workspace")
    os.makedirs(workspace, exist_ok=True)
    monkeypatch.setattr("agent.backend.tools.CURRENT_WORKSPACE_DIR", workspace)
    return workspace


# ==================== parse_tool_arguments ====================
class TestParseToolArguments:
    def test_valid_json_dict(self):
        raw = '{"command": "echo hello"}'
        result = parse_tool_arguments(raw)
        assert result == {"command": "echo hello"}

    def test_valid_json_non_dict_returns_empty(self):
        raw = "[1, 2, 3]"
        result = parse_tool_arguments(raw)
        assert result == {}

    def test_invalid_json_returns_error_key(self):
        raw = '{invalid'
        result = parse_tool_arguments(raw)
        assert "_argument_error" in result
        assert "Invalid JSON arguments" in result["_argument_error"]

    def test_empty_string_returns_empty(self):
        assert parse_tool_arguments("") == {}


# ==================== execute_bash ====================

class TestExecuteBash:
    def test_successful_command(self, sandbox_workspace):
        result_json = execute_bash("echo hello")
        data = json.loads(result_json)
        assert data["status"] == "success"
        assert "hello" in data["output"]
        assert data["returncode"] == 0
        assert data["path"] == sandbox_workspace

    def test_failed_command(self, sandbox_workspace):
        result_json = execute_bash("this_command_does_not_exist_12345")
        data = json.loads(result_json)
        assert data["status"] == "error"
        assert data["returncode"] != 0
        # 输出中应该包含标准错误信息
        assert "STDERR" in data["output"] or "not found" in data["output"].lower() or "不是内部或外部命令" in data["output"]

    def test_blocked_dangerous_command(self, sandbox_workspace, monkeypatch):
        # 注入一个模拟的危险模式，确保阻塞逻辑生效
        monkeypatch.setattr("agent.backend.tools.BLOCKED_BASH_PATTERNS", [r"rm\s+-rf"])
        result_json = execute_bash("rm -rf /")
        data = json.loads(result_json)
        assert data["status"] == "error"
        assert "Blocked" in data["output"]

    def test_command_timeout(self, sandbox_workspace, monkeypatch):
        # 模拟 subprocess.run 抛出 TimeoutExpired
        def mock_run(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="sleep", timeout=20)
        monkeypatch.setattr(subprocess, "run", mock_run)
        result_json = execute_bash("sleep 30")
        data = json.loads(result_json)
        assert data["status"] == "error"
        assert "timed out" in data["output"].lower()

    def test_command_exception(self, sandbox_workspace, monkeypatch):
        # 模拟其他异常
        def mock_run(*args, **kwargs):
            raise OSError("disk full")
        monkeypatch.setattr(subprocess, "run", mock_run)
        result_json = execute_bash("any")
        data = json.loads(result_json)
        assert data["status"] == "error"
        assert "disk full" in data["output"]


# ==================== read_file ====================

class TestReadFile:
    def test_read_existing_file_relative(self, sandbox_workspace):
        rel_path = "notes.txt"
        abs_path = os.path.join(sandbox_workspace, rel_path)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write("hello agent")
        result_json = read_file(rel_path)
        data = json.loads(result_json)
        assert data["status"] == "success"
        assert "hello agent" in data["output"]
        # 返回的路径应为绝对路径
        assert data["path"] == abs_path

    def test_read_existing_file_absolute_bypass_check(self, sandbox_workspace):
        # 当前版本中绝对路径会跳过沙箱检查，这里只测试能正常读取
        abs_path = os.path.join(sandbox_workspace, "direct.txt")
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write("direct")
        result_json = read_file(abs_path)
        data = json.loads(result_json)
        assert data["status"] == "success"
        assert "direct" in data["output"]

    def test_read_nonexistent_file(self, sandbox_workspace):
        result_json = read_file("no_such_file.txt")
        data = json.loads(result_json)
        assert data["status"] == "error"
        # 错误信息应包含文件未找到
        assert ("no such file" in data["output"].lower()
                or "不存在" in data["output"]
                or "not found" in data["output"].lower())

    def test_read_outside_workspace_blocked(self, sandbox_workspace):
        # 尝试用相对路径越权（../../etc）
        result_json = read_file("../outside.txt")
        data = json.loads(result_json)
        assert data["status"] == "error"
        # resolve_workspace_path 会抛出 PermissionError，被捕获为 error
        assert "escapes workspace" in data["output"].lower() or "permission" in data["output"].lower()


# ==================== write_file ====================

class TestWriteFile:
    def test_write_and_check_existence(self, sandbox_workspace):
        rel_path = "sub/demo.py"
        abs_path = os.path.join(sandbox_workspace, rel_path)
        content = "print('ok')"
        result_json = write_file(rel_path, content)
        data = json.loads(result_json)
        assert data["status"] == "success"
        assert os.path.exists(abs_path)
        with open(abs_path, "r", encoding="utf-8") as f:
            assert f.read() == content
        # 使用 Path 归一化比较，兼容 Windows 混合分隔符
        assert Path(data["path"]) == Path(abs_path)

    def test_write_absolute_path_bypass(self, sandbox_workspace):
        abs_path = os.path.join(sandbox_workspace, "abs.py")
        result_json = write_file(abs_path, "x=1")
        data = json.loads(result_json)
        assert data["status"] == "success"
        assert os.path.exists(abs_path)

    def test_write_outside_workspace_blocked(self, sandbox_workspace):
        result_json = write_file("../forbidden.txt", "secret")
        data = json.loads(result_json)
        assert data["status"] == "error"
        assert "escapes workspace" in data["output"].lower() or "permission" in data["output"].lower()

    def test_write_to_directory_creates_parent(self, sandbox_workspace):
        rel_path = "a/b/c/file.txt"
        result_json = write_file(rel_path, "deep")
        data = json.loads(result_json)
        assert data["status"] == "success"
        assert os.path.isfile(os.path.join(sandbox_workspace, rel_path))


# ==================== web_search ====================

class TestWebSearch:
    @patch("agent.backend.tools.urllib.request.urlopen")
    def test_normal_search_returns_results(self, mock_urlopen, sandbox_workspace):
        # 模拟 DuckDuckGo 返回的 HTML
        fake_html = """<html>
            <a class="result__a" href="http://example.com">Example Title</a>
            <a class="result__a" href="http://test.com">Test Page</a>
        </html>"""
        mock_response = MagicMock()
        mock_response.read.return_value = fake_html.encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result_json = web_search("test query")
        data = json.loads(result_json)
        assert data["status"] == "success"
        results = json.loads(data["output"])["results"]
        assert len(results) == 2
        assert results[0]["title"] == "Example Title"
        assert results[0]["url"] == "http://example.com"

    @patch("agent.backend.tools.urllib.request.urlopen")
    def test_search_network_error(self, mock_urlopen, sandbox_workspace):
        mock_urlopen.side_effect = urllib.error.URLError("timeout")
        result_json = web_search("anything")
        data = json.loads(result_json)
        assert data["status"] == "error"
        assert "timeout" in data["output"]


# ==================== fetch_url ====================

class TestFetchUrl:
    @patch("agent.backend.tools.urllib.request.urlopen")
    def test_fetch_text_page(self, mock_urlopen):
        fake_html = "<html><body><p>Hello World</p></body></html>"
        mock_response = MagicMock()
        mock_response.read.return_value = fake_html.encode("utf-8")
        mock_response.headers.get.return_value = "text/html"
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result_json = fetch_url("http://dummy.com")
        data = json.loads(result_json)
        assert data["status"] == "success"
        assert "Hello World" in data["output"]
        # 应该去掉 HTML 标签
        assert "<p>" not in data["output"]

    @patch("agent.backend.tools.urllib.request.urlopen")
    def test_fetch_with_script_and_style_removed(self, mock_urlopen):
        fake_html = """
        <html><head><style>body{}</style></head>
        <body><script>alert(1)</script>Visible Text</body></html>
        """
        mock_response = MagicMock()
        mock_response.read.return_value = fake_html.encode("utf-8")
        mock_response.headers.get.return_value = "text/html"
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result_json = fetch_url("http://dummy.com")
        data = json.loads(result_json)
        assert data["status"] == "success"
        output = data["output"]
        assert "Visible Text" in output
        assert "alert" not in output

    @patch("agent.backend.tools.urllib.request.urlopen")
    def test_fetch_network_error(self, mock_urlopen):
        from urllib.error import URLError
        mock_urlopen.side_effect = URLError("connection refused")
        result_json = fetch_url("http://bad.url")
        data = json.loads(result_json)
        assert data["status"] == "error"
        assert "connection refused" in data["output"]


class TestRagSearchTool:
    def test_rag_search_success_wraps_sources_in_meta(self, monkeypatch):
        from agent.backend import tools as tools_mod

        def mock_backend_rag_search(query, top_k):
            return {
                "query": query,
                "top_k": top_k,
                "results": [
                    {"content": "NEBULA_RAG_7319", "source": "README.md", "score": 0.9}
                ],
            }

        monkeypatch.setattr("agent.backend.rag.rag_search", mock_backend_rag_search)
        result_json = tools_mod.rag_search("internal code", top_k=3)
        data = json.loads(result_json)

        assert data["status"] == "success"
        assert data["meta"]["rag_sources"][0]["source"] == "README.md"
        output = json.loads(data["output"])
        assert output["results"][0]["content"] == "NEBULA_RAG_7319"


# ==================== Integration & Edge Cases ====================
class TestEdgeCases:
    def test_execute_bash_with_unicode(self, sandbox_workspace):
        """确保命令输出中包含 Unicode 时不会崩溃（在 Windows 上可能乱码，但执行应成功）"""
        result_json = execute_bash("echo hello_unicode")
        data = json.loads(result_json)
        assert data["status"] == "success"
        # 不检查具体非 ASCII 字符，只验证正常完成

    def test_write_and_read_empty_file(self, sandbox_workspace):
        result_json = write_file("empty.txt", "")
        data = json.loads(result_json)
        assert data["status"] == "success"
        result_json = read_file("empty.txt")
        data = json.loads(result_json)
        assert data["status"] == "success"
        assert data["output"] == ""

    def test_workspace_not_set_uses_temp(self, tmp_path, monkeypatch):
        # 确保 CURRENT_WORKSPACE_DIR 是 None 时，工具会自己创建一个临时目录
        # 注意：由于 autouse fixture 会重置为 None，这里直接调用即可
        # 但我们需要保证调用时确实为 None
        monkeypatch.setattr("agent.backend.tools.CURRENT_WORKSPACE_DIR", None)
        # 同时要避免 ensure_workspace 真的创建一个临时目录，因为无法预测路径。
        # 我们可以 mock ensure_workspace 返回一个已知的临时路径
        temp_dir = str(tmp_path / "auto_workspace")
        os.makedirs(temp_dir, exist_ok=True)
        monkeypatch.setattr("agent.backend.tools.ensure_workspace", lambda: temp_dir)
        result_json = write_file("auto.txt", "test")
        data = json.loads(result_json)
        assert data["status"] == "success"
        assert os.path.exists(os.path.join(temp_dir, "auto.txt"))
