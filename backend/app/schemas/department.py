"""
部门相关 Schema（schemas/department.py）

说明：定义部门模块的请求/响应模型，包括创建、更新和响应。
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DepartmentCreate(BaseModel):
    """部门创建请求模型"""

    model_config = ConfigDict(extra="ignore")

    dept_name: str = Field(min_length=1, description="部门名称")
    dept_desc: Optional[str] = Field(default=None, description="部门描述")
    parent_id: Optional[int] = Field(default=None, description="上级部门ID")


class DepartmentUpdate(BaseModel):
    """部门更新请求模型（所有字段可选）"""

    model_config = ConfigDict(extra="ignore")

    dept_name: Optional[str] = Field(default=None, description="部门名称")
    dept_desc: Optional[str] = Field(default=None, description="部门描述")
    parent_id: Optional[int] = Field(default=None, description="上级部门ID")


class DepartmentResponse(BaseModel):
    """部门响应模型（对应 ORM Department 模型）"""

    model_config = ConfigDict(from_attributes=True)

    dept_id: int = Field(description="部门ID")
    dept_name: Optional[str] = Field(default=None, description="部门名称")
    dept_desc: Optional[str] = Field(default=None, description="部门描述")
    parent_id: Optional[int] = Field(default=None, description="上级部门ID")
    create_time: Optional[datetime] = Field(default=None, description="创建时间")
    update_time: Optional[datetime] = Field(default=None, description="更新时间")
