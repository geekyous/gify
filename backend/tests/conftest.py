"""测试基础设施

- 独立测试库 gify_test：每个测试会话重建，经 Alembic 迁移建表
- Redis 使用 db 1，每个测试前清空
- engine 用 NullPool，避免连接跨事件循环复用
"""

import os
from pathlib import Path


def _env_value(key: str) -> str:
    """从 deploy/.env 读取配置"""
    path = Path(__file__).resolve().parents[2] / "deploy" / ".env"

    if path.exists():
        for line in path.read_text().splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    return ""


_pg_user = _env_value("POSTGRES_USER") or "gify"
_pg_password = _env_value("POSTGRES_PASSWORD") or "gify"
TEST_DB_PORT = _env_value("POSTGRES_PORT") or 5432
# 测试库是独立的，
TEST_DB_NAME = "gify_test"
TEST_DATABASE_URL = f"postgresql+psycopg://{_pg_user}:{_pg_password}@localhost:{TEST_DB_PORT}/{TEST_DB_NAME}"

ADMIN_DB_URL = (
    f"postgresql://{_pg_user}:{_pg_password}@localhost:{TEST_DB_PORT}/postgres"
)

_redis_password = _env_value("REDIS_PASSWORD")
_redis_port = _env_value("REDIS_PORT") or 6379
TEST_REDIS_URL = f"redis://:{_redis_password}@localhost:{_redis_port}/1"

os.environ.setdefault("POSTGRES_DB", TEST_DB_NAME)
os.environ.setdefault("REDIS_DB", "1")
os.environ.setdefault("REDIS_PASSWORD", _env_value("REDIS_PASSWORD"))
os.environ.setdefault("SECRET_KEY", "test-secret")
# 固定初始管理员凭据，不随本地 deploy/.env 漂移（进程环境优先于 .env 文件）
os.environ.setdefault("INIT_ADMIN_USERNAME", "admin")
os.environ.setdefault("INIT_ADMIN_PASSWORD", "change-on-first-login")

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
from app.identity.models import User

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
    cleaner = Redis.from_url(TEST_REDIS_URL, decode_responses=True)
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
