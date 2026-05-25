"""
Agent 状态定义（ai/agent/state.py）

说明：定义 LangGraph Agent 的状态模式（State Schema）。
     状态在图的每个节点之间传递，每个节点可以读取和修改状态。

核心概念：
    - TypedDict：Python 类型化字典，用于定义状态的字段和类型
    - 状态是不可变的快照：每个节点返回新的状态字典（部分更新）
    - LangGraph 会自动合并节点返回的部分状态到完整状态中

状态流转：
    1. 用户输入 → intent_recognition（填充 intent, provider_name）
    2. → plan_generation（填充 plan, risk_level, executable, warnings）
    3. → human_approval（填充 approval_status, requires_approval）
    4. → execution（填充 execution_results, result_summary）
    5. → result_reporting / error_reporting（最终状态）

Java 对应关系：
    AgentTask 实体的各字段 → AgentState 的各字段
    AgentTaskService 的中间变量 → AgentState 的中间状态
"""

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """
    Agent 状态模式 - 在图的每个节点之间传递

    说明：使用 total=False 表示所有字段都是可选的，
         这样每个节点只需要返回它修改的字段即可。
         LangGraph 会自动将返回的部分状态合并到完整状态中。

    字段分组：
        - 输入字段：用户请求的原始数据
        - 意图识别字段：LLM 或规则引擎识别的意图
        - 执行计划字段：生成的结构化执行计划
        - 审批字段：人工审批相关状态
        - 执行字段：计划执行的结果
        - 错误字段：错误历史记录
        - 元数据字段：任务追踪信息
    """

    # ========================================
    # 输入字段（由调用方设置）
    # ========================================
    user_id: int  # 发起指令的用户ID
    command: str  # 用户原始指令文本（如 "帮我请两天年假"）

    # ========================================
    # 意图识别字段（由 intent_recognition 节点填充）
    # ========================================
    intent: str | None  # 识别到的意图类型
    # 可选值：leave.create / attendance.upsert / role-permission.update / unknown

    # ========================================
    # 执行计划字段（由 plan_generation 节点填充）
    # ========================================
    plan: dict[str, Any] | None  # 完整的执行计划（AgentPlan 的字典形式）
    risk_level: str | None  # 风险等级：low / medium / high
    executable: bool  # 计划是否可执行（权限校验通过等）
    warnings: list[str]  # 警告信息列表（如缺少权限、参数不完整等）

    # ========================================
    # 审批字段（由 human_approval 节点填充）
    # ========================================
    approval_status: str | None  # 审批状态：pending / approved / rejected
    requires_approval: bool  # 是否需要人工审批（当前所有任务都需要）

    # ========================================
    # 执行字段（由 execution 节点填充）
    # ========================================
    current_step: int  # 当前执行到的步骤序号
    execution_results: list[dict]  # 每个步骤的执行结果列表
    result_summary: str | None  # 最终执行结果摘要

    # ========================================
    # 错误字段（由各节点在出错时填充）
    # ========================================
    error_history: list[str]  # 错误历史记录（用于调试和重试）

    # ========================================
    # 元数据字段（由服务层设置）
    # ========================================
    task_id: int | None  # 数据库中的任务ID（保存后回填）
    provider_name: str | None  # 使用的 LLM 提供商名称

    # ========================================
    # DraftPlan 中间结果（意图识别的原始输出）
    # ========================================
    draft_plan: dict[str, Any] | None  # LLM 或规则引擎输出的草稿计划
