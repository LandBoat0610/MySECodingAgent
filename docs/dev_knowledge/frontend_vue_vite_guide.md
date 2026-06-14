# Vue、Vite 与前端测试知识

本知识文档用于辅助 Agent 编写和调试前端功能。

## Vue 组件开发原则

- 组件显示的数据应来自 store 或明确的 props。
- 用户操作应通过事件、store action 或 API 封装完成。
- 异步状态应包含 loading、error 和空状态。
- 长文本、按钮文字和卡片内容应避免在移动端溢出。

## Pinia store 开发原则

修改 store 时要检查：

- state 初始值是否合理。
- computed 是否覆盖空数据情况。
- action 是否捕获错误并更新 error 状态。
- WebSocket 消息是否保留未知工具名和未知事件，不要误过滤。

## Vite 代理规则

前端开发服务器端口是：

```text
http://localhost:3000
```

后端 FastAPI 端口是：

```text
http://127.0.0.1:8000
```

Vite 应把 `/projects`、`/settings`、`/eval` 等后端请求代理到 `8000`。不要把前端代理指向 ChromaDB 的 `8001`。

WebSocket 开发代理偶尔出现 `ECONNRESET` 或 `ECONNABORTED`，通常是连接正常关闭时的开发日志噪音。若页面流程正常完成，可以忽略。

## 前端测试

运行前端测试：

```powershell
cd agent\frontend
npm run test
```

如果修改了组件展示，应补充组件测试。如果修改了 API 路径，应补充 API 层测试。如果修改 WebSocket store 逻辑，应补充 store 测试。

