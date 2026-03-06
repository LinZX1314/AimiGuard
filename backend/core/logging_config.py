"""
统一结构化日志配置。
所有日志行包含 trace_id / module / action 字段。
"""
import logging
import json
import sys
from datetime import datetime, timezone


class StructuredFormatter(logging.Formatter):
    """输出 JSON 格式日志，方便后续采集"""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("trace_id", "method", "path", "status", "elapsed_ms",
                     "module", "action", "detail", "error"):
            val = getattr(record, key, None)
            if val is not None:
                payload[key] = val
        if record.exc_info and record.exc_info[1]:
            payload["exception"] = str(record.exc_info[1])
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: str = "INFO"):
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()
    root.addHandler(handler)

    logging.getLogger("aimiguan").setLevel(getattr(logging, level.upper(), logging.INFO))
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
