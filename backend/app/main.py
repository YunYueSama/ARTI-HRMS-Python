"""
HRMS Python 后端主入口（main.py）

说明：创建 FastAPI 应用实例，注册所有路由、中间件和事件处理器。
     这是整个后端应用的启动入口，类似 Spring Boot 的 Application 类。

启动方式：
    开发环境：uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    生产环境：uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

架构说明：
    FastAPI 应用的初始化流程：
    1. 创建 FastAPI 实例（配置标题、描述、版本）
    2. 注册生命周期事件（启动时初始化资源，关闭时释放资源）
    3. 注册中间件（CORS、请求日志等）
    4. 注册全局异常处理器
    5. 挂载路由（各业务模块的 API 端点）
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import close_engines, init_engines
from app.core.exceptions import register_exception_handlers
from app.routers.agent_tasks import router as agent_task_router
from app.routers.ai_chat import router as ai_chat_router
from app.routers.approval_rule_types import router as approval_rule_type_router
from app.routers.approval_rules import router as approval_rule_router
from app.routers.attendance import router as attendance_router
from app.routers.auth import router as auth_router
from app.routers.config import router as config_router
from app.routers.departments import router as department_router
from app.routers.dept_permission_templates import router as dept_permission_template_router
from app.routers.employees import router as employee_router
from app.routers.job_positions import router as job_position_router
from app.routers.knowledge_graph import router as knowledge_graph_router
from app.routers.leave_requests import router as leave_request_router
from app.routers.module_scope_rules import router as module_scope_rule_router
from app.routers.multimodal import router as multimodal_router
from app.routers.nlp import router as nlp_router
from app.routers.observability import router as observability_router
from app.routers.permissions import router as permission_router
from app.routers.persona import router as persona_router
from app.routers.rag import router as rag_router
from app.routers.reports import router as report_router
from app.routers.role_permissions import router as role_permission_router
from app.routers.roles import router as role_router
from app.routers.salary_configs import router as salary_config_router
from app.routers.salary_records import router as salary_record_router
from app.routers.users import router as user_router

# 配置日志
logging.basicConfig(
    level=logging.DEBUG if settings.APP_DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================
# 应用生命周期管理（Lifespan）
#
# 说明：使用 asynccontextmanager 定义应用的启动和关闭逻辑。
#      类似 Spring 的 @PostConstruct 和 @PreDestroy。
#
# 启动时（yield 之前）：
#   - 初始化数据库连接池
#   - 初始化 Redis 连接
#   - 初始化 Langfuse 客户端
#   - 打印启动信息
#
# 关闭时（yield 之后）：
#   - 关闭数据库连接池
#   - 关闭 Redis 连接
#   - 释放其他资源
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    应用生命周期上下文管理器

    说明：FastAPI 推荐使用 lifespan 替代旧版的 on_event("startup")/on_event("shutdown")。
         yield 之前的代码在应用启动时执行，yield 之后的代码在应用关闭时执行。
    """
    # ===== 启动阶段 =====
    logger.info("=" * 60)
    logger.info("HRMS Python 后端启动中...")
    logger.info(f"  环境: {settings.APP_ENV}")
    logger.info(f"  调试模式: {settings.APP_DEBUG}")
    logger.info(f"  监听地址: {settings.APP_HOST}:{settings.APP_PORT}")
    logger.info(f"  PostgreSQL: {settings.PGVECTOR_HOST}:{settings.PGVECTOR_PORT}/{settings.PGVECTOR_DATABASE}")
    logger.info(f"  Redis: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
    logger.info(f"  主 LLM: {settings.LLM_PRIMARY_PROVIDER} ({settings.LLM_PRIMARY_MODEL})")
    logger.info("=" * 60)

    # 初始化数据库连接池
    init_engines()
    logger.info("  数据库连接池已初始化")

    # 自动构建知识图谱（首次启动时从 MySQL 拉取数据填充图）
    # 即使失败也不应该阻断启动；用户可以稍后通过 /api/graph/sync 手动触发
    try:
        from app.ai.graph_rag.knowledge_graph import hr_knowledge_graph
        from app.core.database import MySQLSessionFactory

        if MySQLSessionFactory is not None:
            async with MySQLSessionFactory() as session:
                stats = await hr_knowledge_graph.build_from_database(session)
                await session.commit()
                logger.info(f"  知识图谱已自动构建: 节点={stats['nodes']}, 边={stats['edges']}")
    except Exception as e:
        logger.warning(f"  知识图谱自动构建失败（可在登录后手动同步）: {e}")

    # TODO: 初始化 Redis 连接
    # TODO: 初始化 Langfuse 客户端

    yield  # 应用运行中...

    # ===== 关闭阶段 =====
    logger.info("HRMS Python 后端关闭中...")
    await close_engines()
    logger.info("  数据库连接池已关闭")
    # TODO: 关闭 Redis 连接
    logger.info("所有资源已释放，应用已关闭")


# ============================================================
# 创建 FastAPI 应用实例
#
# 参数说明：
# - title: API 文档标题（显示在 Swagger UI 顶部）
# - description: API 文档描述
# - version: API 版本号
# - lifespan: 生命周期管理器
# - docs_url: Swagger UI 地址（访问 /docs 查看交互式 API 文档）
# - redoc_url: ReDoc 地址（访问 /redoc 查看另一种风格的文档）
# ============================================================
app = FastAPI(
    title="HRMS 人力资源管理系统 API",
    description=(
        "基于 FastAPI + LangChain/LangGraph 的智能人力资源管理系统后端。\n\n"
        "功能模块：\n"
        "- 员工管理、部门管理、职位管理\n"
        "- 考勤管理、请假管理、薪资管理\n"
        "- 角色权限管理（四层权限模型）\n"
        "- AI 聊天助手（亚托莉）\n"
        "- Agent 任务引擎（LangGraph）\n"
        "- RAG 文档知识库\n"
        "- GraphRAG 知识图谱\n"
        "- 多模态交互（语音/视觉）\n"
        "- LLM 可观测性（Langfuse）"
    ),
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    redirect_slashes=False,  # 禁用尾部斜杠重定向
)


# ============================================================
# 注册 CORS 中间件
#
# 说明：CORS（跨域资源共享）允许前端应用从不同域名访问后端 API。
#      开发环境中前端通常运行在 localhost:3000 或 localhost:5173，
#      而后端运行在 localhost:8000，属于跨域请求。
#
# 类似 Spring 的 WebMvcConfigurer.addCorsMappings() 或 @CrossOrigin
# ============================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,  # 允许的前端域名列表
    allow_credentials=True,  # 允许携带 Cookie
    allow_methods=["*"],  # 允许所有 HTTP 方法
    allow_headers=["*"],  # 允许所有请求头
)


# ============================================================
# 注册全局异常处理器
#
# 说明：将自定义异常处理器注册到 FastAPI 应用，
#      确保所有异常都返回统一的 JSON 格式响应。
# ============================================================
register_exception_handlers(app)


# ============================================================
# 健康检查端点
#
# 说明：用于 Docker 健康检查和负载均衡器探活。
#      返回简单的 JSON 表示服务正常运行。
# ============================================================
@app.get("/health", tags=["系统"])
async def health_check():
    """
    健康检查端点

    返回服务运行状态，用于：
    - Docker HEALTHCHECK 指令
    - Kubernetes liveness/readiness probe
    - 负载均衡器健康探测
    """
    return {
        "status": "healthy",
        "service": "hrms-backend",
        "version": "2.0.0",
    }


# ============================================================
# 路由注册（按模块分组）
#
# 说明：每个业务模块有独立的 Router 文件，在此统一挂载。
#      prefix 定义 URL 前缀，tags 用于 Swagger UI 分组显示。
#      类似 Spring 的 @RequestMapping 类级别路径前缀。
#
# 注意：以下路由将在后续模块实现后逐步取消注释
# ============================================================

# --- 认证模块 ---
app.include_router(auth_router, prefix="/api/auth", tags=["认证"])

# --- HR 业务模块 ---
app.include_router(employee_router, prefix="/api/employees", tags=["员工管理"])
app.include_router(department_router, prefix="/api/departments", tags=["部门管理"])
app.include_router(job_position_router, prefix="/api/positions", tags=["职位管理"])
app.include_router(attendance_router, prefix="/api/attendance", tags=["考勤管理"])
app.include_router(leave_request_router, prefix="/api/leave-requests", tags=["请假管理"])
app.include_router(salary_config_router, prefix="/api/salary-configs", tags=["薪资配置"])
app.include_router(salary_record_router, prefix="/api/salary-records", tags=["薪资记录"])

# --- 用户和权限模块 ---
app.include_router(user_router, prefix="/api/users", tags=["用户管理"])
app.include_router(role_router, prefix="/api/roles", tags=["角色管理"])
app.include_router(permission_router, prefix="/api/permissions", tags=["权限管理"])
app.include_router(role_permission_router, prefix="/api/role-permissions", tags=["角色权限"])
app.include_router(module_scope_rule_router, prefix="/api/module-scope-rules", tags=["模块范围规则"])
app.include_router(approval_rule_router, prefix="/api/approval-rules", tags=["审批规则"])
app.include_router(approval_rule_type_router, prefix="/api/approval-rule-types", tags=["审批规则类型"])
app.include_router(dept_permission_template_router, prefix="/api/dept-permission-templates", tags=["部门权限模板"])

# --- 报表模块 ---
app.include_router(report_router, prefix="/api/report", tags=["报表统计"])

# --- AI 模块 ---
app.include_router(ai_chat_router, prefix="/api/ai", tags=["AI 聊天"])
app.include_router(agent_task_router, prefix="/api/agent/tasks", tags=["Agent 任务"])
app.include_router(rag_router, prefix="/api/rag", tags=["RAG 知识库"])
app.include_router(knowledge_graph_router, prefix="/api/graph", tags=["知识图谱"])
app.include_router(multimodal_router, prefix="/api/multimodal", tags=["多模态"])
app.include_router(observability_router, prefix="/api/traces", tags=["可观测性"])

# --- 配置模块 ---
app.include_router(config_router, prefix="/api/config", tags=["模型配置"])
app.include_router(persona_router, prefix="/api/ai", tags=["人设配置"])

# --- NLP 模块 ---
app.include_router(nlp_router, prefix="/api/nlp", tags=["NLP 文本分析"])
