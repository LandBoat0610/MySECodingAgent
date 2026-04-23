# tests/test_tools.py
import pytest
from agent.backend.tools import execute_bash
from agent.backend.utils import parse_json_object

def test_execute_bash_success():
    """测试 execute_bash 工具是否能正确执行基础命令"""
    result = execute_bash( "echo hello")
    assert type(result) is str  # 确保它是字符串
    assert "hello" in result    # 确保命令的输出里包含了 hello

def test_parse_json_object_robustness():
    """测试 JSON 解析工具的鲁棒性"""
    # 传入乱码，断言它是否能安全返回空字典而不崩溃
    result = parse_json_object("这是一个无法解析的乱码字符串")
    assert result == {}