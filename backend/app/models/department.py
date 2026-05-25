"""
部门模型（Department）

说明：映射 MySQL hrms_db 中的 department 表，存储部门信息。
     支持 parent_id 实现树形层级结构。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Department(Base):
    """部门表 ORM 模型，对应 MySQL department 表"""

    __tablename__ = "department"

    # 部门ID（主键，自增）
    dept_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 部门名称
    dept_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # 部门描述
    dept_desc: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # 上级部门ID（支持树形结构）
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 创建时间
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # 更新时间
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
