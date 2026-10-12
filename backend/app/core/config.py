"""全局配置：唯一入口，业务代码禁止直接读环境变量（见开发规范 3.5）。"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../deploy/.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Literal["dev", "prod"] = "dev"

    database_url: str
    redis_url: str
    secret_key: str

    init_admin_username: str = "admin"
    init_admin_password: str = "change-on-first-login"

    session_ttl_seconds: int = 7 * 24 * 3600
    login_max_attempts: int = 5
    login_lock_seconds: int = 600


@lru_cache
def get_settings() -> Settings:
    return Settings()
