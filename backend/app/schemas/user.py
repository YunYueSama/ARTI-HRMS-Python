"""
用户相关 Schema（schemas/user.py）

说明：定义用户管理模块的请求/响应模型。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserCreateRequest(BaseModel):
    """用户创建请求模型"""

    username: str = Field(min_length=1, description="用户名")
    password: str = Field(min_length=6, description="密码")
    emp_id: int | None = Field(default=None, description="关联员工ID")
    role_id: int | None = Field(default=None, description="角色ID")
    status: str | None = Field(default="active", description="账号状态")


class UserUpdateRequest(BaseModel):
    """用户更新请求模型（所有字段可选）"""

    username: str | None = Field(default=None, description="用户名")
    password: str | None = Field(default=None, description="密码（为空则不修改）")
    emp_id: int | None = Field(default=None, description="关联员工ID")
    role_id: int | None = Field(default=None, description="角色ID")
    status: str | None = Field(default=None, description="账号状态")


class UserViewResponse(BaseModel):
    """用户视图响应模型（不含密码，安全展示）"""

    model_config = ConfigDict(from_attributes=True)

    user_id: int = Field(description="用户ID")
    emp_id: int | None = Field(default=None, description="关联员工ID")
    username: str | None = Field(default=None, description="用户名")
    role_id: int | None = Field(default=None, description="角色ID")
    status: str | None = Field(default=None, description="账号状态")
    last_login: datetime | None = Field(default=None, description="最后登录时间")
    create_time: datetime | None = Field(default=None, description="创建时间")
    update_time: datetime | None = Field(default=None, description="更新时间")
