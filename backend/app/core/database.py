"""
数据库连接模块（core/database.py）

说明：项目已统一到 PostgreSQL 单库架构。
     原本设计的两个独立数据库（MySQL 业务库 + PG 向量库）合并到同一个 PG 实例：
       - 业务表：employee、department、salary_record、ai_chat_message、agent_task 等
       - 向量表：rag_document、rag_chunk（依赖 pgvector 扩展）
       - 追踪表：llm_trace（持久化 LLM 调用监控）

为什么从双库改为单库：
    1. pgvector 必须用 PostgreSQL，本来就要装一份 PG
    2. PG 的 JSONB / 数组 / 窗口函数比 MySQL 强，更适合 trace、agent 计划等半结构化数据
    3. 一个数据库进程 → 运维成本减半，备份/迁移更简单
    4. 兼容性：保留 get_mysql_session 名称作为别名，避免大规模改 router 代码

核心概念：
- Engine（引擎）：管理数据库连接池，类似 Spring 的 DataSource
- Session（会话）：一次数据库交互的上下文
- 连接池：预先创建一组数据库连接，避免每次请求都新建连接
- 异步：使用 asyncio 实现非阻塞 I/O，一个线程可处理多个并发请求

用法：
    from app.core.database import get_session, get_mysql_session, get_pgvector_session

    @router.get("/employees")
    async def list_employees(db: AsyncSession = Depends(get_session)):
        result = await db.execute(select(Employee))
        return result.scalars().all()
"""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from typing import AsyncGenerator, Optional

from app.core.config import settings


# ============================================================
# ORM 基类
# ============================================================
class Base(DeclarativeBase):
    """SQLAlchemy ORM 声明式基类，所有模型继承此类"""
    pass


# pgvector 模型也使用同一个 Base，存到同一个 PG 数据库
PgVectorBase = Base


# ============================================================
# 数据库引擎和会话工厂（延迟初始化）
# 说明：项目已统一到 PostgreSQL，所有数据共享一个引擎和会话工厂。
#      为了向后兼容，仍然导出 mysql_engine / MySQLSessionFactory 名称，
#      但它们指向的是同一个 PG 实例。
# ============================================================
pg_engine: Optional[AsyncEngine] = None
SessionFactory: Optional[async_sessionmaker[AsyncSession]] = None

# 兼容别名（旧代码用的 mysql_engine / pgvector_engine 都指向同一个 PG 引擎）
mysql_engine: Optional[AsyncEngine] = None
pgvector_engine: Optional[AsyncEngine] = None
MySQLSessionFactory: Optional[async_sessionmaker[AsyncSession]] = None
PgVectorSessionFactory: Optional[async_sessionmaker[AsyncSession]] = None


def init_engines() -> None:
    """
    初始化数据库引擎和会话工厂

    说明：在应用启动时（lifespan）调用此函数创建连接池。

    引擎参数说明：
    - pool_size=10: 连接池中保持的连接数
    - max_overflow=20: 超出 pool_size 时允许额外创建的连接数
    - pool_recycle=3600: 连接最大存活时间（秒），防止超时断开
    - echo: 是否打印 SQL 语句到控制台（调试用）
    """
    global pg_engine, SessionFactory
    global mysql_engine, pgvector_engine, MySQLSessionFactory, PgVectorSessionFactory

    # 创建唯一的 PostgreSQL 异步引擎（业务数据 + 向量数据 + 追踪数据共用）
    pg_engine = create_async_engine(
        settings.pgvector_url,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,
        echo=settings.APP_DEBUG,
    )

    # 创建会话工厂
    # expire_on_commit=False: 提交后对象属性仍可访问（避免 lazy loading 问题）
    SessionFactory = async_sessionmaker(
        bind=pg_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # 兼容别名：旧代码引用 mysql_engine / pgvector_engine 都指向同一个 PG
    mysql_engine = pg_engine
    pgvector_engine = pg_engine
    MySQLSessionFactory = SessionFactory
    PgVectorSessionFactory = SessionFactory


async def close_engines() -> None:
    """
    关闭数据库引擎，释放连接池资源

    说明：在应用关闭时（lifespan）调用此函数。
    """
    global pg_engine, mysql_engine, pgvector_engine

    if pg_engine:
        await pg_engine.dispose()
        pg_engine = None
        mysql_engine = None
        pgvector_engine = None


# ============================================================
# 依赖注入：获取数据库会话
# ============================================================
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    获取 PostgreSQL 异步数据库会话（依赖注入用）

    使用方式：
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_session)):
            ...

    异常处理：
        - 业务逻辑正常完成 → 自动提交事务
        - 发生异常 → 自动回滚事务
        - 无论如何 → 关闭会话，归还连接到连接池
    """
    if SessionFactory is None:
        raise RuntimeError("数据库未初始化，请先调用 init_engines()")

    async with SessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# 向后兼容别名：旧代码用 get_mysql_session / get_pgvector_session 都映射到同一个会话
async def get_mysql_session() -> AsyncGenerator[AsyncSession, None]:
    """已废弃名称，保留为向后兼容。等价于 get_session。"""
    async for session in get_session():
        yield session


async def get_pgvector_session() -> AsyncGenerator[AsyncSession, None]:
    """已废弃名称，保留为向后兼容。等价于 get_session。"""
    async for session in get_session():
        yield session
