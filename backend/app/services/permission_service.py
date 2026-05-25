"""
权限管理服务（services/permission_service.py）

说明：实现角色、权限和角色-权限关联的业务逻辑。
     对应 Java 的 RoleService、PermissionService、RolePermissionService 类。
"""

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.models.permission import Permission
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.schemas.common import PageResponse
from app.schemas.permission import (
    PermissionResponse,
    RoleCreate,
    RolePermissionUpdateRequest,
    RoleResponse,
    RoleUpdate,
)

# ============================================================
# 角色 CRUD
# ============================================================


async def list_roles(page: int, size: int, keyword: str | None, db: AsyncSession) -> PageResponse[RoleResponse]:
    """
    分页查询角色列表

    支持筛选条件：
        - keyword: 模糊匹配角色名称或角色编码
    """
    stmt = select(Role)
    count_stmt = select(func.count()).select_from(Role)

    if keyword:
        like_pattern = f"%{keyword.strip()}%"
        keyword_filter = or_(
            Role.role_name.like(like_pattern),
            Role.role_code.like(like_pattern),
        )
        stmt = stmt.where(keyword_filter)
        count_stmt = count_stmt.where(keyword_filter)

    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    stmt = stmt.offset((page - 1) * size).limit(size)
    result = await db.execute(stmt)
    roles = result.scalars().all()

    return PageResponse(
        items=[RoleResponse.model_validate(r) for r in roles],
        total=total,
        page=page,
        size=size,
    )


async def get_role(role_id: int, db: AsyncSession) -> RoleResponse:
    """根据ID获取角色"""
    result = await db.execute(select(Role).where(Role.role_id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        raise NotFoundException(message="角色不存在", detail=f"role_id={role_id}")
    return RoleResponse.model_validate(role)


async def create_role(data: RoleCreate, db: AsyncSession) -> RoleResponse:
    """创建角色"""
    role = Role(
        **data.model_dump(),
        create_time=datetime.now(),
    )
    db.add(role)
    await db.flush()
    await db.refresh(role)
    return RoleResponse.model_validate(role)


async def update_role(role_id: int, data: RoleUpdate, db: AsyncSession) -> RoleResponse:
    """更新角色（部分更新）"""
    result = await db.execute(select(Role).where(Role.role_id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        raise NotFoundException(message="角色不存在", detail=f"role_id={role_id}")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(role, field, value)

    await db.flush()
    await db.refresh(role)
    return RoleResponse.model_validate(role)


async def delete_role(role_id: int, db: AsyncSession) -> None:
    """删除角色"""
    result = await db.execute(select(Role).where(Role.role_id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        raise NotFoundException(message="角色不存在", detail=f"role_id={role_id}")
    await db.delete(role)
    await db.flush()


# ============================================================
# 权限查询（只读）
# ============================================================


async def list_all_permissions(db: AsyncSession) -> list[PermissionResponse]:
    """
    获取所有权限列表（树形结构用）

    说明：按 sort_order 和 perm_id 排序，前端自行构建树形结构。
    """
    result = await db.execute(select(Permission).order_by(Permission.sort_order.asc(), Permission.perm_id.asc()))
    permissions = result.scalars().all()
    return [PermissionResponse.model_validate(p) for p in permissions]


# ============================================================
# 角色-权限关联
# ============================================================


async def list_perm_ids_by_role(role_id: int, db: AsyncSession) -> list[int]:
    """获取角色关联的权限ID列表"""
    # 确认角色存在
    role_result = await db.execute(select(Role).where(Role.role_id == role_id))
    if not role_result.scalar_one_or_none():
        raise NotFoundException(message="角色不存在", detail=f"role_id={role_id}")

    result = await db.execute(
        select(RolePermission.perm_id).where(RolePermission.role_id == role_id).order_by(RolePermission.perm_id.asc())
    )
    return [x for x in result.scalars().all() if x is not None]


async def replace_role_permissions(role_id: int, data: RolePermissionUpdateRequest, db: AsyncSession) -> list[int]:
    """
    替换角色的所有权限（先删后增）

    说明：删除角色现有的所有权限关联，然后批量插入新的权限关联。
         对应 Java 的 RolePermissionService.replaceByRoleId()。
    """
    # 确认角色存在
    role_result = await db.execute(select(Role).where(Role.role_id == role_id))
    if not role_result.scalar_one_or_none():
        raise NotFoundException(message="角色不存在", detail=f"role_id={role_id}")

    # 删除现有关联
    existing = await db.execute(select(RolePermission).where(RolePermission.role_id == role_id))
    for rp in existing.scalars().all():
        await db.delete(rp)
    await db.flush()

    # 批量插入新关联（去重）
    unique_perm_ids: list[int] = []
    seen: set[int] = set()
    for perm_id in data.perm_ids:
        if perm_id not in seen:
            seen.add(perm_id)
            unique_perm_ids.append(perm_id)

    for perm_id in unique_perm_ids:
        rp = RolePermission(role_id=role_id, perm_id=perm_id)
        db.add(rp)

    await db.flush()
    return unique_perm_ids
