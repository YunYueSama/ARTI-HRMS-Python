"""
员工管理服务（services/employee_service.py）

说明：实现员工的增删改查和分页查询功能。
     对应 Java 的 EmployeeService 类。
"""

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.models.employee import Employee
from app.schemas.common import PageResponse
from app.schemas.employee import EmployeeCreate, EmployeeQuery, EmployeeResponse, EmployeeUpdate


async def list_employees(query: EmployeeQuery, db: AsyncSession) -> PageResponse[EmployeeResponse]:
    """
    分页查询员工列表

    支持筛选条件：
        - keyword: 模糊匹配姓名、手机号、邮箱
        - dept_id: 部门ID精确匹配
        - status: 状态精确匹配
    """
    # 构建基础查询
    stmt = select(Employee)
    count_stmt = select(func.count()).select_from(Employee)

    # 关键词模糊搜索
    if query.keyword:
        like_pattern = f"%{query.keyword.strip()}%"
        keyword_filter = or_(
            Employee.emp_name.like(like_pattern),
            Employee.phone.like(like_pattern),
            Employee.email.like(like_pattern),
        )
        stmt = stmt.where(keyword_filter)
        count_stmt = count_stmt.where(keyword_filter)

    # 部门筛选
    if query.dept_id is not None:
        stmt = stmt.where(Employee.dept_id == query.dept_id)
        count_stmt = count_stmt.where(Employee.dept_id == query.dept_id)

    # 状态筛选
    if query.status:
        stmt = stmt.where(Employee.status == query.status)
        count_stmt = count_stmt.where(Employee.status == query.status)

    # 查询总数
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # 分页查询
    stmt = stmt.offset((query.page - 1) * query.size).limit(query.size)
    result = await db.execute(stmt)
    employees = result.scalars().all()

    return PageResponse(
        items=[EmployeeResponse.model_validate(emp) for emp in employees],
        total=total,
        page=query.page,
        size=query.size,
    )


async def get_employee(emp_id: int, db: AsyncSession) -> EmployeeResponse:
    """根据ID获取员工详情"""
    result = await db.execute(select(Employee).where(Employee.emp_id == emp_id))
    employee = result.scalar_one_or_none()
    if not employee:
        raise NotFoundException(message="员工不存在", detail=f"emp_id={emp_id}")
    return EmployeeResponse.model_validate(employee)


async def create_employee(data: EmployeeCreate, db: AsyncSession) -> EmployeeResponse:
    """创建员工"""
    now = datetime.now()
    employee = Employee(
        **data.model_dump(),
        create_time=now,
        update_time=now,
    )
    db.add(employee)
    await db.flush()
    await db.refresh(employee)
    return EmployeeResponse.model_validate(employee)


async def update_employee(emp_id: int, data: EmployeeUpdate, db: AsyncSession) -> EmployeeResponse:
    """
    更新员工信息（部分更新）

    说明：只更新请求中提供的字段（非 None），未提供的字段保持不变。
    """
    result = await db.execute(select(Employee).where(Employee.emp_id == emp_id))
    employee = result.scalar_one_or_none()
    if not employee:
        raise NotFoundException(message="员工不存在", detail=f"emp_id={emp_id}")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(employee, field, value)
    employee.update_time = datetime.now()

    await db.flush()
    await db.refresh(employee)
    return EmployeeResponse.model_validate(employee)


async def delete_employee(emp_id: int, db: AsyncSession) -> None:
    """删除员工"""
    result = await db.execute(select(Employee).where(Employee.emp_id == emp_id))
    employee = result.scalar_one_or_none()
    if not employee:
        raise NotFoundException(message="员工不存在", detail=f"emp_id={emp_id}")
    await db.delete(employee)
    await db.flush()
