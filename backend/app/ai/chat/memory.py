"""
数据库聊天记忆（ai/chat/memory.py）

说明：实现基于 MySQL 的聊天历史存储和加载，替代 LangChain 内置的内存组件。
     将 ai_chat_message 表中的历史消息转换为 LangChain 消息对象，
     支持滑动窗口加载（默认最近 10 轮对话）。
     支持摘要压缩和分层记忆管理。

Java 对应关系：
    AiChatService.saveUserMessage()      → DatabaseChatMemory.save_messages()
    AiChatService.saveAssistantMessage() → DatabaseChatMemory.save_messages()
    AiChatService.getHistory()           → DatabaseChatMemory.load_messages()

设计说明：
    - 不使用 LangChain 的 ConversationBufferMemory（它不支持异步数据库）
    - 直接操作 SQLAlchemy 异步会话，与项目数据库层一致
    - 消息按时间正序加载，最新的在最后
    - 支持三层记忆：工作记忆（原文）、短期记忆（摘要）、长期记忆（向量检索）
"""

import logging
from datetime import datetime

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_chat import AiChatMessage

logger = logging.getLogger(__name__)


class DatabaseChatMemory:
    """
    基于数据库的聊天记忆管理器

    说明：负责从 ai_chat_message 表加载历史消息和保存新消息。
         每个实例绑定一个用户 ID 和数据库会话。

    用法：
        memory = DatabaseChatMemory(user_id=1, db=session)
        history = await memory.load_messages(window_size=10)
        await memory.save_messages("你好", "主人好！", "dashscope", "qwen-plus")
    """

    def __init__(self, user_id: int, db: AsyncSession):
        """
        初始化聊天记忆管理器

        参数：
            user_id: 用户 ID（用于过滤该用户的聊天记录）
            db: SQLAlchemy 异步数据库会话
        """
        self.user_id = user_id
        self.db = db

    async def load_messages(self, window_size: int = 10) -> list[BaseMessage]:
        """
        加载最近的聊天历史，转换为 LangChain 消息对象

        说明：从数据库加载最近 window_size 条消息（包含 user 和 assistant），
             按时间正序排列，转换为 HumanMessage/AIMessage 对象。
             类似 Java 版中 buildMessagePayload() 里截取最近 10 条历史的逻辑。

        参数：
            window_size: 滑动窗口大小（加载最近多少条消息），默认 10

        返回：
            LangChain BaseMessage 对象列表（HumanMessage 和 AIMessage 交替）
        """
        # 查询最近的消息（按 id 倒序取 window_size 条，再反转为正序）
        # 说明：用 id 而非 create_time，避免同秒插入的两条记录顺序错乱
        stmt = (
            select(AiChatMessage)
            .where(AiChatMessage.user_id == self.user_id)
            .order_by(desc(AiChatMessage.id))
            .limit(window_size)
        )
        result = await self.db.execute(stmt)
        records = result.scalars().all()

        # 反转为时间正序（最早的在前）
        records = list(reversed(records))

        # 转换为 LangChain 消息对象
        messages: list[BaseMessage] = []
        for record in records:
            content = record.content or ""
            if not content.strip():
                continue

            if record.role == "user":
                messages.append(HumanMessage(content=content))
            elif record.role == "assistant":
                messages.append(AIMessage(content=content))

        logger.debug(f"加载了 {len(messages)} 条历史消息 (user_id={self.user_id})")
        return messages

    async def save_messages(
        self,
        human_message: str,
        ai_message: str,
        provider_name: str = "",
        model_name: str = "",
        used_system_data: bool = False,
    ) -> None:
        """
        保存一轮对话（用户消息 + AI 回复）到数据库

        说明：将用户消息和 AI 回复分别作为两条记录保存到 ai_chat_message 表。
             类似 Java 版 AiChatService.saveUserMessage() + saveAssistantMessage()。

        参数：
            human_message: 用户消息内容
            ai_message: AI 回复内容
            provider_name: LLM 提供商名称（如 dashscope、ollama）
            model_name: LLM 模型名称（如 qwen-plus、qwen3:4b）
            used_system_data: 是否使用了系统数据（知识注入）
        """
        now = datetime.now()

        # 保存用户消息（先 add → flush → 拿到 id；user 在前）
        user_msg = AiChatMessage(
            user_id=self.user_id,
            role="user",
            content=human_message,
            create_time=now,
        )
        self.db.add(user_msg)
        await self.db.flush()  # 立即写入，确保 user 的 id < assistant 的 id

        # 保存 AI 回复（id 自然比 user 行大）
        assistant_msg = AiChatMessage(
            user_id=self.user_id,
            role="assistant",
            content=ai_message,
            provider_name=provider_name or None,
            model_name=model_name or None,
            used_system_data=used_system_data,
            create_time=datetime.now(),  # 重新取时间，至少在数值上区分
        )
        self.db.add(assistant_msg)

        # 注意：不在这里 commit，由外层的数据库会话管理器统一提交
        await self.db.flush()
        logger.debug(f"保存对话记录 (user_id={self.user_id}, provider={provider_name}, model={model_name})")

    async def load_messages_with_compression(
        self,
        window_size: int = 10,
        compress_threshold: int = 20,
        summary_model: BaseChatModel | None = None,
    ) -> list[BaseMessage]:
        """
        加载对话历史，超过阈值时自动压缩早期消息为摘要

        策略：
            1. 消息数 <= compress_threshold → 直接返回（与 load_messages 相同）
            2. 消息数 > compress_threshold → 前半部分压缩为摘要，后半部分保留原文

        参数：
            window_size: 最终保留的最近消息数
            compress_threshold: 触发压缩的消息数阈值
            summary_model: 用于生成摘要的 LLM 模型

        返回：
            LangChain 消息列表（可能包含摘要 SystemMessage）
        """
        # 加载所有消息（不限窗口）
        stmt = (
            select(AiChatMessage)
            .where(AiChatMessage.user_id == self.user_id)
            .order_by(desc(AiChatMessage.id))
            .limit(compress_threshold + window_size)
        )
        result = await self.db.execute(stmt)
        records = list(reversed(result.scalars().all()))

        if len(records) <= compress_threshold:
            # 未超过阈值，直接返回最近的消息
            return await self.load_messages(window_size)

        # 分离：需要压缩的旧消息 + 保留的最近消息
        to_compress = records[:len(records) - window_size]
        to_keep = records[len(records) - window_size:]

        # 生成摘要
        summary = await self._compress_messages(to_compress, summary_model)

        # 构建结果
        messages: list[BaseMessage] = []
        if summary:
            messages.append(SystemMessage(content=f"[历史对话摘要]\n{summary}"))

        for record in to_keep:
            content = record.content or ""
            if not content.strip():
                continue
            if record.role == "user":
                messages.append(HumanMessage(content=content))
            elif record.role == "assistant":
                messages.append(AIMessage(content=content))

        logger.info(
            f"压缩历史: 原始{len(records)}条 → 摘要 + 最近{len(to_keep)}条 "
            f"(user_id={self.user_id})"
        )
        return messages

    async def _compress_messages(
        self,
        records: list,
        summary_model: BaseChatModel | None = None,
    ) -> str:
        """
        将消息列表压缩为摘要

        参数：
            records: AiChatMessage 记录列表
            summary_model: 用于生成摘要的 LLM 模型

        返回：
            摘要文本
        """
        if not records:
            return ""

        # 构建对话文本
        conversation_lines = []
        for record in records:
            role = "用户" if record.role == "user" else "助手"
            content = (record.content or "").strip()
            if content:
                conversation_lines.append(f"{role}: {content[:200]}")

        if not conversation_lines:
            return ""

        conversation_text = "\n".join(conversation_lines)

        # 如果没有模型，用简单的截断替代
        if summary_model is None:
            logger.warning("摘要模型不可用，使用截断替代压缩")
            return conversation_text[:500]

        prompt = (
            "请将以下对话压缩为简洁的摘要（200字以内）。\n"
            "保留关键信息：用户的核心需求、AI 的关键结论、未完成的待办。\n"
            "只输出摘要，不要解释。\n\n"
            f"对话内容：\n{conversation_text[:2000]}\n\n"
            "摘要："
        )

        try:
            response = await summary_model.ainvoke([HumanMessage(content=prompt)])
            summary = response.content.strip()
            logger.debug(f"对话摘要生成成功: {len(summary)}字")
            return summary
        except Exception as e:
            logger.warning(f"摘要生成失败: {e}")
            return conversation_text[:500]

    async def load_hierarchical_messages(
        self,
        working_window: int = 5,
        short_term_window: int = 20,
        summary_model: BaseChatModel | None = None,
    ) -> list[BaseMessage]:
        """
        分层记忆加载

        三层结构：
            1. 工作记忆：最近 working_window 轮原文（直接注入）
            2. 短期记忆：更早的消息压缩为摘要（注入摘要）
            3. 长期记忆：持久化存储（未来扩展向量检索）

        参数：
            working_window: 工作记忆保留的最近轮数
            short_term_window: 短期记忆的消息数上限
            summary_model: 用于生成摘要的 LLM 模型

        返回：
            LangChain 消息列表（摘要 + 最近消息）
        """
        # 加载所有消息
        stmt = (
            select(AiChatMessage)
            .where(AiChatMessage.user_id == self.user_id)
            .order_by(desc(AiChatMessage.id))
            .limit(short_term_window + working_window * 2)
        )
        result = await self.db.execute(stmt)
        records = list(reversed(result.scalars().all()))

        if len(records) <= working_window * 2:
            # 消息很少，直接返回原文
            messages: list[BaseMessage] = []
            for record in records:
                content = record.content or ""
                if not content.strip():
                    continue
                if record.role == "user":
                    messages.append(HumanMessage(content=content))
                elif record.role == "assistant":
                    messages.append(AIMessage(content=content))
            return messages

        # 分层
        to_keep = records[-(working_window * 2):]  # 最近 N 轮原文
        to_compress = records[:-(working_window * 2)]  # 更早的消息

        # 短期记忆 → 压缩为摘要
        summary = await self._compress_messages(to_compress, summary_model)

        # 组装
        messages = []
        if summary:
            messages.append(SystemMessage(content=f"[近期对话摘要]\n{summary}"))

        for record in to_keep:
            content = record.content or ""
            if not content.strip():
                continue
            if record.role == "user":
                messages.append(HumanMessage(content=content))
            elif record.role == "assistant":
                messages.append(AIMessage(content=content))

        logger.info(
            f"分层记忆: 压缩{len(to_compress)}条为摘要 + 保留最近{len(to_keep)}条 "
            f"(user_id={self.user_id})"
        )
        return messages
