"""
AI 聊天模块（ai/chat）

说明：实现 AI 聊天助手"亚托莉"的核心功能，包括：
    - LLM 提供商管理和调用（llm_provider）
    - 角色人设和提示词模板（persona、prompts）
    - 消息分类器（classifier）
    - 数据库聊天记忆（memory）
    - 聊天服务（service）
"""

from app.ai.chat.service import ChatService

__all__ = ["ChatService"]
