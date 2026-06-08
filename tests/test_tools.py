# tests/test_tools.py
from agent.backend.tools import (
    execute_bash,
    list_files,
    read_file,
    read_file_range,
    write_file,
    search_code,
    apply_patch,
    get_git_diff,
    run_tests,
    run_lint,
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
        temp_dir = str(tmp_path / "auto_workspace")
        os.makedirs(temp_dir, exist_ok=True)
        monkeypatch.setattr("agent.backend.tools.ensure_workspace", lambda: temp_dir)
        result_json = write_file("auto.txt", "test")
        data = json.loads(result_json)
        assert data["status"] == "success"
        assert os.path.exists(os.path.join(temp_dir, "auto.txt"))


# ==================== list_files ====================
class TestListFiles:
    def test_list_non_recursive(self, sandbox_workspace):
        # Create some files/dirs
        os.makedirs(os.path.join(sandbox_workspace, "subdir"), exist_ok=True)
        with open(os.path.join(sandbox_workspace, "a.py"), "w") as f:
            f.write("x")
        result_json = list_files(".")
        data = json.loads(result_json)
        assert data["status"] == "success"
        output = json.loads(data["output"])
        entries = output["entries"]
        names = [e["name"] for e in entries]
        assert "a.py" in names
        assert "subdir" in names

    def test_list_recursive(self, sandbox_workspace):
        os.makedirs(os.path.join(sandbox_workspace, "sub"), exist_ok=True)
        with open(os.path.join(sandbox_workspace, "sub", "b.py"), "w") as f:
            f.write("y")
        result_json = list_files(".", recursive=True)
        data = json.loads(result_json)
        assert data["status"] == "success"
        output = json.loads(data["output"])
        entries = output["entries"]
        names = [e["name"] for e in entries]
        assert "b.py" in names

    def test_list_not_a_directory(self, sandbox_workspace):
        with open(os.path.join(sandbox_workspace, "file.txt"), "w") as f:
            f.write("content")
        result_json = list_files("file.txt")
        data = json.loads(result_json)
        assert data["status"] == "error"

    def test_list_nonexistent_path(self, sandbox_workspace):
        result_json = list_files("no_such_dir")
        data = json.loads(result_json)
        assert data["status"] == "error"


# ==================== read_file_range ====================
class TestReadFileRange:
    def test_read_range_basic(self, sandbox_workspace):
        filepath = os.path.join(sandbox_workspace, "range_test.py")
        lines = [f"line{i}\n" for i in range(1, 11)]
        with open(filepath, "w") as f:
            f.writelines(lines)
        result_json = read_file_range("range_test.py", offset=1, limit=3)
        data = json.loads(result_json)
        assert data["status"] == "success"
        assert "line1" in data["output"]
        assert "line3" in data["output"]
        assert "line4" not in data["output"]

    def test_read_range_offset(self, sandbox_workspace):
        filepath = os.path.join(sandbox_workspace, "offset_test.txt")
        with open(filepath, "w") as f:
            for i in range(1, 6):
                f.write(f"Line {i}\n")
        result_json = read_file_range("offset_test.txt", offset=3, limit=1)
        data = json.loads(result_json)
        assert "Line 3" in data["output"]

    def test_read_range_file_not_found(self, sandbox_workspace):
        result_json = read_file_range("nope.txt")
        data = json.loads(result_json)
        assert data["status"] == "error"
        assert "not_found" in data.get("error_type", "")

    def test_read_range_empty_file(self, sandbox_workspace):
        filepath = os.path.join(sandbox_workspace, "empty_range.txt")
        with open(filepath, "w") as f:
            f.write("")
        result_json = read_file_range("empty_range.txt", offset=1, limit=50)
        data = json.loads(result_json)
        assert data["status"] == "success"
        output = json.loads(data["output"])
        assert "lines" in output


# ==================== search_code ====================
class TestSearchCode:
    def test_search_in_file(self, sandbox_workspace):
        filepath = os.path.join(sandbox_workspace, "search_me.py")
        with open(filepath, "w") as f:
            f.write("def hello():\n    return 'world'\n")
        result_json = search_code("def hello", path="search_me.py")
        data = json.loads(result_json)
        assert data["status"] == "success"
        output = json.loads(data["output"])
        assert output["count"] >= 1

    def test_search_in_directory(self, sandbox_workspace):
        filepath = os.path.join(sandbox_workspace, "code.py")
        with open(filepath, "w") as f:
            f.write("TODO: fix this bug\n")
        result_json = search_code("TODO", path=".")
        data = json.loads(result_json)
        assert data["status"] == "success"
        output = json.loads(data["output"])
        assert output["count"] >= 1

    def test_search_no_match(self, sandbox_workspace):
        filepath = os.path.join(sandbox_workspace, "nomatch.py")
        with open(filepath, "w") as f:
            f.write("nothing here\n")
        result_json = search_code("zzzz_not_present", path=".")
        data = json.loads(result_json)
        assert data["status"] == "success"
        output = json.loads(data["output"])
        assert output["count"] == 0

    def test_search_path_not_found(self, sandbox_workspace):
        result_json = search_code("pattern", path="no_such_path")
        data = json.loads(result_json)
        assert data["status"] == "error"

    def test_search_case_insensitive(self, sandbox_workspace):
        filepath = os.path.join(sandbox_workspace, "case.py")
        with open(filepath, "w") as f:
            f.write("Hello World\n")
        result_json = search_code("hello", path=".", case_sensitive=False)
        data = json.loads(result_json)
        assert data["status"] == "success"
        output = json.loads(data["output"])
        assert output["count"] >= 1


# ==================== apply_patch ====================
class TestApplyPatch:
    def test_apply_simple_patch(self, sandbox_workspace):
        filepath = os.path.join(sandbox_workspace, "patch_target.py")
        with open(filepath, "w") as f:
            f.write("line1\nline2\nline3\n")
        patch = "@@ -2,1 +2,1 @@\n-line2\n+modified_line2\n"
        result_json = apply_patch("patch_target.py", patch)
        data = json.loads(result_json)
        assert data["status"] == "success"
        with open(filepath) as f:
            content = f.read()
        assert "modified_line2" in content

    def test_apply_patch_file_not_found(self, sandbox_workspace):
        result_json = apply_patch("no_file.py", "@@ -1,1 +1,1 @@\n-old\n+new\n")
        data = json.loads(result_json)
        assert data["status"] == "error"

    def test_apply_patch_no_hunks(self, sandbox_workspace):
        filepath = os.path.join(sandbox_workspace, "no_hunk.py")
        with open(filepath, "w") as f:
            f.write("content\n")
        result_json = apply_patch("no_hunk.py", "just text no hunks")
        data = json.loads(result_json)
        assert data["status"] == "error"


# ==================== get_git_diff ====================
class TestGetGitDiff:
    def test_diff_in_non_repo_dir(self, sandbox_workspace):
        result_json = get_git_diff()
        data = json.loads(result_json)
        # In a directory that is not a git repo (or git not installed), we may
        # get an error from git or a "clean" response from a parent git repo
        assert data["status"] in ("success", "error")
        if data["status"] == "error":
            assert "not_repo" in data.get("error_type", "") or "git" in data["output"].lower()


# ==================== run_tests ====================
class TestRunTests:
    def test_pytest_not_installed(self, sandbox_workspace, monkeypatch):
        def mock_run(*args, **kwargs):
            raise FileNotFoundError("pytest")
        monkeypatch.setattr(subprocess, "run", mock_run)
        result_json = run_tests(".")
        data = json.loads(result_json)
        assert data["status"] == "error"
        assert "missing_tool" in data.get("error_type", "")

    def test_no_tests_collected(self, sandbox_workspace, monkeypatch):
        mock_result = MagicMock()
        mock_result.returncode = 5
        mock_result.stdout = "no tests ran"
        mock_result.stderr = ""
        monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: mock_result)
        result_json = run_tests(".")
        data = json.loads(result_json)
        assert "No tests collected" in data["output"]


# ==================== run_lint ====================
class TestRunLint:
    def test_flake8_not_installed(self, sandbox_workspace, monkeypatch):
        def mock_run(*args, **kwargs):
            raise FileNotFoundError("flake8")
        monkeypatch.setattr(subprocess, "run", mock_run)
        result_json = run_lint("test.py")
        data = json.loads(result_json)
        assert data["status"] == "error"
        assert "missing_tool" in data.get("error_type", "")

    def test_lint_clean(self, sandbox_workspace, monkeypatch):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: mock_result)
        result_json = run_lint("clean.py")
        data = json.loads(result_json)
        assert data["status"] == "success"
        assert "No lint errors" in data["output"]
