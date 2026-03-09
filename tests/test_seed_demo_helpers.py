"""seed_demo_data.py tests — _trace_id, _utc_now, constants."""
from datetime import datetime, timezone

from seed_demo_data import _utc_now, _trace_id, DEMO_TRACE_PREFIX


def test_utc_now_is_utc():
    dt = _utc_now()
    assert dt.tzinfo is not None
    assert isinstance(dt, datetime)


def test_trace_id_deterministic():
    t1 = _trace_id("test_event")
    t2 = _trace_id("test_event")
    assert t1 == t2


def test_trace_id_prefix():
    t = _trace_id("foo")
    assert t.startswith(DEMO_TRACE_PREFIX)


def test_trace_id_different_names():
    assert _trace_id("a") != _trace_id("b")


def test_trace_id_length():
    t = _trace_id("something")
    assert len(t) == len(DEMO_TRACE_PREFIX) + 10  # sha1[:10]
