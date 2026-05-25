"""
考勤模型（Attendance）

说明：映射 MySQL hrms_db 中的 attendance 表，存储员工每日考勤记录。
     clock_in 和 clock_out 使用 Time 类型（对应 Java 的 LocalTime）。
"""

from datetime import date, datetime, time
from typing import Optional

from sqlalchemy import Date, DateTime, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Attendance(Base):
    """考勤表 ORM 模型，对应 MySQL attendance 表"""

    __tablename__ = "attendance"

    # 考勤记录ID（主键，自增）
    attendance_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 员工ID
    emp_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 考勤日期
    attendance_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    # 签到时间（Time 类型，对应 Java LocalTime）
    clock_in: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    # 签退时间（Time 类型，对应 Java LocalTime）
    clock_out: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    # 考勤状态（正常/迟到/早退/缺勤等）
    status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # 备注
    remark: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # 创建时间
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
