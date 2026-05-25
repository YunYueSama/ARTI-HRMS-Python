"""
数据模型单元测试（tests/unit/test_models.py）

说明：测试 ORM 模型的基本 CRUD 操作，验证字段约束和类型。
"""

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.department import Department
from app.models.employee import Employee
from app.models.role import Role
from app.models.sys_user import SysUser


class TestSysUser:
    """系统用户模型测试"""

    @pytest_asyncio.fixture
    async def seed_data(self, db_session: AsyncSession):
        """准备测试数据：部门 → 员工 → 角色"""
        dept = Department(dept_name="测试部门")
        db_session.add(dept)
        await db_session.flush()

        emp = Employee(emp_name="张三", gender="男", dept_id=dept.dept_id, status="在职")
        db_session.add(emp)
        await db_session.flush()

        role = Role(role_name="管理员", role_code="admin")
        db_session.add(role)
        await db_session.flush()

        return {"dept": dept, "emp": emp, "role": role}

    async def test_create_user(self, db_session: AsyncSession, seed_data):
        """创建用户：验证 username/password/status NOT NULL 约束"""
        user = SysUser(
            username="testuser",
            password=hash_password("123456"),
            emp_id=seed_data["emp"].emp_id,
            role_id=seed_data["role"].role_id,
            status="启用",
        )
        db_session.add(user)
        await db_session.flush()

        assert user.user_id is not None
        assert user.username == "testuser"
        assert user.status == "启用"

    async def test_query_user_by_username(self, db_session: AsyncSession, seed_data):
        """按用户名查询用户"""
        user = SysUser(
            username="queryuser",
            password=hash_password("pass"),
            emp_id=seed_data["emp"].emp_id,
            role_id=seed_data["role"].role_id,
            status="启用",
        )
        db_session.add(user)
        await db_session.flush()

        stmt = select(SysUser).where(SysUser.username == "queryuser")
        result = await db_session.execute(stmt)
        found = result.scalar_one_or_none()

        assert found is not None
        assert found.username == "queryuser"

    async def test_user_without_optional_fields(self, db_session: AsyncSession):
        """创建用户：emp_id 和 role_id 可选"""
        user = SysUser(
            username="minimal",
            password=hash_password("pass"),
            status="启用",
        )
        db_session.add(user)
        await db_session.flush()

        assert user.user_id is not None
        assert user.emp_id is None
        assert user.role_id is None


class TestDepartment:
    """部门模型测试"""

    async def test_create_department(self, db_session: AsyncSession):
        dept = Department(dept_name="研发部", dept_desc="技术研发部门")
        db_session.add(dept)
        await db_session.flush()

        assert dept.dept_id is not None
        assert dept.dept_name == "研发部"

    async def test_department_optional_fields(self, db_session: AsyncSession):
        dept = Department(dept_name="市场部")
        db_session.add(dept)
        await db_session.flush()

        assert dept.dept_desc is None
        assert dept.parent_id is None


class TestEmployee:
    """员工模型测试"""

    async def test_create_employee(self, db_session: AsyncSession):
        emp = Employee(
            emp_name="李四",
            gender="女",
            phone="13800138000",
            email="lisi@test.com",
            status="在职",
        )
        db_session.add(emp)
        await db_session.flush()

        assert emp.emp_id is not None
        assert emp.emp_name == "李四"
        assert emp.phone == "13800138000"


class TestRole:
    """角色模型测试"""

    async def test_create_role(self, db_session: AsyncSession):
        role = Role(role_name="普通员工", role_code="employee", role_desc="基本操作权限")
        db_session.add(role)
        await db_session.flush()

        assert role.role_id is not None
        assert role.role_code == "employee"
