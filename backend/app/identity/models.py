"""用户表 ORM 模型。"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("username", name="uk_users_username"),
        CheckConstraint("role IN ('admin', 'builder', 'user')", name="ck_users_role"),
        {"comment": "平台账号（开号制，由管理员创建）"},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=func.gen_random_uuid(),
        comment="用户 ID",
    )
    username: Mapped[str] = mapped_column(String(50), comment="登录用户名")
    display_name: Mapped[str | None] = mapped_column(
        String(50), comment="显示名（选填）"
    )
    password_hash: Mapped[str] = mapped_column(comment="argon2id 哈希")
    role: Mapped[str] = mapped_column(
        String(10), comment="角色：admin / builder / user"
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        comment="禁用后无法登录且会话即时失效",
    )
    must_change_password: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        comment="首次登录或重置密码后须修改密码",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        comment="最后更新时间",
    )
