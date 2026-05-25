# ============================================================
# HRMS Python 后端 - Makefile
# 说明：常用操作命令集合，简化开发和部署流程
# 用法：make <target>
# 兼容：Linux / macOS
# ============================================================

.PHONY: install dev start stop build logs test lint migrate seed clean help

# 默认目标：显示帮助信息
.DEFAULT_GOAL := help

# ============================================================
# 变量定义
# ============================================================
PYTHON := python
PIP := pip
UVICORN := uvicorn
DOCKER := docker
COMPOSE := docker compose -f ../docker/docker-compose.yml
COMPOSE_DEV := $(COMPOSE) -f ../docker/docker-compose.dev.yml
APP_MODULE := app.main:app
IMAGE_NAME := hrms-backend
IMAGE_TAG := latest

# ============================================================
# 开发环境命令
# ============================================================

## install: 安装项目依赖（包含开发依赖）
install:
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install -e ".[dev]"

## dev: 启动开发服务器（热重载模式）
dev:
	$(UVICORN) $(APP_MODULE) --host 0.0.0.0 --port 8000 --reload

## start: 启动生产服务器
start:
	$(UVICORN) $(APP_MODULE) --host 0.0.0.0 --port 8000 --workers 4

## stop: 停止所有 Docker 服务
stop:
	$(COMPOSE) down

# ============================================================
# Docker 命令
# ============================================================

## build: 构建 Docker 镜像
build:
	$(DOCKER) build -t $(IMAGE_NAME):$(IMAGE_TAG) .

## up: 启动所有 Docker 服务（生产模式）
up:
	$(COMPOSE) up -d

## up-dev: 启动所有 Docker 服务（开发模式，热重载）
up-dev:
	$(COMPOSE_DEV) up -d

## down: 停止并移除所有 Docker 容器
down:
	$(COMPOSE) down

## logs: 查看所有服务日志（实时跟踪）
logs:
	$(COMPOSE) logs -f

## logs-backend: 仅查看后端服务日志
logs-backend:
	$(COMPOSE) logs -f backend

## ps: 查看所有服务运行状态
ps:
	$(COMPOSE) ps

# ============================================================
# 测试和代码质量
# ============================================================

## test: 运行所有测试
test:
	pytest tests/ -v --tb=short

## test-cov: 运行测试并生成覆盖率报告
test-cov:
	pytest tests/ -v --cov=app --cov-report=term-missing --cov-report=html

## lint: 运行代码检查（ruff 格式检查 + mypy 类型检查）
lint:
	ruff check app/ tests/
	ruff format --check app/ tests/
	mypy app/ --ignore-missing-imports

## format: 自动格式化代码
format:
	ruff check --fix app/ tests/
	ruff format app/ tests/

# ============================================================
# 数据库命令
# ============================================================

## migrate: 运行数据库迁移（Alembic）
migrate:
	alembic upgrade head

## migrate-new: 创建新的迁移文件（需要传入 MSG 参数）
## 用法：make migrate-new MSG="add_user_table"
migrate-new:
	alembic revision --autogenerate -m "$(MSG)"

## migrate-down: 回滚最近一次迁移
migrate-down:
	alembic downgrade -1

## seed: 初始化种子数据
seed:
	$(PYTHON) -m app.scripts.seed

# ============================================================
# 清理命令
# ============================================================

## clean: 清理临时文件和缓存
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

## clean-docker: 清理 Docker 数据卷（⚠️ 会删除所有数据）
clean-docker:
	$(COMPOSE) down -v

# ============================================================
# 帮助信息
# ============================================================

## help: 显示所有可用命令
help:
	@echo ""
	@echo "HRMS Python 后端 - 可用命令："
	@echo "============================================"
	@echo ""
	@echo "  开发环境："
	@echo "    make install       安装项目依赖（包含开发依赖）"
	@echo "    make dev           启动开发服务器（热重载）"
	@echo "    make start         启动生产服务器"
	@echo "    make stop          停止所有 Docker 服务"
	@echo ""
	@echo "  Docker："
	@echo "    make build         构建 Docker 镜像"
	@echo "    make up            启动所有服务（生产模式）"
	@echo "    make up-dev        启动所有服务（开发模式）"
	@echo "    make down          停止并移除所有容器"
	@echo "    make logs          查看所有服务日志"
	@echo "    make logs-backend  查看后端服务日志"
	@echo "    make ps            查看服务运行状态"
	@echo ""
	@echo "  测试和质量："
	@echo "    make test          运行所有测试"
	@echo "    make test-cov      运行测试（含覆盖率报告）"
	@echo "    make lint          代码检查（ruff + mypy）"
	@echo "    make format        自动格式化代码"
	@echo ""
	@echo "  数据库："
	@echo "    make migrate       运行数据库迁移"
	@echo "    make migrate-new   创建新迁移文件"
	@echo "    make migrate-down  回滚最近一次迁移"
	@echo "    make seed          初始化种子数据"
	@echo ""
	@echo "  清理："
	@echo "    make clean         清理临时文件和缓存"
	@echo "    make clean-docker  清理 Docker 数据卷（⚠️ 删除数据）"
	@echo ""
