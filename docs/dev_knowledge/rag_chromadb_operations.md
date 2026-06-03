# RAG 与 ChromaDB 开发运维知识

本知识文档用于辅助 Agent 处理 RAG、Embedding、ChromaDB 和知识库入库相关任务。

## RAG 模块职责

RAG 知识增强模块负责：

- 加载 README、docs、任务书 PDF 和技术文档。
- 将长文档切分为 chunk。
- 调用 Embedding API 生成向量。
- 写入 ChromaDB collection。
- 通过 `rag_search(query, top_k)` 返回相关内容片段。
- 返回结果必须包含 `content`、`source` 和 `score`。

## Windows 下的 ChromaDB 注意事项

在 Windows 本机环境中，不建议使用 ChromaDB `PersistentClient` 执行 `upsert()`。该路径可能触发底层 access violation 崩溃。

推荐使用 Docker 中的 ChromaDB HTTP 服务：

```powershell
$env:CHROMA_MODE="http"
$env:CHROMA_HOST="localhost"
$env:CHROMA_PORT="8001"
```

端口约定：

- FastAPI 后端：`127.0.0.1:8000`
- Vite 前端：`localhost:3000`
- ChromaDB 容器：容器内 `8000`，宿主机映射 `8001`

Vite 代理应指向 FastAPI 的 `8000`，不要指向 ChromaDB 的 `8001`。

## 知识库清理与重新入库

当知识库混入 pytest 临时目录、tmp 文档或旧验收数据时，应清空 collection 后重新入库正式资料。

正式资料优先包括：

- 项目 README
- docs 目录
- agent/docs 目录
- api 文档
- 开发辅助知识文档
- 任务书 PDF

不要把 `.env`、真实 API Key、临时测试输出或虚拟环境目录入库。

## RAG 检索失败排查

- `OPENAI_API_KEY is not configured`：后端启动环境缺少 API Key。
- `Connection error`：检查 `OPENAI_BASE_URL`、网络和 API Key 是否可用。
- `rag_search failed: unexpected keyword argument`：检查工具包装层是否向 `tool_result()` 传入了不支持的参数。
- Chroma 连接失败：先运行 `get_rag_stats()`，确认 `status: ok`、`mode: http`、`port: 8001`。

