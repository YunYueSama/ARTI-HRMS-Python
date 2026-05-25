"""
AI 知识查询模块（ai/knowledge）

说明：提供基于关键词的业务数据查询服务，
     将数据库中的结构化数据转换为文本注入到 LLM 上下文。
"""

from app.ai.knowledge.service import query_knowledge

__all__ = ["query_knowledge"]
