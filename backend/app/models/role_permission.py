"""
角色-权限关联模型（RolePermission）

说明：映射 MySQL hrms_db 中的 role_permission 表，
     实现角色与权限的多对多关联关系。
"""

from typing import Optional

from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RolePermission(Base):
    """角色-权限关联表 ORM 模型，对应 MySQL role_permission 表"""

    __tablename__ = "role_permission"

    # 关联记录ID（主键，自增）
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 角色ID
    role_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 权限ID
    perm_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
