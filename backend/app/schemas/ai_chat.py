"""
AI 聊天相关 Schema（schemas/ai_chat.py）

说明：定义 AI 聊天模块的请求/响应模型，包括聊天消息发送、历史查询等。

Java 对应关系：
    AiChatPayloads.ChatRequest  → ChatRequest
    AiChatPayloads.ChatResponse → ChatMessageResponse
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    """AI 聊天请求模型"""

    user_id: int = Field(description="用户ID")
    message: str = Field(min_length=1, max_length=2000, description="用户消息内容")


class ChatMessageResponse(BaseModel):
    """AI 聊天消息响应模型（对应 ORM AiChatMessage 模型）"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="消息ID")
    user_id: int = Field(description="用户ID")
    role: str = Field(description="消息角色（user/assistant）")
    content: str = Field(description="消息内容")
    provider_name: Optional[str] = Field(default=None, description="LLM 提供商名称")
    model_name: Optional[str] = Field(default=None, description="LLM 模型名称")
    create_time: datetime = Field(description="创建时间")


class ChatHistoryQuery(BaseModel):
    """聊天历史分页查询参数模型"""

    user_id: int = Field(description="用户ID")
    page: int = Field(default=1, ge=1, description="页码（从1开始）")
    size: int = Field(default=50, ge=1, le=200, description="每页大小")
