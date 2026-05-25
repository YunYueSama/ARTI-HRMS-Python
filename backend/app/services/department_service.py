"""
部门管理服务（services/department_service.py）

说明：实现部门的增删改查和分页查询功能。
     对应 Java 的 DepartmentService 类。
     删除时检查是否有员工引用该部门。
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessException, NotFoundException
from app.models.department import Department
from app.models.employee import Employee
from app.schemas.common import PageResponse
from app.schemas.department import DepartmentCreate, DepartmentResponse, DepartmentUpdate


async def list_departments(
    page: int, size: int, keyword: str | None, db: AsyncSession
) -> PageResponse[DepartmentResponse]:
    """
    分页查询部门列表

    支持筛选条件：
        - keyword: 模糊匹配部门名称
    """
    stmt = select(Department)
    count_stmt = select(func.count()).select_from(Department)

    if keyword:
        like_pattern = f"%{keyword.strip()}%"
        stmt = stmt.where(Department.dept_name.like(like_pattern))
        count_stmt = count_stmt.where(Department.dept_name.like(like_pattern))

    # 查询总数
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # 分页查询
    stmt = stmt.offset((page - 1) * size).limit(size)
    result = await db.execute(stmt)
    departments = result.scalars().all()

    return PageResponse(
        items=[DepartmentResponse.model_validate(dept) for dept in departments],
        total=total,
        page=page,
        size=size,
    )


async def get_department(dept_id: int, db: AsyncSession) -> DepartmentResponse:
    """根据ID获取部门详情"""
    result = await db.execute(select(Department).where(Department.dept_id == dept_id))
    department = result.scalar_one_or_none()
    if not department:
        raise NotFoundException(message="部门不存在", detail=f"dept_id={dept_id}")
    return DepartmentResponse.model_validate(department)


async def create_department(data: DepartmentCreate, db: AsyncSession) -> DepartmentResponse:
    """创建部门"""
    now = datetime.now()
    department = Department(
        **data.model_dump(),
        create_time=now,
        update_time=now,
    )
    db.add(department)
    await db.flush()
    await db.refresh(department)
    return DepartmentResponse.model_validate(department)


async def update_department(dept_id: int, data: DepartmentUpdate, db: AsyncSession) -> DepartmentResponse:
    """更新部门信息（部分更新）"""
    result = await db.execute(select(Department).where(Department.dept_id == dept_id))
    department = result.scalar_one_or_none()
    if not department:
        raise NotFoundException(message="部门不存在", detail=f"dept_id={dept_id}")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(department, field, value)
    department.update_time = datetime.now()

    await db.flush()
    await db.refresh(department)
    return DepartmentResponse.model_validate(department)


async def delete_department(dept_id: int, db: AsyncSession) -> None:
    """
    删除部门

    说明：删除前检查是否有员工引用该部门，如有则拒绝删除。
    """
    result = await db.execute(select(Department).where(Department.dept_id == dept_id))
    department = result.scalar_one_or_none()
    if not department:
        raise NotFoundException(message="部门不存在", detail=f"dept_id={dept_id}")

    # 检查是否有员工引用该部门
    emp_count_result = await db.execute(
        select(func.count()).select_from(Employee).where(Employee.dept_id == dept_id)
    )
    emp_count = emp_count_result.scalar() or 0
    if emp_count > 0:
        raise BusinessException(
            message="该部门下存在员工，无法删除",
            detail=f"部门ID={dept_id}，关联员工数={emp_count}",
        )

    await db.delete(department)
    await db.flush()
