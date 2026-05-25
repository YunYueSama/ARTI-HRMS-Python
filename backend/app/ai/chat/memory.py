"""
数据库聊天记忆（ai/chat/memory.py）

说明：实现基于 MySQL 的聊天历史存储和加载，替代 LangChain 内置的内存组件。
     将 ai_chat_message 表中的历史消息转换为 LangChain 消息对象，
     支持滑动窗口加载（默认最近 10 轮对话）。

Java 对应关系：
    AiChatService.saveUserMessage()      → DatabaseChatMemory.save_messages()
    AiChatService.saveAssistantMessage() → DatabaseChatMemory.save_messages()
    AiChatService.getHistory()           → DatabaseChatMemory.load_messages()

设计说明：
    - 不使用 LangChain 的 ConversationBufferMemory（它不支持异步数据库）
    - 直接操作 SQLAlchemy 异步会话，与项目数据库层一致
    - 消息按时间正序加载，最新的在最后
"""

import logging
from datetime import datetime

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
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
