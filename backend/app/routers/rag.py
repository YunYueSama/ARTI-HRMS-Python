"""
RAG 知识库路由（routers/rag.py）

说明：定义 RAG 文档知识库的 API 端点，包括文档上传、列表查询、
     分块预览、语义搜索和文档删除。

端点列表：
    POST   /api/rag/upload              → 上传文档（multipart/form-data）
    GET    /api/rag/documents            → 文档列表（分页）
    GET    /api/rag/documents/{doc_id}/chunks → 分块预览（分页）
    DELETE /api/rag/documents/{doc_id}   → 删除文档及其分块
    POST   /api/rag/search              → 语义搜索
    POST   /api/rag/reprocess/{doc_id}  → 重新处理文档

Java 对应关系：
    无直接对应（Python 新增的 RAG 功能模块）

文件上传说明：
    使用 FastAPI 的 UploadFile 处理 multipart/form-data 文件上传。
    上传的文件先保存到临时目录，处理完成后清理临时文件。
"""

import logging
import os
import tempfile
from datetime import datetime

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.rag.models import RagChunk, RagDocument
from app.ai.rag.pipeline import ingest_document
from app.ai.rag.retriever import get_document_chunks, search
from app.core.config import settings
from app.core.database import get_pgvector_session
from app.core.dependencies import TokenPayload, get_current_user
from app.schemas.common import ApiResponse, PageResponse, fail, ok
from app.schemas.rag import (
    ChunkPreviewResponse,
    DocumentListResponse,
    DocumentUploadResponse,
    SearchRequest,
    SearchResult,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# 支持的文件类型
ALLOWED_FILE_TYPES = {"pdf", "docx", "md", "txt"}
# 最大文件大小（10MB）
MAX_FILE_SIZE = 10 * 1024 * 1024


@router.post("/upload", summary="上传文档")
async def upload_document(
    file: UploadFile = File(..., description="上传的文档文件"),
    db: AsyncSession = Depends(get_pgvector_session),
    current_user: TokenPayload = Depends(get_current_user),
) -> ApiResponse[DocumentUploadResponse]:
    """
    上传文档到 RAG 知识库

    说明：接收文件上传，提取文本、分块、生成嵌入并存储到 pgvector。
         支持 PDF、DOCX、MD、TXT 格式，最大 10MB。

    处理流程：
        1. 校验文件类型和大小
        2. 保存到临时目录
        3. 调用处理管线（提取 → 清洗 → 分块 → 嵌入 → 存储）
        4. 清理临时文件
        5. 返回处理结果
    """
    # 校验文件名
    if not file.filename:
        return fail(message="文件名不能为空")

    # 提取文件扩展名
    file_ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if file_ext not in ALLOWED_FILE_TYPES:
        return fail(message=f"不支持的文件类型: .{file_ext}，支持: {', '.join(ALLOWED_FILE_TYPES)}")

    # 读取文件内容并校验大小
    content = await file.read()
    file_size = len(content)
    if file_size > MAX_FILE_SIZE:
        return fail(message=f"文件过大，最大支持 {MAX_FILE_SIZE // (1024*1024)}MB")
    if file_size == 0:
        return fail(message="文件内容为空")

    # 保存到临时文件
    temp_dir = tempfile.mkdtemp(prefix="hrms_rag_")
    temp_path = os.path.join(temp_dir, file.filename)

    try:
        # 写入临时文件
        with open(temp_path, "wb") as f:
            f.write(content)

        # 调用处理管线
        result = await ingest_document(
            file_path=temp_path,
            filename=file.filename,
            file_type=file_ext,
            file_size=file_size,
            db=db,
        )

        # 构建响应
        response_data = DocumentUploadResponse(
            doc_id=result["doc_id"],
            filename=result["filename"],
            file_type=file_ext,
            chunk_count=result["chunks"],
            status=result["status"],
        )

        if result["status"] == "failed":
            return fail(
                message=f"文档处理失败: {result.get('error', '未知错误')}",
                data=response_data,
            )

        return ok(data=response_data, message="文档上传并处理成功")

    finally:
        # 清理临时文件
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)
        except OSError as e:
            logger.warning(f"清理临时文件失败: {e}")


@router.get("/documents", summary="文档列表")
async def list_documents(
    page: int = Query(default=1, ge=1, description="页码"),
    size: int = Query(default=10, ge=1, le=500, description="每页大小"),
    current_user: TokenPayload = Depends(get_current_user),
) -> ApiResponse[PageResponse[DocumentListResponse]]:
    """
    获取文档列表（分页）

    说明：查询所有已上传的文档，按上传时间倒序排列。
         如果 pgvector 数据库未就绪（PostgreSQL 未启动），返回空列表 + 友好提示，
         避免页面整体崩溃为"服务器内部错误"。
    """
    from app.core.database import PgVectorSessionFactory

    # 优雅降级：pgvector 不可用时直接返回空列表
    if PgVectorSessionFactory is None:
        empty_page: PageResponse = PageResponse(items=[], total=0, page=page, size=size)
        return ok(
            data=empty_page,
            message="向量数据库尚未启动，RAG 知识库当前不可用。请先启动 PostgreSQL + pgvector。",
        )

    async with PgVectorSessionFactory() as db:
        try:
            # 查询总数
            count_stmt = select(func.count()).select_from(RagDocument)
            total_result = await db.execute(count_stmt)
            total = total_result.scalar() or 0

            # 查询分页数据
            offset = (page - 1) * size
            stmt = select(RagDocument).order_by(RagDocument.upload_time.desc()).offset(offset).limit(size)
            result = await db.execute(stmt)
            documents = result.scalars().all()

            # 转换为响应模型
            items = [
                DocumentListResponse(
                    doc_id=doc.doc_id,
                    filename=doc.filename,
                    file_type=doc.file_type,
                    file_size=doc.file_size,
                    chunk_count=doc.chunk_count,
                    status=doc.status,
                    upload_time=doc.upload_time,
                    processed_time=doc.processed_time,
                )
                for doc in documents
            ]

            page_response = PageResponse(
                items=items,
                total=total,
                page=page,
                size=size,
            )
            return ok(data=page_response)
        except Exception as exc:
            await db.rollback()
            logger.warning(f"RAG 文档列表查询失败：{exc}")
            empty_page = PageResponse(items=[], total=0, page=page, size=size)
            return ok(
                data=empty_page,
                message=f"向量数据库连接失败：{exc.__class__.__name__}。请检查 PostgreSQL 与 pgvector 是否就绪。",
            )


@router.get("/documents/{doc_id}/chunks", summary="分块预览")
async def get_chunks(
    doc_id: int,
    page: int = Query(default=1, ge=1, description="页码"),
    size: int = Query(default=20, ge=1, le=500, description="每页大小"),
    db: AsyncSession = Depends(get_pgvector_session),
    current_user: TokenPayload = Depends(get_current_user),
) -> ApiResponse[PageResponse[ChunkPreviewResponse]]:
    """
    获取文档分块预览（分页）

    说明：查看指定文档的所有分块内容，按分块序号排列。
         用于调试和验证分块效果。
    """
    # 检查文档是否存在
    doc_stmt = select(RagDocument).where(RagDocument.doc_id == doc_id)
    doc_result = await db.execute(doc_stmt)
    document = doc_result.scalar_one_or_none()

    if not document:
        return fail(message=f"文档不存在: doc_id={doc_id}")

    # 获取分块列表
    chunk_list, total = await get_document_chunks(doc_id, db, page, size)

    items = [ChunkPreviewResponse(**chunk) for chunk in chunk_list]

    page_response = PageResponse(
        items=items,
        total=total,
        page=page,
        size=size,
    )

    return ok(data=page_response)


@router.delete("/documents/{doc_id}", summary="删除文档")
async def delete_document(
    doc_id: int,
    db: AsyncSession = Depends(get_pgvector_session),
    current_user: TokenPayload = Depends(get_current_user),
) -> ApiResponse:
    """
    删除文档及其所有分块

    说明：级联删除文档记录和关联的所有分块数据（包括向量嵌入）。
         此操作不可逆。
    """
    # 检查文档是否存在
    doc_stmt = select(RagDocument).where(RagDocument.doc_id == doc_id)
    doc_result = await db.execute(doc_stmt)
    document = doc_result.scalar_one_or_none()

    if not document:
        return fail(message=f"文档不存在: doc_id={doc_id}")

    filename = document.filename

    # 删除分块（级联删除也会处理，但显式删除更清晰）
    await db.execute(delete(RagChunk).where(RagChunk.doc_id == doc_id))

    # 删除文档
    await db.execute(delete(RagDocument).where(RagDocument.doc_id == doc_id))

    logger.info(f"文档已删除: doc_id={doc_id}, filename={filename}")
    return ok(message=f"文档 '{filename}' 已删除")


@router.post("/search", summary="语义搜索")
async def semantic_search(
    request: SearchRequest,
    db: AsyncSession = Depends(get_pgvector_session),
    current_user: TokenPayload = Depends(get_current_user),
) -> ApiResponse[list[SearchResult]]:
    """
    语义搜索

    说明：将查询文本转换为向量，在知识库中搜索最相关的文档分块。
         返回按相似度降序排列的结果列表。

    注意：如果嵌入 API 未配置，搜索将返回空结果。
    """
    results = await search(
        query=request.query,
        top_k=request.top_k,
        db=db,
    )

    # 转换为响应模型
    search_results = [
        SearchResult(
            content=r["content"],
            score=r["score"],
            doc_id=r["doc_id"],
            chunk_index=r["chunk_index"],
            filename=r.get("filename"),
            token_count=r.get("token_count"),
        )
        for r in results
    ]

    return ok(data=search_results, message=f"找到 {len(search_results)} 条相关结果")


@router.post("/reprocess/{doc_id}", summary="重新处理文档")
async def reprocess_document(
    doc_id: int,
    db: AsyncSession = Depends(get_pgvector_session),
    current_user: TokenPayload = Depends(get_current_user),
) -> ApiResponse[DocumentUploadResponse]:
    """
    重新处理文档

    说明：删除文档的现有分块，重新执行文本提取、分块和嵌入流程。
         适用于嵌入模型更新后需要重新生成向量的场景。

    注意：由于原始文件已被清理，此接口需要文档仍有可用的分块内容。
         实际实现中会从现有分块重新组装文本并重新处理。
    """
    # 检查文档是否存在
    doc_stmt = select(RagDocument).where(RagDocument.doc_id == doc_id)
    doc_result = await db.execute(doc_stmt)
    document = doc_result.scalar_one_or_none()

    if not document:
        return fail(message=f"文档不存在: doc_id={doc_id}")

    # 获取现有分块内容，重新组装原始文本
    chunk_stmt = select(RagChunk).where(RagChunk.doc_id == doc_id).order_by(RagChunk.chunk_index)
    chunk_result = await db.execute(chunk_stmt)
    existing_chunks = chunk_result.scalars().all()

    if not existing_chunks:
        return fail(message="文档没有可用的分块内容，无法重新处理")

    # 组装原始文本
    original_text = "\n\n".join(chunk.content for chunk in existing_chunks)

    # 删除现有分块
    await db.execute(delete(RagChunk).where(RagChunk.doc_id == doc_id))

    # 更新文档状态为 processing
    document.status = "processing"
    document.chunk_count = 0
    document.processed_time = None
    await db.flush()

    # 重新分块和嵌入
    try:
        from app.ai.rag.pipeline import estimate_token_count, generate_embeddings, split_text

        # 分块
        chunks = split_text(
            text=original_text,
            chunk_size=settings.RAG_CHUNK_SIZE,
            chunk_overlap=settings.RAG_CHUNK_OVERLAP,
        )

        if not chunks:
            document.status = "failed"
            await db.flush()
            return fail(message="重新分块结果为空")

        # 生成嵌入
        embeddings = await generate_embeddings(chunks)

        # 存储新分块
        for idx, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            chunk = RagChunk(
                doc_id=doc_id,
                chunk_index=idx,
                content=chunk_text,
                embedding=embedding,
                token_count=estimate_token_count(chunk_text),
            )
            db.add(chunk)

        # 更新文档状态
        document.status = "ready"
        document.chunk_count = len(chunks)
        document.processed_time = datetime.now()
        await db.flush()

        response_data = DocumentUploadResponse(
            doc_id=doc_id,
            filename=document.filename,
            file_type=document.file_type,
            chunk_count=len(chunks),
            status="ready",
        )

        return ok(data=response_data, message="文档重新处理成功")

    except Exception as e:
        document.status = "failed"
        document.processed_time = datetime.now()
        await db.flush()

        logger.error(f"文档重新处理失败: doc_id={doc_id}, 错误: {e}")
        return fail(message=f"重新处理失败: {str(e)}")
