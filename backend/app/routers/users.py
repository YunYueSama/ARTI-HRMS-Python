"""
用户管理路由（routers/users.py）

说明：定义用户管理模块的 API 端点。
     对应 Java 的 SysUserController 类。

端点列表：
    GET    /            → 分页查询用户列表
    GET    /{user_id}   → 获取用户详情
    POST   /            → 创建用户
    PUT    /{user_id}   → 更新用户
    DELETE /{user_id}   → 删除用户
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_mysql_session
from app.core.dependencies import TokenPayload, require_permission
from app.core.exceptions import NotFoundException
from app.models.sys_user import SysUser
from app.schemas.common import ApiResponse, PageResponse, ok
from app.schemas.user import UserCreateRequest, UserUpdateRequest, UserViewResponse

router = APIRouter()


@router.get("", summary="分页查询用户列表")
async def list_users(
    page: int = Query(default=1, ge=1, description="页码"),
    size: int = Query(default=10, ge=1, le=500, description="每页大小"),
    keyword: str | None = Query(default=None, description="搜索关键词"),
    role_id: int | None = Query(default=None, description="角色ID筛选"),
    status: str | None = Query(default=None, description="状态筛选"),
    current_user: TokenPayload = Depends(require_permission("permission:user:view")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[PageResponse[UserViewResponse]]:
    """分页查询用户列表，支持关键词、角色和状态筛选"""
    stmt = select(SysUser)
    count_stmt = select(func.count()).select_from(SysUser)

    if keyword:
        like_pattern = f"%{keyword.strip()}%"
        keyword_filter = SysUser.username.like(like_pattern)
        stmt = stmt.where(keyword_filter)
        count_stmt = count_stmt.where(keyword_filter)

    if role_id is not None:
        stmt = stmt.where(SysUser.role_id == role_id)
        count_stmt = count_stmt.where(SysUser.role_id == role_id)

    if status:
        stmt = stmt.where(SysUser.status == status)
        count_stmt = count_stmt.where(SysUser.status == status)

    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    stmt = stmt.offset((page - 1) * size).limit(size)
    result = await db.execute(stmt)
    users = result.scalars().all()

    page_data = PageResponse(
        items=[UserViewResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        size=size,
    )
    return ok(data=page_data)


@router.get("/{user_id}", summary="获取用户详情")
async def get_user(
    user_id: int,
    current_user: TokenPayload = Depends(require_permission("permission:user:view")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[UserViewResponse]:
    """根据ID获取用户详情（不含密码）"""
    result = await db.execute(select(SysUser).where(SysUser.user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundException(message="用户不存在", detail=f"user_id={user_id}")
    return ok(data=UserViewResponse.model_validate(user))


@router.post("", summary="创建用户")
async def create_user(
    data: UserCreateRequest,
    current_user: TokenPayload = Depends(require_permission("permission:user:add")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[UserViewResponse]:
    """创建新用户"""
    from app.core.security import hash_password

    now = datetime.now()
    user = SysUser(
        username=data.username,
        password=hash_password(data.password),
        emp_id=data.emp_id,
        role_id=data.role_id,
        status=data.status or "active",
        create_time=now,
        update_time=now,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return ok(data=UserViewResponse.model_validate(user), message="创建成功")


@router.put("/{user_id}", summary="更新用户")
async def update_user(
    user_id: int,
    data: UserUpdateRequest,
    current_user: TokenPayload = Depends(require_permission("permission:user:edit")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[UserViewResponse]:
    """更新用户信息"""
    result = await db.execute(select(SysUser).where(SysUser.user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundException(message="用户不存在", detail=f"user_id={user_id}")

    update_data = data.model_dump(exclude_unset=True)
    if "password" in update_data and update_data["password"]:
        from app.core.security import hash_password
        update_data["password"] = hash_password(update_data["password"])
    elif "password" in update_data:
        del update_data["password"]

    for field, value in update_data.items():
        setattr(user, field, value)
    user.update_time = datetime.now()

    await db.flush()
    await db.refresh(user)
    return ok(data=UserViewResponse.model_validate(user), message="更新成功")


@router.delete("/{user_id}", summary="删除用户")
async def delete_user(
    user_id: int,
    current_user: TokenPayload = Depends(require_permission("permission:user:view")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[None]:
    """删除用户"""
    result = await db.execute(select(SysUser).where(SysUser.user_id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundException(message="用户不存在", detail=f"user_id={user_id}")
    await db.delete(user)
    await db.flush()
    return ok(message="删除成功")
