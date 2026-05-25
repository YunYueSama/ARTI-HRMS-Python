"""
职位管理路由（routers/job_positions.py）

说明：定义职位模块的 API 端点，包括分页查询、详情、创建、更新、删除。
     对应 Java 的 JobPositionController 类。

端点列表：
    GET    /                → 分页查询职位列表
    GET    /{position_id}   → 获取职位详情
    POST   /                → 创建职位
    PUT    /{position_id}   → 更新职位
    DELETE /{position_id}   → 删除职位
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_mysql_session
from app.core.dependencies import TokenPayload, require_permission
from app.core.exceptions import NotFoundException
from app.models.job_position import JobPosition
from app.schemas.common import ApiResponse, PageResponse, ok
from app.schemas.job_position import JobPositionCreate, JobPositionResponse, JobPositionUpdate

router = APIRouter()


@router.get("", summary="分页查询职位列表")
async def list_job_positions(
    page: int = Query(default=1, ge=1, description="页码"),
    size: int = Query(default=10, ge=1, le=500, description="每页大小"),
    keyword: str | None = Query(default=None, description="搜索关键词"),
    dept_id: int | None = Query(default=None, description="部门ID筛选"),
    current_user: TokenPayload = Depends(require_permission("base:position:view")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[PageResponse[JobPositionResponse]]:
    """分页查询职位列表，支持关键词搜索和部门筛选"""
    stmt = select(JobPosition)
    count_stmt = select(func.count()).select_from(JobPosition)

    if keyword:
        like_pattern = f"%{keyword.strip()}%"
        stmt = stmt.where(JobPosition.position_name.like(like_pattern))
        count_stmt = count_stmt.where(JobPosition.position_name.like(like_pattern))

    if dept_id is not None:
        stmt = stmt.where(JobPosition.dept_id == dept_id)
        count_stmt = count_stmt.where(JobPosition.dept_id == dept_id)

    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    stmt = stmt.offset((page - 1) * size).limit(size)
    result = await db.execute(stmt)
    positions = result.scalars().all()

    page_data = PageResponse(
        items=[JobPositionResponse.model_validate(p) for p in positions],
        total=total,
        page=page,
        size=size,
    )
    return ok(data=page_data)


@router.get("/{position_id}", summary="获取职位详情")
async def get_job_position(
    position_id: int,
    current_user: TokenPayload = Depends(require_permission("base:position:view")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[JobPositionResponse]:
    """根据ID获取职位详情"""
    result = await db.execute(select(JobPosition).where(JobPosition.position_id == position_id))
    position = result.scalar_one_or_none()
    if not position:
        raise NotFoundException(message="职位不存在", detail=f"position_id={position_id}")
    return ok(data=JobPositionResponse.model_validate(position))


@router.post("", summary="创建职位")
async def create_job_position(
    data: JobPositionCreate,
    current_user: TokenPayload = Depends(require_permission("base:position:add")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[JobPositionResponse]:
    """创建新职位"""
    now = datetime.now()
    position = JobPosition(**data.model_dump(), create_time=now, update_time=now)
    db.add(position)
    await db.flush()
    await db.refresh(position)
    return ok(data=JobPositionResponse.model_validate(position), message="创建成功")


@router.put("/{position_id}", summary="更新职位")
async def update_job_position(
    position_id: int,
    data: JobPositionUpdate,
    current_user: TokenPayload = Depends(require_permission("base:position:edit")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[JobPositionResponse]:
    """更新职位信息"""
    result = await db.execute(select(JobPosition).where(JobPosition.position_id == position_id))
    position = result.scalar_one_or_none()
    if not position:
        raise NotFoundException(message="职位不存在", detail=f"position_id={position_id}")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(position, field, value)
    position.update_time = datetime.now()

    await db.flush()
    await db.refresh(position)
    return ok(data=JobPositionResponse.model_validate(position), message="更新成功")


@router.delete("/{position_id}", summary="删除职位")
async def delete_job_position(
    position_id: int,
    current_user: TokenPayload = Depends(require_permission("base:position:delete")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[None]:
    """删除职位"""
    result = await db.execute(select(JobPosition).where(JobPosition.position_id == position_id))
    position = result.scalar_one_or_none()
    if not position:
        raise NotFoundException(message="职位不存在", detail=f"position_id={position_id}")
    await db.delete(position)
    await db.flush()
    return ok(message="删除成功")
