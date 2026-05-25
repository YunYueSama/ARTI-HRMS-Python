"""
审批规则模型（ApprovalRule、ApprovalRuleType、DeptPermissionTemplate）

说明：映射 MySQL hrms_db 中的审批相关表。
     - ApprovalRule：审批规则（定义不同身份标签在不同条件下的审批链）
     - ApprovalRuleType：审批规则类型（如请假审批、薪资审批等）
     - DeptPermissionTemplate：部门权限模板（定义部门可访问的模块）
     注意：ApprovalRuleType 的主键为 type_code（字符串类型），非自增整数。
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ApprovalRule(Base):
    """审批规则表 ORM 模型，对应 MySQL approval_rule 表"""

    __tablename__ = "approval_rule"

    # 规则ID（主键，自增）
    rule_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 审批类型编码（关联 approval_rule_type）
    type_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 申请人身份标签
    applicant_tag: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 天数比较运算符（<=、>、== 等）
    days_op: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # 天数阈值（BigDecimal → Numeric）
    days_value: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    # 第一级审批人身份标签
    first_approver_tag: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 第二级审批人身份标签
    second_approver_tag: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 第二级审批人数据范围
    second_approver_scope: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 排序序号
    sort_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 创建时间
    create_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 更新时间
    update_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ApprovalRuleType(Base):
    """审批规则类型表 ORM 模型，对应 MySQL approval_rule_type 表"""

    __tablename__ = "approval_rule_type"

    # 类型编码（主键，字符串类型）
    type_code: Mapped[str] = mapped_column(String(50), primary_key=True)
    # 类型名称
    type_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # 类型描述
    type_desc: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 状态（active/disabled）
    status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # 创建时间
    create_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 更新时间
    update_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DeptPermissionTemplate(Base):
    """部门权限模板表 ORM 模型，对应 MySQL dept_permission_template 表"""

    __tablename__ = "dept_permission_template"

    # 模板记录ID（主键，自增）
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 部门ID
    dept_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 模块编码
    module_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 创建时间
    create_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
