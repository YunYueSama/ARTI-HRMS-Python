"""
报表统计服务（services/report_service.py）

说明：实现报表汇总数据的查询功能。
     对应 Java 的 ReportService 类。
"""

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance import Attendance
from app.models.department import Department
from app.models.employee import Employee
from app.models.leave_request import LeaveRequest
from app.schemas.permission import DepartmentStat, ReportSummary


async def get_summary(db: AsyncSession) -> ReportSummary:
    """
    获取报表汇总数据

    包含：
        - total_employees: 员工总数
        - new_employees_this_month: 本月新入职员工数
        - attendance_rate: 本月出勤率（百分比）
        - leave_count: 本月请假人次
        - department_stats: 各部门人数统计
    """
    today = date.today()
    month_start = today.replace(day=1)
    month_end = today.replace(day=_last_day_of_month(today))

    # 员工总数
    total_result = await db.execute(select(func.count()).select_from(Employee))
    total_employees = total_result.scalar() or 0

    # 本月新入职员工数
    new_emp_result = await db.execute(
        select(func.count())
        .select_from(Employee)
        .where(Employee.hire_date >= month_start)
        .where(Employee.hire_date <= month_end)
    )
    new_employees_this_month = new_emp_result.scalar() or 0

    # 本月出勤率
    attendance_total_result = await db.execute(
        select(func.count())
        .select_from(Attendance)
        .where(Attendance.attendance_date >= month_start)
        .where(Attendance.attendance_date <= month_end)
    )
    attendance_total = attendance_total_result.scalar() or 0

    attendance_normal_result = await db.execute(
        select(func.count())
        .select_from(Attendance)
        .where(Attendance.attendance_date >= month_start)
        .where(Attendance.attendance_date <= month_end)
        .where(Attendance.status == "正常")
    )
    attendance_normal = attendance_normal_result.scalar() or 0

    if attendance_total == 0:
        attendance_rate = Decimal("0.0")
    else:
        attendance_rate = (Decimal(attendance_normal) * Decimal("100") / Decimal(attendance_total)).quantize(
            Decimal("0.1"), rounding=ROUND_HALF_UP
        )

    # 本月请假人次
    month_start_dt = datetime(today.year, today.month, 1)
    month_end_dt = datetime(today.year, today.month, _last_day_of_month(today), 23, 59, 59)
    leave_count_result = await db.execute(
        select(func.count())
        .select_from(LeaveRequest)
        .where(LeaveRequest.apply_time >= month_start_dt)
        .where(LeaveRequest.apply_time <= month_end_dt)
    )
    leave_count = leave_count_result.scalar() or 0

    # 各部门人数统计
    dept_result = await db.execute(select(Department))
    departments = dept_result.scalars().all()

    department_stats: list[DepartmentStat] = []
    for dept in departments:
        emp_count_result = await db.execute(
            select(func.count()).select_from(Employee).where(Employee.dept_id == dept.dept_id)
        )
        emp_count = emp_count_result.scalar() or 0
        department_stats.append(DepartmentStat(name=dept.dept_name or "未命名", value=emp_count))

    return ReportSummary(
        total_employees=total_employees,  # type: ignore[call-arg]
        new_employees_this_month=new_employees_this_month,  # type: ignore[call-arg]
        attendance_rate=attendance_rate,  # type: ignore[call-arg]
        leave_count=leave_count,  # type: ignore[call-arg]
        department_stats=department_stats,  # type: ignore[call-arg]
    )


def _last_day_of_month(d: date) -> int:
    """获取指定日期所在月份的最后一天"""
    import calendar

    return calendar.monthrange(d.year, d.month)[1]
