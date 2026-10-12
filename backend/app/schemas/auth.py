"""认证相关请求 / 响应模型。"""

import uuid

from pydantic import Field

from app.schemas.base import CamelModel


class LoginIn(CamelModel):
    username: str
    password: str


class ChangePasswordIn(CamelModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=128)


class SessionUser(CamelModel):
    """当前登录用户信息（GET /api/auth/me）。"""

    id: uuid.UUID
    username: str
    display_name: str | None
    role: str
    must_change_password: bool
