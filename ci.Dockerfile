# ci.Dockerfile – 用于 GitLab CI 测试环境的镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /ci-env

# 设置 pip 缓存目录（可选，配合 GitLab 缓存加速）
ENV PIP_CACHE_DIR=/.cache/pip

# 复制依赖文件
COPY requirements.txt .

# 安装所有项目依赖 + 测试依赖（pytest, pytest-cov, python-multipart, etc.）
# 如果你习惯将测试依赖单独分组，也可以放在 requirements-test.txt 中
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir pytest pytest-cov python-multipart

# （可选）安装 flake8 / bandit（如果你希望它们也预装，但通常这两个工具在各自的作业中单独安装更好，因为不是每个作业都需要）
# 我们仍保留这些工具在各自的作业中安装，避免镜像膨胀