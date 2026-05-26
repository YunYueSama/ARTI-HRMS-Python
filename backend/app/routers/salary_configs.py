"""
薪资配置路由（routers/salary_configs.py）

说明：定义薪资配置模块的 API 端点。
     对应 Java 的 SalaryConfigController 类。

端点列表：
    GET    /                → 分页查询薪资配置
    GET    /{config_id}     → 获取薪资配置详情
    POST   /                → 创建薪资配置
    PUT    /{config_id}     → 更新薪资配置
    DELETE /{config_id}     → 删除薪资配置
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_mysql_session
from app.core.dependencies import TokenPayload, require_permission
from app.schemas.common import ApiResponse, PageResponse, ok
from app.schemas.salary import SalaryConfigCreate, SalaryConfigResponse, SalaryConfigUpdate
from app.services import salary_service

router = APIRouter()


@router.get("", summary="分页查询薪资配置")
async def list_salary_configs(
    page: int = Query(default=1, ge=1, description="页码"),
    size: int = Query(default=10, ge=1, le=500, description="每页大小"),
    keyword: str | None = Query(default=None, description="搜索关键词"),
    status: str | None = Query(default=None, description="状态筛选"),
    current_user: TokenPayload = Depends(require_permission("salary:config:view")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[PageResponse[SalaryConfigResponse]]:
    """分页查询薪资配置，支持关键词和状态筛选"""
    result = await salary_service.list_salary_configs(page, size, keyword, status, db)
    return ok(data=result)


@router.get("/{config_id}", summary="获取薪资配置详情")
async def get_salary_config(
    config_id: int,
    current_user: TokenPayload = Depends(require_permission("salary:config:view")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[SalaryConfigResponse]:
    """根据ID获取薪资配置详情"""
    result = await salary_service.get_salary_config(config_id, db)
    return ok(data=result)


@router.post("", summary="创建薪资配置")
async def create_salary_config(
    data: SalaryConfigCreate,
    current_user: TokenPayload = Depends(require_permission("salary:config:add")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[SalaryConfigResponse]:
    """创建薪资配置"""
    result = await salary_service.create_salary_config(data, db)
    return ok(data=result, message="创建成功")


@router.put("/{config_id}", summary="更新薪资配置")
async def update_salary_config(
    config_id: int,
    data: SalaryConfigUpdate,
    current_user: TokenPayload = Depends(require_permission("salary:config:edit")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[SalaryConfigResponse]:
    """更新薪资配置"""
    result = await salary_service.update_salary_config(config_id, data, db)
    return ok(data=result, message="更新成功")


@router.delete("/{config_id}", summary="删除薪资配置")
async def delete_salary_config(
    config_id: int,
    current_user: TokenPayload = Depends(require_permission("salary:config:delete")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse[None]:
    """删除薪资配置"""
    await salary_service.delete_salary_config(config_id, db)
    return ok(message="删除成功")
