"""
LangChain Tools 声明（ai/agent/tools.py）

说明：定义 Agent 可调用的工具（Tools），每个工具对应一个业务操作。
     使用 LangChain 的 @tool 装饰器和 Pydantic args_schema 声明工具。

核心概念：
    - Tool：Agent 可以调用的外部函数，有明确的输入输出定义
    - args_schema：使用 Pydantic 模型定义工具的输入参数结构
    - @tool 装饰器：将普通函数注册为 LangChain Tool

工具列表：
    1. create_leave_request - 创建请假申请
    2. upsert_attendance    - 创建或更新考勤记录
    3. update_role_permission - 更新角色权限

注意：这些工具目前是占位实现，实际执行逻辑在 agent_task_service 中。
     工具的主要作用是为 LLM 提供结构化的函数调用接口描述。

Java 对应关系：
    AgentTaskService.executeLeave()          → create_leave_request
    AgentTaskService.executeAttendance()     → upsert_attendance
    AgentTaskService.executeRolePermission() → update_role_permission
"""

from langchain_core.tools import tool
from pydantic import BaseModel, Field

# ============================================================
# 工具参数模型（Pydantic Schema）
# ============================================================


class LeaveCreateArgs(BaseModel):
    """
    创建请假申请的参数模型

    说明：定义创建请假申请所需的所有参数。
         LLM 会根据此 Schema 生成结构化的函数调用参数。
    """

    emp_id: int = Field(description="员工ID")
    leave_type: str = Field(description="请假类型（年假/病假/事假/婚假/产假/陪产假/丧假）")
    start_date: str = Field(description="开始日期，格式 yyyy-MM-dd")
    end_date: str = Field(description="结束日期，格式 yyyy-MM-dd")
    days: int = Field(description="请假天数")
    reason: str = Field(default="", description="请假原因")


class AttendanceUpsertArgs(BaseModel):
    """
    创建或更新考勤记录的参数模型

    说明：定义考勤操作所需的所有参数。
         如果指定日期已有记录则更新，否则创建新记录。
    """

    emp_id: int = Field(description="员工ID")
    attendance_date: str = Field(description="考勤日期，格式 yyyy-MM-dd")
    clock_in: str | None = Field(default=None, description="签到时间，格式 HH:mm")
    clock_out: str | None = Field(default=None, description="签退时间，格式 HH:mm")
    remark: str = Field(default="", description="备注说明")


class RolePermissionUpdateArgs(BaseModel):
    """
    更新角色权限的参数模型

    说明：定义角色权限变更所需的所有参数。
         action 为 add 时增加权限，为 remove 时移除权限。
    """

    role_id: int = Field(description="角色ID")
    permission_id: int = Field(description="权限ID")
    action: str = Field(description="操作类型：add（增加）或 remove（移除）")


# ============================================================
# 工具定义
# ============================================================


@tool(args_schema=LeaveCreateArgs)
async def create_leave_request(
    emp_id: int,
    leave_type: str,
    start_date: str,
    end_date: str,
    days: int,
    reason: str = "",
) -> str:
    """创建请假申请。为指定员工提交一条请假申请记录，包含请假类型、起止日期和原因。"""
    # 占位实现：实际执行由 agent_task_service.py 中的 _execute_leave() 完成
    return f"请假申请已创建：{leave_type}，{start_date} 至 {end_date}，共 {days} 天"


@tool(args_schema=AttendanceUpsertArgs)
async def upsert_attendance(
    emp_id: int,
    attendance_date: str,
    clock_in: str | None = None,
    clock_out: str | None = None,
    remark: str = "",
) -> str:
    """创建或更新考勤记录。如果指定日期已有考勤记录则更新，否则创建新记录。"""
    # 占位实现：实际执行由 agent_task_service.py 中的 _execute_attendance() 完成
    return f"考勤记录已处理：{attendance_date}，签到 {clock_in}，签退 {clock_out}"


@tool(args_schema=RolePermissionUpdateArgs)
async def update_role_permission(
    role_id: int,
    permission_id: int,
    action: str,
) -> str:
    """更新角色权限。为指定角色增加或移除一项权限。action 为 add 表示增加，remove 表示移除。"""
    # 占位实现：实际执行由 agent_task_service.py 中的 _execute_role_permission() 完成
    action_text = "增加" if action == "add" else "移除"
    return f"角色权限已{action_text}：角色ID={role_id}，权限ID={permission_id}"


# ============================================================
# 工具列表（供 Agent 使用）
# ============================================================

AGENT_TOOLS = [
    create_leave_request,
    upsert_attendance,
    update_role_permission,
]
"""Agent 可用的工具列表，传递给 LangGraph Agent 或 LLM 的 bind_tools()"""
