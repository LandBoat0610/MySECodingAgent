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

## Runner 环境

| 项目            | 配置                         |
| --------------- | ---------------------------- |
| **Executor**    | `docker`（Linux 容器模式）   |
| **默认镜像**    | `python:3.11`                |
| **Runner 名称** | `ymm`                        |
| **GitLab 地址** | `http://172.29.4.49`（内网） |

> **关键提醒**：必须使用 `docker` executor，**不能**使用 `docker-windows` executor。
> 因为 `.gitlab-ci.yml` 中指定的 `image: python:3.11`、`image: node:20` 等均为 Linux 镜像，
> 在 Windows 容器模式下无法运行。

### Runner 注册命令（参考）

```powershell
cd D:\GitLab-Runner
.\gitlab-runner.exe register --url http://172.29.4.49 --token <你的token>

# 交互式回答：
# Enter an executor: docker
# Enter the default Docker image: python:3.11
```

注册完成后启动 runner：

```powershell
.\gitlab-runner.exe install   # 安装为 Windows 服务
.\gitlab-runner.exe start     # 启动服务
```

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

| 文件                                 | 说明                                      |
| ------------------------------------ | ----------------------------------------- |
| `.gitlab-ci.yml`                     | 在原有 CI 基础上新增 `build` stage        |
| `docker-compose.yml`                 | 本地联调时使用                            |
| `agent/frontend/Dockerfile.frontend` | 前端多阶段构建（npm build → nginx 托管）  |
| `agent/frontend/nginx.conf`          | nginx 配置（history 路由 + API 反向代理） |

---

## `.gitlab-ci.yml` 注意事项

### 必须使用 bash 语法

由于 CI 任务在 Linux Docker 容器中运行（`image: python:3.11`），脚本语法必须是 **bash**，不能使用 PowerShell。

| 场景         | ❌ 错误（PowerShell）                       | ✅ 正确（bash）                             |
| ------------ | ------------------------------------------ | ------------------------------------------ |
| 设置环境变量 | `$env:COVERAGE_FILE = ".coverage.backend"` | `export COVERAGE_FILE=".coverage.backend"` |
| 安装包       | `pip install xxx`                          | `pip install xxx`（无变化）                |
| 条件判断     | `if ($?) { ... }`                          | `if [ $? -eq 0 ]; then ... fi`             |

---

## 使用前提

**不需要额外配置任何 GitLab 变量！**

`CI_REGISTRY`、`CI_REGISTRY_USER`、`CI_REGISTRY_PASSWORD`、`CI_REGISTRY_IMAGE`、`CI_COMMIT_SHORT_SHA`
这些都是 GitLab 内置变量，流水线运行时会自动注入。

需要确认的事项：
1. **Docker Desktop** 已安装并处于 **Linux 容器模式**
2. GitLab Runner 已注册为 **`docker` executor**
3. **GitLab 项目已开启 Container Registry**（Settings → General → Visibility → Container Registry）

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

已配置的 `docker` executor runner 支持 Docker-in-Docker（`build_docker` job 使用 `docker:24-dind` service）。
GitLab 私服的 shared runner 通常也支持。如果报错说 `docker:dind` 服务无法启动，可以把 `build_docker` 的 `when` 改为 `when: manual`，这样不影响 CI 阶段的正常运行，演示时手动触发就行。

**Q: Runner 报 403 Forbidden 怎么办？**

说明 Runner 的注册 token 已失效或在 GitLab 上被删除。解决方法：
1. 进入 GitLab 项目 → Settings → CI/CD → Runners
2. 删除旧 runner，重新点击 **"New project runner"** 创建
3. 在本机重新执行 `gitlab-runner register` 命令
4. 启动 runner：`gitlab-runner start`

**Q: 为什么 CI 脚本里不能用 `$env:` 语法？**

因为 CI 任务在 Linux Docker 容器中运行，shell 是 bash 而非 PowerShell。
`$env:VAR = "value"` 是 PowerShell 语法，在 bash 中应使用 `export VAR="value"`。

**Q: 前端 Dockerfile 构建时 npm install 很慢怎么办？**

`Dockerfile.frontend` 里已经把 `package.json` 单独 COPY 并先 install，Docker 会缓存这一层，只要 `package.json` 没变，后续 push 时不会重新 install。
