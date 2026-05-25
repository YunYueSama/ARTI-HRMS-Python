# ============================================================
# HRMS Python 后端 Dockerfile
# 说明：多阶段构建，减小最终镜像体积
# 基础镜像：python:3.11-slim（Debian 精简版）
# ============================================================

# ============================================================
# 阶段一：构建阶段（builder）
# 目的：安装所有 Python 依赖到虚拟环境中
# ============================================================
FROM python:3.11-slim AS builder

# 设置工作目录
WORKDIR /build

# 安装系统级构建依赖（编译某些 Python 包需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 创建虚拟环境（隔离依赖，方便复制到运行阶段）
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 先复制依赖文件，利用 Docker 缓存层加速构建
COPY pyproject.toml ./

# 安装项目依赖（不安装开发依赖）
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir .

# ============================================================
# 阶段二：运行阶段（runtime）
# 目的：仅包含运行时必需的文件，镜像更小更安全
# ============================================================
FROM python:3.11-slim AS runtime

# 安装运行时系统依赖（MySQL/PostgreSQL 客户端库、健康检查工具）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户（安全最佳实践，避免容器以 root 运行）
RUN groupadd -r hrms && useradd -r -g hrms -d /app -s /sbin/nologin hrms

# 设置工作目录
WORKDIR /app

# 从构建阶段复制已安装的 Python 虚拟环境
COPY --from=builder /opt/venv /opt/venv

# 设置环境变量：使用虚拟环境中的 Python
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_ENV=production

# 复制应用代码
COPY . /app

# 更改文件所有权为非 root 用户
RUN chown -R hrms:hrms /app

# 切换到非 root 用户运行
USER hrms

# 暴露应用端口
EXPOSE 8000

# 健康检查：每 30 秒检测一次 /health 端点
# 超时 10 秒，连续 3 次失败则标记为不健康
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 启动命令：使用 uvicorn 运行 FastAPI 应用
# --host 0.0.0.0 监听所有网络接口
# --port 8000 监听端口
# --workers 可通过环境变量 WEB_CONCURRENCY 控制
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
