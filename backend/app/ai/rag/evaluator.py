"""
RAG 评测框架（ai/rag/evaluator.py）

说明：提供 RAG 检索和生成质量的自动化评测能力。
     基于 LLM 的评测方法（类似 RAGAS），不引入额外依赖。

评测指标：
    - faithfulness（忠实度）：回答是否基于检索到的上下文，无幻觉
    - answer_relevancy（回答相关性）：回答是否与问题相关
    - context_precision（上下文精确率）：检索结果中相关结果的比例

用法：
    from app.ai.rag.evaluator import RAGEvaluator

    evaluator = RAGEvaluator()
    results = await evaluator.evaluate_batch(eval_dataset)
    report = evaluator.generate_report(results)
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage

from app.core.config import LLMProviderConfig, settings

logger = logging.getLogger(__name__)


@dataclass
class EvalCase:
    """单个评测用例"""
    question: str
    answer: str
    contexts: list[str]          # 检索到的上下文片段
    ground_truth: str = ""       # 标准答案（可选）


@dataclass
class EvalResult:
    """单个评测结果"""
    question: str
    faithfulness: float = 0.0    # 0-1
    answer_relevancy: float = 0.0  # 0-1
    context_precision: float = 0.0  # 0-1
    ground_truth_similarity: float = 0.0  # 0-1（有标准答案时）


@dataclass
class EvalReport:
    """评测报告"""
    total_cases: int = 0
    avg_faithfulness: float = 0.0
    avg_answer_relevancy: float = 0.0
    avg_context_precision: float = 0.0
    avg_ground_truth_similarity: float = 0.0
    results: list[EvalResult] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class RAGEvaluator:
    """
    RAG 质量评测器

    说明：使用 LLM 对 RAG 的检索和生成质量进行自动化评测。
         评测方法参考 RAGAS 框架，但使用 LLM 替代模型评分。
    """

    def __init__(self):
        self._model: BaseChatModel | None = None

    def _ensure_model(self) -> BaseChatModel | None:
        """懒加载评测模型"""
        if self._model is not None:
            return self._model

        try:
            from app.ai.chat.llm_provider import _is_placeholder_key, get_chat_model

            config = settings.primary_llm_config
            if _is_placeholder_key(config.api_key):
                logger.warning("LLM API Key 未配置，RAG 评测不可用")
                return None

            eval_config = LLMProviderConfig(
                provider=config.provider,
                base_url=config.base_url,
                api_key=config.api_key,
                model="qwen-turbo",
                temperature=0.1,
                max_tokens=16,
            )
            self._model = get_chat_model(eval_config)
            return self._model
        except Exception as e:
            logger.warning(f"评测模型初始化失败: {e}")
            return None

    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM 并返回结果"""
        model = self._ensure_model()
        if model is None:
            return ""
        try:
            response = await model.ainvoke([HumanMessage(content=prompt)])
            return response.content.strip()
        except Exception as e:
            logger.warning(f"评测 LLM 调用失败: {e}")
            return ""

    def _extract_score(self, text: str) -> float:
        """从 LLM 输出中提取分数"""
        import re
        match = re.search(r"(\d+\.?\d*)", text)
        if match:
            score = float(match.group(1))
            if score > 1:
                score = score / 10  # 处理 0-10 分制
            return min(max(score, 0.0), 1.0)
        return 0.5

    async def evaluate_faithfulness(self, question: str, answer: str, contexts: list[str]) -> float:
        """
        评测忠实度：回答是否基于检索到的上下文

        方法：检查回答中的每个声明是否能从上下文中找到依据。
        """
        context_text = "\n".join(contexts[:5])
        prompt = (
            "请评估以下回答是否完全基于给定的参考文档。\n"
            "评分标准：\n"
            "- 1.0: 回答中的所有信息都能在参考文档中找到依据\n"
            "- 0.5: 回答部分基于文档，部分来自推测\n"
            "- 0.0: 回答包含文档中没有的信息（幻觉）\n\n"
            f"用户问题：{question}\n\n"
            f"参考文档：{context_text[:1000]}\n\n"
            f"AI 回答：{answer[:500]}\n\n"
            "忠实度分数（0-1）："
        )
        result = await self._call_llm(prompt)
        return self._extract_score(result)

    async def evaluate_answer_relevancy(self, question: str, answer: str) -> float:
        """
        评测回答相关性：回答是否与问题相关

        方法：检查回答是否直接回应了用户的问题。
        """
        prompt = (
            "请评估以下回答是否与用户问题相关。\n"
            "评分标准：\n"
            "- 1.0: 回答直接、完整地回应了问题\n"
            "- 0.5: 回答部分相关，但没有完全回答问题\n"
            "- 0.0: 回答与问题完全无关\n\n"
            f"用户问题：{question}\n\n"
            f"AI 回答：{answer[:500]}\n\n"
            "相关性分数（0-1）："
        )
        result = await self._call_llm(prompt)
        return self._extract_score(result)

    async def evaluate_context_precision(self, question: str, contexts: list[str]) -> float:
        """
        评测上下文精确率：检索结果中相关结果的比例

        方法：检查每个检索到的上下文片段是否与问题相关。
        """
        if not contexts:
            return 0.0

        relevant_count = 0
        for ctx in contexts[:5]:
            prompt = (
                "请判断以下文档片段是否与用户问题相关。\n"
                "只回答 1（相关）或 0（无关），不要解释。\n\n"
                f"用户问题：{question}\n\n"
                f"文档片段：{ctx[:300]}\n\n"
                "相关性（1/0）："
            )
            result = await self._call_llm(prompt)
            if "1" in result:
                relevant_count += 1

        return round(relevant_count / min(len(contexts), 5), 4)

    async def evaluate_ground_truth(self, answer: str, ground_truth: str) -> float:
        """
        评测答案正确性：与标准答案的相似度

        方法：用 LLM 判断回答与标准答案的语义一致性。
        """
        if not ground_truth:
            return 0.0

        prompt = (
            "请评估以下 AI 回答与标准答案的语义一致性。\n"
            "评分标准：\n"
            "- 1.0: AI 回答与标准答案含义完全一致\n"
            "- 0.5: AI 回答部分正确，但有遗漏或偏差\n"
            "- 0.0: AI 回答与标准答案完全不同或矛盾\n\n"
            f"标准答案：{ground_truth[:300]}\n\n"
            f"AI 回答：{answer[:300]}\n\n"
            "一致性分数（0-1）："
        )
        result = await self._call_llm(prompt)
        return self._extract_score(result)

    async def evaluate_single(self, case: EvalCase) -> EvalResult:
        """评测单个用例"""
        faithfulness = await self.evaluate_faithfulness(case.question, case.answer, case.contexts)
        answer_relevancy = await self.evaluate_answer_relevancy(case.question, case.answer)
        context_precision = await self.evaluate_context_precision(case.question, case.contexts)

        gt_similarity = 0.0
        if case.ground_truth:
            gt_similarity = await self.evaluate_ground_truth(case.answer, case.ground_truth)

        return EvalResult(
            question=case.question,
            faithfulness=faithfulness,
            answer_relevancy=answer_relevancy,
            context_precision=context_precision,
            ground_truth_similarity=gt_similarity,
        )

    async def evaluate_batch(self, dataset: list[EvalCase]) -> EvalReport:
        """
        批量评测

        参数：
            dataset: 评测用例列表

        返回：
            评测报告
        """
        results = []
        for i, case in enumerate(dataset):
            logger.info(f"评测进度: {i + 1}/{len(dataset)} - {case.question[:30]}...")
            result = await self.evaluate_single(case)
            results.append(result)

        # 计算平均指标
        n = len(results) or 1
        report = EvalReport(
            total_cases=len(results),
            avg_faithfulness=round(sum(r.faithfulness for r in results) / n, 4),
            avg_answer_relevancy=round(sum(r.answer_relevancy for r in results) / n, 4),
            avg_context_precision=round(sum(r.context_precision for r in results) / n, 4),
            avg_ground_truth_similarity=round(
                sum(r.ground_truth_similarity for r in results) / n, 4
            ) if any(r.ground_truth_similarity > 0 for r in results) else 0.0,
            results=results,
        )

        logger.info(
            f"评测完成: {report.total_cases} 条用例, "
            f"faithfulness={report.avg_faithfulness:.2%}, "
            f"relevancy={report.avg_answer_relevancy:.2%}, "
            f"precision={report.avg_context_precision:.2%}"
        )

        return report

    def generate_report(self, report: EvalReport) -> str:
        """生成格式化的评测报告"""
        lines = [
            "=" * 60,
            "RAG 评测报告",
            f"时间: {report.timestamp}",
            f"用例数: {report.total_cases}",
            "=" * 60,
            "",
            "整体指标:",
            f"  忠实度 (Faithfulness):      {report.avg_faithfulness:.2%}",
            f"  回答相关性 (Relevancy):      {report.avg_answer_relevancy:.2%}",
            f"  上下文精确率 (Precision):    {report.avg_context_precision:.2%}",
        ]

        if report.avg_ground_truth_similarity > 0:
            lines.append(f"  答案正确性 (Correctness):    {report.avg_ground_truth_similarity:.2%}")

        lines.extend(["", "-" * 60, "详细结果:"])

        for i, r in enumerate(report.results, 1):
            lines.extend([
                f"\n[{i}] {r.question[:50]}...",
                f"    faithfulness={r.faithfulness:.2f}, "
                f"relevancy={r.answer_relevancy:.2f}, "
                f"precision={r.context_precision:.2f}",
            ])

        lines.append("=" * 60)
        return "\n".join(lines)


def load_eval_dataset(path: str) -> list[EvalCase]:
    """
    从 JSON 文件加载评测数据集

    文件格式：
    [
        {
            "question": "...",
            "answer": "...",
            "contexts": ["...", "..."],
            "ground_truth": "..."  // 可选
        },
        ...
]
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    return [
        EvalCase(
            question=item["question"],
            answer=item["answer"],
            contexts=item.get("contexts", []),
            ground_truth=item.get("ground_truth", ""),
        )
        for item in data
    ]


def save_eval_dataset(dataset: list[EvalCase], path: str) -> None:
    """保存评测数据集到 JSON 文件"""
    data = [
        {
            "question": case.question,
            "answer": case.answer,
            "contexts": case.contexts,
            "ground_truth": case.ground_truth,
        }
        for case in dataset
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
