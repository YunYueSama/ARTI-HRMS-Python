"""
认证服务（services/auth_service.py）

说明：实现用户登录、获取用户档案、修改密码、重置密码、密码强度检测等功能。
     对应 Java 的 AuthService 类，使用异步数据库操作。

Java 对应关系：
    AuthService.login()              → login()
    AuthService.getProfile()         → get_profile()
    AuthService.changePassword()     → change_password()
    AuthService.resetPassword()      → reset_password()
    AuthService.checkPasswordStrength() → check_password_strength()
"""

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessException, NotFoundException
from app.core.security import create_access_token, hash_password, verify_password
from app.models.department import Department
from app.models.employee import Employee
from app.models.job_position import JobPosition
from app.models.permission import Permission
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.sys_user import SysUser
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginResponse,
    PasswordStrengthResponse,
    ResetPasswordRequest,
    UserProfile,
)


async def login(username: str, password: str, db: AsyncSession) -> LoginResponse:
    """
    用户登录

    流程：
        1. 根据用户名查询 SysUser
        2. 验证密码（支持 BCrypt 哈希和明文兼容）
        3. 检查账户状态和员工状态
        4. 更新最后登录时间
        5. 构建 UserProfile
        6. 生成 JWT Token
        7. 返回 LoginResponse

    参数：
        username: 登录用户名
        password: 登录密码
        db: 异步数据库会话

    返回：
        LoginResponse（包含 token 和用户档案）

    异常：
        NotFoundException: 用户名或密码错误 / 账户被禁用
    """
    # 1. 根据用户名查询用户
    stmt = select(SysUser).where(SysUser.username == username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise NotFoundException(message="用户名或密码错误")

    # 2. 验证密码（兼容明文和 BCrypt 哈希）
    if not _password_matches(password, user.password):
        raise NotFoundException(message="用户名或密码错误")

    # 3. 检查账户状态
    if user.status != "启用":
        raise NotFoundException(message="账户已被禁用，请联系管理员")

    # 4. 检查关联员工状态
    if user.emp_id is not None:
        emp_stmt = select(Employee).where(Employee.emp_id == user.emp_id)
        emp_result = await db.execute(emp_stmt)
        employee = emp_result.scalar_one_or_none()
        if employee is not None and employee.status != "在职":
            raise NotFoundException(message=f"员工状态为{employee.status}，无法登录系统")

    # 5. 更新最后登录时间
    user.last_login = datetime.now()
    await db.flush()

    # 6. 构建用户档案
    profile = await _build_profile(user, db)

    # 7. 生成 JWT Token（包含权限信息）
    token = create_access_token(
        {
            "user_id": user.user_id,
            "username": user.username,
            "role_id": user.role_id,
            "emp_id": user.emp_id,
            "permissions": profile.permissions,
        }
    )

    return LoginResponse(token=token, user=profile)


async def get_profile(user_id: int, db: AsyncSession) -> UserProfile:
    """
    获取用户档案信息

    参数：
        user_id: 用户ID
        db: 异步数据库会话

    返回：
        UserProfile 用户档案

    异常：
        NotFoundException: 用户不存在
    """
    stmt = select(SysUser).where(SysUser.user_id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise NotFoundException(message="用户不存在")

    return await _build_profile(user, db)


async def change_password(request: ChangePasswordRequest, db: AsyncSession) -> None:
    """
    修改密码

    流程：
        1. 验证新密码和确认密码是否一致
        2. 验证新密码强度
        3. 查询用户
        4. 验证旧密码
        5. 检查新旧密码是否相同
        6. 哈希新密码并保存

    参数：
        request: 修改密码请求
        db: 异步数据库会话

    异常：
        BusinessException: 密码不一致 / 强度不足 / 旧密码错误 / 新旧密码相同
        NotFoundException: 用户不存在
    """
    # 验证新密码和确认密码一致
    if request.new_password != request.confirm_password:
        raise BusinessException(message="新密码和确认密码不一致")

    # 验证新密码强度
    strength = check_password_strength(request.new_password)
    if strength.is_weak:
        raise BusinessException(message="密码强度不足，请设置更复杂的密码")

    # 查询用户
    stmt = select(SysUser).where(SysUser.user_id == request.user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise NotFoundException(message="用户不存在")

    # 验证旧密码
    if not _password_matches(request.old_password, user.password):
        raise BusinessException(message="旧密码错误")

    # 检查新旧密码是否相同
    if request.new_password == request.old_password:
        raise BusinessException(message="新密码不能与旧密码相同")

    # 哈希新密码并保存
    user.password = hash_password(request.new_password)
    user.update_time = datetime.now(UTC)
    await db.flush()


async def reset_password(request: ResetPasswordRequest, db: AsyncSession) -> None:
    """
    重置密码（管理员操作）

    参数：
        request: 重置密码请求（包含 user_id 和 new_password）
        db: 异步数据库会话

    异常：
        BusinessException: 密码强度不足
        NotFoundException: 用户不存在
    """
    # 验证新密码强度
    strength = check_password_strength(request.new_password)
    if strength.is_weak:
        raise BusinessException(message="密码强度不足，请设置更复杂的密码")

    # 查询用户
    stmt = select(SysUser).where(SysUser.user_id == request.user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise NotFoundException(message="用户不存在")

    # 哈希新密码并保存
    user.password = hash_password(request.new_password)
    user.update_time = datetime.now(UTC)
    await db.flush()


def check_password_strength(password: str) -> PasswordStrengthResponse:
    """
    检测密码强度

    规则：
        - 长度 >= 8
        - 包含大写字母
        - 包含小写字母
        - 包含数字
        - 包含特殊字符

    强度等级：
        1 - 弱（满足 0-1 项）
        2 - 中（满足 2-3 项）
        3 - 强（满足 4 项）
        4 - 非常强（满足全部 5 项）

    参数：
        password: 待检测的密码

    返回：
        PasswordStrengthResponse 密码强度信息
    """
    suggestions: list[str] = []
    score = 0

    # 检查长度
    if len(password) >= 8:
        score += 1
    else:
        suggestions.append("密码长度至少为8位")

    # 检查大写字母
    if re.search(r"[A-Z]", password):
        score += 1
    else:
        suggestions.append("建议包含大写字母")

    # 检查小写字母
    if re.search(r"[a-z]", password):
        score += 1
    else:
        suggestions.append("建议包含小写字母")

    # 检查数字
    if re.search(r"\d", password):
        score += 1
    else:
        suggestions.append("建议包含数字")

    # 检查特殊字符
    if re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?]", password):
        score += 1
    else:
        suggestions.append("建议包含特殊字符")

    # 确定强度等级
    if score <= 1:
        level = 1
        strength_desc = "弱"
    elif score <= 3:
        level = 2
        strength_desc = "中"
    elif score == 4:
        level = 3
        strength_desc = "强"
    else:
        level = 4
        strength_desc = "非常强"

    is_weak = level <= 1

    # 弱密码额外提示
    if is_weak:
        suggestions.append("检测到弱密码，强烈建议更换")

    return PasswordStrengthResponse(
        strength=strength_desc,
        level=level,
        is_weak=is_weak,
        suggestions=suggestions,
    )


# ============================================================
# 内部辅助函数
# ============================================================


def _password_matches(raw: str, stored: str | None) -> bool:
    """
    验证密码（兼容 BCrypt 哈希和明文）

    说明：数据库中可能存在未加密的旧密码，需要兼容处理。
         BCrypt 哈希以 $2a$、$2b$、$2y$ 开头。
    """
    if stored is None:
        return False

    if _is_password_encrypted(stored):
        return verify_password(raw, stored)

    # 明文密码直接比较
    return stored == raw


def _is_password_encrypted(password: str) -> bool:
    """检查密码是否已加密（BCrypt 格式）"""
    return password.startswith(("$2a$", "$2b$", "$2y$"))


async def _build_profile(user: SysUser, db: AsyncSession) -> UserProfile:
    """
    构建用户档案信息

    说明：查询关联的员工、部门、职位、角色和权限信息，
         组装完整的 UserProfile 对象。
    """
    # 查询关联员工
    employee: Employee | None = None
    if user.emp_id is not None:
        emp_stmt = select(Employee).where(Employee.emp_id == user.emp_id)
        emp_result = await db.execute(emp_stmt)
        employee = emp_result.scalar_one_or_none()

    # 查询角色
    role: Role | None = None
    if user.role_id is not None:
        role_stmt = select(Role).where(Role.role_id == user.role_id)
        role_result = await db.execute(role_stmt)
        role = role_result.scalar_one_or_none()

    # 查询部门
    department: Department | None = None
    if employee is not None and employee.dept_id is not None:
        dept_stmt = select(Department).where(Department.dept_id == employee.dept_id)
        dept_result = await db.execute(dept_stmt)
        department = dept_result.scalar_one_or_none()

    # 查询职位
    position: JobPosition | None = None
    if employee is not None and employee.position_id is not None:
        pos_stmt = select(JobPosition).where(JobPosition.position_id == employee.position_id)
        pos_result = await db.execute(pos_stmt)
        position = pos_result.scalar_one_or_none()

    # 查询权限码列表
    permissions: list[str] = []
    if role is not None:
        permissions = await _get_permission_codes(role.role_id, db)

    # 构建审批指派标签
    identity_tag = employee.identity_tag_code if employee else None
    role_code = role.role_code if role else None
    approval_tags = _resolve_approval_assignee_tags(identity_tag, role_code)

    return UserProfile(
        user_id=user.user_id,
        username=user.username or "",
        emp_id=user.emp_id,
        emp_name=employee.emp_name if employee else None,
        dept_id=employee.dept_id if employee else None,
        dept_name=department.dept_name if department else None,
        position_id=employee.position_id if employee else None,
        position_name=position.position_name if position else None,
        role_id=user.role_id,
        role_name=role.role_name if role else None,
        role_code=role.role_code if role else None,
        identity_tag=identity_tag,
        status=user.status,
        permissions=permissions,
        approval_assignee_tags=approval_tags,
    )


async def _get_permission_codes(role_id: int, db: AsyncSession) -> list[str]:
    """
    根据角色ID查询权限码列表

    说明：通过 role_permission 关联表查询角色拥有的所有权限编码。
    """
    stmt = (
        select(Permission.perm_code)
        .join(RolePermission, RolePermission.perm_id == Permission.perm_id)
        .where(RolePermission.role_id == role_id)
        .where(Permission.perm_code.isnot(None))
    )
    result = await db.execute(stmt)
    return [row[0] for row in result.all()]


def _resolve_approval_assignee_tags(identity_tag: str | None, role_code: str | None) -> list[str]:
    """
    解析审批指派标签

    说明：根据用户的身份标签和角色编码，生成审批系统中可匹配的标签列表。
         用于审批流程中确定该用户可以作为哪些审批节点的处理人。
    """
    tags: list[str] = []

    # 身份标签标准化
    normalized_tag = _normalize_approval_tag(identity_tag)
    if normalized_tag is not None:
        tags.append(normalized_tag)

    # 角色编码映射
    role_tag_map = {
        "HR": "HR_SPECIALIST",
        "HR_MANAGER": "HR_MANAGER",
        "GENERAL_MANAGER": "GENERAL_MANAGER",
        "FINANCE_MANAGER": "FINANCE_MANAGER",
        "FINANCE": "FINANCE_SPECIALIST",
        "MANAGER": "MANAGER",
        "EMPLOYEE": "EMPLOYEE",
        "ADMIN": "ADMIN",
    }

    if role_code and role_code in role_tag_map:
        role_mapped = role_tag_map[role_code]
        if role_mapped not in tags:
            tags.append(role_mapped)

    return tags


def _normalize_approval_tag(tag: str | None) -> str | None:
    """
    标准化审批标签

    说明：将简写的身份标签转换为审批系统使用的标准标签名。
    """
    if not tag or not tag.strip():
        return None
    if tag == "HR":
        return "HR_SPECIALIST"
    if tag == "FINANCE":
        return "FINANCE_SPECIALIST"
    return tag
