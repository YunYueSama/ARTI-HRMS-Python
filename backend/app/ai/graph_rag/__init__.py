"""
GraphRAG 知识图谱模块（ai/graph_rag/）

说明：基于 NetworkX 的 HR 知识图谱，支持多跳关系查询和融合搜索。

子模块：
    - knowledge_graph: HR 知识图谱（构建、查询、可视化）
    - fusion: 向量检索 + 图谱查询融合搜索
"""

from app.ai.graph_rag.knowledge_graph import HRKnowledgeGraph, hr_knowledge_graph
from app.ai.graph_rag.fusion import fusion_search

__all__ = ["HRKnowledgeGraph", "hr_knowledge_graph", "fusion_search"]
