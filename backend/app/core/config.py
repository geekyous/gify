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

    # CORS 允许的前端来源（开发规范 5.5.1）：逗号分隔的完整 origin，含协议与端口
    cors_origins: str = "http://localhost:5173"
    # SameSite 默认 Lax；前后端跨注册域部署时调整为 none（强制 Secure，需 HTTPS）
    cookie_samesite: Literal["lax", "none", "strict"] = "lax"

    init_admin_username: str = "admin"
    init_admin_password: str = "change-on-first-login"

    session_ttl_seconds: int = 7 * 24 * 3600
    login_max_attempts: int = 5
    login_lock_seconds: int = 600

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip() for origin in self.cors_origins.split(",") if origin.strip()
        ]

    @property
    def cookie_secure(self) -> bool:
        return self.env == "prod" or self.cookie_samesite == "none"


@lru_cache
def get_settings() -> Settings:
    return Settings()
