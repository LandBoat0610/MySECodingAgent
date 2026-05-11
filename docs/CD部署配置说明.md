# CD 部署配置说明

## 概述

本项目的 CI/CD 流水线共分 **5 个阶段**：

```
lint → security → test → report → build
```

前 4 个阶段（CI）使用公开 Docker 镜像 `python:3.11-slim` 并在 job 内安装依赖，`build` 阶段通过挂载的宿主机 Docker socket 直接构建部署镜像。

---

## Runner 环境

### 当前配置

| 项目            | 配置                                                  |
| --------------- | ----------------------------------------------------- |
| **Executor**    | `docker`（Linux 容器模式）                            |
| **Runner 名称** | `ymm`                                                 |
| **GitLab 地址** | `http://172.29.4.49`（内网）                          |
| **pull_policy** | 当前 Runner 只允许 `always`                           |
| **privileged**  | `true`（允许容器内使用 Docker）                       |
| **volumes**     | 挂载 `/var/run/docker.sock`（复用宿主机 Docker 引擎） |

> **关键提醒**：必须使用 `docker` executor，**不能**使用 `docker-windows` 或 `shell` executor。

### config.toml 配置参考

```toml
concurrent = 4
check_interval = 0

[[runners]]
  name = "ymm"
  url = "http://172.29.4.49"
  executor = "docker"
  [runners.docker]
    image = "python:3.11"
    privileged = true
    volumes = ["/var/run/docker.sock:/var/run/docker.sock"]
    pull_policy = "always"
    allowed_pull_policies = ["always"]
```

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

## Python CI 镜像

当前 `.gitlab-ci.yml` 使用 `python:3.11-slim`，并在隐藏 job `.python_ci` 的 `before_script`
中安装 `requirements.txt`、pytest、pytest-cov、flake8、bandit、coverage 等依赖。

这样可以避免依赖 Runner 宿主机上预先构建的本地 `ci-python:latest` 镜像。日志中如果出现：

```text
Using effective pull policy of [always]
failed to pull image "ci-python:latest"
```

说明 Runner 配置强制拉取镜像。当前 `.gitlab-ci.yml` 不再显式配置 `pull_policy`，避免在
`allowed_pull_policies = ["always"]` 的 Runner 上触发 `invalid pull policy`。

项目仍保留 `ci.Dockerfile`，需要进一步加速时可以构建并推送到可访问的镜像仓库：

```dockerfile
FROM python:3.11-slim
COPY requirements.txt .
RUN pip install --no-cache-dir \
    -r requirements.txt \
    pytest pytest-cov python-multipart \
    flake8 bandit coverage
```

### 可选构建命令

```powershell
# 在项目根目录执行（需先启动 Docker Desktop）
docker build -f ci.Dockerfile -t ci-python .
```

另外，本次失败日志里 Docker Desktop 正在访问 `docker.mirrors.ustc.edu.cn`，并且 DNS 解析失败。
`python:3.11-slim`、`node:20`、`docker:24` 都需要从 Docker Hub 拉取，所以必须在 Runner
宿主机的 Docker Desktop Docker Engine 配置中移除或替换这个失效的 registry mirror，然后重启
Docker Desktop 和 GitLab Runner。

---

## 整体流水线流程图

```
push to any branch
     │
     ├─ lint       (flake8 代码风格检查, image: python:3.11-slim)
     ├─ security   (bandit 安全扫描, image: python:3.11-slim)
     ├─ test       (pytest × 5 + vitest, 并行运行, image: python:3.11-slim / node:20)
     ├─ report     (coverage 覆盖率合并, image: python:3.11-slim)
     │
     └─ [main only] build_docker  ← CI 全部通过后自动触发
          ├─ 构建后端镜像  → 推送 registry.../backend:SHA
          ├─ 构建后端镜像  → 推送 registry.../backend:latest
          ├─ 构建前端镜像  → 推送 registry.../frontend:SHA
          └─ 构建前端镜像  → 推送 registry.../frontend:latest
```

---

## 新增文件清单

| 文件                                 | 说明                                           |
| ------------------------------------ | ---------------------------------------------- |
| `.gitlab-ci.yml`                     | 完整 CI/CD 流水线配置（5 阶段）                |
| `ci.Dockerfile`                      | CI 专用镜像（预装全部 Python 依赖 + 测试工具） |
| `docker-compose.yml`                 | 前后端本地联调编排                             |
| `Dockerfile`                         | 后端生产部署镜像                               |
| `agent/frontend/Dockerfile.frontend` | 前端多阶段构建（npm build → nginx 托管）       |
| `agent/frontend/nginx.conf`          | nginx 配置（history 路由 + API 反向代理）      |

---

## `.gitlab-ci.yml` 注意事项

### 必须使用 bash 语法

由于 CI 任务在 Linux Docker 容器中运行，脚本语法必须是 **bash**，不能使用 PowerShell。

| 场景         | ❌ 错误（PowerShell）                       | ✅ 正确（bash）                             |
| ------------ | ------------------------------------------ | ------------------------------------------ |
| 设置环境变量 | `$env:COVERAGE_FILE = ".coverage.backend"` | `export COVERAGE_FILE=".coverage.backend"` |
| 安装包       | `pip install ...`                          | `python -m pip install ...`               |
| 条件判断     | `if ($?) { ... }`                          | `if [ $? -eq 0 ]; then ... fi`             |

### 不需要 docker:dind

`build_docker` job 通过挂载的宿主机 Docker socket（`/var/run/docker.sock`）直接操作宿主机 Docker 引擎，无需启动额外的 `docker:24-dind` 服务容器。这避免了 dind 在 Windows Docker Desktop 下的兼容性问题。

---

## 使用前提

**不需要额外配置任何 GitLab 变量！**

`CI_REGISTRY`、`CI_REGISTRY_USER`、`CI_REGISTRY_PASSWORD`、`CI_REGISTRY_IMAGE`、`CI_COMMIT_SHORT_SHA` 均为 GitLab 内置变量，流水线运行时自动注入。

需要确认的事项：
1. **Docker Desktop** 已安装并处于 **Linux 容器模式**
2. GitLab Runner 已注册为 **`docker` executor**（不是 `shell` 或 `docker-windows`）
3. Docker Desktop 的 Docker Engine 配置中没有失效的 Docker Hub 镜像源
4. Runner 当前只允许 `pull_policy = "always"`，因此必须保证可以正常拉取 `python:3.11-slim`、`node:20` 和 `docker:24`

---

## 演示视频里如何展示 CD

1. Push 代码到 `cd` 分支，展示流水线运行，所有 stage 绿色 ✅
2. 点进 lint/test job，展示依赖安装、测试和覆盖率输出
3. （main 分支）点进 `build_docker` job，展示 Docker 镜像构建成功

---

## 本地拉取镜像运行（可选演示）

```bash
# 用 docker-compose 一键启动（需先配置环境变量）
# 编辑 .env 文件，填入 OPENAI_API_KEY 和 OPENAI_BASE_URL
docker-compose up

# 访问
# 前端: http://localhost:3000
# 后端 API 文档: http://localhost:8000/docs
```

---

## 常见问题

**Q: Runner 报 403 Forbidden 怎么办？**

说明 Runner 的注册 token 已失效或在 GitLab 上被删除。解决方法：
1. 进入 GitLab 项目 → Settings → CI/CD → Runners
2. 删除旧 runner，重新点击 **"New project runner"** 创建
3. 在本机重新执行 `gitlab-runner register` 命令
4. 启动 runner：`gitlab-runner start`

**Q: 为什么 CI 脚本里不能用 `$env:` 语法？**

因为 CI 任务在 Linux Docker 容器中运行，shell 是 bash 而非 PowerShell。
`$env:VAR = "value"` 是 PowerShell 语法，在 bash 中应使用 `export VAR="value"`。

**Q: 拉取 Docker Hub 镜像失败（EOF / timeout / no such host）？**

国内访问 Docker Hub 不稳定，且本项目当前 Runner 只允许 `pull_policy = "always"`，所以本地提前
`docker pull` 不能绕过拉取。解决方法：
1. 打开 Docker Desktop → Settings → Docker Engine
2. 删除或替换失效的 `"registry-mirrors"` 项，例如 `https://docker.mirrors.ustc.edu.cn`
3. 点击 Apply & Restart
4. 重启 GitLab Runner 服务后重新运行流水线

**Q: `build_docker` 是否需要 docker:dind？**

不需要。宿主机 Docker socket 已通过 `volumes` 挂入 CI 容器，`docker:24` 客户端可直接与宿主机 Docker 引擎通信。

**Q: 前端 Dockerfile 构建时 npm install 很慢怎么办？**

`Dockerfile.frontend` 里已经把 `package.json` 单独 COPY 并先 install，Docker 会缓存这一层，只要 `package.json` 没变，后续 push 时不会重新 install。
