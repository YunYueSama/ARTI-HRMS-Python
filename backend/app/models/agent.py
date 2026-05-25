"""
Agent 相关模型（AgentTask、AgentExecutionLog、AgentApprovalRecord）

说明：映射 MySQL hrms_db 中的 Agent 相关表。
     - AgentTask：Agent 任务主表，存储用户指令、意图、计划和执行结果
     - AgentExecutionLog：Agent 执行日志，记录每个步骤的执行详情
     - AgentApprovalRecord：Agent 审批记录，记录人工审批操作
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AgentTask(Base):
    """Agent 任务表 ORM 模型，对应 MySQL agent_task 表"""

    __tablename__ = "agent_task"

    # 任务ID（主键，自增）
    task_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 用户ID
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 用户原始指令文本
    command_text: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # 识别到的意图
    intent: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # 风险等级（low/medium/high）
    risk_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # 任务状态（planned/approved/executing/completed/failed/cancelled）
    status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # LLM 提供商名称
    provider_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # 是否需要人工审批
    requires_approval: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    # 是否可执行
    executable: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    # 执行计划 JSON（TEXT 类型）
    plan_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 执行结果摘要
    result_summary: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # 创建时间
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # 更新时间
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class AgentExecutionLog(Base):
    """Agent 执行日志表 ORM 模型，对应 MySQL agent_execution_log 表"""

    __tablename__ = "agent_execution_log"

    # 日志ID（主键，自增）
    log_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 关联任务ID
    task_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 步骤序号
    step_no: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 日志级别（INFO/WARN/ERROR）
    log_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # 日志消息内容（TEXT 类型）
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 创建时间
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class AgentApprovalRecord(Base):
    """Agent 审批记录表 ORM 模型，对应 MySQL agent_approval_record 表"""

    __tablename__ = "agent_approval_record"

    # 审批记录ID（主键，自增）
    approval_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 关联任务ID
    task_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 审批人用户ID
    approver_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 审批动作（approve/reject）
    action: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # 审批备注
    remark: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # 创建时间
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
