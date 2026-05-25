"""
LLM 提供商配置和初始化（ai/chat/llm_provider.py）

说明：封装 LangChain ChatOpenAI 实例的创建和调用逻辑。
     支持主提供商（阿里云百炼 DashScope）和备用提供商（Ollama 本地），
     两者均兼容 OpenAI API 格式，因此统一使用 ChatOpenAI 类。

核心功能：
    - get_chat_model: 根据配置创建 LangChain ChatOpenAI 实例
    - get_primary_model: 获取主 LLM 模型实例
    - get_fallback_model: 获取备用 LLM 模型实例
    - call_with_retry: 带指数退避重试的 LLM 调用

Java 对应关系：
    AiChatService.callProvider()         → get_chat_model + call_with_retry
    AiChatService.callOpenAiCompatible() → ChatOpenAI (LangChain 封装)
    AiChatService.callOllama()           → ChatOpenAI (Ollama 兼容 OpenAI 格式)
"""

import asyncio
import logging
from typing import Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage

from app.core.config import LLMProviderConfig, settings

logger = logging.getLogger(__name__)


def get_effective_primary_config(runtime_overrides: dict | None = None) -> LLMProviderConfig:
    """获取合并运行时覆盖后的主模型配置"""
    base = settings.primary_llm_config
    if not runtime_overrides:
        return base

    return LLMProviderConfig(
        provider=runtime_overrides.get("provider", base.provider),
        base_url=runtime_overrides.get("base_url", base.base_url),
        api_key=runtime_overrides.get("api_key") or base.api_key,
        model=runtime_overrides.get("model_name", base.model),
        temperature=runtime_overrides.get("temperature", base.temperature),
        max_tokens=runtime_overrides.get("max_output_tokens", base.max_tokens),
    )


def get_chat_model(provider_config: LLMProviderConfig) -> BaseChatModel:
    """
    根据提供商配置创建 LangChain ChatOpenAI 实例

    说明：无论是阿里云百炼（DashScope）还是 Ollama，都兼容 OpenAI API 格式，
         因此统一使用 langchain_openai.ChatOpenAI 类，只需调整 base_url 和 api_key。

    参数：
        provider_config: LLM 提供商配置对象，包含 base_url、api_key、model 等

    返回：
        BaseChatModel 实例（实际为 ChatOpenAI）

    异常：
        ImportError: 未安装 langchain-openai 包时抛出
    """
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        base_url=provider_config.base_url,
        api_key=provider_config.api_key,
        model=provider_config.model,
        temperature=provider_config.temperature,
        max_tokens=provider_config.max_tokens,
        streaming=True,  # 默认启用流式输出
    )


def get_primary_model(runtime_overrides: dict | None = None) -> Optional[BaseChatModel]:
    """
    获取主 LLM 模型实例

    说明：从全局配置中读取主提供商参数，支持运行时覆盖。
         如果 API Key 未配置（仍为默认占位值），返回 None。

    参数：
        runtime_overrides: 运行时配置覆盖字典（来自 PUT /api/config/model）

    返回：
        BaseChatModel 实例，或 None（未配置时）
    """
    config = get_effective_primary_config(runtime_overrides)
    if _is_placeholder_key(config.api_key):
        logger.warning("主 LLM API Key 未配置，跳过主模型初始化")
        return None
    return get_chat_model(config)


def get_fallback_model() -> Optional[BaseChatModel]:
    """
    获取备用 LLM 模型实例（Ollama 本地）

    说明：从全局配置中读取备用提供商参数，创建 ChatOpenAI 实例。
         Ollama 使用固定 api_key="ollama"，始终可用（只要 Ollama 服务在运行）。

    返回：
        BaseChatModel 实例，或 None（未配置时）
    """
    config = settings.fallback_llm_config
    if _is_placeholder_key(config.api_key) and config.provider != "ollama":
        logger.warning("备用 LLM API Key 未配置，跳过备用模型初始化")
        return None
    return get_chat_model(config)


async def call_with_retry(
    model: BaseChatModel,
    messages: list[BaseMessage],
    max_retries: int = 3,
) -> str:
    """
    带指数退避重试的 LLM 调用

    说明：调用 LLM 模型生成回复，失败时按指数退避策略重试。
         退避间隔：1s → 2s → 4s（2^attempt 秒）。
         类似 Java 版 AiChatService.callProvider() 中的重试逻辑。

    参数：
        model: LangChain 聊天模型实例
        messages: 消息列表（SystemMessage、HumanMessage、AIMessage 等）
        max_retries: 最大重试次数，默认 3 次

    返回：
        LLM 生成的文本回复

    异常：
        最后一次重试仍失败时，抛出原始异常
    """
    last_exception: Optional[Exception] = None

    for attempt in range(max_retries):
        try:
            response = await model.ainvoke(messages)
            content = response.content
            if isinstance(content, str) and content.strip():
                return content.strip()
            raise ValueError("LLM 响应内容为空")
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                wait_seconds = 2**attempt  # 1s, 2s, 4s
                logger.warning(
                    f"LLM 调用失败（第 {attempt + 1} 次），{wait_seconds}s 后重试: {e}"
                )
                await asyncio.sleep(wait_seconds)
            else:
                logger.error(f"LLM 调用失败（已达最大重试次数 {max_retries}）: {e}")

    raise last_exception  # type: ignore[misc]


def _is_placeholder_key(api_key: str) -> bool:
    """检查 API Key 是否为占位符（未真正配置）"""
    placeholders = {
        "your_dashscope_api_key_here",
        "your_api_key_here",
        "sk-xxx",
        "",
    }
    return api_key.strip() in placeholders
