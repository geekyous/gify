"""业务异常与错误码登记（开发规范 2.5 / 3.4）。

错误码与 HTTP 状态码必须在此成对声明，业务代码禁止使用裸数字。
"""

from fastapi import status


class AppError(Exception):
    """业务异常。路由层与 service 层统一 raise，由全局异常处理器输出信封。"""

    def __init__(self, code: int, message: str, http_status: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


# ---- COMMON 1000–1999 ----
COMMON_INTERNAL = (1000, "服务内部错误", status.HTTP_500_INTERNAL_SERVER_ERROR)
COMMON_VALIDATION = (1001, "请求参数校验失败", status.HTTP_422_UNPROCESSABLE_CONTENT)
COMMON_INVALID_ARGUMENT = (1002, "请求参数不合法", status.HTTP_400_BAD_REQUEST)

# ---- AUTH 2000–2999 ----
AUTH_INVALID_CREDENTIALS = (2001, "用户名或密码错误", status.HTTP_401_UNAUTHORIZED)
AUTH_USER_DISABLED = (2002, "账号已被禁用", status.HTTP_403_FORBIDDEN)
AUTH_NOT_AUTHENTICATED = (2003, "未登录或会话已失效", status.HTTP_401_UNAUTHORIZED)
AUTH_FORBIDDEN = (2004, "没有执行该操作的权限", status.HTTP_403_FORBIDDEN)
AUTH_LOGIN_LOCKED = (2005, "失败次数过多，账号已临时锁定", status.HTTP_403_FORBIDDEN)
AUTH_OLD_PASSWORD_MISMATCH = (2006, "原密码不正确", status.HTTP_400_BAD_REQUEST)

# ---- USER 3000–3999 ----
USER_USERNAME_TAKEN = (3001, "用户名已存在", status.HTTP_409_CONFLICT)
USER_NOT_FOUND = (3002, "用户不存在", status.HTTP_404_NOT_FOUND)
USER_CANNOT_DISABLE_SELF = (3003, "不能禁用自己的账号", status.HTTP_400_BAD_REQUEST)
USER_CANNOT_CHANGE_OWN_ROLE = (3004, "不能修改自己的角色", status.HTTP_400_BAD_REQUEST)
USER_LAST_ADMIN = (3005, "系统至少保留一名启用的管理员", status.HTTP_400_BAD_REQUEST)


def err(registration: tuple[int, str, int], message: str | None = None) -> AppError:
    """按登记项构造 AppError，message 可按场景覆盖。"""
    code, default_message, http_status = registration
    return AppError(code, message or default_message, http_status)
