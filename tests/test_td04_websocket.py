"""TD-04 WebSocket 实时推送 — 基础验证"""
import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


def test_defense_ws_requires_token(client: TestClient):
    """连接 /ws/defense/events 不带 token 应被关闭"""
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/defense/events?token=") as ws:
            ws.receive()


def test_defense_ws_invalid_token(client: TestClient):
    """连接 /ws/defense/events 带无效 token 应被关闭"""
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/defense/events?token=invalid_jwt") as ws:
            ws.receive()


def test_defense_ws_ready_event(client: TestClient, admin_token: str):
    """连接成功后应收到 ready 事件"""
    with client.websocket_connect(f"/ws/defense/events?token={admin_token}") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "ready"
        assert msg["channel"] == "defense.events"
        assert "username" in msg.get("data", {})


def test_defense_ws_ping_pong(client: TestClient, admin_token: str):
    """客户端发 ping 后应收到 pong"""
    with client.websocket_connect(f"/ws/defense/events?token={admin_token}") as ws:
        ws.receive_json()  # ready
        ws.send_text("ping")
        pong = ws.receive_json()
        assert pong["type"] == "pong"


def test_scan_ws_ready_event(client: TestClient, admin_token: str):
    """连接 /ws/scan/tasks 成功后应收到 ready 事件"""
    with client.websocket_connect(f"/ws/scan/tasks?token={admin_token}") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "ready"
        assert msg["channel"] == "scan.tasks"


def test_scan_ws_viewer_has_access(client: TestClient, viewer_token: str):
    """viewer 用户拥有 scan:view 权限，连接应成功"""
    with client.websocket_connect(f"/ws/scan/tasks?token={viewer_token}") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "ready"
        assert msg["channel"] == "scan.tasks"
