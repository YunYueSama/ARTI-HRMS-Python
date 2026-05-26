"""
模块数据范围规则路由（routers/module_scope_rules.py）

说明：定义模块数据范围规则的 API 端点。
     对应 Java 的 ModuleScopeRuleController 类。

端点列表：
    GET  /configs              → 获取所有模块范围配置（含身份标签范围）
    GET  /                     → 分页查询模块范围规则列表
    PUT  /{module_code}/config → 更新模块范围配置（含身份标签范围）
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_mysql_session
from app.core.dependencies import TokenPayload, require_permission
from app.core.exceptions import NotFoundException
from app.models.module_scope import ModuleScopeDetail, ModuleScopeRule
from app.schemas.common import ApiResponse, PageResponse, ok

router = APIRouter()


@router.get("/configs", summary="获取所有模块范围配置")
async def get_module_scope_configs(
    current_user: TokenPayload = Depends(require_permission("permission:module-scope:view")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse:
    """获取所有模块的数据范围配置列表（含身份标签范围）"""
    stmt = select(ModuleScopeRule)
    result = await db.execute(stmt)
    rules = result.scalars().all()

    # 查询所有模块的身份标签范围明细
    detail_stmt = select(ModuleScopeDetail)
    detail_result = await db.execute(detail_stmt)
    details = detail_result.scalars().all()

    # 按 module_code 分组构建 tagScopes
    tag_scopes_map: dict[str, dict[str, str]] = {}
    for d in details:
        if d.module_code and d.tag_code and d.scope:
            tag_scopes_map.setdefault(d.module_code, {})[d.tag_code] = d.scope

    configs = [
        {
            "moduleCode": r.module_code,
            "moduleName": r.module_name,
            "defaultScope": r.default_scope,
            "tagScopes": tag_scopes_map.get(r.module_code, {}),
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
    current_user: TokenPayload = Depends(require_permission("permission:module-scope:edit")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse:
    """更新指定模块的数据范围配置（含身份标签范围）"""
    result = await db.execute(select(ModuleScopeRule).where(ModuleScopeRule.module_code == module_code))
    rule = result.scalar_one_or_none()
    if not rule:
        raise NotFoundException(message="模块范围规则不存在", detail=f"module_code={module_code}")

    # 更新模块默认范围
    if "defaultScope" in data:
        rule.default_scope = data["defaultScope"]
    if "default_scope" in data:
        rule.default_scope = data["default_scope"]
    if "moduleName" in data:
        rule.module_name = data["moduleName"]
    if "module_name" in data:
        rule.module_name = data["module_name"]

    rule.update_time = datetime.now()

    # 更新身份标签范围明细（请求拦截器将 tagScopes 转为 tag_scopes）
    tag_scopes = data.get("tagScopes") or data.get("tag_scopes")
    if tag_scopes is not None and isinstance(tag_scopes, dict):
        # 先删除该模块所有旧的明细记录
        await db.execute(delete(ModuleScopeDetail).where(ModuleScopeDetail.module_code == module_code))

        # 再插入新的明细记录
        now = datetime.now()
        for tag_code, scope in tag_scopes.items():
            if scope:  # 跳过空值
                detail = ModuleScopeDetail(
                    module_code=module_code,
                    tag_code=tag_code,
                    scope=scope,
                    create_time=now,
                    update_time=now,
                )
                db.add(detail)

    await db.flush()
    await db.refresh(rule)

    # 返回更新后的 tagScopes
    tag_scopes_result = {}
    if tag_scopes is not None:
        tag_scopes_result = {k: v for k, v in tag_scopes.items() if v}
    else:
        # 重新查询
        detail_stmt = select(ModuleScopeDetail).where(ModuleScopeDetail.module_code == module_code)
        detail_result = await db.execute(detail_stmt)
        for d in detail_result.scalars().all():
            if d.tag_code and d.scope:
                tag_scopes_result[d.tag_code] = d.scope

    return ok(
        data={
            "moduleCode": rule.module_code,
            "moduleName": rule.module_name,
            "defaultScope": rule.default_scope,
            "tagScopes": tag_scopes_result,
            "updateTime": rule.update_time.isoformat() if rule.update_time else None,
        },
        message="更新成功",
    )
