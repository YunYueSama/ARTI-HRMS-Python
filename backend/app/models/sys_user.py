"""
系统用户模型（SysUser）

说明：映射 MySQL hrms_db 中的 sys_user 表，存储系统登录用户信息。
     通过 emp_id 关联员工表，通过 role_id 关联角色表。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SysUser(Base):
    """系统用户表 ORM 模型，对应 MySQL sys_user 表"""

    __tablename__ = "sys_user"

    # 用户ID（主键，自增）
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 关联员工ID
    emp_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 登录用户名
    username: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # 登录密码（加密存储）
    password: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    # 角色ID
    role_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 账号状态（active/disabled 等）
    status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # 最后登录时间
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # 创建时间
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # 更新时间
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
