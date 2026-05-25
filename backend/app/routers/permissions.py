"""
权限管理路由（routers/permissions.py）

说明：定义权限模块的 API 端点（只读，用于前端权限树展示）。
     对应 Java 的 PermissionController 中的列表查询功能。

端点列表：
    GET /  → 获取所有权限列表（树形结构数据）
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_mysql_session
from app.core.dependencies import TokenPayload, require_permission
from app.schemas.common import ApiResponse, ok
from app.schemas.permission import PermissionResponse
from app.services import permission_service

router = APIRouter()


@router.get("/all", summary="获取所有权限列表")
async def list_permissions(
    current_user: TokenPayload = Depends(require_permission("permission:role:view")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[list[PermissionResponse]]:
    """
    获取所有权限列表

    说明：返回按 sort_order 排序的完整权限列表，前端根据 parent_id 构建树形结构。
    """
    result = await permission_service.list_all_permissions(db)
    return ok(data=result)
