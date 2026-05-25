"""
审批规则路由（routers/approval_rules.py）

说明：定义审批规则的 CRUD API 端点。
     对应 Java 的 ApprovalRuleController 类。

端点列表：
    GET    /            → 分页查询审批规则列表
    POST   /            → 创建审批规则
    PUT    /{rule_id}   → 更新审批规则
    DELETE /{rule_id}   → 删除审批规则
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_mysql_session
from app.core.dependencies import TokenPayload, require_permission
from app.core.exceptions import NotFoundException
from app.models.approval import ApprovalRule
from app.schemas.common import ApiResponse, PageResponse, ok

router = APIRouter()


class ApprovalRuleCreate(BaseModel):
    """审批规则创建请求"""

    type_code: Optional[str] = Field(default=None, description="审批类型编码")
    applicant_tag: Optional[str] = Field(default=None, description="申请人身份标签")
    days_op: Optional[str] = Field(default=None, description="天数比较运算符")
    days_value: Optional[Decimal] = Field(default=None, description="天数阈值")
    first_approver_tag: Optional[str] = Field(default=None, description="第一级审批人标签")
    second_approver_tag: Optional[str] = Field(default=None, description="第二级审批人标签")
    second_approver_scope: Optional[str] = Field(default=None, description="第二级审批人范围")
    sort_order: Optional[int] = Field(default=None, description="排序序号")


class ApprovalRuleUpdate(BaseModel):
    """审批规则更新请求"""

    type_code: Optional[str] = Field(default=None, description="审批类型编码")
    applicant_tag: Optional[str] = Field(default=None, description="申请人身份标签")
    days_op: Optional[str] = Field(default=None, description="天数比较运算符")
    days_value: Optional[Decimal] = Field(default=None, description="天数阈值")
    first_approver_tag: Optional[str] = Field(default=None, description="第一级审批人标签")
    second_approver_tag: Optional[str] = Field(default=None, description="第二级审批人标签")
    second_approver_scope: Optional[str] = Field(default=None, description="第二级审批人范围")
    sort_order: Optional[int] = Field(default=None, description="排序序号")


def _rule_to_dict(rule: ApprovalRule) -> dict:
    """将 ApprovalRule ORM 对象转为响应字典"""
    return {
        "ruleId": rule.rule_id,
        "typeCode": rule.type_code,
        "applicantTag": rule.applicant_tag,
        "daysOp": rule.days_op,
        "daysValue": str(rule.days_value) if rule.days_value is not None else None,
        "firstApproverTag": rule.first_approver_tag,
        "secondApproverTag": rule.second_approver_tag,
        "secondApproverScope": rule.second_approver_scope,
        "sortOrder": rule.sort_order,
        "createTime": rule.create_time.isoformat() if rule.create_time else None,
        "updateTime": rule.update_time.isoformat() if rule.update_time else None,
    }


@router.get("", summary="分页查询审批规则列表")
async def list_approval_rules(
    page: int = Query(default=1, ge=1, description="页码"),
    size: int = Query(default=10, ge=1, le=500, description="每页大小"),
    type_code: Optional[str] = Query(default=None, description="审批类型编码筛选"),
    current_user: TokenPayload = Depends(require_permission("permission:approval-rule:view")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse:
    """分页查询审批规则列表"""
    stmt = select(ApprovalRule)
    count_stmt = select(func.count()).select_from(ApprovalRule)

    if type_code:
        stmt = stmt.where(ApprovalRule.type_code == type_code)
        count_stmt = count_stmt.where(ApprovalRule.type_code == type_code)

    # 排序
    stmt = stmt.order_by(ApprovalRule.sort_order)

    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    stmt = stmt.offset((page - 1) * size).limit(size)
    result = await db.execute(stmt)
    rules = result.scalars().all()

    items = [_rule_to_dict(r) for r in rules]
    page_data = PageResponse(items=items, total=total, page=page, size=size)
    return ok(data=page_data)


@router.post("", summary="创建审批规则")
async def create_approval_rule(
    data: ApprovalRuleCreate,
    current_user: TokenPayload = Depends(require_permission("permission:approval-rule:view")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse:
    """创建新的审批规则"""
    now = datetime.now()
    rule = ApprovalRule(
        type_code=data.type_code,
        applicant_tag=data.applicant_tag,
        days_op=data.days_op,
        days_value=data.days_value,
        first_approver_tag=data.first_approver_tag,
        second_approver_tag=data.second_approver_tag,
        second_approver_scope=data.second_approver_scope,
        sort_order=data.sort_order,
        create_time=now,
        update_time=now,
    )
    db.add(rule)
    await db.flush()
    await db.refresh(rule)
    return ok(data=_rule_to_dict(rule), message="创建成功")


@router.put("/{rule_id}", summary="更新审批规则")
async def update_approval_rule(
    rule_id: int,
    data: ApprovalRuleUpdate,
    current_user: TokenPayload = Depends(require_permission("permission:approval-rule:view")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse:
    """更新审批规则"""
    result = await db.execute(
        select(ApprovalRule).where(ApprovalRule.rule_id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise NotFoundException(message="审批规则不存在", detail=f"rule_id={rule_id}")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(rule, field, value)
    rule.update_time = datetime.now()

    await db.flush()
    await db.refresh(rule)
    return ok(data=_rule_to_dict(rule), message="更新成功")


@router.delete("/{rule_id}", summary="删除审批规则")
async def delete_approval_rule(
    rule_id: int,
    current_user: TokenPayload = Depends(require_permission("permission:approval-rule:view")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse:
    """删除审批规则"""
    result = await db.execute(
        select(ApprovalRule).where(ApprovalRule.rule_id == rule_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise NotFoundException(message="审批规则不存在", detail=f"rule_id={rule_id}")
    await db.delete(rule)
    await db.flush()
    return ok(message="删除成功")
