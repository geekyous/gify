"""应用入口：中间件、异常处理器、路由注册、生命周期（开发规范 3.1）。"""

import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from app.core import errors, security, session_store
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.core.schemas import Envelope
from app.db import provide_session
from app.identity import api as identity_api
from app.identity.models import User

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.redis = session_store.create_redis()
    await _seed_initial_admin()
    yield
    if getattr(app.state, "redis", None) is not None:
        await app.state.redis.aclose()


app = FastAPI(title="Gify API", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def request_context(request: Request, call_next):
    """分配 requestId、记录访问日志（开发规范 6.3）。"""
    request_id = uuid.uuid4().hex
    request.state.request_id = request_id
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = round((time.monotonic() - start) * 1000, 1)
    response.headers["X-Request-Id"] = request_id
    logger.info(
        "http 请求",
        extra_fields={
            "event": "http.request",
            "requestId": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "durationMs": duration_ms,
        },
    )
    return response


# CORS 白名单放行（开发规范 5.5）：生产前端与 API 不同源，凭证依赖精确 Allow-Origin
# 放在 request_context 之后注册，使其位于最外层，错误响应同样携带 CORS 头
_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(errors.AppError)
async def app_error_handler(request: Request, exc: errors.AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.http_status,
        content={"code": exc.code, "message": exc.message, "data": None},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """请求体校验失败：code 1001，data 为字段级错误（开发规范 2.4）。"""
    field_errors: dict[str, str] = {}
    for item in exc.errors():
        loc = [part for part in item["loc"] if part not in ("body", "query", "path")]
        if loc:
            field_errors[str(loc[-1])] = item["msg"]
    return JSONResponse(
        status_code=422,
        content={
            "code": 1001,
            "message": "请求参数校验失败",
            "data": field_errors or None,
        },
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "未处理异常",
        extra_fields={
            "event": "http.unhandled",
            "requestId": getattr(request.state, "request_id", None),
        },
        exc_info=exc,
    )
    registration = errors.COMMON_INTERNAL
    return JSONResponse(
        status_code=registration[2],
        content={"code": registration[0], "message": registration[1], "data": None},
    )


app.include_router(identity_api.auth_router)
app.include_router(identity_api.users_router)


@app.get("/api/health")
async def health() -> Envelope[dict[str, str]]:
    return Envelope.ok({"status": "up"})


async def _seed_initial_admin() -> None:
    """空库时按部署配置创建初始管理员，首次登录强制改密（FR-01 要求 3）。"""
    settings = get_settings()
    async for db in provide_session():
        try:
            count = await db.scalar(select(func.count()).select_from(User)) or 0
            if count > 0:
                return
            db.add(
                User(
                    username=settings.init_admin_username,
                    display_name="初始管理员",
                    password_hash=security.hash_password(settings.init_admin_password),
                    role="admin",
                    must_change_password=True,
                )
            )
            await db.commit()
            logger.info(
                "初始管理员已创建",
                extra_fields={
                    "event": "user.initial_admin_seeded",
                    "username": settings.init_admin_username,
                },
            )
        except Exception:
            await db.rollback()
            raise
