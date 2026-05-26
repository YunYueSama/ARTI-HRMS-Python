"""
人设配置模型（models/persona.py）

说明：定义 AI 助手人设（Persona）的数据库模型，支持动态切换人设。
     人设内容以 TEXT 字段存储完整的系统提示词，通过 is_active 标记当前激活的人设。
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PersonaConfig(Base):
    """AI 助手人设配置"""

    __tablename__ = "persona_config"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    create_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    update_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
