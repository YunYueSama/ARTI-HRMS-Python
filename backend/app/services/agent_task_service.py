"""
Agent 任务管理服务（services/agent_task_service.py）

说明：实现 Agent 任务的完整生命周期管理：
     计划生成 → 审批 → 执行 → 结果记录

     内部使用 LangGraph StateGraph 处理用户指令，
     将自然语言转换为结构化的执行计划，经人工确认后执行。

核心流程：
    1. plan_task: 运行 Agent 图（意图识别 + 计划生成），保存任务
    2. approve_and_execute: 审批并执行计划（调用业务服务）
    3. cancel_task: 取消待审批的任务
    4. delete_task: 删除任务及关联记录

Java 对应关系：
    AgentTaskService.planTask()          → plan_task()
    AgentTaskService.approveAndExecute() → approve_and_execute()
    AgentTaskService.cancelTask()        → cancel_task()
    AgentTaskService.deleteTask()        → delete_task()
    AgentTaskService.listByUser()        → list_tasks()
    AgentTaskService.getTask()           → get_task()
"""

import json
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agent.graph import get_agent_graph
from app.ai.agent.state import AgentState
from app.core.exceptions import BusinessException, NotFoundException
from app.models.agent import AgentApprovalRecord, AgentExecutionLog, AgentTask
from app.models.attendance import Attendance
from app.models.leave_request import LeaveRequest
from app.models.permission import Permission
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.schemas.agent import AgentPlan, AgentTaskView, ApproveRequest, PlanRequest

logger = logging.getLogger(__name__)

# 任务状态常量
STATUS_PLANNED = "planned"
STATUS_EXECUTING = "executing"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"


# ============================================================
# 公开 API 方法
# ============================================================


async def plan_task(request: PlanRequest, db: AsyncSession) -> AgentTaskView:
    """
    生成 Agent 任务计划

    说明：运行 LangGraph Agent 图进行意图识别和计划生成，
         将结果保存到数据库，返回任务视图。

    流程：
        1. 运行 Agent 图（intent_recognition + plan_generation + human_approval）
        2. 保存 AgentTask 记录到数据库
        3. 记录执行日志
        4. 返回 AgentTaskView

    参数：
        request: 计划请求（包含 user_id 和 command）
        db: 数据库会话

    返回：
        AgentTaskView 任务视图

    异常：
        BusinessException: 命令为空时抛出
    """
    if not request.command or not request.command.strip():
        raise BusinessException(message="命令不能为空")

    command = request.command.strip()

    # 运行 Agent 图（意图识别 + 计划生成）
    graph = get_agent_graph()
    initial_state: dict = {
        "user_id": request.user_id,
        "command": command,
        "warnings": [],
        "error_history": [],
        "execution_results": [],
        "current_step": 0,
        "executable": False,
        "requires_approval": True,
    }

    # 执行图（同步方式，因为图节点是 async 的）
    result = await graph.ainvoke(initial_state)

    # 从结果中提取计划信息
    intent = result.get("intent", "unknown")
    plan_dict = result.get("plan") or {}
    risk_level = result.get("risk_level", "medium")
    executable = result.get("executable", False)
    warnings = result.get("warnings", [])
    provider_name = result.get("provider_name", "unknown")

    # 保存任务到数据库
    task = AgentTask(
        user_id=request.user_id,
        command_text=command,
        intent=intent,
        risk_level=risk_level,
        status=STATUS_PLANNED,
        provider_name=provider_name,
        requires_approval=True,
        executable=executable,
        plan_json=json.dumps(plan_dict, ensure_ascii=False) if plan_dict else "{}",
        create_time=datetime.now(),
        update_time=datetime.now(),
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)

    # 记录日志
    await _log(db, task.task_id, 0, "info", f"计划已生成，来源：{provider_name}")
    for warning in warnings:
        await _log(db, task.task_id, 0, "warn", warning)

    return await _to_view(task, db)


async def approve_and_execute(
    task_id: int, request: ApproveRequest, db: AsyncSession
) -> AgentTaskView:
    """
    审批并执行 Agent 任务

    说明：验证任务状态和权限后，执行计划中的操作。
         对应 Java 的 AgentTaskService.approveAndExecute() 方法。

    流程：
        1. 验证任务存在且属于当前用户
        2. 验证任务状态为 planned
        3. 保存审批记录
        4. 根据意图类型执行对应的业务操作
        5. 更新任务状态为 succeeded 或 failed
        6. 记录执行日志

    参数：
        task_id: 任务ID
        request: 审批请求（包含 user_id 和 remark）
        db: 数据库会话

    返回：
        AgentTaskView 任务视图

    异常：
        NotFoundException: 任务不存在
        BusinessException: 任务状态不允许执行
    """
    task = await _find_task(task_id, db)

    # 验证任务归属
    if task.user_id != request.user_id:
        raise BusinessException(message="只有任务创建者可以审批和执行此任务")

    # 验证任务状态
    if task.status == STATUS_SUCCEEDED:
        raise BusinessException(message="任务已经成功完成")
    if task.status == STATUS_EXECUTING:
        raise BusinessException(message="任务正在执行中")
    if task.status != STATUS_PLANNED:
        raise BusinessException(message="只有待审批状态的任务可以执行")

    # 读取计划
    plan_dict = _read_plan(task.plan_json)
    if not plan_dict.get("executable", False) and not task.executable:
        warnings = plan_dict.get("warnings", [])
        raise BusinessException(message=warnings[0] if warnings else "任务无法执行")

    # 保存审批记录
    approval_record = AgentApprovalRecord(
        task_id=task_id,
        approver_user_id=request.user_id,
        action="approve",
        remark=request.remark.strip() if request.remark else "",
        create_time=datetime.now(),
    )
    db.add(approval_record)

    # 更新任务状态为执行中
    task.status = STATUS_EXECUTING
    task.update_time = datetime.now()
    await db.flush()
    await _log(db, task_id, 0, "info", "审批已确认，开始执行")

    # 执行计划
    try:
        intent = plan_dict.get("intent", "unknown")
        result_summary = await _execute_plan(task_id, intent, plan_dict, request.user_id, db)

        task.status = STATUS_SUCCEEDED
        task.result_summary = result_summary
        task.update_time = datetime.now()
        await db.flush()
        await _log(db, task_id, 999, "info", result_summary)

    except Exception as ex:
        task.status = STATUS_FAILED
        task.result_summary = str(ex)[:500]
        task.update_time = datetime.now()
        await db.flush()
        await _log(db, task_id, 999, "error", str(ex)[:500])
        raise BusinessException(message=str(ex))

    return await _to_view(task, db)


async def cancel_task(task_id: int, request: ApproveRequest, db: AsyncSession) -> AgentTaskView:
    """
    取消 Agent 任务

    说明：仅任务创建者可以取消，且任务必须处于 planned 状态。
         对应 Java 的 AgentTaskService.cancelTask() 方法。

    参数：
        task_id: 任务ID
        request: 请求（包含 user_id）
        db: 数据库会话

    返回：
        AgentTaskView 任务视图
    """
    task = await _find_task(task_id, db)

    if task.user_id != request.user_id:
        raise BusinessException(message="只有任务创建者可以取消此任务")

    if task.status != STATUS_PLANNED:
        raise BusinessException(message="只有待审批状态的任务可以取消")

    task.status = STATUS_CANCELLED
    task.result_summary = "用户主动取消"
    task.update_time = datetime.now()
    await db.flush()
    await _log(db, task_id, 0, "info", "任务已被用户取消")

    return await _to_view(task, db)


async def delete_task(task_id: int, request: ApproveRequest, db: AsyncSession) -> None:
    """
    删除 Agent 任务

    说明：删除任务及其关联的执行日志和审批记录。
         仅任务创建者可以删除。
         对应 Java 的 AgentTaskService.deleteTask() 方法。

    参数：
        task_id: 任务ID
        request: 请求（包含 user_id）
        db: 数据库会话
    """
    task = await _find_task(task_id, db)

    if task.user_id != request.user_id:
        raise BusinessException(message="只有任务创建者可以删除此任务")

    # 删除关联的日志记录
    logs_result = await db.execute(
        select(AgentExecutionLog).where(AgentExecutionLog.task_id == task_id)
    )
    for log_record in logs_result.scalars().all():
        await db.delete(log_record)

    # 删除关联的审批记录
    approvals_result = await db.execute(
        select(AgentApprovalRecord).where(AgentApprovalRecord.task_id == task_id)
    )
    for approval in approvals_result.scalars().all():
        await db.delete(approval)

    # 删除任务本身
    await db.delete(task)
    await db.flush()


async def list_tasks(user_id: int, db: AsyncSession) -> list[AgentTaskView]:
    """
    查询用户的 Agent 任务列表

    说明：按创建时间倒序返回最近 50 条任务。
         对应 Java 的 AgentTaskService.listByUser() 方法。

    参数：
        user_id: 用户ID
        db: 数据库会话

    返回：
        AgentTaskView 列表
    """
    result = await db.execute(
        select(AgentTask)
        .where(AgentTask.user_id == user_id)
        .order_by(AgentTask.create_time.desc())
        .limit(50)
    )
    tasks = result.scalars().all()
    views = []
    for task in tasks:
        views.append(await _to_view(task, db))
    return views


async def get_task(task_id: int, db: AsyncSession) -> AgentTaskView:
    """
    获取单个 Agent 任务详情

    参数：
        task_id: 任务ID
        db: 数据库会话

    返回：
        AgentTaskView 任务视图
    """
    task = await _find_task(task_id, db)
    return await _to_view(task, db)


# ============================================================
# 内部辅助方法：执行计划
# ============================================================


async def _execute_plan(
    task_id: int, intent: str, plan: dict, user_id: int, db: AsyncSession
) -> str:
    """
    根据意图类型执行计划

    说明：路由到对应的执行函数。
         对应 Java 中 approveAndExecute() 的 switch 分支。
    """
    if intent == "leave.create":
        return await _execute_leave(task_id, plan, user_id, db)
    elif intent == "attendance.upsert":
        return await _execute_attendance(task_id, plan, user_id, db)
    elif intent == "role-permission.update":
        return await _execute_role_permission(task_id, plan, user_id, db)
    else:
        raise BusinessException(message="不支持的任务类型")


async def _execute_leave(
    task_id: int, plan: dict, user_id: int, db: AsyncSession
) -> str:
    """
    执行请假申请

    说明：对应 Java 的 AgentTaskService.executeLeave() 方法。
         从计划预览中提取参数，创建请假记录。
    """
    from app.models.employee import Employee
    from app.models.approval import ApprovalRule

    preview = plan.get("preview", {})
    start_date_str = str(preview.get("startDate", ""))
    end_date_str = str(preview.get("endDate", ""))
    days = int(preview.get("days", 1))
    leave_type = str(preview.get("leaveType", "事假"))
    reason = str(preview.get("reason", "AI代理提交"))

    if not leave_type.strip():
        leave_type = "事假"
    if not reason.strip():
        reason = "AI代理提交"

    # 兜底：日期为空时以今天为起点推算（与 nodes.py 逻辑一致）
    if not start_date_str:
        start_date_str = date.today().isoformat()
    if not end_date_str:
        try:
            d = date.fromisoformat(start_date_str)
            end_date_str = (d + timedelta(days=days - 1)).isoformat()
        except Exception:
            end_date_str = start_date_str

    await _log(db, task_id, 1, "info", "请假参数校验通过")

    # 查找用户关联的员工ID
    from app.models.sys_user import SysUser
    user_result = await db.execute(select(SysUser).where(SysUser.user_id == user_id))
    user = user_result.scalar_one_or_none()
    emp_id = user.emp_id if user else None

    if not emp_id:
        raise BusinessException(message="当前账号未绑定员工记录")

    # 查找审批规则
    rules_result = await db.execute(
        select(ApprovalRule)
        .where(ApprovalRule.type_code == "leave")
        .order_by(ApprovalRule.sort_order.asc())
    )
    rules = rules_result.scalars().all()
    first_approver_tag = "ADMIN"
    second_approver_tag = ""
    second_approver_scope = ""

    if rules:
        # 简化的规则匹配：取第一条匹配的规则
        for rule in rules:
            first_approver_tag = rule.first_approver_tag or "ADMIN"
            second_approver_tag = rule.second_approver_tag or ""
            second_approver_scope = rule.second_approver_scope or ""
            break

    await _log(db, task_id, 2, "info", "审批链匹配完成")

    # 解析日期
    from datetime import date as date_type
    try:
        start_date = date_type.fromisoformat(start_date_str) if start_date_str else date_type.today()
    except ValueError:
        start_date = date_type.today()
    try:
        end_date = date_type.fromisoformat(end_date_str) if end_date_str else start_date
    except ValueError:
        end_date = start_date

    # 创建请假记录
    leave_record = LeaveRequest(
        emp_id=emp_id,
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        days=Decimal(str(days)),
        reason=reason,
        status="待审批",
        pending_approver_tag=first_approver_tag,
        pending_approver_scope="company",
        next_approver_tag=second_approver_tag,
        next_approver_scope=second_approver_scope,
        apply_time=datetime.now(),
    )
    db.add(leave_record)
    await db.flush()

    await _log(db, task_id, 3, "info", "请假申请已创建")
    return "请假申请提交成功"


async def _execute_attendance(
    task_id: int, plan: dict, user_id: int, db: AsyncSession
) -> str:
    """
    执行考勤记录操作

    说明：对应 Java 的 AgentTaskService.executeAttendance() 方法。
         如果指定日期已有记录则更新，否则创建新记录。
    """
    from datetime import date as date_type, time as time_type

    preview = plan.get("preview", {})
    attendance_date_str = str(preview.get("attendanceDate", ""))
    clock_in_str = str(preview.get("clockIn", ""))
    clock_out_str = str(preview.get("clockOut", ""))
    remark = str(preview.get("remark", ""))

    # 解析日期
    try:
        attendance_date = date_type.fromisoformat(attendance_date_str) if attendance_date_str else date_type.today()
    except ValueError:
        attendance_date = date_type.today()

    # 解析时间
    clock_in = _parse_time(clock_in_str)
    clock_out = _parse_time(clock_out_str)

    # 查找用户关联的员工ID
    from app.models.sys_user import SysUser
    user_result = await db.execute(select(SysUser).where(SysUser.user_id == user_id))
    user = user_result.scalar_one_or_none()
    emp_id = user.emp_id if user else None

    if not emp_id:
        raise BusinessException(message="当前账号未绑定员工记录")

    # 查找是否已有该日期的考勤记录
    existing_result = await db.execute(
        select(Attendance)
        .where(Attendance.emp_id == emp_id)
        .where(Attendance.attendance_date == attendance_date)
        .limit(1)
    )
    existing = existing_result.scalar_one_or_none()

    await _log(
        db, task_id, 1, "info",
        "已找到该日期的考勤记录" if existing else "该日期暂无考勤记录"
    )

    # 计算考勤状态
    status = _resolve_attendance_status(clock_in, clock_out)
    await _log(db, task_id, 2, "info", f"考勤状态计算为：{status}")

    if existing:
        # 更新现有记录
        if clock_in is not None:
            existing.clock_in = clock_in
        if clock_out is not None:
            existing.clock_out = clock_out
        if remark:
            existing.remark = remark
        existing.status = status
        await db.flush()
        await _log(db, task_id, 3, "info", "考勤记录已更新")
        return "考勤记录更新成功"
    else:
        # 创建新记录
        record = Attendance(
            emp_id=emp_id,
            attendance_date=attendance_date,
            clock_in=clock_in,
            clock_out=clock_out,
            status=status,
            remark=remark,
            create_time=datetime.now(),
        )
        db.add(record)
        await db.flush()
        await _log(db, task_id, 3, "info", "考勤记录已创建")
        return "考勤记录创建成功"


async def _execute_role_permission(
    task_id: int, plan: dict, user_id: int, db: AsyncSession
) -> str:
    """
    执行角色权限更新

    说明：对应 Java 的 AgentTaskService.executeRolePermission() 方法。
         读取角色当前权限集，增加或移除指定权限，然后替换。
    """
    preview = plan.get("preview", {})
    role_id = _cast_int(preview.get("roleId"))
    permission_id = _cast_int(preview.get("permissionId"))
    action = str(preview.get("action", ""))

    if role_id is None or permission_id is None or not action:
        raise BusinessException(message="角色权限计划不完整")

    # 读取当前权限集
    current_result = await db.execute(
        select(RolePermission.perm_id).where(RolePermission.role_id == role_id)
    )
    current_ids = list(current_result.scalars().all())
    await _log(db, task_id, 1, "info", "当前权限集已加载")

    # 计算新权限集
    next_ids = list(dict.fromkeys(current_ids))  # 保持顺序去重
    if action == "remove":
        next_ids = [pid for pid in next_ids if pid != permission_id]
    else:
        if permission_id not in next_ids:
            next_ids.append(permission_id)

    # 删除现有关联
    existing_rps = await db.execute(
        select(RolePermission).where(RolePermission.role_id == role_id)
    )
    for rp in existing_rps.scalars().all():
        await db.delete(rp)
    await db.flush()

    # 批量插入新关联
    for perm_id in next_ids:
        rp = RolePermission(role_id=role_id, perm_id=perm_id)
        db.add(rp)
    await db.flush()

    await _log(db, task_id, 2, "info", "角色权限已更新")
    return "角色权限更新成功"


# ============================================================
# 内部辅助方法
# ============================================================


async def _find_task(task_id: int, db: AsyncSession) -> AgentTask:
    """查找任务，不存在时抛出 NotFoundException"""
    result = await db.execute(
        select(AgentTask).where(AgentTask.task_id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise NotFoundException(message="代理任务不存在", detail=f"task_id={task_id}")
    return task


async def _log(db: AsyncSession, task_id: int, step_no: int, level: str, message: str) -> None:
    """
    记录执行日志

    说明：对应 Java 的 AgentTaskService.log() 方法。
         每个步骤的执行详情都记录到 agent_execution_log 表。
    """
    log_entry = AgentExecutionLog(
        task_id=task_id,
        step_no=step_no,
        log_level=level,
        message=message[:2000] if message and len(message) > 2000 else message,
        create_time=datetime.now(),
    )
    db.add(log_entry)
    await db.flush()


async def _to_view(task: AgentTask, db: AsyncSession) -> AgentTaskView:
    """
    将 AgentTask ORM 模型转换为 AgentTaskView 视图

    说明：对应 Java 的 AgentTaskService.toView() 方法。
         包含计划解析和日志查询。
    """
    # 解析计划 JSON
    plan_dict = _read_plan(task.plan_json)
    plan_obj = None
    if plan_dict:
        try:
            plan_obj = AgentPlan.model_validate(plan_dict)
        except Exception:
            plan_obj = None

    return AgentTaskView(
        task_id=task.task_id,
        user_id=task.user_id,
        command_text=task.command_text,
        intent=task.intent,
        risk_level=task.risk_level,
        status=task.status,
        provider_name=task.provider_name,
        requires_approval=task.requires_approval,
        executable=task.executable,
        plan=plan_obj,
        result_summary=task.result_summary,
        create_time=task.create_time,
        update_time=task.update_time,
    )


def _read_plan(plan_json: Optional[str]) -> dict:
    """解析计划 JSON 字符串为字典"""
    if not plan_json:
        return {}
    try:
        return json.loads(plan_json)
    except (json.JSONDecodeError, TypeError):
        return {}


def _parse_time(time_str: str):
    """解析 HH:mm 格式时间字符串为 time 对象"""
    from datetime import time as time_type
    if not time_str or time_str.strip().lower() in ("", "null", "none"):
        return None
    try:
        parts = time_str.strip().split(":")
        return time_type(int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        return None


def _resolve_attendance_status(clock_in, clock_out) -> str:
    """
    计算考勤状态

    说明：对应 Java 的 resolveAttendanceStatus() 方法。
    """
    from datetime import time as time_type
    standard_in = time_type(9, 0)
    standard_out = time_type(18, 0)

    if clock_in is None and clock_out is None:
        return "缺勤"
    if clock_in and clock_in > standard_in:
        return "迟到"
    if clock_out and clock_out < standard_out:
        return "早退"
    return "正常"


def _cast_int(value) -> Optional[int]:
    """安全转换为整数"""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        text = str(value).strip()
        if not text or text.lower() in ("null", "none"):
            return None
        return int(text)
    except (ValueError, TypeError):
        return None
