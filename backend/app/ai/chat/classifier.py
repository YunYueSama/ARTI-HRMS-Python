"""
消息分类器（ai/chat/classifier.py）

说明：使用关键词匹配 + LLM 辅助的方式将用户消息分类到预定义类别。
     分类结果决定后续的回答策略（情绪安抚/流程解释/数据查询/日常聊天）。

分类策略：
    1. 优先使用关键词规则快速分类（零延迟）
    2. 关键词无法确定时，调用 LLM 进行分类（有延迟但更准确）
    3. LLM 不可用时，回退到 daily_chat 默认类别

Java 对应关系：
    AiChatService.detectQuestionCategory() → classify_message()

消息类别：
    - emotional_support: 情绪安抚/陪伴
    - process_explanation: 流程解释
    - system_data_query: 系统数据查询
    - daily_chat: 日常聊天
    - unknown: 无法确认/超出系统范围
"""

import logging
from typing import Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.ai.chat.prompts import get_classification_prompt
from app.schemas.agent import MessageCategory

logger = logging.getLogger(__name__)

# 关键词分类规则（优先级从高到低）
_EMOTIONAL_KEYWORDS = frozenset([
    "累", "难过", "烦", "焦虑", "委屈", "崩溃", "不开心", "压力",
    "想哭", "安慰", "陪我", "郁闷", "心烦", "受不了", "好难",
])

_PROCESS_KEYWORDS = frozenset([
    "如何", "怎么", "流程", "步骤", "入口", "审批", "申请", "操作",
    "怎样", "方法", "教程", "指南",
])

_DATA_KEYWORDS = frozenset([
    "员工", "人员", "部门", "岗位", "职位", "考勤", "打卡", "签到",
    "请假", "休假", "工资", "薪资", "薪酬", "报表", "统计",
    "多少人", "出勤率", "我的", "当前", "查询", "记录",
    "角色", "权限", "用户", "账号", "天气",
    # 关于 AI 自身的元问题（亚托莉用的什么模型/底层 LLM 是什么等）
    "模型", "model", "大模型", "llm", "provider", "底层架构",
    "技术架构", "什么版本", "用的什么", "用什么", "哪个模型",
    "qwen", "通义", "deepseek", "ollama", "openai", "dashscope", "百炼",
])

_UNKNOWN_KEYWORDS = frozenset([
    "未来", "一定会", "能不能保证", "预测", "估计", "会不会",
])


async def classify_message(
    message: str,
    model: Optional[BaseChatModel] = None,
) -> MessageCategory:
    """
    对用户消息进行分类

    说明：采用两阶段分类策略：
         1. 关键词快速匹配（毫秒级，覆盖大部分常见场景）
         2. LLM 辅助分类（当关键词无法确定时，调用模型判断）

    参数：
        message: 用户消息文本
        model: LangChain 聊天模型实例（可选，用于 LLM 辅助分类）

    返回：
        MessageCategory 枚举值
    """
    # 预处理：去空格、转小写
    normalized = message.strip().lower().replace(" ", "")

    # 阶段一：关键词快速分类
    keyword_result = _classify_by_keywords(normalized)
    if keyword_result is not None:
        logger.debug(f"关键词分类结果: {keyword_result.value} (消息: {message[:30]}...)")
        return keyword_result

    # 阶段二：LLM 辅助分类（如果模型可用）
    if model is not None:
        try:
            llm_result = await _classify_by_llm(message, model)
            if llm_result is not None:
                logger.debug(f"LLM 分类结果: {llm_result.value} (消息: {message[:30]}...)")
                return llm_result
        except Exception as e:
            logger.warning(f"LLM 分类失败，回退到默认类别: {e}")

    # 默认：日常聊天
    return MessageCategory.DAILY_CHAT


def _classify_by_keywords(normalized: str) -> Optional[MessageCategory]:
    """基于关键词规则进行快速分类

    优先级说明：
        1. 情绪类（最优先，避免冷冰冰回应情绪问题）
        2. 数据查询类（次之，"天气怎么样"这种带"怎么"的也要优先走数据，
                       否则会被误判为流程解释，触发不到天气查询）
        3. 流程解释类（如何/怎么/步骤等）
        4. 无法确认类
    """
    # 情绪类优先级最高
    if _contains_any(normalized, _EMOTIONAL_KEYWORDS):
        return MessageCategory.EMOTIONAL_SUPPORT

    # 数据查询类（提前到流程类之前，避免"天气怎么样"被误分到流程类）
    if _contains_any(normalized, _DATA_KEYWORDS):
        return MessageCategory.SYSTEM_DATA_QUERY

    # 流程类
    if _contains_any(normalized, _PROCESS_KEYWORDS):
        return MessageCategory.PROCESS_EXPLANATION

    # 无法确认类
    if _contains_any(normalized, _UNKNOWN_KEYWORDS):
        return MessageCategory.UNKNOWN

    # 关键词无法确定
    return None


async def _classify_by_llm(message: str, model: BaseChatModel) -> Optional[MessageCategory]:
    """使用 LLM 进行消息分类"""
    prompt = get_classification_prompt().format(message=message)

    response = await model.ainvoke([
        SystemMessage(content="你是一个消息分类器，只返回类别名称，不要返回其他内容。"),
        HumanMessage(content=prompt),
    ])

    # 解析 LLM 返回的类别名称
    result_text = response.content.strip().lower().replace(" ", "").replace("-", "_")

    # 映射到枚举
    category_map = {
        "emotional_support": MessageCategory.EMOTIONAL_SUPPORT,
        "process_explanation": MessageCategory.PROCESS_EXPLANATION,
        "system_data_query": MessageCategory.SYSTEM_DATA_QUERY,
        "daily_chat": MessageCategory.DAILY_CHAT,
        "unknown": MessageCategory.UNKNOWN,
    }

    return category_map.get(result_text)


def _contains_any(text: str, keywords: frozenset[str]) -> bool:
    """检查文本是否包含关键词集合中的任意一个"""
    return any(kw in text for kw in keywords)
