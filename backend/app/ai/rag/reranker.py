"""
检索重排序器（ai/rag/reranker.py）

说明：对向量检索的结果进行二次精排，提升检索准确率。
     使用 LLM 对每个候选结果与查询的相关性进行打分，
     按分数重新排序后返回 Top-N 结果。

设计思路：
    向量余弦相似度只能捕捉粗粒度语义相关性，
    Cross-Encoder 或 LLM Rerank 可以做更精细的相关性判断。
    本模块复用现有 qwen-turbo 模型做 Rerank，不引入额外依赖。

降级策略：
    LLM 不可用或调用失败时，直接返回原始排序结果。

用法：
    from app.ai.rag.reranker import rerank_results

    reranked = await rerank_results(
        query="员工请假流程",
        results=vector_search_results,
        top_n=5,
    )
"""

import asyncio
import logging
import re

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage

from app.core.config import LLMProviderConfig, settings

logger = logging.getLogger(__name__)


class Reranker:
    """
    基于 LLM 的检索结果重排序器

    说明：使用便宜模型（qwen-turbo）对检索结果进行相关性打分。
         每个结果独立评分，避免位置偏差。
         批量处理以控制 API 调用次数。

    属性：
        _model: LLM 模型实例（懒加载）
    """

    def __init__(self):
        self._model: BaseChatModel | None = None

    def _ensure_model(self) -> BaseChatModel | None:
        """懒加载 Rerank 模型"""
        if self._model is not None:
            return self._model

        try:
            from app.ai.chat.llm_provider import _is_placeholder_key, get_chat_model

            config = settings.primary_llm_config
            if _is_placeholder_key(config.api_key):
                logger.warning("LLM API Key 未配置，Rerank 不可用")
                return None

            rerank_config = LLMProviderConfig(
                provider=config.provider,
                base_url=config.base_url,
                api_key=config.api_key,
                model="qwen-turbo",
                temperature=0.1,  # 低温度保证打分稳定
                max_tokens=32,    # 只输出分数
            )
            self._model = get_chat_model(rerank_config)
            return self._model
        except Exception as e:
            logger.warning(f"Rerank 模型初始化失败: {e}")
            return None

    async def score(self, query: str, content: str) -> float:
        """
        对单个结果与查询的相关性打分

        参数：
            query: 用户查询
            content: 检索结果内容

        返回：
            相关性分数（0.0 - 1.0）
        """
        model = self._ensure_model()
        if model is None:
            return -1.0  # 表示不可用

        prompt = (
            "请判断以下文档片段与用户问题的相关性。\n"
            "评分标准：0=完全无关，1=高度相关，0.5=部分相关。\n"
            "只输出一个 0 到 1 之间的数字，不要解释。\n\n"
            f"用户问题：{query}\n\n"
            f"文档片段：{content[:500]}\n\n"
            "相关性分数（0-1）："
        )

        try:
            response = await model.ainvoke([HumanMessage(content=prompt)])
            score_text = response.content.strip()
            # 提取数字
            match = re.search(r"(\d+\.?\d*)", score_text)
            if match:
                score = float(match.group(1))
                return min(max(score, 0.0), 1.0)  # 钳制到 [0, 1]
            return 0.5  # 解析失败返回中性分数
        except Exception as e:
            logger.warning(f"Rerank 打分失败: {e}")
            return -1.0

    async def rerank(
        self,
        query: str,
        results: list[dict],
        top_n: int = 5,
        batch_size: int = 5,
    ) -> list[dict]:
        """
        对检索结果批量打分并重新排序

        参数：
            query: 用户查询
            results: 检索结果列表（需包含 content 字段）
            top_n: 返回的结果数量
            batch_size: 每批打分的结果数量

        返回：
            按相关性分数重新排序的结果列表
        """
        if not results:
            return []

        model = self._ensure_model()
        if model is None:
            # 模型不可用，返回原始排序
            logger.info("Rerank 模型不可用，返回原始排序")
            return results[:top_n]

        # 批量打分（并行）
        score_tasks = [self.score(query, r.get("content", "")) for r in results]
        scores = await asyncio.gather(*score_tasks, return_exceptions=True)

        # 组装分数
        scored_results = []
        for result, score in zip(results, scores):
            if isinstance(score, Exception) or score < 0:
                # 打分失败，使用原始分数
                scored_results.append(result)
            else:
                r = result.copy()
                r["rerank_score"] = round(float(score), 4)
                scored_results.append(r)

        # 按 rerank_score 降序排序（没有 rerank_score 的用原始 score）
        scored_results.sort(
            key=lambda x: x.get("rerank_score", x.get("score", 0)),
            reverse=True,
        )

        logger.info(
            f"Rerank 完成: 输入={len(results)}条, "
            f"输出={min(top_n, len(scored_results))}条"
        )

        return scored_results[:top_n]


# 全局单例
reranker = Reranker()


async def rerank_results(
    query: str,
    results: list[dict],
    top_n: int = 5,
) -> list[dict]:
    """
    重排序检索结果（便捷函数）

    参数：
        query: 用户查询
        results: 检索结果列表
        top_n: 返回的结果数量

    返回：
        重新排序后的结果列表
    """
    return await reranker.rerank(query, results, top_n)
