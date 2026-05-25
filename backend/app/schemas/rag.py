"""
RAG 知识库请求/响应模型（schemas/rag.py）

说明：定义 RAG 文档知识库 API 的请求和响应数据模型。
     使用 Pydantic v2 进行数据校验和序列化。

模型列表：
    - DocumentUploadResponse: 文档上传响应
    - DocumentListResponse: 文档列表项
    - ChunkPreviewResponse: 分块预览
    - SearchRequest: 语义搜索请求
    - SearchResult: 搜索结果项
"""

from datetime import datetime

from pydantic import BaseModel, Field


class DocumentUploadResponse(BaseModel):
    """
    文档上传响应

    说明：文档上传并处理完成后返回的信息。
    """

    doc_id: int = Field(description="文档 ID")
    filename: str = Field(description="文件名")
    file_type: str = Field(description="文件类型")
    chunk_count: int = Field(description="分块数量")
    status: str = Field(description="处理状态(processing/ready/failed)")


class DocumentListResponse(BaseModel):
    """
    文档列表项

    说明：文档列表查询时返回的单条文档信息。
    """

    doc_id: int = Field(description="文档 ID")
    filename: str = Field(description="文件名")
    file_type: str = Field(description="文件类型")
    file_size: int = Field(description="文件大小(字节)")
    chunk_count: int = Field(description="分块数量")
    status: str = Field(description="处理状态")
    upload_time: datetime = Field(description="上传时间")
    processed_time: datetime | None = Field(default=None, description="处理完成时间")

    model_config = {"from_attributes": True}


class ChunkPreviewResponse(BaseModel):
    """
    分块预览响应

    说明：查看文档分块详情时返回的单条分块信息。
    """

    chunk_id: int = Field(description="分块 ID")
    doc_id: int = Field(description="所属文档 ID")
    chunk_index: int = Field(description="分块序号")
    content: str = Field(description="分块文本内容")
    token_count: int = Field(description="Token 数量")

    model_config = {"from_attributes": True}


class SearchRequest(BaseModel):
    """
    语义搜索请求

    说明：用户提交的语义搜索参数。
    """

    query: str = Field(min_length=1, max_length=1000, description="搜索查询文本")
    top_k: int = Field(default=5, ge=1, le=20, description="返回结果数量")


class SearchResult(BaseModel):
    """
    搜索结果项

    说明：语义搜索返回的单条结果，包含分块内容和相似度分数。
    """

    content: str = Field(description="分块文本内容")
    score: float = Field(description="相似度分数(0-1)")
    doc_id: int = Field(description="所属文档 ID")
    chunk_index: int = Field(description="分块序号")
    filename: str | None = Field(default=None, description="所属文档文件名")
    token_count: int | None = Field(default=None, description="Token 数量")
