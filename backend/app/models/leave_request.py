"""
请假申请模型（LeaveRequest）

说明：映射 MySQL hrms_db 中的 leave_request 表，存储员工请假申请记录。
     包含多级审批链字段（pending_approver_tag/scope、next_approver_tag/scope）。
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LeaveRequest(Base):
    """请假申请表 ORM 模型，对应 MySQL leave_request 表"""

    __tablename__ = "leave_request"

    # 请假记录ID（主键，自增）
    leave_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 员工ID
    emp_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 请假类型（年假/事假/病假等）
    leave_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 开始日期
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # 结束日期
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # 请假天数（BigDecimal → Numeric）
    days: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    # 请假原因
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # 审批状态（pending/approved/rejected 等）
    status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # 审批人ID
    approver_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 当前待审批人身份标签
    pending_approver_tag: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 当前待审批人数据范围
    pending_approver_scope: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 下一级审批人身份标签
    next_approver_tag: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 下一级审批人数据范围
    next_approver_scope: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 申请时间
    apply_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 审批时间
    approve_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 审批备注
    approve_remark: Mapped[str | None] = mapped_column(String(500), nullable=True)
