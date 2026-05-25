"""
权限与角色相关 Schema（schemas/permission.py）

说明：定义角色、权限、报表统计等模块的请求/响应模型。

Java 对应关系：
    RolePermissionUpdateRequest → RolePermissionUpdateRequest
    ReportSummary              → ReportSummary
    DepartmentStat             → DepartmentStat
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# 角色管理
# ============================================================


class RoleCreate(BaseModel):
    """角色创建请求模型"""

    model_config = ConfigDict(extra="ignore")

    role_name: str = Field(min_length=1, description="角色名称")
    role_code: str = Field(min_length=1, description="角色编码")
    role_desc: Optional[str] = Field(default=None, description="角色描述")


class RoleUpdate(BaseModel):
    """角色更新请求模型（所有字段可选）"""

    model_config = ConfigDict(extra="ignore")

    role_name: Optional[str] = Field(default=None, description="角色名称")
    role_code: Optional[str] = Field(default=None, description="角色编码")
    role_desc: Optional[str] = Field(default=None, description="角色描述")


class RoleResponse(BaseModel):
    """角色响应模型（对应 ORM Role 模型）"""

    model_config = ConfigDict(from_attributes=True)

    role_id: int = Field(description="角色ID")
    role_name: Optional[str] = Field(default=None, description="角色名称")
    role_code: Optional[str] = Field(default=None, description="角色编码")
    role_desc: Optional[str] = Field(default=None, description="角色描述")
    create_time: Optional[datetime] = Field(default=None, description="创建时间")


# ============================================================
# 权限管理
# ============================================================


class PermissionResponse(BaseModel):
    """权限响应模型（对应 ORM Permission 模型）"""

    model_config = ConfigDict(from_attributes=True)

    perm_id: int = Field(description="权限ID")
    perm_name: Optional[str] = Field(default=None, description="权限名称")
    perm_code: Optional[str] = Field(default=None, description="权限编码")
    perm_type: Optional[str] = Field(default=None, description="权限类型（menu/button）")
    parent_id: Optional[int] = Field(default=None, description="父级权限ID")
    path: Optional[str] = Field(default=None, description="前端路由路径")
    icon: Optional[str] = Field(default=None, description="图标名称")
    sort_order: Optional[int] = Field(default=None, description="排序序号")
    create_time: Optional[datetime] = Field(default=None, description="创建时间")


# ============================================================
# 角色-权限关联
# ============================================================


class RolePermissionUpdateRequest(BaseModel):
    """角色权限更新请求模型（批量设置角色的权限列表）

    说明：支持前端发送 camelCase 字段名 permIds，也支持 snake_case perm_ids。
    """

    role_id: Optional[int] = Field(default=None, description="角色ID（可选，路径参数已提供）")
    perm_ids: list[int] = Field(default_factory=list, alias="permIds", description="权限ID列表")

    model_config = ConfigDict(populate_by_name=True)


# ============================================================
# 报表统计
# ============================================================


class DepartmentStat(BaseModel):
    """部门统计数据模型"""

    name: str = Field(description="部门名称")
    value: int = Field(description="统计数值（如人数）")


class ReportSummary(BaseModel):
    """报表汇总数据模型"""

    model_config = ConfigDict(populate_by_name=True)

    total_employees: int = Field(alias="totalEmployees", description="员工总数")
    new_employees_this_month: int = Field(alias="newEmployeesThisMonth", description="本月新入职员工数")
    attendance_rate: Decimal = Field(alias="attendanceRate", description="出勤率（百分比）")
    leave_count: int = Field(alias="leaveCount", description="本月请假人次")
    department_stats: list[DepartmentStat] = Field(
        alias="departmentStats", default_factory=list, description="各部门人数统计"
    )
