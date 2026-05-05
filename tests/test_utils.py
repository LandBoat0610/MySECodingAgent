import os
import sys
import re
import json
import tempfile
from pathlib import Path
import pytest

# 导入 agent 模块
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent.backend.utils import (
    parse_json_object,
    safe_trim,
    resolve_workspace_path,
    tool_result,
    now_str
)


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
            assert resolved == file_in_ws

    def test_resolve_absolute_path_inside_workspace(self):
        """绝对路径在工作区内部应正常返回"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_abs = os.path.join(tmpdir, "test.py")
            Path(file_abs).touch()
            resolved = resolve_workspace_path(tmpdir, file_abs)
            assert resolved == file_abs

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