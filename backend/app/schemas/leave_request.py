"""
请假相关 Schema（schemas/leave_request.py）

说明：定义请假模块的请求/响应模型，包括请假申请、审批操作、查询和响应。
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class LeaveRequestCreate(BaseModel):
    """请假申请创建请求模型"""

    model_config = ConfigDict(extra="ignore")

    emp_id: int = Field(description="员工ID")
    leave_type: str = Field(min_length=1, description="请假类型（年假/事假/病假/调休等）")
    start_date: date = Field(description="开始日期")
    end_date: date = Field(description="结束日期")
    days: Decimal = Field(gt=0, description="请假天数")
    reason: Optional[str] = Field(default=None, description="请假原因")


class LeaveApprovalAction(BaseModel):
    """请假审批操作请求模型"""

    action: str = Field(pattern=r"^(approve|reject)$", description="审批动作（approve=通过, reject=驳回）")
    approver_remark: Optional[str] = Field(default=None, description="审批备注")


class LeaveRequestResponse(BaseModel):
    """请假申请响应模型（对应 ORM LeaveRequest 模型）"""

    model_config = ConfigDict(from_attributes=True)

    leave_id: int = Field(description="请假记录ID")
    emp_id: Optional[int] = Field(default=None, description="员工ID")
    leave_type: Optional[str] = Field(default=None, description="请假类型")
    start_date: Optional[date] = Field(default=None, description="开始日期")
    end_date: Optional[date] = Field(default=None, description="结束日期")
    days: Optional[Decimal] = Field(default=None, description="请假天数")
    reason: Optional[str] = Field(default=None, description="请假原因")
    status: Optional[str] = Field(default=None, description="审批状态")
    approver_id: Optional[int] = Field(default=None, description="审批人ID")
    pending_approver_tag: Optional[str] = Field(default=None, description="当前待审批人身份标签")
    pending_approver_scope: Optional[str] = Field(default=None, description="当前待审批人数据范围")
    next_approver_tag: Optional[str] = Field(default=None, description="下一级审批人身份标签")
    next_approver_scope: Optional[str] = Field(default=None, description="下一级审批人数据范围")
    apply_time: Optional[datetime] = Field(default=None, description="申请时间")
    approve_time: Optional[datetime] = Field(default=None, description="审批时间")
    approve_remark: Optional[str] = Field(default=None, description="审批备注")


class LeaveRequestQuery(BaseModel):
    """请假分页查询参数模型"""

    page: int = Field(default=1, ge=1, description="页码（从1开始）")
    size: int = Field(default=10, ge=1, le=500, description="每页大小")
    emp_id: Optional[int] = Field(default=None, description="员工ID筛选")
    status: Optional[str] = Field(default=None, description="审批状态筛选")
