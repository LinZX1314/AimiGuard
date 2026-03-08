"""S2-02 最小Agency原则落地 — 插件权限声明+沙箱隔离 测试"""
import json
import pytest
from starlette.testclient import TestClient
from sqlalchemy.orm import Session as SASession
from sqlalchemy import text


# ── plugin_sandbox 服务逻辑 ──

def test_parse_permissions():
    """解析权限JSON"""
    from services.plugin_sandbox import parse_permissions
    perms = parse_permissions('["read_only","network_access"]')
    assert perms == {"read_only", "network_access"}


def test_parse_empty_permissions():
    """空权限应返回空集"""
    from services.plugin_sandbox import parse_permissions
    assert parse_permissions(None) == set()
    assert parse_permissions("") == set()


def test_parse_invalid_permissions():
    """无效权限应被过滤"""
    from services.plugin_sandbox import parse_permissions
    perms = parse_permissions('["read_only","hacker_mode"]')
    assert perms == {"read_only"}


def test_check_permission_granted():
    """声明权限内的调用应允许"""
    from services.plugin_sandbox import check_permission
    allowed, reason = check_permission({"read_only"}, "read_file")
    assert allowed is True


def test_check_permission_denied():
    """超出声明权限的调用应拒绝"""
    from services.plugin_sandbox import check_permission
    allowed, reason = check_permission({"read_only"}, "execute_command")
    assert allowed is False
    assert "permission_denied" in reason


def test_validate_declared_permissions():
    """合法权限声明应通过"""
    from services.plugin_sandbox import validate_declared_permissions
    valid, reason = validate_declared_permissions(["read_only", "network_access"])
    assert valid is True


def test_validate_empty_permissions():
    """空权限声明应失败"""
    from services.plugin_sandbox import validate_declared_permissions
    valid, reason = validate_declared_permissions([])
    assert valid is False


def test_validate_invalid_permissions():
    """含无效权限应失败"""
    from services.plugin_sandbox import validate_declared_permissions
    valid, reason = validate_declared_permissions(["read_only", "root_access"])
    assert valid is False
    assert "invalid" in reason


def test_compute_risk_score():
    """风险评分应按权限累加"""
    from services.plugin_sandbox import compute_risk_score
    assert compute_risk_score(["read_only"]) == 10
    assert compute_risk_score(["execute", "file_system"]) == 90
    assert compute_risk_score(["read_only", "execute", "network_access", "file_system"]) == 100


def test_enforce_sandbox_allowed():
    """沙箱内合法调用应通过"""
    from services.plugin_sandbox import enforce_sandbox
    allowed, reason = enforce_sandbox(
        plugin_id=1, plugin_name="test",
        declared_permissions_json='["read_only"]',
        tool_name="read_file",
    )
    assert allowed is True


def test_enforce_sandbox_blocked():
    """沙箱外调用应阻止"""
    from services.plugin_sandbox import enforce_sandbox
    allowed, reason = enforce_sandbox(
        plugin_id=1, plugin_name="test",
        declared_permissions_json='["read_only"]',
        tool_name="execute_command",
    )
    assert allowed is False


def test_enforce_sandbox_no_permissions():
    """无权限声明应全部拒绝"""
    from services.plugin_sandbox import enforce_sandbox
    allowed, reason = enforce_sandbox(
        plugin_id=1, plugin_name="test",
        declared_permissions_json=None,
        tool_name="read_file",
    )
    assert allowed is False


# ── API 集成 ──

def _create_plugin(client: TestClient, token: str, name: str = "sandbox-test") -> int:
    res = client.post(
        "/api/v1/plugins",
        json={"plugin_name": name, "plugin_type": "mcp", "endpoint": "stdio"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    return (res.json().get("data") or res.json())["id"]


def test_get_plugin_permissions_api(client: TestClient, admin_token: str):
    """GET /plugins/{id}/permissions 应返回权限信息"""
    pid = _create_plugin(client, admin_token)
    res = client.get(
        f"/api/v1/plugins/{pid}/permissions",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert "declared_permissions" in data
    assert "risk_score" in data
    assert "valid_permissions" in data


def test_update_plugin_permissions_api(client: TestClient, admin_token: str):
    """PUT /plugins/{id}/permissions 应更新权限"""
    pid = _create_plugin(client, admin_token, name="perm-update-test")
    res = client.put(
        f"/api/v1/plugins/{pid}/permissions",
        json={"permissions": ["read_only", "network_access"]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert "read_only" in data["declared_permissions"]
    assert "network_access" in data["declared_permissions"]
    assert data["risk_score"] == 40  # 10 + 30


def test_update_invalid_permissions_api(client: TestClient, admin_token: str):
    """无效权限更新应400"""
    pid = _create_plugin(client, admin_token, name="invalid-perm-test")
    res = client.put(
        f"/api/v1/plugins/{pid}/permissions",
        json={"permissions": ["read_only", "super_admin"]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 400
