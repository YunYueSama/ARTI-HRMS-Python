"""
可观测性模块（ai/observability）

说明：提供 LLM 调用链路追踪、Token 统计、费用估算和异常检测功能。
     集成 Langfuse 实现全链路可观测性，支持在 Langfuse 未配置时优雅降级。

子模块：
    - tracer: Langfuse SDK 集成和 Trace 管理
    - token_counter: Token 统计和费用估算
    - alerts: 异常检测（慢响应、逻辑死锁）

用法：
    from app.ai.observability.tracer import langfuse_tracer
    from app.ai.observability.token_counter import count_tokens, calculate_cost
    from app.ai.observability.alerts import detect_anomalies
"""
