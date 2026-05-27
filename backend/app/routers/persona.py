"""
人设配置路由（routers/persona.py）

说明：定义 AI 助手人设（Persona）的 CRUD API 端点。
     支持创建、查询、更新、删除人设，以及激活/取消激活操作。

端点列表：
    GET    /api/ai/personas              → 人设列表
    GET    /api/ai/personas/active       → 获取当前激活的人设
    POST   /api/ai/personas              → 创建人设
    PUT    /api/ai/personas/{id}         → 更新人设
    PUT    /api/ai/personas/{id}/activate → 激活人设
    DELETE /api/ai/personas/{id}         → 删除人设
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import get_current_user
from app.models.persona import PersonaConfig
from app.schemas.common import ApiResponse, fail, ok
from app.schemas.persona import PersonaCreate, PersonaResponse, PersonaUpdate

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/personas", response_model=ApiResponse[list[PersonaResponse]])
async def list_personas(
    db: AsyncSession = Depends(get_session),
    _current_user=Depends(get_current_user),
):
    """查询所有人设列表"""
    stmt = select(PersonaConfig).order_by(PersonaConfig.is_active.desc(), PersonaConfig.id)
    result = await db.execute(stmt)
    personas = result.scalars().all()
    return ok(data=[PersonaResponse.model_validate(p) for p in personas])


@router.get("/personas/active", response_model=ApiResponse[PersonaResponse])
async def get_active_persona(
    db: AsyncSession = Depends(get_session),
    _current_user=Depends(get_current_user),
):
    """获取当前激活的人设"""
    stmt = select(PersonaConfig).where(PersonaConfig.is_active.is_(True))
    result = await db.execute(stmt)
    persona = result.scalar_one_or_none()
    if not persona:
        return fail(message="没有激活的人设")
    return ok(data=PersonaResponse.model_validate(persona))


@router.post("/personas", response_model=ApiResponse[PersonaResponse])
async def create_persona(
    req: PersonaCreate,
    db: AsyncSession = Depends(get_session),
    _current_user=Depends(get_current_user),
):
    """创建新的人设"""
    # 检查名称是否重复
    stmt = select(PersonaConfig).where(PersonaConfig.name == req.name)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        return fail(message=f"人设名称 '{req.name}' 已存在")

    now = datetime.now()
    persona = PersonaConfig(
        name=req.name,
        content=req.content,
        description=req.description,
        is_active=False,
        create_time=now,
        update_time=now,
    )
    db.add(persona)
    await db.flush()
    await db.refresh(persona)
    logger.info(f"创建人设: id={persona.id}, name={persona.name}")
    return ok(data=PersonaResponse.model_validate(persona), message="创建成功")


@router.put("/personas/{persona_id}", response_model=ApiResponse[PersonaResponse])
async def update_persona(
    persona_id: int,
    req: PersonaUpdate,
    db: AsyncSession = Depends(get_session),
    _current_user=Depends(get_current_user),
):
    """更新人设内容"""
    persona = await db.get(PersonaConfig, persona_id)
    if not persona:
        return fail(message="人设不存在")

    if req.name is not None:
        # 检查名称冲突
        stmt = select(PersonaConfig).where(PersonaConfig.name == req.name, PersonaConfig.id != persona_id)
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            return fail(message=f"人设名称 '{req.name}' 已存在")
        persona.name = req.name

    if req.content is not None:
        persona.content = req.content

    if req.description is not None:
        persona.description = req.description

    persona.update_time = datetime.now()
    await db.flush()
    await db.refresh(persona)
    logger.info(f"更新人设: id={persona.id}, name={persona.name}")
    return ok(data=PersonaResponse.model_validate(persona), message="更新成功")


@router.put("/personas/{persona_id}/activate", response_model=ApiResponse)
async def activate_persona(
    persona_id: int,
    db: AsyncSession = Depends(get_session),
    _current_user=Depends(get_current_user),
):
    """激活指定人设（同时取消其他已激活的人设）"""
    persona = await db.get(PersonaConfig, persona_id)
    if not persona:
        return fail(message="人设不存在")

    # 取消所有已激活的人设
    stmt = select(PersonaConfig).where(PersonaConfig.is_active.is_(True))
    result = await db.execute(stmt)
    for p in result.scalars().all():
        p.is_active = False

    # 激活目标人设
    persona.is_active = True
    persona.update_time = datetime.now()
    await db.flush()
    logger.info(f"激活人设: id={persona.id}, name={persona.name}")
    return ok(message=f"已激活人设 '{persona.name}'")


@router.delete("/personas/{persona_id}", response_model=ApiResponse)
async def delete_persona(
    persona_id: int,
    db: AsyncSession = Depends(get_session),
    _current_user=Depends(get_current_user),
):
    """删除人设"""
    persona = await db.get(PersonaConfig, persona_id)
    if not persona:
        return fail(message="人设不存在")

    if persona.is_active:
        return fail(message="不能删除当前激活的人设，请先激活其他人设")

    await db.delete(persona)
    await db.flush()
    logger.info(f"删除人设: id={persona.id}, name={persona.name}")
    return ok(message="删除成功")
