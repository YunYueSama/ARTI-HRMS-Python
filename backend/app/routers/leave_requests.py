"""
请假管理路由（routers/leave_requests.py）

说明：定义请假模块的 API 端点，包括申请、审批、取消和查询。
     对应 Java 的 LeaveRequestController 类。

端点列表：
    GET    /                    → 分页查询请假记录
    GET    /{leave_id}          → 获取请假详情
    POST   /                    → 创建请假申请
    POST   /{leave_id}/approve  → 审批请假（通过/驳回）
    POST   /{leave_id}/cancel   → 取消请假申请
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_mysql_session
from app.core.dependencies import TokenPayload, get_current_user, require_permission
from app.schemas.common import ApiResponse, PageResponse, ok
from app.schemas.leave_request import (
    LeaveApprovalAction,
    LeaveRequestCreate,
    LeaveRequestQuery,
    LeaveRequestResponse,
)
from app.services import leave_service

router = APIRouter()


@router.get("", summary="分页查询请假记录")
async def list_leave_requests(
    page: int = Query(default=1, ge=1, description="页码"),
    size: int = Query(default=10, ge=1, le=500, description="每页大小"),
    emp_id: int | None = Query(default=None, description="员工ID筛选"),
    status: str | None = Query(default=None, description="审批状态筛选"),
    current_user: TokenPayload = Depends(require_permission("attendance:leave:view")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[PageResponse[LeaveRequestResponse]]:
    """分页查询请假记录，支持员工和状态筛选"""
    query = LeaveRequestQuery(page=page, size=size, emp_id=emp_id, status=status)
    result = await leave_service.list_leave_requests(query, db)
    return ok(data=result)


@router.get("/{leave_id}", summary="获取请假详情")
async def get_leave_request(
    leave_id: int,
    current_user: TokenPayload = Depends(require_permission("attendance:leave:view")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[LeaveRequestResponse]:
    """根据ID获取请假详情"""
    result = await leave_service.get_leave_request(leave_id, db)
    return ok(data=result)


@router.post("", summary="创建请假申请")
async def create_leave_request(
    data: LeaveRequestCreate,
    current_user: TokenPayload = Depends(require_permission("attendance:leave:add")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[LeaveRequestResponse]:
    """创建请假申请，自动设置审批链"""
    result = await leave_service.create_leave_request(data, db)
    return ok(data=result, message="申请提交成功")


@router.post("/{leave_id}/approve", summary="审批请假")
async def approve_leave_request(
    leave_id: int,
    action_data: LeaveApprovalAction,
    current_user: TokenPayload = Depends(require_permission("attendance:leave:approve")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[LeaveRequestResponse]:
    """审批请假申请（通过或驳回）"""
    result = await leave_service.approve_leave(leave_id, action_data, current_user.user_id, db)
    return ok(data=result, message="审批完成")


@router.post("/{leave_id}/cancel", summary="取消请假申请")
async def cancel_leave_request(
    leave_id: int,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[LeaveRequestResponse]:
    """取消请假申请（仅限申请人本人，且状态为待审批）"""
    result = await leave_service.cancel_leave(leave_id, current_user.user_id, db)
    return ok(data=result, message="已取消")


@router.post("/{leave_id}/reject", summary="驳回请假申请")
async def reject_leave_request(
    leave_id: int,
    action_data: LeaveApprovalAction,
    current_user: TokenPayload = Depends(require_permission("attendance:leave:approve")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[LeaveRequestResponse]:
    """驳回请假申请（独立的驳回端点，前端通过 /leave-requests/{leaveId}/reject 调用）"""
    # 构造 reject action（忽略前端传入的 action 字段，强制为 reject）
    reject_action = LeaveApprovalAction(action="reject", approver_remark=action_data.approver_remark)
    result = await leave_service.approve_leave(leave_id, reject_action, current_user.user_id, db)
    return ok(data=result, message="已驳回")
