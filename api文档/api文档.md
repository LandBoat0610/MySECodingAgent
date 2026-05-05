# Agent Platform API 文档

> **版本**: 0.1.0  
> **基础地址**: `http://127.0.0.1:8000`  
> **在线文档**: `http://127.0.0.1:8000/docs`（Swagger UI）  
> **启动命令**: `uvicorn agent.main:app --reload`

---

## 目录

- [1. 概述](#1-概述)
- [2. 全局约定](#2-全局约定)
- [3. 数据模型](#3-数据模型)
  - [3.1 数据库表结构](#31-数据库表结构)
  - [3.2 AgentState 状态模型](#32-agentstate-状态模型)
  - [3.3 请求/响应 Schema](#33-请求响应-schema)
- [4. API 接口详细说明](#4-api-接口详细说明)
  - [4.1 项目模块](#41-项目模块)
  - [4.2 会话模块](#42-会话模块)
  - [4.3 对话模块](#43-对话模块)
  - [4.4 计划模块](#44-计划模块)
  - [4.5 文件模块](#45-文件模块)
- [5. Agent 执行生命周期](#5-agent-执行生命周期)
- [6. WebSocket 实时流式协议](#6-websocket-实时流式协议)
  - [6.1 消息格式](#61-消息格式)
  - [6.2 实时同步机制](#62-实时同步机制)
  - [6.3 断连检测与接管制](#63-断连检测与接管制)
- [7. Agent 工具清单](#7-agent-工具清单)
- [8. 会话状态流转图](#8-会话状态流转图)
- [9. 环境变量与配置](#9-环境变量与配置)
- [10. 错误码说明](#10-错误码说明)
- [11. 完整交互时序示例](#11-完整交互时序示例)

---

## 1. 概述

Agent Platform 是一个自主编码 Agent 后端服务，提供项目/会话管理、对话任务分发、执行计划确认、文件树浏览等能力。核心特点：

- **项目级隔离**：每个项目拥有独立的工作区目录（`workspaces/project_{id}/`）
- **会话级并发控制**：同一会话同一时刻只允许一个 Agent 运行，刷新页面不中断 Agent，WebSocket 可重新挂载
- **计划确认机制**：Agent 生成执行计划后阻塞，等待用户审批（同意/优化/跳过/终止）
- **WebSocket 实时流式推送**：Agent 执行过程中的每一步日志实时推送至前端
- **断连重连机制**：刷新/关闭页面时 Agent 继续运行，新连接可重新挂载 WebSocket 恢复日志推送
- **执行终止支持**：用户可通过 `POST /plan/{pid}/action` (action=stop) 终止正在运行的 Agent
- **文件同步回传**：Agent 执行完成后，修改过的文件自动从工作区同步回项目根目录

---

## 2. 全局约定

| 约定项 | 说明 |
|--------|------|
| 数据格式 | 请求/响应均为 JSON |
| 字符编码 | UTF-8 |
| 时间格式 | ISO 8601 字符串，如 `2026-05-05T12:00:00.123456` |
| ID 生成 | 8 位十六进制随机字符串（`uuid.uuid4().hex[:8]`） |
| 错误响应 | `{"detail": "错误描述"}`，HTTP 状态码标识错误类型 |
| 数据库 | SQLite，文件位于项目根目录 `agent_platform.db` |
| 工作区根目录 | `{项目根}/workspaces/`，每个项目在此下创建独立子目录 |

---

## 3. 数据模型

### 3.1 数据库表结构

#### projects（项目表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | TEXT | PRIMARY KEY | 项目 ID（8 位 hex） |
| name | TEXT | NOT NULL | 项目名称 |
| workspace_path | TEXT | NOT NULL | 工作区绝对路径 |
| created_at | TEXT | NOT NULL | 创建时间（ISO 8601） |
| description | TEXT | DEFAULT '' | 项目描述 |

#### sessions（会话表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | TEXT | PRIMARY KEY | 会话 ID（8 位 hex） |
| project_id | TEXT | NOT NULL, FK → projects.id | 所属项目 |
| title | TEXT | DEFAULT 'New Session' | 会话标题 |
| created_at | TEXT | NOT NULL | 创建时间 |
| state_snapshot | TEXT | DEFAULT '{}' | AgentState 的 JSON 快照 |
| status | TEXT | DEFAULT 'idle' | 会话当前状态 |

#### plans（计划表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | TEXT | PRIMARY KEY | 计划 ID（8 位 hex） |
| session_id | TEXT | NOT NULL, FK → sessions.id | 所属会话 |
| project_id | TEXT | NOT NULL | 所属项目 |
| content | TEXT | DEFAULT '' | 计划步骤内容 |
| status | TEXT | DEFAULT 'pending' | 计划状态 |
| created_at | TEXT | NOT NULL | 创建时间 |

#### plan_actions（计划操作表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | TEXT | PRIMARY KEY | 操作 ID（8 位 hex） |
| plan_id | TEXT | NOT NULL, FK → plans.id | 关联计划 |
| action_type | TEXT | NOT NULL | 操作类型：agree / refine / skip / stop |
| created_at | TEXT | NOT NULL | 操作时间 |

### 3.2 AgentState 状态模型

AgentState 是贯穿整个 Agent 执行过程的核心数据结构，以 `TypedDict` 形式定义，存储在 `sessions.state_snapshot` 字段中。

| 字段 | 类型 | 说明 |
|------|------|------|
| session_id | str | 所属会话 ID |
| project_id | str | 所属项目 ID |
| task | str | 用户输入的任务描述 |
| messages | List[Dict] | 对话历史（含 role/content/tool_calls/tool_call_id） |
| workspace_dir | str | Agent 沙箱工作区路径 |
| project_root | str | 项目原始根目录路径 |
| status | str | 当前状态（见状态流转图） |
| task_list | List[str] | 生成的执行计划步骤列表 |
| current_task_index | int | 当前执行到的步骤索引 |
| current_task | str | 当前正在执行的步骤描述 |
| code_context | str | 当前目标文件的代码内容 |
| target_file | str | 目标文件相对路径 |
| run_command | str | 运行命令 |
| last_tool_result | Dict | 最近一次工具调用的返回结果 |
| last_execution | Dict | 最近一次 execute_bash 的返回结果 |
| errors | List[Dict] | 执行过程中的错误记录 |
| reflections | int | 自修复/反思次数 |
| trace | List[Dict] | 执行轨迹日志 |
| used_tools | List[str] | 已使用过的工具名称列表 |
| result_history | List[str] | 各步骤的结果摘要历史 |
| modified_files | List[str] | 被修改过的文件路径列表 |
| final_answer | str | 最终执行结果摘要 |
| original_target_path | str | 原始目标文件路径 |
| should_sync_back | bool | 是否需要将工作区文件同步回项目 |

### 3.3 请求/响应 Schema

#### ProjectCreateRequest

```json
{
  "name": "string (必填)",
  "description": "string (可选，默认 '')",
  "workspace_path": "string | null (可选，提供则打开已有项目)"
}
```

#### ProjectResponse

```json
{
  "id": "string",
  "name": "string",
  "workspace_path": "string",
  "created_at": "string",
  "description": "string"
}
```

#### SessionCreateRequest

```json
{
  "title": "string (可选，默认 'New Session')"
}
```

#### SessionResponse

```json
{
  "id": "string",
  "project_id": "string",
  "title": "string",
  "created_at": "string",
  "status": "string"
}
```

#### StateResponse

```json
{
  "session_id": "string",
  "project_id": "string",
  "status": "string",
  "snapshot": { }
}
```

`snapshot` 字段为完整的 AgentState JSON 对象，参见 [3.2 AgentState 状态模型](#32-agentstate-状态模型)。

#### ChatRequest

```json
{
  "message": "string (必填)"
}
```

#### ChatResponse

```json
{
  "session_id": "string",
  "reply": "string",
  "status": "string"
}
```

#### PlanActionRequest

```json
{
  "action": "agree | refine | skip | stop"
}
```

`action` 取值说明：

| 值 | 含义 |
|----|------|
| agree | 同意计划，Agent 开始执行 |
| refine | 要求 Agent 重新生成更优计划 |
| skip | 跳过当前计划 |
| stop | 终止 Agent 执行 |

#### PlanActionResponse

```json
{
  "plan_id": "string",
  "action": "string",
  "status": "string"
}
```

`status` 映射关系：

| action | status |
|--------|--------|
| agree | approved |
| refine | refining |
| skip | skipped |
| stop | stopped |

#### PlanResponse

```json
{
  "id": "string",
  "session_id": "string",
  "content": "string",
  "status": "string",
  "created_at": "string"
}
```

#### FileTreeResponse

```json
{
  "path": "string (相对路径)",
  "type": "file | directory",
  "children": ["FileTreeResponse (递归，仅 directory 有)"]
}
```

---

## 4. API 接口详细说明

### 4.1 项目模块

#### 4.1.1 获取项目列表

获取系统中所有已创建的项目，按创建时间降序排列。

```
GET /projects
```

**请求参数**：无

**响应**：`200 OK`

```json
[
  {
    "id": "a1b2c3d4",
    "name": "My Project",
    "workspace_path": "/abs/path/workspaces/project_a1b2c3d4",
    "created_at": "2026-05-05T12:00:00.123456",
    "description": "项目描述"
  }
]
```

**cURL 示例**：

```bash
curl http://127.0.0.1:8000/projects
```

---

#### 4.1.2 创建/打开项目

创建新项目或打开已有项目。当提供 `workspace_path` 时为打开已有项目，否则在 `workspaces/` 下自动创建新目录。

```
POST /projects
```

**请求体**：

```json
{
  "name": "My New Project",
  "description": "这是一个示例项目",
  "workspace_path": null
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | ✅ | 项目名称 |
| description | string | ❌ | 项目描述，默认为空 |
| workspace_path | string | ❌ | 已有目录的绝对路径；提供则打开已有项目 |

**响应**：`201 Created`

```json
{
  "id": "e5f6a7b8",
  "name": "My New Project",
  "workspace_path": "/abs/path/workspaces/project_e5f6a7b8",
  "created_at": "2026-05-05T14:30:00.654321",
  "description": "这是一个示例项目"
}
```

**错误响应**：

| 状态码 | 条件 | detail |
|--------|------|--------|
| 400 | workspace_path 不存在 | "指定的工作区路径不存在" |

**cURL 示例**：

```bash
# 创建新项目
curl -X POST http://127.0.0.1:8000/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "My Project", "description": "示例"}'

# 打开已有项目
curl -X POST http://127.0.0.1:8000/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "Existing", "workspace_path": "/path/to/existing/dir"}'
```

---

### 4.2 会话模块

#### 4.2.1 获取会话列表

获取指定项目下的所有会话，按创建时间降序排列。

```
GET /projects/{project_id}/sessions
```

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| project_id | string | 项目 ID |

**响应**：`200 OK`

```json
[
  {
    "id": "c9d0e1f2",
    "project_id": "a1b2c3d4",
    "title": "New Session",
    "created_at": "2026-05-05T12:00:00.123456",
    "status": "idle"
  }
]
```

**错误响应**：

| 状态码 | 条件 | detail |
|--------|------|--------|
| 404 | 项目不存在 | "项目不存在" |

**cURL 示例**：

```bash
curl http://127.0.0.1:8000/projects/a1b2c3d4/sessions
```

---

#### 4.2.2 新建会话

在指定项目下创建新会话，自动初始化 AgentState 快照。

```
POST /projects/{project_id}/sessions
```

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| project_id | string | 项目 ID |

**请求体**：

```json
{
  "title": "Debug Python Script"
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| title | string | ❌ | 会话标题，默认 "New Session" |

**响应**：`201 Created`

```json
{
  "id": "g3h4i5j6",
  "project_id": "a1b2c3d4",
  "title": "Debug Python Script",
  "created_at": "2026-05-05T15:00:00.111111",
  "status": "idle"
}
```

**初始化 AgentState 说明**：

新建会话时，系统会自动生成以下 AgentState 快照并存入数据库：

- `session_id` / `project_id`：绑定会话与项目
- `workspace_dir`：设为项目的工作区路径
- `project_root`：同 `workspace_dir`
- `status`：初始为 `"idle"`
- `messages` / `trace` / `errors` / `used_tools` / `modified_files` 等：初始化为空列表
- `reflections`：初始为 0

**错误响应**：

| 状态码 | 条件 | detail |
|--------|------|--------|
| 404 | 项目不存在 | "项目不存在" |

**cURL 示例**：

```bash
curl -X POST http://127.0.0.1:8000/projects/a1b2c3d4/sessions \
  -H "Content-Type: application/json" \
  -d '{"title": "Debug Python Script"}'
```

---

#### 4.2.3 获取会话状态快照

获取指定会话的当前状态，包含完整的 AgentState 快照。

```
GET /projects/{project_id}/sessions/{sid}/state
```

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| project_id | string | 项目 ID |
| sid | string | 会话 ID |

**响应**：`200 OK`

```json
{
  "session_id": "g3h4i5j6",
  "project_id": "a1b2c3d4",
  "status": "running",
  "snapshot": {
    "session_id": "g3h4i5j6",
    "project_id": "a1b2c3d4",
    "task": "在我的工作区中创建一个 readmetest.txt 文件，内容为 Hello Agent",
    "messages": [
      {"role": "user", "content": "在我的工作区中创建一个 readmetest.txt 文件，内容为 Hello Agent"}
    ],
    "workspace_dir": "/abs/path/workspaces/project_a1b2c3d4",
    "status": "running",
    "task_list": [],
    "current_task_index": 0,
    "current_task": "",
    "code_context": "",
    "target_file": "",
    "run_command": "",
    "last_tool_result": {},
    "last_execution": {},
    "errors": [],
    "reflections": 0,
    "trace": [],
    "used_tools": [],
    "result_history": [],
    "modified_files": [],
    "final_answer": "",
    "original_target_path": "",
    "should_sync_back": false,
    "project_root": "/abs/path/workspaces/project_a1b2c3d4"
  }
}
```

**错误响应**：

| 状态码 | 条件 | detail |
|--------|------|--------|
| 404 | 会话不存在 | "会话不存在于该项目下" |

**cURL 示例**：

```bash
curl http://127.0.0.1:8000/projects/a1b2c3d4/sessions/g3h4i5j6/state
```

---

### 4.3 对话模块

#### 4.3.1 发送消息（同步）

向指定会话发送任务消息。消息写入 AgentState 后 Agent 即开始处理（但此接口不会等待 Agent 执行完成，需通过 WebSocket 接口获取实时执行流）。

```
POST /projects/{project_id}/sessions/{sid}/chat
```

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| project_id | string | 项目 ID |
| sid | string | 会话 ID |

**请求体**：

```json
{
  "message": "创建一个 hello.py 文件，内容为 print('Hello World')"
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| message | string | ✅ | 任务消息内容 |

**响应**：`200 OK`

```json
{
  "session_id": "g3h4i5j6",
  "reply": "消息已接收，Agent 开始处理...",
  "status": "running"
}
```

**说明**：

- 调用此接口后，会话状态自动从 `idle` 变为 `running`
- 消息被追加到 `state.messages` 中作为 `role: user` 记录
- `state.task` 被设置为消息内容
- 此接口**不等待** Agent 执行完成，返回后需通过 WebSocket 或轮询 `/state` 接口查看进度

**错误响应**：

| 状态码 | 条件 | detail |
|--------|------|--------|
| 404 | 会话不存在 | "会话不存在于该项目下" |

**cURL 示例**：

```bash
curl -X POST http://127.0.0.1:8000/projects/a1b2c3d4/sessions/g3h4i5j6/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "创建一个 hello.py，输出 Hello World"}'
```

---

#### 4.3.2 WebSocket 流式对话

通过 WebSocket 建立 Agent 执行流式连接，实时接收 Agent 执行过程中的日志、状态变化和最终结果。支持断连自动检测与新连接接管。

```
WS /projects/{project_id}/sessions/{sid}/chat/stream
```

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| project_id | string | 项目 ID |
| sid | string | 会话 ID |

**前置条件**：

1. 必须先通过 `POST /chat` 接口发送任务消息（否则返回错误）
2. 同一会话同一时刻只允许一个 Agent 运行（新连接会自动取消旧 Agent 后接管）

**WebSocket 连接生命周期**：

```
客户端连接 → 服务端验证 → 取消旧 Agent（如有）→ Agent 执行 → 日志实时推送 → 完成推送 → 关闭连接
```

**服务端推送消息类型**：

1. **执行开始**

```json
{
  "phase": "start",
  "message": "Agent 开始执行..."
}
```

2. **执行轨迹日志**（持续推送）

```json
{
  "type": "trace",
  "data": {
    "time": "2026-05-05 12:05:30",
    "phase": "plan",
    "content": "Creating plan for task: ...",
    "meta": {}
  }
}
```

`data.phase` 取值说明：

| phase | 含义 |
|-------|------|
| plan | 生成执行计划 |
| plan_result | 计划生成结果 |
| planner | 等待用户确认计划 |
| reason | Agent 推理过程 |
| act | Agent 调用工具 |
| observe | 工具执行返回结果 |
| check_result | 检查步骤结果 |
| modify_code | 代码修复 |
| repair_written | 修复写入完成 |
| final | 任务完成 |
| cancelled | 被用户终止 |
| sync_back_success | 文件同步回传成功 |
| sync_back_skip | 跳过文件同步 |

3. **执行完成**

```json
{
  "phase": "done",
  "message": "任务完成",
  "final_answer": "Overall task: ...",
  "status": "completed"
}
```

4. **执行被终止**

```json
{
  "phase": "cancelled",
  "message": "Agent 已终止"
}
```

5. **错误信息**

```json
{
  "error": "错误描述"
}
```

**浏览器 JavaScript 示例**：

```javascript
const ws = new WebSocket("ws://127.0.0.1:8000/projects/a1b2c3d4/sessions/g3h4i5j6/chat/stream");

ws.onopen = () => console.log("已连接");
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log("[Agent]", data);
};
ws.onclose = () => console.log("连接关闭");
ws.onerror = (err) => console.error("连接错误", err);
```

**终止 Agent 执行**：

在 WebSocket 连接期间，可通过以下方式终止 Agent：
- 调用 `POST /plan/{pid}/action` 并传入 `action: "stop"`
- 直接关闭 WebSocket 连接（刷新页面、关闭标签页等），服务端会自动检测断连并设置取消信号

---

### 4.4 计划模块

#### 4.4.1 获取当前会话的计划树

获取指定会话下所有已生成的执行计划步骤。

```
GET /projects/{project_id}/sessions/{sid}/plan
```

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| project_id | string | 项目 ID |
| sid | string | 会话 ID |

**响应**：`200 OK`

```json
[
  {
    "id": "k7l8m9n0",
    "session_id": "g3h4i5j6",
    "content": "创建 readmetest.txt 文件并写入 Hello Agent",
    "status": "pending",
    "created_at": "2026-05-05T12:01:00.222222"
  },
  {
    "id": "o1p2q3r4",
    "session_id": "g3h4i5j6",
    "content": "验证文件内容是否正确",
    "status": "pending",
    "created_at": "2026-05-05T12:01:00.333333"
  }
]
```

**说明**：

- 计划步骤按 `created_at DESC` 排序（最新优先）
- `status` 可能的值：`pending` / `approved` / `refining` / `skipped` / `stopped`

**错误响应**：

| 状态码 | 条件 | detail |
|--------|------|--------|
| 404 | 会话不存在 | "会话不存在于该项目下" |

**cURL 示例**：

```bash
curl http://127.0.0.1:8000/projects/a1b2c3d4/sessions/g3h4i5j6/plan
```

---

#### 4.4.2 用户对计划执行确认操作

用户对指定计划步骤执行确认操作。此操作同时更新 `plans.status` 和 `sessions.status`，从而解除 Agent 的计划等待阻塞。

```
POST /projects/{project_id}/sessions/{sid}/plan/{pid}/action
```

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| project_id | string | 项目 ID |
| sid | string | 会话 ID |
| pid | string | 计划 ID |

**请求体**：

```json
{
  "action": "agree"
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| action | string | ✅ | 操作类型，枚举值：agree / refine / skip / stop |

**响应**：`200 OK`

```json
{
  "plan_id": "k7l8m9n0",
  "action": "agree",
  "status": "approved"
}
```

**action 与 status 映射**：

| action | plans.status | sessions.status | Agent 行为 |
|--------|-------------|-----------------|------------|
| agree | approved | approved | 立即开始执行计划 |
| refine | refining | refining | 重新生成计划后再等待确认 |
| skip | skipped | skipped | 跳过计划 |
| stop | stopped | stopped | 终止 Agent 执行 |

**关键机制说明**：

- `plan_action` 同时更新 `plans` 和 `sessions` 两张表的 `status`
- Agent 的 `wait_for_plan_approval()` 轮询 `sessions.status`（而非 `plans.status`）
- 所以必须更新 `sessions.status` 才能解除 Agent 的阻塞等待
- 用户选择 `refine` 后，Agent 会重新调用 LLM 生成新计划，然后再轮询等待用户确认

**错误响应**：

| 状态码 | 条件 | detail |
|--------|------|--------|
| 404 | 会话不存在 | "会话不存在于该项目下" |
| 404 | 计划不存在 | "计划不存在" |

**cURL 示例**：

```bash
# 同意计划
curl -X POST http://127.0.0.1:8000/projects/a1b2c3d4/sessions/g3h4i5j6/plan/k7l8m9n0/action \
  -H "Content-Type: application/json" \
  -d '{"action": "agree"}'

# 要求优化计划
curl -X POST http://127.0.0.1:8000/projects/a1b2c3d4/sessions/g3h4i5j6/plan/k7l8m9n0/action \
  -H "Content-Type: application/json" \
  -d '{"action": "refine"}'

# 终止执行
curl -X POST http://127.0.0.1:8000/projects/a1b2c3d4/sessions/g3h4i5j6/plan/k7l8m9n0/action \
  -H "Content-Type: application/json" \
  -d '{"action": "stop"}'
```

---

### 4.5 文件模块

#### 4.5.1 获取项目文件树

获取指定项目工作区下的完整文件树（递归）。

```
GET /projects/{project_id}/files
```

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| project_id | string | 项目 ID |

**响应**：`200 OK`

```json
[
  {
    "path": "src",
    "type": "directory",
    "children": [
      {
        "path": "src/main.py",
        "type": "file",
        "children": null
      },
      {
        "path": "src/utils",
        "type": "directory",
        "children": [
          {
            "path": "src/utils/helper.py",
            "type": "file",
            "children": null
          }
        ]
      }
    ]
  },
  {
    "path": "readme.md",
    "type": "file",
    "children": null
  }
]
```

**说明**：

- 所有路径均为相对于工作区根目录的相对路径
- 文件节点的 `children` 为 `null`
- 目录节点的 `children` 为子节点数组（递归结构）
- 如果工作区为空目录，返回空数组 `[]`

**错误响应**：

| 状态码 | 条件 | detail |
|--------|------|--------|
| 404 | 项目不存在 | "项目不存在" |

**cURL 示例**：

```bash
curl http://127.0.0.1:8000/projects/a1b2c3d4/files
```

---

## 5. Agent 执行生命周期

Agent 的执行由一个状态图（StateGraph）驱动，包含以下节点和流转：

```
┌──────────┐
│ planner  │ ← 入口：生成执行计划，等待用户确认
└────┬─────┘
     │
     ▼
┌──────────┐
│ executor │ ← 执行当前步骤（调用 LLM + 工具）
└────┬─────┘
     │
     ▼
┌──────────────┐
│ check_result │ ← 检查执行结果是否成功
└────┬─────────┘
     │
     ├── needs_fix (且 reflections < MAX_REFLECTIONS=3)
     │   ┌──────────────┐
     │   │ modify_code  │ ← 修复代码后返回 executor 重试
     │   └──────┬───────┘
     │          │
     │          ▼
     │      executor (循环)
     │
     ├── step_ok (且有下一步)
     │   ┌────────────┐
     │   │ next_step  │ ← 推进到下一步后返回 executor
     │   └──────┬─────┘
     │          │
     │          ▼
     │      executor (循环)
     │
     ├── stopped
     │   ┌──────────┐
     │   │ finalize │ ← 提前终止
     │   └──────────┘
     │
     └── 其他（完成/超反思次数）
         ┌──────────┐
         │ finalize │ ← 生成最终摘要
         └──────────┘
```

**各节点职责**：

| 节点 | 职责 |
|------|------|
| planner | 调用 LLM 将任务拆分为 3-6 步计划；写入 plans 表；设置 status=awaiting_approval；轮询 sessions 表等待用户确认 |
| executor | 调用 LLM（带 tools）执行当前步骤；循环最多 MAX_STEP_ITERATIONS(6) 次；每次迭代检查取消信号 |
| check_result | 检查执行输出和 stderr 中是否包含错误信号（SyntaxError、NameError 等）；判断 returncode |
| modify_code | 将错误信息和当前代码交给 LLM 生成修复；写回文件；reflections 计数 +1 |
| next_step | 任务索引 +1，推进到下一步 |
| finalize | 生成最终摘要（包含使用的工具、反思次数、各步骤结果），保存记忆，更新会话状态为 completed |

---

## 6. WebSocket 实时流式协议

### 6.1 消息格式

所有服务端推送消息均为 JSON 格式，分为以下类型：

#### 轨迹消息（trace）

Agent 执行过程中的每一步操作都会以轨迹消息推送：

```json
{
  "type": "trace",
  "data": {
    "time": "2026-05-05 12:05:30",
    "phase": "act",
    "content": "write_file({\"path\": \"hello.py\", \"content\": \"print('Hello')\"})",
    "meta": {}
  }
}
```

#### 阶段消息（phase）

表示 Agent 执行的整体阶段变化：

| 消息 | 说明 |
|------|------|
| `{"phase": "start", "message": "..."}` | Agent 开始执行 |
| `{"phase": "done", "message": "任务完成", "final_answer": "...", "status": "completed"}` | 正常完成 |
| `{"phase": "cancelled", "message": "Agent 已终止"}` | 被用户终止 |

#### 错误消息

```json
{
  "error": "错误描述文本"
}
```

### 6.2 实时同步机制

- **日志回调**：Agent 通过 `log_state()` 记录轨迹时，同步调用注册的回调函数
- **跨线程推送**：Agent 在独立线程中运行，通过 `asyncio.run_coroutine_threadsafe()` 将消息推送至主事件循环的 WebSocket
- **数据库同步**：每次 `log_state()` 调用时同时更新 `sessions.state_snapshot`，确保 REST API 也能获取最新状态
- **取消信号**：通过 `threading.Event`（`cancel_event`）传递，Agent 在每次工具调用前后检查 `_check_cancel()`

### 6.3 断连重连机制

Agent 的生命周期**绑定到会话**，而非绑定到 WebSocket 连接。这意味着刷新页面不会中断正在运行的 Agent。

#### 核心架构：AgentRunner

每个会话对应一个 `AgentRunner` 实例，Agent 在独立守护线程中运行：

```
AgentRunner(sid)
├── _thread: Agent 执行线程（守护线程）
├── _ws_ref: 当前活跃的 WebSocket 引用（线程安全切换）
├── cancel_event: 取消信号（仅用于用户主动 stop）
├── done: Agent 执行完成标志
└── started: Agent 已启动标志
```

#### 断连行为

当客户端断开 WebSocket（刷新页面/关闭标签页/网络中断）：

1. WebSocket handler 正常退出 `finally` 块
2. `runner.set_ws(None, None)` 将 WebSocket 引用置空
3. Agent 线程**继续运行**，日志回调检查到 `_ws_ref is None` 后静默跳过
4. Agent 的 `log_state()` 仍然将状态写入数据库，确保进度不丢失

#### 重连行为

当客户端重新建立 WebSocket 连接：

1. 检查 `runner.is_alive() and not runner.done.is_set()` 判断 Agent 是否正在运行
2. 如果 Agent 还在运行：`runner.set_ws(websocket, loop)` 重新挂载 WebSocket → 日志恢复推送
3. 如果 Agent 尚未启动：启动 Agent 线程，挂载 WebSocket
4. 如果 Agent 已完成（`done.is_set()`）：创建新的 `AgentRunner` 实例，启动新的 Agent 任务

**关键**：重连不会取消 Agent，而是重新挂载 WebSocket 引用，让用户可以继续观察进度。已完成的后会话可以发起新任务。

#### 取消机制

Agent 的取消**仅由用户主动触发**，不会因 WebSocket 断开而自动取消：

| 触发方式 | 原理 |
|----------|------|
| `POST /plan/{pid}/action` (action=stop) | 设置 `sessions.status = "stopped"` → `cancel_event.set()` → Agent 在 `_check_cancel()` 检查点终止 |
| 直接修改数据库 | 将 `sessions.status` 设为 `stopped` → 下次 `wait_for_plan_approval` 轮询时感知 |

#### 状态保护

`finalize_node` 不会覆盖已被用户设置为 `stopped` 的状态：

```python
final_status = state.get("status", "completed")
if final_status not in ("stopped", "skipped"):
    final_status = "completed"
```

#### 场景对比

| 场景 | 旧行为（AsyncIO Lock） | 新行为（AgentRunner） |
|------|------------------------|----------------------|
| 刷新页面 | Agent 继续跑但锁不释放，新连接被拒绝 | Agent 继续跑，重连后恢复日志推送 |
| 关闭标签页后重开 | 同上 | 同上 |
| 网络中断后恢复 | Agent 继续跑，send_json 静默失败 | Agent 继续跑，重连后恢复 |
| 新连接到已完成会话 | N/A | 创建新 AgentRunner，启动新任务 |
| 用户主动 stop | cancel_event 设置，但可能被覆盖为 completed | cancel_event 设置，finalize 尊重 stopped 状态 |

---

## 7. Agent 工具清单

Agent 可调用以下 5 个工具与环境交互，均运行在项目沙箱工作区内：

| 工具名 | 功能 | 参数 | 安全限制 |
|--------|------|------|----------|
| execute_bash | 执行 shell 命令 | `command: string` | 拦截危险命令（rm -rf /、shutdown、fork bomb 等）；超时 20 秒 |
| read_file | 读取文件内容 | `path: string` | 路径不能逃逸工作区 |
| write_file | 写入文件内容 | `path: string, content: string` | 路径不能逃逸工作区；自动创建父目录 |
| web_search | 搜索互联网信息 | `query: string` | 使用 DuckDuckGo HTML 搜索，返回前 5 条结果 |
| fetch_url | 获取网页文本内容 | `url: string` | 去除 HTML 标签，提取纯文本 |

**工具返回格式**（统一 JSON）：

```json
{
  "status": "success | error",
  "output": "输出内容",
  "path": "相关路径（可选）",
  "returncode": 0,
  "meta": {}
}
```

**安全拦截规则**（`BLOCKED_BASH_PATTERNS`）：

| 正则模式 | 拦截对象 |
|----------|----------|
| `rm -rf /` | 递归删除根目录 |
| `shutdown` | 关机命令 |
| `reboot` | 重启命令 |
| `:(){ :\|:& };:` | Fork bomb |
| `dd if=` | 磁盘覆写 |
| `mkfs` | 格式化文件系统 |
| `chmod -R 777 /` | 递归修改根权限 |

---

## 8. 会话状态流转图

```
                ┌──────────┐
                │   idle   │ ← 初始状态
                └────┬─────┘
                     │ POST /chat
                     ▼
                ┌──────────┐
                │  running │ ← Agent 正在执行
                └────┬─────┘
                     │ planner 生成计划
                     ▼
           ┌───────────────────┐
           │ awaiting_approval │ ← 等待用户确认计划
           └──┬────┬────┬──────┘
              │    │    │
     agree ──┘    │    └── stop
              │    │         │
              ▼    ▼         ▼
         running  running  stopped
              │    │
              │  refine
              │    │
              │    ▼
              │  (重新生成计划)
              │
      ┌───────┴────────┐
      │                 │
  step_ok          needs_fix
      │                 │
      ▼                 ▼
  next_step       modify_code
      │                 │
      ▼                 ▼
  running ──────► running
                        │ (最多 MAX_REFLECTIONS=3 次)
                        ▼
                   finalize
                        │
                        ▼
                  ┌───────────┐
                  │ completed │ ← 最终完成
                  └───────────┘
```

**完整状态枚举**：

| 状态 | 说明 |
|------|------|
| idle | 初始空闲状态 |
| running | Agent 正在执行 |
| awaiting_approval | 等待用户确认执行计划 |
| approved | 用户已同意计划 |
| refining | 用户要求优化计划 |
| needs_fix | 当前步骤执行出错，需要修复 |
| next_step | 当前步骤成功，推进下一步 |
| step_ok | 步骤检查通过 |
| stopped | 被用户终止 |
| skipped | 计划被跳过 |
| completed | 任务完成 |

---

## 9. 环境变量与配置

### 必需环境变量

| 变量名 | 说明 | 示例 |
|--------|------|------|
| OPENAI_API_KEY | OpenAI API 密钥 | `sk-...` |

### 可选环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| OPENAI_BASE_URL | None | OpenAI API 代理地址 |
| OPENAI_MODEL | gpt-4o-mini | 使用的模型名称 |
| ZIZHI_AGENT_WORKSPACE | None | 自定义工作区根目录 |

### 运行时配置常量（config.py）

| 常量 | 默认值 | 说明 |
|------|--------|------|
| MAX_STEP_ITERATIONS | 6 | 每个步骤内 LLM 循环最大迭代次数 |
| MAX_REFLECTIONS | 3 | 单个步骤最大自修复/反思次数 |
| MAX_TOOL_OUTPUT | 4000 | 工具输出的最大截断字符数 |
| MEMORY_FILE | agent_memory.md | Agent 记忆文件路径 |
| TRACE_JSON | agent_trace.json | 轨迹 JSON 文件路径 |
| TRACE_MERMAID | agent_trace.mmd | 轨迹 Mermaid 图文件路径 |

---

## 10. 错误码说明

| HTTP 状态码 | 含义 | 常见场景 |
|-------------|------|----------|
| 200 | 成功 | GET 请求成功 |
| 201 | 创建成功 | POST 创建项目/会话成功 |
| 400 | 请求错误 | workspace_path 路径不存在 |
| 404 | 资源不存在 | 项目/会话/计划 ID 不存在 |
| 422 | 参数校验失败 | 请求体字段类型错误、必填字段缺失 |
| 500 | 服务器内部错误 | 数据库错误、序列化异常 |

**422 校验错误响应示例**：

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "message"],
      "msg": "Field required",
      "input": {}
    }
  ]
}
```

---

## 11. 完整交互时序示例

以下展示一个完整的"创建项目 → 新建会话 → 发送任务 → WebSocket 执行 → 确认计划 → 查看文件树"的端到端流程。

### Step 1: 创建项目

```bash
curl -X POST http://127.0.0.1:8000/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Project", "description": "测试项目"}'
```

响应：

```json
{
  "id": "a1b2c3d4",
  "name": "Test Project",
  "workspace_path": "D:\\dasanxia\\ruangong3\\diedai2\\2-1\\workspaces\\project_a1b2c3d4",
  "created_at": "2026-05-05T12:00:00.123456",
  "description": "测试项目"
}
```

### Step 2: 新建会话

```bash
curl -X POST http://127.0.0.1:8000/projects/a1b2c3d4/sessions \
  -H "Content-Type: application/json" \
  -d '{"title": "Create README"}'
```

响应：

```json
{
  "id": "e5f6g7h8",
  "project_id": "a1b2c3d4",
  "title": "Create README",
  "created_at": "2026-05-05T12:01:00.123456",
  "status": "idle"
}
```

### Step 3: 发送任务消息

```bash
curl -X POST http://127.0.0.1:8000/projects/a1b2c3d4/sessions/e5f6g7h8/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "创建一个 readmetest.txt 文件，内容为 Hello Agent"}'
```

响应：

```json
{
  "session_id": "e5f6g7h8",
  "reply": "消息已接收，Agent 开始处理...",
  "status": "running"
}
```

### Step 4: 建立 WebSocket 连接

在浏览器 `about:blank` 页面控制台执行：

```javascript
const ws = new WebSocket("ws://127.0.0.1:8000/projects/a1b2c3d4/sessions/e5f6g7h8/chat/stream");
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(JSON.stringify(data));
};
```

收到执行日志：

```json
{"phase": "start", "message": "Agent 开始执行..."}
{"type": "trace", "data": {"time": "2026-05-05 12:02:01", "phase": "plan", "content": "Creating plan for task: ...", "meta": {}}}
{"type": "trace", "data": {"time": "2026-05-05 12:02:05", "phase": "plan_result", "content": "1. 创建 readmetest.txt\n2. 验证文件内容", "meta": {}}}
{"type": "trace", "data": {"time": "2026-05-05 12:02:05", "phase": "planner", "content": "计划已生成，等待用户确认...", "meta": {}}}
```

### Step 5: 查看计划并确认

```bash
# 查看计划
curl http://127.0.0.1:8000/projects/a1b2c3d4/sessions/e5f6g7h8/plan
```

响应：

```json
[
  {
    "id": "i9j0k1l2",
    "session_id": "e5f6g7h8",
    "content": "创建 readmetest.txt 文件并写入内容",
    "status": "pending",
    "created_at": "2026-05-05T12:02:05.123456"
  },
  {
    "id": "m3n4o5p6",
    "session_id": "e5f6g7h8",
    "content": "验证文件内容是否正确",
    "status": "pending",
    "created_at": "2026-05-05T12:02:05.234567"
  }
]
```

```bash
# 同意计划
curl -X POST http://127.0.0.1:8000/projects/a1b2c3d4/sessions/e5f6g7h8/plan/i9j0k1l2/action \
  -H "Content-Type: application/json" \
  -d '{"action": "agree"}'
```

响应：

```json
{
  "plan_id": "i9j0k1l2",
  "action": "agree",
  "status": "approved"
}
```

### Step 6: 观察 Agent 继续执行

WebSocket 继续收到日志：

```json
{"type": "trace", "data": {"time": "...", "phase": "reason", "content": "Step '创建 readmetest.txt...' iteration 1", "meta": {}}}
{"type": "trace", "data": {"time": "...", "phase": "act", "content": "write_file({\"path\": \"readmetest.txt\", \"content\": \"Hello Agent\"})", "meta": {}}}
{"type": "trace", "data": {"time": "...", "phase": "observe", "content": "{\"status\": \"success\", \"output\": \"Successfully wrote to ...\"}", "meta": {}}}
{"type": "trace", "data": {"time": "...", "phase": "final", "content": "Overall task: ...", "meta": {}}}
{"phase": "done", "message": "任务完成", "final_answer": "...", "status": "completed"}
```

### Step 7: 断连后重新连接（新增场景）

用户刷新页面后，在新页面重新建立 WebSocket 连接：

```javascript
// 旧连接因刷新自动断开 → detect_disconnect 检测到 → cancel_event 设置 → Agent 终止
// 新连接到来 → 检测到旧 Agent 的 done_event → 等待最多 5 秒 → 接管
const ws = new WebSocket("ws://127.0.0.1:8000/projects/a1b2c3d4/sessions/e5f6g7h8/chat/stream");
```

### Step 8: 查看最终状态

```bash
curl http://127.0.0.1:8000/projects/a1b2c3d4/sessions/e5f6g7h8/state
```

`status` 已变为 `"completed"`，`snapshot.final_answer` 包含完整执行摘要。

### Step 9: 查看文件树

```bash
curl http://127.0.0.1:8000/projects/a1b2c3d4/files
```

响应：

```json
[
  {
    "path": "readmetest.txt",
    "type": "file",
    "children": null
  }
]
```

---

## 附录：API 速查表

| # | 方法 | 路径 | 说明 |
|---|------|------|------|
| 1 | GET | `/projects` | 获取项目列表 |
| 2 | POST | `/projects` | 创建/打开项目 |
| 3 | GET | `/projects/{project_id}/sessions` | 获取会话列表 |
| 4 | POST | `/projects/{project_id}/sessions` | 新建会话 |
| 5 | GET | `/projects/{project_id}/sessions/{sid}/state` | 获取会话状态快照 |
| 6 | POST | `/projects/{project_id}/sessions/{sid}/chat` | 发送任务消息 |
| 7 | WS | `/projects/{project_id}/sessions/{sid}/chat/stream` | WebSocket 流式对话 |
| 8 | GET | `/projects/{project_id}/sessions/{sid}/plan` | 获取计划树 |
| 9 | POST | `/projects/{project_id}/sessions/{sid}/plan/{pid}/action` | 确认计划操作 |
| 10 | GET | `/projects/{project_id}/files` | 获取文件树 |
