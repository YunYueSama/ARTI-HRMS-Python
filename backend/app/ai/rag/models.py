"""
RAG 数据模型和 pgvector 连接（ai/rag/models.py）

说明：定义 RAG 文档知识库的 SQLAlchemy 模型，使用 pgvector 扩展存储向量嵌入。
     这些模型存储在 PostgreSQL 数据库中（非 MySQL），使用独立的声明基类 PgVectorBase。

数据库架构：
    ┌─────────────────────────────────────────────────────────────┐
    │ PostgreSQL (hrms_vector)                                     │
    ├─────────────────────────────────────────────────────────────┤
    │ rag_document: 文档元数据（文件名、类型、状态等）              │
    │ rag_chunk: 文档分块 + 向量嵌入（content + embedding）        │
    └─────────────────────────────────────────────────────────────┘

关键技术：
    - pgvector: PostgreSQL 向量相似度搜索扩展
    - Vector(1536): 1536 维向量列（匹配 text-embedding-v3 输出维度）
    - 余弦距离: 用于语义相似度计算

用法：
    from app.ai.rag.models import RagDocument, RagChunk, PgVectorBase
"""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.core.database import PgVectorBase


class RagDocument(PgVectorBase):
    """
    文档元数据表

    说明：记录上传到 RAG 知识库的文档信息，包括文件名、类型、大小、
         处理状态和分块数量。每个文档对应多个 RagChunk 分块。

    状态流转：
        uploading → processing → ready（成功）
                                → failed（失败）

    字段说明：
        doc_id: 文档主键（自增）
        filename: 原始文件名
        file_type: 文件类型（pdf/docx/md/txt）
        file_size: 文件大小（字节）
        chunk_count: 分块数量（处理完成后更新）
        status: 处理状态
        upload_time: 上传时间
        processed_time: 处理完成时间
    """

    __tablename__ = "rag_document"

    doc_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="文档ID")
    filename: Mapped[str] = mapped_column(String(500), nullable=False, comment="原始文件名")
    file_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="文件类型(pdf/docx/md/txt)")
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="文件大小(字节)")
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="分块数量")
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="uploading",
        comment="处理状态(uploading/processing/ready/failed)",
    )
    upload_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        comment="上传时间",
    )
    processed_time: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="处理完成时间",
    )

    # 关联关系：一个文档对应多个分块
    chunks = relationship("RagChunk", back_populates="document", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<RagDocument(doc_id={self.doc_id}, filename='{self.filename}', status='{self.status}')>"


class RagChunk(PgVectorBase):
    """
    文档分块表（含向量嵌入）

    说明：存储文档分块后的文本内容和对应的向量嵌入。
         向量嵌入使用 pgvector 的 Vector 类型，支持高效的相似度搜索。

    向量维度：
        默认 1536 维，匹配 text-embedding-v3 模型输出。
        可通过 settings.EMBEDDING_DIMENSIONS 配置。

    索引策略：
        建议在 embedding 列上创建 IVFFlat 或 HNSW 索引以加速检索：
        CREATE INDEX ON rag_chunk USING hnsw (embedding vector_cosine_ops);

    字段说明：
        chunk_id: 分块主键（自增）
        doc_id: 所属文档 ID（外键）
        chunk_index: 分块在文档中的序号（从 0 开始）
        content: 分块文本内容
        embedding: 向量嵌入（1536 维浮点数组）
        token_count: 分块的 Token 数量
        create_time: 创建时间
    """

    __tablename__ = "rag_chunk"

    chunk_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="分块ID")
    doc_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("rag_document.doc_id", ondelete="CASCADE"),
        nullable=False,
        comment="所属文档ID",
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="分块序号")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="分块文本内容")
    embedding = mapped_column(
        Vector(settings.EMBEDDING_DIMENSIONS),
        nullable=True,
        comment="向量嵌入",
    )
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="Token数量")
    create_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        comment="创建时间",
    )

    # 关联关系：多个分块属于一个文档
    document = relationship("RagDocument", back_populates="chunks")

    def __repr__(self) -> str:
        return f"<RagChunk(chunk_id={self.chunk_id}, doc_id={self.doc_id}, index={self.chunk_index})>"
