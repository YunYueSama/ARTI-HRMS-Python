"""
四层权限系统（core/permissions.py）

说明：实现 HRMS 的四层权限控制模型，提供细粒度的访问控制。

四层权限模型：
┌─────────────────────────────────────────────────────────────────────┐
│ 层级 │ 名称              │ 作用                                     │
├─────────────────────────────────────────────────────────────────────┤
│  1   │ role_permission   │ 角色是否拥有某个功能权限码               │
│  2   │ identity_tag      │ 用户身份标签是否匹配业务要求             │
│  3   │ module_scope_rule │ 用户在某模块中的数据可见范围             │
│  4   │ approval_rule     │ 审批流程中匹配的审批链                   │
└─────────────────────────────────────────────────────────────────────┘

层级说明：
    Layer 1 - 功能权限：用户的角色是否拥有操作某个功能的权限码。
              例如：employee:create、leave:approve 等。
    Layer 2 - 身份标签：用户的身份标签是否满足业务场景要求。
              例如：只有 HR_SPECIALIST 才能操作入职流程。
    Layer 3 - 数据范围：用户在某个业务模块中能看到的数据范围。
              例如：普通员工只能看自己的考勤，部门经理能看本部门的。
    Layer 4 - 审批链：根据申请人身份和请假天数等条件，匹配对应的审批流程。
              例如：普通员工请假 <=3 天由部门经理审批，>3 天需要 HR 审批。

用法：
    from app.core.permissions import check_role_permission, get_data_scope, get_approval_chain

    # Layer 1: 检查功能权限
    if not check_role_permission(user.permissions, ["employee:create"]):
        raise PermissionDeniedException("无权创建员工")

    # Layer 3: 获取数据范围
    scope = await get_data_scope(db, role_id=1, module_code="attendance")
    # scope = "dept" → 只能查看本部门数据

    # Layer 4: 获取审批链
    chain = await get_approval_chain(db, type_code="leave", applicant_tag="EMPLOYEE", days=5)
    # chain = {"first_approver_tag": "MANAGER", "second_approver_tag": "HR_SPECIALIST"}
"""

from decimal import Decimal

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval import ApprovalRule
from app.models.module_scope import ModuleScopeDetail, ModuleScopeRule

# ============================================================
# Layer 1: 角色权限检查
# ============================================================


def check_role_permission(user_permissions: list[str], required: list[str]) -> bool:
    """
    Layer 1: 检查用户是否拥有所需的功能权限码

    说明：判断用户的权限列表中是否包含 required 中的任意一个权限码。
         只要匹配其中一个即视为通过（OR 逻辑）。

    参数：
        user_permissions: 用户拥有的权限码列表（从 JWT Token 中获取）
        required: 需要的权限码列表（任一匹配即可）

    返回：
        True 表示权限通过，False 表示权限不足

    示例：
        # 用户拥有 ["employee:view", "employee:create"]
        check_role_permission(user_perms, ["employee:create"])  # True
        check_role_permission(user_perms, ["employee:delete"])  # False
    """
    if not required:
        return True

    user_perm_set = set(user_permissions)
    required_set = set(required)
    return bool(user_perm_set.intersection(required_set))


# ============================================================
# Layer 2: 身份标签检查
# ============================================================


def check_identity_tag(user_tag: str | None, required_tags: list[str]) -> bool:
    """
    Layer 2: 检查用户身份标签是否匹配业务要求

    说明：判断用户的身份标签是否在允许的标签列表中。
         用于限制某些操作只能由特定身份的人执行。

    参数：
        user_tag: 用户的身份标签（如 "HR_SPECIALIST"、"MANAGER"）
        required_tags: 允许的身份标签列表

    返回：
        True 表示身份匹配，False 表示不匹配

    示例：
        check_identity_tag("HR_SPECIALIST", ["HR_SPECIALIST", "HR_MANAGER"])  # True
        check_identity_tag("EMPLOYEE", ["HR_SPECIALIST"])  # False
    """
    if not required_tags:
        return True

    if user_tag is None:
        return False

    return user_tag in required_tags


# ============================================================
# Layer 3: 模块数据范围
# ============================================================


async def get_data_scope(db: AsyncSession, role_id: int, module_code: str, identity_tag: str | None = None) -> str:
    """
    Layer 3: 获取用户在指定模块中的数据可见范围

    说明：根据用户的身份标签查询 module_scope_detail 表，
         如果没有匹配的明细记录，则使用 module_scope_rule 表的默认范围。

    数据范围值：
        - "self": 只能查看自己的数据
        - "dept": 可以查看本部门的数据
        - "all": 可以查看所有数据（全公司）

    参数：
        db: 异步数据库会话
        role_id: 角色ID（预留，当前未使用）
        module_code: 模块编码（如 "attendance"、"leave"、"salary"）
        identity_tag: 用户身份标签（用于查询明细范围）

    返回：
        数据范围字符串（"self" / "dept" / "all"）

    示例：
        scope = await get_data_scope(db, role_id=1, module_code="attendance", identity_tag="MANAGER")
        # 返回 "dept"（部门经理可以看本部门考勤）
    """
    # 优先查询身份标签对应的明细范围
    if identity_tag:
        detail_stmt = select(ModuleScopeDetail.scope).where(
            and_(
                ModuleScopeDetail.module_code == module_code,
                ModuleScopeDetail.tag_code == identity_tag,
            )
        )
        detail_result = await db.execute(detail_stmt)
        detail_scope = detail_result.scalar_one_or_none()
        if detail_scope:
            return detail_scope

    # 回退到模块默认范围
    rule_stmt = select(ModuleScopeRule.default_scope).where(ModuleScopeRule.module_code == module_code)
    rule_result = await db.execute(rule_stmt)
    default_scope = rule_result.scalar_one_or_none()

    return default_scope or "self"


# ============================================================
# Layer 4: 审批链匹配
# ============================================================


async def get_approval_chain(
    db: AsyncSession,
    type_code: str,
    applicant_tag: str,
    days: int,
) -> dict | None:
    """
    Layer 4: 根据条件匹配审批链

    说明：根据审批类型、申请人身份标签和天数条件，
         从 approval_rule 表中查找匹配的审批规则。
         规则按 sort_order 排序，返回第一条匹配的规则。

    匹配逻辑：
        1. type_code 必须匹配
        2. applicant_tag 必须匹配
        3. days_op + days_value 条件必须满足（如 days <= 3）

    参数：
        db: 异步数据库会话
        type_code: 审批类型编码（如 "leave"、"salary"）
        applicant_tag: 申请人身份标签（如 "EMPLOYEE"、"MANAGER"）
        days: 天数（用于条件比较）

    返回：
        匹配的审批链字典，包含：
            - rule_id: 规则ID
            - first_approver_tag: 第一级审批人标签
            - second_approver_tag: 第二级审批人标签（可选）
            - second_approver_scope: 第二级审批人数据范围（可选）
        未匹配到规则时返回 None

    示例：
        chain = await get_approval_chain(db, "leave", "EMPLOYEE", 5)
        # 返回 {"rule_id": 1, "first_approver_tag": "MANAGER", "second_approver_tag": "HR_SPECIALIST", ...}
    """
    # 查询匹配 type_code 和 applicant_tag 的所有规则，按 sort_order 排序
    stmt = (
        select(ApprovalRule)
        .where(
            and_(
                ApprovalRule.type_code == type_code,
                ApprovalRule.applicant_tag == applicant_tag,
            )
        )
        .order_by(ApprovalRule.sort_order.asc())
    )
    result = await db.execute(stmt)
    rules = result.scalars().all()

    # 逐条匹配天数条件
    for rule in rules:
        if _match_days_condition(rule.days_op, rule.days_value, days):
            return {
                "rule_id": rule.rule_id,
                "first_approver_tag": rule.first_approver_tag,
                "second_approver_tag": rule.second_approver_tag,
                "second_approver_scope": rule.second_approver_scope,
            }

    return None


def _match_days_condition(days_op: str | None, days_value: float | int | Decimal | None, actual_days: int) -> bool:
    """
    匹配天数条件

    说明：根据运算符和阈值判断实际天数是否满足条件。

    支持的运算符：
        <=  小于等于
        <   小于
        >=  大于等于
        >   大于
        ==  等于
        !=  不等于

    参数：
        days_op: 比较运算符
        days_value: 阈值（Decimal 类型）
        actual_days: 实际天数

    返回：
        True 表示条件满足
    """
    # 如果没有天数条件，视为无条件匹配
    if days_op is None or days_value is None:
        return True

    threshold = float(days_value)

    if days_op == "<=":
        return actual_days <= threshold
    elif days_op == "<":
        return actual_days < threshold
    elif days_op == ">=":
        return actual_days >= threshold
    elif days_op == ">":
        return actual_days > threshold
    elif days_op == "==":
        return actual_days == threshold
    elif days_op == "!=":
        return actual_days != threshold
    else:
        # 未知运算符，默认不匹配
        return False
