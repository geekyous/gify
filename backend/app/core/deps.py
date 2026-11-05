"""公共依赖：DB Session、Redis（模块内的用户和角色依赖见各模块 deps）。"""

from typing import Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import provide_session


def get_redis(request: Request) -> Redis:
    return request.app.state.redis


SessionDep = Annotated[AsyncSession, Depends(provide_session)]
RedisDep = Annotated[Redis, Depends(get_redis)]
