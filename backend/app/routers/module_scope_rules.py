"""
模块数据范围规则路由（routers/module_scope_rules.py）

说明：定义模块数据范围规则的 API 端点。
     对应 Java 的 ModuleScopeRuleController 类。

端点列表：
    GET  /configs              → 获取所有模块范围配置
    GET  /                     → 分页查询模块范围规则列表
    PUT  /{module_code}/config → 更新模块范围配置
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_mysql_session
from app.core.dependencies import TokenPayload, require_permission
from app.core.exceptions import NotFoundException
from app.models.module_scope import ModuleScopeRule
from app.schemas.common import ApiResponse, PageResponse, ok

router = APIRouter()


@router.get("/configs", summary="获取所有模块范围配置")
async def get_module_scope_configs(
    current_user: TokenPayload = Depends(require_permission("permission:module-scope:view")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse:
    """获取所有模块的数据范围配置列表"""
    stmt = select(ModuleScopeRule)
    result = await db.execute(stmt)
    rules = result.scalars().all()

    configs = [
        {
            "moduleCode": r.module_code,
            "moduleName": r.module_name,
            "defaultScope": r.default_scope,
            "createTime": r.create_time.isoformat() if r.create_time else None,
            "updateTime": r.update_time.isoformat() if r.update_time else None,
        }
        for r in rules
    ]
    return ok(data=configs)


@router.get("", summary="分页查询模块范围规则列表")
async def list_module_scope_rules(
    page: int = Query(default=1, ge=1, description="页码"),
    size: int = Query(default=10, ge=1, le=500, description="每页大小"),
    current_user: TokenPayload = Depends(require_permission("permission:module-scope:view")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse:
    """分页查询模块范围规则列表"""
    count_stmt = select(func.count()).select_from(ModuleScopeRule)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    stmt = select(ModuleScopeRule).offset((page - 1) * size).limit(size)
    result = await db.execute(stmt)
    rules = result.scalars().all()

    items = [
        {
            "moduleCode": r.module_code,
            "moduleName": r.module_name,
            "defaultScope": r.default_scope,
            "createTime": r.create_time.isoformat() if r.create_time else None,
            "updateTime": r.update_time.isoformat() if r.update_time else None,
        }
        for r in rules
    ]

    page_data = PageResponse(items=items, total=total, page=page, size=size)
    return ok(data=page_data)


@router.put("/{module_code}/config", summary="更新模块范围配置")
async def update_module_scope_config(
    module_code: str,
    data: dict,
    current_user: TokenPayload = Depends(require_permission("permission:module-scope:view")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse:
    """更新指定模块的数据范围配置"""
    result = await db.execute(select(ModuleScopeRule).where(ModuleScopeRule.module_code == module_code))
    rule = result.scalar_one_or_none()
    if not rule:
        raise NotFoundException(message="模块范围规则不存在", detail=f"module_code={module_code}")

    if "defaultScope" in data:
        rule.default_scope = data["defaultScope"]
    if "default_scope" in data:
        rule.default_scope = data["default_scope"]
    if "moduleName" in data:
        rule.module_name = data["moduleName"]
    if "module_name" in data:
        rule.module_name = data["module_name"]

    rule.update_time = datetime.now()
    await db.flush()
    await db.refresh(rule)

    return ok(
        data={
            "moduleCode": rule.module_code,
            "moduleName": rule.module_name,
            "defaultScope": rule.default_scope,
            "updateTime": rule.update_time.isoformat() if rule.update_time else None,
        },
        message="更新成功",
    )
