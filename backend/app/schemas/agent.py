"""
Agent 相关 Schema（schemas/agent.py）

说明：定义 Agent 模块的请求/响应模型，包括意图识别、执行计划、任务视图等。
     DraftPlan 用于 LLM 结构化输出（Structured Output），其他模型用于 API 交互。

Java 对应关系：
    AgentTaskPayloads.PlanRequest    → PlanRequest
    AgentTaskPayloads.ApproveRequest → ApproveRequest
    AgentTaskPayloads.DraftPlan      → DraftPlan
    AgentTaskPayloads.AgentPlan      → AgentPlan
    AgentTaskPayloads.AgentPlanStep  → AgentPlanStep
    AgentTaskPayloads.AgentPlanEntity → AgentPlanEntity
    AgentTaskPayloads.AgentTaskView  → AgentTaskView
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ============================================================
# 枚举定义
# ============================================================


class IntentType(StrEnum):
    """Agent 意图类型枚举"""

    LEAVE_CREATE = "leave.create"
    ATTENDANCE_UPSERT = "attendance.upsert"
    ROLE_PERMISSION_UPDATE = "role-permission.update"
    UNKNOWN = "unknown"


class RiskLevel(StrEnum):
    """风险等级枚举"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MessageCategory(StrEnum):
    """消息分类枚举（用于意图路由）"""

    EMOTIONAL_SUPPORT = "emotional_support"
    PROCESS_EXPLANATION = "process_explanation"
    SYSTEM_DATA_QUERY = "system_data_query"
    DAILY_CHAT = "daily_chat"
    UNKNOWN = "unknown"


# ============================================================
# 请求模型
# ============================================================


class PlanRequest(BaseModel):
    """Agent 计划生成请求模型"""

    user_id: int = Field(description="用户ID")
    command: str = Field(min_length=1, max_length=500, description="用户指令文本")


class ApproveRequest(BaseModel):
    """Agent 任务审批请求模型"""

    user_id: int = Field(description="用户ID")
    remark: str = Field(default="", max_length=500, description="审批备注")


# ============================================================
# LLM 结构化输出模型
# ============================================================


class DraftPlan(BaseModel):
    """
    LLM 结构化输出模型（用于从自然语言指令中提取结构化信息）

    说明：LLM 根据用户指令填充此模型的字段，不同意图使用不同字段组合。
         - leave.create: 使用 leave_type, start_date, end_date, days, reason
         - attendance.upsert: 使用 attendance_date, clock_in, clock_out
         - role-permission.update: 使用 role_name, permission_name
    """

    intent: str | None = Field(default=None, description="识别到的意图类型")
    summary: str | None = Field(default=None, description="操作摘要描述")
    action: str | None = Field(default=None, description="具体动作")
    # 请假相关字段
    leave_type: str | None = Field(default=None, description="请假类型")
    start_date: str | None = Field(default=None, description="开始日期")
    end_date: str | None = Field(default=None, description="结束日期")
    days: int | None = Field(default=None, description="天数")
    reason: str | None = Field(default=None, description="原因")
    # 考勤相关字段
    attendance_date: str | None = Field(default=None, description="考勤日期")
    clock_in: str | None = Field(default=None, description="签到时间")
    clock_out: str | None = Field(default=None, description="签退时间")
    # 权限相关字段
    role_name: str | None = Field(default=None, description="角色名称")
    permission_name: str | None = Field(default=None, description="权限名称")


# ============================================================
# Agent 计划相关模型
# ============================================================


class AgentPlanStep(BaseModel):
    """Agent 执行计划步骤模型"""

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)  # type: ignore[typeddict-unknown-key]

    step_no: int = Field(alias="stepNo", default=0, description="步骤序号")
    title: str = Field(default="", description="步骤标题")
    method: str = Field(default="LOCAL", description="执行方式（LOCAL/GET/POST/PUT/DELETE）")
    api: str = Field(default="", description="API 端点或内部服务名")
    payload_preview: dict[str, Any] = Field(alias="payloadPreview", default_factory=dict, description="请求参数预览")


class AgentPlanEntity(BaseModel):
    """Agent 计划影响实体模型"""

    type: str = Field(default="", description="实体类型（employee/role/permission 等）")
    id: int | None = Field(default=None, description="实体ID")
    name: str = Field(default="", description="实体名称")


class AgentPlan(BaseModel):
    """Agent 执行计划模型（完整的计划结构）"""

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)  # type: ignore[typeddict-unknown-key]

    intent: str = Field(default="unknown", description="识别到的意图")
    summary: str = Field(default="", description="计划摘要")
    risk_level: str = Field(alias="riskLevel", default="medium", description="风险等级")
    requires_approval: bool = Field(alias="requiresApproval", default=True, description="是否需要人工审批")
    executable: bool = Field(default=False, description="是否可执行")
    warnings: list[str] = Field(default_factory=list, description="警告信息列表")
    entities: list[AgentPlanEntity] = Field(default_factory=list, description="受影响的实体列表")
    preview: dict[str, Any] = Field(default_factory=dict, description="操作预览数据")
    steps: list[AgentPlanStep] = Field(default_factory=list, description="执行步骤列表")
    rollback_plan: list[str] = Field(alias="rollbackPlan", default_factory=list, description="回滚方案")


# ============================================================
# Agent 任务视图
# ============================================================


class AgentTaskView(BaseModel):
    """Agent 任务视图模型（用于前端展示任务详情）"""

    model_config = ConfigDict(from_attributes=True)

    task_id: int = Field(description="任务ID")
    user_id: int | None = Field(default=None, description="用户ID")
    command_text: str | None = Field(default=None, description="用户原始指令")
    intent: str | None = Field(default=None, description="识别到的意图")
    risk_level: str | None = Field(default=None, description="风险等级")
    status: str | None = Field(default=None, description="任务状态")
    provider_name: str | None = Field(default=None, description="LLM 提供商名称")
    requires_approval: bool | None = Field(default=None, description="是否需要审批")
    executable: bool | None = Field(default=None, description="是否可执行")
    plan: AgentPlan | None = Field(default=None, description="执行计划")
    result_summary: str | None = Field(default=None, description="执行结果摘要")
    create_time: datetime | None = Field(default=None, description="创建时间")
    update_time: datetime | None = Field(default=None, description="更新时间")
