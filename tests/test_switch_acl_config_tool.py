from ai.tools import _switch_acl_config


def test_ban_idempotent_short_circuit(monkeypatch):
    cfg = {
        "switches": [
            {
                "host": "192.168.0.2",
                "port": 23,
                "password": "admin",
                "acl_number": 30,
            }
        ]
    }

    monkeypatch.setattr(
        "database.models.SwitchAclModel.get_rules",
        lambda *_args, **_kwargs: [{"target_ip": "192.168.0.6", "action": "ban", "rule_id": 7}],
    )

    def _unexpected(*_args, **_kwargs):
        raise AssertionError("幂等封禁不应继续下发配置")

    monkeypatch.setattr("database.models.SwitchAclModel.add_rule", _unexpected)
    monkeypatch.setattr("telnetlib3.Telnet", _unexpected)

    result = _switch_acl_config({"action": "ban", "target_ip": "192.168.0.6"}, cfg)

    assert result["ok"] is True
    assert result["success_count"] == 1
    assert result["fail_count"] == 0
    assert result["skip_count"] == 1
    assert result["target_ip"] == "192.168.0.6"

    item = result["results"][0]
    assert item["ok"] is True
    assert item["status"] == "already_banned"
    assert item["rule_id"] == 7


def test_unban_removes_all_rule_ids(monkeypatch):
    cfg = {
        "switches": [
            {
                "host": "192.168.0.2",
                "port": 23,
                "password": "admin",
                "acl_number": 30,
            }
        ]
    }

    monkeypatch.setattr(
        "database.models.SwitchAclModel.get_rules",
        lambda *_args, **_kwargs: [
            {"target_ip": "192.168.0.6", "action": "ban", "rule_id": 2},
            {"target_ip": "192.168.0.6", "action": "ban", "rule_id": 1},
            {"target_ip": "192.168.0.10", "action": "ban", "rule_id": 3},
        ],
    )

    removed = []
    monkeypatch.setattr(
        "database.models.SwitchAclModel.remove_rule",
        lambda switch_ip, acl_number, target_ip: removed.append((switch_ip, acl_number, target_ip)),
    )

    sent_lines = []

    class FakeTelnet:
        def __init__(self, *_args, **_kwargs):
            pass

        def read_very_eager(self):
            return b""

        def write(self, data):
            sent_lines.append(data.decode("utf-8", errors="ignore").strip())

        def close(self):
            pass

    monkeypatch.setattr("telnetlib3.Telnet", FakeTelnet)
    monkeypatch.setattr("time.sleep", lambda *_args, **_kwargs: None)

    result = _switch_acl_config({"action": "unban", "target_ip": "192.168.0.6"}, cfg)

    assert result["ok"] is True
    assert result["success_count"] == 1
    assert result["fail_count"] == 0
    assert result["target_ip"] == "192.168.0.6"

    item = result["results"][0]
    assert item["ok"] is True
    assert item["target_ip"] == "192.168.0.6"
    assert item["rule_id"] == 1
    assert item["rule_ids"] == [1, 2]

    assert removed == [("192.168.0.2", 30, "192.168.0.6")]
    assert "no 1" in sent_lines
    assert "no 2" in sent_lines
