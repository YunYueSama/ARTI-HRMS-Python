"""
薪资记录路由（routers/salary_records.py）

说明：定义薪资记录模块的 API 端点。
     对应 Java 的 SalaryRecordController 类。

端点列表：
    GET    /                → 分页查询薪资记录
    GET    /{salary_id}     → 获取薪资记录详情
    POST   /                → 创建薪资记录
    PUT    /{salary_id}     → 更新薪资记录
    DELETE /{salary_id}     → 删除薪资记录
"""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_mysql_session
from app.core.dependencies import TokenPayload, require_permission
from app.core.permissions import get_data_scope
from app.models.employee import Employee
from app.models.sys_user import SysUser
from app.schemas.common import ApiResponse, PageResponse, ok
from app.schemas.salary import (
    SalaryRecordCreate,
    SalaryRecordQuery,
    SalaryRecordResponse,
    SalaryRecordUpdate,
)
from app.services import salary_service

router = APIRouter()


@router.get("", summary="分页查询薪资记录")
async def list_salary_records(
    page: int = Query(default=1, ge=1, description="页码"),
    size: int = Query(default=10, ge=1, le=500, description="每页大小"),
    emp_id: int | None = Query(default=None, description="员工ID筛选"),
    status: str | None = Query(default=None, description="审批状态筛选"),
    month_start: date | None = Query(default=None, description="薪资月份起始"),
    month_end: date | None = Query(default=None, description="薪资月份截止"),
    current_user: TokenPayload = Depends(require_permission("salary:record:view")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[PageResponse[SalaryRecordResponse]]:
    """分页查询薪资记录，支持员工、状态和月份范围筛选（按数据范围过滤）"""
    # 获取当前用户的身份标签和部门信息
    identity_tag = None
    emp_id_for_scope = None
    dept_id = None
    user_stmt = select(SysUser).where(SysUser.user_id == current_user.user_id)
    user_result = await db.execute(user_stmt)
    sys_user = user_result.scalar_one_or_none()
    if sys_user and sys_user.emp_id:
        emp_stmt = select(Employee).where(Employee.emp_id == sys_user.emp_id)
        emp_result = await db.execute(emp_stmt)
        emp = emp_result.scalar_one_or_none()
        if emp:
            identity_tag = emp.identity_tag_code
            emp_id_for_scope = emp.emp_id
            dept_id = emp.dept_id

    # 查询数据范围
    scope = await get_data_scope(db, role_id=0, module_code="salary:record", identity_tag=identity_tag)

    query = SalaryRecordQuery(
        page=page,
        size=size,
        emp_id=emp_id,
        status=status,
        month_start=month_start,
        month_end=month_end,
    )
    result = await salary_service.list_salary_records(query, db, scope=scope, user_emp_id=emp_id_for_scope, user_dept_id=dept_id)
    return ok(data=result)


@router.get("/{salary_id}", summary="获取薪资记录详情")
async def get_salary_record(
    salary_id: int,
    current_user: TokenPayload = Depends(require_permission("salary:record:view")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[SalaryRecordResponse]:
    """根据ID获取薪资记录详情"""
    result = await salary_service.get_salary_record(salary_id, db)
    return ok(data=result)


@router.post("", summary="创建薪资记录")
async def create_salary_record(
    data: SalaryRecordCreate,
    current_user: TokenPayload = Depends(require_permission("salary:record:add")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[SalaryRecordResponse]:
    """创建薪资记录"""
    result = await salary_service.create_salary_record(data, db)
    return ok(data=result, message="创建成功")


@router.put("/{salary_id}", summary="更新薪资记录")
async def update_salary_record(
    salary_id: int,
    data: SalaryRecordUpdate,
    current_user: TokenPayload = Depends(require_permission("salary:record:edit")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[SalaryRecordResponse]:
    """更新薪资记录"""
    result = await salary_service.update_salary_record(salary_id, data, db)
    return ok(data=result, message="更新成功")


@router.delete("/{salary_id}", summary="删除薪资记录")
async def delete_salary_record(
    salary_id: int,
    current_user: TokenPayload = Depends(require_permission("salary:record:view")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[None]:
    """删除薪资记录"""
    await salary_service.delete_salary_record(salary_id, db)
    return ok(message="删除成功")
