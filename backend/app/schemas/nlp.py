"""
NLP 相关 Schema（schemas/nlp.py）

说明：定义 NLP 模块的请求/响应模型，包括文本分析、实体提取、情感分析等。
"""

from typing import Optional

from pydantic import BaseModel, Field


class TextAnalyzeRequest(BaseModel):
    """文本分析请求模型"""

    text: str = Field(min_length=1, max_length=5000, description="待分析的文本内容")
    tasks: list[str] = Field(
        default=["ner", "sentiment", "keywords"],
        description="分析任务列表：ner（命名实体识别）、sentiment（情感分析）、keywords（关键词提取）",
    )


class EntityItem(BaseModel):
    """命名实体识别结果"""

    text: str = Field(description="实体文本")
    label: str = Field(description="实体类型标签（如 PERSON、DEPARTMENT、DATE 等）")
    start: int = Field(description="起始位置")
    end: int = Field(description="结束位置")


class SentimentResult(BaseModel):
    """情感分析结果"""

    label: str = Field(description="情感标签：positive / neutral / negative")
    score: float = Field(ge=0.0, le=1.0, description="置信度分数")


class KeywordItem(BaseModel):
    """关键词提取结果"""

    word: str = Field(description="关键词")
    weight: float = Field(ge=0.0, le=1.0, description="权重（TF-IDF 或其他算法计算）")


class TextAnalyzeResponse(BaseModel):
    """文本分析响应模型"""

    original_text: str = Field(description="原始文本")
    entities: list[EntityItem] = Field(default_factory=list, description="命名实体列表")
    sentiment: Optional[SentimentResult] = Field(default=None, description="情感分析结果")
    keywords: list[KeywordItem] = Field(default_factory=list, description="关键词列表")


class KeywordExtractRequest(BaseModel):
    """关键词提取请求模型"""

    text: str = Field(min_length=1, max_length=10000, description="待提取的文本内容")
    top_k: int = Field(default=10, ge=1, le=50, description="返回前 N 个关键词")


class KeywordExtractResponse(BaseModel):
    """关键词提取响应模型"""

    keywords: list[KeywordItem] = Field(description="关键词列表")
    total_words: int = Field(description="文本总词数")


class SentimentAnalyzeRequest(BaseModel):
    """情感分析请求模型"""

    text: str = Field(min_length=1, max_length=5000, description="待分析的文本内容")


class SentimentAnalyzeResponse(BaseModel):
    """情感分析响应模型"""

    sentiment: SentimentResult = Field(description="情感分析结果")
