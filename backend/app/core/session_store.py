"""服务端会话存储（Redis）。

键设计：
- session:{sid} -> JSON {userId, createdAt}，TTL 为会话有效期，每次请求滑动续期
- user-sessions:{userId} -> SET of sid，用于用户禁用时一次性清空其全部会话
"""

import json
from datetime import UTC, datetime
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.security import generate_session_id

SESSION_PREFIX = "session:"
_USER_SESSIONS_PREFIX = "user-sessions:"
_LOGIN_FAIL_PREFIX = "login-fail:"


def create_redis() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=True)


async def create_session(redis: Redis, user_id: UUID) -> str:
    settings = get_settings()
    sid = f"{SESSION_PREFIX}{generate_session_id()}"
    payload = json.dumps(
        {"userId": str(user_id), "createdAt": datetime.now(UTC).isoformat()},
        ensure_ascii=False,
    )
    async with redis.pipeline(transaction=True) as pipe:
        pipe.set(sid, payload, ex=settings.session_ttl_seconds)
        pipe.sadd(f"{_USER_SESSIONS_PREFIX}{user_id}", sid)
        await pipe.execute()
    return sid.removeprefix(SESSION_PREFIX)


async def load_session(redis: Redis, sid: str) -> UUID | None:
    """读取会话并滑动续期，返回用户 ID；不存在或已过期返回 None。"""
    settings = get_settings()
    key = f"{SESSION_PREFIX}{sid}"
    payload = await redis.get(key)
    if payload is None:
        return None
    await redis.expire(key, settings.session_ttl_seconds)
    return UUID(json.loads(payload)["userId"])


async def destroy_session(redis: Redis, sid: str, user_id: UUID) -> None:
    async with redis.pipeline(transaction=True) as pipe:
        pipe.delete(f"{SESSION_PREFIX}{sid}")
        pipe.srem(f"{_USER_SESSIONS_PREFIX}{user_id}", f"{SESSION_PREFIX}{sid}")
        await pipe.execute()


async def destroy_user_sessions(redis: Redis, user_id: UUID) -> int:
    """用户被禁用或重置密码后清空其全部存量会话。"""
    sids = await redis.smembers(f"{_USER_SESSIONS_PREFIX}{user_id}")
    if not sids:
        return 0
    async with redis.pipeline(transaction=True) as pipe:
        for sid in sids:
            pipe.delete(sid)
        pipe.delete(f"{_USER_SESSIONS_PREFIX}{user_id}")
        await pipe.execute()
    return len(sids)


async def register_login_failure(redis: Redis, username: str) -> int:
    """记录一次登录失败，返回当前失败次数；达到上限后进入锁定窗口。"""
    settings = get_settings()
    key = f"{_LOGIN_FAIL_PREFIX}{username}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, settings.login_lock_seconds)
    return count


async def is_login_locked(redis: Redis, username: str) -> bool:
    settings = get_settings()
    count = await redis.get(f"{_LOGIN_FAIL_PREFIX}{username}")
    return count is not None and int(count) >= settings.login_max_attempts


async def clear_login_failures(redis: Redis, username: str) -> None:
    await redis.delete(f"{_LOGIN_FAIL_PREFIX}{username}")
