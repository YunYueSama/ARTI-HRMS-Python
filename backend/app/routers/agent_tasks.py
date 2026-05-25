"""
Agent 任务路由（routers/agent_tasks.py）

说明：定义 Agent 任务管理的 API 端点。
     提供任务计划生成、审批执行、取消、删除和查询功能。

API 端点：
    POST   /api/agent/tasks/plan           → 生成任务计划
    POST   /api/agent/tasks/{task_id}/approve → 审批并执行任务
    POST   /api/agent/tasks/{task_id}/cancel  → 取消任务
    DELETE /api/agent/tasks/{task_id}       → 删除任务
    GET    /api/agent/tasks/               → 查询任务列表
    GET    /api/agent/tasks/{task_id}      → 查询单个任务

Java 对应关系：
    AgentTaskController → 本文件
    @PostMapping("/plan")              → POST /plan
    @PostMapping("/{taskId}/approve-execute") → POST /{task_id}/approve
    @PostMapping("/{taskId}/cancel")   → POST /{task_id}/cancel
    @PostMapping("/{taskId}/delete")   → DELETE /{task_id}
    @GetMapping("/history/{userId}")   → GET /?user_id=xxx
    @GetMapping("/{taskId}")           → GET /{task_id}
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_mysql_session
from app.schemas.agent import AgentTaskView, ApproveRequest, PlanRequest
from app.schemas.common import ApiResponse, ok
from app.services import agent_task_service

router = APIRouter()


@router.post("/plan", response_model=ApiResponse[AgentTaskView])
async def plan(
    request: PlanRequest,
    db: AsyncSession = Depends(get_mysql_session),
):
    """
    生成 Agent 任务计划

    说明：接收用户自然语言指令，通过 LangGraph Agent 进行意图识别和计划生成。
         返回结构化的执行计划供用户确认。

    请求体：
        - user_id: 用户ID
        - command: 自然语言指令（如 "帮我请两天年假"）

    返回：
        AgentTaskView 包含识别到的意图、执行计划、风险等级等信息
    """
    result = await agent_task_service.plan_task(request, db)
    return ok(data=result)


@router.get("/history/{user_id}", response_model=ApiResponse[list[AgentTaskView]])
async def list_by_user(
    user_id: int,
    db: AsyncSession = Depends(get_mysql_session),
):
    """
    查询用户的 Agent 任务历史

    说明：按创建时间倒序返回指定用户最近 50 条任务记录。
         对应 Java 的 GET /history/{userId} 端点。

    路径参数：
        - user_id: 用户ID

    返回：
        AgentTaskView 列表
    """
    result = await agent_task_service.list_tasks(user_id, db)
    return ok(data=result)


@router.get("/{task_id}", response_model=ApiResponse[AgentTaskView])
async def get(
    task_id: int,
    db: AsyncSession = Depends(get_mysql_session),
):
    """
    获取单个 Agent 任务详情

    路径参数：
        - task_id: 任务ID

    返回：
        AgentTaskView 任务详情
    """
    result = await agent_task_service.get_task(task_id, db)
    return ok(data=result)


@router.post("/{task_id}/approve-execute", response_model=ApiResponse[AgentTaskView])
async def approve_and_execute(
    task_id: int,
    request: ApproveRequest,
    db: AsyncSession = Depends(get_mysql_session),
):
    """
    审批并执行 Agent 任务

    说明：用户确认执行计划后，调用此端点进行审批和执行。
         执行成功后任务状态变为 succeeded，失败则变为 failed。

    路径参数：
        - task_id: 任务ID

    请求体：
        - user_id: 审批人用户ID（必须是任务创建者）
        - remark: 审批备注（可选）

    返回：
        AgentTaskView 包含执行结果
    """
    result = await agent_task_service.approve_and_execute(task_id, request, db)
    return ok(data=result)


@router.post("/{task_id}/cancel", response_model=ApiResponse[AgentTaskView])
async def cancel(
    task_id: int,
    request: ApproveRequest,
    db: AsyncSession = Depends(get_mysql_session),
):
    """
    取消 Agent 任务

    说明：仅任务创建者可以取消，且任务必须处于 planned 状态。

    路径参数：
        - task_id: 任务ID

    请求体：
        - user_id: 用户ID（必须是任务创建者）

    返回：
        AgentTaskView 取消后的任务状态
    """
    result = await agent_task_service.cancel_task(task_id, request, db)
    return ok(data=result)


@router.post("/{task_id}/delete", response_model=ApiResponse)
async def delete(
    task_id: int,
    request: ApproveRequest,
    db: AsyncSession = Depends(get_mysql_session),
):
    """
    删除 Agent 任务

    说明：删除任务及其关联的执行日志和审批记录。
         仅任务创建者可以删除。
         使用 POST 方法（与 Java 端保持一致）。

    路径参数：
        - task_id: 任务ID

    请求体：
        - user_id: 用户ID（必须是任务创建者）

    返回：
        成功响应（无数据）
    """
    await agent_task_service.delete_task(task_id, request, db)
    return ok()
