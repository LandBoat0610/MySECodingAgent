# API 契约文档 (v1.0)

## 1. 通讯协议概述

为了实现 Agent 思考过程的实时展示，本项目采用 **HTTP POST** 发起任务，并使用 **Server-Sent Events (SSE)** 技术进行流式响应。

- **后端入口**: `http://<server-ip>:8000/api/agent/run`
- **通讯方式**: `POST` 请求开启连接，`text/event-stream` 持续推送。

------

## 2. 任务启动接口

### 请求 (Request)

- **Method**: `POST`
- **Path**: `/api/agent/run`
- **Body**:



```json
{
  "task": "string",          // 用户输入的具体指令
  "file_path": "string",     // 当前正在处理的文件路径（可选）
  "project_context": "object" // 包含项目结构等上下文信息
}
```

------

## 3. 状态推送流规格 (SSE Payload)

所有推送消息均采用 `event: message`，数据部分为标准的 JSON 字符串。

### 数据基础结构

```json
{
  "node": "string",    // 当前执行节点：planner | executor | reviewer
  "status": "string",  // 节点状态：thinking | acting | success | error
  "message": "string", // 给用户看的实时日志（内心独白）
  "data": "object"     // 该步骤产生的具体附件数据
}
```

### 节点与 payload 详解

#### A. 规划阶段 (Planner)

- **node**: `planner`

- **data 内容**:

  ```JSON
  {
    "plan_list": ["step1", "step2"], // 拆解的任务列表
    "current_step": 0
  }
  ```

#### B. 执行阶段 (Executor)

- **node**: `executor`

- **data 内容**:

  JSON

  ```JSON
  {
    "tool": "terminal/file_reader", // 使用的工具名
    "input": "pytest ...",          // 输入参数
    "output": "FAILED: ...",        // 执行结果（非常重要，用于展示报错）
    "code_diff": "string"           // 如果修改了代码，返回 diff 内容
  }
  ```

#### C. 审阅/修正阶段 (Reviewer)

- **node**: `reviewer`

- **data 内容**:

  JSON

  ```JSON
  {
    "review_result": "pass/fail",
    "reflection": "发现死循环，准备重新规划..." // 反思内容
  }
  ```

------

## 4. 状态枚举值定义 (Enums)

为了防止前后端解析错误，必须严格遵守以下字符串取值：

| **字段**   | **取值**   | **描述**                     |
| ---------- | ---------- | ---------------------------- |
| **node**   | `planner`  | Agent 正在拆解任务           |
|            | `executor` | Agent 正在调用工具执行操作   |
|            | `reviewer` | Agent 正在检查结果/进行反思  |
| **status** | `thinking` | 正在调用 LLM 进行推理        |
|            | `acting`   | 正在执行本地 IO 或终端命令   |
|            | `success`  | 当前环节成功完成             |
|            | `error`    | 发生异常（触发自我修正逻辑） |

------

## 5. 异常处理机制 (Requirement 3)

当后端捕获到系统异常（如文件不存在、编译报错）时，必须推送一条 `status: "error"` 的消息。

**示例消息：**

```json
{
  "node": "executor",
  "status": "error",
  "message": "代码运行失败，准备进行自我修正...",
  "data": {
    "error_type": "SyntaxError",
    "stack_trace": "line 15: expected ':'"
  }
}
```

------

### 给组员的实施建议

1. **后端实现**: 在 FastAPI 的生成器函数中，每当进入一个新的 LangGraph 节点，就 `yield` 一次符合上述格式的 JSON。
2. **前端实现**: 使用 `fetch` 的 `body.getReader()` 来解析流数据。每收到一个包，根据 `node` 的值去点亮 React Flow 中对应的节点图标。
3. **Mock 开发**: 前端组现在可以根据这个文档，在 `src/mocks/` 目录下手写几个 JSON 数组，模拟一个“报错 -> 修复 -> 通过”的全过程。