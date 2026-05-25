"""
测试公共 fixtures（tests/conftest.py）

说明：提供异步数据库会话、测试客户端等共享 fixture。
     使用 SQLite 内存数据库替代 PostgreSQL 进行单元测试。
"""

import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool

from app.core.database import get_mysql_session

# 使用独立的 DeclarativeBase，只导入测试需要的模型
from app.models.department import Department
from app.models.employee import Employee
from app.models.role import Role
from app.models.sys_user import SysUser

# SQLite 内存数据库引擎（使用 StaticPool 保持连接）
test_engine = create_async_engine(
    "sqlite+aiosqlite://",
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionFactory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    """使用 session 级别的事件循环，避免异步测试冲突"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    """在测试会话开始前创建需要的表，结束后销毁"""
    from app.core.database import Base

    # 只创建测试用到的表（避免 JSONB 等 PG 专有类型）
    tables = [Department.__table__, Employee.__table__, Role.__table__, SysUser.__table__]
    async with test_engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=tables))
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: Base.metadata.drop_all(sync_conn, tables=tables))
    await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """每个测试用例独立的数据库会话（自动回滚）"""
    async with TestSessionFactory() as session:
        async with session.begin():
            yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """注入测试数据库会话的 HTTP 客户端"""
    from app.main import app

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_mysql_session] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
