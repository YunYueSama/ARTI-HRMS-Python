"""
审批规则类型路由（routers/approval_rule_types.py）

说明：定义审批规则类型的 API 端点。
     对应 Java 的 ApprovalRuleTypeController 类。

端点列表：
    GET  /all  → 获取所有审批规则类型
    POST /     → 创建审批规则类型
"""

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_mysql_session
from app.core.dependencies import TokenPayload, require_permission
from app.models.approval import ApprovalRuleType
from app.schemas.common import ApiResponse, ok

router = APIRouter()


class ApprovalRuleTypeCreate(BaseModel):
    """审批规则类型创建请求"""

    type_code: str = Field(min_length=1, description="类型编码")
    type_name: str | None = Field(default=None, description="类型名称")
    type_desc: str | None = Field(default=None, description="类型描述")
    status: str | None = Field(default="active", description="状态")


@router.get("/all", summary="获取所有审批规则类型")
async def list_all_approval_rule_types(
    current_user: TokenPayload = Depends(require_permission("permission:approval-rule:view")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse:
    """获取所有审批规则类型列表"""
    stmt = select(ApprovalRuleType)
    result = await db.execute(stmt)
    types = result.scalars().all()

    items = [
        {
            "typeCode": t.type_code,
            "typeName": t.type_name,
            "typeDesc": t.type_desc,
            "status": t.status,
            "createTime": t.create_time.isoformat() if t.create_time else None,
            "updateTime": t.update_time.isoformat() if t.update_time else None,
        }
        for t in types
    ]
    return ok(data=items)


@router.post("", summary="创建审批规则类型")
async def create_approval_rule_type(
    data: ApprovalRuleTypeCreate,
    current_user: TokenPayload = Depends(require_permission("permission:approval-rule:view")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse:
    """创建新的审批规则类型"""
    now = datetime.now()
    rule_type = ApprovalRuleType(
        type_code=data.type_code,
        type_name=data.type_name,
        type_desc=data.type_desc,
        status=data.status or "active",
        create_time=now,
        update_time=now,
    )
    db.add(rule_type)
    await db.flush()
    await db.refresh(rule_type)

    return ok(
        data={
            "typeCode": rule_type.type_code,
            "typeName": rule_type.type_name,
            "typeDesc": rule_type.type_desc,
            "status": rule_type.status,
            "createTime": rule_type.create_time.isoformat() if rule_type.create_time else None,
        },
        message="创建成功",
    )
