"""
员工模型（Employee）

说明：映射 MySQL hrms_db 中的 employee 表，存储员工基本信息。
     包含姓名、性别、联系方式、入职/离职日期、所属部门和职位等字段。
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Employee(Base):
    """员工表 ORM 模型，对应 MySQL employee 表"""

    __tablename__ = "employee"

    # 员工ID（主键，自增）
    emp_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 员工姓名
    emp_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # 性别
    gender: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    # 手机号
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # 邮箱
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # 身份证号
    id_card: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # 出生日期
    birthday: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    # 住址
    address: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    # 入职日期
    hire_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    # 离职日期
    leave_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    # 所属部门ID
    dept_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 职位ID
    position_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 身份标签编码
    identity_tag_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # 状态（在职/离职等）
    status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # 创建时间
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # 更新时间
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
