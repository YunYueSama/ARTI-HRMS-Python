"""
融合搜索（ai/graph_rag/fusion.py）

说明：将向量检索（Vector RAG）和图谱查询（Graph RAG）的结果融合，
     生成统一的 LLM 上下文，提升 AI 回答的准确性和完整性。

核心功能：
    - fusion_search(): 融合向量检索和图谱查询结果

设计说明：
    融合策略：
    1. 向量检索结果 → 提供语义相关的文档片段（事实性知识）
    2. 图谱查询结果 → 提供实体关系和结构化数据（关系性知识）
    3. 融合后的上下文 → 同时包含事实和关系，供 LLM 生成更准确的回答

    上下文格式：
    ┌─────────────────────────────────────────────────────┐
    │ === 知识库检索结果 ===                                │
    │ [文档片段1]                                          │
    │ [文档片段2]                                          │
    │                                                     │
    │ === 知识图谱关系 ===                                  │
    │ 张三 --[属于]--> 技术部                               │
    │ 张三 --[担任]--> 高级工程师                            │
    │ 技术部 --[下属部门]--> 前端组                          │
    └─────────────────────────────────────────────────────┘

Java 对应关系：
    无直接对应（Python 新增的 GraphRAG 融合功能）

用法：
    from app.ai.graph_rag.fusion import fusion_search

    context = fusion_search(
        query="张三在哪个部门",
        vector_results=[{"content": "...", "score": 0.9}],
        graph_results=[{"source_name": "张三", "relation": "belongs_to", ...}],
    )
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def fusion_search(
    query: str,
    vector_results: list[dict],
    graph_results: list[dict],
    max_vector_chunks: int = 5,
    max_graph_relations: int = 10,
) -> str:
    """
    融合向量检索和图谱查询结果

    说明：将两种检索方式的结果合并为统一的 LLM 上下文字符串。
         向量结果提供语义相关的文档片段，图谱结果提供结构化关系数据。

    融合策略：
        1. 对向量结果按相关性分数排序，取 top-N
        2. 对图谱结果按跳数排序（近的优先），取 top-M
        3. 格式化为结构化文本，供 LLM 作为上下文参考

    参数：
        query: 用户查询文本（用于日志记录）
        vector_results: 向量检索结果列表
            [{"content": str, "score": float, "source": str}, ...]
        graph_results: 图谱查询结果列表
            [{"source_name": str, "relation": str, "target_name": str, "hops": int}, ...]
        max_vector_chunks: 最大向量结果数量（默认 5）
        max_graph_relations: 最大图谱关系数量（默认 10）

    返回：
        str: 融合后的上下文文本（供注入 LLM 系统提示词）
             如果两种结果都为空，返回空字符串
    """
    context_parts = []

    # ============================================================
    # Part 1: 向量检索结果（语义相关文档片段）
    # ============================================================
    if vector_results:
        # 按分数降序排序
        sorted_vectors = sorted(
            vector_results,
            key=lambda x: x.get("score", 0.0),
            reverse=True,
        )[:max_vector_chunks]

        context_parts.append("=== 知识库检索结果 ===")
        for i, result in enumerate(sorted_vectors, 1):
            content = result.get("content", "").strip()
            score = result.get("score", 0.0)
            source = result.get("source", "未知来源")

            if content:
                context_parts.append(
                    f"[{i}] (相关度: {score:.2f}, 来源: {source})"
                )
                context_parts.append(content)
                context_parts.append("")  # 空行分隔

    # ============================================================
    # Part 2: 图谱查询结果（实体关系）
    # ============================================================
    if graph_results:
        # 按跳数升序排序（近的关系优先）
        sorted_graph = sorted(
            graph_results,
            key=lambda x: x.get("hops", 999),
        )[:max_graph_relations]

        context_parts.append("=== 知识图谱关系 ===")
        for result in sorted_graph:
            source_name = result.get("source_name", "?")
            target_name = result.get("target_name", "?")
            relation = result.get("relation", "related")
            label = result.get("label", relation)
            hops = result.get("hops", 0)

            context_parts.append(
                f"  {source_name} --[{label}]--> {target_name} (跳数: {hops})"
            )

        context_parts.append("")  # 结尾空行

    # 合并结果
    if not context_parts:
        logger.debug(f"融合搜索无结果: query='{query[:50]}'")
        return ""

    fused_context = "\n".join(context_parts)

    logger.info(
        f"融合搜索完成: query='{query[:30]}...', "
        f"vector_count={len(vector_results)}, "
        f"graph_count={len(graph_results)}, "
        f"context_length={len(fused_context)}"
    )

    return fused_context


def build_graph_context_summary(graph_results: list[dict]) -> str:
    """
    构建图谱关系摘要（简洁版）

    说明：将图谱查询结果转换为简洁的自然语言描述，
         适合作为 LLM 的补充上下文。

    参数：
        graph_results: 图谱查询结果列表

    返回：
        str: 自然语言描述的关系摘要
    """
    if not graph_results:
        return ""

    # 按关系类型分组
    relations_by_type: dict[str, list[str]] = {}
    for result in graph_results:
        relation = result.get("label", result.get("relation", "相关"))
        source_name = result.get("source_name", "?")
        target_name = result.get("target_name", "?")

        if relation not in relations_by_type:
            relations_by_type[relation] = []
        relations_by_type[relation].append(f"{source_name} → {target_name}")

    # 构建摘要
    summary_parts = ["根据知识图谱，相关关系如下："]
    for relation_type, pairs in relations_by_type.items():
        summary_parts.append(f"  [{relation_type}]: {', '.join(pairs[:5])}")
        if len(pairs) > 5:
            summary_parts.append(f"    ...（共 {len(pairs)} 条）")

    return "\n".join(summary_parts)
