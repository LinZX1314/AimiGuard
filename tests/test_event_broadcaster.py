"""EventBroadcaster tests — connect, disconnect, publish, stale cleanup."""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from services.event_broadcaster import EventBroadcaster, DEFENSE_EVENTS_CHANNEL


@pytest.fixture
def broadcaster():
    return EventBroadcaster()


def _mock_ws(*, fail=False):
    ws = AsyncMock()
    if fail:
        ws.send_json.side_effect = Exception("connection closed")
    return ws


# ── Connect / Disconnect ──

@pytest.mark.asyncio
async def test_connect_returns_client_id(broadcaster):
    ws = _mock_ws()
    cid = await broadcaster.connect("ch1", ws)
    assert isinstance(cid, str)
    assert len(cid) == 32  # uuid hex


@pytest.mark.asyncio
async def test_disconnect_removes_client(broadcaster):
    ws = _mock_ws()
    cid = await broadcaster.connect("ch1", ws)
    await broadcaster.disconnect("ch1", cid)
    delivered = await broadcaster.broadcast("ch1", {"test": True})
    assert delivered == 0


@pytest.mark.asyncio
async def test_disconnect_nonexistent_channel(broadcaster):
    await broadcaster.disconnect("nonexistent", "fake_id")


@pytest.mark.asyncio
async def test_disconnect_nonexistent_client(broadcaster):
    ws = _mock_ws()
    await broadcaster.connect("ch1", ws)
    await broadcaster.disconnect("ch1", "wrong_id")


# ── Broadcast ──

@pytest.mark.asyncio
async def test_broadcast_delivers_to_all(broadcaster):
    ws1 = _mock_ws()
    ws2 = _mock_ws()
    await broadcaster.connect("ch1", ws1)
    await broadcaster.connect("ch1", ws2)
    delivered = await broadcaster.broadcast("ch1", {"msg": "hello"})
    assert delivered == 2
    ws1.send_json.assert_called_once_with({"msg": "hello"})
    ws2.send_json.assert_called_once_with({"msg": "hello"})


@pytest.mark.asyncio
async def test_broadcast_empty_channel(broadcaster):
    delivered = await broadcaster.broadcast("empty_ch", {"msg": "nobody"})
    assert delivered == 0


@pytest.mark.asyncio
async def test_broadcast_cleans_stale(broadcaster):
    good = _mock_ws()
    stale = _mock_ws(fail=True)
    await broadcaster.connect("ch1", good)
    await broadcaster.connect("ch1", stale)
    delivered = await broadcaster.broadcast("ch1", {"msg": "test"})
    assert delivered == 1
    # Second broadcast: stale should be gone
    delivered2 = await broadcaster.broadcast("ch1", {"msg": "test2"})
    assert delivered2 == 1


@pytest.mark.asyncio
async def test_broadcast_all_stale_cleans_channel(broadcaster):
    stale1 = _mock_ws(fail=True)
    stale2 = _mock_ws(fail=True)
    await broadcaster.connect("ch1", stale1)
    await broadcaster.connect("ch1", stale2)
    delivered = await broadcaster.broadcast("ch1", {"msg": "test"})
    assert delivered == 0
    # Channel should be cleaned up
    delivered2 = await broadcaster.broadcast("ch1", {"msg": "test2"})
    assert delivered2 == 0


# ── Publish ──

@pytest.mark.asyncio
async def test_publish_formats_payload(broadcaster):
    ws = _mock_ws()
    await broadcaster.connect(DEFENSE_EVENTS_CHANNEL, ws)
    count = await broadcaster.publish(
        DEFENSE_EVENTS_CHANNEL,
        "threat_detected",
        data={"ip": "10.0.0.1"},
        trace_id="tr123",
        reason="test reason",
    )
    assert count == 1
    payload = ws.send_json.call_args[0][0]
    assert payload["type"] == "threat_detected"
    assert payload["channel"] == DEFENSE_EVENTS_CHANNEL
    assert payload["data"]["ip"] == "10.0.0.1"
    assert payload["trace_id"] == "tr123"
    assert payload["reason"] == "test reason"
    assert "timestamp" in payload


@pytest.mark.asyncio
async def test_publish_without_optional_fields(broadcaster):
    ws = _mock_ws()
    await broadcaster.connect("ch1", ws)
    await broadcaster.publish("ch1", "ping")
    payload = ws.send_json.call_args[0][0]
    assert "trace_id" not in payload
    assert "reason" not in payload
    assert payload["data"] == {}


# ── Channel isolation ──

@pytest.mark.asyncio
async def test_channels_isolated(broadcaster):
    ws1 = _mock_ws()
    ws2 = _mock_ws()
    await broadcaster.connect("ch_a", ws1)
    await broadcaster.connect("ch_b", ws2)
    await broadcaster.broadcast("ch_a", {"only": "a"})
    ws1.send_json.assert_called_once()
    ws2.send_json.assert_not_called()
