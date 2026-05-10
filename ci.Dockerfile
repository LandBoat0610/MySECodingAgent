# ci.Dockerfile – 用于 GitLab CI 测试环境的镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /ci-env

# 设置 pip 缓存目录（可选，配合 GitLab 缓存加速）
ENV PIP_CACHE_DIR=/.cache/pip

# 复制依赖文件
COPY requirements.txt .

# 一次性安装所有依赖：项目依赖 + 测试工具 + 代码检查 + 覆盖率
RUN pip install --no-cache-dir \
    -r requirements.txt \
    pytest pytest-cov python-multipart \
    flake8 bandit coverage