"""identity 模块路由：认证（登录、登出、当前用户、修改密码）与用户管理。"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response, status

from app.core.config import get_settings
from app.core.deps import RedisDep, SessionDep
from app.core.schemas import Envelope, Page
from app.core.security import SESSION_COOKIE
from app.identity import service
from app.identity.deps import AdminUser, CurrentUser
from app.identity.schemas import (
    ChangePasswordIn,
    LoginIn,
    ResetPasswordIn,
    ResetPasswordOut,
    SessionUser,
    UserCreateIn,
    UserCreateOut,
    UserOut,
    UserUpdateIn,
)

auth_router = APIRouter(prefix="/api/auth", tags=["auth"])
users_router = APIRouter(prefix="/api/users", tags=["users"])


@auth_router.post("/login", status_code=status.HTTP_200_OK)
async def login(
    data: LoginIn,
    response: Response,
    db: SessionDep,
    redis: RedisDep,
) -> Envelope[SessionUser]:
    user, sid = await service.login(db, redis, data.username, data.password)
    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        sid,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
        path="/",
    )
    return Envelope.ok(SessionUser.model_validate(user))


@auth_router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    user: CurrentUser,
    redis: RedisDep,
) -> Envelope[None]:
    sid = request.state.session_id
    await service.logout(redis, sid, user.id)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return Envelope.ok(None)


@auth_router.get("/me")
async def me(user: CurrentUser) -> Envelope[SessionUser]:
    return Envelope.ok(SessionUser.model_validate(user))


@auth_router.post("/change-password")
async def change_password(
    data: ChangePasswordIn,
    response: Response,
    user: CurrentUser,
    db: SessionDep,
    redis: RedisDep,
) -> Envelope[None]:
    await service.change_password(db, redis, user, data.old_password, data.new_password)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return Envelope.ok(None)


@users_router.get("")
async def list_users(
    db: SessionDep,
    _admin: AdminUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100), Query(alias="pageSize")] = 20,
    order_by: str = Query(default="createdAt", alias="orderBy"),
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
) -> Envelope[Page[UserOut]]:
    users, total = await service.list_users(db, page, page_size, order_by, order)
    return Envelope.ok(
        Page(
            items=[UserOut.model_validate(u) for u in users],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@users_router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreateIn,
    db: SessionDep,
    _admin: AdminUser,
) -> Envelope[UserCreateOut]:
    user, initial = await service.create_user(db, data)
    out = UserCreateOut.model_validate(user)
    out.initial_password = None if data.password else initial
    return Envelope.ok(out)


@users_router.post("/{user_id}/reset-password")
async def reset_password(
    user_id: uuid.UUID,
    data: ResetPasswordIn,
    db: SessionDep,
    redis: RedisDep,
    _admin: AdminUser,
) -> Envelope[ResetPasswordOut]:
    _user, initial = await service.reset_password(db, redis, user_id, data.new_password)
    return Envelope.ok(ResetPasswordOut(initial_password=initial))


@users_router.patch("/{user_id}")
async def update_user(
    user_id: uuid.UUID,
    data: UserUpdateIn,
    db: SessionDep,
    admin: AdminUser,
) -> Envelope[UserOut]:
    user = await service.update_user(db, admin, user_id, data)
    return Envelope.ok(UserOut.model_validate(user))
