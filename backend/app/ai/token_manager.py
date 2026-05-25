"""
Token 与上下文窗口管理（ai/token_manager.py）

说明：管理 LLM 对话中的 Token 预算分配和上下文窗口使用。
     提供 Token 计数、消息限制检查、历史截断和预算分配功能。

核心功能：
    - count_message_tokens(): 精确计数消息 Token 数
    - check_message_limit(): 检查消息是否超出 Token 限制
    - truncate_history(): 滑动窗口截断历史消息
    - allocate_budget(): 上下文窗口预算分配

设计说明：
    上下文窗口预算分配策略：
    ┌─────────────────────────────────────────────────────┐
    │  系统提示词 (20%)  │  对话历史 (40%)  │  RAG (30%)  │ 用户消息 (10%) │
    └─────────────────────────────────────────────────────┘

    当对话历史超出预算时，使用滑动窗口策略：
    - 始终保留系统提示词（system prompt）
    - 保留最近的 N 条消息
    - 丢弃最早的历史消息

Java 对应关系：
    无直接对应（Java 版未实现 Token 管理）

用法：
    from app.ai.token_manager import TokenManager

    manager = TokenManager()
    is_ok, count = manager.check_message_limit("你好", max_tokens=4096)
    truncated = manager.truncate_history(messages, budget=3000)
"""

import logging
from typing import Optional

from app.ai.observability.token_counter import count_tokens
from app.core.config import settings

logger = logging.getLogger(__name__)


class TokenManager:
    """
    Token 与上下文窗口管理器

    说明：管理 LLM 对话中的 Token 使用，确保不超出模型的上下文窗口限制。
         提供 Token 计数、限制检查、历史截断和预算分配功能。

    属性：
        context_window: 模型上下文窗口大小（Token 数）
        warning_threshold: 使用率警告阈值（0-1）
        max_input_tokens: 单条用户消息最大 Token 数

    用法：
        manager = TokenManager()
        budget = manager.allocate_budget(context_window=8192)
        truncated = manager.truncate_history(messages, budget=budget["conversation_history"])
    """

    def __init__(
        self,
        context_window: Optional[int] = None,
        warning_threshold: Optional[float] = None,
        max_input_tokens: Optional[int] = None,
    ):
        """
        初始化 Token 管理器

        参数：
            context_window: 模型上下文窗口大小（默认从配置读取）
            warning_threshold: 使用率警告阈值（默认从配置读取）
            max_input_tokens: 单条消息最大 Token 数（默认从配置读取）
        """
        self.context_window = context_window or settings.TOKEN_CONTEXT_WINDOW
        self.warning_threshold = warning_threshold or settings.TOKEN_WARNING_THRESHOLD
        self.max_input_tokens = max_input_tokens or settings.TOKEN_MAX_INPUT

    def count_message_tokens(self, text: str) -> int:
        """
        计算消息的 Token 数量

        说明：使用 tiktoken 进行精确的 Token 计数。
             对于不支持的模型编码，回退到近似估算。

        参数：
            text: 消息文本内容

        返回：
            int: Token 数量
        """
        if not text:
            return 0
        return count_tokens(text, model=settings.LLM_PRIMARY_MODEL)

    def check_message_limit(
        self, text: str, max_tokens: int = 4096
    ) -> tuple[bool, int]:
        """
        检查消息是否超出 Token 限制

        说明：计算消息的 Token 数，判断是否在允许范围内。
             用于在发送消息前进行前置校验。

        参数：
            text: 消息文本内容
            max_tokens: 最大允许 Token 数（默认 4096）

        返回：
            tuple[bool, int]: (是否在限制内, Token 数量)
                - True: 消息未超出限制
                - False: 消息超出限制

        示例：
            >>> manager = TokenManager()
            >>> is_ok, count = manager.check_message_limit("你好世界")
            >>> print(is_ok, count)  # True, 4
        """
        token_count = self.count_message_tokens(text)
        is_within_limit = token_count <= max_tokens
        return (is_within_limit, token_count)

    def truncate_history(self, messages: list[dict], budget: int) -> list[dict]:
        """
        滑动窗口截断历史消息

        说明：当对话历史超出 Token 预算时，保留系统提示词和最近的消息，
             丢弃最早的历史消息。

        截断策略：
            1. 始终保留 role="system" 的消息（系统提示词）
            2. 从最新消息开始向前累加 Token 数
            3. 当累计 Token 数接近预算时停止
            4. 返回系统消息 + 保留的最近消息

        参数：
            messages: 消息列表，每条消息格式为 {"role": str, "content": str}
            budget: Token 预算（最大允许的总 Token 数）

        返回：
            list[dict]: 截断后的消息列表

        示例：
            >>> messages = [
            ...     {"role": "system", "content": "你是助手"},
            ...     {"role": "user", "content": "第一条消息"},
            ...     {"role": "assistant", "content": "第一条回复"},
            ...     {"role": "user", "content": "最新消息"},
            ... ]
            >>> truncated = manager.truncate_history(messages, budget=100)
        """
        if not messages:
            return []

        # 分离系统消息和对话消息
        system_messages = [m for m in messages if m.get("role") == "system"]
        conversation_messages = [m for m in messages if m.get("role") != "system"]

        # 计算系统消息占用的 Token 数
        system_tokens = sum(
            self.count_message_tokens(m.get("content", ""))
            for m in system_messages
        )

        # 剩余预算分配给对话历史
        remaining_budget = budget - system_tokens
        if remaining_budget <= 0:
            # 预算不足以容纳系统消息，仅返回系统消息
            logger.warning(
                f"Token 预算不足: system_tokens={system_tokens}, budget={budget}"
            )
            return system_messages

        # 从最新消息开始向前累加，保留尽可能多的最近消息
        kept_messages = []
        accumulated_tokens = 0

        for msg in reversed(conversation_messages):
            msg_tokens = self.count_message_tokens(msg.get("content", ""))
            if accumulated_tokens + msg_tokens > remaining_budget:
                break
            kept_messages.insert(0, msg)
            accumulated_tokens += msg_tokens

        # 合并系统消息和保留的对话消息
        result = system_messages + kept_messages

        if len(kept_messages) < len(conversation_messages):
            dropped = len(conversation_messages) - len(kept_messages)
            logger.info(
                f"历史截断: 丢弃 {dropped} 条消息, "
                f"保留 {len(kept_messages)} 条, "
                f"Token 使用: {accumulated_tokens}/{remaining_budget}"
            )

        return result

    def allocate_budget(
        self, context_window: Optional[int] = None, threshold: float = 0.8
    ) -> dict:
        """
        上下文窗口预算分配

        说明：将模型的上下文窗口按比例分配给不同用途。
             使用阈值（默认 80%）作为安全边界，避免完全填满上下文窗口。

        分配策略：
            - 系统提示词: 20%（人设 + 指令 + Few-Shot 示例）
            - 对话历史: 40%（最近的对话记录）
            - RAG 上下文: 30%（检索到的知识文档片段）
            - 用户消息: 10%（当前用户输入）

        参数：
            context_window: 上下文窗口大小（默认使用实例配置）
            threshold: 使用率阈值（0-1，默认 0.8 即使用 80% 的窗口）

        返回：
            dict: 预算分配结果
                {
                    "total_budget": int,        # 总可用预算
                    "context_window": int,      # 原始窗口大小
                    "threshold": float,         # 使用率阈值
                    "system_prompt": int,       # 系统提示词预算
                    "conversation_history": int, # 对话历史预算
                    "rag_context": int,         # RAG 上下文预算
                    "user_message": int,        # 用户消息预算
                }

        示例：
            >>> manager = TokenManager()
            >>> budget = manager.allocate_budget(context_window=8192)
            >>> print(budget["conversation_history"])  # 2621
        """
        window = context_window or self.context_window
        total_budget = int(window * threshold)

        allocation = {
            "total_budget": total_budget,
            "context_window": window,
            "threshold": threshold,
            "system_prompt": int(total_budget * 0.20),
            "conversation_history": int(total_budget * 0.40),
            "rag_context": int(total_budget * 0.30),
            "user_message": int(total_budget * 0.10),
        }

        logger.debug(
            f"Token 预算分配: window={window}, threshold={threshold}, "
            f"total={total_budget}, "
            f"system={allocation['system_prompt']}, "
            f"history={allocation['conversation_history']}, "
            f"rag={allocation['rag_context']}, "
            f"user={allocation['user_message']}"
        )

        return allocation

    def get_usage_stats(self, messages: list[dict]) -> dict:
        """
        获取当前消息列表的 Token 使用统计

        说明：计算消息列表中各部分的 Token 使用情况，
             并与预算分配进行对比。

        参数：
            messages: 消息列表

        返回：
            dict: 使用统计
                {
                    "total_tokens": int,
                    "system_tokens": int,
                    "conversation_tokens": int,
                    "usage_ratio": float,
                    "is_warning": bool,
                }
        """
        system_tokens = sum(
            self.count_message_tokens(m.get("content", ""))
            for m in messages
            if m.get("role") == "system"
        )
        conversation_tokens = sum(
            self.count_message_tokens(m.get("content", ""))
            for m in messages
            if m.get("role") != "system"
        )
        total_tokens = system_tokens + conversation_tokens
        usage_ratio = total_tokens / self.context_window if self.context_window > 0 else 0.0

        return {
            "total_tokens": total_tokens,
            "system_tokens": system_tokens,
            "conversation_tokens": conversation_tokens,
            "usage_ratio": round(usage_ratio, 4),
            "is_warning": usage_ratio >= self.warning_threshold,
        }
