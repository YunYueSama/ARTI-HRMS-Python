"""
模块数据范围模型（ModuleScopeRule、ModuleScopeDetail）

说明：映射 MySQL hrms_db 中的 module_scope_rule 和 module_scope_detail 表。
     - ModuleScopeRule：定义各业务模块的默认数据范围规则
     - ModuleScopeDetail：定义各身份标签在各模块中的具体数据范围
     注意：ModuleScopeRule 的主键为 module_code（字符串类型），非自增整数。
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ModuleScopeRule(Base):
    """模块数据范围规则表 ORM 模型，对应 MySQL module_scope_rule 表"""

    __tablename__ = "module_scope_rule"

    # 模块编码（主键，字符串类型）
    module_code: Mapped[str] = mapped_column(String(50), primary_key=True)
    # 模块名称
    module_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # 默认数据范围（self/dept/all 等）
    default_scope: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 创建时间
    create_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 更新时间
    update_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ModuleScopeDetail(Base):
    """模块数据范围明细表 ORM 模型，对应 MySQL module_scope_detail 表"""

    __tablename__ = "module_scope_detail"

    # 明细ID（主键，自增）
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 模块编码
    module_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 身份标签编码
    tag_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 数据范围（self/dept/all 等）
    scope: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 创建时间
    create_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 更新时间
    update_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
