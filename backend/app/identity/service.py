"""identity 模块业务逻辑：认证（登录、登出、修改密码）与用户管理。"""

import uuid
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import errors, security, session_store
from app.core.logging import get_logger
from app.identity.models import User
from app.identity.schemas import UserCreateIn, UserUpdateIn

logger = get_logger(__name__)

# 排序白名单：camelCase 请求值 -> 列
ORDERABLE_COLUMNS: dict[str, Any] = {
    "createdAt": User.created_at,
    "username": User.username,
    "role": User.role,
    "enabled": User.enabled,
}


async def get_by_username(db: AsyncSession, username: str) -> User | None:
    result = await db.scalars(select(User).where(User.username == username))
    return result.first()


async def get_by_id(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise errors.err(errors.USER_NOT_FOUND)
    return user


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

    user = await get_by_username(db, username)
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


async def list_users(
    db: AsyncSession,
    page: int,
    page_size: int,
    order_by: str,
    order: str,
) -> tuple[list[User], int]:
    column = ORDERABLE_COLUMNS.get(order_by)
    if column is None:
        raise errors.err(errors.COMMON_INVALID_ARGUMENT, f"不支持按 {order_by} 排序")
    total = await db.scalar(select(func.count()).select_from(User)) or 0
    stmt = (
        select(User)
        .order_by(column.asc() if order == "asc" else column.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list((await db.scalars(stmt)).all()), total


async def create_user(db: AsyncSession, data: UserCreateIn) -> tuple[User, str]:
    if await get_by_username(db, data.username) is not None:
        raise errors.err(errors.USER_USERNAME_TAKEN)
    initial_password = data.password or security.generate_initial_password()
    user = User(
        username=data.username,
        display_name=data.display_name,
        password_hash=security.hash_password(initial_password),
        role=data.role,
        must_change_password=True,
    )
    db.add(user)
    await db.flush()
    logger.info(
        "用户创建",
        extra_fields={
            "event": "user.created",
            "userId": str(user.id),
            "username": user.username,
            "role": user.role,
        },
    )
    return user, initial_password


async def update_user(
    db: AsyncSession, actor: User, user_id: uuid.UUID, data: UserUpdateIn
) -> User:
    user = await get_by_id(db, user_id)

    if data.role is not None and data.role != user.role:
        if user.id == actor.id:
            raise errors.err(errors.USER_CANNOT_CHANGE_OWN_ROLE)
        if user.role == "admin":
            await _assert_not_last_admin(db, excluding=user)
        user.role = data.role

    if data.enabled is not None and data.enabled != user.enabled:
        if not data.enabled and user.id == actor.id:
            raise errors.err(errors.USER_CANNOT_DISABLE_SELF)
        if user.role == "admin" and not data.enabled:
            await _assert_not_last_admin(db, excluding=user)
        user.enabled = data.enabled

    if data.display_name is not None:
        user.display_name = data.display_name

    await db.flush()
    logger.info(
        "用户更新",
        extra_fields={
            "event": "user.updated",
            "userId": str(user.id),
            "username": user.username,
            "role": user.role,
            "enabled": user.enabled,
        },
    )
    return user


async def reset_password(
    db: AsyncSession,
    redis: Redis,
    user_id: uuid.UUID,
    new_password: str | None,
) -> tuple[User, str]:
    user = await get_by_id(db, user_id)
    initial_password = new_password or security.generate_initial_password()
    await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(
            password_hash=security.hash_password(initial_password),
            must_change_password=True,
        )
    )
    # 口令被重置视为泄露响应，存量会话一并失效
    await session_store.destroy_user_sessions(redis, user.id)
    logger.info(
        "密码重置",
        extra_fields={"event": "user.password_reset", "userId": str(user.id)},
    )
    return user, initial_password


async def _assert_not_last_admin(db: AsyncSession, excluding: User) -> None:
    """禁用或降级管理员前，确认仍有一名启用的管理员。"""
    remaining = await db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.role == "admin", User.enabled, User.id != excluding.id)
    )
    if not remaining:
        raise errors.err(errors.USER_LAST_ADMIN)
