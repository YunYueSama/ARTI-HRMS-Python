"""
模型配置路由（routers/config.py）

说明：定义模型参数运行时配置的 API 端点。
     允许在运行时动态调整 LLM 模型参数（温度、top_p、最大输出 Token 等），
     无需重启服务。

端点列表：
    GET  /api/config/model  → 获取当前模型配置
    PUT  /api/config/model  → 更新模型参数

Java 对应关系：
    无直接对应（Java 版通过 application.properties 静态配置）

设计说明：
    - 运行时配置存储在 app.core.config._runtime_overrides 中
    - 重启后恢复为 .env 中的默认值
    - 后续可扩展为持久化到 Redis 或数据库
    - 参数校验：Temperature 0-2, top_p 0-1, max_tokens 1-32768
"""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.config import get_runtime_overrides, settings, update_runtime_overrides
from app.core.dependencies import TokenPayload, get_current_user
from app.schemas.common import ApiResponse, fail, ok

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_effective_config() -> dict:
    """
    获取当前生效的模型配置

    说明：合并 .env 默认配置和运行时修改的配置。
         运行时配置优先级高于默认配置。
    """
    rc = get_runtime_overrides()
    return {
        "model_name": rc.get("model_name", settings.LLM_PRIMARY_MODEL),
        "context_window_size": rc.get("context_window_size", settings.TOKEN_CONTEXT_WINDOW),
        "temperature": rc.get("temperature", settings.LLM_PRIMARY_TEMPERATURE),
        "top_p": rc.get("top_p", 0.9),
        "max_output_tokens": rc.get("max_output_tokens", settings.LLM_PRIMARY_MAX_TOKENS),
        "provider": rc.get("provider", settings.LLM_PRIMARY_PROVIDER),
        "base_url": rc.get("base_url", settings.LLM_PRIMARY_BASE_URL),
        "api_key": rc.get("api_key", ""),
    }


# ============================================================
# 请求/响应模型
# ============================================================


class ModelConfigResponse(BaseModel):
    """模型配置响应"""

    model_name: str = Field(description="当前使用的模型名称")
    context_window_size: int = Field(description="上下文窗口大小（Token 数）")
    temperature: float = Field(description="生成温度（0-2）")
    top_p: float = Field(description="Top-P 采样参数（0-1）")
    max_output_tokens: int = Field(description="最大输出 Token 数")
    provider: str = Field(description="LLM 提供商")
    base_url: str = Field(description="API 基础 URL")
    api_key: str = Field(default="", description="API 密钥")


class ModelConfigUpdateRequest(BaseModel):
    """
    模型配置更新请求

    说明：所有字段均为可选，仅更新提供的字段。
         参数校验规则：
         - temperature: 0 ~ 2（0 = 确定性输出，2 = 最大随机性）
         - top_p: 0 ~ 1（核采样参数）
         - max_output_tokens: 1 ~ 32768
    """

    model_name: str | None = Field(default=None, description="模型名称")
    context_window_size: int | None = Field(default=None, ge=1024, le=131072, description="上下文窗口大小")
    temperature: float | None = Field(default=None, ge=0.0, le=2.0, description="生成温度（0-2）")
    top_p: float | None = Field(default=None, ge=0.0, le=1.0, description="Top-P 采样参数（0-1）")
    max_output_tokens: int | None = Field(default=None, ge=1, le=32768, description="最大输出 Token 数")
    provider: str | None = Field(default=None, description="LLM 提供商")
    base_url: str | None = Field(default=None, description="API 基础 URL")
    api_key: str | None = Field(default=None, description="API 密钥")


# ============================================================
# API 端点
# ============================================================


@router.get("/model", summary="获取当前模型配置")
async def get_model_config(
    user: TokenPayload = Depends(get_current_user),
) -> ApiResponse:
    """
    获取当前模型配置

    说明：返回当前生效的 LLM 模型参数配置。
         包含模型名称、上下文窗口大小、温度、top_p 和最大输出 Token 数。

    返回：
        {
            "success": true,
            "data": {
                "model_name": "qwen-plus",
                "context_window_size": 8192,
                "temperature": 0.7,
                "top_p": 0.9,
                "max_output_tokens": 2048,
                "provider": "dashscope",
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"
            }
        }
    """
    config = _get_effective_config()
    return ok(data=config, message="获取模型配置成功")


@router.put("/model", summary="更新模型参数")
async def update_model_config(
    request: ModelConfigUpdateRequest,
    user: TokenPayload = Depends(get_current_user),
) -> ApiResponse:
    """
    更新模型参数（运行时）

    说明：动态修改 LLM 模型参数，无需重启服务。
         仅更新请求中提供的字段，未提供的字段保持不变。
         修改仅在内存中生效，重启后恢复默认值。

    参数校验：
        - temperature: 0 ~ 2
        - top_p: 0 ~ 1
        - max_output_tokens: 1 ~ 32768
        - context_window_size: 1024 ~ 131072

    请求体：
        {
            "temperature": 0.5,
            "max_output_tokens": 4096
        }

    返回：
        {
            "success": true,
            "data": { ... 更新后的完整配置 ... },
            "message": "模型配置已更新"
        }
    """
    # 更新运行时配置（仅更新非 None 字段）
    update_data = request.model_dump(exclude_none=True)

    if not update_data:
        return fail(message="未提供任何需要更新的参数")

    for key, value in update_data.items():
        update_runtime_overrides({key: value})

    logger.info(f"模型配置已更新: {update_data} (by user_id={user.user_id})")

    # 返回更新后的完整配置
    config = _get_effective_config()
    return ok(data=config, message="模型配置已更新")
