"""
NLP 服务工具（ai/nlp_tools.py）

说明：提供 NLP 文本分析能力，包括命名实体识别（NER）、情感分析和关键词提取。
     使用 LLM + 规则混合策略实现，优先规则匹配，回退到 LLM 分析。

能力列表：
    1. 命名实体识别（NER）：识别 HR 领域实体（人名、部门、日期等）
    2. 情感分析：判断文本情感倾向（正面/中性/负面）
    3. 关键词提取：基于 TF-IDF 简化版提取文本关键词

设计说明：
    - NER 使用 LLM 结构化输出 + HR 领域词典补充
    - 情感分析使用关键词规则 + LLM 辅助
    - 关键词提取使用词频统计（不依赖 LLM，零延迟）
"""

import logging
import re
from collections import Counter
from typing import Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.nlp import EntityItem, KeywordItem, SentimentResult

logger = logging.getLogger(__name__)

# ============================================================
# HR 领域词典（用于规则匹配补充）
# ============================================================

# HR 常见部门名称
_DEPARTMENT_KEYWORDS = frozenset([
    "人力资源部", "技术部", "财务部", "市场部", "销售部",
    "行政部", "研发部", "产品部", "运营部", "法务部",
    "客服部", "采购部", "质量部", "生产部", "信息部",
    "人力资源", "技术", "财务", "市场", "销售",
    "研发", "产品", "运营", "法务", "客服",
])

# HR 常见职位名称
_POSITION_KEYWORDS = frozenset([
    "总经理", "总监", "经理", "主管", "专员", "助理",
    "工程师", "设计师", "分析师", "顾问", "实习生",
    "副总", "部长", "科长", "组长", "主任",
    "前端", "后端", "全栈", "测试", "运维",
])

# HR 常见请假类型
_LEAVE_KEYWORDS = frozenset([
    "年假", "病假", "事假", "婚假", "产假", "陪产假", "丧假",
    "调休", "加班", "出差", "外勤",
])

# 考勤相关关键词
_ATTENDANCE_KEYWORDS = frozenset([
    "签到", "签退", "打卡", "迟到", "早退", "缺勤", "加班",
    "出勤", "旷工", "请假",
])

# 积极情感词
_POSITIVE_WORDS = frozenset([
    "好", "优秀", "出色", "满意", "开心", "高兴", "感谢", "谢谢",
    "不错", "很好", "太棒", "完美", "优秀", "赞", "支持",
    "喜欢", "快乐", "幸福", "顺利", "成功", "升职", "加薪",
])

# 消极情感词
_NEGATIVE_WORDS = frozenset([
    "差", "糟糕", "不满", "失望", "难过", "生气", "愤怒", "投诉",
    "不好", "太差", "垃圾", "差劲", "恶心", "讨厌", "反对",
    "累", "压力", "焦虑", "委屈", "崩溃", "烦", "郁闷",
])

# 停用词（中文常见）
_STOP_WORDS = frozenset([
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人",
    "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去",
    "你", "会", "着", "没有", "看", "好", "自己", "这", "他", "她",
    "它", "们", "那", "些", "什么", "怎么", "这个", "那个", "可以",
    "因为", "所以", "但是", "如果", "虽然", "然后", "已经", "把",
    "被", "让", "给", "从", "向", "对", "为", "以", "与", "及",
])


class NLPService:
    """
    NLP 文本分析服务

    说明：提供 HR 领域的文本分析能力，包括实体识别、情感分析和关键词提取。
         支持规则匹配（零延迟）和 LLM 辅助（更准确）两种模式。

    用法：
        service = NLPService()
        result = await service.analyze_text("张三申请了3天年假", tasks=["ner", "sentiment"])
    """

    def __init__(self, model: Optional[BaseChatModel] = None):
        """
        初始化 NLP 服务

        参数：
            model: LangChain 聊天模型实例（可选，用于 LLM 辅助分析）
        """
        self._model = model

    async def extract_entities(self, text: str) -> list[EntityItem]:
        """
        命名实体识别（NER）

        说明：识别 HR 领域的命名实体，包括人名、部门名、日期、数字等。
             采用规则匹配 + LLM 辅助的混合策略。

        参数：
            text: 待分析文本

        返回：
            EntityItem 列表
        """
        entities: list[EntityItem] = []

        # 规则匹配：日期
        entities.extend(self._extract_dates(text))

        # 规则匹配：数字（天数、金额等）
        entities.extend(self._extract_numbers(text))

        # 规则匹配：HR 领域关键词
        entities.extend(self._extract_hr_keywords(text))

        # LLM 辅助识别（如果模型可用且规则匹配结果不足）
        if self._model and len(entities) < 2:
            try:
                llm_entities = await self._extract_entities_by_llm(text)
                entities.extend(llm_entities)
            except Exception as e:
                logger.warning(f"LLM 实体识别失败: {e}")

        # 去重
        return self._deduplicate_entities(entities)

    async def analyze_sentiment(self, text: str) -> SentimentResult:
        """
        情感分析

        说明：判断文本的情感倾向，返回 positive/neutral/negative 标签和置信度。
             优先使用关键词规则匹配，无法确定时回退到 LLM 分析。

        参数：
            text: 待分析文本

        返回：
            SentimentResult 对象
        """
        # 规则匹配
        result = self._analyze_sentiment_by_keywords(text)
        if result is not None:
            return result

        # LLM 辅助分析
        if self._model:
            try:
                return await self._analyze_sentiment_by_llm(text)
            except Exception as e:
                logger.warning(f"LLM 情感分析失败: {e}")

        # 默认返回中性
        return SentimentResult(label="neutral", score=0.5)

    def extract_keywords(self, text: str, top_k: int = 10) -> tuple[list[KeywordItem], int]:
        """
        关键词提取

        说明：基于简化版 TF-IDF 算法提取文本关键词。
             不依赖 LLM，零延迟，适合实时分析。

        参数：
            text: 待分析文本
            top_k: 返回前 N 个关键词

        返回：
            (关键词列表, 总词数)
        """
        # 简单中文分词：按标点和空格分词
        words = self._tokenize(text)
        total_words = len(words)

        if total_words == 0:
            return [], 0

        # 过滤停用词
        filtered = [w for w in words if w not in _STOP_WORDS and len(w) > 1]

        if not filtered:
            return [], total_words

        # 统计词频（简化版 TF）
        word_counts = Counter(filtered)
        max_freq = max(word_counts.values())

        # 计算权重并排序
        keywords = [
            KeywordItem(word=word, weight=round(count / max_freq, 4))
            for word, count in word_counts.most_common(top_k)
        ]

        return keywords, total_words

    async def analyze_text(
        self,
        text: str,
        tasks: list[str],
    ) -> dict:
        """
        综合文本分析

        说明：根据指定的任务列表执行多种 NLP 分析。

        参数：
            text: 待分析文本
            tasks: 分析任务列表，可选值：ner、sentiment、keywords

        返回：
            分析结果字典
        """
        result: dict = {"original_text": text}

        if "ner" in tasks:
            result["entities"] = await self.extract_entities(text)

        if "sentiment" in tasks:
            result["sentiment"] = await self.analyze_sentiment(text)

        if "keywords" in tasks:
            keywords, total_words = self.extract_keywords(text)
            result["keywords"] = keywords
            result["total_words"] = total_words

        return result

    # ============================================================
    # 规则匹配辅助方法
    # ============================================================

    def _extract_dates(self, text: str) -> list[EntityItem]:
        """提取日期实体"""
        entities = []
        # 匹配 yyyy-MM-dd 或 yyyy/MM/dd 格式
        for match in re.finditer(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}", text):
            entities.append(EntityItem(
                text=match.group(),
                label="DATE",
                start=match.start(),
                end=match.end(),
            ))
        # 匹配 X天/X个工作日
        for match in re.finditer(r"\d+\s*(天|个工作日|小时)", text):
            entities.append(EntityItem(
                text=match.group(),
                label="DURATION",
                start=match.start(),
                end=match.end(),
            ))
        return entities

    def _extract_numbers(self, text: str) -> list[EntityItem]:
        """提取数字实体（金额等）"""
        entities = []
        # 匹配金额（如 ¥5000、5000元）
        for match in re.finditer(r"[¥￥]?\d+(?:\.\d+)?元?", text):
            matched = match.group()
            if re.search(r"[¥￥元]", matched) or len(matched) >= 4:
                entities.append(EntityItem(
                    text=matched,
                    label="MONEY",
                    start=match.start(),
                    end=match.end(),
                ))
        return entities

    def _extract_hr_keywords(self, text: str) -> list[EntityItem]:
        """提取 HR 领域关键词实体"""
        entities = []

        for dept in _DEPARTMENT_KEYWORDS:
            start = 0
            while True:
                idx = text.find(dept, start)
                if idx == -1:
                    break
                entities.append(EntityItem(
                    text=dept,
                    label="DEPARTMENT",
                    start=idx,
                    end=idx + len(dept),
                ))
                start = idx + 1

        for pos in _POSITION_KEYWORDS:
            start = 0
            while True:
                idx = text.find(pos, start)
                if idx == -1:
                    break
                entities.append(EntityItem(
                    text=pos,
                    label="POSITION",
                    start=idx,
                    end=idx + len(pos),
                ))
                start = idx + 1

        for leave in _LEAVE_KEYWORDS:
            start = 0
            while True:
                idx = text.find(leave, start)
                if idx == -1:
                    break
                entities.append(EntityItem(
                    text=leave,
                    label="LEAVE_TYPE",
                    start=idx,
                    end=idx + len(leave),
                ))
                start = idx + 1

        for att in _ATTENDANCE_KEYWORDS:
            start = 0
            while True:
                idx = text.find(att, start)
                if idx == -1:
                    break
                entities.append(EntityItem(
                    text=att,
                    label="ATTENDANCE",
                    start=idx,
                    end=idx + len(att),
                ))
                start = idx + 1

        return entities

    def _analyze_sentiment_by_keywords(self, text: str) -> Optional[SentimentResult]:
        """基于关键词的情感分析"""
        positive_count = sum(1 for w in _POSITIVE_WORDS if w in text)
        negative_count = sum(1 for w in _NEGATIVE_WORDS if w in text)

        if positive_count == 0 and negative_count == 0:
            return None  # 无法确定

        total = positive_count + negative_count
        if positive_count > negative_count:
            return SentimentResult(
                label="positive",
                score=round(positive_count / total, 2),
            )
        elif negative_count > positive_count:
            return SentimentResult(
                label="negative",
                score=round(negative_count / total, 2),
            )
        else:
            return SentimentResult(label="neutral", score=0.5)

    def _tokenize(self, text: str) -> list[str]:
        """简单中文分词（按标点和空格切分）"""
        # 去除标点和特殊字符，保留中文、英文、数字
        cleaned = re.sub(r"[^一-鿿\w]", " ", text)
        # 按空格分词
        tokens = cleaned.split()
        # 对纯中文 token 进一步按 2-gram 切分（简化版分词）
        result = []
        for token in tokens:
            if re.match(r"^[一-鿿]+$", token) and len(token) > 2:
                # 中文长词按 2-gram 切分
                for i in range(len(token) - 1):
                    result.append(token[i:i + 2])
            else:
                result.append(token)
        return result

    def _deduplicate_entities(self, entities: list[EntityItem]) -> list[EntityItem]:
        """去重实体（相同文本+标签只保留一个）"""
        seen = set()
        result = []
        for e in entities:
            key = (e.text, e.label)
            if key not in seen:
                seen.add(key)
                result.append(e)
        return result

    # ============================================================
    # LLM 辅助分析方法
    # ============================================================

    async def _extract_entities_by_llm(self, text: str) -> list[EntityItem]:
        """使用 LLM 进行命名实体识别"""
        prompt = (
            "请从以下 HR 相关文本中识别命名实体，返回 JSON 数组格式。\n"
            "每个实体包含 text（实体文本）、label（类型标签）。\n"
            "类型标签可选：PERSON、DEPARTMENT、POSITION、DATE、DURATION、MONEY、LEAVE_TYPE、OTHER。\n\n"
            f"文本：{text}\n\n"
            "只返回 JSON 数组，不要返回其他内容。"
        )

        response = await self._model.ainvoke([
            SystemMessage(content="你是 HR 领域的命名实体识别工具，只返回 JSON 格式结果。"),
            HumanMessage(content=prompt),
        ])

        content = response.content.strip()
        # 解析 JSON
        import json
        try:
            items = json.loads(content)
            if isinstance(items, list):
                return [
                    EntityItem(
                        text=item.get("text", ""),
                        label=item.get("label", "OTHER"),
                        start=0,
                        end=0,
                    )
                    for item in items
                    if isinstance(item, dict) and "text" in item
                ]
        except json.JSONDecodeError:
            logger.warning(f"LLM 实体识别结果解析失败: {content[:100]}")

        return []

    async def _analyze_sentiment_by_llm(self, text: str) -> SentimentResult:
        """使用 LLM 进行情感分析"""
        prompt = (
            "请分析以下 HR 相关文本的情感倾向。\n"
            "返回格式：label（positive/neutral/negative）和 score（0-1 置信度）。\n\n"
            f"文本：{text}\n\n"
            "只返回 JSON 对象，如：{\"label\": \"positive\", \"score\": 0.85}"
        )

        response = await self._model.ainvoke([
            SystemMessage(content="你是情感分析工具，只返回 JSON 格式结果。"),
            HumanMessage(content=prompt),
        ])

        content = response.content.strip()
        import json
        try:
            data = json.loads(content)
            return SentimentResult(
                label=data.get("label", "neutral"),
                score=float(data.get("score", 0.5)),
            )
        except (json.JSONDecodeError, ValueError):
            logger.warning(f"LLM 情感分析结果解析失败: {content[:100]}")

        return SentimentResult(label="neutral", score=0.5)
