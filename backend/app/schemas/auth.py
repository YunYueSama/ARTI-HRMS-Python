"""
认证相关 Schema（schemas/auth.py）

说明：定义认证模块的请求/响应模型，包括登录、密码管理、用户信息等。

Java 对应关系：
    LoginRequest         → LoginRequest
    LoginResponse        → LoginResponse
    UserProfile          → UserProfile
    ChangePasswordRequest → ChangePasswordRequest
    ResetPasswordRequest → ResetPasswordRequest
    PasswordCheckRequest → PasswordCheckRequest
    PasswordStrengthResponse → PasswordStrengthResponse
    UserView             → UserView
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# ============================================================
# 登录相关
# ============================================================


class LoginRequest(BaseModel):
    """登录请求模型"""

    username: str = Field(min_length=1, description="用户名")
    password: str = Field(min_length=1, description="密码")


class UserProfile(BaseModel):
    """用户档案信息（登录后返回的用户详情）"""

    user_id: int = Field(description="用户ID")
    username: str = Field(description="用户名")
    emp_id: int | None = Field(default=None, description="关联员工ID")
    emp_name: str | None = Field(default=None, description="员工姓名")
    dept_id: int | None = Field(default=None, description="部门ID")
    dept_name: str | None = Field(default=None, description="部门名称")
    position_id: int | None = Field(default=None, description="职位ID")
    position_name: str | None = Field(default=None, description="职位名称")
    role_id: int | None = Field(default=None, description="角色ID")
    role_name: str | None = Field(default=None, description="角色名称")
    role_code: str | None = Field(default=None, description="角色编码")
    identity_tag: str | None = Field(default=None, description="身份标签")
    status: str | None = Field(default=None, description="账号状态")
    permissions: list[str] = Field(default_factory=list, description="权限码列表")
    approval_assignee_tags: list[str] = Field(default_factory=list, description="审批指派标签列表")


class LoginResponse(BaseModel):
    """登录响应模型"""

    token: str = Field(description="JWT 访问令牌")
    user: UserProfile = Field(description="用户档案信息")


# ============================================================
# 密码管理相关
# ============================================================


class ChangePasswordRequest(BaseModel):
    """修改密码请求模型"""

    user_id: int = Field(description="用户ID")
    old_password: str = Field(min_length=1, description="旧密码")
    new_password: str = Field(min_length=6, description="新密码（至少6位）")
    confirm_password: str = Field(min_length=6, description="确认密码")


class ResetPasswordRequest(BaseModel):
    """重置密码请求模型（管理员操作）"""

    user_id: int = Field(description="用户ID")
    new_password: str = Field(min_length=6, description="新密码（至少6位）")


class PasswordCheckRequest(BaseModel):
    """密码强度检测请求模型"""

    password: str = Field(description="待检测的密码")


class PasswordStrengthResponse(BaseModel):
    """密码强度检测响应模型"""

    strength: str = Field(description="强度等级描述（弱/中/强）")
    level: int = Field(description="强度等级数值（1-4）")
    is_weak: bool = Field(description="是否为弱密码")
    suggestions: list[str] = Field(default_factory=list, description="改进建议列表")


# ============================================================
# 用户视图（管理列表用）
# ============================================================


class UserView(BaseModel):
    """用户列表视图模型（用于管理后台用户列表展示）"""

    model_config = ConfigDict(from_attributes=True)

    user_id: int = Field(description="用户ID")
    username: str | None = Field(default=None, description="用户名")
    emp_id: int | None = Field(default=None, description="关联员工ID")
    emp_name: str | None = Field(default=None, description="员工姓名")
    role_id: int | None = Field(default=None, description="角色ID")
    role_name: str | None = Field(default=None, description="角色名称")
    status: str | None = Field(default=None, description="账号状态")
    last_login: datetime | None = Field(default=None, description="最后登录时间")
    create_time: datetime | None = Field(default=None, description="创建时间")
