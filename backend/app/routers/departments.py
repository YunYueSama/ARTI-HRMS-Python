"""
部门管理路由（routers/departments.py）

说明：定义部门模块的 API 端点，包括分页查询、详情、创建、更新、删除。
     对应 Java 的 DepartmentController 类。

端点列表：
    GET    /                → 分页查询部门列表
    GET    /{dept_id}       → 获取部门详情
    POST   /                → 创建部门
    PUT    /{dept_id}       → 更新部门
    DELETE /{dept_id}       → 删除部门
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_mysql_session
from app.core.dependencies import TokenPayload, require_permission
from app.schemas.common import ApiResponse, PageResponse, ok
from app.schemas.department import DepartmentCreate, DepartmentResponse, DepartmentUpdate
from app.services import department_service

router = APIRouter()


@router.get("", summary="分页查询部门列表")
async def list_departments(
    page: int = Query(default=1, ge=1, description="页码"),
    size: int = Query(default=10, ge=1, le=500, description="每页大小"),
    keyword: str | None = Query(default=None, description="搜索关键词"),
    current_user: TokenPayload = Depends(require_permission("base:department:view")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[PageResponse[DepartmentResponse]]:
    """分页查询部门列表，支持关键词搜索"""
    result = await department_service.list_departments(page, size, keyword, db)
    return ok(data=result)


@router.get("/{dept_id}", summary="获取部门详情")
async def get_department(
    dept_id: int,
    current_user: TokenPayload = Depends(require_permission("base:department:view")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[DepartmentResponse]:
    """根据ID获取部门详情"""
    result = await department_service.get_department(dept_id, db)
    return ok(data=result)


@router.post("", summary="创建部门")
async def create_department(
    data: DepartmentCreate,
    current_user: TokenPayload = Depends(require_permission("base:department:add")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[DepartmentResponse]:
    """创建新部门"""
    result = await department_service.create_department(data, db)
    return ok(data=result, message="创建成功")


@router.put("/{dept_id}", summary="更新部门")
async def update_department(
    dept_id: int,
    data: DepartmentUpdate,
    current_user: TokenPayload = Depends(require_permission("base:department:edit")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[DepartmentResponse]:
    """更新部门信息"""
    result = await department_service.update_department(dept_id, data, db)
    return ok(data=result, message="更新成功")


@router.delete("/{dept_id}", summary="删除部门")
async def delete_department(
    dept_id: int,
    current_user: TokenPayload = Depends(require_permission("base:department:delete")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[None]:
    """删除部门（如有员工引用则拒绝）"""
    await department_service.delete_department(dept_id, db)
    return ok(message="删除成功")
