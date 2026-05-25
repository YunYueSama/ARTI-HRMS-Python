"""
员工相关 Schema（schemas/employee.py）

说明：定义员工模块的请求/响应模型，包括创建、更新、查询和响应。
"""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class EmployeeCreate(BaseModel):
    """员工创建请求模型"""

    model_config = ConfigDict(extra="ignore")

    emp_name: str = Field(min_length=1, description="员工姓名")
    gender: Optional[str] = Field(default=None, description="性别")
    phone: Optional[str] = Field(default=None, description="手机号")
    email: Optional[str] = Field(default=None, description="邮箱")
    id_card: Optional[str] = Field(default=None, description="身份证号")
    birthday: Optional[date] = Field(default=None, description="出生日期")
    address: Optional[str] = Field(default=None, description="住址")
    hire_date: Optional[date] = Field(default=None, description="入职日期")
    dept_id: Optional[int] = Field(default=None, description="所属部门ID")
    position_id: Optional[int] = Field(default=None, description="职位ID")
    identity_tag_code: Optional[str] = Field(default=None, description="身份标签编码")
    status: Optional[str] = Field(default="在职", description="状态（在职/离职）")


class EmployeeUpdate(BaseModel):
    """员工更新请求模型（所有字段可选）"""

    model_config = ConfigDict(extra="ignore")

    emp_name: Optional[str] = Field(default=None, description="员工姓名")
    gender: Optional[str] = Field(default=None, description="性别")
    phone: Optional[str] = Field(default=None, description="手机号")
    email: Optional[str] = Field(default=None, description="邮箱")
    id_card: Optional[str] = Field(default=None, description="身份证号")
    birthday: Optional[date] = Field(default=None, description="出生日期")
    address: Optional[str] = Field(default=None, description="住址")
    hire_date: Optional[date] = Field(default=None, description="入职日期")
    leave_date: Optional[date] = Field(default=None, description="离职日期")
    dept_id: Optional[int] = Field(default=None, description="所属部门ID")
    position_id: Optional[int] = Field(default=None, description="职位ID")
    identity_tag_code: Optional[str] = Field(default=None, description="身份标签编码")
    status: Optional[str] = Field(default=None, description="状态（在职/离职）")


class EmployeeResponse(BaseModel):
    """员工响应模型（对应 ORM Employee 模型）"""

    model_config = ConfigDict(from_attributes=True)

    emp_id: int = Field(description="员工ID")
    emp_name: Optional[str] = Field(default=None, description="员工姓名")
    gender: Optional[str] = Field(default=None, description="性别")
    phone: Optional[str] = Field(default=None, description="手机号")
    email: Optional[str] = Field(default=None, description="邮箱")
    id_card: Optional[str] = Field(default=None, description="身份证号")
    birthday: Optional[date] = Field(default=None, description="出生日期")
    address: Optional[str] = Field(default=None, description="住址")
    hire_date: Optional[date] = Field(default=None, description="入职日期")
    leave_date: Optional[date] = Field(default=None, description="离职日期")
    dept_id: Optional[int] = Field(default=None, description="所属部门ID")
    position_id: Optional[int] = Field(default=None, description="职位ID")
    identity_tag_code: Optional[str] = Field(default=None, description="身份标签编码")
    status: Optional[str] = Field(default=None, description="状态")
    create_time: Optional[datetime] = Field(default=None, description="创建时间")
    update_time: Optional[datetime] = Field(default=None, description="更新时间")


class EmployeeQuery(BaseModel):
    """员工分页查询参数模型"""

    page: int = Field(default=1, ge=1, description="页码（从1开始）")
    size: int = Field(default=10, ge=1, le=500, description="每页大小")
    keyword: Optional[str] = Field(default=None, description="搜索关键词（姓名/手机号）")
    dept_id: Optional[int] = Field(default=None, description="部门ID筛选")
    status: Optional[str] = Field(default=None, description="状态筛选")
