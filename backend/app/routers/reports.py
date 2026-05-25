"""
报表统计路由（routers/reports.py）

说明：定义报表统计模块的 API 端点。
     对应 Java 的 ReportController 类。

端点列表：
    GET /summary  → 获取报表汇总数据
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_mysql_session
from app.core.dependencies import TokenPayload, get_current_user
from app.schemas.common import ok
from app.services import report_service

router = APIRouter()


@router.get("/summary", summary="获取报表汇总数据")
async def get_report_summary(
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_mysql_session),
):
    """
    获取报表汇总数据

    包含员工总数、本月新入职、出勤率、请假人次、各部门人数统计。
    """
    result = await report_service.get_summary(db)
    return ok(data=result)
