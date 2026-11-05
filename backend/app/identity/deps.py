"""identity 模块依赖：当前用户与角色检查。"""

from typing import Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import errors, session_store
from app.core.deps import get_redis
from app.core.security import SESSION_COOKIE
from app.db import provide_session
from app.identity.models import User


async def get_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(provide_session)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> User:
    """解析会话 cookie 并加载用户；禁用用户即使会话残留也拒绝。"""
    sid = request.cookies.get(SESSION_COOKIE)
    if not sid:
        raise errors.err(errors.AUTH_NOT_AUTHENTICATED)
    user_id = await session_store.load_session(redis, sid)
    if user_id is None:
        raise errors.err(errors.AUTH_NOT_AUTHENTICATED)
    user = await db.get(User, user_id)
    if user is None or not user.enabled:
        await session_store.destroy_user_sessions(redis, user_id)
        raise errors.err(errors.AUTH_NOT_AUTHENTICATED)
    request.state.session_id = sid
    return user


async def require_admin(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    if user.role != "admin":
        raise errors.err(errors.AUTH_FORBIDDEN)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_admin)]
