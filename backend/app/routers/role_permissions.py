"""
角色-权限关联路由（routers/role_permissions.py）

说明：定义角色-权限关联模块的 API 端点。
     对应 Java 的 RolePermissionController 类。

端点列表：
    GET /role/{role_id}/perm-ids  → 获取角色的权限ID列表
    PUT /role/{role_id}           → 替换角色的所有权限
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_mysql_session
from app.core.dependencies import TokenPayload, require_permission
from app.schemas.common import ApiResponse, ok
from app.schemas.permission import RolePermissionUpdateRequest
from app.services import permission_service

router = APIRouter()


@router.get("/role/{role_id}/perm-ids", summary="获取角色的权限ID列表")
async def list_perm_ids_by_role(
    role_id: int,
    current_user: TokenPayload = Depends(require_permission("permission:role:view")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[list[int]]:
    """获取指定角色关联的所有权限ID"""
    result = await permission_service.list_perm_ids_by_role(role_id, db)
    return ok(data=result)


@router.put("/role/{role_id}", summary="替换角色的所有权限")
async def replace_role_permissions(
    role_id: int,
    data: RolePermissionUpdateRequest,
    current_user: TokenPayload = Depends(require_permission("permission:role:edit")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[list[int]]:
    """
    替换角色的所有权限

    说明：先删除角色现有的所有权限关联，然后批量设置新的权限列表。
    """
    result = await permission_service.replace_role_permissions(role_id, data, db)
    return ok(data=result, message="权限更新成功")
