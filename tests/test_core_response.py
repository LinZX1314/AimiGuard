"""core/response.py tests — APIResponse, HTTP status normalization, error extraction."""
import pytest
from unittest.mock import MagicMock, AsyncMock

from core.response import (
    APIResponse,
    _normalize_http_status,
    _extract_error_payload,
    http_exception_handler,
    validation_exception_handler,
    general_exception_handler,
)
from starlette.exceptions import HTTPException as StarletteHTTPException


# ── APIResponse ──

def test_success_default():
    r = APIResponse.success()
    assert r["code"] == 0
    assert r["message"] == "操作成功"
    assert r["data"] is None
    assert r["trace_id"] is None


def test_success_with_data():
    r = APIResponse.success(data={"id": 1}, message="ok", trace_id="t1")
    assert r["data"] == {"id": 1}
    assert r["trace_id"] == "t1"


def test_error():
    r = APIResponse.error(code=40001, message="bad", trace_id="t2", data={"field": "x"})
    assert r["code"] == 40001
    assert r["message"] == "bad"
    assert r["data"]["field"] == "x"


# ── _normalize_http_status ──

def test_normalize_valid_status():
    assert _normalize_http_status(200) == 200
    assert _normalize_http_status(404) == 404
    assert _normalize_http_status(500) == 500


def test_normalize_boundary():
    assert _normalize_http_status(100) == 100
    assert _normalize_http_status(599) == 599


def test_normalize_business_code():
    assert _normalize_http_status(40100) == 401
    assert _normalize_http_status(50000) == 500


def test_normalize_invalid_falls_to_500():
    assert _normalize_http_status(99) == 500
    assert _normalize_http_status(600) == 500
    assert _normalize_http_status(0) == 500


# ── _extract_error_payload ──

def test_extract_string_detail():
    exc = StarletteHTTPException(status_code=403, detail="forbidden")
    http_status, biz_code, msg, data = _extract_error_payload(exc)
    assert http_status == 403
    assert biz_code == 403
    assert msg == "forbidden"
    assert data is None


def test_extract_dict_detail_with_code():
    exc = StarletteHTTPException(status_code=400, detail={"code": 40001, "message": "参数错误"})
    http_status, biz_code, msg, data = _extract_error_payload(exc)
    assert http_status == 400
    assert biz_code == 40001
    assert msg == "参数错误"


def test_extract_dict_detail_extra_fields():
    exc = StarletteHTTPException(status_code=400, detail={"code": 40002, "message": "err", "field": "name"})
    _, _, _, data = _extract_error_payload(exc)
    assert data == {"field": "name"}


def test_extract_dict_no_message():
    exc = StarletteHTTPException(status_code=400, detail={"code": 40003, "detail": "fallback msg"})
    _, _, msg, _ = _extract_error_payload(exc)
    assert msg == "fallback msg"


def test_extract_business_status_code():
    exc = StarletteHTTPException(status_code=40100, detail="no auth")
    http_status, biz_code, msg, _ = _extract_error_payload(exc)
    assert http_status == 401
    assert biz_code == 40100


def test_extract_empty_detail():
    exc = StarletteHTTPException(status_code=500, detail="")
    _, _, msg, _ = _extract_error_payload(exc)
    assert msg == "请求失败"


# ── Exception handlers ──

@pytest.mark.asyncio
async def test_http_exception_handler():
    request = MagicMock()
    request.state.trace_id = "tr1"
    exc = StarletteHTTPException(status_code=404, detail="not found")
    resp = await http_exception_handler(request, exc)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_general_exception_handler():
    request = MagicMock()
    request.state.trace_id = "tr2"
    exc = RuntimeError("boom")
    resp = await general_exception_handler(request, exc)
    assert resp.status_code == 500
