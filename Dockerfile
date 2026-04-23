# 使用轻量级的 Python 基础镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 将当前项目代码复制到容器中
COPY . /app

# 安装必要的依赖 (请确保你在根目录建了 requirements.txt)
RUN pip install --no-cache-dir -r requirements.txt

# 设置环境变量，确保 Python 输出直接打印到终端，不被缓冲
ENV PYTHONUNBUFFERED=1

# 默认运行命令
CMD ["python", "main.py"]