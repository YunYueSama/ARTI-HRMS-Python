"""
可观测性 API 路由（routers/observability.py）

说明：提供 LLM 调用追踪的查询、统计和反馈接口。
     trace 数据持久化到 PostgreSQL 的 llm_trace 表（不再用内存存储）。

API 端点：
    GET  /api/traces          → 查询追踪记录（支持过滤和分页）
    GET  /api/traces/usage    → 获取 Token 使用汇总（按天/周聚合）
    POST /api/traces/feedback → 提交用户反馈
    GET  /api/traces/{trace_id} → 获取单条追踪详情
"""

import logging
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.observability.token_counter import (
    TokenUsageRecord,
    aggregate_daily_usage,
    aggregate_weekly_usage,
)
from app.ai.observability.tracer import langfuse_tracer
from app.core.database import get_session
from app.models.llm_trace import LlmTrace
from app.schemas.common import ApiResponse, PageResponse, fail, ok
from app.schemas.observability import (
    FeedbackRequest,
    TokenUsageSummary,
    TraceRecord,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================
# DB-backed TraceStore
#
# 说明：之前的版本用内存 list 存 trace，进程一关就丢。
#      现在改为直接读写 PostgreSQL 的 llm_trace 表，重启不丢数据。
#      `trace_store.add_async(record, db)` 由 chat 服务在调用结束后调用，
#      把 trace 落到表里。
# ============================================================


def _row_to_record(row: LlmTrace) -> TraceRecord:
    """ORM 模型 → Pydantic 响应模型"""
    return TraceRecord(
        trace_id=row.trace_id,
        user_id=row.user_id,
        operation_type=row.operation_type,
        model_name=row.model_name or "",
        input_tokens=row.input_tokens,
        output_tokens=row.output_tokens,
        total_tokens=row.total_tokens,
        latency_ms=float(row.latency_ms or 0),
        cost_estimate=float(row.cost_estimate or 0),
        status=row.status,
        tags=row.tags or [],
        feedback=row.feedback,
        create_time=row.create_time,
    )


class TraceStore:
    """
    PostgreSQL 持久化的 trace 记录访问类

    保留 `trace_store` 单例只是为了 chat 服务的兼容（依旧从代码里
    `from app.routers.observability import trace_store` 引用）。
    """

    async def add_async(self, db: AsyncSession, record: TraceRecord) -> None:
        """把一条 trace 落到数据库"""
        row = LlmTrace(
            trace_id=record.trace_id,
            user_id=record.user_id,
            operation_type=record.operation_type,
            model_name=record.model_name,
            input_tokens=record.input_tokens,
            output_tokens=record.output_tokens,
            total_tokens=record.total_tokens,
            latency_ms=record.latency_ms,
            cost_estimate=record.cost_estimate,
            status=record.status,
            tags=record.tags or [],
            feedback=record.feedback,
            create_time=record.create_time,
        )
        db.add(row)
        await db.flush()


# 全局 TraceStore 实例（被 chat / agent 服务引用）
trace_store = TraceStore()


# ============================================================
# API 端点
# ============================================================


@router.get("", summary="查询追踪记录")
async def query_traces(
    user_id: int | None = Query(default=None, description="按用户 ID 过滤"),
    start_time: datetime | None = Query(default=None, description="开始时间"),
    end_time: datetime | None = Query(default=None, description="结束时间"),
    status: Literal["success", "error", "slow"] | None = Query(default=None, description="按状态过滤"),
    operation_type: Literal["chat", "agent", "rag"] | None = Query(default=None, description="按操作类型过滤"),
    page: int = Query(default=1, ge=1, description="页码"),
    size: int = Query(default=20, ge=1, le=500, description="每页大小"),
    db: AsyncSession = Depends(get_session),
) -> ApiResponse[PageResponse[TraceRecord]]:
    """查询追踪记录（多条件 + 分页，按 create_time 倒序）"""

    # 构建过滤条件
    conditions = []
    if user_id is not None:
        conditions.append(LlmTrace.user_id == user_id)
    if start_time is not None:
        conditions.append(LlmTrace.create_time >= start_time)
    if end_time is not None:
        conditions.append(LlmTrace.create_time <= end_time)
    if status is not None:
        conditions.append(LlmTrace.status == status)
    if operation_type is not None:
        conditions.append(LlmTrace.operation_type == operation_type)

    # 计数
    count_stmt = select(func.count()).select_from(LlmTrace)
    if conditions:
        for cond in conditions:
            count_stmt = count_stmt.where(cond)
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # 分页查询
    offset = (page - 1) * size
    list_stmt = select(LlmTrace).order_by(desc(LlmTrace.create_time)).offset(offset).limit(size)
    if conditions:
        for cond in conditions:
            list_stmt = list_stmt.where(cond)
    list_result = await db.execute(list_stmt)
    rows = list_result.scalars().all()

    records = [_row_to_record(r) for r in rows]
    page_response = PageResponse[TraceRecord](items=records, total=total, page=page, size=size)
    return ok(data=page_response, message="查询成功")


@router.get("/usage", summary="获取 Token 使用汇总")
async def get_token_usage(
    aggregation: Literal["daily", "weekly"] = Query(default="daily", description="聚合方式（daily=按天, weekly=按周）"),
    db: AsyncSession = Depends(get_session),
) -> ApiResponse[list[TokenUsageSummary]]:
    """
    获取 Token 使用汇总

    说明：从数据库拉取所有 trace 记录，按天/按周聚合 Token 使用统计，
         包含输入/输出 Token 数、费用和请求次数。
    """
    # 拉取所有记录（如果数据量很大可改成 SQL 聚合）
    stmt = select(LlmTrace).order_by(desc(LlmTrace.create_time))
    result = await db.execute(stmt)
    rows = result.scalars().all()

    usage_records: list[TokenUsageRecord] = [
        TokenUsageRecord(
            input_tokens=r.input_tokens,
            output_tokens=r.output_tokens,
            total_tokens=r.total_tokens,
            model=r.model_name or "",
            cost=float(r.cost_estimate or 0),
            timestamp=r.create_time,
        )
        for r in rows
    ]

    if aggregation == "weekly":
        aggregated = aggregate_weekly_usage(usage_records)
    else:
        aggregated = aggregate_daily_usage(usage_records)

    summaries: list[TokenUsageSummary] = []
    for key, data in sorted(aggregated.items(), reverse=True):
        summaries.append(
            TokenUsageSummary(
                date=data.get("date") or data.get("week", key),
                total_input_tokens=data["total_input_tokens"],
                total_output_tokens=data["total_output_tokens"],
                total_cost=data["total_cost"],
                request_count=data["request_count"],
            )
        )

    return ok(data=summaries, message="查询成功")


@router.post("/feedback", summary="提交用户反馈")
async def submit_feedback(
    request: FeedbackRequest,
    db: AsyncSession = Depends(get_session),
) -> ApiResponse[None]:
    """
    提交用户反馈（1=好评, -1=差评）

    说明：更新数据库中的 feedback 字段，同时尝试同步到 Langfuse（如果已配置）
    """
    # 更新数据库
    stmt = update(LlmTrace).where(LlmTrace.trace_id == request.trace_id).values(feedback=request.score)
    result = await db.execute(stmt)

    if result.rowcount == 0:
        logger.warning(f"未找到 trace_id={request.trace_id} 的记录")

    # 同步到 Langfuse
    langfuse_tracer.record_feedback(
        trace_id=request.trace_id,
        score=request.score,
        user_id=request.user_id,
    )

    feedback_text = "👍 正面" if request.score == 1 else "👎 负面"
    logger.info(f"用户反馈已记录: trace_id={request.trace_id}, " f"feedback={feedback_text}, user_id={request.user_id}")
    return ok(message="反馈已记录")


@router.get("/{trace_id}", summary="获取追踪详情")
async def get_trace_detail(
    trace_id: str,
    db: AsyncSession = Depends(get_session),
) -> ApiResponse[TraceRecord | None]:
    """根据 trace_id 查询追踪记录的完整信息"""
    stmt = select(LlmTrace).where(LlmTrace.trace_id == trace_id)
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()

    if row is None:
        return fail(message=f"未找到 trace_id={trace_id} 的追踪记录")

    return ok(data=_row_to_record(row), message="查询成功")
