"""
考勤管理服务（services/attendance_service.py）

说明：实现考勤记录的增删改查和分页查询功能。
     对应 Java 的 AttendanceService 类。
     包含自动状态计算逻辑：
     - clock_in > 09:00 → "迟到"
     - clock_out < 18:00 → "早退"
     - 两者都正常 → "正常"
"""

from datetime import datetime, time

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.models.attendance import Attendance
from app.schemas.attendance import AttendanceCreate, AttendanceQuery, AttendanceResponse, AttendanceUpdate
from app.schemas.common import PageResponse

# 考勤时间标准
STANDARD_CLOCK_IN = time(9, 0)   # 09:00
STANDARD_CLOCK_OUT = time(18, 0)  # 18:00


def _parse_time(time_str: str | None) -> time | None:
    """将 HH:MM 格式字符串转换为 time 对象"""
    if not time_str:
        return None
    parts = time_str.split(":")
    return time(int(parts[0]), int(parts[1]))


def _calculate_status(clock_in: time | None, clock_out: time | None) -> str:
    """
    自动计算考勤状态

    规则：
        - clock_in > 09:00 → "迟到"
        - clock_out < 18:00 → "早退"
        - 两者都正常 → "正常"
        - 无打卡记录 → "缺勤"
    """
    if clock_in is None and clock_out is None:
        return "缺勤"
    if clock_in and clock_in > STANDARD_CLOCK_IN:
        return "迟到"
    if clock_out and clock_out < STANDARD_CLOCK_OUT:
        return "早退"
    return "正常"


async def list_attendance(query: AttendanceQuery, db: AsyncSession) -> PageResponse[AttendanceResponse]:
    """
    分页查询考勤记录

    支持筛选条件：
        - emp_id: 员工ID精确匹配
        - start_date / end_date: 日期范围
        - status: 考勤状态精确匹配
    """
    stmt = select(Attendance)
    count_stmt = select(func.count()).select_from(Attendance)

    if query.emp_id is not None:
        stmt = stmt.where(Attendance.emp_id == query.emp_id)
        count_stmt = count_stmt.where(Attendance.emp_id == query.emp_id)

    if query.status:
        stmt = stmt.where(Attendance.status == query.status)
        count_stmt = count_stmt.where(Attendance.status == query.status)

    if query.start_date:
        stmt = stmt.where(Attendance.attendance_date >= query.start_date)
        count_stmt = count_stmt.where(Attendance.attendance_date >= query.start_date)

    if query.end_date:
        stmt = stmt.where(Attendance.attendance_date <= query.end_date)
        count_stmt = count_stmt.where(Attendance.attendance_date <= query.end_date)

    # 查询总数
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # 分页查询
    stmt = stmt.offset((query.page - 1) * query.size).limit(query.size)
    result = await db.execute(stmt)
    records = result.scalars().all()

    return PageResponse(
        items=[AttendanceResponse.model_validate(r) for r in records],
        total=total,
        page=query.page,
        size=query.size,
    )


async def get_attendance(attendance_id: int, db: AsyncSession) -> AttendanceResponse:
    """根据ID获取考勤记录"""
    result = await db.execute(
        select(Attendance).where(Attendance.attendance_id == attendance_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise NotFoundException(message="考勤记录不存在", detail=f"attendance_id={attendance_id}")
    return AttendanceResponse.model_validate(record)


async def create_attendance(data: AttendanceCreate, db: AsyncSession) -> AttendanceResponse:
    """
    创建考勤记录

    说明：将 clock_in/clock_out 字符串转换为 time 对象，
         并自动计算考勤状态（如未手动指定）。
    """
    clock_in_time = _parse_time(data.clock_in)
    clock_out_time = _parse_time(data.clock_out)

    # 如果未手动指定状态，则自动计算
    status = data.status if data.status else _calculate_status(clock_in_time, clock_out_time)

    record = Attendance(
        emp_id=data.emp_id,
        attendance_date=data.attendance_date,
        clock_in=clock_in_time,
        clock_out=clock_out_time,
        status=status,
        remark=data.remark,
        create_time=datetime.now(),
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return AttendanceResponse.model_validate(record)


async def update_attendance(
    attendance_id: int, data: AttendanceUpdate, db: AsyncSession
) -> AttendanceResponse:
    """
    更新考勤记录（部分更新）

    说明：如果更新了 clock_in 或 clock_out 且未手动指定 status，
         则重新自动计算状态。
    """
    result = await db.execute(
        select(Attendance).where(Attendance.attendance_id == attendance_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise NotFoundException(message="考勤记录不存在", detail=f"attendance_id={attendance_id}")

    update_data = data.model_dump(exclude_unset=True)

    # 处理 clock_in/clock_out 字符串转换
    if "clock_in" in update_data:
        update_data["clock_in"] = _parse_time(update_data["clock_in"])
    if "clock_out" in update_data:
        update_data["clock_out"] = _parse_time(update_data["clock_out"])

    for field, value in update_data.items():
        setattr(record, field, value)

    # 如果更新了打卡时间但未手动指定状态，重新计算
    if ("clock_in" in update_data or "clock_out" in update_data) and "status" not in update_data:
        record.status = _calculate_status(record.clock_in, record.clock_out)

    await db.flush()
    await db.refresh(record)
    return AttendanceResponse.model_validate(record)


async def delete_attendance(attendance_id: int, db: AsyncSession) -> None:
    """删除考勤记录"""
    result = await db.execute(
        select(Attendance).where(Attendance.attendance_id == attendance_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise NotFoundException(message="考勤记录不存在", detail=f"attendance_id={attendance_id}")
    await db.delete(record)
    await db.flush()
