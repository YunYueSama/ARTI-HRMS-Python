"""
角色管理路由（routers/roles.py）

说明：定义角色模块的 API 端点。
     对应 Java 的 RoleController 类。

端点列表：
    GET    /            → 分页查询角色列表
    GET    /{role_id}   → 获取角色详情
    POST   /            → 创建角色
    PUT    /{role_id}   → 更新角色
    DELETE /{role_id}   → 删除角色
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_mysql_session
from app.core.dependencies import TokenPayload, require_permission
from app.schemas.common import ApiResponse, PageResponse, ok
from app.schemas.permission import RoleCreate, RoleResponse, RoleUpdate
from app.services import permission_service

router = APIRouter()


@router.get("", summary="分页查询角色列表")
async def list_roles(
    page: int = Query(default=1, ge=1, description="页码"),
    size: int = Query(default=10, ge=1, le=500, description="每页大小"),
    keyword: str | None = Query(default=None, description="搜索关键词"),
    current_user: TokenPayload = Depends(require_permission("permission:role:view")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[PageResponse[RoleResponse]]:
    """分页查询角色列表，支持关键词搜索"""
    result = await permission_service.list_roles(page, size, keyword, db)
    return ok(data=result)


@router.get("/{role_id}", summary="获取角色详情")
async def get_role(
    role_id: int,
    current_user: TokenPayload = Depends(require_permission("permission:role:view")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[RoleResponse]:
    """根据ID获取角色详情"""
    result = await permission_service.get_role(role_id, db)
    return ok(data=result)


@router.post("", summary="创建角色")
async def create_role(
    data: RoleCreate,
    current_user: TokenPayload = Depends(require_permission("permission:role:add")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[RoleResponse]:
    """创建新角色"""
    result = await permission_service.create_role(data, db)
    return ok(data=result, message="创建成功")


@router.put("/{role_id}", summary="更新角色")
async def update_role(
    role_id: int,
    data: RoleUpdate,
    current_user: TokenPayload = Depends(require_permission("permission:role:edit")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[RoleResponse]:
    """更新角色信息"""
    result = await permission_service.update_role(role_id, data, db)
    return ok(data=result, message="更新成功")


@router.delete("/{role_id}", summary="删除角色")
async def delete_role(
    role_id: int,
    current_user: TokenPayload = Depends(require_permission("permission:role:delete")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[None]:
    """删除角色"""
    await permission_service.delete_role(role_id, db)
    return ok(message="删除成功")
