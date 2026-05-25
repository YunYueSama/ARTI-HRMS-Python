"""
向量嵌入和语义检索（ai/rag/retriever.py）

说明：实现基于 pgvector 的语义相似度检索，将用户查询转换为向量，
     在文档分块中搜索最相关的内容，并格式化为 LLM 可用的上下文。

检索流程：
    用户查询 → 生成查询向量 → pgvector 余弦距离搜索 → 过滤低分结果 → 返回 Top-K

相似度计算：
    使用余弦距离（cosine distance）衡量向量相似度：
    - 距离 = 0: 完全相同
    - 距离 = 1: 完全无关
    - 相似度 = 1 - 距离

用法：
    from app.ai.rag.retriever import search, get_rag_context

    # 语义搜索
    results = await search("员工请假流程", top_k=5, db=session)

    # 获取 LLM 上下文
    context = await get_rag_context("员工请假流程", top_k=5, db=session)
"""

import logging

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.rag.models import RagChunk
from app.ai.rag.pipeline import generate_embeddings

logger = logging.getLogger(__name__)

# 默认相似度阈值（低于此值的结果将被过滤）
DEFAULT_SIMILARITY_THRESHOLD = 0.5


async def search(
    query: str,
    top_k: int = 5,
    db: AsyncSession | None = None,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> list[dict]:
    """
    语义相似度搜索

    说明：将查询文本转换为向量，使用 pgvector 的余弦距离算子
         在 rag_chunk 表中搜索最相关的文档分块。

    pgvector 距离算子：
        <=>: 余弦距离（cosine distance）
        <->: L2 距离（欧几里得距离）
        <#>: 内积距离（inner product）

    参数：
        query: 用户查询文本
        top_k: 返回的最大结果数量
        db: PostgreSQL 异步数据库会话
        similarity_threshold: 相似度阈值（0-1），低于此值的结果被过滤

    返回：
        搜索结果列表，每项包含：
        - content: 分块文本内容
        - score: 相似度分数（0-1，越高越相关）
        - doc_id: 所属文档 ID
        - chunk_index: 分块序号
        - filename: 所属文档文件名
    """
    if not db:
        logger.error("数据库会话未提供")
        return []

    if not query or not query.strip():
        return []

    # 1. 生成查询向量
    query_embeddings = await generate_embeddings([query])
    query_vector = query_embeddings[0]

    # 检查是否为零向量（API 未配置时的占位向量）
    if all(v == 0.0 for v in query_vector):
        logger.warning("查询向量为零向量（嵌入 API 未配置），无法执行语义搜索")
        return []

    # 2. 执行 pgvector 余弦距离搜索
    # 使用原生 SQL 以利用 pgvector 的 <=> 算子
    # 余弦距离范围 [0, 2]，相似度 = 1 - 距离
    vector_str = f"[{','.join(str(v) for v in query_vector)}]"

    sql = text("""
        SELECT
            c.chunk_id,
            c.doc_id,
            c.chunk_index,
            c.content,
            c.token_count,
            d.filename,
            1 - (c.embedding <=> :query_vector::vector) AS similarity
        FROM rag_chunk c
        JOIN rag_document d ON c.doc_id = d.doc_id
        WHERE d.status = 'ready'
          AND c.embedding IS NOT NULL
        ORDER BY c.embedding <=> :query_vector::vector ASC
        LIMIT :top_k
    """)

    result = await db.execute(
        sql,
        {"query_vector": vector_str, "top_k": top_k},
    )
    rows = result.fetchall()

    # 3. 过滤低于阈值的结果
    results = []
    for row in rows:
        similarity = float(row.similarity)
        if similarity >= similarity_threshold:
            results.append(
                {
                    "content": row.content,
                    "score": round(similarity, 4),
                    "doc_id": row.doc_id,
                    "chunk_index": row.chunk_index,
                    "filename": row.filename,
                    "token_count": row.token_count,
                }
            )

    logger.info(
        f"语义搜索完成: query='{query[:50]}...', " f"结果数={len(results)}/{len(rows)}, " f"阈值={similarity_threshold}"
    )

    return results


async def get_rag_context(
    query: str,
    top_k: int = 5,
    db: AsyncSession | None = None,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> str:
    """
    获取 RAG 上下文（用于 LLM 注入）

    说明：调用语义搜索获取相关文档分块，格式化为 LLM 可理解的上下文字符串。
         该上下文将被注入到 LLM 的 system prompt 或 user message 中，
         帮助 LLM 基于企业知识库回答问题。

    格式示例：
        以下是从知识库中检索到的相关信息：

        [来源: 员工手册.pdf, 分块 #3, 相关度: 0.89]
        员工请假需提前3个工作日提交申请...

        [来源: 考勤制度.docx, 分块 #7, 相关度: 0.82]
        年假天数根据工龄计算...

    参数：
        query: 用户查询文本
        top_k: 返回的最大结果数量
        db: PostgreSQL 异步数据库会话
        similarity_threshold: 相似度阈值

    返回：
        格式化的上下文字符串，如果无结果则返回空字符串
    """
    results = await search(
        query=query,
        top_k=top_k,
        db=db,
        similarity_threshold=similarity_threshold,
    )

    if not results:
        return ""

    # 格式化上下文
    context_parts = ["以下是从知识库中检索到的相关信息：\n"]

    for i, result in enumerate(results, 1):
        header = (
            f"[来源: {result.get('filename', '未知')}, "
            f"分块 #{result['chunk_index']}, "
            f"相关度: {result['score']:.2f}]"
        )
        context_parts.append(f"{header}\n{result['content']}")

    return "\n\n".join(context_parts)


async def get_document_chunks(
    doc_id: int,
    db: AsyncSession,
    page: int = 1,
    size: int = 20,
) -> tuple[list[dict], int]:
    """
    获取指定文档的分块列表（分页）

    参数：
        doc_id: 文档 ID
        db: PostgreSQL 异步数据库会话
        page: 页码（从 1 开始）
        size: 每页大小

    返回：
        (分块列表, 总数)
    """
    from sqlalchemy import func as sa_func

    # 查询总数
    count_stmt = select(sa_func.count()).select_from(RagChunk).where(RagChunk.doc_id == doc_id)
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # 查询分页数据
    offset = (page - 1) * size
    stmt = select(RagChunk).where(RagChunk.doc_id == doc_id).order_by(RagChunk.chunk_index).offset(offset).limit(size)
    result = await db.execute(stmt)
    chunks = result.scalars().all()

    chunk_list = [
        {
            "chunk_id": chunk.chunk_id,
            "doc_id": chunk.doc_id,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "token_count": chunk.token_count,
        }
        for chunk in chunks
    ]

    return chunk_list, total
