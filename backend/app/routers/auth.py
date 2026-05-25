"""
认证路由（routers/auth.py）

说明：定义认证模块的 API 端点，包括登录、获取用户档案、修改密码、重置密码、密码强度检测。
     对应 Java 的 AuthController 类。

端点列表：
    POST   /login              → 用户登录（无需认证）
    GET    /profile            → 获取当前用户档案（需要认证）
    POST   /change-password    → 修改密码（需要认证）
    POST   /reset-password     → 重置密码（需要认证 + 权限）
    POST   /check-password     → 检测密码强度（无需认证）
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_mysql_session
from app.core.dependencies import TokenPayload, get_current_user, require_permission
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    PasswordCheckRequest,
    PasswordStrengthResponse,
    ResetPasswordRequest,
    UserProfile,
)
from app.schemas.common import ApiResponse, ok
from app.services import auth_service

router = APIRouter()


@router.post("/login", summary="用户登录")
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[LoginResponse]:
    """
    用户登录接口

    说明：验证用户名和密码，返回 JWT Token 和用户档案信息。
         无需认证即可访问。

    请求体：
        username: 用户名
        password: 密码

    返回：
        LoginResponse（token + 用户档案）
    """
    result = await auth_service.login(request.username, request.password, db)
    return ok(data=result, message="登录成功")


@router.get("/profile", summary="获取当前用户档案")
async def profile(
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[UserProfile]:
    """
    获取当前登录用户的档案信息

    说明：根据 JWT Token 中的 user_id 查询完整的用户档案。
         需要认证（Bearer Token）。

    返回：
        UserProfile（用户详细信息，包含角色、权限、部门等）
    """
    result = await auth_service.get_profile(current_user.user_id, db)
    return ok(data=result)


@router.get("/profile/{user_id}", summary="根据用户ID获取档案")
async def profile_by_id(
    user_id: int,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[UserProfile]:
    """
    根据用户ID获取档案信息

    说明：前端通过 /auth/profile/{userId} 获取指定用户的档案。
         需要认证（Bearer Token）。
    """
    result = await auth_service.get_profile(user_id, db)
    return ok(data=result)


@router.post("/change-password", summary="修改密码")
async def change_password(
    request: ChangePasswordRequest,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[None]:
    """
    修改当前用户密码

    说明：验证旧密码后设置新密码。需要认证。

    请求体：
        user_id: 用户ID
        old_password: 旧密码
        new_password: 新密码
        confirm_password: 确认密码

    返回：
        成功提示
    """
    await auth_service.change_password(request, db)
    return ok(message="密码修改成功")


@router.post("/reset-password", summary="重置密码")
async def reset_password(
    request: ResetPasswordRequest,
    current_user: TokenPayload = Depends(require_permission("user:reset-password")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[None]:
    """
    重置用户密码（管理员操作）

    说明：管理员为指定用户重置密码，无需验证旧密码。
         需要认证 + user:reset-password 权限。

    请求体：
        user_id: 目标用户ID
        new_password: 新密码

    返回：
        成功提示
    """
    await auth_service.reset_password(request, db)
    return ok(message="密码重置成功")


@router.post("/check-password", summary="检测密码强度")
async def check_password_strength(
    request: PasswordCheckRequest,
) -> ApiResponse[PasswordStrengthResponse]:
    """
    检测密码强度

    说明：无需认证即可访问。用于前端实时显示密码强度指示器。

    请求体：
        password: 待检测的密码

    返回：
        PasswordStrengthResponse（强度等级、建议等）
    """
    result = auth_service.check_password_strength(request.password)
    return ok(data=result)
