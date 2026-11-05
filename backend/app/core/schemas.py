"""Schema 基类与统一响应。

JSON 字段 camelCase 由 alias 统一转换，业务代码内部使用 snake_case。
"""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """camelCase 序列化基类：请求按 alias 解析，响应按 alias 输出。"""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class Envelope[T](BaseModel):
    """统一响应：{code, message, data}。"""

    code: int = 0
    message: str = "ok"
    data: T | None = None

    @classmethod
    def ok(cls, data: T) -> "Envelope[T]":
        return cls(code=0, message="ok", data=data)


class Page[T](CamelModel):
    """分页响应 data 的固定结构。"""

    items: list[T]
    total: int
    page: int
    page_size: int
