"""
Agent 状态图构建（ai/agent/graph.py）

说明：使用 LangGraph 构建 Agent 的状态机（StateGraph）。
     状态机定义了 Agent 处理用户指令的完整流程：
     意图识别 → 计划生成 → 人工审批 → 执行 → 结果报告

核心概念：
    - StateGraph：有向图，节点是处理函数，边是状态转移条件
    - 节点（Node）：接收状态、处理逻辑、返回新状态的函数
    - 边（Edge）：连接节点的转移路径，可以是无条件的或条件的
    - 条件边（Conditional Edge）：根据状态中的某个字段决定下一个节点
    - END：特殊节点，表示图的终止

状态机流程图：
    ┌─────────────────┐
    │  START (入口)    │
    └────────┬────────┘
             │
    ┌────────▼────────┐
    │ intent_recognition│  ← 意图识别（LLM + 规则回退）
    └────────┬────────┘
             │
        ┌────┴────┐
        │ unknown? │  ← 条件判断：意图是否为 unknown
        └────┬────┘
         yes │    no
    ┌────────▼──┐  ┌──▼────────────┐
    │error_report│  │plan_generation │  ← 生成执行计划
    └────────┬──┘  └──────┬────────┘
             │             │
             │    ┌────────▼────────┐
             │    │ human_approval   │  ← 标记为待审批（虚拟暂停点）
             │    └────────┬────────┘
             │             │
             │        ┌────┴────┐
             │        │approved? │  ← 条件判断：是否已审批
             │        └────┬────┘
             │      rejected│    approved
             │         ┌────▼──┐  ┌──▼──────┐
             │         │  END   │  │execution │  ← 执行计划
             │         └────────┘  └──┬──────┘
             │                        │
             │                   ┌────┴────┐
             │                   │ errors?  │  ← 条件判断：是否有错误
             │                   └────┬────┘
             │                 yes│      no│
             │         ┌──────────▼┐  ┌───▼───────────┐
             │         │error_report│  │result_reporting│
             │         └──────┬────┘  └───────┬───────┘
             │                │               │
             └────────────────┴───────────────┘
                              │
                         ┌────▼────┐
                         │   END    │
                         └─────────┘

Java 对应关系：
    AgentTaskService.planTask()          → intent_recognition + plan_generation + human_approval
    AgentTaskService.approveAndExecute() → execution + result_reporting
    整个 StateGraph                      → AgentTaskService 的方法调用链
"""

from langgraph.graph import END, StateGraph

# 节点函数按需导入，避免模块导入时立即解析大型或可能损坏的文件
from app.ai.agent.state import AgentState


def _route_after_intent(state: AgentState) -> str:
    """
    意图识别后的路由函数

    说明：根据识别到的意图决定下一步走向。
         - 如果意图为 unknown，直接进入错误报告节点
         - 否则进入计划生成节点

    参数：
        state: 当前 Agent 状态

    返回：
        下一个节点的名称字符串
    """
    intent = state.get("intent", "unknown")
    if intent == "unknown":
        return "error_reporting"
    return "plan_generation"


def _route_after_approval(state: AgentState) -> str:
    """
    审批后的路由函数

    说明：根据审批状态决定下一步走向。
         - 如果审批被拒绝（rejected），直接结束
         - 如果审批通过（approved），进入执行节点
         - 如果仍在等待（pending），也结束（等待外部触发）

    注意：在实际使用中，human_approval 节点只是标记状态为 pending，
         图在此处暂停。当用户通过 API 审批后，服务层会直接调用
         execution_node，而不是重新运行整个图。

    参数：
        state: 当前 Agent 状态

    返回：
        下一个节点的名称字符串，或 END 表示终止
    """
    approval_status = state.get("approval_status", "pending")
    if approval_status == "approved":
        return "execution"
    # pending 或 rejected 都终止图的运行
    return END


def _route_after_execution(state: AgentState) -> str:
    """
    执行后的路由函数

    说明：根据执行结果决定下一步走向。
         - 如果有错误记录，进入错误报告节点
         - 否则进入结果报告节点

    参数：
        state: 当前 Agent 状态

    返回：
        下一个节点的名称字符串
    """
    error_history = state.get("error_history", [])
    if error_history:
        return "error_reporting"
    return "result_reporting"


def build_agent_graph() -> StateGraph:
    """
    构建 Agent 状态图

    说明：创建并配置完整的 LangGraph StateGraph 实例。
         图定义了 Agent 处理用户指令的完整状态机。

    返回：
        编译后的 StateGraph 实例（可直接调用 .invoke() 执行）

    使用方式：
        graph = build_agent_graph()
        result = await graph.ainvoke({
            "user_id": 1,
            "command": "帮我请两天年假",
            "warnings": [],
            "error_history": [],
            "execution_results": [],
            "current_step": 0,
            "executable": False,
            "requires_approval": True,
        })
    """
    # ========================================
    # 第一步：创建 StateGraph 实例
    # 传入状态类型定义，LangGraph 会据此验证状态结构
    # ========================================
    graph = StateGraph(AgentState)

    # ========================================
    # 第二步：添加节点（延迟导入节点实现以避免在模块导入时触发解析错误）
    # 每个节点是一个异步函数，接收 AgentState 并返回部分状态更新
    # ========================================
    from app.ai.agent import nodes as agent_nodes

    graph.add_node("intent_recognition", agent_nodes.intent_recognition_node)
    graph.add_node("plan_generation", agent_nodes.plan_generation_node)
    graph.add_node("human_approval", agent_nodes.human_approval_node)
    graph.add_node("execution", agent_nodes.execution_node)
    graph.add_node("result_reporting", agent_nodes.result_reporting_node)
    graph.add_node("error_reporting", agent_nodes.error_reporting_node)

    # ========================================
    # 第三步：设置入口点
    # 图的执行从 intent_recognition 节点开始
    # ========================================
    graph.set_entry_point("intent_recognition")

    # ========================================
    # 第四步：添加条件边
    # 条件边根据路由函数的返回值决定下一个节点
    # ========================================

    # 意图识别后：unknown → error_reporting，其他 → plan_generation
    graph.add_conditional_edges(
        "intent_recognition",
        _route_after_intent,
        {
            "error_reporting": "error_reporting",
            "plan_generation": "plan_generation",
        },
    )

    # 计划生成后：无条件进入 human_approval
    graph.add_edge("plan_generation", "human_approval")

    # 审批后：approved → execution，其他 → END
    graph.add_conditional_edges(
        "human_approval",
        _route_after_approval,
        {
            "execution": "execution",
            END: END,
        },
    )

    # 执行后：有错误 → error_reporting，无错误 → result_reporting
    graph.add_conditional_edges(
        "execution",
        _route_after_execution,
        {
            "error_reporting": "error_reporting",
            "result_reporting": "result_reporting",
        },
    )

    # 结果报告和错误报告后：都进入 END
    graph.add_edge("result_reporting", END)
    graph.add_edge("error_reporting", END)

    # ========================================
    # 第五步：编译图
    # 编译后的图可以直接调用 .invoke() 或 .ainvoke() 执行
    # ========================================
    return graph.compile()


# ============================================================
# 模块级别的图实例（延迟初始化）
#
# 说明：使用函数调用来获取图实例，避免模块导入时就编译图。
#      这样可以在测试中方便地 mock 各个节点。
# ============================================================
_compiled_graph = None


def get_agent_graph():
    """
    获取编译后的 Agent 图实例（单例模式）

    说明：首次调用时编译图，后续调用返回缓存的实例。
         类似 Spring 的 @Bean 单例。

    返回：
        编译后的 StateGraph 实例
    """
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_agent_graph()
    return _compiled_graph
