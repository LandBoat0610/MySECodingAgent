# Agent Platform API 接口文档

> **版本**: 0.1.0  
> **基础地址**: `http://127.0.0.1:8000`  
> **在线文档**: `http://127.0.0.1:8000/docs`（Swagger UI）  
> **启动命令**: `uvicorn agent.main:app --reload`

---

## 目录

- [1. 概述](#1-概述)
- [2. 全局约定](#2-全局约定)
- [3. 数据模型](#3-数据模型)
- [4. API 接口详细说明](#4-api-接口详细说明)
  - [4.1 项目模块](#41-项目模块)
  - [4.2 会话模块](#42-会话模块)
  - [4.3 对话模块](#43-对话模块)
  - [4.4 计划模块](#44-计划模块)
  - [4.5 文件模块](#45-文件模块)
- [5. WebSocket 实时流式协议](#5-websocket-实时流式协议)
- [6. Agent 工具清单](#6-agent-工具清单)
- [7. 会话状态流转](#7-会话状态流转)
- [8. 环境变量与配置](#8-环境变量与配置)

---

## 1. 概述

Agent Platform 是一个自主编码 Agent 后端服务，核心特点：

- **项目级隔离**：每个项目拥有独立工作区目录
- **会话级并发控制**：同一会话同一时刻只允许一个 Agent 运行
- **计划确认机制**：Agent 生成执行计划后阻塞，等待用户审批
- **WebSocket 实时推送**：Agent 执行过程中的每一步日志实时推送至前端
- **断连重连**：刷新页面不中断 Agent，WebSocket 可重新挂载
- **执行终止**：用户可终止正在运行的 Agent

---

## 2. 全局约定

| 约定项 | 说明 |
|--------|------|
| 数据格式 | 请求/响应均为 JSON |
| 字符编码 | UTF-8 |
| 时间格式 | ISO 8601 字符串 |
| ID 生成 | 8 位十六进制随机字符串（`uuid.uuid4().hex[:8]`） |
| 错误响应 | `{"detail": "错误描述"}` |
| 数据库 | SQLite，文件 `agent_platform.db` |

---

## 3. 数据模型

### 3.1 请求/响应 Schema

#### ProjectCreateRequest

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | ✅ | 项目名称 |
| description | string | ❌ | 项目描述，默认空 |
| workspace_path | string | ❌ | 已有目录绝对路径；提供则打开已有项目 |

#### ProjectResponse

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 项目 ID |
| name | string | 项目名称 |
| workspace_path | string | 工作区绝对路径 |
| created_at | string | 创建时间 |
| description | string | 项目描述 |

#### DeleteProjectResponse

| 字段 | 类型 | 说明 |
|------|------|------|
| status | string | 固定值 `deleted` |
| project_id | string | 被删除的项目 ID |

#### SessionCreateRequest

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| title | string | ❌ | 会话标题，默认 "New Session" |

#### SessionResponse

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 会话 ID |
| project_id | string | 所属项目 ID |
| title | string | 会话标题 |
| created_at | string | 创建时间 |
| status | string | 会话状态 |

#### StateResponse

| 字段 | 类型 | 说明 |
|------|------|------|
| session_id | string | 会话 ID |
| project_id | string | 项目 ID |
| status | string | 会话状态 |
| snapshot | object | AgentState 完整快照 |

#### ChatRequest

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| message | string | ✅ | 用户消息内容 |

#### ChatResponse

| 字段 | 类型 | 说明 |
|------|------|------|
| session_id | string | 会话 ID |
| reply | string | 回复消息 |
| status | string | 会话状态 |

#### PlanActionRequest

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| action | string | ✅ | 操作类型：agree / refine / skip / stop |

#### PlanActionResponse

| 字段 | 类型 | 说明 |
|------|------|------|
| plan_id | string | 计划 ID |
| action | string | 操作类型 |
| status | string | 更新后的状态 |

**action 与 status 映射：**

| action | status | 所有 pending plans 状态 |
|--------|--------|------------------------|
| agree | approved | 全部更新为 approved |
| refine | refining | 不变（旧 pending 在后端重新生成计划时被标 skipped） |
| skip | skipped | 全部更新为 skipped |
| stop | stopped | 全部更新为 stopped |

#### PlanResponse

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 计划 ID |
| session_id | string | 所属会话 ID |
| content | string | 计划步骤内容 |
| status | string | 计划状态 |
| created_at | string | 创建时间 |

#### FileTreeResponse

| 字段 | 类型 | 说明 |
|------|------|------|
| path | string | 相对路径 |
| type | string | "file" 或 "directory" |
| children | array | 子节点列表（仅 directory 有） |

#### FileContentResponse

| 字段 | 类型 | 说明 |
|------|------|------|
| path | string | 文件相对路径 |
| content | string | 文件文本内容 |
| size | integer | 文件大小（字节） |
| encoding | string | 编码方式，固定 `utf-8` |

---

## 4. API 接口详细说明

### 4.1 项目模块

#### 4.1.1 获取项目列表

```
GET /projects
```

**响应**：`200 OK` — `ProjectResponse[]`

#### 4.1.2 创建/打开项目

```
POST /projects
```

**请求体**：`ProjectCreateRequest`  
**响应**：`201 Created` — `ProjectResponse`  
**错误**：`400` — workspace_path 不存在

---

#### 4.1.3 删除项目

```
DELETE /projects/{project_id}
```

**响应**：`200 OK` — `DeleteProjectResponse`

```json
{
  "status": "deleted",
  "project_id": "a1b2c3d4"
}
```

**行为说明**：
- 级联删除该项目下所有会话、计划、计划操作记录
- 如果有 Agent 正在运行，会先发送取消信号终止
- **不会**删除磁盘上的工作区目录

**错误**：`404` — 项目不存在

---

### 4.2 会话模块

#### 4.2.1 获取会话列表

```
GET /projects/{project_id}/sessions
```

**响应**：`200 OK` — `SessionResponse[]`  
**错误**：`404` — 项目不存在

#### 4.2.2 新建会话

```
POST /projects/{project_id}/sessions
```

**请求体**：`SessionCreateRequest`  
**响应**：`201 Created` — `SessionResponse`  
**错误**：`404` — 项目不存在

#### 4.2.3 获取会话状态快照

```
GET /projects/{project_id}/sessions/{sid}/state
```

**响应**：`200 OK` — `StateResponse`  
**错误**：`404` — 会话不存在

---

### 4.3 对话模块

#### 4.3.1 发送消息

```
POST /projects/{project_id}/sessions/{sid}/chat
```

**请求体**：`ChatRequest`  
**响应**：`200 OK` — `ChatResponse`

将用户消息写入会话状态，并将会话状态设置为 `running`。之后需通过 WebSocket 连接获取 Agent 执行过程。

#### 4.3.2 WebSocket 流式对话

```
WS /projects/{project_id}/sessions/{sid}/chat/stream
```

WebSocket 连接建立后，如果 Agent 已在运行，则实时接收 trace 日志；如果未运行，则启动新的 Agent 执行。

**消息格式见第 5 节。**

#### 4.3.3 停止会话运行

```
POST /projects/{project_id}/sessions/{sid}/stop
```

**响应**：`200 OK`

```json
{
  "status": "stopped",
  "session_id": "string"
}
```

任何时候都可以调用此接口终止正在运行的 Agent。会话状态和所有 pending 计划都会被标记为 `stopped`。

---

### 4.4 计划模块

#### 4.4.1 获取计划列表

```
GET /projects/{project_id}/sessions/{sid}/plan
```

**响应**：`200 OK` — `PlanResponse[]`  
**错误**：`404` — 会话不存在

#### 4.4.2 对计划执行操作

```
POST /projects/{project_id}/sessions/{sid}/plan/{pid}/action
```

**请求体**：`PlanActionRequest`  
**响应**：`200 OK` — `PlanActionResponse`  
**错误**：`404` — 会话或计划不存在

**行为说明：**
- `agree`：同意计划，所有 pending 计划标记为 approved，Agent 开始执行
- `refine`：要求优化，Agent 重新生成计划（旧 pending 计划会被标记为 skipped）
- `skip`：跳过计划，所有 pending 计划标记为 skipped
- `stop`：终止执行，所有 pending 计划标记为 stopped

---

### 4.5 文件模块

#### 4.5.1 获取项目文件树

```
GET /projects/{project_id}/files
```

**响应**：`200 OK` — `FileTreeResponse[]`（递归树结构）  
**错误**：`404` — 项目不存在

---

#### 4.5.2 获取文件内容

```
GET /projects/{project_id}/files/content?path={relative_path}
```

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| path | string | ✅ | 文件相对于工作区根目录的路径 |

**响应**：`200 OK` — `FileContentResponse`

**错误**：
- `403` — 路径超出项目工作区范围（路径遍历攻击防护）
- `404` — 项目不存在 或 文件不存在
- `413` — 文件过大（超过 10MB）
- `415` — 文件非文本格式，无法以 UTF-8 解码

---

## 5. WebSocket 实时流式协议

### 5.1 连接

```
WS /projects/{project_id}/sessions/{sid}/chat/stream
```

### 5.2 消息格式

后端向客户端推送的消息为 JSON 对象，主要有以下几种类型：

#### trace 消息（Agent 执行步骤日志）

```json
{
  "type": "trace",
  "data": {
    "time": "2026-05-05 12:00:00",
    "phase": "reason",
    "content": "Step 'xxx' iteration 1",
    "meta": {},
    "session_status": "running"
  }
}
```

**phase 取值：**

| phase | 说明 |
|-------|------|
| plan | 生成计划 |
| plan_result | 计划结果 |
| planner | 等待用户确认 |
| reason | 推理步骤 |
| act | 执行工具 |
| observe | 观察结果 |
| check_result | 检查结果 |
| modify_code | 修改代码 |
| repair_written | 修复已写入 |
| final | 最终结果 |
| cancelled | 已取消 |

**session_status** 字段表明当前会话状态，前端应据此同步 UI 状态。

#### phase 消息（生命周期事件）

```json
{
  "phase": "start",
  "message": "Agent 正在执行..."
}
```

```json
{
  "phase": "done",
  "message": "任务完成",
  "final_answer": "最终答案文本",
  "status": "completed"
}
```

#### error 消息

```json
{
  "error": "错误描述"
}
```

### 5.3 断连重连

WebSocket 断开时，如果会话仍处于 `running`/`awaiting_approval`/`approved` 状态，前端应尝试重新建立连接（最多 5 次，递增延迟）。Agent 在后端继续运行，不受连接断开影响。

---

## 6. Agent 工具清单

| 工具名 | 说明 | 参数 |
|--------|------|------|
| execute_bash | 执行 bash 命令 | `command: string` |
| read_file | 读取文件内容 | `path: string` |
| write_file | 写入文件内容 | `path: string, content: string` |
| web_search | 搜索网页 | `query: string` |
| fetch_url | 获取网页内容 | `url: string` |

---

## 7. 会话状态流转

```
idle -> running -> awaiting_approval -> approved -> running -> ... -> completed
                                                          -> stopped
                              -> refining -> running -> awaiting_approval -> ...
                              -> skipped
                                                              -> needs_fix -> modify_code -> running
                                                              -> step_ok -> next_step -> running
                                                              -> stopped
```

---

## 8. 环境变量与配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| OPENAI_API_KEY | OpenAI API Key | - |
| OPENAI_BASE_URL | OpenAI API 基础地址 | - |
| OPENAI_MODEL | 使用的模型名 | gpt-4o-mini |
| ZIZHI_AGENT_WORKSPACE | 工作区根目录 | 自动创建临时目录 |
| COMSPEC | Windows cmd.exe 路径（用于 bash 执行） | 系统默认 |
