"""
只读知识查询服务（ai/knowledge/service.py）

说明：根据用户消息中的关键词，从 MySQL 数据库查询相关业务数据，
     将结果格式化为文本字符串注入到 LLM 上下文中（事实注入/Grounding）。

覆盖的业务域（12+）：
    1. 系统总览（员工总数、部门数、岗位数等）
    2. 当前用户资料
    3. 员工数据
    4. 部门数据
    5. 岗位数据
    6. 用户账号数据
    7. 角色与权限数据
    8. 考勤数据
    9. 请假数据
    10. 薪资数据
    11. 报表统计
    12. 天气信息

Java 对应关系：
    AiReadonlyKnowledgeService.resolve()              → query_knowledge()
    AiReadonlyKnowledgeService.appendEmployeeContext() → _append_employee_context()
    AiReadonlyKnowledgeService.appendSalaryContext()   → _append_salary_context()
    ...（其他 append* 方法一一对应）

设计说明：
    - 所有查询均为只读操作，不修改任何数据
    - 基于关键词匹配触发查询（与 Java 版逻辑一致）
    - 查询结果限制条数，避免上下文过长
    - 基于用户权限过滤数据域：AI 不返回超过当前用户权限范围的数据
"""

import logging
from datetime import date

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance import Attendance
from app.models.department import Department
from app.models.employee import Employee
from app.models.job_position import JobPosition
from app.models.leave_request import LeaveRequest
from app.models.permission import Permission
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.salary import SalaryConfig, SalaryRecord
from app.models.sys_user import SysUser

logger = logging.getLogger(__name__)


async def query_knowledge(
    message: str,
    user_id: int,
    db: AsyncSession,
) -> str:
    """
    根据用户消息查询相关业务数据

    说明：分析消息中的关键词，触发对应的数据库查询，
         将查询结果格式化为文本注入到 LLM 上下文。
         类似 Java 版 AiReadonlyKnowledgeService.resolve() 方法。

    参数：
        message: 用户消息文本
        user_id: 当前用户 ID（用于查询个人相关数据）
        db: 异步数据库会话

    返回：
        格式化的知识文本字符串，为空字符串表示未命中任何数据域
    """
    normalized = message.strip().lower().replace(" ", "")
    context_parts: list[str] = []

    # 查询用户权限，用于数据域过滤
    perms = await _get_user_permission_codes(user_id, db)

    # 按业务域逐一检测并查询（仅在用户有对应权限时执行）
    if _contains_any(normalized, ["公司", "系统", "概况", "总览", "整体", "全部", "所有"]):
        if "dashboard:view" in perms:
            await _append_system_overview(context_parts, db)

    if _contains_any(normalized, ["我", "我的", "当前用户", "当前账号", "个人"]):
        await _append_current_user(context_parts, user_id, db)

    if _contains_any(normalized, ["员工", "人员", "入职", "在职", "离职"]):
        if "base:employee:view" in perms:
            await _append_employee_context(context_parts, db)

    if _contains_any(normalized, ["部门"]):
        if "base:department:view" in perms:
            await _append_department_context(context_parts, db)

    if _contains_any(normalized, ["岗位", "职位"]):
        if "base:position:view" in perms:
            await _append_position_context(context_parts, db)

    if _contains_any(normalized, ["用户", "账号", "登录"]):
        if "permission:user:view" in perms:
            await _append_user_context(context_parts, db)

    if _contains_any(normalized, ["角色", "权限", "授权"]):
        if "permission:role:view" in perms:
            await _append_role_permission_context(context_parts, db)

    if _contains_any(normalized, ["考勤", "出勤", "打卡", "签到", "签退"]):
        if "attendance:record:view" in perms:
            await _append_attendance_context(context_parts, user_id, db)

    if _contains_any(normalized, ["请假", "休假", "假期"]):
        if "attendance:leave:view" in perms:
            await _append_leave_context(context_parts, user_id, db)

    is_salary_config_query = _contains_any(normalized, ["配置", "设置", "规则", "标准", "方案"]) and _contains_any(
        normalized, ["工资", "薪资", "薪酬", "发薪"]
    )

    if is_salary_config_query:
        if "salary:config:view" in perms:
            await _append_salary_config_context(context_parts, db)
        else:
            context_parts.append(
                "薪资配置权限说明：当前用户没有查看薪资配置的权限（缺少 salary:config:view 权限码）。"
                "请直接告知用户：您没有权限查看薪资配置的详细信息，请联系管理员开通 salary:config:view 权限。"
                "不要引用系统总览中的薪资记录数量来回答薪资配置问题。"
            )

    if _contains_any(normalized, ["工资", "薪资", "薪酬", "发薪"]) and not is_salary_config_query:
        if "salary:record:view" in perms:
            await _append_salary_context(context_parts, user_id, db)
        else:
            context_parts.append("当前用户没有薪资记录的查看权限（缺少 salary:record:view）。")

    if _contains_any(normalized, ["报表", "统计", "指标", "分布", "出勤率"]):
        if "report:view" in perms:
            await _append_report_context(context_parts, db)

    # 天气查询：当用户问到天气时，调用高德地图 API 获取实时天气（无需权限）
    if _contains_any(normalized, ["天气", "气温", "下雨", "下雪", "晴", "阴天", "weather"]):
        await _append_weather_context(context_parts, message)

    # 元信息：当主人问到 AI 自身使用的模型 / 技术架构时，把真实配置注入上下文（无需权限）
    if _contains_any(
        normalized,
        [
            "模型",
            "model",
            "ai",
            "大模型",
            "llm",
            "provider",
            "底层",
            "技术",
            "架构",
            "什么版本",
            "用的什么",
            "用什么",
            "哪个模型",
            "什么api",
            "qwen",
            "通义",
            "deepseek",
            "ollama",
            "openai",
            "dashscope",
            "百炼",
        ],
    ):
        _append_self_meta(context_parts)

    return "\n".join(context_parts)


# ============================================================
# 各业务域查询实现
# ============================================================


async def _append_system_overview(parts: list[str], db: AsyncSession) -> None:
    """查询系统总览数据"""
    emp_count = await _count(db, Employee)
    dept_count = await _count(db, Department)
    pos_count = await _count(db, JobPosition)
    user_count = await _count(db, SysUser)
    role_count = await _count(db, Role)
    att_count = await _count(db, Attendance)
    leave_count = await _count(db, LeaveRequest)
    salary_count = await _count(db, SalaryRecord)

    parts.append(
        f"系统总览：员工总数={emp_count}，部门数={dept_count}，岗位数={pos_count}，"
        f"用户数={user_count}，角色数={role_count}，考勤记录数={att_count}，"
        f"请假记录数={leave_count}，薪资记录数={salary_count}。"
    )


async def _append_current_user(parts: list[str], user_id: int, db: AsyncSession) -> None:
    """查询当前用户关联的员工信息"""
    # 查找用户关联的员工
    stmt = select(SysUser).where(SysUser.user_id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        parts.append("当前用户资料：未找到用户信息。")
        return

    # 查找关联的员工
    if user.emp_id:
        emp_stmt = select(Employee).where(Employee.emp_id == user.emp_id)
        emp_result = await db.execute(emp_stmt)
        emp = emp_result.scalar_one_or_none()
        if emp:
            dept_name = await _get_dept_name(db, emp.dept_id)
            pos_name = await _get_position_name(db, emp.position_id)
            parts.append(
                f"当前用户资料：姓名={emp.emp_name or '未知'}，"
                f"部门={dept_name}，岗位={pos_name}，"
                f"状态={emp.status or '未知'}，账号={user.username or '未知'}。"
            )
            return

    parts.append(f"当前用户资料：账号={user.username or '未知'}，未绑定员工信息。")


async def _append_employee_context(parts: list[str], db: AsyncSession) -> None:
    """查询员工数据概览"""
    total = await _count(db, Employee)

    # 获取示例员工（前 8 条）
    stmt = select(Employee).order_by(Employee.emp_id).limit(8)
    result = await db.execute(stmt)
    employees = result.scalars().all()

    sample_texts = []
    for emp in employees:
        dept_name = await _get_dept_name(db, emp.dept_id)
        sample_texts.append(f"{emp.emp_name or '未知'}({dept_name}/{emp.status or '未知'})")

    sample_str = "、".join(sample_texts) if sample_texts else "暂无数据"
    parts.append(f"员工数据：当前员工总数为 {total}。示例员工：{sample_str}。")


async def _append_department_context(parts: list[str], db: AsyncSession) -> None:
    """查询部门数据"""
    stmt = select(Department).order_by(Department.dept_id).limit(12)
    result = await db.execute(stmt)
    departments = result.scalars().all()

    total = await _count(db, Department)
    names = "、".join(d.dept_name or "未知" for d in departments) if departments else "暂无数据"
    parts.append(f"部门数据：当前共有 {total} 个部门。部门列表：{names}。")


async def _append_position_context(parts: list[str], db: AsyncSession) -> None:
    """查询岗位数据"""
    stmt = select(JobPosition).order_by(JobPosition.position_id).limit(12)
    result = await db.execute(stmt)
    positions = result.scalars().all()

    total = await _count(db, JobPosition)
    texts = []
    for pos in positions:
        dept_name = await _get_dept_name(db, pos.dept_id)
        texts.append(f"{pos.position_name or '未知'}({dept_name})")

    sample_str = "、".join(texts) if texts else "暂无数据"
    parts.append(f"岗位数据：当前共有 {total} 个岗位。示例岗位：{sample_str}。")


async def _append_user_context(parts: list[str], db: AsyncSession) -> None:
    """查询系统用户账号数据"""
    total = await _count(db, SysUser)
    stmt = select(SysUser).order_by(SysUser.user_id).limit(10)
    result = await db.execute(stmt)
    users = result.scalars().all()

    texts = []
    for u in users:
        role_name = await _get_role_name(db, u.role_id)
        texts.append(f"{u.username or '未知'}({role_name})")

    sample_str = "、".join(texts) if texts else "暂无数据"
    parts.append(f"用户账号数据：当前共有 {total} 个系统账号。示例账号：{sample_str}。")


async def _append_role_permission_context(parts: list[str], db: AsyncSession) -> None:
    """查询角色与权限数据"""
    role_count = await _count(db, Role)
    stmt = select(Role).order_by(Role.role_id).limit(8)
    result = await db.execute(stmt)
    roles = result.scalars().all()

    role_names = "、".join(r.role_name or "未知" for r in roles) if roles else "暂无数据"
    parts.append(f"角色与权限数据：当前共有 {role_count} 个角色。角色列表：{role_names}。")


async def _append_attendance_context(parts: list[str], user_id: int, db: AsyncSession) -> None:
    """查询考勤数据"""
    total = await _count(db, Attendance)
    parts.append(f"考勤数据：当前系统共有 {total} 条考勤记录。")

    # 查询当前用户关联员工的最近考勤
    emp_id = await _get_emp_id_by_user(db, user_id)
    if emp_id:
        stmt = select(Attendance).where(Attendance.emp_id == emp_id).order_by(desc(Attendance.attendance_date)).limit(5)
        result = await db.execute(stmt)
        records = result.scalars().all()

        if records:
            texts = [f"{r.attendance_date}/{r.status or '未知'}" for r in records]
            parts.append(f"当前用户最近考勤：{'、'.join(texts)}。")
        else:
            parts.append("当前用户最近考勤：暂无记录。")


async def _append_leave_context(parts: list[str], user_id: int, db: AsyncSession) -> None:
    """查询请假数据"""
    total = await _count(db, LeaveRequest)
    parts.append(f"请假数据：当前系统共有 {total} 条请假记录。")

    # 查询当前用户关联员工的最近请假
    emp_id = await _get_emp_id_by_user(db, user_id)
    if emp_id:
        stmt = (
            select(LeaveRequest).where(LeaveRequest.emp_id == emp_id).order_by(desc(LeaveRequest.apply_time)).limit(5)
        )
        result = await db.execute(stmt)
        records = result.scalars().all()

        if records:
            texts = [f"{r.leave_type or '未知'}/{r.status or '未知'}" for r in records]
            parts.append(f"当前用户最近请假：{'、'.join(texts)}。")
        else:
            parts.append("当前用户最近请假：暂无记录。")


async def _append_salary_context(parts: list[str], user_id: int, db: AsyncSession) -> None:
    """查询薪资数据"""
    record_count = await _count(db, SalaryRecord)
    config_count = await _count(db, SalaryConfig)
    parts.append(f"薪资数据：当前系统共有 {record_count} 条薪资记录，{config_count} 条薪资配置。")

    # 查询当前用户关联员工的最近薪资
    emp_id = await _get_emp_id_by_user(db, user_id)
    if emp_id:
        stmt = (
            select(SalaryRecord).where(SalaryRecord.emp_id == emp_id).order_by(desc(SalaryRecord.salary_month)).limit(1)
        )
        result = await db.execute(stmt)
        latest = result.scalar_one_or_none()

        if latest:
            parts.append(
                f"当前用户最近工资：月份={latest.salary_month}，"
                f"税前={_decimal_text(latest.gross_salary)}，"
                f"实发={_decimal_text(latest.net_salary)}，"
                f"基本工资={_decimal_text(latest.base_salary)}，"
                f"岗位工资={_decimal_text(latest.position_salary)}，"
                f"奖金={_decimal_text(latest.bonus)}，"
                f"状态={latest.status or '未知'}。"
            )


async def _append_salary_config_context(parts: list[str], db: AsyncSession) -> None:
    """查询薪资配置详情"""
    total = await _count(db, SalaryConfig)

    stmt = select(SalaryConfig).order_by(SalaryConfig.config_id).limit(20)
    result = await db.execute(stmt)
    configs = result.scalars().all()

    if configs:
        texts = []
        for c in configs:
            texts.append(
                f"配置名称={c.config_name or '未知'}，"
                f"配置键={c.config_key or '未知'}，"
                f"配置值={c.config_value or '未知'}，"
                f"状态={c.status or '未知'}"
            )
        parts.append(f"薪资配置数据：当前系统共有 {total} 条薪资配置。\n" + "\n".join(texts))
    else:
        parts.append("薪资配置数据：当前系统暂无薪资配置。")


async def _append_report_context(parts: list[str], db: AsyncSession) -> None:
    """查询报表统计数据"""
    emp_count = await _count(db, Employee)
    dept_count = await _count(db, Department)
    leave_count = await _count(db, LeaveRequest)
    att_count = await _count(db, Attendance)

    # 本月新入职
    today = date.today()
    first_of_month = today.replace(day=1)
    stmt = select(func.count()).select_from(Employee).where(Employee.hire_date >= first_of_month)
    result = await db.execute(stmt)
    new_hires = result.scalar() or 0

    parts.append(
        f"报表数据：员工总数={emp_count}，本月新入职={new_hires}，"
        f"部门数={dept_count}，请假记录数={leave_count}，考勤记录数={att_count}。"
    )


async def _append_weather_context(parts: list[str], message: str) -> None:
    """
    查询天气数据（调用高德地图 API）

    说明：从用户消息中提取城市名，调用 weather_service 获取实时天气。
         如果无法识别城市名，默认查询配置的城市（.env 中 WEATHER_DEFAULT_CITY）。
    """
    import re

    from app.services.weather_service import get_weather

    # 尝试从消息中提取城市名
    # 常见模式："今天北京的天气"、"绵阳天气怎么样"、"上海天气"
    city_patterns = [
        r"([\u4e00-\u9fa5]{2,4}?)(?:的|市)?天气",
        r"天气.{0,4}([\u4e00-\u9fa5]{2,4})",
    ]

    city_name = ""
    normalized = message.strip()
    for pattern in city_patterns:
        match = re.search(pattern, normalized)
        if match:
            candidate = match.group(1)
            # 排除非城市名的词
            if candidate not in ("今天", "明天", "后天", "这里", "那里", "怎么", "如何", "查询"):
                city_name = candidate
                break

    # 默认城市（从配置读取）
    if not city_name:
        from app.core.config import settings
        city_name = settings.WEATHER_DEFAULT_CITY

    # 调用天气服务
    try:
        result = await get_weather(city_name)
        if result.get("error"):
            # 网络不通时给出明确提示，而不是让 LLM 自己编
            parts.append(
                f"天气查询结果：调用高德地图 API 失败（{result['error']}）。\n"
                f"系统确实配置了天气查询功能（高德地图 Web 服务 API），"
                f"但当前网络环境无法连接到 restapi.amap.com。\n"
                f"请告诉主人：天气功能已集成，但当前网络连接异常，建议检查代理/VPN 设置后重试。"
            )
        else:
            parts.append(
                f"实时天气数据（来自高德地图 API）：\n"
                f"城市：{result.get('city', city_name)}\n"
                f"天气：{result.get('weather', '未知')}\n"
                f"温度：{result.get('temperature', '未知')}°C\n"
                f"风向：{result.get('wind', '未知')}\n"
                f"湿度：{result.get('humidity', '未知')}%"
            )
    except Exception as e:
        logger.warning(f"天气查询异常: {e}")
        parts.append(f"天气查询结果：调用失败（{e}）。\n" f"系统已集成高德地图天气 API，但当前网络无法连接外部服务。")


def _append_self_meta(parts: list[str]) -> None:
    """
    注入"亚托莉自身运行环境"的元信息（同步函数，不需要 DB）

    说明：当主人问到"你用的是什么模型 / 你的底层 AI 是什么"等元问题时，
         把当前 LLM provider、模型名、参数等真实配置注入到 LLM 上下文，
         让亚托莉能够准确回答，而不是含糊推脱。
    """
    # 延迟 import 避免循环依赖
    from app.core.config import settings

    primary = settings.primary_llm_config
    fallback = settings.fallback_llm_config

    # 主模型 API Key 是否真实配置
    primary_configured = primary.api_key not in (
        "your_dashscope_api_key_here",
        "your_api_key_here",
        "sk-xxx",
        "",
    )
    primary_status = "已连接（API Key 已配置）" if primary_configured else "未连接（API Key 未配置）"

    fallback_configured = (
        fallback.api_key
        not in (
            "your_dashscope_api_key_here",
            "your_api_key_here",
            "sk-xxx",
            "",
        )
        or fallback.provider == "ollama"
    )
    fallback_status = "可用" if fallback_configured else "未配置"

    parts.append(
        "AI 运行元信息（这些是当前系统的真实配置，可以直接告诉主人）：\n"
        f"- 角色名：亚托莉（Atri），HRMS 企业人事系统内置 AI 助手。\n"
        f"- 主大模型 provider：{primary.provider}\n"
        f"- 主大模型名称：{primary.model}\n"
        f"- 主大模型 base_url：{primary.base_url}\n"
        f"- 主大模型 temperature：{primary.temperature}\n"
        f"- 主大模型 max_tokens：{primary.max_tokens}\n"
        f"- 主大模型连接状态：{primary_status}\n"
        f"- 备用大模型 provider：{fallback.provider}\n"
        f"- 备用大模型名称：{fallback.model}\n"
        f"- 备用大模型连接状态：{fallback_status}\n"
        "- 技术栈：FastAPI + LangChain + LangGraph + SQLAlchemy（异步）+ MySQL + pgvector + Redis。\n"
        "- 能力范围：基于只读权限读取 HRMS 系统数据（员工、部门、岗位、考勤、请假、薪资、报表等），"
        "支持普通聊天、流程解释、数据问答、情绪陪伴、Agent 工具调用、RAG 文档检索、知识图谱查询。"
    )


# ============================================================
# 辅助函数
# ============================================================


async def _get_user_permission_codes(user_id: int, db: AsyncSession) -> set[str]:
    """
    查询用户角色对应的所有权限编码

    说明：通过 sys_user → role → role_permission → permission 链路查询。
         管理员（ADMIN）和总经理（GENERAL_MANAGER）角色自动拥有全部权限。

    参数：
        user_id: 用户 ID
        db: 异步数据库会话

    返回：
        权限编码集合（如 {"dashboard:view", "salary:record:view", ...}）
    """
    # 查询用户角色
    stmt = select(SysUser.role_id).where(SysUser.user_id == user_id)
    result = await db.execute(stmt)
    role_id = result.scalar_one_or_none()

    if role_id is None:
        return set()

    # 查询角色编码
    stmt = select(Role.role_code).where(Role.role_id == role_id)
    result = await db.execute(stmt)
    role_code = result.scalar_one_or_none()

    # 管理员和总经理拥有全部权限
    if role_code in ("ADMIN", "GENERAL_MANAGER"):
        stmt = select(Permission.perm_code)
        result = await db.execute(stmt)
        return set(result.scalars().all())

    # 查询角色关联的权限编码
    stmt = (
        select(Permission.perm_code)
        .join(RolePermission, RolePermission.perm_id == Permission.perm_id)
        .where(RolePermission.role_id == role_id)
    )
    result = await db.execute(stmt)
    return set(result.scalars().all())


async def _count(db: AsyncSession, model) -> int:
    """通用计数查询"""
    stmt = select(func.count()).select_from(model)
    result = await db.execute(stmt)
    return result.scalar() or 0


async def _get_dept_name(db: AsyncSession, dept_id: int | None) -> str:
    """根据部门 ID 获取部门名称"""
    if dept_id is None:
        return "未知部门"
    stmt = select(Department.dept_name).where(Department.dept_id == dept_id)
    result = await db.execute(stmt)
    name = result.scalar_one_or_none()
    return name or "未知部门"


async def _get_position_name(db: AsyncSession, position_id: int | None) -> str:
    """根据职位 ID 获取职位名称"""
    if position_id is None:
        return "未知岗位"
    stmt = select(JobPosition.position_name).where(JobPosition.position_id == position_id)
    result = await db.execute(stmt)
    name = result.scalar_one_or_none()
    return name or "未知岗位"


async def _get_role_name(db: AsyncSession, role_id: int | None) -> str:
    """根据角色 ID 获取角色名称"""
    if role_id is None:
        return "未知角色"
    stmt = select(Role.role_name).where(Role.role_id == role_id)
    result = await db.execute(stmt)
    name = result.scalar_one_or_none()
    return name or "未知角色"


async def _get_emp_id_by_user(db: AsyncSession, user_id: int) -> int | None:
    """根据用户 ID 获取关联的员工 ID"""
    stmt = select(SysUser.emp_id).where(SysUser.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


def _decimal_text(value) -> str:
    """将 Decimal 值转为文本，None 时返回 '0'"""
    if value is None:
        return "0"
    return str(value).rstrip("0").rstrip(".")


def _contains_any(text: str, keywords: list[str]) -> bool:
    """检查文本是否包含关键词列表中的任意一个"""
    return any(kw in text for kw in keywords)
