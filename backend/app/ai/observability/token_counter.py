"""
Token 统计和费用估算（ai/observability/token_counter.py）

说明：提供 Token 计数和费用估算功能，支持多种模型的定价计算。
     使用 tiktoken 进行精确的 Token 计数（OpenAI 兼容模型），
     对于不支持的模型使用近似估算。

核心功能：
    - count_tokens(): 精确计数文本的 Token 数量
    - calculate_cost(): 根据模型定价计算费用
    - TokenUsageRecord: Token 使用记录数据类
    - aggregate_daily_usage(): 按天聚合使用统计
    - aggregate_weekly_usage(): 按周聚合使用统计

定价说明：
    价格单位为人民币（元），按每 1K Token 计费。
    本地 Ollama 模型（qwen3:4b）免费。

用法：
    from app.ai.observability.token_counter import count_tokens, calculate_cost

    tokens = count_tokens("你好，请帮我查询考勤记录", model="qwen-plus")
    cost = calculate_cost(input_tokens=100, output_tokens=200, model="qwen-plus")
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

# ============================================================
# 尝试导入 tiktoken（Token 计数库）
# ============================================================
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    logger.warning(
        "tiktoken 未安装，Token 计数将使用近似估算。"
        "安装方式: pip install tiktoken"
    )


# ============================================================
# 模型定价表（每 1K Token，单位：人民币元）
#
# 说明：基于各提供商的官方定价。
#      本地 Ollama 模型免费（无 API 调用费用）。
#      嵌入模型仅有输入费用，无输出费用。
# ============================================================
MODEL_PRICING: dict[str, dict[str, float]] = {
    "qwen-plus": {"input": 0.004, "output": 0.012},
    "qwen-turbo": {"input": 0.001, "output": 0.002},
    "qwen3:4b": {"input": 0.0, "output": 0.0},  # 本地 Ollama，免费
    "text-embedding-v3": {"input": 0.0007, "output": 0.0},
}


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """
    计算文本的 Token 数量

    说明：使用 tiktoken 进行精确的 Token 计数。
         对于不支持的模型编码，回退到 cl100k_base 编码器。
         如果 tiktoken 不可用，使用字符数 / 2 的近似估算（中文场景）。

    参数：
        text: 要计数的文本内容
        model: 模型名称（用于选择对应的编码器）

    返回：
        int: Token 数量

    示例：
        >>> count_tokens("你好世界")
        4
        >>> count_tokens("Hello, world!", model="qwen-plus")
        4
    """
    if not text:
        return 0

    if not TIKTOKEN_AVAILABLE:
        # 近似估算：中文约 1 字 = 1-2 token，英文约 4 字符 = 1 token
        # 使用字符数 / 2 作为粗略估算
        return max(1, len(text) // 2)

    try:
        # 尝试获取模型对应的编码器
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        # 模型不在 tiktoken 支持列表中，使用 cl100k_base（GPT-4 编码器）
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            # 最终回退：字符数近似
            return max(1, len(text) // 2)

    try:
        tokens = encoding.encode(text)
        return len(tokens)
    except Exception as e:
        logger.warning(f"Token 计数失败，使用近似估算: {e}")
        return max(1, len(text) // 2)


def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    model: str = "qwen-plus",
) -> float:
    """
    计算 LLM 调用费用

    说明：根据模型定价表计算输入和输出 Token 的总费用。
         费用精确到小数点后 4 位。
         未知模型返回 0.0（不计费）。

    参数：
        input_tokens: 输入 Token 数量
        output_tokens: 输出 Token 数量
        model: 模型名称

    返回：
        float: 费用（人民币元），精确到 4 位小数

    示例：
        >>> calculate_cost(1000, 500, model="qwen-plus")
        0.0100  # 1000/1000 * 0.004 + 500/1000 * 0.012 = 0.004 + 0.006
    """
    pricing = MODEL_PRICING.get(model)

    if pricing is None:
        logger.debug(f"未知模型 '{model}' 的定价信息，费用计为 0")
        return 0.0

    input_cost = (input_tokens / 1000) * pricing["input"]
    output_cost = (output_tokens / 1000) * pricing["output"]
    total_cost = round(input_cost + output_cost, 4)

    return total_cost


@dataclass
class TokenUsageRecord:
    """
    Token 使用记录

    说明：记录单次 LLM 调用的 Token 使用情况和费用。
         用于聚合统计和费用报表。

    字段：
        input_tokens: 输入 Token 数量
        output_tokens: 输出 Token 数量
        total_tokens: 总 Token 数量（input + output）
        model: 使用的模型名称
        cost: 本次调用费用（人民币元）
        timestamp: 记录时间戳
    """
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    model: str = "qwen-plus"
    cost: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """自动计算总 Token 数和费用"""
        if self.total_tokens == 0:
            self.total_tokens = self.input_tokens + self.output_tokens
        if self.cost == 0.0 and (self.input_tokens > 0 or self.output_tokens > 0):
            self.cost = calculate_cost(
                self.input_tokens, self.output_tokens, self.model
            )


def aggregate_daily_usage(records: list[TokenUsageRecord]) -> dict[str, dict]:
    """
    按天聚合 Token 使用统计

    说明：将 Token 使用记录按日期分组，计算每天的总量和费用。

    参数：
        records: Token 使用记录列表

    返回：
        dict: 以日期字符串为键的聚合结果
            {
                "2024-01-15": {
                    "date": "2024-01-15",
                    "total_input_tokens": 5000,
                    "total_output_tokens": 3000,
                    "total_cost": 0.0560,
                    "request_count": 10,
                },
                ...
            }

    示例：
        >>> records = [TokenUsageRecord(input_tokens=100, output_tokens=50, model="qwen-plus")]
        >>> result = aggregate_daily_usage(records)
    """
    daily: dict[str, dict] = defaultdict(
        lambda: {
            "date": "",
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cost": 0.0,
            "request_count": 0,
        }
    )

    for record in records:
        day_key = record.timestamp.strftime("%Y-%m-%d")
        entry = daily[day_key]
        entry["date"] = day_key
        entry["total_input_tokens"] += record.input_tokens
        entry["total_output_tokens"] += record.output_tokens
        entry["total_cost"] = round(entry["total_cost"] + record.cost, 4)
        entry["request_count"] += 1

    return dict(daily)


def aggregate_weekly_usage(records: list[TokenUsageRecord]) -> dict[str, dict]:
    """
    按周聚合 Token 使用统计

    说明：将 Token 使用记录按 ISO 周分组，计算每周的总量和费用。
         周的格式为 "YYYY-WXX"（如 "2024-W03"）。

    参数：
        records: Token 使用记录列表

    返回：
        dict: 以周标识为键的聚合结果
            {
                "2024-W03": {
                    "week": "2024-W03",
                    "total_input_tokens": 35000,
                    "total_output_tokens": 21000,
                    "total_cost": 0.3920,
                    "request_count": 70,
                },
                ...
            }

    示例：
        >>> records = [TokenUsageRecord(input_tokens=100, output_tokens=50, model="qwen-plus")]
        >>> result = aggregate_weekly_usage(records)
    """
    weekly: dict[str, dict] = defaultdict(
        lambda: {
            "week": "",
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cost": 0.0,
            "request_count": 0,
        }
    )

    for record in records:
        # ISO 周格式: YYYY-WXX
        iso_cal = record.timestamp.isocalendar()
        week_key = f"{iso_cal[0]}-W{iso_cal[1]:02d}"
        entry = weekly[week_key]
        entry["week"] = week_key
        entry["total_input_tokens"] += record.input_tokens
        entry["total_output_tokens"] += record.output_tokens
        entry["total_cost"] = round(entry["total_cost"] + record.cost, 4)
        entry["request_count"] += 1

    return dict(weekly)
