# CD 部署配置说明

## 概述

本项目的 CI/CD 流水线共分 **5 个阶段**：

```
lint → security → test → report → build
```

前 4 个阶段（CI）已完成，`build` 阶段为本次新增的 CD 内容。

> **说明**：本方案不依赖外部服务器，使用 GitLab 内置的 Container Registry 作为镜像仓库，
> 只要 `build_docker` job 跑通，即证明"交付物可以打包为可运行的容器镜像"。

---

## 整体流水线流程图

```
push to main
     │
     ├─ lint       (flake8 代码风格检查)
     ├─ security   (bandit 安全扫描)
     ├─ test       (pytest × 5 + vitest，并行运行)
     ├─ report     (coverage 覆盖率合并)
     │
     └─ [build] build_docker  ← CI 全部通过后自动触发
          ├─ 构建后端镜像  → 推送 registry.../backend:SHA
          ├─ 构建后端镜像  → 推送 registry.../backend:latest
          ├─ 构建前端镜像  → 推送 registry.../frontend:SHA
          └─ 构建前端镜像  → 推送 registry.../frontend:latest
```

---

## 新增文件清单

| 文件 | 说明 |
|------|------|
| `.gitlab-ci.yml` | 在原有 CI 基础上新增 `build` stage |
| `docker-compose.yml` | 本地联调时使用 |
| `agent/frontend/Dockerfile.frontend` | 前端多阶段构建（npm build → nginx 托管） |
| `agent/frontend/nginx.conf` | nginx 配置（history 路由 + API 反向代理） |

---

## 使用前提

**不需要额外配置任何 GitLab 变量！**

`CI_REGISTRY`、`CI_REGISTRY_USER`、`CI_REGISTRY_PASSWORD`、`CI_REGISTRY_IMAGE`、`CI_COMMIT_SHORT_SHA`
这些都是 GitLab 内置变量，流水线运行时会自动注入。

唯一要确认的一点：**GitLab 项目要开启 Container Registry**。
- 进入 GitLab 项目页面 → Settings → General → Visibility, project features, permissions
- 确保 **Container Registry** 是开启状态（默认就是开启的）

---

## 演示视频里如何展示 CD

1. 展示 GitLab 流水线页面，所有 stage 全部绿色 ✅
2. 点进 `build_docker` job，展示日志输出（能看到 `docker push` 成功）
3. 进入项目页面 → **Packages & Registries → Container Registry**
   - 展示里面有 `backend` 和 `frontend` 两个镜像，每个都有对应的 tag（SHA + latest）

这三步就足以说明 CD 流程完整跑通了。

---

## 本地拉取镜像运行（可选演示）

如果本机装了 Docker，可以直接拉镜像跑起来：

```bash
# 先登录 GitLab Registry（替换为你们的 gitlab 地址和用户名）
docker login registry.gitlab.com

# 拉取镜像（替换为你们项目的实际 registry 地址，在 Container Registry 页面能看到）
docker pull registry.gitlab.com/你的组/你的项目/backend:latest
docker pull registry.gitlab.com/你的组/你的项目/frontend:latest

# 用 docker-compose 一键启动（需先配置环境变量）
# 编辑 .env 文件，填入 OPENAI_API_KEY 和 OPENAI_BASE_URL
docker-compose up

# 访问
# 前端: http://localhost:3000
# 后端 API 文档: http://localhost:8000/docs
```

---

## 常见问题

**Q: `build_docker` 需要 GitLab Runner 支持 Docker-in-Docker，我们的 Runner 支持吗？**

看你们用的 Runner 类型：
- 学校私服 GitLab 的 shared runner 通常支持
- 如果报错说 `docker:dind` 服务无法启动，可以把 `build_docker` 的 `when` 改为 `when: manual`，这样不影响 CI 阶段的正常运行，演示时手动触发就行

**Q: 前端 Dockerfile 构建时 npm install 很慢怎么办？**

`Dockerfile.frontend` 里已经把 `package.json` 单独 COPY 并先 install，Docker 会缓存这一层，只要 `package.json` 没变，后续 push 时不会重新 install。
