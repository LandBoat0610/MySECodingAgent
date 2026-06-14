# Python、FastAPI 与 pytest 开发知识

本知识文档用于辅助 Agent 编写 Python 后端代码和测试。

## Python 函数规范

新增函数应包含类型标注：

```python
def add(a: int, b: int) -> int:
    return a + b
```

当函数可能失败时，优先返回结构化结果或抛出明确异常，不要吞掉错误。

## pytest 测试规范

测试文件命名：

```text
test_calc_utils.py
```

测试函数命名：

```python
def test_add_returns_sum():
    assert add(2, 3) == 5
```

涉及外部服务、网络、数据库或 LLM API 的测试，应使用 mock、fixture 或独立临时资源，避免污染真实数据。

## FastAPI 接口规范

FastAPI 接口应：

- 使用 Pydantic schema 描述请求和响应。
- 对不存在的资源返回明确的 HTTP 错误。
- WebSocket 中应捕获异常并发送 error event，避免直接崩溃断连。
- 不要在接口中直接硬编码密钥或环境配置。

## Windows 开发注意事项

在 Windows PowerShell 中运行 Python 测试优先使用：

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q --tb=short
```

不要默认使用 Linux 的 `./program` 运行方式。Windows 下运行 exe 通常直接使用：

```powershell
main_exec.exe
```

## RAG 测试注意事项

ChromaDB 在 Windows 本机 `PersistentClient.upsert()` 可能触发底层崩溃。开发和验收优先使用 Docker HTTP ChromaDB：

```powershell
$env:CHROMA_MODE="http"
$env:CHROMA_HOST="localhost"
$env:CHROMA_PORT="8001"
```

