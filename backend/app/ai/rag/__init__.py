"""
RAG 文档知识库模块

说明：实现基于 pgvector 的文档向量存储和语义检索功能。
     包含文档上传、文本分块、向量嵌入和相似度搜索。

子模块：
    - models: pgvector 数据模型（RagDocument, RagChunk）
    - pipeline: 文档处理管线（上传、分块、嵌入）
    - retriever: 语义检索器（向量相似度搜索）
"""
