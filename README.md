# Autonomous Coding Agent Platform

一个面向软件开发任务的智能体平台，提供项目管理、会话管理、任务规划、工具调用、代码执行、文件读写、测试验证、实时执行轨迹展示、评测中心，以及 RAG 知识增强能力。

当前版本的一个特点是：让 Agent 不只依赖当前对话上下文，还可以通过 `rag_search` 检索开发知识库，在执行代码任务、测试任务、调试任务和安全检查任务时获得额外上下文。

---

## 1. 项目简介

本项目是一个全栈 Agent 平台：

- 后端：FastAPI + SQLite + Agent 工作流 + 工具调用 + RAG 检索。
- 前端：Vue 3 + Vite + Pinia，提供项目、会话、文件预览、执行轨迹和评测中心界面。
- RAG：使用 ChromaDB 作为向量数据库，支持文档入库、语义检索、来源展示和相似度返回。
- 测试：后端使用 pytest，前端使用 Vitest。

当前项目中的 RAG 定位为：**辅助开发任意项目的通用开发知识库**。

也就是说，当前长期保留在知识库里的内容主要是通用开发规则、测试规则、调试规则、安全规则、前后端协作规则和 ChromaDB/RAG 运维知识。这个知识库不是专门介绍本 Agent 平台自己的说明书；当 Agent 要辅助某个具体项目时，可以再把该目标项目的 README、docs、任务书、技术文档单独入库。

---

## 2. 核心功能

### 2.1 Agent 开发辅助

Agent 可以接收自然语言任务，并自动完成：

- 理解用户任务。
- 生成执行计划。
- 等待用户确认计划。
- 调用工具执行文件读写、代码搜索、命令运行、测试执行等操作。
- 在需要知识库上下文时调用 `rag_search`。
- 根据工具结果继续推理。
- 输出最终结果。
- 在部分失败场景下尝试自动修复。

### 2.2 项目与会话管理

前端支持：

- 创建项目。
- 管理项目工作区。
- 创建会话。
- 在会话中发送任务。
- 查看 Agent 回复。
- 查看执行计划、工具调用、工具结果和错误信息。

### 2.3 文件与代码操作

Agent 后端提供多种工具能力，包括：

| 工具 | 作用 |
|---|---|
| `read_file` | 读取工作区文件 |
| `write_file` | 写入工作区文件 |
| `list_files` / 文件树相关接口 | 查看工作区结构 |
| `execute_bash` | 执行命令，例如运行测试 |
| `search_code` | 搜索代码内容 |
| `web_search` / `fetch_url` | 搜索和抓取网页内容 |
| `rag_search` | 检索本地 RAG 知识库 |

### 2.4 RAG 知识增强

RAG 用来解决这类问题：

- 用户问的是项目知识库、开发规则、测试规则、调试规则。
- 用户要求“先检索知识库再回答”。
- 用户要求“根据项目知识库创建代码或测试”。
- Agent 执行任务时需要引用已有文档，而不是凭空回答。

简单数学、闲聊、无需知识库的普通问题，不应该触发 RAG。

### 2.5 评测中心

项目内包含评测中心，用于批量评估 Agent 的表现，支持：

- 评测任务管理。
- 评测数据集。
- 运行结果记录。
- 指标展示。
- 图表展示。
- 过程和结果维度分析。

---

## 3. 系统架构

```text
┌────────────────────────────────────────────────────────────┐
│                     Frontend: Vue 3 + Vite                 │
│                                                            │
│  地址: http://localhost:3000                               │
│                                                            │
│  功能:                                                     │
│  - 项目管理                                                │
│  - 会话管理                                                │
│  - 文件预览                                                │
│  - 聊天与执行轨迹                                          │
│  - 计划确认                                                │
│  - 评测中心                                                │
└───────────────────────────┬────────────────────────────────┘
                            │ HTTP + WebSocket
┌───────────────────────────┴────────────────────────────────┐
│                    Backend: FastAPI                         │
│                                                            │
│  地址: http://127.0.0.1:8000                               │
│                                                            │
│  功能:                                                     │
│  - API 路由                                                │
│  - Agent 工作流                                            │
│  - 工具调用                                                │
│  - SQLite 持久化                                           │
│  - RAG 检索接口                                            │
│  - 评测任务执行                                            │
└───────────────┬───────────────────────────────┬────────────┘
                │                               │
                │ OpenAI-compatible API         │ Chroma HTTP
                │                               │
┌───────────────┴──────────────┐      ┌─────────┴─────────────┐
│          LLM Provider         │      │       ChromaDB         │
│  SiliconFlow / GLM-4.7 等     │      │  http://localhost:8001 │
└──────────────────────────────┘      └───────────────────────┘
```

---

## 4. 目录结构

```text
3-tool_chain_improve/
├── agent/
│   ├── main.py                    # FastAPI 后端入口
│   ├── prompts.yaml               # Agent 提示词配置
│   ├── backend/
│   │   ├── graph.py               # Agent 工作流与 RAG 触发逻辑
│   │   ├── tools.py               # 工具定义与工具实现
│   │   ├── rag.py                 # RAG 文档加载、入库、检索
│   │   ├── llm.py                 # LLM 与 embedding 调用封装
│   │   ├── state.py               # Agent 状态结构
│   │   ├── database.py            # SQLite 数据库
│   │   ├── platform_settings.py   # 平台默认工具和模型配置
│   │   └── ...
│   ├── docs/                      # 平台自身 API 和评测相关文档
│   └── frontend/
│       ├── package.json
│       ├── vite.config.js         # 前端开发服务器和代理配置
│       └── src/
├── docs/
│   ├── CD部署配置说明.md
│   └── dev_knowledge/             # 当前通用开发型 RAG 知识库资料
├── api文档/
├── tests/                         # 后端 pytest 测试
├── requirements.txt
├── .env.example
├── README.md
└── README1.md
```

---

## 5. 环境要求

推荐环境：

- Windows + PowerShell。
- Python 3.10 或更高版本。
- Node.js 18 或更高版本。
- npm。
- Docker Desktop。
- 一个可用的 OpenAI-compatible API Key。

当前推荐模型配置：

```powershell
$env:OPENAI_BASE_URL="https://api.siliconflow.cn/v1"
$env:OPENAI_MODEL="Pro/zai-org/GLM-4.7"
```

注意：真实的 `OPENAI_API_KEY` 不要写进 README、代码、提交记录或公开截图中。

---

## 6. 环境变量

后端启动前需要在同一个 PowerShell 窗口中设置环境变量。

```powershell
$env:OPENAI_API_KEY="你的真实 API Key"
$env:OPENAI_BASE_URL="https://api.siliconflow.cn/v1"
$env:OPENAI_MODEL="Pro/zai-org/GLM-4.7"

$env:CHROMA_MODE="http"
$env:CHROMA_HOST="localhost"
$env:CHROMA_PORT="8001"
```

变量说明：

| 变量 | 说明 | 推荐值 |
|---|---|---|
| `OPENAI_API_KEY` | LLM API Key | 使用自己的真实 Key |
| `OPENAI_BASE_URL` | OpenAI-compatible API 地址 | `https://api.siliconflow.cn/v1` |
| `OPENAI_MODEL` | Agent 使用的模型 | `Pro/zai-org/GLM-4.7` |
| `CHROMA_MODE` | Chroma 连接模式 | `http` |
| `CHROMA_HOST` | Chroma HTTP 主机 | `localhost` |
| `CHROMA_PORT` | Chroma HTTP 端口 | `8001` |

`.env.example` 中保留的是示例配置。实际运行时建议直接在 PowerShell 中设置，或者创建本地 `.env`，但不要提交真实密钥。

---

## 7. 端口说明

| 服务 | 地址 |
|---|---|
| 后端 FastAPI | `http://127.0.0.1:8000` |
| 前端 Vite | `http://localhost:3000` |
| ChromaDB 宿主机端口 | `http://localhost:8001` |
| ChromaDB 容器内端口 | `8000` |

注意：

- 前端 Vite 代理应该指向 FastAPI 的 `8000`。
- ChromaDB 是后端 RAG 使用的向量数据库，宿主机端口是 `8001`。
- 不要把前端 API 代理指向 ChromaDB 的 `8001`。

---

## 8. ChromaDB 与 RAG 启动

Windows 本机环境不建议直接使用 ChromaDB `PersistentClient` 做入库操作，因为可能触发底层 access violation 崩溃。当前推荐使用 Docker 中的 ChromaDB HTTP 服务。

### 8.1 启动已有 Chroma 容器

```powershell
cd D:\dasanxia\ruangong3\diedai3\3-tool_chain_improve

docker start chroma-local
```

### 8.2 如果容器不存在，创建容器

```powershell
cd D:\dasanxia\ruangong3\diedai3\3-tool_chain_improve

docker run -d `
  --name chroma-local `
  --restart unless-stopped `
  -v "${PWD}\chroma-data:/data" `
  -p 8001:8000 `
  chromadb/chroma
```

### 8.3 检查 RAG 状态

```powershell
cd D:\dasanxia\ruangong3\diedai3\3-tool_chain_improve

$env:CHROMA_MODE="http"
$env:CHROMA_HOST="localhost"
$env:CHROMA_PORT="8001"

.\.venv\Scripts\python.exe -c "from agent.backend.rag import get_rag_stats; print(get_rag_stats())"
```

正常情况下应该能看到 `status: ok`，并显示 collection、chunk 数量等信息。

---

## 9. 当前 RAG 知识库内容

当前知识库是通用开发型知识库，主要文档位于：

```text
docs/dev_knowledge/
├── coding_agent_workflow.md
├── python_fastapi_pytest_guide.md
├── frontend_vue_vite_guide.md
├── debugging_security_guide.md
└── rag_chromadb_operations.md
```

它主要覆盖：

- 开发任务执行流程。
- Python / FastAPI / pytest 规则。
- Vue / Vite 前端开发规则。
- 前后端代理和端口规则。
- 调试与安全检查。
- 硬编码密钥检查。
- ChromaDB / RAG 运维注意事项。

当前不建议长期放入通用知识库的内容：

- 本 Agent 平台自己的完整说明书。
- 临时验收口令。
- 临时测试文件。
- pytest 临时目录。
- 一次性实验数据。

如果要让 Agent 辅助某个具体项目开发，可以把该项目自己的 README、docs、任务书、接口文档、部署文档等作为“目标项目知识”单独入库。

---

## 10. RAG 接口格式

Agent 使用工具 `rag_search` 检索知识库。

请求格式示例：

```json
{
  "query": "新增 Python 函数和 pytest 测试应该遵循什么规则？",
  "top_k": 5
}
```

返回格式示例：

```json
{
  "status": "success",
  "query": "新增 Python 函数和 pytest 测试应该遵循什么规则？",
  "results": [
    {
      "content": "检索到的内容片段",
      "source": "docs/dev_knowledge/python_fastapi_pytest_guide.md",
      "score": 0.82
    }
  ]
}
```

返回结果应包含：

- `content`：检索到的文本片段。
- `source`：来源文件，方便前端展示和报告说明。
- `score`：相似度或相关性分数。

---

## 11. 启动后端

打开一个 PowerShell 窗口，执行：

```powershell
cd D:\dasanxia\ruangong3\diedai3\3-tool_chain_improve

.\.venv\Scripts\Activate.ps1

$env:OPENAI_API_KEY="你的真实 API Key"
$env:OPENAI_BASE_URL="https://api.siliconflow.cn/v1"
$env:OPENAI_MODEL="Pro/zai-org/GLM-4.7"

$env:CHROMA_MODE="http"
$env:CHROMA_HOST="localhost"
$env:CHROMA_PORT="8001"

python -m uvicorn agent.main:app --host 127.0.0.1 --port 8000 --reload
```

后端启动成功后，浏览器访问：

```text
http://127.0.0.1:8000/docs
```

如果能打开 FastAPI Swagger 页面，说明后端正常。

---

## 12. 启动前端

重新打开另一个 PowerShell 窗口，执行：

```powershell
cd D:\dasanxia\ruangong3\diedai3\3-tool_chain_improve\agent\frontend

npm install
npm run dev
```

前端启动后访问：

```text
http://localhost:3000
```

如果前端页面能打开，并能创建项目、创建会话、发送消息，说明前端基本正常。

---

## 13. 页面使用流程

1. 启动 ChromaDB。
2. 启动后端 FastAPI。
3. 启动前端 Vite。
4. 打开 `http://localhost:3000`。
5. 创建项目。
6. 创建会话。
7. 输入任务。
8. 如果出现执行计划，确认计划。
9. 查看执行轨迹。
10. 查看最终回答和文件变化。

---

## 14. 后端测试

在项目根目录执行：

```powershell
cd D:\dasanxia\ruangong3\diedai3\3-tool_chain_improve

.\.venv\Scripts\Activate.ps1

$env:OPENAI_API_KEY="你的真实 API Key"
$env:OPENAI_BASE_URL="https://api.siliconflow.cn/v1"
$env:OPENAI_MODEL="Pro/zai-org/GLM-4.7"

$env:CHROMA_MODE="http"
$env:CHROMA_HOST="localhost"
$env:CHROMA_PORT="8001"

python -m pytest tests -q --tb=short
```

如果看到 `.pytest_cache` 权限 warning，通常不影响测试结果。以 pytest 最后的 passed / failed 统计为准。

当前已验证过的后端结果：

```text
340 passed, 2 warnings
```

---

## 15. 前端测试

在前端目录执行：

```powershell
cd D:\dasanxia\ruangong3\diedai3\3-tool_chain_improve\agent\frontend

npm test
```

当前已验证过的前端结果：

```text
16 test files passed
246 tests passed
```

---

## 16. RAG 页面验收

启动 ChromaDB、后端和前端后，在页面中创建项目和会话，然后输入以下任务。

### 16.1 自然触发 RAG

输入：

```text
请根据项目知识库回答：新增 Python 函数和 pytest 测试应该遵循什么规则？
```

预期：

- 执行轨迹中出现 `rag_search`。
- 回答提到 Python 函数应保持清晰、类型标注、可测试。
- 回答提到 pytest 测试规则。
- 回答能说明内容来自知识库检索结果。

### 16.2 前端代理知识检索

输入：

```text
请根据项目知识库回答：Vite 前端代理应该指向哪个后端端口？是否应该指向 ChromaDB 的 8001？
```

预期：

- 执行轨迹中出现 `rag_search`。
- 回答说明前端代理应该指向 FastAPI 后端 `8000`。
- 回答说明不应该指向 ChromaDB 的 `8001`。

### 16.3 无答案不编造

输入：

```text
请根据项目知识库告诉我 BLUE_SATURN_9999 的具体定义。
```

预期：

- 可以调用 `rag_search`。
- 不应该编造定义。
- 应明确说明知识库中没有找到该标识的具体定义。

### 16.4 简单问题不走 RAG

输入：

```text
请直接计算 12 × 13，只返回结果。
```

预期：

- 回答 `156`。
- 执行轨迹不应该出现 `rag_search`。

### 16.5 代码任务使用 RAG 规则

输入：

```text
请根据项目知识库中的开发规则，在当前工作区创建 calc_utils.py。要求实现 add(a: int, b: int) -> int，并创建 test_calc_utils.py。完成后运行 pytest 验证。
```

预期：

- 执行轨迹中出现 `rag_search`。
- 创建 `calc_utils.py`。
- 创建 `test_calc_utils.py`。
- `add` 函数有类型标注。
- 运行 pytest。
- 最终说明测试通过，或给出失败原因。

---

## 17. 常见问题

### 17.1 页面没有响应

检查三个服务是否都在运行：

- ChromaDB：`http://localhost:8001`
- 后端：`http://127.0.0.1:8000/docs`
- 前端：`http://localhost:3000`

### 17.2 `rag_search` 连接失败

检查后端窗口中的环境变量：

```powershell
$env:OPENAI_API_KEY
$env:OPENAI_BASE_URL
$env:OPENAI_MODEL
$env:CHROMA_MODE
$env:CHROMA_HOST
$env:CHROMA_PORT
```

尤其要确认：

- `OPENAI_API_KEY` 已设置。
- `OPENAI_BASE_URL` 是 `https://api.siliconflow.cn/v1`。
- `OPENAI_MODEL` 是 `Pro/zai-org/GLM-4.7`。
- `CHROMA_PORT` 是 `8001`。

### 17.3 ChromaDB 报错

先确认 Docker 容器是否在运行：

```powershell
docker ps
```

再检查 RAG 状态：

```powershell
cd D:\dasanxia\ruangong3\diedai3\3-tool_chain_improve

$env:CHROMA_MODE="http"
$env:CHROMA_HOST="localhost"
$env:CHROMA_PORT="8001"

.\.venv\Scripts\python.exe -c "from agent.backend.rag import get_rag_stats; print(get_rag_stats())"
```

### 17.4 Vite 出现 WebSocket proxy 日志

开发环境中偶尔出现这类日志：

```text
ws proxy error: read ECONNRESET
ws proxy socket error: write ECONNABORTED
```

如果页面可以继续使用，后端没有崩溃，通常只是开发服务器 WebSocket 连接中断或刷新造成的噪声。当前前端配置已经对常见的这类日志做了抑制。

如果日志持续刷屏，或者页面无法继续执行，需要检查：

- 后端窗口是否仍在运行。
- 前端代理是否指向 `8000`。
- 浏览器页面是否频繁刷新。
- 后端是否有真实异常。

### 17.5 简单问题也触发 RAG

如果简单计算、普通闲聊也触发了 RAG，需要检查后端的 RAG 触发逻辑。当前预期是：

- 明确提到知识库、项目知识库、先检索、`rag_search` 时触发 RAG。
- 普通数学和无需上下文的问题不触发 RAG。

---

## 18. 当前验证状态

当前项目已经验证过：

- 后端 pytest 可通过。
- 前端 Vitest 可通过。
- ChromaDB HTTP 模式可用。
- `rag_search` 可正常作为 Agent 工具调用。
- RAG 返回结果包含内容、来源和相似度。
- 页面执行轨迹可以显示 RAG 工具调用。
- 知识库相关问题会主动触发 RAG。
- 简单数学问题不会触发 RAG。
- 代码任务可以结合知识库规则执行。

因此，当前 RAG 集成和前后端主流程可以视为已完成基本验收。

---

## 19. 使用建议

如果这个 Agent 要辅助别人的任意项目开发，建议这样使用 RAG：

1. 保留当前 `docs/dev_knowledge/` 作为通用开发知识库。
2. 针对具体目标项目，额外入库该项目的 README、docs、任务书、接口文档、部署文档。
3. 用户提问时明确写“根据项目知识库”或“请先调用 rag_search”。
4. Agent 回答时展示检索来源，避免凭空编造。
5. 开发任务完成后运行对应测试，并说明测试结果。
6. 发布前检查 Git 工作区、硬编码密钥、依赖配置和启动说明。

---

## 20. 注意事项

- 不要把真实 API Key 写入 README 或代码。
- 不要把临时测试口令长期放入通用 RAG 知识库。
- 不要把 ChromaDB 的 `8001` 当成 FastAPI 后端端口。
- Windows 下推荐使用 Docker ChromaDB HTTP 模式。
- 如果需要修改知识库内容，修改文档后需要重新入库。
- 如果只修改 README，不需要重启服务，也不需要重新入库。
