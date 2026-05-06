# Agent Platform

一个面向代码任务的**自治执行代理平台（Autonomous Coding Agent Platform）**，采用 **Planner → Executor → Reviewer → ModifyCode** 的工作流，提供完整的 Web 管理界面，能够针对自然语言任务自动规划步骤、调用工具、执行命令、检查结果，并在失败时自动修复代码。

---

## 1. 项目简介

Agent Platform 是一个全栈项目（Python 后端 + Vue 前端），核心能力包括：

- 📋 **项目管理**：创建/管理多个项目工作区，每个项目拥有独立的工作目录
- 💬 **会话管理**：每个项目下可创建多个对话会话，会话状态持久化到 SQLite
- 🤖 **自治代理**：接收自然语言任务，自动拆解步骤、调用大模型执行、验证结果、修复代码
- 🔧 **工具调用**：内置 5 类工具（bash 执行、文件读写、网页搜索、URL 抓取）
- 🔒 **安全沙箱**：工作区隔离，路径逃逸防护，危险命令拦截
- 📊 **实时追踪**：WebSocket 实时推送执行轨迹，前端可视化展示
- ✅ **计划审批**：执行前可预览计划，支持同意/优化/跳过/停止四种操作
- 🌐 **Web 界面**：Vue 3 构建的现代暗色主题管理界面

---

## 2. 系统架构

```
┌──────────────────────────────────────────────────────────┐
│                      Frontend (Vue 3)                     │
│  端口: 3000  (Vite dev server, 代理后端到 8000)           │
│  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌────────────┐ │
│  │ProjectPanel│ │FileTreePanel│ │FilePreview│ │ ChatPanel │ │
│  └──────────┘ └───────────┘ └──────────┘ └────────────┘ │
└──────────────────────┬───────────────────────────────────┘
                       │ HTTP REST + WebSocket
┌──────────────────────┴───────────────────────────────────┐
│                    Backend (FastAPI)                       │
│  端口: 8000                                                │
│  ┌────────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐ │
│  │  main.py   │ │ graph.py │ │  llm.py  │ │ tools.py  │ │
│  │ (API路由)  │ │(状态机)  │ │(LLM调用) │ │(工具函数) │ │
│  └────────────┘ └──────────┘ └──────────┘ └───────────┘ │
│  ┌────────────┐ ┌──────────┐ ┌──────────┐                │
│  │database.py │ │ state.py │ │ utils.py │                │
│  │ (SQLite)   │ │(状态定义)│ │(工具函数)│                │
│  └────────────┘ └──────────┘ └──────────┘                │
└──────────────────────┬───────────────────────────────────┘
                       │ OpenAI API
┌──────────────────────┴───────────────────────────────────┐
│                  LLM (GPT-4o-mini 等)                      │
└──────────────────────────────────────────────────────────┘
```

---

## 3. 核心特性

### 3.1 自治任务执行 (Planner → Executor → Reviewer → ModifyCode)

1. **Planner（规划）**：LLM 将任务拆解为 3-6 个具体步骤，并生成执行计划等待用户确认
2. **Executor（执行）**：按步骤调用 LLM function calling 选择工具并执行（最多迭代 3 次/步）
3. **Reviewer（审查）**：检查执行结果，识别错误信号（traceback、exit code 等）
4. **ModifyCode（修复）**：根据错误信息生成修正代码并写回文件，最多自动修复 3 次

### 3.2 内置工具能力

| 工具           | 功能     | 说明                                       |
| -------------- | -------- | ------------------------------------------ |
| `execute_bash` | 执行命令 | 在隔离工作区中执行 bash 命令，20s 超时保护 |
| `read_file`    | 读取文件 | 读取工作区内文件内容                       |
| `write_file`   | 写入文件 | 向工作区写入文件，自动创建父目录           |
| `web_search`   | 网页搜索 | 通过 DuckDuckGo 搜索获取外部信息           |
| `fetch_url`    | 抓取网页 | 抓取 URL 并提取纯文本内容                  |

### 3.3 安全机制

- **工作区隔离**：所有文件操作限制在项目专属的工作区目录内
- **路径逃逸防护**：`resolve_workspace_path` 阻止 `../` 等路径逃逸
- **危险命令拦截**：正则匹配拦截 `rm -rf /`、`shutdown`、`mkfs` 等危险操作
- **超时控制**：bash 命令 20 秒超时，LLM 调用有超时限制

### 3.4 实时追踪

- 执行轨迹（trace）通过 WebSocket 实时推送到前端
- 每次执行后状态自动持久化到 SQLite
- 输出 `agent_trace.json` 和 `agent_trace.mmd`（Mermaid 状态图）

### 3.5 LangGraph 支持与降级

- 若安装了 `langgraph`，使用图状态机执行
- 否则自动回退为 `run_manual_fallback` 手写状态机

---

## 4. 项目结构

```
2-1/
├── agent/                          # 后端核心代码
│   ├── main.py                     # FastAPI 应用入口，所有 API 路由
│   ├── prompts.yaml                # LLM 提示词配置（系统角色、约束、模板）
│   ├── conftest.py                 # 测试环境配置
│   ├── __init__.py
│   └── backend/
│       ├── config.py               # 全局常量配置（模型、路径、安全规则等）
│       ├── database.py             # SQLite 数据库初始化与连接管理
│       ├── graph.py                # 核心状态机：Planner/Executor/Reviewer/ModifyCode
│       ├── llm.py                  # LLM 调用封装（OpenAI API）
│       ├── schemas.py              # Pydantic 数据模型（请求/响应）
│       ├── session_manager.py      # 会话管理器（预留）
│       ├── state.py                # AgentState TypedDict 定义
│       ├── tools.py                # 工具定义与实现（5 类工具）
│       └── utils.py                # 工具函数（路径解析、提示词加载、日志等）
├── frontend/                       # Vue 3 前端
│   ├── index.html                  # 入口 HTML
│   ├── package.json                # 前端依赖与脚本
│   ├── vite.config.js              # Vite 配置（含代理到后端）
│   └── src/
│       ├── App.vue                 # 根组件（三栏布局）
│       ├── main.js                 # Vue 应用入口
│       ├── api/index.js            # 后端 API 封装
│       ├── stores/agent.js         # Pinia 全局状态管理
│       ├── utils/persistence.js    # 本地持久化（localStorage）
│       └── components/
│           ├── ProjectPanel.vue    # 项目/会话列表管理
│           ├── FileTreePanel.vue   # 文件树面板
│           ├── FileTreeNode.vue    # 文件树节点组件
│           ├── FilePreview.vue     # 文件预览面板
│           ├── ChatPanel.vue       # 对话面板（消息+执行轨迹）
│           └── PlanDialog.vue      # 计划确认对话框
├── tests/                          # 单元测试
│   ├── test_config.py
│   ├── test_database.py
│   ├── test_graph.py
│   ├── test_llm.py
│   ├── test_main.py
│   ├── test_schemas.py
│   ├── test_state.py
│   ├── test_tools.py
│   └── test_utils.py
├── workspaces/                     # 项目工作区目录（运行时自动创建）
├── docs/                           # 文档目录
├── requirements.txt                # Python 依赖
├── Dockerfile                      # Docker 构建文件
├── agent_memory.md                 # 代理记忆文件（运行时自动生成）
└── README.md                       # 本文件
```

---

## 5. API 接口概览

| 方法 | 路径                                                   | 说明                                     |
| ---- | ------------------------------------------------------ | ---------------------------------------- |
| GET  | `/projects`                                            | 获取所有项目列表                         |
| POST | `/projects`                                            | 创建/打开项目                            |
| GET  | `/projects/{pid}/sessions`                             | 获取项目下会话列表                       |
| POST | `/projects/{pid}/sessions`                             | 创建新会话                               |
| GET  | `/projects/{pid}/sessions/{sid}/state`                 | 获取会话状态快照                         |
| POST | `/projects/{pid}/sessions/{sid}/chat`                  | 发送任务消息                             |
| WS   | `/projects/{pid}/sessions/{sid}/chat/stream`           | WebSocket 流式执行追踪                   |
| GET  | `/projects/{pid}/sessions/{sid}/plan`                  | 获取执行计划                             |
| POST | `/projects/{pid}/sessions/{sid}/plan/{plan_id}/action` | 对计划执行操作（agree/refine/skip/stop） |
| GET  | `/projects/{pid}/files`                                | 获取项目文件树                           |

---

## 6. 环境变量

| 变量                    | 说明                | 默认值                      |
| ----------------------- | ------------------- | --------------------------- |
| `OPENAI_API_KEY`        | OpenAI API 密钥     | **必需**                    |
| `OPENAI_BASE_URL`       | OpenAI API 基础 URL | `https://api.openai.com/v1` |
| `OPENAI_MODEL`          | 使用的模型名称      | `gpt-4o-mini`               |
| `ZIZHI_AGENT_WORKSPACE` | 自定义工作区根目录  | 自动创建临时目录            |

---

## 7. 启动方式

### 7.1 环境要求

- Python 3.10+
- Node.js 18+
- npm

### 7.2 后端启动

```bash
# 1. 进入项目目录
cd 2-1

# 2. 创建并激活虚拟环境
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 3. 安装 Python 依赖
pip install -r requirements.txt

# 4. 设置环境变量
# Windows (PowerShell):
$env:OPENAI_API_KEY="your-api-key-here"
$env:OPENAI_BASE_URL="https://api.openai.com/v1"   # 可选，若使用代理则必填
# Linux/macOS:
export OPENAI_API_KEY="your-api-key-here"

# 5. 启动后端服务
cd agent
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

后端启动后访问 http://127.0.0.1:8000/docs 查看 Swagger API 文档。

### 7.3 前端启动

```bash
# 打开新终端，进入前端目录
cd agent/frontend

# 安装 npm 依赖
npm install

# 启动前端开发服务器
npm run dev
```

前端启动后访问 http://localhost:3000。

> **说明**：Vite dev server 已配置代理，`/projects` 开头的请求会自动转发到 `http://127.0.0.1:8000`。

### 7.4 使用 Docker 启动（仅后端）

```bash
# 构建镜像
docker build -t agent-platform .

# 运行容器
docker run -p 8000:8000 \
  -e OPENAI_API_KEY="your-api-key-here" \
  -e OPENAI_BASE_URL="https://api.openai.com/v1" \
  agent-platform
```

### 7.5 完整使用流程

1. 打开浏览器访问 `http://localhost:3000`
2. 在左侧面板点击 `+` 创建一个**项目**
3. 选中项目后，点击 `+` 创建一个**会话**
4. 在右侧 ChatPanel 输入框中描述你的任务（例如"帮我写一个 Python 快速排序程序"）
5. 点击 **Send** 发送任务
6. 在弹出对话框中查看 Agent 生成的执行计划，选择：
   - ✅ **Agree**：同意计划并开始执行
   - 🔄 **Refine**：让 Agent 重新生成计划
   - ⏭ **Skip**：跳过当前计划
   - ⏹ **Stop**：停止执行
7. 执行过程中可在右侧面板实时查看日志轨迹和最终结果

---

## 8. 运行测试

```bash
cd 2-1
pytest tests/ -v
```

---

## 9. 配置说明

### 9.1 修改 LLM 提示词

编辑 `agent/prompts.yaml` 可自定义系统角色、编程原则、约束条件和各阶段提示词模板。

### 9.2 调整代理行为

编辑 `agent/backend/config.py` 可调整：

| 配置项                  | 说明                 | 默认值        |
| ----------------------- | -------------------- | ------------- |
| `MAX_STEP_ITERATIONS`   | 每个步骤最大迭代次数 | 3             |
| `MAX_REFLECTIONS`       | 最大自我修复次数     | 3             |
| `MAX_TOOL_OUTPUT`       | 工具输出最大字符数   | 4000          |
| `BLOCKED_BASH_PATTERNS` | 危险命令拦截正则列表 | 预置 7 条规则 |

---

## 10. 技术栈

| 层级        | 技术                              |
| ----------- | --------------------------------- |
| 后端框架    | FastAPI + Uvicorn                 |
| LLM 调用    | OpenAI Python SDK                 |
| 状态机      | LangGraph（可选降级为手写状态机） |
| 数据库      | SQLite                            |
| 前端框架    | Vue 3 (Composition API)           |
| 状态管理    | Pinia                             |
| HTTP 客户端 | Axios                             |
| 实时通信    | WebSocket                         |
| 构建工具    | Vite                              |
| 容器化      | Docker                            |
| 数据校验    | Pydantic v2                       |

---

## 11. 已知限制与未来计划

- [ ] 文件预览功能 API 尚未实现（当前为占位 UI）
- [ ] 仅支持 OpenAI 兼容 API，暂未接入其他 LLM 提供商
- [ ] Web 搜索基于 DuckDuckGo HTML 解析，稳定性有限
- [ ] 无用户认证/授权机制
- [ ] 会话管理器（`session_manager.py`）尚未实现
- [ ] 修复策略为整文件覆盖，对大型项目不够精细
- [ ] 不支持多文件联动分析与修复
