# tests/test_tools.py
import pytest
import os
import json
import re
from agent.backend.tools import execute_bash, read_file, write_file
from agent.backend.utils import parse_json_object

# 1. 命令行执行工具测试 (execute_bash)
def test_execute_bash_success():
    """测试 execute_bash 工具是否能正确执行基础命令"""
    result = execute_bash( "echo hello")
    assert type(result) is str  # 确保它是字符串
    assert "hello" in result    # 确保命令的输出里包含了 hello

def test_execute_bash_failure():
    """测试执行错误命令时，是否能安全捕获报错而不是让程序崩溃"""
    result = execute_bash("this_command_does_not_exist_12345")
    assert type(result) is str
    # 期望返回错误信息，而不是直接抛出 Python Exception
    assert "error" in result or "不是内部或外部命令" in result or "not found" in result.lower()

# 2. 文件读写工具测试 (read_file / write_file)
def test_file_read_write(tmp_path):
    """
    测试文件写入和读取的闭环。
    使用 pytest 内置的 tmp_path fixture,
    它会自动创建一个临时目录,测试结束后自动清理。
    """
    # 构建临时文件路径
    test_file_path = str(tmp_path / "agent_test_code.py")
    test_content = "print('Hello, Coding Agent!')"
    
    write_result = write_file(test_file_path, test_content)
    assert os.path.exists(test_file_path) # 确保文件落盘
    
    read_result = read_file(test_file_path)
    assert test_content in read_result    

def test_read_nonexistent_file():
    """测试读取不存在的文件时，工具的容错能力"""
    result = read_file("some_random_path_that_does_not_exist.txt")
    assert "error" in result or "不存在" in result or "no such file" in result

# 3. JSON 解析及其他 Utils 测试
def test_parse_standard_json():
    """测试 1: 最基础的标准 JSON 解析"""
    raw_text = '{"action": "write", "file": "test.py"}'
    result = parse_json_object(raw_text)
    
    assert isinstance(result, dict)
    assert result.get("action") == "write"
    assert result.get("file") == "test.py"

def test_parse_markdown_wrapped_json():
    """测试 2: 大模型最爱用的 Markdown 代码块包裹格式"""
    # 大模型经常输出带有 ```json 和 ``` 的内容
    llm_output = """```json
    {
        "tool": "execute_bash",
        "command": "pytest"
    }
    ```"""
    result = parse_json_object(llm_output)
    
    assert result.get("tool") == "execute_bash"
    assert result.get("command") == "pytest"

def test_parse_json_with_chatty_text():
    """测试 3: 带有大量啰嗦上下文的 JSON (前后都有自然语言)"""
    # 大模型经常会有诸如 "好的，我将为你执行以下命令：" 的前置语
    llm_output = """
    I understand your request. Here is the tool call you need:
    ```json
    {"tool": "read_file", "path": "main.py"}
    ```
    Let me know if you need anything else!
    """
    result = parse_json_object(llm_output)
    
    # 解析器应当能自动从这一堆废话中精准提取出 JSON 核心
    assert result.get("tool") == "read_file"
    assert result.get("path") == "main.py"

def test_parse_invalid_or_empty_json():
    """测试 4: 完全无效的字符串或纯文本（容错兜底测试）"""
    # 如果大模型彻底发疯，输出了完全不是 JSON 的内容
    messy_text = "我决定不调用任何工具，直接回答你的问题。"
    result = parse_json_object(messy_text)
    
    # 保证程序不抛出 JSONDecodeError 崩溃，而是返回空字典
    assert result == {}
    assert isinstance(result, dict)

