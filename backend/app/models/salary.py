"""
薪资模型（SalaryConfig、SalaryRecord）

说明：映射 MySQL hrms_db 中的 salary_config 和 salary_record 表。
     - SalaryConfig：薪资配置项（如基本工资标准、社保比例等）
     - SalaryRecord：员工月度薪资记录（含各项收入、扣除和审批状态流转）
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SalaryConfig(Base):
    """薪资配置表 ORM 模型，对应 MySQL salary_config 表"""

    __tablename__ = "salary_config"

    # 配置ID（主键，自增）
    config_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 配置名称
    config_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # 配置键
    config_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # 配置值
    config_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 配置描述
    config_desc: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 生效日期
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # 状态（draft/pending/approved 等）
    status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # 提交日期
    submit_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # 审批日期
    approve_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # 创建时间
    create_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 更新时间
    update_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SalaryRecord(Base):
    """薪资记录表 ORM 模型，对应 MySQL salary_record 表"""

    __tablename__ = "salary_record"

    # 薪资记录ID（主键，自增）
    salary_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 员工ID
    emp_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 薪资月份
    salary_month: Mapped[date | None] = mapped_column(Date, nullable=True)
    # 基本工资
    base_salary: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    # 岗位工资
    position_salary: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    # 奖金
    bonus: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    # 加班费
    overtime_pay: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    # 应发工资（总额）
    gross_salary: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    # 社保扣除
    social_insurance: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    # 住房公积金扣除
    housing_fund: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    # 考勤扣除
    attendance_deduct: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    # 个人所得税
    tax: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    # 其他扣除
    other_deduct: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    # 实发工资
    net_salary: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    # 审批状态（draft/pending/approved/paid 等）
    status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # 当前待审批人角色
    pending_approver_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 下一级审批人角色
    next_approver_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 下一级审批人数据范围
    next_approver_scope: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 提交日期
    submit_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # 审批日期
    approve_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # 发放日期
    pay_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # 创建时间
    create_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 更新时间
    update_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
