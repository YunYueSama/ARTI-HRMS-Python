"""
ORM 模型包（models）

说明：本包包含所有 SQLAlchemy 2.0 ORM 模型，映射 MySQL hrms_db 中的现有表。
     所有模型使用 Mapped[type] + mapped_column() 声明式语法。
     导入本包即可访问所有模型类和 Base 基类。

用法：
    from app.models import Employee, Department, Base
"""

from app.core.database import Base
from app.models.agent import AgentApprovalRecord, AgentExecutionLog, AgentTask

# AI 相关模型
from app.models.ai_chat import AiChatMessage
from app.models.approval import ApprovalRule, ApprovalRuleType, DeptPermissionTemplate

# 考勤和请假模型
from app.models.attendance import Attendance
from app.models.department import Department

# 核心业务模型
from app.models.employee import Employee
from app.models.identity_tag import IdentityTag
from app.models.job_position import JobPosition
from app.models.leave_request import LeaveRequest
from app.models.module_scope import ModuleScopeDetail, ModuleScopeRule
from app.models.permission import Permission
from app.models.persona import PersonaConfig
from app.models.role import Role
from app.models.role_permission import RolePermission

# 薪资模型
from app.models.salary import SalaryConfig, SalaryRecord

# 用户和权限模型
from app.models.sys_user import SysUser

__all__ = [
    "Base",
    # 核心业务
    "Employee",
    "Department",
    "JobPosition",
    # 考勤和请假
    "Attendance",
    "LeaveRequest",
    # 薪资
    "SalaryConfig",
    "SalaryRecord",
    # 用户和权限
    "SysUser",
    "Role",
    "Permission",
    "RolePermission",
    "IdentityTag",
    "ModuleScopeRule",
    "ModuleScopeDetail",
    "ApprovalRule",
    "ApprovalRuleType",
    "DeptPermissionTemplate",
    # AI 相关
    "AiChatMessage",
    "PersonaConfig",
    "AgentTask",
    "AgentExecutionLog",
    "AgentApprovalRecord",
]
