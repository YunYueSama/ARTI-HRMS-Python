# ============================================================
# ATRI-HRMS Python 后端 Dockerfile
# 基础镜像：python:3.11-slim（Debian 精简版）
# ============================================================

FROM python:3.11-slim

# 安装系统依赖（PostgreSQL 客户端库、健康检查工具）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 先复制依赖文件，利用 Docker 缓存层
COPY pyproject.toml ./

# 安装项目依赖（先单独装 whisper 避免构建隔离问题）
RUN pip install --no-cache-dir --upgrade pip "setuptools<70" wheel \
    && pip install --no-cache-dir --no-build-isolation "openai-whisper==20240930" \
    && pip install --no-cache-dir .

# 复制应用代码
COPY . /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_ENV=production

# 暴露应用端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
