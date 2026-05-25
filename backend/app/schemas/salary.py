"""
薪资相关 Schema（schemas/salary.py）

说明：定义薪资模块的请求/响应模型，包括薪资配置和薪资记录的 CRUD 操作。
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SalaryConfigCreate(BaseModel):
    """薪资配置创建请求模型"""

    model_config = ConfigDict(extra="ignore")

    config_name: str = Field(min_length=1, description="配置名称")
    config_key: str = Field(min_length=1, description="配置键")
    config_value: str = Field(description="配置值")
    config_desc: Optional[str] = Field(default=None, description="配置描述")
    effective_date: Optional[date] = Field(default=None, description="生效日期")


class SalaryConfigUpdate(BaseModel):
    """薪资配置更新请求模型（所有字段可选）"""

    model_config = ConfigDict(extra="ignore")

    config_name: Optional[str] = Field(default=None, description="配置名称")
    config_key: Optional[str] = Field(default=None, description="配置键")
    config_value: Optional[str] = Field(default=None, description="配置值")
    config_desc: Optional[str] = Field(default=None, description="配置描述")
    effective_date: Optional[date] = Field(default=None, description="生效日期")


class SalaryConfigResponse(BaseModel):
    """薪资配置响应模型"""

    model_config = ConfigDict(from_attributes=True)

    config_id: int = Field(description="配置ID")
    config_name: Optional[str] = Field(default=None, description="配置名称")
    config_key: Optional[str] = Field(default=None, description="配置键")
    config_value: Optional[str] = Field(default=None, description="配置值")
    config_desc: Optional[str] = Field(default=None, description="配置描述")
    effective_date: Optional[date] = Field(default=None, description="生效日期")
    status: Optional[str] = Field(default=None, description="状态")
    submit_date: Optional[date] = Field(default=None, description="提交日期")
    approve_date: Optional[date] = Field(default=None, description="审批日期")
    create_time: Optional[datetime] = Field(default=None, description="创建时间")
    update_time: Optional[datetime] = Field(default=None, description="更新时间")


class SalaryRecordCreate(BaseModel):
    """薪资记录创建请求模型"""

    model_config = ConfigDict(extra="ignore")

    emp_id: int = Field(description="员工ID")
    salary_month: date = Field(description="薪资月份")
    base_salary: Optional[Decimal] = Field(default=None, description="基本工资")
    position_salary: Optional[Decimal] = Field(default=None, description="岗位工资")
    bonus: Optional[Decimal] = Field(default=None, description="奖金")
    overtime_pay: Optional[Decimal] = Field(default=None, description="加班费")
    social_insurance: Optional[Decimal] = Field(default=None, description="社保扣除")
    housing_fund: Optional[Decimal] = Field(default=None, description="住房公积金扣除")
    attendance_deduct: Optional[Decimal] = Field(default=None, description="考勤扣除")
    tax: Optional[Decimal] = Field(default=None, description="个人所得税")
    other_deduct: Optional[Decimal] = Field(default=None, description="其他扣除")


class SalaryRecordUpdate(BaseModel):
    """薪资记录更新请求模型（所有字段可选）"""

    model_config = ConfigDict(extra="ignore")

    emp_id: Optional[int] = Field(default=None, description="员工ID")
    salary_month: Optional[date] = Field(default=None, description="薪资月份")
    base_salary: Optional[Decimal] = Field(default=None, description="基本工资")
    position_salary: Optional[Decimal] = Field(default=None, description="岗位工资")
    bonus: Optional[Decimal] = Field(default=None, description="奖金")
    overtime_pay: Optional[Decimal] = Field(default=None, description="加班费")
    social_insurance: Optional[Decimal] = Field(default=None, description="社保扣除")
    housing_fund: Optional[Decimal] = Field(default=None, description="住房公积金扣除")
    attendance_deduct: Optional[Decimal] = Field(default=None, description="考勤扣除")
    tax: Optional[Decimal] = Field(default=None, description="个人所得税")
    other_deduct: Optional[Decimal] = Field(default=None, description="其他扣除")


class SalaryRecordResponse(BaseModel):
    """薪资记录响应模型"""

    model_config = ConfigDict(from_attributes=True)

    salary_id: int = Field(description="薪资记录ID")
    emp_id: Optional[int] = Field(default=None, description="员工ID")
    salary_month: Optional[date] = Field(default=None, description="薪资月份")
    base_salary: Optional[Decimal] = Field(default=None, description="基本工资")
    position_salary: Optional[Decimal] = Field(default=None, description="岗位工资")
    bonus: Optional[Decimal] = Field(default=None, description="奖金")
    overtime_pay: Optional[Decimal] = Field(default=None, description="加班费")
    gross_salary: Optional[Decimal] = Field(default=None, description="应发工资")
    social_insurance: Optional[Decimal] = Field(default=None, description="社保扣除")
    housing_fund: Optional[Decimal] = Field(default=None, description="住房公积金扣除")
    attendance_deduct: Optional[Decimal] = Field(default=None, description="考勤扣除")
    tax: Optional[Decimal] = Field(default=None, description="个人所得税")
    other_deduct: Optional[Decimal] = Field(default=None, description="其他扣除")
    net_salary: Optional[Decimal] = Field(default=None, description="实发工资")
    status: Optional[str] = Field(default=None, description="审批状态")
    pending_approver_role: Optional[str] = Field(default=None, description="当前待审批人角色")
    next_approver_role: Optional[str] = Field(default=None, description="下一级审批人角色")
    next_approver_scope: Optional[str] = Field(default=None, description="下一级审批人数据范围")
    submit_date: Optional[date] = Field(default=None, description="提交日期")
    approve_date: Optional[date] = Field(default=None, description="审批日期")
    pay_date: Optional[date] = Field(default=None, description="发放日期")
    create_time: Optional[datetime] = Field(default=None, description="创建时间")
    update_time: Optional[datetime] = Field(default=None, description="更新时间")


class SalaryRecordQuery(BaseModel):
    """薪资记录分页查询参数模型"""

    page: int = Field(default=1, ge=1, description="页码（从1开始）")
    size: int = Field(default=10, ge=1, le=500, description="每页大小")
    emp_id: Optional[int] = Field(default=None, description="员工ID筛选")
    status: Optional[str] = Field(default=None, description="审批状态筛选")
    month_start: Optional[date] = Field(default=None, description="薪资月份起始")
    month_end: Optional[date] = Field(default=None, description="薪资月份截止")
