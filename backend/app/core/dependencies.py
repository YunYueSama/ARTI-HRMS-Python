"""
依赖注入系统（core/dependencies.py）

说明：实现 FastAPI 的依赖注入机制，提供认证和权限检查功能。

FastAPI Depends vs Spring @Autowired 对比：
┌─────────────────────────────────────────────────────────────────────┐
│ Spring Boot                          │ FastAPI                       │
├─────────────────────────────────────────────────────────────────────┤
│ @Autowired UserService userService   │ Depends(get_current_user)     │
│ @PreAuthorize("hasRole('ADMIN')")    │ Depends(require_permission()) │
│ SecurityContextHolder.getContext()   │ Depends(get_current_user)     │
│ @Bean + @Configuration               │ 函数 + Depends()              │
│ 容器管理生命周期                      │ 请求级别生命周期              │
└─────────────────────────────────────────────────────────────────────┘

核心区别：
- Spring 的依赖注入是容器级别的（单例/原型），FastAPI 是请求级别的
- Spring 通过注解声明依赖，FastAPI 通过函数参数 + Depends() 声明
- FastAPI 的依赖可以是异步函数，天然支持 async/await

用法：
    from app.core.dependencies import get_current_user, require_permission

    @router.get("/employees")
    async def list_employees(
        user: TokenPayload = Depends(get_current_user)  # 需要登录
    ):
        ...

    @router.delete("/employees/{id}")
    async def delete_employee(
        user: TokenPayload = Depends(require_permission("employee:delete"))  # 需要特定权限
    ):
        ...
"""

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.core.exceptions import PermissionDeniedException, UnauthorizedException
from app.core.security import decode_access_token

# ============================================================
# HTTP Bearer Token 提取器
#
# 说明：从请求头 Authorization: Bearer <token> 中提取 JWT Token。
#      auto_error=False 表示缺少 Token 时不自动抛出 403，
#      而是返回 None，由我们自己处理错误逻辑。
# ============================================================
security_scheme = HTTPBearer(auto_error=False)


class TokenPayload(BaseModel):
    """
    JWT Token 解码后的载荷数据

    说明：从 JWT Token 中解码出的用户信息，在整个请求生命周期中使用。
         类似 Spring Security 的 Authentication 对象。

    字段：
        user_id: 用户 ID（sys_user 表主键）
        username: 用户名
        role_id: 角色 ID（关联 role 表）
        permissions: 用户拥有的权限码列表（从 role_permission 表查询）
    """

    user_id: int = Field(description="用户 ID")
    username: str = Field(description="用户名")
    role_id: int | None = Field(default=None, description="角色 ID")
    permissions: list[str] = Field(default_factory=list, description="权限码列表")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> TokenPayload:
    """
    获取当前登录用户信息（核心认证依赖）

    工作流程：
        1. 从 Authorization Header 提取 Bearer Token
        2. 解码 JWT Token，校验签名和有效期
        3. 提取 payload 中的用户信息
        4. 返回 TokenPayload 对象供后续使用

    异常：
        - Token 缺失 → 401 UnauthorizedException
        - Token 无效/过期 → 401 UnauthorizedException

    说明：
        这个依赖会被注入到所有需要认证的路由中。
        类似 Spring Security 的 SecurityContextHolder.getContext().getAuthentication()
    """
    # 检查是否提供了 Token
    if credentials is None:
        raise UnauthorizedException(message="未提供认证凭据，请先登录")

    # 解码 JWT Token
    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        raise UnauthorizedException(message="Token 无效或已过期，请重新登录")

    # 从 payload 中提取用户信息
    user_id = payload.get("user_id")
    username = payload.get("username")

    if user_id is None or username is None:
        raise UnauthorizedException(message="Token 载荷不完整")

    # 构建 TokenPayload 对象
    return TokenPayload(
        user_id=user_id,
        username=username,
        role_id=payload.get("role_id"),
        permissions=payload.get("permissions", []),
    )


def require_permission(*perm_codes: str):
    """
    权限检查依赖工厂（高阶函数）

    说明：返回一个依赖函数，检查当前用户是否拥有指定的权限码。
         类似 Spring Security 的 @PreAuthorize("hasAuthority('xxx')")。

    参数：
        *perm_codes: 需要的权限码（任一匹配即可通过）

    返回：
        一个 FastAPI 依赖函数

    用法：
        @router.delete("/employees/{id}")
        async def delete_employee(
            user: TokenPayload = Depends(require_permission("employee:delete", "employee:manage"))
        ):
            ...

    权限检查逻辑：
        - 用户拥有的权限列表存储在 JWT Token 的 permissions 字段中
        - 只要用户拥有 perm_codes 中的任意一个权限，即通过检查
        - 如果用户没有任何匹配的权限，抛出 403 PermissionDeniedException
    """

    async def permission_checker(
        current_user: TokenPayload = Depends(get_current_user),
    ) -> TokenPayload:
        """
        实际的权限检查逻辑

        说明：先通过 get_current_user 确保用户已认证，
             然后检查用户权限列表中是否包含所需权限码。
        """
        # 如果未指定权限码，仅要求登录即可
        if not perm_codes:
            return current_user

        # 检查用户是否拥有所需权限中的任意一个
        user_permissions = set(current_user.permissions)
        required_permissions = set(perm_codes)

        if not user_permissions.intersection(required_permissions):
            raise PermissionDeniedException(
                message="权限不足，无法执行此操作",
                detail=f"需要权限: {', '.join(perm_codes)}",
            )

        return current_user

    return permission_checker
