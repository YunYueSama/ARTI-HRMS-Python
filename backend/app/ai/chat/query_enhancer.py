"""
查询增强引擎（ai/chat/query_enhancer.py）

说明：对简短/模糊的用户问题进行语义增强，提升向量检索的召回率。
     支持三种增强策略：
     1. 查询改写（Rewrite）：重新表述以匹配知识库用语
     2. 查询扩展（Expand）：生成相关搜索词
     3. HyDE（假设性文档嵌入）：生成假设性答案用于嵌入检索

增强策略：
    简单查询（字符数 < 15 或缺少上下文信号词）→ 触发增强
    复杂查询 → 直接使用原始查询

模型选择：
    使用与主 LLM 同 provider 的便宜模型（qwen-turbo）进行增强，
    三个增强请求并行执行，总延迟约等于 1 次 LLM 调用。
"""

import asyncio
import logging

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage

from app.ai.rag.retriever import search
from app.core.config import LLMProviderConfig, settings

logger = logging.getLogger(__name__)

# 上下文信号词 — 有足够信息量的查询不需要增强
_CONTEXT_SIGNALS = frozenset(
    [
        "如何", "怎么", "为什么", "什么时候", "告诉我", "查询",
        "请问", "帮我", "解释", "什么是", "多少", "哪些",
        "区别", "对比", "哪些", "有没有", "能不能", "可以",
    ]
)


def is_simple_query(message: str) -> bool:
    """
    判断是否为简单查询（需要增强）。

    规则：
    1. 字符数 < 15（中文约5个字，英文约3个词）
    2. 不含上下文信号词
    """
    stripped = message.strip()
    if len(stripped) < 15:
        return True
    if not any(s in stripped for s in _CONTEXT_SIGNALS):
        return True
    return False


class QueryEnhancer:
    """使用便宜模型进行查询增强（单例）"""

    def __init__(self):
        self._model: BaseChatModel | None = None

    def _ensure_model(self) -> BaseChatModel | None:
        """懒加载便宜模型"""
        if self._model is not None:
            return self._model

        try:
            from app.ai.chat.llm_provider import get_chat_model, _is_placeholder_key

            config = settings.primary_llm_config
            if _is_placeholder_key(config.api_key):
                logger.warning("LLM API Key 未配置，查询增强不可用")
                return None

            # 使用与主模型相同的 provider，但指定 qwen-turbo 作为增强模型
            enhancer_config = LLMProviderConfig(
                provider=config.provider,
                base_url=config.base_url,
                api_key=config.api_key,
                model="qwen-turbo",
                temperature=0.3,
                max_tokens=512,
            )
            self._model = get_chat_model(enhancer_config)
            return self._model
        except Exception as e:
            logger.warning(f"查询增强模型初始化失败: {e}")
            return None

    async def _call(self, prompt: str) -> str:
        """调用增强模型"""
        model = self._ensure_model()
        if model is None:
            return ""
        try:
            response = await model.ainvoke([HumanMessage(content=prompt)])
            return str(response.content).strip()
        except Exception as e:
            logger.warning(f"查询增强调用失败: {e}")
            return ""

    async def rewrite(self, query: str) -> str:
        """查询改写：重新表述以匹配知识库用语"""
        prompt = (
            "请将以下用户问题改写为更适合企业知识库检索的查询语句。\n"
            "要求：保持原意，使用更正式、更完整的表述，只返回改写后的查询，不要解释。\n"
            f"原问题：{query}"
        )
        return await self._call(prompt)

    async def expand(self, query: str) -> list[str]:
        """查询扩展：生成相关搜索关键词"""
        prompt = (
            "为以下企业人事系统相关问题生成3个相关的搜索关键词或短语。\n"
            "每行一个，不要编号，不要解释。关键词应该能帮助在知识库中找到相关信息。\n"
            f"问题：{query}"
        )
        result = await self._call(prompt)
        if not result:
            return []
        return [line.strip() for line in result.split("\n") if line.strip()][:3]

    async def hyde(self, query: str) -> str:
        """HyDE：生成假设性文档片段用于嵌入检索"""
        prompt = (
            "请为以下问题生成一段简洁的假设性答案（模拟企业文档片段）。\n"
            "要求：用正式的企业文档语气，包含具体的数据和流程，50-100字即可。\n"
            "这段文字将用于向量检索匹配，不需要准确，只需要语义接近。\n"
            f"问题：{query}"
        )
        return await self._call(prompt)


# 全局单例
query_enhancer = QueryEnhancer()


def _deduplicate_results(all_results: list[list[dict]]) -> list[dict]:
    """
    去重合并向量检索结果

    基于 doc_id + chunk_index 去重，保留最高分的版本。
    """
    seen: dict[tuple, dict] = {}
    for results in all_results:
        if not isinstance(results, list):
            continue
        for item in results:
            key = (item.get("doc_id"), item.get("chunk_index"))
            if key not in seen or item.get("score", 0) > seen[key].get("score", 0):
                seen[key] = item

    # 按分数降序排列
    return sorted(seen.values(), key=lambda x: x.get("score", 0), reverse=True)


async def enhanced_vector_search(query: str, db) -> list[dict]:
    """
    增强向量检索

    完整流程：
    1. 检测是否需要增强
    2. 复杂查询 → 直接检索
    3. 简单查询 → 并行增强（rewrite + expand + hyde）→ 多查询并行检索 → 去重合并

    参数：
        query: 用户查询
        db: 数据库会话

    返回：
        去重合并后的向量检索结果列表
    """
    if not is_simple_query(query):
        # 复杂查询不需要增强，直接检索
        return await search(query, top_k=5, db=db)

    enhancer = query_enhancer

    # 检查增强模型是否可用
    if enhancer._ensure_model() is None:
        logger.info("增强模型不可用，使用原始查询直接检索")
        return await search(query, top_k=5, db=db)

    # 并行执行三种增强
    try:
        rewritten, expansions, hyde_text = await asyncio.gather(
            enhancer.rewrite(query),
            enhancer.expand(query),
            enhancer.hyde(query),
            return_exceptions=True,
        )
    except Exception as e:
        logger.warning(f"查询增强失败，回退到原始查询: {e}")
        return await search(query, top_k=5, db=db)

    # 收集所有查询变体
    queries = [query]  # 始终保留原始查询
    if isinstance(rewritten, str) and rewritten and rewritten != query:
        queries.append(rewritten)
        logger.debug(f"查询改写: {query} → {rewritten}")
    if isinstance(expansions, list):
        queries.extend(expansions)
        logger.debug(f"查询扩展: {expansions}")
    if isinstance(hyde_text, str) and hyde_text:
        queries.append(hyde_text)
        logger.debug(f"HyDE 生成: {hyde_text[:50]}...")

    # 对每个查询变体执行向量检索（并行）
    search_tasks = [search(q, top_k=3, db=db) for q in queries]
    all_results = await asyncio.gather(*search_tasks, return_exceptions=True)

    # 记录异常
    for i, r in enumerate(all_results):
        if isinstance(r, BaseException):
            logger.warning(f"向量检索异常 (查询#{i}): {r}")

    # 过滤异常结果
    valid_results = [r for r in all_results if isinstance(r, list)]

    # 去重合并
    merged = _deduplicate_results(valid_results)

    logger.info(
        f"增强检索完成: 原始查询='{query[:30]}...', "
        f"查询变体数={len(queries)}, "
        f"有效结果={len(valid_results)}/{len(all_results)}, "
        f"合并结果数={len(merged)}"
    )

    return merged[:10]  # 最多返回 10 条
