"""ORM 模型汇总导入：Alembic autogenerate 依赖此处收集全部表。"""

from app.models.base import Base
from app.models.user import User

__all__ = ["Base", "User"]
