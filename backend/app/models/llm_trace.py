"""
LLM 追踪记录 ORM 模型（models/llm_trace.py）

说明：用于持久化每一次 LLM 调用的元数据，替代旧版 routers/observability.py
     里的内存 TraceStore。重启进程不再丢数据。

对应表：llm_trace（在 init_postgres.sql 中创建）
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LlmTrace(Base):
    """
    LLM 调用追踪记录

    每一次 chat / agent / rag 调用都在这里落一行，
    供 LLM 追踪页面、用量统计、用户反馈使用。
    """

    __tablename__ = "llm_trace"

    trace_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    operation_type: Mapped[str] = mapped_column(String(20), nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    cost_estimate: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success")
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)
    feedback: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
