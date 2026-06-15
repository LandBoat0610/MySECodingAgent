# Autonomous Coding Agent Platform

一个面向代码任务的**自治执行代理平台**，集成**评测中心**和 **RAG 知识增强**，采用 **Planner → ContextBuilder → Executor → Verifier → Repair → Finalize** 工作流，提供完整的 Web 管理界面，能够针对自然语言任务自动规划步骤、调用工具、执行命令、检查结果，并在失败时自动修复代码。

---

## 1. 项目简介

Agent Platform 是一个全栈项目（Python 后端 + Vue 前端），核心能力包括：

- 📋 **项目管理**：创建/管理多个项目工作区，每个项目拥有独立的工作目录
- 💬 **会话管理**：每个项目下可创建多个对话会话，支持置顶，会话状态持久化到 SQLite
- 🤖 **自治代理**：接收自然语言任务，自动拆解步骤、调用大模型执行、验证结果、修复代码
- 🔧 **工具调用**：内置 13 种工具（bash 执行、文件读写、代码搜索、网页搜索、RAG 检索、patch 应用、测试运行等）
- 🔒 **安全沙箱**：工作区隔离，路径逃逸防护，危险命令拦截，命令审批机制
- 📊 **实时追踪**：WebSocket 实时推送执行轨迹，前端可视化展示
- ✅ **计划审批**：执行前可预览计划，支持同意/优化/跳过/停止四种操作
- 🧠 **跨对话记忆**：自动记住项目启动命令、测试命令、已知问题、用户偏好
- 📚 **RAG 知识增强**：ChromaDB 向量数据库，支持文档入库、语义检索、来源展示
- 🧪 **评测中心**：批量评测 Agent 质量，支持结果导向/过程导向两种模式
- 📈 **多维指标**：Ragas 评分、LLM-as-a-Judge、运行时指标、安全扫描、雷达图
- ⚙️ **平台设置**：运行时切换模型、启用/禁用工具、管理自定义技能
- 🌐 **Web 界面**：Vue 3 构建的现代暗色主题管理界面，含 IDE 与评测双工作区
- 🐳 **容器化部署**：Docker Compose 一键部署，GitLab CI/CD 流水线

---

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Frontend (Vue 3 + Vite)                      │
│  端口: 3000  (Vite dev server, 代理后端到 8000)                      │
│  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐  │
│  │ProjectPanel│ │FileTreePanel│ │FilePreview│ │ ChatPanel │ │ EvalHUD││
│  └──────────┘ └───────────┘ └──────────┘ └──────────┘ └─────────┘  │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │           评测中心 (EvalLayout)                                │   │
│  │  EvalTasksView | EvalMetricsView | EvalCompareView | EvalCharts│ │
│  └──────────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │           平台设置 (Agent 配置 / 工具开关 / 技能管理)          │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────────────────────────┘
                       │ HTTP REST + WebSocket
┌──────────────────────┴──────────────────────────────────────────────┐
│                      Backend (FastAPI)                              │
│  端口: 8000  API 文档: http://127.0.0.1:8000/docs                   │
│  ┌────────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────────┐    │
│  │  main.py   │ │ graph.py │ │  llm.py  │ │ evaluation_jobs.py│    │
│  │ (API + 评测│ │(Agent状态│ │(LLM调用) │ │(评测任务调度执行)  │    │
│  │  + RAG路由)│ │  机)     │ └──────────┘ └───────────────────┘    │
│  └────────────┘ └──────────┘                                        │
│  ┌────────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐     │
│  │database.py │ │ tools.py │ │  rag.py  │ │session_manager.py│     │
│  │ (SQLite)   │ │(13种工具)│ │(ChromaDB)│ │(跨对话记忆)      │     │
│  └────────────┘ └──────────┘ └──────────┘ └──────────────────┘     │
│  ┌────────────────┐ ┌──────────────┐ ┌────────────────────┐        │
│  │ eval_quality.py│ │eval_security │ │ runtime_metrics.py │        │
│  │ (Ragas+LLMJudge│ │ (安全扫描)   │ │ (Token/工具统计)   │        │
│  └────────────────┘ └──────────────┘ └────────────────────┘        │
└───────────────┬───────────────────────────────┬──────────────────────┘
                │                               │
                │ OpenAI-compatible API         │ Chroma HTTP
                │                               │
┌───────────────┴──────────────┐      ┌─────────┴─────────────────────┐
│         LLM Provider          │      │          ChromaDB              │
│  SiliconFlow / 任意兼容 API   │      │  http://localhost:8001         │
│  默认模型: GLM-4.7            │      │  (Docker 容器, 向量数据库)     │
└──────────────────────────────┘      └───────────────────────────────┘
```

---

## 3. 核心特性

### 3.1 自治任务执行 (Planner → ContextBuilder → Executor → Verifier → Repair → Finalize)

1. **Planner（规划）**：LLM 评估任务难度（easy/medium/hard），拆解为具体步骤，生成结构化执行计划，等待用户确认
2. **ContextBuilder（上下文构建）**：收集工作区文件、相关代码、跨对话记忆、用户偏好，构建完整执行上下文
3. **Executor（执行）**：按步骤调用 LLM function calling 选择工具并执行。支持工具调用轮次上限自动申请续延。每步最多迭代 5~10 轮（根据难度）
4. **Verifier（验证）**：检查执行结果，识别错误信号（traceback、exit code、error_type 等）
5. **Repair（修复）**：根据错误信息生成修正代码并写回文件，最多自动修复 2 轮
6. **Finalize（总结）**：输出最终总结，自动保存会话摘要和项目记忆

### 3.2 跨对话记忆与上下文工程

Agent 拥有跨对话记忆能力，每次任务初始化时会收到：

- **session_summary**：当前会话前几轮的摘要
- **project_memory**：此项目的历史关键信息（启动命令、测试命令、已知问题、项目约定），按类别分组
- **user_preferences**：用户的偏好设置（如是否需要命令确认、代码风格偏好等）
- **relevant_history**：与此任务相关的历史对话记录（关键词匹配检索）
- **context_budget**：当前可用的上下文 token 上限

执行完成后，Agent 自动提取和保存项目级关键信息，供后续会话复用。

### 3.3 内置工具能力

Agent 后端提供 13 种工具，可在平台设置中独立启用/禁用：

| 工具              | 功能     | 说明                                                           |
| ----------------- | -------- | -------------------------------------------------------------- |
| `read_file`       | 读取文件 | 读取工作区内文件全文                                           |
| `read_file_range` | 分段读取 | 指定行范围读取大文件                                           |
| `write_file`      | 写入文件 | 向工作区写入文件，自动创建父目录                               |
| `list_files`      | 列出目录 | 查看工作区目录结构，支持递归                                   |
| `execute_bash`    | 执行命令 | 在隔离工作区中执行 cmd 命令，20s 超时，危险命令拦截 + 用户确认 |
| `search_code`     | 搜索代码 | 正则搜索代码内容，支持大小写                                   |
| `web_search`      | 网页搜索 | DuckDuckGo → Bing 多引擎降级搜索                               |
| `fetch_url`       | 抓取网页 | 抓取 URL 并提取纯文本内容                                      |
| `apply_patch`     | 应用补丁 | 将 unified diff patch 应用到目标文件（精确修改）               |
| `get_git_diff`    | Git 差异 | 获取工作区 git diff                                            |
| `run_tests`       | 运行测试 | 执行 pytest 并返回结果摘要                                     |
| `run_lint`        | 代码检查 | 运行 flake8 代码风格检查                                       |
| `rag_search`      | RAG 检索 | 在 ChromaDB 知识库中语义检索文档片段                           |

### 3.4 RAG 知识增强

RAG（Retrieval-Augmented Generation）用来解决以下问题：

- 用户问的是项目知识库、开发规则、测试规则、调试规则
- 用户要求"先检索知识库再回答"
- Agent 执行任务时需要引用已有文档，而不是凭空回答

技术实现：

- **向量数据库**：ChromaDB（Docker HTTP 模式）
- **Embedding 模型**：通过 OpenAI 兼容 API 调用（默认 `BAAI/bge-large-zh-v1.5`）
- **文档格式**：支持 Markdown、纯文本、PDF
- **检索结果**：返回内容片段、来源路径、相似度分数

简单数学、闲聊、无需知识库的普通问题，不应该触发 RAG。

### 3.5 安全机制

- **工作区隔离**：所有文件操作限制在项目专属的工作区目录内
- **路径逃逸防护**：`resolve_workspace_path` 阻止 `../` 等路径逃逸
- **危险命令拦截**：正则匹配拦截 `rm -rf /`、`shutdown`、`mkfs`、`dd if=` 等危险操作
- **命令审批**：`execute_bash` 执行前弹出确认对话框，支持批准/拒绝/要求修改
- **超时控制**：bash 命令 20 秒超时，LLM 调用有超时限制

### 3.6 实时追踪

- 执行轨迹（trace）通过 WebSocket 实时推送到前端
- 每次执行后状态自动持久化到 SQLite
- 输出 `agent_trace.json` 和 `agent_trace.mmd`（Mermaid 状态图）
- 实时 HUD 面板显示 Token 消耗、工具调用统计、耗时等信息

### 3.7 LangGraph 支持与降级

- 若安装了 `langgraph`，使用图状态机执行
- 否则自动回退为 `run_manual_fallback` 手写状态机

---

## 4. 项目结构

```
3/
├── agent/                              # 后端核心代码
│   ├── main.py                         # FastAPI 应用入口，所有 API 路由（含评测/RAG/记忆路由）
│   ├── prompts.yaml                    # LLM 提示词配置（系统角色、约束、各阶段模板）
│   ├── conftest.py                     # 测试环境配置
│   ├── __init__.py
│   ├── docs/                           # 平台文档
│   │   ├── api接口文档.md
│   │   ├── 评测中心使用说明.md
│   │   ├── 评测端到端跑通示例.md
│   │   └── 一些评估样例.md
│   ├── evaluation-platform/            # 评测前端独立页面（预留）
│   └── backend/
│       ├── config.py                   # 全局常量配置（模型、路径、安全规则、RAG 参数等）
│       ├── database.py                 # SQLite 数据库初始化、迁移与连接管理
│       ├── graph.py                    # 核心状态机：Planner/ContextBuilder/Executor/Verifier/Repair/Finalize
│       ├── llm.py                      # LLM 调用封装（OpenAI 兼容 API）
│       ├── schemas.py                  # Pydantic 数据模型（请求/响应，含评测模型）
│       ├── state.py                    # AgentState TypedDict 定义（50+ 字段）
│       ├── tools.py                    # 工具定义与实现（13 种工具）
│       ├── utils.py                    # 工具函数（路径解析、提示词加载、日志、JSON 解析等）
│       ├── rag.py                      # RAG 模块（文档加载、切分、向量化、入库、检索）
│       ├── session_manager.py          # 跨对话记忆与上下文工程（会话摘要、项目记忆、用户偏好、历史检索）
│       ├── platform_settings.py        # 平台级设置（Agent 模型/版本/工具开关/技能管理）
│       ├── runtime_metrics.py          # Token/工具调用统计与归一化
│       ├── eval_router.py              # 评测中心 HTTP 路由（/eval/*）
│       ├── eval_dataset.py             # 评测数据集解析与规范化
│       ├── eval_scoring.py             # 评测评分判定（结果导向/过程导向）
│       ├── eval_quality.py             # Ragas 指标 + LLM-as-a-Judge 评分
│       ├── eval_security.py            # 启发式安全扫描（20+ 危险模式规则）
│       ├── eval_storage.py             # 评测数据存储目录配置
│       └── evaluation_jobs.py          # 评测任务 CRUD 与后台 Worker 调度
├── agent/frontend/                     # Vue 3 前端
│   ├── index.html                      # 入口 HTML
│   ├── package.json                    # 前端依赖与脚本
│   ├── vite.config.js                  # Vite 配置（含代理到后端 8000）
│   ├── vitest.config.js                # Vitest 测试配置
│   ├── Dockerfile.frontend             # 前端多阶段 Docker 构建（npm build → nginx 托管）
│   ├── nginx.conf                      # nginx 配置（Vue Router history 模式 + API 反向代理）
│   └── src/
│       ├── App.vue                     # 根组件
│       ├── main.js                     # Vue 应用入口
│       ├── api/index.js                # 后端 API 封装（含评测 API）
│       ├── router/index.js             # 路由配置（IDE + 评测中心）
│       ├── stores/
│       │   ├── agent.js                # Pinia Agent 状态管理
│       │   ├── agentConfig.js          # Pinia Agent 配置管理
│       │   └── evaluation.js           # Pinia 评测中心状态管理
│       ├── composables/
│       │   ├── useConfirm.js           # 确认对话框组合式函数
│       │   └── useExpandedDirs.js      # 目录展开状态管理
│       ├── utils/
│       │   ├── highlight.js            # 代码高亮
│       │   └── persistence.js          # 本地持久化（localStorage）
│       ├── layouts/
│       │   ├── MainShell.vue           # 主布局外壳（IDE/评测切换）
│       │   ├── IdeLayout.vue           # IDE 三栏布局
│       │   └── EvalLayout.vue          # 评测中心布局
│       ├── components/
│       │   ├── ProjectPanel.vue        # 项目/会话列表管理
│       │   ├── FileTreePanel.vue       # 文件树面板
│       │   ├── FileTreeNode.vue        # 文件树节点组件
│       │   ├── FilePreview.vue         # 文件预览面板
│       │   ├── ChatPanel.vue           # 对话面板（消息 + 执行轨迹）
│       │   ├── PlanDialog.vue          # 计划确认对话框
│       │   ├── CommandApprovalDialog.vue   # 命令审批对话框
│       │   ├── ContinueApprovalDialog.vue  # 执行续延审批对话框
│       │   ├── ConfirmDialog.vue       # 通用确认对话框
│       │   ├── ToolResultCard.vue      # 工具结果卡片
│       │   ├── RagSources.vue          # RAG 来源展示
│       │   ├── DiffViewer.vue          # 差异对比器
│       │   ├── WorkspaceSwitcher.vue   # 工作区切换器
│       │   ├── LiveEvalHud.vue         # 实时评测指标 HUD 面板
│       │   └── status/                 # 状态组件
│       │       ├── EmptyState.vue
│       │       ├── ErrorBanner.vue
│       │       └── LoadingSpinner.vue
│       ├── views/evaluation/
│       │   ├── EvalTasksView.vue       # 评测任务管理视图
│       │   ├── EvalMetricsView.vue     # 评测指标看板视图
│       │   ├── EvalCompareView.vue     # 评测对比分析视图
│       │   ├── EvalChartsView.vue      # 评测图表可视化视图
│       │   └── EvalResultDetail.vue    # 评测结果明细视图
│       └── __tests__/                  # 前端单元测试（Vitest）
│           ├── setup.js
│           ├── api/index.test.js
│           ├── components/             # 组件测试（12 个）
│           ├── composables/            # 组合式函数测试
│           ├── layouts/                # 布局测试
│           ├── router/                 # 路由测试
│           ├── stores/                 # Store 测试
│           ├── utils/                  # 工具函数测试
│           └── views/evaluation/       # 评测视图测试
├── tests/                              # 后端单元测试（pytest, 19 个文件）
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_database.py
│   ├── test_eval_dataset.py
│   ├── test_eval_quality.py
│   ├── test_eval_scoring.py
│   ├── test_eval_security.py
│   ├── test_eval_storage.py
│   ├── test_evaluation_jobs.py
│   ├── test_graph.py
│   ├── test_llm.py
│   ├── test_main.py
│   ├── test_platform_settings.py
│   ├── test_rag.py
│   ├── test_runtime_metrics.py
│   ├── test_schemas.py
│   ├── test_session_manager.py
│   ├── test_state.py
│   ├── test_tools.py
│   └── test_utils.py
├── docs/                               # 文档目录
│   ├── CD部署配置说明.md
│   └── dev_knowledge/                  # RAG 通用开发知识库
│       ├── coding_agent_workflow.md
│       ├── python_fastapi_pytest_guide.md
│       ├── frontend_vue_vite_guide.md
│       ├── debugging_security_guide.md
│       └── rag_chromadb_operations.md
├── api文档/                            # API 文档
│   └── api文档.md
├── toolchain_eval/                     # 工具链评测脚本
│   ├── run_eval.py
│   └── toolchain_baseline.json
├── workspaces/                         # 项目工作区目录（运行时自动创建）
├── requirements.txt                    # Python 依赖
├── Dockerfile                          # 后端生产部署镜像
├── ci.Dockerfile                       # CI 专用镜像（预装全部依赖 + 测试工具）
├── docker-compose.yml                  # 前后端本地联调编排
├── .gitlab-ci.yml                      # GitLab CI/CD 流水线配置（lint→security→test→report→build→deploy）
├── .env.example                        # 环境变量示例
├── .gitignore
├── .dockerignore
├── conftest.py                         # pytest 全局配置
├── agent_platform.db                   # SQLite 数据库（运行时生成）
├── agent_memory.md                     # Agent 记忆文件
└── README.md                           # 本文件
```

---

## 5. API 接口概览

### 5.1 Agent IDE 接口

| 方法   | 路径                                                   | 说明                                     |
| ------ | ------------------------------------------------------ | ---------------------------------------- |
| GET    | `/health`                                              | 健康检查端点                             |
| GET    | `/projects`                                            | 获取所有项目列表                         |
| POST   | `/projects`                                            | 创建/打开项目                            |
| DELETE | `/projects/{pid}`                                      | 删除项目（级联删除会话和计划）           |
| GET    | `/projects/{pid}/sessions`                             | 获取项目下会话列表                       |
| POST   | `/projects/{pid}/sessions`                             | 创建新会话（可选自动生成标题）           |
| PATCH  | `/projects/{pid}/sessions/{sid}`                       | 更新会话（标题/置顶）                    |
| DELETE | `/projects/{pid}/sessions/{sid}`                       | 删除会话                                 |
| POST   | `/projects/{pid}/sessions/{sid}/clear`                 | 清空会话状态                             |
| GET    | `/projects/{pid}/sessions/{sid}/state`                 | 获取会话状态快照                         |
| POST   | `/projects/{pid}/sessions/{sid}/chat`                  | 发送任务消息                             |
| WS     | `/projects/{pid}/sessions/{sid}/chat/stream`           | WebSocket 流式执行追踪                   |
| POST   | `/projects/{pid}/sessions/{sid}/stop`                  | 停止会话执行                             |
| GET    | `/projects/{pid}/sessions/{sid}/plan`                  | 获取执行计划树                           |
| GET    | `/projects/{pid}/sessions/{sid}/rounds`                | 获取对话轮次列表（带分页）               |
| POST   | `/projects/{pid}/sessions/{sid}/plan/{plan_id}/action` | 对计划执行操作（agree/refine/skip/stop） |
| POST   | `/projects/{pid}/sessions/{sid}/command-approval`      | 命令审批（approve/reject/revise）        |
| POST   | `/projects/{pid}/sessions/{sid}/continue-approval`     | 执行续延审批（continue/stop）            |
| GET    | `/projects/{pid}/files`                                | 获取项目文件树                           |
| GET    | `/projects/{pid}/files/content`                        | 获取文件内容                             |

### 5.2 平台设置接口

| 方法   | 路径                          | 说明                             |
| ------ | ----------------------------- | -------------------------------- |
| GET    | `/settings/agent-config`      | 获取 Agent 配置（模型/版本标签） |
| PUT    | `/settings/agent-config`      | 更新 Agent 配置                  |
| GET    | `/settings/tools`             | 获取工具开关列表                 |
| PUT    | `/settings/tools`             | 更新工具开关                     |
| GET    | `/settings/skills`            | 获取技能列表                     |
| POST   | `/settings/skills`            | 创建技能                         |
| PATCH  | `/settings/skills/{skill_id}` | 更新技能                         |
| DELETE | `/settings/skills/{skill_id}` | 删除技能                         |

### 5.3 RAG 接口

| 方法 | 路径                            | 说明                         |
| ---- | ------------------------------- | ---------------------------- |
| POST | `/rag/ingest?project_id=...`    | 将项目工作区文档入库到知识库 |
| GET  | `/rag/search?query=...&top_k=5` | 直接搜索知识库（调试用）     |
| GET  | `/rag/stats`                    | 获取知识库统计信息           |

#### 5.3.1 新增 RAG 知识文件

当前版本没有单独的“上传 RAG 文件”按钮或上传接口。用户可以先把知识文件放入项目工作区中会被自动扫描的位置，然后调用入库接口重新写入知识库。

自动入库会扫描以下文件：

- 项目工作区根目录下的 `README.md`
- 项目工作区 `docs/` 目录下的 `.md`、`.txt`、`.markdown` 文件
- 项目工作区 `agent/docs/` 目录下的 `.md`、`.txt`、`.markdown` 文件
- 项目工作区根目录下的 `.pdf` 文件

操作步骤：

1. 将新增文档放到上述目录，例如 `docs/my_knowledge.md` 或 `agent/docs/usage.md`。
2. 确保 ChromaDB 已启动，后端服务正在运行。
3. 调用入库接口：

```powershell
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/rag/ingest?project_id=你的项目ID"
```

4. 查看知识库统计：

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/rag/stats"
```

5. 可选：直接搜索验证是否入库成功：

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/rag/search?query=你的问题&top_k=5"
```

同一路径的文档重复入库时会使用 `upsert` 覆盖对应分块，避免每次重新入库都产生重复记录。

### 5.4 跨对话记忆接口

| 方法 | 路径                                        | 说明                 |
| ---- | ------------------------------------------- | -------------------- |
| GET  | `/projects/{pid}/memory/context`            | 获取完整记忆上下文   |
| GET  | `/projects/{pid}/memory`                    | 列出项目所有记忆条目 |
| POST | `/projects/{pid}/memory`                    | 保存一条项目记忆     |
| GET  | `/projects/{pid}/history?query=...&limit=5` | 检索项目历史对话     |
| GET  | `/preferences`                              | 获取用户偏好列表     |
| POST | `/preferences`                              | 保存一条用户偏好     |

### 5.5 评测中心接口 (`/eval/*`)

| 方法   | 路径                         | 说明                            |
| ------ | ---------------------------- | ------------------------------- |
| POST   | `/eval/datasets/upload`      | 上传 JSON 文件创建数据集        |
| POST   | `/eval/datasets`             | JSON Body 创建数据集            |
| GET    | `/eval/datasets`             | 获取所有数据集列表              |
| GET    | `/eval/datasets/{id}`        | 获取单个数据集信息              |
| DELETE | `/eval/datasets/{id}`        | 删除数据集（支持 cascade 级联） |
| POST   | `/eval/tasks`                | 创建评测任务                    |
| GET    | `/eval/tasks`                | 获取评测任务列表                |
| GET    | `/eval/tasks/{id}`           | 获取单个评测任务                |
| PATCH  | `/eval/tasks/{id}`           | 修改评测任务配置                |
| DELETE | `/eval/tasks/{id}`           | 删除评测任务                    |
| POST   | `/eval/tasks/{id}/start`     | 启动评测任务                    |
| POST   | `/eval/tasks/{id}/cancel`    | 取消评测任务                    |
| GET    | `/eval/tasks/{id}/results`   | 获取评测结果列表                |
| GET    | `/eval/tasks/{id}/analytics` | 获取任务汇总分析（雷达图等）    |

---

## 6. 环境变量

### 6.1 必填

| 变量              | 说明                 | 默认值                      |
| ----------------- | -------------------- | --------------------------- |
| `OPENAI_API_KEY`  | OpenAI 兼容 API 密钥 | **必需**                    |
| `OPENAI_BASE_URL` | OpenAI 兼容 API 地址 | `https://api.openai.com/v1` |
| `OPENAI_MODEL`    | Agent 使用的模型     | `gpt-4o-mini`               |

### 6.2 ChromaDB / RAG

| 变量                  | 说明                                      | 默认值                   |
| --------------------- | ----------------------------------------- | ------------------------ |
| `CHROMA_MODE`         | Chroma 连接模式（http/persistent/memory） | `http`                   |
| `CHROMA_HOST`         | Chroma HTTP 主机                          | `localhost`              |
| `CHROMA_PORT`         | Chroma HTTP 端口                          | `8001`                   |
| `RAG_DEFAULT_TOP_K`   | RAG 默认检索数量                          | `5`                      |
| `RAG_CHUNK_SIZE`      | RAG 文档分块大小                          | `500`                    |
| `RAG_CHUNK_OVERLAP`   | RAG 分块重叠大小                          | `50`                     |
| `RAG_EMBEDDING_MODEL` | RAG Embedding 模型                        | `BAAI/bge-large-zh-v1.5` |

### 6.3 可选配置

| 变量                         | 说明                  | 默认值              |
| ---------------------------- | --------------------- | ------------------- |
| `SKIP_BASH_APPROVAL`         | 设为 `1` 跳过命令审批 | `false`             |
| `CONTEXT_BUDGET`             | 上下文 token 预算     | `12000`             |
| `MEMORY_MAX_ENTRIES`         | 项目记忆最大条目数    | `20`                |
| `HISTORY_RETRIEVAL_LIMIT`    | 历史检索返回条数      | `5`                 |
| `SESSION_SUMMARY_MAX_LENGTH` | 会话摘要最大字符数    | `500`               |
| `AGENT_DB_PATH`              | SQLite 数据库路径     | `agent_platform.db` |

当前默认模型配置（通过 SiliconFlow）：

```powershell
$env:OPENAI_BASE_URL="https://api.siliconflow.cn/v1"
$env:OPENAI_MODEL="Pro/zai-org/GLM-4.7"
```

> **注意**：真实的 `OPENAI_API_KEY` 不要写进 README、代码、提交记录或公开截图中。

`.env.example` 中保留的是 LLM 示例配置。实际运行时建议直接在 PowerShell 中设置，或者创建本地 `.env` 文件。

---

## 7. 启动方式

### 7.1 环境要求

- Windows（推荐 PowerShell）
- Python 3.10+
- Node.js 18+
- npm
- Docker Desktop（用于 ChromaDB RAG 和 CI/CD 部署）

### 7.2 启动 ChromaDB（RAG 依赖）

Windows 本机推荐使用 Docker 中的 ChromaDB HTTP 服务。

**启动已有容器：**

```powershell
docker start chroma-local
```

**如果容器不存在，创建容器：**

```powershell
docker run -d `
  --name chroma-local `
  --restart unless-stopped `
  -v "${PWD}\chroma-data:/data" `
  -p 8001:8000 `
  chromadb/chroma
```

**检查 RAG 状态：**

```powershell
$env:CHROMA_MODE="http"
$env:CHROMA_HOST="localhost"
$env:CHROMA_PORT="8001"

python -c "from agent.backend.rag import get_rag_stats; print(get_rag_stats())"
```

正常情况下应该能看到 `status: ok`，并显示 collection、chunk 数量等信息。

### 7.3 后端启动

```powershell
# 1. 进入项目目录
cd 3

# 2. 创建并激活虚拟环境
python -m venv venv
venv\Scripts\activate

# 3. 安装 Python 依赖
pip install -r requirements.txt

# 4. 设置环境变量（PowerShell）
$env:OPENAI_API_KEY="your-api-key-here"
$env:OPENAI_BASE_URL="https://api.siliconflow.cn/v1"
$env:OPENAI_MODEL="Pro/zai-org/GLM-4.7"
$env:CHROMA_MODE="http"
$env:CHROMA_HOST="localhost"
$env:CHROMA_PORT="8001"

# 5. 启动后端服务
python -m uvicorn agent.main:app --host 127.0.0.1 --port 8000 --reload
```

后端启动后访问 http://127.0.0.1:8000/docs 查看 Swagger API 文档。

### 7.4 前端启动

```powershell
# 打开新终端，进入前端目录
cd agent/frontend

# 安装 npm 依赖
npm install

# 启动前端开发服务器
npm run dev
```

前端启动后访问 http://localhost:3000。

> **说明**：Vite dev server 已配置代理，`/projects`、`/eval`、`/settings`、`/rag`、`/preferences` 等请求会自动转发到 `http://127.0.0.1:8000`。

### 7.5 使用 Docker Compose 启动（前后端一键部署）

```powershell
# 配置环境变量（创建 .env 文件）
# 或直接在 PowerShell 中设置
$env:OPENAI_API_KEY="your-key-here"
$env:OPENAI_BASE_URL="https://api.siliconflow.cn/v1"

# 启动
docker-compose up

# 访问
# 前端: http://localhost:3000
# 后端 API 文档: http://localhost:8000/docs
```

> **注意**：Docker Compose 部署不包含 ChromaDB 容器，RAG 功能需单独启动 ChromaDB（参见 7.2 节）。

### 7.6 完整使用流程

1. 启动 ChromaDB（如需 RAG 功能）
2. 启动后端 FastAPI
3. 启动前端 Vite
4. 打开浏览器访问 `http://localhost:3000`
5. 在左侧面板点击 `+` 创建一个**项目**（可选指定工作区路径）
6. 选中项目后，点击 `+` 创建一个**会话**
7. 在右侧 ChatPanel 输入框中描述你的任务（例如"帮我写一个 Python 快速排序程序"）
8. 点击 **Send** 发送任务
9. 在弹出对话框中查看 Agent 生成的执行计划，选择：
   - ✅ **Agree**：同意计划并开始执行
   - 🔄 **Refine**：让 Agent 重新生成计划
   - ⏭ **Skip**：跳过当前计划
   - ⏹ **Stop**：停止执行
10. 执行过程中可在右侧面板实时查看 WebSocket 推送的执行轨迹
11. 如果出现命令审批，确认 / 拒绝 / 要求修改
12. 如果到达工具调用上限，确认继续或停止
13. 查看最终回答和文件变化

---

## 8. 运行测试

### 8.1 后端测试

```powershell
# 进入项目目录
cd 3

# 激活虚拟环境
venv\Scripts\activate

# 设置环境变量
$env:OPENAI_API_KEY="your-api-key-here"
$env:OPENAI_BASE_URL="https://api.siliconflow.cn/v1"
$env:OPENAI_MODEL="Pro/zai-org/GLM-4.7"
$env:CHROMA_MODE="http"
$env:CHROMA_HOST="localhost"
$env:CHROMA_PORT="8001"

# 运行所有后端测试
python -m pytest tests -q --tb=short

# 带覆盖率报告
python -m pytest tests -q --tb=short --cov=agent/ --cov-report=term-missing

# 运行特定测试文件
python -m pytest tests/test_tools.py -v
python -m pytest tests/test_eval_scoring.py -v
```

当前已验证结果：**340+ passed, 2 warnings**。

### 8.2 前端测试

```powershell
cd agent/frontend

# 运行所有前端单元测试
npm test

# 监听模式
npm run test:watch

# 带覆盖率报告
npm run test:coverage
```

当前已验证结果：**16 test files passed, 246 tests passed**。

### 8.3 测试文件清单

**后端测试 (tests/):**

| 测试文件                    | 覆盖模块                                                   |
| --------------------------- | ---------------------------------------------------------- |
| `test_config.py`            | config.py（常量、get_effective_model、eval_model_context） |
| `test_database.py`          | database.py（表创建、外键、事务、评测表、迁移）            |
| `test_eval_dataset.py`      | eval_dataset.py（数据规范化、解析、校验）                  |
| `test_eval_quality.py`      | eval_quality.py（Ragas 指标、LLM-as-a-Judge）              |
| `test_eval_scoring.py`      | eval_scoring.py（结果/过程评分、prompt 构建）              |
| `test_eval_security.py`     | eval_security.py（20+ 危险模式扫描、安全评估）             |
| `test_eval_storage.py`      | eval_storage.py（存储目录配置）                            |
| `test_evaluation_jobs.py`   | evaluation_jobs.py（任务 CRUD、Worker 调度）               |
| `test_graph.py`             | graph.py（状态机各节点、路由、图构建）                     |
| `test_llm.py`               | llm.py（提示词构建、计划生成、目标推断）                   |
| `test_main.py`              | main.py（全部 REST API + WebSocket + 评测路由）            |
| `test_platform_settings.py` | platform_settings.py（配置读写合并、技能管理）             |
| `test_rag.py`               | rag.py（文档加载、切分、入库、检索、统计）                 |
| `test_runtime_metrics.py`   | runtime_metrics.py（Token 统计、工具调用、归一化）         |
| `test_schemas.py`           | schemas.py（Pydantic 模型校验、评测模型）                  |
| `test_session_manager.py`   | session_manager.py（记忆上下文、摘要、偏好、历史检索）     |
| `test_state.py`             | state.py（AgentState TypedDict 定义）                      |
| `test_tools.py`             | tools.py（13 种工具实现）                                  |
| `test_utils.py`             | utils.py（JSON 解析、路径安全、日志等）                    |

**前端测试 (agent/frontend/src/__tests__/):**

| 测试文件                                    | 覆盖模块                           |
| ------------------------------------------- | ---------------------------------- |
| `api/index.test.js`                         | API 请求函数（项目、会话、评测）   |
| `components/App.test.js`                    | App.vue 根组件                     |
| `components/ChatPanel.test.js`              | ChatPanel.vue 聊天面板             |
| `components/ConfirmDialog.test.js`          | ConfirmDialog.vue 确认对话框       |
| `components/DiffViewer.test.js`             | DiffViewer.vue 差异对比器          |
| `components/FilePreview.test.js`            | FilePreview.vue 文件预览           |
| `components/FileTreeNode.test.js`           | FileTreeNode.vue 文件树节点        |
| `components/FileTreePanel.test.js`          | FileTreePanel.vue 文件树面板       |
| `components/LiveEvalHud.test.js`            | LiveEvalHud.vue 实时评测面板       |
| `components/PlanDialog.test.js`             | PlanDialog.vue 计划对话框          |
| `components/ProjectPanel.test.js`           | ProjectPanel.vue 项目管理面板      |
| `components/RagSources.test.js`             | RagSources.vue RAG 来源展示        |
| `components/ToolResultCard.test.js`         | ToolResultCard.vue 工具结果卡片    |
| `components/WorkspaceSwitcher.test.js`      | WorkspaceSwitcher.vue 工作区切换器 |
| `composables/useExpandedDirs.test.js`       | useExpandedDirs.js 目录展开状态    |
| `layouts/IdeLayout.test.js`                 | IdeLayout.vue IDE 布局             |
| `layouts/EvalLayout.test.js`                | EvalLayout.vue 评测中心布局        |
| `layouts/MainShell.test.js`                 | MainShell.vue 主布局壳             |
| `router/index.test.js`                      | router/index.js 路由配置           |
| `stores/agent.test.js`                      | agent.js Agent Store               |
| `stores/agentConfig.test.js`                | agentConfig.js Agent 配置 Store    |
| `stores/evaluation.test.js`                 | evaluation.js 评测 Store           |
| `utils/highlight.test.js`                   | highlight.js 代码高亮              |
| `utils/persistence.test.js`                 | persistence.js 本地持久化          |
| `views/evaluation/EvalResultDetail.test.js` | EvalResultDetail.vue 结果明细      |
| `views/evaluation/EvalTasksView.test.js`    | EvalTasksView.vue 任务视图         |

---

## 9. 配置说明

### 9.1 修改 LLM 提示词

编辑 `agent/prompts.yaml` 可自定义系统角色、编程原则、约束条件、各阶段提示词模板（Planner/Executor/Verifier/Finalize）以及跨对话记忆使用规则。

### 9.2 调整 Agent 行为

编辑 `agent/backend/config.py` 可调整：

| 配置项                          | 说明                     | 默认值                     |
| ------------------------------- | ------------------------ | -------------------------- |
| `MAX_STEP_ITERATIONS`           | 每个步骤最大工具调用轮次 | 5                          |
| `STEP_ITERATIONS_BY_DIFFICULTY` | 按难度分级的轮次上限     | easy=4, medium=7, hard=10  |
| `MAX_REFLECTIONS`               | 最大自我修复次数         | 2                          |
| `MAX_TOOL_OUTPUT`               | 工具输出最大字符数       | 4000                       |
| `BLOCKED_BASH_PATTERNS`         | 危险命令拦截正则列表     | 预置 7 条规则              |
| `BASH_APPROVAL_REQUIRED`        | 是否需要命令审批         | true（可通过环境变量关闭） |
| `CONTEXT_BUDGET`                | 上下文预算（tokens）     | 12000                      |
| `MEMORY_MAX_ENTRIES`            | 项目记忆最大条目数       | 20                         |

### 9.3 平台设置（Web 界面）

通过 Web 界面或 API 可动态调整：

- **模型选择**：`GET/PUT /settings/agent-config`，运行时切换 LLM 模型
- **版本标签**：记录当前使用的 Agent 版本标识，评测任务会自动快照
- **工具开关**：`GET/PUT /settings/tools`，独立启用/禁用每个 Agent 工具
- **技能管理**：`GET/POST/PATCH/DELETE /settings/skills`，创建和编辑自定义技能提示词

### 9.4 评测数据集格式

```json
{
  "name": "示例数据集",
  "items": [
    {
      "id": "1",
      "description": "写一个 Python 快速排序函数",
      "expected_output": "def quicksort",
      "test_cases": [
        {"input": "[3,1,2]", "expected": "[1,2,3]"},
        {"input": "[]", "expected": "[]"}
      ]
    }
  ]
}
```

- `description`：任务描述（必填）
- `expected_output`：预期输出关键词（可选，用于结果匹配）
- `test_cases`：测试用例数组（可选，每个包含 input/expected）
- 评测方法：`result`（面向结果对比）或 `process`（面向过程，检查错误和轨迹步数）

---

## 10. RAG 页面验收

启动 ChromaDB、后端和前端后，在页面中创建项目和会话，然后输入以下任务验证 RAG 功能。

### 10.1 自然触发 RAG

输入：

```text
请根据项目知识库回答：新增 Python 函数和 pytest 测试应该遵循什么规则？
```

预期：

- 执行轨迹中出现 `rag_search`
- 回答提到 Python 函数应保持清晰、类型标注、可测试
- 回答提到 pytest 测试规则
- 回答能说明内容来自知识库检索结果

### 10.2 简单问题不走 RAG

输入：

```text
请直接计算 12 × 13，只返回结果。
```

预期：回答 `156`，执行轨迹不应该出现 `rag_search`。

### 10.3 无答案不编造

输入：

```text
请根据项目知识库告诉我 BLUE_SATURN_9999 的具体定义。
```

预期：可以调用 `rag_search`，但不应该编造定义，应明确说明知识库中没有找到。

---

## 11. CI/CD 流水线

本项目使用 GitLab CI/CD，配置见 `.gitlab-ci.yml`，共 6 个阶段：

```
lint → security → test → report → build → deploy
```

| 阶段     | Job                                                | 说明                                      |
| -------- | -------------------------------------------------- | ----------------------------------------- |
| lint     | `flake8_lint`                                      | Python 代码风格检查                       |
| security | `bandit_scan`                                      | 安全漏洞扫描                              |
| test     | `pytest_backend / tools / llm / graph_main / eval` | 后端分组并行测试 + 覆盖率                 |
| test     | `vitest_frontend`                                  | 前端单元测试                              |
| report   | `coverage_merge`                                   | 合并覆盖率报告                            |
| build    | `build_docker`                                     | 构建前后端 Docker 镜像（仅 master 分支）  |
| deploy   | `deploy_local`                                     | Docker Compose 本地部署（仅 master 分支） |

### Runner 要求

- **Executor**：`docker`（Linux 容器模式）
- **宿主机配置**：挂载 `/var/run/docker.sock` + `privileged = true`
- 移除失效的 Docker Hub 镜像源
- 详见 [docs/CD部署配置说明.md](docs/CD部署配置说明.md)

---

## 12. 端口说明

| 服务           | 地址                         | 说明                     |
| -------------- | ---------------------------- | ------------------------ |
| 后端 FastAPI   | `http://127.0.0.1:8000`      | REST API + WebSocket     |
| 后端 API 文档  | `http://127.0.0.1:8000/docs` | Swagger UI               |
| 前端 Vite 开发 | `http://localhost:3000`      | 热重载开发服务器         |
| 前端生产部署   | `http://localhost:3000:80`   | nginx 静态托管           |
| ChromaDB       | `http://localhost:8001`      | 向量数据库（宿主机端口） |

> **注意**：前端 Vite 代理指向 FastAPI 的 `8000`，不要把前端代理指向 ChromaDB 的 `8001`。

---

## 13. 常见问题

### 13.1 页面没有响应

检查三个服务是否都在运行：

- ChromaDB：`docker ps` 确认容器状态
- 后端：访问 `http://127.0.0.1:8000/docs`
- 前端：访问 `http://localhost:3000`

### 13.2 `rag_search` 连接失败

检查环境变量：

```powershell
$env:CHROMA_MODE    # 应为 "http"
$env:CHROMA_HOST    # 应为 "localhost"
$env:CHROMA_PORT    # 应为 "8001"
```

确保 Docker 中的 ChromaDB 容器正在运行。

### 13.3 Vite 出现 WebSocket proxy 日志

开发环境中偶尔出现：

```text
ws proxy error: read ECONNRESET
ws proxy socket error: write ECONNABORTED
```

如果页面可以继续使用，后端没有崩溃，这只是开发服务器 WebSocket 连接中断或刷新造成的噪声。当前前端 `vite.config.js` 已经对这些日志做了抑制。

### 13.4 简单问题也触发 RAG

如果简单计算触发了 RAG，检查后端的 RAG 触发逻辑。当前预期是明确提到知识库、`rag_search` 时才触发，普通数学和无需上下文的问题不触发 RAG。

### 13.5 Docker Compose 启动失败

检查：

- Docker Desktop 是否运行且处于 Linux 容器模式
- `.env` 文件中 `OPENAI_API_KEY` 是否已配置
- 端口 8000 和 3000 是否被占用

---

## 14. 技术栈

| 层级        | 技术                                                    |
| ----------- | ------------------------------------------------------- |
| 后端框架    | FastAPI + Uvicorn                                       |
| LLM 调用    | OpenAI Python SDK（兼容 API）                           |
| 状态机      | LangGraph（可选降级为手写状态机）                       |
| 数据库      | SQLite（含评测表结构，WAL 模式，自动迁移）              |
| 向量数据库  | ChromaDB（Docker HTTP 模式）                            |
| 评测评分    | Ragas（answer_relevancy, faithfulness）+ LLM-as-a-Judge |
| 安全扫描    | 启发式正则匹配（20+ 危险模式规则）                      |
| 前端框架    | Vue 3 (Composition API)                                 |
| 状态管理    | Pinia                                                   |
| 路由        | Vue Router 4                                            |
| 图表        | ECharts 6 + vue-echarts                                 |
| Markdown    | marked                                                  |
| 代码高亮    | highlight.js                                            |
| HTTP 客户端 | Axios                                                   |
| 实时通信    | WebSocket                                               |
| 构建工具    | Vite 6                                                  |
| 后端测试    | pytest + pytest-cov                                     |
| 前端测试    | Vitest + @vue/test-utils + jsdom                        |
| 容器化      | Docker + Docker Compose                                 |
| CI/CD       | GitLab CI（6 阶段流水线）                               |
| 数据校验    | Pydantic v2                                             |

---

## 15. 已知限制与未来计划

- [ ] 仅支持 OpenAI 兼容 API，暂未接入其他 LLM 提供商
- [ ] Web 搜索基于 DuckDuckGo/Bing HTML 解析，稳定性有限
- [ ] 无用户认证/授权机制
- [ ] 修复策略为整文件覆盖，对大型项目不够精细
- [ ] ChromaDB 需单独启动 Docker 容器
- [ ] 不支持多文件联动分析与修复

---

## 16. 注意事项

- 不要把真实 API Key 写入 README、代码或提交到 Git
- 不要把临时测试口令长期放入通用 RAG 知识库
- 不要把 ChromaDB 的 `8001` 当成 FastAPI 后端端口
- Windows 下推荐使用 Docker ChromaDB HTTP 模式，避免 PersistentClient 的 access violation 崩溃
- 如果需要修改知识库内容，修改文档后需要重新入库
- 如果只修改 README，不需要重启服务，也不需要重新入库
- CI/CD 流水线脚本使用 bash 语法（在 Linux 容器中运行），不是 PowerShell
- 后端虚拟环境路径、项目根目录路径以实际环境为准
