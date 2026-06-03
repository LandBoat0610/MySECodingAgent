# 调试、安全与交付知识

本知识文档用于辅助 Agent 排查错误、保护敏感信息并完成交付说明。

## 调试流程

1. 先复现问题，记录命令、输入和错误输出。
2. 根据错误栈定位具体文件和函数。
3. 优先修复根因，不要只隐藏报错。
4. 增加回归测试覆盖失败场景。
5. 重新运行相关测试确认修复。

## 常见错误判断

- `ModuleNotFoundError`：通常是依赖未安装或 Python 环境不对。
- `Connection error`：通常是网络、API 地址、Key 或外部服务不可用。
- `ECONNRESET` / `ECONNABORTED`：如果只出现在 Vite WebSocket 代理日志中，且页面流程完成，通常是开发代理断连噪音。
- `unexpected keyword argument`：调用函数时传入了函数签名不支持的参数，应检查包装层和工具函数签名。
- ChromaDB Windows access violation：避免使用本机 PersistentClient，改用 Docker HTTP 模式。

## 安全规则

- 不要把真实 API Key 写入 README、代码、测试或提交记录。
- `.env` 不应提交。
- `.env.example` 只保留占位值。
- 日志和最终回答中不要复述用户的完整密钥。
- 涉及删除、重置、覆盖数据的操作应先说明影响。

## 交付说明格式

开发任务完成后，最终说明应包含：

- 修改了哪些文件。
- 根因是什么。
- 修复方式是什么。
- 运行了哪些测试。
- 测试结果如何。
- 是否还有剩余限制。

