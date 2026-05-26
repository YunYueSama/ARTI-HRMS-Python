"""
部门权限模板路由（routers/dept_permission_templates.py）

说明：定义部门权限模板的 API 端点。
     对应 Java 的 DeptPermissionTemplateController 类。

端点列表：
    GET /all                    → 获取所有部门权限模板
    PUT /dept/{dept_id}/modules → 更新部门的模块权限
"""

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_mysql_session
from app.core.dependencies import TokenPayload, require_permission
from app.models.approval import DeptPermissionTemplate
from app.schemas.common import ApiResponse, ok

router = APIRouter()


class DeptModulesUpdate(BaseModel):
    """部门模块权限更新请求"""

    module_codes: list[str] = Field(default_factory=list, alias="moduleCodes", description="模块编码列表")

    class Config:
        populate_by_name = True


@router.get("/all", summary="获取所有部门权限模板")
async def list_all_dept_permission_templates(
    current_user: TokenPayload = Depends(require_permission("permission:dept-template:view")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse:
    """获取所有部门权限模板列表"""
    stmt = select(DeptPermissionTemplate)
    result = await db.execute(stmt)
    templates = result.scalars().all()

    items = [
        {
            "id": t.id,
            "deptId": t.dept_id,
            "moduleCode": t.module_code,
            "createTime": t.create_time.isoformat() if t.create_time else None,
        }
        for t in templates
    ]
    return ok(data=items)


@router.put("/dept/{dept_id}/modules", summary="更新部门的模块权限")
async def update_dept_modules(
    dept_id: int,
    data: DeptModulesUpdate,
    current_user: TokenPayload = Depends(require_permission("permission:dept-template:edit")),
    db: AsyncSession = Depends(get_mysql_session),
) -> ApiResponse:
    """
    更新部门的模块权限

    说明：先删除该部门现有的所有模块权限，然后批量插入新的模块列表。
    """
    # 删除现有记录
    await db.execute(delete(DeptPermissionTemplate).where(DeptPermissionTemplate.dept_id == dept_id))

    # 批量插入新记录
    now = datetime.now()
    for module_code in data.module_codes:
        template = DeptPermissionTemplate(
            dept_id=dept_id,
            module_code=module_code,
            create_time=now,
        )
        db.add(template)

    await db.flush()

    # 返回更新后的列表
    stmt = select(DeptPermissionTemplate).where(DeptPermissionTemplate.dept_id == dept_id)
    result = await db.execute(stmt)
    templates = result.scalars().all()

    items = [
        {
            "id": t.id,
            "deptId": t.dept_id,
            "moduleCode": t.module_code,
            "createTime": t.create_time.isoformat() if t.create_time else None,
        }
        for t in templates
    ]
    return ok(data=items, message="更新成功")
