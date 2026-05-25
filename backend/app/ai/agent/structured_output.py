"""
LLM 结构化输出解析和重试（ai/agent/structured_output.py）

说明：封装 LLM 结构化输出的调用和解析逻辑。
     使用 Pydantic 模型验证 LLM 返回的 JSON，失败时带纠正提示重试。

核心功能：
    - parse_draft_plan: 解析 LLM 响应为 DraftPlan 模型
    - call_llm_with_structured_output: 带重试的 LLM 结构化输出调用
    - build_agent_system_prompt: 构建 Agent 意图识别的系统提示词

重试策略：
    1. 第一次调用：使用标准系统提示词
    2. 解析失败后重试：在提示词中附加验证错误信息，要求 LLM 修正
    3. 最多重试 2 次（共 3 次调用）

Java 对应关系：
    AgentTaskService.callOpenAiDraft()    → call_llm_with_structured_output
    AgentTaskService.buildSystemPrompt()  → build_agent_system_prompt
    ObjectMapper.readValue(content, DraftPlan.class) → parse_draft_plan
"""

import json
import logging

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from app.schemas.agent import DraftPlan

logger = logging.getLogger(__name__)


# ============================================================
# 系统提示词模板
# ============================================================

AGENT_SYSTEM_PROMPT = """你是一个 HR 系统的意图识别助手。根据用户的自然语言指令，提取结构化信息。

请返回一个 JSON 对象，包含以下字段：
- intent: 意图类型，必须是以下之一：leave.create, attendance.upsert, role-permission.update, unknown
- summary: 操作摘要描述（中文）
- action: 具体动作（仅 role-permission.update 时使用，值为 add 或 remove）
- leave_type: 请假类型（年假/病假/事假/婚假/产假/陪产假/丧假）
- start_date: 开始日期（格式 yyyy-MM-dd）
- end_date: 结束日期（格式 yyyy-MM-dd）
- days: 天数（整数）
- reason: 原因/备注
- attendance_date: 考勤日期（格式 yyyy-MM-dd）
- clock_in: 签到时间（格式 HH:mm）
- clock_out: 签退时间（格式 HH:mm）
- role_name: 角色名称
- permission_name: 权限名称

规则：
1. 只返回 JSON 对象，不要包含其他文本
2. 日期格式必须是 yyyy-MM-dd，时间格式必须是 HH:mm
3. 未提及的字段设为 null
4. intent 字段必须填写
"""

CORRECTION_PROMPT_TEMPLATE = """上一次的 JSON 输出解析失败，错误信息如下：
{errors}

请修正你的输出，确保返回有效的 JSON 对象。注意：
1. 所有字段名使用下划线命名（如 leave_type, start_date）
2. intent 必须是 leave.create, attendance.upsert, role-permission.update, unknown 之一
3. 日期格式 yyyy-MM-dd，时间格式 HH:mm
4. 只返回 JSON，不要包含 markdown 代码块标记

用户原始指令：{command}
"""


# ============================================================
# 解析函数
# ============================================================


def parse_draft_plan(llm_response: str) -> DraftPlan:
    """
    解析 LLM 响应为 DraftPlan 模型

    说明：从 LLM 的文本响应中提取 JSON 并验证为 DraftPlan 模型。
         支持处理 LLM 可能返回的 markdown 代码块包裹的 JSON。

    参数：
        llm_response: LLM 返回的原始文本

    返回：
        验证通过的 DraftPlan 实例

    异常：
        ValidationError: JSON 结构不符合 DraftPlan Schema
        json.JSONDecodeError: 响应不是有效的 JSON
    """
    # 清理响应文本：去除 markdown 代码块标记
    content = llm_response.strip()

    # 处理 ```json ... ``` 包裹
    if content.startswith("```"):
        # 去除开头的 ```json 或 ```
        first_newline = content.find("\n")
        if first_newline != -1:
            content = content[first_newline + 1 :]
        # 去除结尾的 ```
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

    # 尝试提取 JSON 对象（处理 LLM 可能在 JSON 前后添加文字的情况）
    json_start = content.find("{")
    json_end = content.rfind("}")
    if json_start != -1 and json_end != -1:
        content = content[json_start : json_end + 1]

    # 解析并验证
    return DraftPlan.model_validate_json(content)


# ============================================================
# LLM 调用函数
# ============================================================


async def call_llm_with_structured_output(
    model: BaseChatModel,
    command: str,
    system_prompt: str | None = None,
    max_retries: int = 2,
) -> DraftPlan:
    """
    带重试的 LLM 结构化输出调用

    说明：调用 LLM 获取结构化的意图识别结果。
         如果解析失败，会附带错误信息重试，最多重试 max_retries 次。

    处理流程：
        1. 使用系统提示词 + 用户指令调用 LLM
        2. 解析 LLM 响应为 DraftPlan
        3. 如果解析失败，构建纠正提示词重试
        4. 重试时将验证错误信息包含在提示中，帮助 LLM 修正

    参数：
        model: LangChain 聊天模型实例
        command: 用户原始指令文本
        system_prompt: 自定义系统提示词（可选，默认使用内置提示词）
        max_retries: 最大重试次数，默认 2 次

    返回：
        验证通过的 DraftPlan 实例

    异常：
        Exception: 所有重试都失败后抛出最后一次的异常
    """
    prompt = system_prompt or AGENT_SYSTEM_PROMPT
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            # 构建消息
            if attempt == 0:
                messages = [
                    SystemMessage(content=prompt),
                    HumanMessage(content=command),
                ]
            else:
                # 重试时附带纠正提示
                correction = CORRECTION_PROMPT_TEMPLATE.format(
                    errors=str(last_error),
                    command=command,
                )
                messages = [
                    SystemMessage(content=prompt),
                    HumanMessage(content=correction),
                ]

            # 调用 LLM
            response = await model.ainvoke(messages)
            content = response.content
            if isinstance(content, str):
                content = content.strip()
            else:
                raise ValueError("LLM 响应内容不是字符串")

            if not content:
                raise ValueError("LLM 响应内容为空")

            # 解析响应
            draft_plan = parse_draft_plan(content)
            logger.info(f"LLM 结构化输出解析成功（第 {attempt + 1} 次尝试）: intent={draft_plan.intent}")
            return draft_plan

        except (ValidationError, json.JSONDecodeError, ValueError) as e:
            last_error = e
            if attempt < max_retries:
                logger.warning(f"LLM 结构化输出解析失败（第 {attempt + 1} 次），准备重试: {e}")
            else:
                logger.error(f"LLM 结构化输出解析失败（已达最大重试次数 {max_retries + 1}）: {e}")

        except Exception as e:
            # 网络错误等非解析错误，直接抛出不重试
            logger.error(f"LLM 调用异常: {e}")
            raise

    # 所有重试都失败
    raise last_error  # type: ignore[misc]


def build_agent_system_prompt(
    user_context: dict | None = None,
    available_roles: list[str] | None = None,
    available_permissions: list[str] | None = None,
) -> str:
    """
    构建 Agent 意图识别的系统提示词（增强版）

    说明：对应 Java 的 AgentTaskService.buildSystemPrompt() 方法。
         在基础提示词基础上附加用户上下文和可用选项信息。

    参数：
        user_context: 用户上下文信息（userId, empId, identityTag 等）
        available_roles: 系统中可用的角色名称列表
        available_permissions: 系统中可用的权限名称列表

    返回：
        完整的系统提示词字符串
    """
    prompt = AGENT_SYSTEM_PROMPT

    # 附加上下文信息
    context_parts: list[str] = []

    if user_context:
        context_parts.append(f"当前用户信息: {json.dumps(user_context, ensure_ascii=False)}")

    context_parts.append('可用请假类型: ["年假", "病假", "事假", "婚假", "产假", "陪产假", "丧假"]')

    if available_roles:
        roles_str = json.dumps(available_roles[:20], ensure_ascii=False)
        context_parts.append(f"可用角色: {roles_str}")

    if available_permissions:
        perms_str = json.dumps(available_permissions[:80], ensure_ascii=False)
        context_parts.append(f"可用权限: {perms_str}")

    if context_parts:
        prompt += "\n\n上下文信息：\n" + "\n".join(context_parts)

    return prompt
