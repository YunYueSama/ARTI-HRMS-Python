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
                context_parts.append(f"[{i}] (相关度: {score:.2f}, 来源: {source})")
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

            context_parts.append(f"  {source_name} --[{label}]--> {target_name} (跳数: {hops})")

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


# ============================================================
# RRF（Reciprocal Rank Fusion）融合
# ============================================================

def reciprocal_rank_fusion(
    ranked_lists: list[list[dict]],
    k: int = 60,
    top_n: int = 10,
) -> list[dict]:
    """
    Reciprocal Rank Fusion（RRF）排名融合算法

    公式：RRF_score(d) = Σ_i 1 / (k + rank_i(d))

    说明：
        - d 是一个文档/结果
        - rank_i(d) 是文档 d 在第 i 个排名列表中的排名（从 1 开始）
        - k 是常数（默认 60），用于降低高排名结果的权重差异
        - 如果文档不在某个列表中，该列表贡献为 0

    参数：
        ranked_lists: 多个已排序的结果列表。
            每个列表的元素必须有 _rrf_id 字段用于去重标识。
        k: RRF 常数，默认 60
        top_n: 返回的最终结果数量

    返回：
        按 RRF 分数降序排列的融合结果列表
    """
    rrf_scores: dict[str, float] = {}
    doc_lookup: dict[str, dict] = {}

    for ranked_list in ranked_lists:
        for rank, item in enumerate(ranked_list, start=1):
            doc_id = item.get("_rrf_id", f"{item.get('doc_id', '?')}:{item.get('chunk_index', '?')}")
            if doc_id not in rrf_scores:
                rrf_scores[doc_id] = 0.0
                doc_lookup[doc_id] = item
            rrf_scores[doc_id] += 1.0 / (k + rank)

    # 按 RRF 分数降序排列
    sorted_ids = sorted(rrf_scores.keys(), key=lambda d: rrf_scores[d], reverse=True)

    results = []
    for doc_id in sorted_ids[:top_n]:
        item = doc_lookup[doc_id].copy()
        item["_rrf_score"] = round(rrf_scores[doc_id], 6)
        results.append(item)

    return results


def fusion_search_rrf(
    keyword_context: str,
    vector_results: list[dict],
    graph_results: list[dict],
    k: int = 60,
    top_n: int = 10,
) -> str:
    """
    使用 RRF 融合三种检索结果

    说明：将关键词查询、向量检索、知识图谱三种来源的结果，
         通过 RRF（Reciprocal Rank Fusion）算法融合为统一的排名列表。

    排名列表构建：
        1. keyword_context：按段落拆分为独立条目，按出现顺序排名
        2. vector_results：来自 search()，按 score 降序（已排序）
        3. graph_results：来自 query_relationships()，按 hops 升序（近的优先）

    参数：
        keyword_context: 关键词查询返回的格式化文本
        vector_results: 向量检索结果列表 [{"content", "score", "doc_id", ...}]
        graph_results: 图谱查询结果列表 [{"source_name", "relation", "target_name", "hops", ...}]
        k: RRF 常数，默认 60
        top_n: 最终返回的结果数量

    返回：
        融合后的 LLM 上下文文本
    """
    ranked_lists = []

    # 列表 1：关键词查询结果（按段落拆分）
    if keyword_context and keyword_context.strip():
        paragraphs = [p.strip() for p in keyword_context.split("\n\n") if p.strip()]
        # 如果段落太短，按单行拆分
        if len(paragraphs) <= 1:
            paragraphs = [line.strip() for line in keyword_context.split("\n") if line.strip() and len(line.strip()) > 10]
        keyword_items = []
        for i, para in enumerate(paragraphs):
            keyword_items.append({
                "_rrf_id": f"keyword:{i}",
                "content": para,
                "source": "系统数据",
                "score": 1.0,
            })
        if keyword_items:
            ranked_lists.append(keyword_items)

    # 列表 2：向量检索结果（已按 score 降序）
    if vector_results:
        for item in vector_results:
            item["_rrf_id"] = f"vector:{item.get('doc_id', '?')}:{item.get('chunk_index', '?')}"
        ranked_lists.append(vector_results)

    # 列表 3：图谱结果（按 hops 升序排列）
    if graph_results:
        sorted_graph = sorted(graph_results, key=lambda x: x.get("hops", 999))
        for item in sorted_graph:
            item["_rrf_id"] = f"graph:{item.get('source_name', '?')}:{item.get('target_name', '?')}"
            item["content"] = (
                f"{item.get('source_name', '?')} --[{item.get('label', item.get('relation', '相关'))}]--> "
                f"{item.get('target_name', '?')}"
            )
            item["source"] = "知识图谱"
            item["score"] = 1.0 / (1 + item.get("hops", 1))
        ranked_lists.append(sorted_graph)

    if not ranked_lists:
        return ""

    # 执行 RRF
    fused = reciprocal_rank_fusion(ranked_lists, k=k, top_n=top_n)

    # 格式化为 LLM 上下文 — 每个结果用分隔线隔开
    context_parts = ["=== 融合检索结果（以下为独立片段，来自不同位置，请分别引用） ===\n"]
    for i, item in enumerate(fused, 1):
        content = item.get("content", "").strip()
        source = item.get("filename", item.get("source", "未知来源"))
        rrf_score = item.get("_rrf_score", 0)

        if content:
            context_parts.append(f"--- 片段 {i} [来源: {source}, RRF: {rrf_score:.4f}] ---")
            context_parts.append(content)
            context_parts.append("")

    context_parts.append("=== 检索结束，请逐字引用以上片段，不要合并，不要添加片段中没有的内容 ===")
    fused_context = "\n".join(context_parts)

    logger.info(
        f"RRF 融合完成: 关键词={len(ranked_lists[0]) if ranked_lists else 0}条, "
        f"向量={len(vector_results)}条, "
        f"图谱={len(graph_results)}条, "
        f"融合后={len(fused)}条, "
        f"上下文长度={len(fused_context)}"
    )

    return fused_context
