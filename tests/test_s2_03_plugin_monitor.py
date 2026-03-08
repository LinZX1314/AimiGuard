"""S2-03 MCP插件行为监控与异常检测 测试"""
import uuid
import pytest
from starlette.testclient import TestClient
from sqlalchemy.orm import Session as SASession
from sqlalchemy import text


# ── plugin_monitor 服务逻辑 ──

def test_log_plugin_call(db: SASession):
    """记录插件调用"""
    from services.plugin_monitor import log_plugin_call

    entry = log_plugin_call(
        db=db,
        plugin_id=1,
        plugin_name="test-plugin",
        tool_name="read_file",
        args={"path": "/tmp/test"},
        result={"content": "hello"},
        latency_ms=15.5,
        success=True,
    )
    assert entry.id is not None
    assert entry.plugin_id == 1
    assert entry.tool_name == "read_file"
    assert entry.latency_ms == 15.5


def test_log_failed_call(db: SASession):
    """记录失败的调用"""
    from services.plugin_monitor import log_plugin_call

    entry = log_plugin_call(
        db=db,
        plugin_id=1,
        plugin_name="test-plugin",
        tool_name="execute_command",
        success=False,
        error_message="Permission denied",
    )
    assert entry.success == 0
    assert entry.error_message == "Permission denied"


def test_check_args_private_ip():
    """检测调用参数中的内网IP"""
    from services.plugin_monitor import check_args_for_private_ip

    assert check_args_for_private_ip({"target": "192.168.1.100"}) == "192.168.1.100"
    assert check_args_for_private_ip({"target": "10.0.0.1"}) == "10.0.0.1"
    assert check_args_for_private_ip({"target": "8.8.8.8"}) is None
    assert check_args_for_private_ip(None) is None


def test_get_call_stats(db: SASession):
    """获取插件调用统计"""
    from services.plugin_monitor import log_plugin_call, get_call_stats

    for i in range(3):
        log_plugin_call(db=db, plugin_id=99, plugin_name="stat-test",
                        tool_name="read_file", latency_ms=10.0 + i)

    stats = get_call_stats(db, plugin_id=99)
    assert stats["total_calls"] == 3
    assert stats["error_calls"] == 0
    assert stats["avg_latency_ms"] > 0
    assert "read_file" in stats["tools"]


def test_detect_anomalies_no_data(db: SASession):
    """无数据时无异常"""
    from services.plugin_monitor import detect_anomalies
    anomalies = detect_anomalies(db, plugin_id=9999)
    assert anomalies == []


def test_auto_suspend_plugin(db: SASession):
    """自动暂停插件"""
    from services.plugin_monitor import auto_suspend_plugin
    from core.database import PluginRegistry

    db.execute(
        text(
            "INSERT INTO plugin_registry (plugin_name, plugin_type, enabled, created_at, updated_at) "
            "VALUES ('suspend-test', 'mcp', 1, datetime('now'), datetime('now'))"
        )
    )
    db.commit()
    row = db.execute(text("SELECT last_insert_rowid()")).fetchone()
    pid = row[0]

    result = auto_suspend_plugin(db, pid, "test_reason")
    assert result is True

    plugin = db.query(PluginRegistry).filter(PluginRegistry.id == pid).first()
    assert plugin.enabled == 0


# ── API 集成 ──

def _create_plugin(client: TestClient, token: str, name: str) -> int:
    res = client.post(
        "/api/v1/plugins",
        json={"plugin_name": name, "plugin_type": "mcp", "endpoint": "stdio"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    return (res.json().get("data") or res.json())["id"]


def test_call_logs_api(client: TestClient, admin_token: str, db: SASession):
    """GET /plugins/{id}/call-logs 应返回调用日志"""
    pid = _create_plugin(client, admin_token, "logs-api-test")

    from services.plugin_monitor import log_plugin_call
    log_plugin_call(db=db, plugin_id=pid, plugin_name="logs-api-test",
                    tool_name="read_file", latency_ms=5.0)

    res = client.get(
        f"/api/v1/plugins/{pid}/call-logs",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["total"] >= 1
    assert data["items"][0]["tool_name"] == "read_file"


def test_anomalies_api(client: TestClient, admin_token: str):
    """GET /plugins/{id}/anomalies 应返回异常检测结果"""
    pid = _create_plugin(client, admin_token, "anomaly-api-test")

    res = client.get(
        f"/api/v1/plugins/{pid}/anomalies",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert "anomalies" in data
    assert "stats" in data


def test_call_logs_not_found(client: TestClient, admin_token: str):
    """不存在的插件应404"""
    res = client.get(
        "/api/v1/plugins/99999/call-logs",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 404
