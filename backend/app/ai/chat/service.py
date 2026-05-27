"""
AI 聊天服务（ai/chat/service.py）

说明：核心聊天服务类，整合 LLM 调用、消息分类、知识注入、对话记忆和流式输出。
     使用 LangChain LCEL（LangChain Expression Language）构建聊天链。

核心流程：
    1. 消息分类 → 确定回答策略
    2. 知识查询 → 注入系统数据（如果是数据查询类）
    3. 加载历史 → 从数据库读取最近对话
    4. 构建 LCEL 链 → ChatPromptTemplate | model | StrOutputParser
    5. 流式输出 → 逐 chunk 返回给前端
    6. 保存记录 → 将对话存入数据库

Java 对应关系：
    AiChatService.chat()         → ChatService.chat_stream() / chat_sync()
    AiChatService.callProvider() → LCEL chain (ChatPromptTemplate | model | StrOutputParser)

设计说明：
    - 主模型不可用时自动回退到备用模型
    - 备用模型也不可用时返回优雅降级回复
    - 支持流式（SSE）和同步两种调用方式
    - 所有操作均为异步，不阻塞事件循环
"""

import logging
from collections.abc import AsyncGenerator

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.chat.classifier import classify_message
from app.ai.chat.llm_provider import (
    call_with_retry,
    get_effective_primary_config,
    get_fallback_model,
    get_primary_model,
)
from app.ai.chat.memory import DatabaseChatMemory
from app.ai.chat.prompts import build_system_prompt, get_active_persona, get_few_shot_examples
from app.ai.knowledge.service import query_knowledge
from app.core.config import get_runtime_overrides, settings
from app.schemas.agent import MessageCategory

logger = logging.getLogger(__name__)


class ChatService:
    """
    AI 聊天服务

    说明：封装完整的聊天流程，包括分类、知识注入、LLM 调用和记忆管理。
         支持流式输出（chat_stream）和同步调用（chat_sync）两种模式。

    用法：
        service = ChatService()
        async for chunk in service.chat_stream(user_id=1, message="你好", db=session):
            print(chunk, end="")
    """

    def __init__(self):
        """
        初始化聊天服务

        说明：延迟初始化 LLM 模型实例。模型在首次调用时创建，
             避免应用启动时因 API Key 未配置而报错。
             支持运行时配置变更：当 PUT /api/config/model 更新配置后，
             下次调用会自动重新创建模型实例。
        """
        self._primary_model: BaseChatModel | None = None
        self._fallback_model: BaseChatModel | None = None
        self._initialized = False
        self._last_config_hash: str = ""

    def _ensure_initialized(self) -> None:
        """确保模型已初始化，配置变更时自动重建"""
        current_overrides = get_runtime_overrides()
        current_hash = str(hash(frozenset(current_overrides.items()))) if current_overrides else "empty"

        if self._initialized and current_hash == self._last_config_hash:
            return

        # 配置已变更或首次初始化，重建模型
        self._primary_model = get_primary_model(current_overrides or None)
        self._fallback_model = get_fallback_model()
        self._initialized = True
        self._last_config_hash = current_hash
        logger.info(
            f"ChatService 模型已{'更新' if current_overrides else '初始化'}: "
            f"primary={'可用' if self._primary_model else '未配置'}, "
            f"fallback={'可用' if self._fallback_model else '未配置'}"
        )

    async def chat_stream(
        self,
        user_id: int,
        message: str,
        db: AsyncSession,
    ) -> AsyncGenerator[str, None]:
        """
        流式聊天（SSE 输出）

        说明：完整的聊天流程，逐 chunk 返回 LLM 生成的文本。
             适用于前端 SSE（Server-Sent Events）实时展示。

        流程：
            1. 分类消息 → 确定回答策略
            2. 查询知识 → 注入系统数据（system_data_query 类别时）
            3. 加载历史 → 从数据库读取最近对话
            4. 构建 LCEL 链 → 组装提示词模板和模型
            5. 流式调用 → 逐 chunk yield
            6. 保存记录 → 完成后存入数据库

        参数：
            user_id: 用户 ID
            message: 用户消息文本
            db: 异步数据库会话

        Yields：
            str: LLM 生成的文本片段（chunk）
        """
        self._ensure_initialized()

        # Step 1: 消息分类
        category = await classify_message(message, self._primary_model)
        logger.info(f"消息分类: {category.value} (user_id={user_id})")

        # Step 2: 混合检索（关键词 + 增强向量 + 知识图谱，并行执行，RRF 融合）
        knowledge_context = ""
        if category == MessageCategory.SYSTEM_DATA_QUERY:
            knowledge_context = await _hybrid_retrieve(message, user_id, db)
            logger.info(
                f"知识注入结果: 长度={len(knowledge_context)}, 预览={knowledge_context[:200] if knowledge_context else '(空)'}"
            )

        # Step 3: 加载对话历史
        # 回滚以清除可能的失败事务状态（前面的并行检索可能已损坏会话）
        await db.rollback()
        memory = DatabaseChatMemory(user_id=user_id, db=db)
        history_messages = await memory.load_messages(window_size=10)

        # Step 4: 加载人设并构建系统提示词
        persona_text = await get_active_persona(db)
        system_prompt = build_system_prompt(category.value, knowledge_context, persona_text)
        few_shot = get_few_shot_examples(category.value)

        # Step 5: 尝试流式调用（主模型 → 备用模型 → 降级回复）
        full_response = ""
        provider_name = ""
        model_name = ""

        # 尝试主模型
        if self._primary_model:
            try:
                async for chunk in self._stream_with_model(
                    self._primary_model, system_prompt, few_shot, history_messages, message
                ):
                    full_response += chunk
                    yield chunk
                provider_name = settings.LLM_PRIMARY_PROVIDER
                model_name = get_effective_primary_config(get_runtime_overrides() or None).model
            except Exception as e:
                logger.warning(f"主模型流式调用失败: {e}")
                full_response = ""  # 重置，尝试备用模型

        # 主模型失败，尝试备用模型
        if not full_response and self._fallback_model:
            try:
                async for chunk in self._stream_with_model(
                    self._fallback_model, system_prompt, few_shot, history_messages, message
                ):
                    full_response += chunk
                    yield chunk
                provider_name = settings.LLM_FALLBACK_PROVIDER
                model_name = settings.LLM_FALLBACK_MODEL
            except Exception as e:
                logger.warning(f"备用模型流式调用失败: {e}")
                full_response = ""

        # 所有模型都失败，返回降级回复
        if not full_response:
            fallback_reply = self._build_fallback_reply(knowledge_context)
            full_response = fallback_reply
            provider_name = "local-fallback"
            model_name = "persona-template"
            yield fallback_reply

        # Step 6: 保存对话记录
        try:
            await memory.save_messages(
                human_message=message,
                ai_message=full_response,
                provider_name=provider_name,
                model_name=model_name,
                used_system_data=bool(knowledge_context),
            )
        except Exception as e:
            logger.error(f"保存对话记录失败: {e}")

    async def chat_sync(
        self,
        user_id: int,
        message: str,
        db: AsyncSession,
    ) -> dict:
        """
        同步聊天（非流式，用于回退场景）

        说明：与 chat_stream 相同的流程，但一次性返回完整回复。
             适用于不支持 SSE 的场景或内部调用。

        参数：
            user_id: 用户 ID
            message: 用户消息文本
            db: 异步数据库会话

        返回：
            dict: {reply, provider, model, providerAvailable}
        """
        import time

        from app.ai.observability.tracer import langfuse_tracer

        self._ensure_initialized()
        start_ts = time.time()

        # 分类
        category = await classify_message(message, self._primary_model)

        # 混合检索
        knowledge_context = ""
        if category == MessageCategory.SYSTEM_DATA_QUERY:
            knowledge_context = await _hybrid_retrieve(message, user_id, db)

        # 加载对话历史
        # 回滚以清除可能的失败事务状态（前面的并行检索可能已损坏会话）
        await db.rollback()
        memory = DatabaseChatMemory(user_id=user_id, db=db)
        history_messages = await memory.load_messages(window_size=10)

        # 加载人设并构建提示词
        persona_text = await get_active_persona(db)
        system_prompt = build_system_prompt(category.value, knowledge_context, persona_text)
        few_shot = get_few_shot_examples(category.value)

        # 构建消息列表
        messages = self._build_messages(system_prompt, few_shot, history_messages, message)

        # 尝试调用（主模型 → 备用模型 → 降级）
        reply = ""
        provider_name = ""
        model_name = ""
        status = "success"

        async with langfuse_tracer.trace("chat", user_id=user_id, input=message[:200]) as trace_ctx:
            if self._primary_model:
                try:
                    reply = await call_with_retry(self._primary_model, messages)
                    provider_name = settings.LLM_PRIMARY_PROVIDER
                    model_name = get_effective_primary_config(get_runtime_overrides() or None).model
                except Exception as e:
                    logger.warning(f"主模型同步调用失败: {e}")

            if not reply and self._fallback_model:
                try:
                    reply = await call_with_retry(self._fallback_model, messages)
                    provider_name = settings.LLM_FALLBACK_PROVIDER
                    model_name = settings.LLM_FALLBACK_MODEL
                except Exception as e:
                    logger.warning(f"备用模型同步调用失败: {e}")
                    status = "error"

            if not reply:
                reply = self._build_fallback_reply(knowledge_context)
                provider_name = "local-fallback"
                model_name = "persona-template"
                status = "error"

            # 记录 trace 元信息（trace_ctx 已经持有 trace_id 和耗时）
            trace_ctx.metadata["output"] = reply[:300]
            trace_ctx.metadata["model"] = model_name
            trace_ctx.metadata["provider"] = provider_name
            trace_ctx.metadata["status"] = status
            trace_ctx.metadata["category"] = category.value

        # 把 trace 写入数据库 llm_trace 表，供 /api/traces 查询使用
        try:
            await self._record_trace(
                db=db,
                trace_id=trace_ctx.trace_id,
                user_id=user_id,
                operation_type="chat",
                model_name=model_name,
                input_text=message,
                output_text=reply,
                latency_ms=(time.time() - start_ts) * 1000,
                status=status,
            )
        except Exception as e:
            logger.warning(f"记录 trace 失败: {e}")

        # 保存记录
        try:
            await memory.save_messages(
                human_message=message,
                ai_message=reply,
                provider_name=provider_name,
                model_name=model_name,
                used_system_data=bool(knowledge_context),
            )
        except Exception as e:
            logger.error(f"保存对话记录失败: {e}")

        return {
            "reply": reply,
            "provider": provider_name,
            "model": model_name,
            "providerAvailable": status != "error",
        }

    @staticmethod
    async def _record_trace(
        db: AsyncSession,
        trace_id: str,
        user_id: int,
        operation_type: str,
        model_name: str,
        input_text: str,
        output_text: str,
        latency_ms: float,
        status: str,
    ) -> None:
        """
        把一次 LLM 调用持久化到 llm_trace 表

        说明：替代了旧版的内存 TraceStore，重启后数据不丢。
        """
        # 延迟 import 避免循环依赖
        from datetime import datetime

        from app.ai.observability.token_counter import calculate_cost, count_tokens
        from app.routers.observability import trace_store
        from app.schemas.observability import TraceRecord

        input_tokens = count_tokens(input_text, model_name)
        output_tokens = count_tokens(output_text, model_name)
        total_tokens = input_tokens + output_tokens
        cost = calculate_cost(input_tokens, output_tokens, model_name)

        record = TraceRecord(
            trace_id=trace_id,
            user_id=user_id,
            operation_type=operation_type,
            model_name=model_name or "",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            cost_estimate=cost,
            status=status if latency_ms < 10_000 else "slow",
            tags=[],
            feedback=None,
            create_time=datetime.now(),
        )
        await trace_store.add_async(db, record)

    async def _stream_with_model(
        self,
        model: BaseChatModel,
        system_prompt: str,
        few_shot: str,
        history: list[BaseMessage],
        user_message: str,
    ) -> AsyncGenerator[str, None]:
        """
        使用指定模型进行流式调用

        说明：构建 LCEL 链（ChatPromptTemplate | model | StrOutputParser），
             使用 chain.astream() 逐 chunk 输出。

        参数：
            model: LangChain 聊天模型实例
            system_prompt: 系统提示词（含人设 + 分类指令 + 事实注入）
            few_shot: Few-Shot 示例文本
            history: 历史消息列表
            user_message: 当前用户消息

        Yields：
            str: 模型生成的文本片段
        """
        # 构建 LCEL 链
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_prompt}"),
                ("system", "{few_shot}"),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}"),
            ]
        )

        chain = prompt | model | StrOutputParser()

        # 流式调用
        async for chunk in chain.astream(
            {
                "system_prompt": system_prompt,
                "few_shot": few_shot,
                "history": history,
                "input": user_message,
            }
        ):
            if chunk:
                yield chunk

    def _build_messages(
        self,
        system_prompt: str,
        few_shot: str,
        history: list[BaseMessage],
        user_message: str,
    ) -> list[BaseMessage]:
        """构建完整的消息列表（用于同步调用）"""
        messages: list[BaseMessage] = [
            SystemMessage(content=system_prompt),
            SystemMessage(content=few_shot),
        ]
        messages.extend(history)
        messages.append(HumanMessage(content=user_message))
        return messages

    @staticmethod
    def _build_fallback_reply(knowledge_context: str) -> str:
        """
        构建降级回复（所有 LLM 都不可用时）

        说明：当主模型和备用模型都无法连接时，返回一个基于模板的回复。
             如果有知识上下文，会将系统数据包含在回复中。
             类似 Java 版 AiChatService.buildFallbackReply()。
        """
        parts = ["我是亚托莉。虽然这次模型连接没有成功，不过主人先别着急，" "高性能的我还是会先把能确认的信息告诉你。"]

        if knowledge_context.strip():
            parts.append("")
            parts.append(knowledge_context)
            parts.append("")
            parts.append("这些内容来自当前系统里的只读数据，所以可以先把它当成可靠依据。")
        else:
            parts.append("")
            parts.append("这轮没有命中系统里的只读数据，所以我暂时先陪你聊天，或者解释通用流程。")

        parts.append("")
        parts.append("如果你愿意，可以把问题再问得更具体一点。请交给我吧，我会继续认真回答你。")

        return "\n".join(parts)


# ============================================================
# 混合检索编排（模块级函数）
# ============================================================

import asyncio  # noqa: E402


async def _hybrid_retrieve(message: str, user_id: int, db: AsyncSession) -> str:
    """
    混合检索：关键词查询 + 增强向量检索 + 知识图谱，并行执行，RRF 融合

    流程：
        1. 并行执行三个检索任务：
           - 关键词查询（query_knowledge）→ 直查 MySQL
           - 增强向量检索（enhanced_vector_search）→ pgvector + 查询增强
           - 知识图谱查询（_try_graph_query）→ 实体匹配 → NetworkX
        2. 使用 RRF 融合三路结果
        3. 返回融合后的 LLM 上下文文本

    参数：
        message: 用户消息
        user_id: 用户 ID
        db: 数据库会话

    返回：
        融合后的知识上下文文本（空字符串表示无结果）
    """
    from app.ai.chat.query_enhancer import enhanced_vector_search
    from app.ai.graph_rag.fusion import fusion_search_rrf

    try:
        # 并行执行三个检索任务
        keyword_task = query_knowledge(message, user_id, db)
        vector_task = enhanced_vector_search(message, db)
        graph_task = _try_graph_query(message)

        results = await asyncio.gather(
            keyword_task,
            vector_task,
            graph_task,
            return_exceptions=True,
        )

        # 如果任何一路检索抛出异常，回滚事务以恢复会话状态
        # 否则后续操作（如 load_messages）会在失败的事务上崩溃
        if any(isinstance(r, BaseException) for r in results):
            await db.rollback()
            for r in results:
                if isinstance(r, BaseException):
                    logger.warning(f"混合检索子任务异常: {r}")

        keyword_ctx = results[0] if isinstance(results[0], str) else ""
        vector_results = results[1] if isinstance(results[1], list) else []
        graph_results = results[2] if isinstance(results[2], list) else []

        # 调试日志：显示各路检索结果
        top_score = max((r.get("score", 0) for r in vector_results), default=0)
        logger.info(
            f"混合检索结果: keyword={'有' if keyword_ctx else '无'}, "
            f"vector={len(vector_results)}条(最高分={top_score:.3f}), "
            f"graph={len(graph_results)}条"
        )

        if not keyword_ctx and not vector_results and not graph_results:
            # 所有检索都无结果，回退到关键词查询
            logger.info("混合检索三路均无结果，回退到关键词查询")
            return await query_knowledge(message, user_id, db)

        # RRF 融合
        return fusion_search_rrf(
            keyword_context=keyword_ctx,
            vector_results=vector_results,
            graph_results=graph_results,
        )
    except Exception as e:
        logger.warning(f"混合检索失败，回退到关键词查询: {e}")
        await db.rollback()
        try:
            return await query_knowledge(message, user_id, db)
        except Exception:
            return ""


async def _try_graph_query(message: str) -> list[dict]:
    """
    尝试从消息中提取实体名称并查询知识图谱

    策略：遍历知识图谱中的节点名，检查是否出现在用户消息中。
         命中则调用 query_relationships 查询关联关系。
         未命中则返回空列表（不影响其他检索）。

    参数：
        message: 用户消息

    返回：
        图谱查询结果列表
    """
    entity_name = _extract_entity_name(message)
    if not entity_name:
        return []

    try:
        from app.ai.graph_rag.knowledge_graph import hr_knowledge_graph

        return hr_knowledge_graph.query_relationships(entity_name, max_hops=2)
    except Exception as e:
        logger.debug(f"知识图谱查询失败: {e}")
        return []


def _extract_entity_name(message: str) -> str | None:
    """
    从消息中提取实体名称（基于知识图谱节点匹配）

    遍历知识图谱的所有节点名，检查是否出现在消息文本中。
    优先返回最长的匹配名称（更具体的实体）。

    参数：
        message: 用户消息

    返回：
        匹配到的实体名称，未匹配返回 None
    """
    try:
        from app.ai.graph_rag.knowledge_graph import hr_knowledge_graph

        graph = hr_knowledge_graph.graph
        if not graph or graph.number_of_nodes() == 0:
            return None

        best_match: str | None = None
        best_len = 0
        for _node_id, attrs in graph.nodes(data=True):
            name = attrs.get("name", "")
            if name and len(name) >= 2 and name in message and len(name) > best_len:
                best_match = name
                best_len = len(name)

        if best_match:
            logger.debug(f"图谱实体提取: '{best_match}' from '{message[:30]}...'")

        return best_match
    except Exception:
        return None
