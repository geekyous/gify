"""认证路由：登录、登出、当前用户、修改密码。"""

from fastapi import APIRouter, Request, Response, status

from app.core.config import get_settings
from app.core.deps import CurrentUser, RedisDep, SessionDep
from app.core.security import SESSION_COOKIE
from app.schemas.auth import ChangePasswordIn, LoginIn, SessionUser
from app.schemas.base import Envelope
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", status_code=status.HTTP_200_OK)
async def login(
    data: LoginIn,
    response: Response,
    db: SessionDep,
    redis: RedisDep,
) -> Envelope[SessionUser]:
    user, sid = await auth_service.login(db, redis, data.username, data.password)
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


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    user: CurrentUser,
    redis: RedisDep,
) -> Envelope[None]:
    sid = request.state.session_id
    await auth_service.logout(redis, sid, user.id)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return Envelope.ok(None)


@router.get("/me")
async def me(user: CurrentUser) -> Envelope[SessionUser]:
    return Envelope.ok(SessionUser.model_validate(user))


@router.post("/change-password")
async def change_password(
    data: ChangePasswordIn,
    response: Response,
    user: CurrentUser,
    db: SessionDep,
    redis: RedisDep,
) -> Envelope[None]:
    await auth_service.change_password(
        db, redis, user, data.old_password, data.new_password
    )
    response.delete_cookie(SESSION_COOKIE, path="/")
    return Envelope.ok(None)
