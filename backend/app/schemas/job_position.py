"""
职位相关 Schema（schemas/job_position.py）

说明：定义职位模块的请求/响应模型，包括创建、更新和响应。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class JobPositionCreate(BaseModel):
    """职位创建请求模型"""

    model_config = ConfigDict(extra="ignore")

    position_name: str = Field(min_length=1, description="职位名称")
    position_desc: str | None = Field(default=None, description="职位描述")
    dept_id: int | None = Field(default=None, description="所属部门ID")


class JobPositionUpdate(BaseModel):
    """职位更新请求模型（所有字段可选）"""

    model_config = ConfigDict(extra="ignore")

    position_name: str | None = Field(default=None, description="职位名称")
    position_desc: str | None = Field(default=None, description="职位描述")
    dept_id: int | None = Field(default=None, description="所属部门ID")


class JobPositionResponse(BaseModel):
    """职位响应模型（对应 ORM JobPosition 模型）"""

    model_config = ConfigDict(from_attributes=True)

    position_id: int = Field(description="职位ID")
    position_name: str | None = Field(default=None, description="职位名称")
    position_desc: str | None = Field(default=None, description="职位描述")
    dept_id: int | None = Field(default=None, description="所属部门ID")
    create_time: datetime | None = Field(default=None, description="创建时间")
    update_time: datetime | None = Field(default=None, description="更新时间")
