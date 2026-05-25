"""
AI 聊天消息模型（AiChatMessage）

说明：映射 MySQL hrms_db 中的 ai_chat_message 表，存储用户与 AI 助手的对话记录。
     每条消息记录角色（user/assistant）、内容、使用的模型和提供商等信息。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AiChatMessage(Base):
    """AI 聊天消息表 ORM 模型，对应 MySQL ai_chat_message 表"""

    __tablename__ = "ai_chat_message"

    # 消息ID（主键，自增，BigInteger）
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # 用户ID（BigInteger，非空）
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # 消息角色（user/assistant，非空）
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    # 消息内容（TEXT 类型，非空）
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # LLM 提供商名称
    provider_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # LLM 模型名称
    model_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # 是否使用了系统数据（知识注入）
    used_system_data: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    # 创建时间（非空）
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
