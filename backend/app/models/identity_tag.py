"""
身份标签模型（IdentityTag）

说明：映射 MySQL hrms_db 中的 identity_tag 表，存储身份标签信息。
     身份标签用于标识员工的身份类别（如：普通员工、部门经理、HR等），
     在审批流程和数据权限控制中使用。
     注意：主键为 tag_code（字符串类型），非自增整数。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class IdentityTag(Base):
    """身份标签表 ORM 模型，对应 MySQL identity_tag 表"""

    __tablename__ = "identity_tag"

    # 标签编码（主键，字符串类型）
    tag_code: Mapped[str] = mapped_column(String(50), primary_key=True)
    # 标签名称
    tag_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # 标签描述
    tag_desc: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # 创建时间
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
