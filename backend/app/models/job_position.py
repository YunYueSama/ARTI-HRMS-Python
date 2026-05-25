"""
职位模型（JobPosition）

说明：映射 MySQL hrms_db 中的 job_position 表，存储职位信息。
     每个职位关联一个部门。
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class JobPosition(Base):
    """职位表 ORM 模型，对应 MySQL job_position 表"""

    __tablename__ = "job_position"

    # 职位ID（主键，自增）
    position_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 职位名称
    position_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # 职位描述
    position_desc: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 所属部门ID
    dept_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 创建时间
    create_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 更新时间
    update_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
