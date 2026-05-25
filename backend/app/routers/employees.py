"""
员工管理路由（routers/employees.py）

说明：定义员工模块的 API 端点，包括分页查询、详情、创建、更新、删除。
     对应 Java 的 EmployeeController 类。

端点列表：
    GET    /                → 分页查询员工列表
    GET    /{emp_id}        → 获取员工详情
    POST   /                → 创建员工
    PUT    /{emp_id}        → 更新员工
    DELETE /{emp_id}        → 删除员工
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_mysql_session
from app.core.dependencies import TokenPayload, get_current_user, require_permission
from app.schemas.common import ApiResponse, ok
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeQuery,
    EmployeeResponse,
    EmployeeUpdate,
)
from app.schemas.common import PageResponse
from app.services import employee_service

router = APIRouter()


@router.get("", summary="分页查询员工列表")
async def list_employees(
    page: int = Query(default=1, ge=1, description="页码"),
    size: int = Query(default=10, ge=1, le=500, description="每页大小"),
    keyword: str | None = Query(default=None, description="搜索关键词"),
    dept_id: int | None = Query(default=None, description="部门ID筛选"),
    status: str | None = Query(default=None, description="状态筛选"),
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_mysql_session),
):
    """分页查询员工列表，支持关键词搜索、部门和状态筛选"""
    query = EmployeeQuery(page=page, size=size, keyword=keyword, dept_id=dept_id, status=status)
    result = await employee_service.list_employees(query, db)
    return ok(data=result)


@router.get("/{emp_id}", summary="获取员工详情")
async def get_employee(
    emp_id: int,
    current_user: TokenPayload = Depends(require_permission("base:employee:view")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[EmployeeResponse]:
    """根据ID获取员工详情"""
    result = await employee_service.get_employee(emp_id, db)
    return ok(data=result)


@router.post("", summary="创建员工")
async def create_employee(
    data: EmployeeCreate,
    current_user: TokenPayload = Depends(require_permission("base:employee:add")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[EmployeeResponse]:
    """创建新员工"""
    result = await employee_service.create_employee(data, db)
    return ok(data=result, message="创建成功")


@router.put("/{emp_id}", summary="更新员工")
async def update_employee(
    emp_id: int,
    data: EmployeeUpdate,
    current_user: TokenPayload = Depends(require_permission("base:employee:edit")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[EmployeeResponse]:
    """更新员工信息（部分更新）"""
    result = await employee_service.update_employee(emp_id, data, db)
    return ok(data=result, message="更新成功")


@router.delete("/{emp_id}", summary="删除员工")
async def delete_employee(
    emp_id: int,
    current_user: TokenPayload = Depends(require_permission("base:employee:delete")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[None]:
    """删除员工"""
    await employee_service.delete_employee(emp_id, db)
    return ok(message="删除成功")
