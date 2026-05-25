"""
Agent 模块（ai/agent/）

说明：基于 LangGraph 的 Agent 引擎，实现自然语言指令到结构化操作的转换。

模块结构：
    - state.py: Agent 状态定义（TypedDict）
    - graph.py: LangGraph StateGraph 构建
    - nodes.py: 图节点实现（意图识别、计划生成、执行等）
    - tools.py: LangChain Tools 声明
    - structured_output.py: LLM 结构化输出解析和重试
"""

from app.ai.agent.graph import build_agent_graph, get_agent_graph
from app.ai.agent.state import AgentState

__all__ = [
    "AgentState",
    "build_agent_graph",
    "get_agent_graph",
]
