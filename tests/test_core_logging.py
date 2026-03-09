"""core/logging_config.py tests — StructuredFormatter, setup_logging."""
import json
import logging
import pytest

from core.logging_config import StructuredFormatter, setup_logging


def test_formatter_basic():
    fmt = StructuredFormatter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="hello world", args=(), exc_info=None,
    )
    output = fmt.format(record)
    data = json.loads(output)
    assert data["level"] == "INFO"
    assert data["message"] == "hello world"
    assert "ts" in data


def test_formatter_extra_fields():
    fmt = StructuredFormatter()
    record = logging.LogRecord(
        name="test", level=logging.WARNING, pathname="", lineno=0,
        msg="req", args=(), exc_info=None,
    )
    record.trace_id = "t1"
    record.method = "GET"
    record.path = "/api/test"
    record.status = 200
    record.elapsed_ms = 12.5
    output = fmt.format(record)
    data = json.loads(output)
    assert data["trace_id"] == "t1"
    assert data["method"] == "GET"
    assert data["status"] == 200
    assert data["elapsed_ms"] == 12.5


def test_formatter_exception():
    fmt = StructuredFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        import sys
        exc_info = sys.exc_info()
    record = logging.LogRecord(
        name="test", level=logging.ERROR, pathname="", lineno=0,
        msg="error", args=(), exc_info=exc_info,
    )
    output = fmt.format(record)
    data = json.loads(output)
    assert "boom" in data["exception"]


def test_formatter_no_extra_keys_when_absent():
    fmt = StructuredFormatter()
    record = logging.LogRecord(
        name="test", level=logging.DEBUG, pathname="", lineno=0,
        msg="plain", args=(), exc_info=None,
    )
    output = fmt.format(record)
    data = json.loads(output)
    assert "trace_id" not in data
    assert "method" not in data


def test_setup_logging():
    setup_logging("DEBUG")
    logger = logging.getLogger("aimiguan")
    assert logger.level == logging.DEBUG
