"""
人设配置 Schema（schemas/persona.py）

说明：定义人设配置的请求和响应模型，用于 API 参数校验和序列化。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PersonaCreate(BaseModel):
    """创建人设请求"""

    name: str = Field(min_length=1, max_length=100, description="人设名称")
    content: str = Field(min_length=1, description="人设提示词内容")
    description: str | None = Field(default=None, max_length=255, description="人设描述")


class PersonaUpdate(BaseModel):
    """更新人设请求"""

    name: str | None = Field(default=None, min_length=1, max_length=100, description="人设名称")
    content: str | None = Field(default=None, min_length=1, description="人设提示词内容")
    description: str | None = Field(default=None, max_length=255, description="人设描述")


class PersonaResponse(BaseModel):
    """人设响应"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    content: str
    is_active: bool
    description: str | None
    create_time: datetime
    update_time: datetime
