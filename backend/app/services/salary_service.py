"""
薪资管理服务（services/salary_service.py）

说明：实现薪资配置和薪资记录的增删改查和分页查询功能。
     对应 Java 的 SalaryConfigService 和 SalaryRecordService 类。
"""

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.models.salary import SalaryConfig, SalaryRecord
from app.schemas.common import PageResponse
from app.schemas.salary import (
    SalaryConfigCreate,
    SalaryConfigResponse,
    SalaryConfigUpdate,
    SalaryRecordCreate,
    SalaryRecordQuery,
    SalaryRecordResponse,
    SalaryRecordUpdate,
)


# ============================================================
# 薪资配置 CRUD
# ============================================================


async def list_salary_configs(
    page: int, size: int, keyword: str | None, status: str | None, db: AsyncSession
) -> PageResponse[SalaryConfigResponse]:
    """
    分页查询薪资配置

    支持筛选条件：
        - keyword: 模糊匹配配置名称或配置键
        - status: 状态精确匹配
    """
    stmt = select(SalaryConfig)
    count_stmt = select(func.count()).select_from(SalaryConfig)

    if keyword:
        like_pattern = f"%{keyword.strip()}%"
        keyword_filter = or_(
            SalaryConfig.config_name.like(like_pattern),
            SalaryConfig.config_key.like(like_pattern),
        )
        stmt = stmt.where(keyword_filter)
        count_stmt = count_stmt.where(keyword_filter)

    if status:
        stmt = stmt.where(SalaryConfig.status == status)
        count_stmt = count_stmt.where(SalaryConfig.status == status)

    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    stmt = stmt.offset((page - 1) * size).limit(size)
    result = await db.execute(stmt)
    configs = result.scalars().all()

    return PageResponse(
        items=[SalaryConfigResponse.model_validate(c) for c in configs],
        total=total,
        page=page,
        size=size,
    )


async def get_salary_config(config_id: int, db: AsyncSession) -> SalaryConfigResponse:
    """根据ID获取薪资配置"""
    result = await db.execute(select(SalaryConfig).where(SalaryConfig.config_id == config_id))
    config = result.scalar_one_or_none()
    if not config:
        raise NotFoundException(message="薪资配置不存在", detail=f"config_id={config_id}")
    return SalaryConfigResponse.model_validate(config)


async def create_salary_config(data: SalaryConfigCreate, db: AsyncSession) -> SalaryConfigResponse:
    """创建薪资配置"""
    now = datetime.now()
    config = SalaryConfig(
        **data.model_dump(),
        create_time=now,
        update_time=now,
    )
    db.add(config)
    await db.flush()
    await db.refresh(config)
    return SalaryConfigResponse.model_validate(config)


async def update_salary_config(
    config_id: int, data: SalaryConfigUpdate, db: AsyncSession
) -> SalaryConfigResponse:
    """更新薪资配置（部分更新）"""
    result = await db.execute(select(SalaryConfig).where(SalaryConfig.config_id == config_id))
    config = result.scalar_one_or_none()
    if not config:
        raise NotFoundException(message="薪资配置不存在", detail=f"config_id={config_id}")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(config, field, value)
    config.update_time = datetime.now()

    await db.flush()
    await db.refresh(config)
    return SalaryConfigResponse.model_validate(config)


async def delete_salary_config(config_id: int, db: AsyncSession) -> None:
    """删除薪资配置"""
    result = await db.execute(select(SalaryConfig).where(SalaryConfig.config_id == config_id))
    config = result.scalar_one_or_none()
    if not config:
        raise NotFoundException(message="薪资配置不存在", detail=f"config_id={config_id}")
    await db.delete(config)
    await db.flush()


# ============================================================
# 薪资记录 CRUD
# ============================================================


async def list_salary_records(query: SalaryRecordQuery, db: AsyncSession) -> PageResponse[SalaryRecordResponse]:
    """
    分页查询薪资记录

    支持筛选条件：
        - emp_id: 员工ID精确匹配
        - status: 审批状态精确匹配
        - month_start / month_end: 薪资月份范围
    """
    stmt = select(SalaryRecord)
    count_stmt = select(func.count()).select_from(SalaryRecord)

    if query.emp_id is not None:
        stmt = stmt.where(SalaryRecord.emp_id == query.emp_id)
        count_stmt = count_stmt.where(SalaryRecord.emp_id == query.emp_id)

    if query.status:
        stmt = stmt.where(SalaryRecord.status == query.status)
        count_stmt = count_stmt.where(SalaryRecord.status == query.status)

    if query.month_start:
        stmt = stmt.where(SalaryRecord.salary_month >= query.month_start)
        count_stmt = count_stmt.where(SalaryRecord.salary_month >= query.month_start)

    if query.month_end:
        stmt = stmt.where(SalaryRecord.salary_month <= query.month_end)
        count_stmt = count_stmt.where(SalaryRecord.salary_month <= query.month_end)

    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    stmt = stmt.offset((query.page - 1) * query.size).limit(query.size)
    result = await db.execute(stmt)
    records = result.scalars().all()

    return PageResponse(
        items=[SalaryRecordResponse.model_validate(r) for r in records],
        total=total,
        page=query.page,
        size=query.size,
    )


async def get_salary_record(salary_id: int, db: AsyncSession) -> SalaryRecordResponse:
    """根据ID获取薪资记录"""
    result = await db.execute(select(SalaryRecord).where(SalaryRecord.salary_id == salary_id))
    record = result.scalar_one_or_none()
    if not record:
        raise NotFoundException(message="薪资记录不存在", detail=f"salary_id={salary_id}")
    return SalaryRecordResponse.model_validate(record)


async def create_salary_record(data: SalaryRecordCreate, db: AsyncSession) -> SalaryRecordResponse:
    """创建薪资记录"""
    now = datetime.now()
    record = SalaryRecord(
        **data.model_dump(),
        create_time=now,
        update_time=now,
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return SalaryRecordResponse.model_validate(record)


async def update_salary_record(
    salary_id: int, data: SalaryRecordUpdate, db: AsyncSession
) -> SalaryRecordResponse:
    """更新薪资记录（部分更新）"""
    result = await db.execute(select(SalaryRecord).where(SalaryRecord.salary_id == salary_id))
    record = result.scalar_one_or_none()
    if not record:
        raise NotFoundException(message="薪资记录不存在", detail=f"salary_id={salary_id}")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(record, field, value)
    record.update_time = datetime.now()

    await db.flush()
    await db.refresh(record)
    return SalaryRecordResponse.model_validate(record)


async def delete_salary_record(salary_id: int, db: AsyncSession) -> None:
    """删除薪资记录"""
    result = await db.execute(select(SalaryRecord).where(SalaryRecord.salary_id == salary_id))
    record = result.scalar_one_or_none()
    if not record:
        raise NotFoundException(message="薪资记录不存在", detail=f"salary_id={salary_id}")
    await db.delete(record)
    await db.flush()
