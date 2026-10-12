"""认证业务逻辑：登录、登出、修改密码（FR-01 功能要求 1–4）。"""

import uuid

from redis.asyncio import Redis
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import errors, security, session_store
from app.core.logging import get_logger
from app.models.user import User
from app.services import user_service

logger = get_logger(__name__)


async def login(
    db: AsyncSession, redis: Redis, username: str, password: str
) -> tuple[User, str]:
    """校验口令并创建会话。锁定检查在最前，不泄露口令正误。"""
    if await session_store.is_login_locked(redis, username):
        logger.info(
            "登录拒绝（锁定中）",
            extra_fields={"event": "auth.login_locked", "username": username},
        )
        raise errors.err(errors.AUTH_LOGIN_LOCKED)

    user = await user_service.get_by_username(db, username)
    if user is None or not security.verify_password(password, user.password_hash):
        attempts = await session_store.register_login_failure(redis, username)
        logger.info(
            "登录失败",
            extra_fields={
                "event": "auth.login_failed",
                "username": username,
                "attempts": attempts,
            },
        )
        raise errors.err(errors.AUTH_INVALID_CREDENTIALS)

    if not user.enabled:
        logger.info(
            "登录拒绝（已禁用）",
            extra_fields={"event": "auth.login_disabled", "username": username},
        )
        raise errors.err(errors.AUTH_USER_DISABLED)

    await session_store.clear_login_failures(redis, username)
    sid = await session_store.create_session(redis, user.id)
    logger.info(
        "登录成功",
        extra_fields={
            "event": "auth.login",
            "userId": str(user.id),
            "username": username,
        },
    )
    return user, sid


async def logout(redis: Redis, sid: str, user_id: uuid.UUID) -> None:
    await session_store.destroy_session(redis, sid, user_id)
    logger.info("登出", extra_fields={"event": "auth.logout", "userId": str(user_id)})


async def change_password(
    db: AsyncSession,
    redis: Redis,
    user: User,
    old_password: str,
    new_password: str,
) -> None:
    """修改密码后销毁该用户全部会话，要求重新登录（含首登强制改密场景）。"""
    if not security.verify_password(old_password, user.password_hash):
        raise errors.err(errors.AUTH_OLD_PASSWORD_MISMATCH)
    await db.execute(
        update(User)
        .where(User.id == user.id)
        .values(
            password_hash=security.hash_password(new_password),
            must_change_password=False,
        )
    )
    await session_store.destroy_user_sessions(redis, user.id)
    logger.info(
        "密码修改",
        extra_fields={"event": "user.password_change", "userId": str(user.id)},
    )
