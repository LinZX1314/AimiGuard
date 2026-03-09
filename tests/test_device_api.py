"""Device & Credential API tests — full CRUD + connection test."""
import pytest
from unittest.mock import patch, MagicMock


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Device CRUD ──

def test_create_device(client, admin_token):
    resp = client.post("/api/v1/device/create", json={
        "name": "switch-core-01",
        "ip": "192.168.1.1",
        "port": 22,
        "vendor": "Huawei",
        "device_type": "switch",
        "description": "核心交换机",
    }, headers=_h(admin_token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["name"] == "switch-core-01"
    assert data["ip"] == "192.168.1.1"
    assert data["vendor"] == "Huawei"
    assert data["enabled"] is True


def test_create_device_duplicate_name(client, admin_token):
    client.post("/api/v1/device/create", json={
        "name": "dup-switch", "ip": "10.0.0.1", "vendor": "Cisco",
    }, headers=_h(admin_token))
    resp = client.post("/api/v1/device/create", json={
        "name": "dup-switch", "ip": "10.0.0.2", "vendor": "Cisco",
    }, headers=_h(admin_token))
    assert resp.status_code == 400


def test_list_devices(client, admin_token):
    client.post("/api/v1/device/create", json={
        "name": "list-dev-1", "ip": "10.0.1.1", "vendor": "H3C",
    }, headers=_h(admin_token))
    resp = client.get("/api/v1/device/list", headers=_h(admin_token))
    assert resp.status_code == 200
    devices = resp.json()["data"]
    assert any(d["name"] == "list-dev-1" for d in devices)
    assert "credentials" in devices[0]


def test_update_device(client, admin_token):
    create = client.post("/api/v1/device/create", json={
        "name": "upd-dev", "ip": "10.0.2.1", "vendor": "Juniper",
    }, headers=_h(admin_token))
    dev_id = create.json()["data"]["id"]
    resp = client.put(f"/api/v1/device/{dev_id}", json={
        "name": "upd-dev-renamed", "enabled": False,
    }, headers=_h(admin_token))
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "upd-dev-renamed"
    assert resp.json()["data"]["enabled"] is False


def test_update_device_not_found(client, admin_token):
    resp = client.put("/api/v1/device/99999", json={
        "name": "ghost",
    }, headers=_h(admin_token))
    assert resp.status_code == 404


def test_update_device_name_conflict(client, admin_token):
    client.post("/api/v1/device/create", json={
        "name": "conflict-a", "ip": "10.0.3.1", "vendor": "X",
    }, headers=_h(admin_token))
    create_b = client.post("/api/v1/device/create", json={
        "name": "conflict-b", "ip": "10.0.3.2", "vendor": "X",
    }, headers=_h(admin_token))
    dev_b_id = create_b.json()["data"]["id"]
    resp = client.put(f"/api/v1/device/{dev_b_id}", json={
        "name": "conflict-a",
    }, headers=_h(admin_token))
    assert resp.status_code == 400


def test_delete_device(client, admin_token):
    create = client.post("/api/v1/device/create", json={
        "name": "del-dev", "ip": "10.0.4.1", "vendor": "Dell",
    }, headers=_h(admin_token))
    dev_id = create.json()["data"]["id"]
    resp = client.delete(f"/api/v1/device/{dev_id}", headers=_h(admin_token))
    assert resp.status_code == 200
    assert resp.json()["code"] == 0


def test_delete_device_not_found(client, admin_token):
    resp = client.delete("/api/v1/device/99999", headers=_h(admin_token))
    assert resp.status_code == 404


# ── Credential CRUD ──

def _create_device(client, admin_token, name="cred-dev") -> int:
    resp = client.post("/api/v1/device/create", json={
        "name": name, "ip": "10.0.5.1", "vendor": "Arista",
    }, headers=_h(admin_token))
    return resp.json()["data"]["id"]


def test_add_credential(client, admin_token):
    dev_id = _create_device(client, admin_token, "cred-add-dev")
    resp = client.post(f"/api/v1/device/{dev_id}/credentials", json={
        "username": "admin", "password": "s3cret",
    }, headers=_h(admin_token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["username"] == "admin"
    assert "secret_ciphertext" not in data  # password not exposed


def test_add_credential_device_not_found(client, admin_token):
    resp = client.post("/api/v1/device/99999/credentials", json={
        "username": "admin", "password": "pass",
    }, headers=_h(admin_token))
    assert resp.status_code == 404


def test_list_credentials(client, admin_token):
    dev_id = _create_device(client, admin_token, "cred-list-dev")
    client.post(f"/api/v1/device/{dev_id}/credentials", json={
        "username": "user1", "password": "p1",
    }, headers=_h(admin_token))
    client.post(f"/api/v1/device/{dev_id}/credentials", json={
        "username": "user2", "password": "p2",
    }, headers=_h(admin_token))
    resp = client.get(f"/api/v1/device/{dev_id}/credentials", headers=_h(admin_token))
    assert resp.status_code == 200
    creds = resp.json()["data"]
    assert len(creds) >= 2
    usernames = {c["username"] for c in creds}
    assert "user1" in usernames
    assert "user2" in usernames


def test_list_credentials_device_not_found(client, admin_token):
    resp = client.get("/api/v1/device/99999/credentials", headers=_h(admin_token))
    assert resp.status_code == 404


def test_update_credential(client, admin_token):
    dev_id = _create_device(client, admin_token, "cred-upd-dev")
    add = client.post(f"/api/v1/device/{dev_id}/credentials", json={
        "username": "olduser", "password": "oldpass",
    }, headers=_h(admin_token))
    cred_id = add.json()["data"]["id"]
    resp = client.put(f"/api/v1/device/{dev_id}/credentials/{cred_id}", json={
        "username": "newuser", "password": "newpass",
    }, headers=_h(admin_token))
    assert resp.status_code == 200
    assert resp.json()["data"]["username"] == "newuser"


def test_update_credential_not_found(client, admin_token):
    dev_id = _create_device(client, admin_token, "cred-upd-ghost-dev")
    resp = client.put(f"/api/v1/device/{dev_id}/credentials/99999", json={
        "username": "x",
    }, headers=_h(admin_token))
    assert resp.status_code == 404


def test_delete_credential(client, admin_token):
    dev_id = _create_device(client, admin_token, "cred-del-dev")
    add = client.post(f"/api/v1/device/{dev_id}/credentials", json={
        "username": "delme", "password": "p",
    }, headers=_h(admin_token))
    cred_id = add.json()["data"]["id"]
    resp = client.delete(f"/api/v1/device/{dev_id}/credentials/{cred_id}", headers=_h(admin_token))
    assert resp.status_code == 200


def test_delete_credential_not_found(client, admin_token):
    dev_id = _create_device(client, admin_token, "cred-del-ghost-dev")
    resp = client.delete(f"/api/v1/device/{dev_id}/credentials/99999", headers=_h(admin_token))
    assert resp.status_code == 404


# ── Connection Test ──

def test_device_connection_test_not_found(client, admin_token):
    resp = client.post("/api/v1/device/99999/test", headers=_h(admin_token))
    assert resp.status_code == 404


def test_device_connection_test_unreachable(client, admin_token, db):
    from core.database import Device
    dev_id = _create_device(client, admin_token, "conn-test-dev")
    dev = db.query(Device).filter(Device.id == dev_id).first()
    dev.ip = "127.0.0.1"
    dev.port = 1  # port 1 is almost certainly closed
    db.commit()
    resp = client.post(f"/api/v1/device/{dev_id}/test", headers=_h(admin_token))
    assert resp.status_code == 200
    body = resp.json()
    assert "ok" in body
    assert "message" in body


def test_device_connection_response_structure(client, admin_token):
    dev_id = _create_device(client, admin_token, "conn-struct-dev")
    resp = client.post(f"/api/v1/device/{dev_id}/test", headers=_h(admin_token))
    assert resp.status_code == 200
    body = resp.json()
    assert "code" in body
    assert "ok" in body
    assert "message" in body


# ── Delete device cascades credentials ──

def test_delete_device_cascades_credentials(client, admin_token, db):
    from core.database import Credential
    dev_id = _create_device(client, admin_token, "cascade-del-dev")
    client.post(f"/api/v1/device/{dev_id}/credentials", json={
        "username": "cascade-user", "password": "p",
    }, headers=_h(admin_token))
    assert db.query(Credential).filter(Credential.device_id == dev_id).count() >= 1
    client.delete(f"/api/v1/device/{dev_id}", headers=_h(admin_token))
    db.expire_all()
    assert db.query(Credential).filter(Credential.device_id == dev_id).count() == 0
