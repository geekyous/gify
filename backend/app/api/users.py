"""用户管理路由（管理员，FR-01 功能要求 5）。"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.deps import AdminUser, RedisDep, SessionDep
from app.schemas.base import Envelope, Page
from app.schemas.user import (
    ResetPasswordIn,
    ResetPasswordOut,
    UserCreateIn,
    UserCreateOut,
    UserOut,
    UserUpdateIn,
)
from app.services import user_service

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("")
async def list_users(
    db: SessionDep,
    _admin: AdminUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100), Query(alias="pageSize")] = 20,
    order_by: str = Query(default="createdAt", alias="orderBy"),
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
) -> Envelope[Page[UserOut]]:
    users, total = await user_service.list_users(db, page, page_size, order_by, order)
    return Envelope.ok(
        Page(
            items=[UserOut.model_validate(u) for u in users],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreateIn,
    db: SessionDep,
    _admin: AdminUser,
) -> Envelope[UserCreateOut]:
    user, initial = await user_service.create_user(db, data)
    out = UserCreateOut.model_validate(user)
    out.initial_password = None if data.password else initial
    return Envelope.ok(out)


@router.post("/{user_id}/reset-password")
async def reset_password(
    user_id: uuid.UUID,
    data: ResetPasswordIn,
    db: SessionDep,
    redis: RedisDep,
    _admin: AdminUser,
) -> Envelope[ResetPasswordOut]:
    _user, initial = await user_service.reset_password(
        db, redis, user_id, data.new_password
    )
    return Envelope.ok(ResetPasswordOut(initial_password=initial))


@router.patch("/{user_id}")
async def update_user(
    user_id: uuid.UUID,
    data: UserUpdateIn,
    db: SessionDep,
    admin: AdminUser,
) -> Envelope[UserOut]:
    user = await user_service.update_user(db, admin, user_id, data)
    return Envelope.ok(UserOut.model_validate(user))
