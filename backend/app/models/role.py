"""
角色模型（Role）

说明：映射 MySQL hrms_db 中的 role 表，存储系统角色信息。
     角色通过 role_permission 关联表与权限建立多对多关系。
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Role(Base):
    """角色表 ORM 模型，对应 MySQL role 表"""

    __tablename__ = "role"

    # 角色ID（主键，自增）
    role_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 角色名称
    role_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 角色编码（唯一标识）
    role_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 角色描述
    role_desc: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 创建时间
    create_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
