# 使用轻量级的 Python 基础镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 先复制依赖文件，利用 Docker 层缓存加速构建
COPY requirements.txt .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . /app

# 设置环境变量，确保 Python 输出直接打印到终端，不被缓冲
ENV PYTHONUNBUFFERED=1

# 暴露后端服务端口
EXPOSE 8000

# 使用 uvicorn 启动 FastAPI 服务
CMD ["uvicorn", "agent.main:app", "--host", "0.0.0.0", "--port", "8000"]