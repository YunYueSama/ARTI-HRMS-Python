"""
薪资相关 Schema（schemas/salary.py）

说明：定义薪资模块的请求/响应模型，包括薪资配置和薪资记录的 CRUD 操作。
"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class SalaryConfigCreate(BaseModel):
    """薪资配置创建请求模型"""

    model_config = ConfigDict(extra="ignore")

    config_name: str = Field(min_length=1, description="配置名称")
    config_key: str = Field(min_length=1, description="配置键")
    config_value: str = Field(description="配置值")
    config_desc: str | None = Field(default=None, description="配置描述")
    effective_date: date | None = Field(default=None, description="生效日期")


class SalaryConfigUpdate(BaseModel):
    """薪资配置更新请求模型（所有字段可选）"""

    model_config = ConfigDict(extra="ignore")

    config_name: str | None = Field(default=None, description="配置名称")
    config_key: str | None = Field(default=None, description="配置键")
    config_value: str | None = Field(default=None, description="配置值")
    config_desc: str | None = Field(default=None, description="配置描述")
    effective_date: date | None = Field(default=None, description="生效日期")


class SalaryConfigResponse(BaseModel):
    """薪资配置响应模型"""

    model_config = ConfigDict(from_attributes=True)

    config_id: int = Field(description="配置ID")
    config_name: str | None = Field(default=None, description="配置名称")
    config_key: str | None = Field(default=None, description="配置键")
    config_value: str | None = Field(default=None, description="配置值")
    config_desc: str | None = Field(default=None, description="配置描述")
    effective_date: date | None = Field(default=None, description="生效日期")
    status: str | None = Field(default=None, description="状态")
    submit_date: date | None = Field(default=None, description="提交日期")
    approve_date: date | None = Field(default=None, description="审批日期")
    create_time: datetime | None = Field(default=None, description="创建时间")
    update_time: datetime | None = Field(default=None, description="更新时间")


class SalaryRecordCreate(BaseModel):
    """薪资记录创建请求模型"""

    model_config = ConfigDict(extra="ignore")

    emp_id: int = Field(description="员工ID")
    salary_month: date = Field(description="薪资月份")
    base_salary: Decimal | None = Field(default=None, description="基本工资")
    position_salary: Decimal | None = Field(default=None, description="岗位工资")
    bonus: Decimal | None = Field(default=None, description="奖金")
    overtime_pay: Decimal | None = Field(default=None, description="加班费")
    social_insurance: Decimal | None = Field(default=None, description="社保扣除")
    housing_fund: Decimal | None = Field(default=None, description="住房公积金扣除")
    attendance_deduct: Decimal | None = Field(default=None, description="考勤扣除")
    tax: Decimal | None = Field(default=None, description="个人所得税")
    other_deduct: Decimal | None = Field(default=None, description="其他扣除")


class SalaryRecordUpdate(BaseModel):
    """薪资记录更新请求模型（所有字段可选）"""

    model_config = ConfigDict(extra="ignore")

    emp_id: int | None = Field(default=None, description="员工ID")
    salary_month: date | None = Field(default=None, description="薪资月份")
    base_salary: Decimal | None = Field(default=None, description="基本工资")
    position_salary: Decimal | None = Field(default=None, description="岗位工资")
    bonus: Decimal | None = Field(default=None, description="奖金")
    overtime_pay: Decimal | None = Field(default=None, description="加班费")
    social_insurance: Decimal | None = Field(default=None, description="社保扣除")
    housing_fund: Decimal | None = Field(default=None, description="住房公积金扣除")
    attendance_deduct: Decimal | None = Field(default=None, description="考勤扣除")
    tax: Decimal | None = Field(default=None, description="个人所得税")
    other_deduct: Decimal | None = Field(default=None, description="其他扣除")


class SalaryRecordResponse(BaseModel):
    """薪资记录响应模型"""

    model_config = ConfigDict(from_attributes=True)

    salary_id: int = Field(description="薪资记录ID")
    emp_id: int | None = Field(default=None, description="员工ID")
    salary_month: date | None = Field(default=None, description="薪资月份")
    base_salary: Decimal | None = Field(default=None, description="基本工资")
    position_salary: Decimal | None = Field(default=None, description="岗位工资")
    bonus: Decimal | None = Field(default=None, description="奖金")
    overtime_pay: Decimal | None = Field(default=None, description="加班费")
    gross_salary: Decimal | None = Field(default=None, description="应发工资")
    social_insurance: Decimal | None = Field(default=None, description="社保扣除")
    housing_fund: Decimal | None = Field(default=None, description="住房公积金扣除")
    attendance_deduct: Decimal | None = Field(default=None, description="考勤扣除")
    tax: Decimal | None = Field(default=None, description="个人所得税")
    other_deduct: Decimal | None = Field(default=None, description="其他扣除")
    net_salary: Decimal | None = Field(default=None, description="实发工资")
    status: str | None = Field(default=None, description="审批状态")
    pending_approver_role: str | None = Field(default=None, description="当前待审批人角色")
    next_approver_role: str | None = Field(default=None, description="下一级审批人角色")
    next_approver_scope: str | None = Field(default=None, description="下一级审批人数据范围")
    submit_date: date | None = Field(default=None, description="提交日期")
    approve_date: date | None = Field(default=None, description="审批日期")
    pay_date: date | None = Field(default=None, description="发放日期")
    create_time: datetime | None = Field(default=None, description="创建时间")
    update_time: datetime | None = Field(default=None, description="更新时间")


class SalaryRecordQuery(BaseModel):
    """薪资记录分页查询参数模型"""

    page: int = Field(default=1, ge=1, description="页码（从1开始）")
    size: int = Field(default=10, ge=1, le=500, description="每页大小")
    emp_id: int | None = Field(default=None, description="员工ID筛选")
    status: str | None = Field(default=None, description="审批状态筛选")
    month_start: date | None = Field(default=None, description="薪资月份起始")
    month_end: date | None = Field(default=None, description="薪资月份截止")
