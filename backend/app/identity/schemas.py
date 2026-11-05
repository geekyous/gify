"""identity 模块请求与响应模型：认证、用户管理。"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.core.schemas import CamelModel

Role = Literal["admin", "builder", "user"]


class LoginIn(CamelModel):
    username: str
    password: str


class ChangePasswordIn(CamelModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=128)


class SessionUser(CamelModel):
    """当前登录用户信息。"""

    id: uuid.UUID
    username: str
    display_name: str | None
    role: str
    must_change_password: bool


class UserOut(CamelModel):
    id: uuid.UUID
    username: str
    display_name: str | None
    role: str
    enabled: bool
    must_change_password: bool
    created_at: datetime


class UserCreateOut(UserOut):
    """创建响应：未指定口令时返回随机初始口令，仅此一次。"""

    initial_password: str | None = None


class UserCreateIn(CamelModel):
    username: str = Field(min_length=2, max_length=50)
    display_name: str | None = Field(default=None, max_length=50)
    role: Role
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateIn(CamelModel):
    display_name: str | None = Field(default=None, max_length=50)
    role: Role | None = None
    enabled: bool | None = None


class ResetPasswordIn(CamelModel):
    new_password: str | None = Field(default=None, min_length=8, max_length=128)


class ResetPasswordOut(CamelModel):
    """重置或创建时生成的初始口令，仅返回一次。"""

    initial_password: str
