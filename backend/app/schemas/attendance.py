"""
考勤相关 Schema（schemas/attendance.py）

说明：定义考勤模块的请求/响应模型，包括打卡记录的创建、更新、查询和响应。
"""

from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field


class AttendanceCreate(BaseModel):
    """考勤记录创建请求模型"""

    model_config = ConfigDict(extra="ignore")

    emp_id: int | None = Field(default=None, description="员工ID")
    attendance_date: date | None = Field(default=None, description="考勤日期")
    clock_in: str | None = Field(default=None, description="签到时间（格式 HH:MM）")
    clock_out: str | None = Field(default=None, description="签退时间（格式 HH:MM）")
    status: str | None = Field(default=None, description="考勤状态（正常/迟到/早退/缺勤）")
    remark: str | None = Field(default=None, description="备注")


class AttendanceUpdate(BaseModel):
    """考勤记录更新请求模型（所有字段可选）"""

    model_config = ConfigDict(extra="ignore")

    emp_id: int | None = Field(default=None, description="员工ID")
    attendance_date: date | None = Field(default=None, description="考勤日期")
    clock_in: str | None = Field(default=None, description="签到时间（格式 HH:MM）")
    clock_out: str | None = Field(default=None, description="签退时间（格式 HH:MM）")
    status: str | None = Field(default=None, description="考勤状态（正常/迟到/早退/缺勤）")
    remark: str | None = Field(default=None, description="备注")


class AttendanceResponse(BaseModel):
    """考勤记录响应模型（对应 ORM Attendance 模型）"""

    model_config = ConfigDict(from_attributes=True)

    attendance_id: int = Field(description="考勤记录ID")
    emp_id: int | None = Field(default=None, description="员工ID")
    attendance_date: date | None = Field(default=None, description="考勤日期")
    clock_in: time | None = Field(default=None, description="签到时间")
    clock_out: time | None = Field(default=None, description="签退时间")
    status: str | None = Field(default=None, description="考勤状态")
    remark: str | None = Field(default=None, description="备注")
    create_time: datetime | None = Field(default=None, description="创建时间")


class AttendanceQuery(BaseModel):
    """考勤分页查询参数模型"""

    page: int = Field(default=1, ge=1, description="页码（从1开始）")
    size: int = Field(default=10, ge=1, le=500, description="每页大小")
    emp_id: int | None = Field(default=None, description="员工ID筛选")
    start_date: date | None = Field(default=None, description="开始日期")
    end_date: date | None = Field(default=None, description="结束日期")
    status: str | None = Field(default=None, description="考勤状态筛选")
