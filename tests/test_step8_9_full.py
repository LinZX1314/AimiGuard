"""Step 8-9 集成测试：Plugin、Firewall、TTS、审计链、告警阈值、可观测性、E2E 闭环"""
import pytest


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ═══════════════ Plugin CRUD ═══════════════

class TestPluginCRUD:

    def test_list_empty(self, client, admin_token):
        r = client.get("/api/v1/plugins", headers=auth_headers(admin_token))
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == 0
        assert isinstance(body["data"], list)

    def test_create_plugin(self, client, admin_token):
        r = client.post("/api/v1/plugins", json={
            "plugin_name": "test-scanner",
            "plugin_type": "scanner",
        }, headers=auth_headers(admin_token))
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == 0
        assert body["data"]["plugin_name"] == "test-scanner"

    def test_create_duplicate(self, client, admin_token):
        client.post("/api/v1/plugins", json={
            "plugin_name": "dup-plugin", "plugin_type": "mcp",
        }, headers=auth_headers(admin_token))
        r = client.post("/api/v1/plugins", json={
            "plugin_name": "dup-plugin", "plugin_type": "mcp",
        }, headers=auth_headers(admin_token))
        assert r.status_code == 400

    def test_toggle_plugin(self, client, admin_token):
        cr = client.post("/api/v1/plugins", json={
            "plugin_name": "toggle-me", "plugin_type": "notifier",
        }, headers=auth_headers(admin_token))
        pid = cr.json()["data"]["id"]

        r = client.post(f"/api/v1/plugins/{pid}/toggle",
                        headers=auth_headers(admin_token))
        assert r.status_code == 200
        assert "enabled" in r.json()["data"]

    def test_update_plugin(self, client, admin_token):
        cr = client.post("/api/v1/plugins", json={
            "plugin_name": "upd-plugin", "plugin_type": "scanner",
        }, headers=auth_headers(admin_token))
        pid = cr.json()["data"]["id"]

        r = client.put(f"/api/v1/plugins/{pid}", json={
            "plugin_name": "upd-plugin-v2",
            "plugin_type": "ai_model",
        }, headers=auth_headers(admin_token))
        assert r.status_code == 200

    def test_delete_plugin(self, client, admin_token):
        cr = client.post("/api/v1/plugins", json={
            "plugin_name": "del-plugin", "plugin_type": "mcp",
        }, headers=auth_headers(admin_token))
        pid = cr.json()["data"]["id"]

        r = client.delete(f"/api/v1/plugins/{pid}",
                          headers=auth_headers(admin_token))
        assert r.status_code == 200


# ═══════════════ Firewall ═══════════════

class TestFirewall:

    def test_sync_create(self, client, admin_token):
        r = client.post("/api/v1/firewall/sync", json={
            "ip": "10.0.0.99",
            "action": "BLOCK",
            "reason": "test block",
        }, headers=auth_headers(admin_token))
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == 0
        assert "task_id" in body["data"]

    def test_sync_idempotent(self, client, admin_token):
        payload = {
            "ip": "10.0.0.100", "action": "BLOCK", "reason": "idem test",
        }
        r1 = client.post("/api/v1/firewall/sync", json=payload,
                         headers=auth_headers(admin_token))
        tid1 = r1.json()["data"]["task_id"]
        r2 = client.post("/api/v1/firewall/sync", json=payload,
                         headers=auth_headers(admin_token))
        tid2 = r2.json()["data"]["task_id"]
        assert tid1 == tid2

    def test_receipt_success(self, client, admin_token):
        cr = client.post("/api/v1/firewall/sync", json={
            "ip": "10.0.0.101", "action": "BLOCK",
        }, headers=auth_headers(admin_token))
        tid = cr.json()["data"]["task_id"]

        r = client.post(f"/api/v1/firewall/tasks/{tid}/receipt", json={
            "state": "SUCCESS", "message": "applied",
        }, headers=auth_headers(admin_token))
        assert r.status_code == 200
        assert r.json()["data"]["state"] == "SUCCESS"

    def test_receipt_failed_retry(self, client, admin_token):
        cr = client.post("/api/v1/firewall/sync", json={
            "ip": "10.0.0.102", "action": "BLOCK",
        }, headers=auth_headers(admin_token))
        tid = cr.json()["data"]["task_id"]

        client.post(f"/api/v1/firewall/tasks/{tid}/receipt", json={
            "state": "FAILED", "message": "timeout",
        }, headers=auth_headers(admin_token))

        r = client.post(f"/api/v1/firewall/tasks/{tid}/retry",
                        headers=auth_headers(admin_token))
        assert r.status_code == 200
        assert r.json()["data"]["state"] == "PENDING"

    def test_list_tasks(self, client, admin_token):
        r = client.get("/api/v1/firewall/tasks",
                       headers=auth_headers(admin_token))
        assert r.status_code == 200
        assert "items" in r.json()["data"]


# ═══════════════ TTS ═══════════════

class TestTTS:

    def test_create_task(self, client, admin_token):
        r = client.post("/api/v1/tts/tasks", json={
            "text": "你好，这是一个测试语音",
            "voice_model": "local-tts-v1",
        }, headers=auth_headers(admin_token))
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == 0
        assert body["data"]["state"] == "PENDING"

    def test_list_tasks(self, client, admin_token):
        client.post("/api/v1/tts/tasks", json={"text": "list test"},
                    headers=auth_headers(admin_token))
        r = client.get("/api/v1/tts/tasks",
                       headers=auth_headers(admin_token))
        assert r.status_code == 200
        assert r.json()["data"]["total"] >= 1

    def test_process_task(self, client, admin_token):
        cr = client.post("/api/v1/tts/tasks", json={"text": "process me"},
                         headers=auth_headers(admin_token))
        tid = cr.json()["data"]["task_id"]

        r = client.post(f"/api/v1/tts/tasks/{tid}/process",
                        headers=auth_headers(admin_token))
        assert r.status_code == 200
        assert r.json()["data"]["state"] == "SUCCESS"

    def test_get_task_detail(self, client, admin_token):
        cr = client.post("/api/v1/tts/tasks", json={"text": "detail check"},
                         headers=auth_headers(admin_token))
        tid = cr.json()["data"]["task_id"]

        r = client.get(f"/api/v1/tts/tasks/{tid}",
                       headers=auth_headers(admin_token))
        assert r.status_code == 200
        assert "text_content" in r.json()["data"]


# ═══════════════ Audit Chain ═══════════════

class TestAuditChain:

    def test_audit_logs_query(self, client, admin_token):
        client.post("/api/v1/tts/tasks", json={"text": "audit trail"},
                    headers=auth_headers(admin_token))

        r = client.get("/api/v1/system/audit/logs",
                       headers=auth_headers(admin_token))
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == 0
        assert "items" in body["data"]

    def test_audit_verify_chain(self, client, admin_token):
        r = client.get("/api/v1/system/audit/verify",
                       headers=auth_headers(admin_token))
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == 0
        assert "valid" in body["data"]

    def test_audit_filter_by_action(self, client, admin_token):
        r = client.get("/api/v1/system/audit/logs?action=tts",
                       headers=auth_headers(admin_token))
        assert r.status_code == 200


# ═══════════════ Observability & Alert ═══════════════

class TestObservability:

    def test_metrics_endpoint(self, client, admin_token):
        r = client.get("/api/v1/system/metrics",
                       headers=auth_headers(admin_token))
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == 0
        data = body["data"]
        assert "uptime_seconds" in data
        assert "counters" in data
        assert "latencies" in data
        assert "database" in data

    def test_alert_thresholds_get(self, client, admin_token):
        r = client.get("/api/v1/system/alert-thresholds",
                       headers=auth_headers(admin_token))
        assert r.status_code == 200
        data = r.json()["data"]
        assert "scan_fail_rate_pct" in data

    def test_alert_thresholds_update(self, client, admin_token):
        r = client.put("/api/v1/system/alert-thresholds",
                       json={"scan_fail_rate_pct": 30.0},
                       headers=auth_headers(admin_token))
        assert r.status_code == 200
        assert r.json()["data"]["scan_fail_rate_pct"] == 30.0

    def test_alert_check(self, client, admin_token):
        r = client.get("/api/v1/system/alert-check",
                       headers=auth_headers(admin_token))
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == 0
        assert "has_alerts" in body["data"]


# ═══════════════ E2E: 防御闭环（HFish告警 -> 审批 -> 防火墙） ═══════════════

class TestDefenseE2E:

    def test_defense_full_loop(self, client, admin_token):
        """E2E: HFish告警入站 -> 查看事件 -> 审批 -> 防火墙同步"""
        # 1. 通过 HFish 告警接口创建事件
        r = client.post("/api/v1/defense/alerts", json={
            "ip": "192.168.1.100",
            "protocol": "ssh",
            "port": 22,
            "info": "暴力破解尝试",
            "first_seen": "2026-03-06T00:00:00Z",
            "last_seen": "2026-03-06T06:00:00Z",
            "threat_label": "brute_force",
            "attack_count": 50,
        }, headers=auth_headers(admin_token))
        assert r.status_code == 200
        event_id = r.json()["data"]["event_id"]

        # 2. 查看事件列表
        r = client.get("/api/v1/defense/events",
                       headers=auth_headers(admin_token))
        assert r.status_code == 200

        # 3. 审批通过
        r = client.post(f"/api/v1/defense/events/{event_id}/approve",
                        json={"reason": "confirmed by e2e"},
                        headers=auth_headers(admin_token))
        assert r.status_code == 200

        # 4. 防火墙同步
        r = client.post("/api/v1/firewall/sync", json={
            "ip": "192.168.1.100",
            "action": "BLOCK",
            "reason": "approved by e2e",
        }, headers=auth_headers(admin_token))
        assert r.status_code == 200
        fw_tid = r.json()["data"]["task_id"]

        # 5. 回执成功
        r = client.post(f"/api/v1/firewall/tasks/{fw_tid}/receipt", json={
            "state": "SUCCESS", "message": "blocked",
        }, headers=auth_headers(admin_token))
        assert r.status_code == 200


# ═══════════════ E2E: 扫描闭环 ═══════════════

class TestScanE2E:

    def test_scan_full_loop(self, client, admin_token):
        """E2E: 创建扫描任务 -> 查看进度 -> AI 分析"""
        # 1. 创建扫描任务
        r = client.post("/api/v1/scan/tasks", json={
            "target": "10.0.0.0/24",
            "scan_type": "port_scan",
        }, headers=auth_headers(admin_token))
        assert r.status_code == 200
        task_id = r.json()["data"]["task_id"]

        # 2. 查看任务
        r = client.get(f"/api/v1/scan/tasks/{task_id}",
                       headers=auth_headers(admin_token))
        assert r.status_code == 200

        # 3. AI 对话关联扫描
        r = client.post("/api/v1/ai/chat", json={
            "message": "请分析这个扫描任务的结果",
            "context_type": "scan_task",
            "context_id": str(task_id),
        }, headers=auth_headers(admin_token))
        assert r.status_code == 200
        assert r.json()["data"]["message"]


# ═══════════════ RBAC: 权限隔离 ═══════════════

class TestRBAC:

    def test_viewer_cannot_create_plugin(self, client, viewer_token):
        r = client.post("/api/v1/plugins", json={
            "plugin_name": "forbidden-plugin", "plugin_type": "mcp",
        }, headers=auth_headers(viewer_token))
        assert r.status_code == 403

    def test_viewer_cannot_sync_firewall(self, client, viewer_token):
        r = client.post("/api/v1/firewall/sync", json={
            "ip": "10.0.0.200", "action": "BLOCK",
        }, headers=auth_headers(viewer_token))
        assert r.status_code == 403

    def test_viewer_cannot_update_thresholds(self, client, viewer_token):
        r = client.put("/api/v1/system/alert-thresholds",
                       json={"scan_fail_rate_pct": 50.0},
                       headers=auth_headers(viewer_token))
        assert r.status_code == 403


# ═══════════════ Health ═══════════════

class TestHealth:

    def test_health_check(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["data"]["status"] == "healthy"

    def test_version_info(self, client, admin_token):
        r = client.get("/api/v1/system/version",
                       headers=auth_headers(admin_token))
        assert r.status_code == 200
        assert "app_version" in r.json()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
