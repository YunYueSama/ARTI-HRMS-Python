"""
AI 聊天路由（routers/ai_chat.py）

说明：定义 AI 聊天模块的 API 端点，包括 SSE 流式聊天、历史查询和历史清除。
     使用 FastAPI 的 StreamingResponse 实现 Server-Sent Events（SSE）。

端点列表：
    POST /api/ai/chat     → SSE 流式聊天
    GET  /api/ai/history  → 获取聊天历史（分页）
    DELETE /api/ai/history → 清除聊天历史

Java 对应关系：
    AiChatController.chat()         → chat_stream()
    AiChatController.getHistory()   → get_history()
    AiChatController.clearHistory() → clear_history()

SSE 协议格式：
    每个数据块：data: {text}\n\n
    结束标记：  data: [DONE]\n\n
"""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.chat.service import ChatService
from app.core.config import settings
from app.core.database import get_mysql_session
from app.models.ai_chat import AiChatMessage
from app.schemas.ai_chat import ChatMessageResponse, ChatRequest
from app.schemas.common import ApiResponse, PageResponse, ok

logger = logging.getLogger(__name__)

router = APIRouter()

# 聊天服务单例（延迟初始化）
_chat_service: ChatService | None = None


def _get_chat_service() -> ChatService:
    """获取聊天服务单例"""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service


# ============================================================
# POST /api/ai/chat - SSE 流式聊天
# ============================================================


@router.post("/chat")
async def chat_stream(
    request: ChatRequest,
    db: AsyncSession = Depends(get_mysql_session),
):
    """
    AI 聊天

    说明：接收用户消息，通过 LLM 生成回复。
         支持两种模式：
         - 如果请求头包含 Accept: text/event-stream → SSE 流式输出
         - 否则 → 普通 JSON 响应（兼容前端 axios 调用）

    请求体：
        - user_id: 用户 ID
        - message: 用户消息内容（1-2000 字符）
    """
    service = _get_chat_service()

    # 普通 JSON 响应模式（前端 axios 调用）
    try:
        result = await service.chat_sync(
            user_id=request.user_id,
            message=request.message,
            db=db,
        )
        return ok(
            data={
                "reply": result["reply"],
                "role": "assistant",
                "provider": result["provider"],
                "model": result["model"],
                "providerAvailable": result["providerAvailable"],
            }
        )
    except Exception as e:
        logger.error(f"聊天异常: {e}")
        return ok(
            data={
                "reply": f"抱歉，模型连接出现问题：{str(e)}",
                "role": "assistant",
                "providerAvailable": False,
            }
        )


# ============================================================
# GET /api/ai/history - 获取聊天历史（分页）
# ============================================================


@router.get("/history", response_model=ApiResponse[PageResponse[ChatMessageResponse]])
async def get_history(
    user_id: int = Query(description="用户ID"),
    page: int = Query(default=1, ge=1, description="页码"),
    size: int = Query(default=50, ge=1, le=200, description="每页大小"),
    db: AsyncSession = Depends(get_mysql_session),
):
    """
    获取聊天历史记录（分页）

    说明：按时间倒序返回指定用户的聊天记录，支持分页。
         类似 Java 版 AiChatController.getHistory()。

    参数：
        user_id: 用户 ID
        page: 页码（从 1 开始）
        size: 每页大小（1-200）

    返回：
        分页的聊天消息列表
    """
    # 查询总数
    count_stmt = select(func.count()).select_from(AiChatMessage).where(AiChatMessage.user_id == user_id)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    # 分页查询（按 id 倒序，避免同秒级时间戳导致顺序错乱）
    offset = (page - 1) * size
    query_stmt = (
        select(AiChatMessage)
        .where(AiChatMessage.user_id == user_id)
        .order_by(desc(AiChatMessage.id))
        .offset(offset)
        .limit(size)
    )
    result = await db.execute(query_stmt)
    records = result.scalars().all()

    # 转换为响应模型
    items = [ChatMessageResponse.model_validate(record) for record in records]

    page_response = PageResponse[ChatMessageResponse](
        items=items,
        total=total,
        page=page,
        size=size,
    )

    return ok(data=page_response)


# ============================================================
# DELETE /api/ai/history - 清除聊天历史
# ============================================================


@router.delete("/history", response_model=ApiResponse)
async def clear_history(
    user_id: int = Query(description="用户ID"),
    db: AsyncSession = Depends(get_mysql_session),
):
    """
    清除指定用户的聊天历史

    说明：删除该用户的所有聊天记录。
         类似 Java 版 AiChatController.clearHistory()。

    参数：
        user_id: 用户 ID

    返回：
        操作结果
    """
    stmt = delete(AiChatMessage).where(AiChatMessage.user_id == user_id)
    await db.execute(stmt)
    logger.info(f"已清除用户 {user_id} 的聊天历史")

    return ok(message="聊天历史已清除")


# ============================================================
# GET /api/ai/history/{user_id} - 获取聊天历史（路径参数版本）
# ============================================================


@router.get("/history/{user_id}")
async def get_history_by_path(
    user_id: int,
    page: int = Query(default=1, ge=1, description="页码"),
    size: int = Query(default=50, ge=1, le=200, description="每页大小"),
    db: AsyncSession = Depends(get_mysql_session),
):
    """
    获取聊天历史记录（路径参数版本）

    说明：前端通过 /ai/history/{userId} 获取指定用户的聊天记录。
         返回值为聊天消息数组（按时间正序，最早的在前），
         前端可直接遍历渲染，不需要再访问 .items 字段。

    注意：这里特意不使用 response_model 参数。
         如果声明 response_model=ApiResponse[PageResponse[...]] 会导致 FastAPI
         尝试把 list 强制转换为 PageResponse 对象，失败后 data 字段会变成 null，
         前端就拿不到数据了。
    """
    # 查询当前页的所有消息（按 id 倒序，限制条数）
    # 说明：之所以用 id 而非 create_time 排序，是因为同一轮对话的
    #      user 行与 assistant 行常常落在同一秒（datetime 精度不够），
    #      用 create_time 排序会导致用户消息和助手消息次序错乱。
    #      id 是自增主键，严格反映插入顺序，最稳。
    offset = (page - 1) * size
    query_stmt = (
        select(AiChatMessage)
        .where(AiChatMessage.user_id == user_id)
        .order_by(desc(AiChatMessage.id))
        .offset(offset)
        .limit(size)
    )
    result = await db.execute(query_stmt)
    records = result.scalars().all()

    # 转换为响应模型，再逐条转字典（避免 Pydantic 包装 list 出问题）
    items = [ChatMessageResponse.model_validate(record).model_dump(mode="json") for record in records]
    # 前端期望直接返回数组（不是分页对象）
    # 按时间正序返回（最早的在前，最新的在后）
    items.reverse()

    logger.info(f"返回用户 {user_id} 的聊天历史共 {len(items)} 条")
    return ok(data=items)


# ============================================================
# DELETE /api/ai/history/{user_id} - 清除聊天历史（路径参数版本）
# ============================================================


@router.delete("/history/{user_id}", response_model=ApiResponse)
async def clear_history_by_path(
    user_id: int,
    db: AsyncSession = Depends(get_mysql_session),
):
    """
    清除指定用户的聊天历史（路径参数版本）

    说明：前端通过 DELETE /ai/history/{userId} 清除聊天记录。
    """
    stmt = delete(AiChatMessage).where(AiChatMessage.user_id == user_id)
    await db.execute(stmt)
    logger.info(f"已清除用户 {user_id} 的聊天历史")
    return ok(message="聊天历史已清除")


# ============================================================
# GET /api/ai/provider-info - 获取当前 LLM 提供商信息
# ============================================================


async def _check_ollama_alive(base_url: str) -> bool:
    """检测 Ollama 服务是否实际运行中（TCP 端口探测）"""
    import asyncio
    from urllib.parse import urlparse

    try:
        parsed = urlparse(base_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 11434
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=2.0)
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False


@router.get("/provider-info", response_model=ApiResponse)
async def get_provider_info():
    """
    获取当前 LLM 提供商信息

    说明：返回当前配置的主 LLM 提供商名称、模型和真实连接状态。
         前端通过 /ai/provider-info 获取。
    """
    from app.ai.chat.llm_provider import get_effective_primary_config
    from app.core.config import get_runtime_overrides

    # 获取合并运行时覆盖后的配置
    effective = get_effective_primary_config(get_runtime_overrides() or None)

    # 检测主模型：API Key 是否已配置
    api_key_display = ""
    if effective.api_key and effective.api_key not in ("your_dashscope_api_key_here", ""):
        api_key_display = effective.api_key[:8] + "..." + effective.api_key[-4:]
        primary_status = "active"
    else:
        primary_status = "disconnected"

    # 检测备用模型：Ollama 服务是否实际在运行
    if settings.LLM_FALLBACK_PROVIDER == "ollama":
        fallback_alive = await _check_ollama_alive(settings.LLM_FALLBACK_BASE_URL)
        fallback_status = "active" if fallback_alive else "disconnected"
    else:
        # 非 Ollama 备用提供商，检查 API Key
        fallback_config = settings.fallback_llm_config
        fallback_status = "active" if fallback_config.api_key else "disconnected"

    return ok(
        data={
            "provider": effective.provider,
            "model": effective.model,
            "status": primary_status,
            "providerAvailable": primary_status == "active",
            "apiKeyConfigured": bool(api_key_display),
            "apiKeyPreview": api_key_display,
            "fallbackProvider": settings.LLM_FALLBACK_PROVIDER,
            "fallbackModel": settings.LLM_FALLBACK_MODEL,
            "fallbackStatus": fallback_status,
        }
    )
