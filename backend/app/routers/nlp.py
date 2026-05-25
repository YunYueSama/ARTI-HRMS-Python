"""
NLP 文本分析路由（routers/nlp.py）

说明：定义 NLP 文本分析模块的 API 端点，包括实体识别、情感分析和关键词提取。

端点列表：
    POST /api/nlp/analyze    → 综合文本分析（NER + 情感 + 关键词）
    POST /api/nlp/entities   → 命名实体识别
    POST /api/nlp/sentiment  → 情感分析
    POST /api/nlp/keywords   → 关键词提取
"""

import logging

from fastapi import APIRouter, Depends

from app.ai.nlp_tools import NLPService
from app.ai.chat.llm_provider import get_primary_model
from app.core.config import get_runtime_overrides
from app.core.dependencies import get_current_user, TokenPayload
from app.schemas.common import ApiResponse, ok
from app.schemas.nlp import (
    KeywordExtractRequest,
    KeywordExtractResponse,
    KeywordItem,
    SentimentAnalyzeRequest,
    SentimentAnalyzeResponse,
    SentimentResult,
    TextAnalyzeRequest,
    TextAnalyzeResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_nlp_service() -> NLPService:
    """获取 NLP 服务实例（延迟初始化 LLM）"""
    model = get_primary_model(get_runtime_overrides() or None)
    return NLPService(model=model)


# ============================================================
# POST /api/nlp/analyze - 综合文本分析
# ============================================================


@router.post("/analyze", response_model=ApiResponse)
async def analyze_text(
    request: TextAnalyzeRequest,
    user: TokenPayload = Depends(get_current_user),
) -> ApiResponse:
    """
    综合文本分析

    说明：对输入文本执行多种 NLP 分析任务，包括命名实体识别（NER）、
         情感分析和关键词提取。可通过 tasks 参数指定需要的分析任务。

    请求体：
        - text: 待分析文本（1-5000 字符）
        - tasks: 分析任务列表，默认 ["ner", "sentiment", "keywords"]
    """
    service = _get_nlp_service()
    result = await service.analyze_text(
        text=request.text,
        tasks=request.tasks,
    )

    response = TextAnalyzeResponse(
        original_text=request.text,
        entities=result.get("entities", []),
        sentiment=result.get("sentiment"),
        keywords=result.get("keywords", []),
    )

    return ok(data=response.model_dump(mode="json"), message="文本分析完成")


# ============================================================
# POST /api/nlp/entities - 命名实体识别
# ============================================================


@router.post("/entities", response_model=ApiResponse)
async def extract_entities(
    request: TextAnalyzeRequest,
    user: TokenPayload = Depends(get_current_user),
) -> ApiResponse:
    """
    命名实体识别（NER）

    说明：识别 HR 领域的命名实体，包括人名、部门名、职位、日期、
         金额、请假类型等。采用规则匹配 + LLM 辅助的混合策略。

    请求体：
        - text: 待分析文本（1-5000 字符）
    """
    service = _get_nlp_service()
    entities = await service.extract_entities(request.text)

    return ok(
        data=[e.model_dump(mode="json") for e in entities],
        message=f"识别到 {len(entities)} 个实体",
    )


# ============================================================
# POST /api/nlp/sentiment - 情感分析
# ============================================================


@router.post("/sentiment", response_model=ApiResponse)
async def analyze_sentiment(
    request: SentimentAnalyzeRequest,
    user: TokenPayload = Depends(get_current_user),
) -> ApiResponse:
    """
    情感分析

    说明：判断文本的情感倾向，返回 positive/neutral/negative 标签和置信度。
         优先使用关键词规则匹配，无法确定时回退到 LLM 分析。

    请求体：
        - text: 待分析文本（1-5000 字符）
    """
    service = _get_nlp_service()
    sentiment = await service.analyze_sentiment(request.text)

    response = SentimentAnalyzeResponse(sentiment=sentiment)

    return ok(data=response.model_dump(mode="json"), message="情感分析完成")


# ============================================================
# POST /api/nlp/keywords - 关键词提取
# ============================================================


@router.post("/keywords", response_model=ApiResponse)
async def extract_keywords(
    request: KeywordExtractRequest,
    user: TokenPayload = Depends(get_current_user),
) -> ApiResponse:
    """
    关键词提取

    说明：基于词频统计提取文本关键词，不依赖 LLM，零延迟。
         适用于快速分析文本主题和重点内容。

    请求体：
        - text: 待分析文本（1-10000 字符）
        - top_k: 返回前 N 个关键词（1-50，默认 10）
    """
    service = _get_nlp_service()
    keywords, total_words = service.extract_keywords(request.text, request.top_k)

    response = KeywordExtractResponse(
        keywords=keywords,
        total_words=total_words,
    )

    return ok(data=response.model_dump(mode="json"), message=f"提取到 {len(keywords)} 个关键词")
