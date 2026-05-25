"""
可观测性数据模型（schemas/observability.py）

说明：定义 LLM 可观测性相关的请求/响应数据模型。
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TraceRecord(BaseModel):
    """追踪记录模型"""

    trace_id: str = Field(description="追踪 ID")
    user_id: int | None = Field(default=None, description="用户 ID")
    operation_type: str = Field(description="操作类型（chat/agent/rag）")
    model_name: str = Field(default="", description="模型名称")
    input_tokens: int = Field(default=0, description="输入 Token 数量")
    output_tokens: int = Field(default=0, description="输出 Token 数量")
    total_tokens: int = Field(default=0, description="总 Token 数量")
    latency_ms: float = Field(default=0.0, description="响应耗时（毫秒）")
    cost_estimate: float = Field(default=0.0, description="费用估算（元）")
    status: str = Field(default="success", description="状态（success/error/slow）")
    tags: list[str] = Field(default_factory=list, description="标签列表")
    feedback: int | None = Field(default=None, description="用户反馈（1=好, -1=差）")
    create_time: datetime = Field(default_factory=datetime.now, description="创建时间")

    model_config = {"from_attributes": True}


class TraceQuery(BaseModel):
    """追踪查询参数模型"""

    user_id: int | None = Field(default=None, description="按用户 ID 过滤")
    start_time: datetime | None = Field(default=None, description="开始时间")
    end_time: datetime | None = Field(default=None, description="结束时间")
    status: Literal["success", "error", "slow"] | None = Field(default=None, description="按状态过滤")
    operation_type: Literal["chat", "agent", "rag"] | None = Field(default=None, description="按操作类型过滤")
    feedback: Literal["up", "down"] | None = Field(default=None, description="按反馈过滤")
    page: int = Field(default=1, ge=1, description="页码")
    size: int = Field(default=20, ge=1, le=500, description="每页大小")


class TokenUsageSummary(BaseModel):
    """Token 使用汇总模型"""

    date: str = Field(description="日期")
    total_input_tokens: int = Field(default=0, description="总输入 Token 数")
    total_output_tokens: int = Field(default=0, description="总输出 Token 数")
    total_cost: float = Field(default=0.0, description="总费用")
    request_count: int = Field(default=0, description="请求次数")


class FeedbackRequest(BaseModel):
    """用户反馈请求模型"""

    trace_id: str = Field(description="追踪 ID")
    score: Literal[1, -1] = Field(description="反馈分数（1=好, -1=差）")
    user_id: int = Field(description="用户 ID")
