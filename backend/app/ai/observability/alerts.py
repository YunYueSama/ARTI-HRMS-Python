"""
异常检测模块（ai/observability/alerts.py）

说明：提供 LLM 调用链路的异常检测功能，包括：
     - 慢响应检测：识别超过阈值的 LLM 调用
     - 逻辑死锁检测：识别 Agent 状态机中的循环
     - 综合异常检测：分析 trace 数据中的各类异常

用法：
    from app.ai.observability.alerts import is_slow_response, is_logic_deadlock, detect_anomalies

    if is_slow_response(latency_seconds=15.0):
        logger.warning("检测到慢响应")

    is_deadlock, node = is_logic_deadlock(["plan", "execute", "plan", "execute", "plan", "execute", "plan"])
    if is_deadlock:
        logger.warning(f"检测到死锁节点: {node}")
"""

import logging
from collections import Counter

from app.core.config import settings

logger = logging.getLogger(__name__)


def is_slow_response(
    latency_seconds: float,
    threshold: float | None = None,
) -> bool:
    """
    检测是否为慢响应

    说明：将实际响应耗时与阈值进行比较。
         阈值优先使用传入参数，其次使用配置文件中的 SLOW_RESPONSE_THRESHOLD，
         默认为 10.0 秒。

    参数：
        latency_seconds: 实际响应耗时（秒）
        threshold: 慢响应阈值（秒），默认从配置读取或使用 10.0

    返回：
        bool: 是否为慢响应（耗时超过阈值）

    示例：
        >>> is_slow_response(5.0)
        False
        >>> is_slow_response(15.0)
        True
        >>> is_slow_response(8.0, threshold=5.0)
        True
    """
    if threshold is None:
        threshold = getattr(settings, "SLOW_RESPONSE_THRESHOLD", 10.0)

    return latency_seconds > threshold


def is_logic_deadlock(
    state_history: list[str],
    max_visits: int = 3,
) -> tuple[bool, str | None]:
    """
    检测 Agent 状态机逻辑死锁

    说明：分析 Agent 执行过程中的状态节点访问历史，
         如果同一个节点被访问超过 max_visits 次，
         判定为逻辑死锁（Agent 陷入循环无法推进）。

    参数：
        state_history: 状态节点访问历史列表
                      例如: ["plan", "execute", "plan", "execute", "plan", "execute", "plan"]
        max_visits: 单个节点最大允许访问次数（超过此值判定为死锁），默认 3

    返回：
        tuple[bool, str | None]:
            - (True, "node_name"): 检测到死锁，返回死锁节点名称
            - (False, None): 未检测到死锁

    示例：
        >>> is_logic_deadlock(["plan", "execute", "plan", "execute"])
        (False, None)
        >>> is_logic_deadlock(["plan", "execute", "plan", "execute", "plan", "execute", "plan"])
        (True, "plan")  # "plan" 出现 4 次，超过阈值 3
    """
    if not state_history:
        return (False, None)

    state_counts = Counter(state_history)

    for state, count in state_counts.items():
        if count > max_visits:
            logger.warning(
                f"检测到逻辑死锁: 节点 '{state}' 被访问 {count} 次 "
                f"(最大允许: {max_visits}), 状态历史长度: {len(state_history)}"
            )
            return (True, state)

    return (False, None)


def detect_anomalies(trace_data: dict) -> list[str]:
    """
    综合异常检测

    说明：分析 trace 数据，检测各类异常情况并返回异常标签列表。
         检测项包括：
         - 慢响应（slow_response）
         - 逻辑死锁（logic_deadlock）
         - 高 Token 消耗（high_token_usage）
         - 高费用（high_cost）
         - 错误状态（error_status）
         - 空响应（empty_response）

    参数：
        trace_data: trace 数据字典，可能包含以下字段：
            - latency_seconds (float): 响应耗时
            - state_history (list[str]): 状态历史
            - total_tokens (int): 总 Token 数
            - cost (float): 费用
            - status (str): 状态（success/error）
            - output (str): 输出内容

    返回：
        list[str]: 检测到的异常标签列表

    示例：
        >>> detect_anomalies({"latency_seconds": 15.0, "total_tokens": 10000})
        ["slow_response", "high_token_usage"]
    """
    anomalies: list[str] = []

    # 1. 慢响应检测
    latency = trace_data.get("latency_seconds", 0.0)
    if latency and is_slow_response(latency):
        anomalies.append("slow_response")

    # 2. 逻辑死锁检测
    state_history = trace_data.get("state_history")
    if state_history and isinstance(state_history, list):
        deadlock, _ = is_logic_deadlock(state_history)
        if deadlock:
            anomalies.append("logic_deadlock")

    # 3. 高 Token 消耗检测（单次调用超过 4000 Token）
    total_tokens = trace_data.get("total_tokens", 0)
    if total_tokens > 4000:
        anomalies.append("high_token_usage")

    # 4. 高费用检测（单次调用超过 0.1 元）
    cost = trace_data.get("cost", 0.0)
    if cost > 0.1:
        anomalies.append("high_cost")

    # 5. 错误状态检测
    status = trace_data.get("status", "")
    if status == "error":
        anomalies.append("error_status")

    # 6. 空响应检测
    output = trace_data.get("output")
    if output is not None and isinstance(output, str) and len(output.strip()) == 0:
        anomalies.append("empty_response")

    if anomalies:
        logger.info(f"异常检测结果: 发现 {len(anomalies)} 个异常 - {anomalies}")

    return anomalies
