"""
Langfuse SDK 集成和 Trace 管理（ai/observability/tracer.py）

说明：封装 Langfuse SDK，提供 LLM 调用链路追踪功能。
     当 Langfuse 未配置或 SDK 不可用时，自动降级为无操作模式。

核心功能：
    - trace() 上下文管理器：自动记录操作耗时和元数据
    - get_langchain_callback(): 获取 LangChain 回调处理器
    - record_feedback(): 记录用户反馈（👍/👎）
    - check_deadlock(): 检测 Agent 状态机死锁

用法：
    from app.ai.observability.tracer import langfuse_tracer

    async with langfuse_tracer.trace("chat", user_id=1) as trace:
        # 执行 LLM 调用
        result = await llm.invoke(messages)
"""

import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

# ============================================================
# 尝试导入 Langfuse SDK（可选依赖）
# 如果未安装或导入失败，使用 no-op 降级模式
# ============================================================
try:
    from langfuse import Langfuse
    from langfuse.callback import CallbackHandler as LangfuseCallbackHandler

    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    Langfuse = None
    LangfuseCallbackHandler = None
    logger.info("Langfuse SDK 未安装，可观测性追踪将使用本地模式")


@dataclass
class TraceContext:
    """
    Trace 上下文对象

    说明：在 trace() 上下文管理器中 yield 给调用方，
         用于记录额外的 span、事件和元数据。
    """

    trace_id: str = ""
    operation_type: str = ""
    user_id: int | None = None
    start_time: float = 0.0
    metadata: dict = field(default_factory=dict)
    _langfuse_trace: Any = None

    @property
    def duration_ms(self) -> float:
        """获取当前已经过的毫秒数"""
        return (time.time() - self.start_time) * 1000 if self.start_time else 0.0


class LangfuseTracer:
    """
    Langfuse 追踪管理器

    说明：封装 Langfuse SDK 的初始化和追踪操作。
         当 Langfuse 未配置（使用默认占位符密钥）时，
         自动禁用远程追踪，仅保留本地日志记录。

    设计模式：
        - 单例模式：全局共享一个 tracer 实例
        - 优雅降级：SDK 不可用时不影响业务逻辑
        - 上下文管理器：自动管理 trace 生命周期
    """

    def __init__(self) -> None:
        """
        初始化 Langfuse 客户端

        说明：检查配置中的密钥是否为有效值（非占位符），
             如果是有效密钥则初始化 Langfuse 客户端，
             否则记录警告并禁用远程追踪。
        """
        self._client: Any | None = None
        self._enabled: bool = False
        self._slow_threshold: float = getattr(settings, "SLOW_RESPONSE_THRESHOLD", 10.0)

        # 检查是否配置了有效的 Langfuse 密钥
        public_key = settings.LANGFUSE_PUBLIC_KEY
        secret_key = settings.LANGFUSE_SECRET_KEY
        host = settings.LANGFUSE_HOST

        if not LANGFUSE_AVAILABLE:
            logger.warning("Langfuse SDK 未安装，追踪功能已禁用。" "安装方式: pip install langfuse")
            return

        # 检查密钥是否为占位符
        if "your_" in public_key or "your_" in secret_key:
            logger.warning(
                "Langfuse 密钥未配置（仍为占位符），远程追踪已禁用。"
                "请在 .env 中设置 LANGFUSE_PUBLIC_KEY 和 LANGFUSE_SECRET_KEY"
            )
            return

        # 初始化 Langfuse 客户端
        try:
            self._client = Langfuse(
                public_key=public_key,
                secret_key=secret_key,
                host=host,
            )
            self._enabled = True
            logger.info(f"Langfuse 客户端已初始化，服务地址: {host}")
        except Exception as e:
            logger.error(f"Langfuse 客户端初始化失败: {e}")
            self._client = None
            self._enabled = False

    @property
    def enabled(self) -> bool:
        """是否启用了 Langfuse 远程追踪"""
        return self._enabled

    @asynccontextmanager
    async def trace(
        self,
        operation_type: str,
        user_id: int | None = None,
        **metadata: Any,
    ):
        """
        创建追踪上下文管理器

        说明：自动记录操作的开始时间、结束时间和耗时。
             如果 Langfuse 已启用，同时创建远程 trace。
             退出时检查是否为慢响应。

        参数：
            operation_type: 操作类型（chat/agent/rag）
            user_id: 执行操作的用户 ID
            **metadata: 额外的元数据（model_name, input_text 等）

        用法：
            async with tracer.trace("chat", user_id=1, model="qwen-plus") as ctx:
                result = await llm.invoke(messages)
                ctx.metadata["output_tokens"] = 150

        Yields:
            TraceContext: 追踪上下文对象
        """
        import uuid

        trace_id = str(uuid.uuid4())
        start_time = time.time()

        # 创建 TraceContext
        ctx = TraceContext(
            trace_id=trace_id,
            operation_type=operation_type,
            user_id=user_id,
            start_time=start_time,
            metadata=dict(metadata),
        )

        # 如果 Langfuse 已启用，创建远程 trace
        if self._enabled and self._client:
            try:
                langfuse_trace = self._client.trace(
                    id=trace_id,
                    name=operation_type,
                    user_id=str(user_id) if user_id else None,
                    metadata=metadata,
                )
                ctx._langfuse_trace = langfuse_trace
            except Exception as e:
                logger.warning(f"创建 Langfuse trace 失败: {e}")

        try:
            yield ctx
        finally:
            # 计算耗时
            duration_ms = (time.time() - start_time) * 1000
            latency_seconds = duration_ms / 1000

            # 检查慢响应
            if latency_seconds > self._slow_threshold:
                logger.warning(
                    f"慢响应检测: {operation_type} 耗时 {latency_seconds:.2f}s "
                    f"(阈值: {self._slow_threshold}s), trace_id={trace_id}"
                )

            # 更新 Langfuse trace
            if self._enabled and self._client and ctx._langfuse_trace:
                try:
                    ctx._langfuse_trace.update(
                        output=ctx.metadata.get("output"),
                        metadata={
                            **ctx.metadata,
                            "duration_ms": duration_ms,
                            "is_slow": latency_seconds > self._slow_threshold,
                        },
                    )
                except Exception as e:
                    logger.warning(f"更新 Langfuse trace 失败: {e}")

            logger.debug(f"Trace 完成: type={operation_type}, " f"duration={duration_ms:.1f}ms, trace_id={trace_id}")

    def get_langchain_callback(self, trace_id: str | None = None) -> Any | None:
        """
        获取 LangChain 回调处理器

        说明：返回一个 LangfuseCallbackHandler 实例，
             可以传入 LangChain 的 callbacks 参数中，
             自动追踪 LangChain 的所有 LLM 调用。

        参数：
            trace_id: 关联的 trace ID（可选，用于将回调关联到已有 trace）

        返回：
            LangfuseCallbackHandler 实例，或 None（如果 Langfuse 未启用）

        用法：
            callback = tracer.get_langchain_callback(trace_id="xxx")
            if callback:
                result = await llm.ainvoke(messages, config={"callbacks": [callback]})
        """
        if not self._enabled or not LANGFUSE_AVAILABLE or LangfuseCallbackHandler is None:
            return None

        try:
            handler = LangfuseCallbackHandler(
                public_key=settings.LANGFUSE_PUBLIC_KEY,
                secret_key=settings.LANGFUSE_SECRET_KEY,
                host=settings.LANGFUSE_HOST,
                trace_id=trace_id,
            )
            return handler
        except Exception as e:
            logger.warning(f"创建 LangChain 回调处理器失败: {e}")
            return None

    def record_feedback(
        self,
        trace_id: str,
        score: int,
        user_id: int | None = None,
    ) -> bool:
        """
        记录用户反馈

        说明：将用户对 AI 回复的评价（👍=1, 👎=-1）关联到对应的 trace。
             用于后续分析模型质量和用户满意度。

        参数：
            trace_id: 要关联反馈的 trace ID
            score: 反馈分数（1=👍 正面, -1=👎 负面）
            user_id: 提交反馈的用户 ID

        返回：
            bool: 是否成功记录反馈
        """
        if not self._enabled or not self._client:
            logger.debug(f"Langfuse 未启用，反馈仅本地记录: " f"trace_id={trace_id}, score={score}")
            return False

        try:
            self._client.score(
                trace_id=trace_id,
                name="user_feedback",
                value=score,
                comment=f"user_id={user_id}" if user_id else None,
            )
            logger.info(f"用户反馈已记录: trace_id={trace_id}, " f"score={score}, user_id={user_id}")
            return True
        except Exception as e:
            logger.error(f"记录用户反馈失败: {e}")
            return False

    def check_deadlock(self, state_history: list[str]) -> bool:
        """
        检测 Agent 状态机死锁

        说明：分析 Agent 执行过程中的状态历史，
             如果同一个状态节点被访问超过 3 次，
             判定为逻辑死锁（Agent 陷入循环）。

        参数：
            state_history: Agent 状态节点访问历史列表
                          例如: ["plan", "execute", "plan", "execute", "plan", "execute", "plan"]

        返回：
            bool: 是否检测到死锁

        示例：
            history = ["plan", "execute", "plan", "execute", "plan", "execute", "plan"]
            if tracer.check_deadlock(history):
                # "plan" 出现了 4 次，超过阈值 3
                raise AgentDeadlockError("检测到状态死锁")
        """
        if not state_history:
            return False

        from collections import Counter

        state_counts = Counter(state_history)

        for state, count in state_counts.items():
            if count > 3:
                logger.warning(
                    f"检测到状态死锁: 节点 '{state}' 被访问 {count} 次 " f"(阈值: 3), 状态历史: {state_history}"
                )
                return True

        return False

    def flush(self) -> None:
        """
        刷新 Langfuse 客户端缓冲区

        说明：确保所有待发送的 trace 数据被发送到 Langfuse 服务器。
             通常在应用关闭时调用。
        """
        if self._enabled and self._client:
            try:
                self._client.flush()
                logger.debug("Langfuse 缓冲区已刷新")
            except Exception as e:
                logger.warning(f"刷新 Langfuse 缓冲区失败: {e}")

    def shutdown(self) -> None:
        """
        关闭 Langfuse 客户端

        说明：释放 Langfuse 客户端资源，在应用关闭时调用。
        """
        if self._enabled and self._client:
            try:
                self._client.shutdown()
                logger.info("Langfuse 客户端已关闭")
            except Exception as e:
                logger.warning(f"关闭 Langfuse 客户端失败: {e}")


# ============================================================
# 导出全局单例实例
# 说明：整个应用共享同一个 LangfuseTracer 实例
# ============================================================
langfuse_tracer = LangfuseTracer()
