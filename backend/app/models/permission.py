"""
权限模型（Permission）

说明：映射 MySQL hrms_db 中的 permission 表，存储系统权限（菜单/按钮）信息。
     支持 parent_id 实现树形层级结构，包含前端路由路径和图标。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Permission(Base):
    """权限表 ORM 模型，对应 MySQL permission 表"""

    __tablename__ = "permission"

    # 权限ID（主键，自增）
    perm_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 权限名称
    perm_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # 权限编码（唯一标识）
    perm_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # 权限类型（menu/button 等）
    perm_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # 父级权限ID（树形结构）
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 前端路由路径
    path: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    # 图标名称
    icon: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # 排序序号
    sort_order: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 创建时间
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
