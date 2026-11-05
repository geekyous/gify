"""密码哈希与会话凭证。"""

import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# argon2id，库默认参数集
_hasher = PasswordHasher()

SESSION_COOKIE = "gify_session"


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, plain)
    except VerifyMismatchError:
        return False


def generate_session_id() -> str:
    """会话 ID：密码学安全随机数，URL-safe 编码（≥32 字节熵）。"""
    return secrets.token_urlsafe(32)


def generate_initial_password() -> str:
    """创建用户或重置密码时未指定口令则生成随机口令，仅展示一次。"""
    return secrets.token_urlsafe(9)
