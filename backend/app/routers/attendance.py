"""
考勤管理路由（routers/attendance.py）

说明：定义考勤模块的 API 端点，包括分页查询、详情、创建、更新、删除。
     对应 Java 的 AttendanceController 类。

端点列表：
    GET    /                    → 分页查询考勤记录
    GET    /{attendance_id}     → 获取考勤记录详情
    POST   /                    → 创建考勤记录
    PUT    /{attendance_id}     → 更新考勤记录
    DELETE /{attendance_id}     → 删除考勤记录
"""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_mysql_session
from app.core.dependencies import TokenPayload, require_permission
from app.schemas.attendance import AttendanceCreate, AttendanceQuery, AttendanceResponse, AttendanceUpdate
from app.schemas.common import ApiResponse, PageResponse, ok
from app.services import attendance_service

router = APIRouter()


@router.get("", summary="分页查询考勤记录")
async def list_attendance(
    page: int = Query(default=1, ge=1, description="页码"),
    size: int = Query(default=10, ge=1, le=500, description="每页大小"),
    emp_id: int | None = Query(default=None, description="员工ID筛选"),
    status: str | None = Query(default=None, description="考勤状态筛选"),
    start_date: date | None = Query(default=None, description="开始日期"),
    end_date: date | None = Query(default=None, description="结束日期"),
    current_user: TokenPayload = Depends(require_permission("attendance:record:view")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[PageResponse[AttendanceResponse]]:
    """分页查询考勤记录，支持员工、状态和日期范围筛选"""
    query = AttendanceQuery(
        page=page, size=size, emp_id=emp_id, status=status,
        start_date=start_date, end_date=end_date,
    )
    result = await attendance_service.list_attendance(query, db)
    return ok(data=result)


@router.get("/{attendance_id}", summary="获取考勤记录详情")
async def get_attendance(
    attendance_id: int,
    current_user: TokenPayload = Depends(require_permission("attendance:record:view")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[AttendanceResponse]:
    """根据ID获取考勤记录详情"""
    result = await attendance_service.get_attendance(attendance_id, db)
    return ok(data=result)


@router.post("", summary="创建考勤记录")
async def create_attendance(
    data: AttendanceCreate,
    current_user: TokenPayload = Depends(require_permission("attendance:record:add")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[AttendanceResponse]:
    """创建考勤记录（自动计算考勤状态）"""
    result = await attendance_service.create_attendance(data, db)
    return ok(data=result, message="创建成功")


@router.put("/{attendance_id}", summary="更新考勤记录")
async def update_attendance(
    attendance_id: int,
    data: AttendanceUpdate,
    current_user: TokenPayload = Depends(require_permission("attendance:record:edit")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[AttendanceResponse]:
    """更新考勤记录"""
    result = await attendance_service.update_attendance(attendance_id, data, db)
    return ok(data=result, message="更新成功")


@router.delete("/{attendance_id}", summary="删除考勤记录")
async def delete_attendance(
    attendance_id: int,
    current_user: TokenPayload = Depends(require_permission("attendance:record:view")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[None]:
    """删除考勤记录"""
    await attendance_service.delete_attendance(attendance_id, db)
    return ok(message="删除成功")
