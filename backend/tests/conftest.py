"""测试基础设施（开发规范 9.2）。

- 独立测试库 gify_test：每个测试会话重建，经 Alembic 迁移建表
- Redis 使用 db 1，每个测试前清空
- engine 用 NullPool，避免连接跨事件循环复用
"""

import os

# 必须在导入 app 之前覆盖环境（app.core.config 在导入时实例化）
TEST_DB_NAME = "gify_test"
TEST_DATABASE_URL = os.environ.setdefault(
    "DATABASE_URL", f"postgresql+psycopg://gify:gify@localhost:5432/{TEST_DB_NAME}"
)
ADMIN_DB_URL = "postgresql://gify:gify@localhost:5432/postgres"
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("SECRET_KEY", "test-secret")

import httpx
import psycopg
import pytest
import sqlalchemy as sa
from alembic.config import Config
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from alembic import command
from app.core.security import hash_password
from app.models.user import User

INITIAL_ADMIN = ("admin", "change-on-first-login")


@pytest.fixture(scope="session", autouse=True)
def test_database():
    """重建测试库并迁移到 head。"""
    with psycopg.connect(ADMIN_DB_URL, autocommit=True) as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB_NAME} WITH (FORCE)")
        conn.execute(f"CREATE DATABASE {TEST_DB_NAME}")
    command.upgrade(Config("alembic.ini"), "head")
    yield


@pytest.fixture
async def client():
    """每测：清空数据、重启 lifespan（空库触发初始管理员 seed）、提供 httpx client。"""
    import app.db as db_mod

    db_mod._engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    db_mod._session_factory = None

    async with db_mod.get_engine().begin() as conn:
        await conn.execute(sa.text("TRUNCATE users CASCADE"))
    cleaner = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    await cleaner.flushdb()
    await cleaner.aclose()

    from app.main import app

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
    await db_mod.get_engine().dispose()
    db_mod._engine = None
    db_mod._session_factory = None


async def create_user_direct(
    username: str,
    password: str = "Passw0rd!",
    role: str = "user",
    enabled: bool = True,
    must_change_password: bool = False,
) -> User:
    """绕过路由层直接造用户。"""
    import app.db as db_mod

    factory = db_mod.get_session_factory()
    async with factory() as session:
        user = User(
            username=username,
            display_name=username,
            password_hash=hash_password(password),
            role=role,
            enabled=enabled,
            must_change_password=must_change_password,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def login(
    client: httpx.AsyncClient, username: str, password: str
) -> httpx.Response:
    return await client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )


async def login_admin(client: httpx.AsyncClient) -> None:
    resp = await login(client, *INITIAL_ADMIN)
    assert resp.status_code == 200, resp.text
