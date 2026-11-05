"""结构化 JSON 日志：一行一条输出 stdout，字段 camelCase。"""

import json
import logging
import sys
from datetime import UTC, datetime

# 日志脱敏字段清单，输出层统一过滤
_REDACTED_FIELDS = {"password", "api_key", "authorization", "session_id", "token"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update(
                {
                    k: ("[REDACTED]" if k.lower() in _REDACTED_FIELDS else v)
                    for k, v in extra.items()
                }
            )
        if record.exc_info and record.exc_info[0] is not None:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


def get_logger(name: str) -> logging.LoggerAdapter[logging.Logger]:
    """业务代码取 logger 的统一入口，通过 extra_fields 传结构化字段。"""

    class _Adapter(logging.LoggerAdapter[logging.Logger]):
        def process(
            self, msg: str, kwargs: dict[str, object]
        ) -> tuple[str, dict[str, object]]:
            extra = kwargs.pop("extra_fields", {})
            kwargs["extra"] = {"extra_fields": extra}
            return msg, kwargs  # type: ignore[return-value]

    return _Adapter(logging.getLogger(name), {})
