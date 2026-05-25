"""
配置管理模块（core/config.py）

说明：使用 pydantic-settings 从 .env 文件加载所有配置项。
     .env 文件优先级高于系统环境变量。
     API Key 如果 .env 未配置，才回退到系统环境变量。

用法：
    from app.core.config import settings
    print(settings.MYSQL_HOST)
"""

import os

from pydantic import Field
from pydantic_settings import BaseSettings, DotEnvSettingsSource, PydanticBaseSettingsSource, SettingsConfigDict


class LLMProviderConfig:
    """
    LLM 提供商配置（嵌套模型）

    说明：每个 LLM 提供商（如阿里云百炼、Ollama）都有独立的连接参数。
         通过此结构统一管理多个提供商的配置。
    """

    def __init__(
        self,
        provider: str,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ):
        self.provider = provider  # 提供商标识（dashscope/ollama）
        self.base_url = base_url  # API 基础 URL
        self.api_key = api_key  # API 密钥
        self.model = model  # 模型名称
        self.temperature = temperature  # 生成温度（0-1）
        self.max_tokens = max_tokens  # 最大输出 Token 数


class Settings(BaseSettings):
    """
    应用全局配置类

    说明：继承 BaseSettings，自动从环境变量和 .env 文件加载配置。
         所有字段名对应环境变量名（大写），支持默认值。
         类似 Spring 的 @ConfigurationProperties。
    """

    # 配置加载方式：仅从 .env 文件读取（不从系统环境变量覆盖）
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """
        自定义配置加载源：仅从 .env 文件读取，不读取系统环境变量。

        说明：pydantic-settings 默认会同时读取 .env 和系统环境变量，
             系统环境变量会覆盖 .env 中的同名值。
             此处禁用系统环境变量读取，确保 .env 文件优先。
             需要系统环境变量回退的字段（如 API Key），在属性中手动处理。
        """
        return (DotEnvSettingsSource(settings_cls, env_file=".env"),)

    # ========================================
    # PostgreSQL 数据库配置（统一主数据库 + pgvector）
    # 业务数据 + AI 聊天 + RAG 向量 + LLM 追踪全部在同一个 PG 库
    # ========================================
    # 用于 RAG 文档向量存储和语义检索
    # ========================================
    PGVECTOR_HOST: str = Field(default="localhost", description="PostgreSQL 主机地址")
    PGVECTOR_PORT: int = Field(default=5432, description="PostgreSQL 端口")
    PGVECTOR_USER: str = Field(default="postgres", description="PostgreSQL 用户名")
    PGVECTOR_PASSWORD: str = Field(default="postgres", description="PostgreSQL 密码")
    PGVECTOR_DATABASE: str = Field(default="hrms_vector", description="PostgreSQL 数据库名")

    @property
    def pgvector_url(self) -> str:
        """构建 PostgreSQL 异步连接 URL（使用 asyncpg 驱动）"""
        return (
            f"postgresql+asyncpg://{self.PGVECTOR_USER}:{self.PGVECTOR_PASSWORD}"
            f"@{self.PGVECTOR_HOST}:{self.PGVECTOR_PORT}/{self.PGVECTOR_DATABASE}"
        )

    # ========================================
    # Redis 缓存配置
    # 用于会话缓存、Token 计数缓存、配置缓存
    # ========================================
    REDIS_HOST: str = Field(default="localhost", description="Redis 主机地址")
    REDIS_PORT: int = Field(default=6379, description="Redis 端口")
    REDIS_PASSWORD: str = Field(default="", description="Redis 密码")
    REDIS_DB: int = Field(default=0, description="Redis 数据库编号")

    @property
    def redis_url(self) -> str:
        """构建 Redis 连接 URL"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # ========================================
    # JWT 认证配置
    # 用于用户登录后的 Token 生成和校验
    # ========================================
    JWT_SECRET_KEY: str = Field(
        default="your-super-secret-key-change-in-production",
        description="JWT 签名密钥（生产环境必须修改为强随机字符串）",
    )
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT 签名算法")
    JWT_EXPIRE_MINUTES: int = Field(default=1440, description="JWT Token 过期时间（分钟）")

    # ========================================
    # LLM 主提供商配置（阿里云百炼 DashScope）
    # 用于 AI 聊天、Agent 意图识别、计划生成
    # 支持从 LLM_PRIMARY_API_KEY 或 AI_CHAT_PROVIDER_OPENAI_API_KEY（Java版兼容）读取
    # ========================================
    LLM_PRIMARY_PROVIDER: str = Field(default="dashscope", description="主 LLM 提供商标识")
    LLM_PRIMARY_BASE_URL: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1", description="主 LLM API 基础 URL"
    )
    LLM_PRIMARY_API_KEY: str = Field(default="your_dashscope_api_key_here", description="主 LLM API 密钥")
    # 兼容 Java 版环境变量名（如果 LLM_PRIMARY_API_KEY 未配置，从这里读取）
    AI_CHAT_PROVIDER_OPENAI_API_KEY: str = Field(default="", description="Java版兼容API密钥")
    LLM_PRIMARY_MODEL: str = Field(default="qwen-plus", description="主 LLM 模型名称")
    LLM_PRIMARY_TEMPERATURE: float = Field(default=0.7, description="主 LLM 生成温度")
    LLM_PRIMARY_MAX_TOKENS: int = Field(default=2048, description="主 LLM 最大输出 Token 数")

    # ========================================
    # LLM 备用提供商配置（Ollama 本地）
    # 主提供商不可用时自动回退到本地模型
    # ========================================
    LLM_FALLBACK_PROVIDER: str = Field(default="ollama", description="备用 LLM 提供商标识")
    LLM_FALLBACK_BASE_URL: str = Field(default="http://127.0.0.1:11434/v1", description="备用 LLM API 地址")
    LLM_FALLBACK_API_KEY: str = Field(default="ollama", description="备用 LLM API 密钥")
    LLM_FALLBACK_MODEL: str = Field(default="qwen3:4b", description="备用 LLM 模型名称")
    LLM_FALLBACK_TEMPERATURE: float = Field(default=0.7, description="备用 LLM 生成温度")

    @property
    def primary_llm_config(self) -> LLMProviderConfig:
        """获取主 LLM 提供商配置对象

        读取优先级：
            1. .env 中的 LLM_PRIMARY_API_KEY
            2. 系统环境变量 AI_CHAT_PROVIDER_OPENAI_API_KEY（兼容 Java 版）
            3. 系统环境变量 LLM_PRIMARY_API_KEY
        """
        api_key = self.LLM_PRIMARY_API_KEY
        # .env 未配置或为占位符时，才回退到系统环境变量
        if not api_key or api_key in ("your_dashscope_api_key_here",):
            api_key = (
                os.environ.get("AI_CHAT_PROVIDER_OPENAI_API_KEY", "")
                or os.environ.get("LLM_PRIMARY_API_KEY", "")
                or api_key
            )
        return LLMProviderConfig(
            provider=self.LLM_PRIMARY_PROVIDER,
            base_url=self.LLM_PRIMARY_BASE_URL,
            api_key=api_key,
            model=self.LLM_PRIMARY_MODEL,
            temperature=self.LLM_PRIMARY_TEMPERATURE,
            max_tokens=self.LLM_PRIMARY_MAX_TOKENS,
        )

    @property
    def fallback_llm_config(self) -> LLMProviderConfig:
        """获取备用 LLM 提供商配置对象"""
        return LLMProviderConfig(
            provider=self.LLM_FALLBACK_PROVIDER,
            base_url=self.LLM_FALLBACK_BASE_URL,
            api_key=self.LLM_FALLBACK_API_KEY,
            model=self.LLM_FALLBACK_MODEL,
            temperature=self.LLM_FALLBACK_TEMPERATURE,
        )

    # ========================================
    # Embedding 向量嵌入配置
    # 用于 RAG 文档分块的向量化
    # ========================================
    EMBEDDING_BASE_URL: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1", description="嵌入模型 API 地址"
    )
    EMBEDDING_API_KEY: str = Field(default="your_dashscope_api_key_here", description="嵌入模型 API 密钥")
    EMBEDDING_MODEL: str = Field(default="text-embedding-v3", description="嵌入模型名称")
    EMBEDDING_DIMENSIONS: int = Field(default=1536, description="向量维度")

    @property
    def embedding_api_key(self) -> str:
        """获取 Embedding API Key

        读取优先级：
            1. .env 中的 EMBEDDING_API_KEY
            2. 系统环境变量 EMBEDDING_API_KEY
            3. 主 LLM 的 API Key
        """
        key = self.EMBEDDING_API_KEY
        if not key or key in ("your_dashscope_api_key_here",):
            key = os.environ.get("EMBEDDING_API_KEY", "") or key
        if not key or key in ("your_dashscope_api_key_here",):
            return self.primary_llm_config.api_key
        return key

    # ========================================
    # RAG 检索增强生成配置
    # 控制文档分块策略和检索参数
    # ========================================
    RAG_CHUNK_SIZE: int = Field(default=512, description="文档分块大小（Token 数）")
    RAG_CHUNK_OVERLAP: int = Field(default=50, description="分块重叠大小（Token 数）")
    RAG_TOP_K: int = Field(default=5, description="语义检索返回的最相关分块数量")

    # ========================================
    # Langfuse 可观测性配置
    # 用于追踪所有 LLM 调用链路、Token 统计和费用估算
    # ========================================
    LANGFUSE_PUBLIC_KEY: str = Field(default="your_langfuse_public_key", description="Langfuse 公钥")
    LANGFUSE_SECRET_KEY: str = Field(default="your_langfuse_secret_key", description="Langfuse 私钥")
    LANGFUSE_HOST: str = Field(default="https://cloud.langfuse.com", description="Langfuse 服务地址")
    SLOW_RESPONSE_THRESHOLD: float = Field(default=10.0, description="慢响应阈值（秒）")

    # ========================================
    # Neo4j 知识图谱配置
    # 用于 GraphRAG 实体关系存储和多跳查询
    # ========================================
    NEO4J_URI: str = Field(default="bolt://localhost:7687", description="Neo4j 连接地址")
    NEO4J_USER: str = Field(default="neo4j", description="Neo4j 用户名")
    NEO4J_PASSWORD: str = Field(default="neo4j_password", description="Neo4j 密码")

    # ========================================
    # 高德地图天气 API 配置
    # 用于 AI 助手天气查询功能
    # ========================================
    WEATHER_AMAP_KEY: str = Field(default="your_amap_key_here", description="高德地图 Web 服务 API Key")

    # ========================================
    # Whisper 语音识别配置
    # 用于多模态语音输入转文字
    # ========================================
    WHISPER_MODEL: str = Field(default="large-v3", description="Whisper 模型大小")
    WHISPER_DEVICE: str = Field(default="cpu", description="运行设备（cpu/cuda）")

    # ========================================
    # TTS 文字转语音配置
    # ========================================
    TTS_PROVIDER: str = Field(default="edge", description="TTS 提供商")
    TTS_VOICE: str = Field(default="zh-CN-XiaoxiaoNeural", description="TTS 语音角色")

    # ========================================
    # Token 管理配置
    # 控制上下文窗口使用策略和 Token 预算分配
    # ========================================
    TOKEN_CONTEXT_WINDOW: int = Field(default=8192, description="模型上下文窗口大小（Token 数）")
    TOKEN_WARNING_THRESHOLD: float = Field(default=0.8, description="上下文窗口使用率警告阈值")
    TOKEN_MAX_INPUT: int = Field(default=4096, description="单条用户消息最大 Token 数")

    # ========================================
    # 应用运行配置
    # ========================================
    APP_ENV: str = Field(default="development", description="运行环境")
    APP_DEBUG: bool = Field(default=True, description="调试模式")
    APP_HOST: str = Field(default="0.0.0.0", description="监听地址")
    APP_PORT: int = Field(default=8000, description="监听端口")
    CORS_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:5173", description="允许的跨域来源（逗号分隔）"
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """将逗号分隔的 CORS 来源字符串转为列表"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


# ============================================================
# 导出单例配置实例
# 说明：整个应用共享同一个 Settings 实例，避免重复加载 .env 文件
# 类似 Spring 的 @Configuration Bean
# ============================================================
settings = Settings()


# ============================================================
# 运行时配置覆盖（内存级别）
#
# 说明：通过 PUT /api/config/model 动态修改的模型参数。
#      应用重启后恢复为 .env 中的默认值。
# ============================================================
_runtime_overrides: dict = {}


def get_runtime_overrides() -> dict:
    """获取运行时配置覆盖字典"""
    return dict(_runtime_overrides)


def update_runtime_overrides(data: dict) -> None:
    """更新运行时配置覆盖"""
    _runtime_overrides.update(data)
