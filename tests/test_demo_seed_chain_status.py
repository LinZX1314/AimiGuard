from core.database import (
    AIChatMessage,
    AIChatSession,
    AIReport,
    AITTSTask,
    Asset,
    AuditLog,
    CollectorConfig,
    ExecutionTask,
    ScanFinding,
    ScanTask,
    ThreatEvent,
)
from seed_demo_data import DEMO_TAG, seed_demo_data


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _reset_overview_state(db) -> None:
    db.query(AIChatMessage).delete()
    db.query(AIChatSession).delete()
    db.query(AIReport).delete()
    db.query(AITTSTask).delete()
    db.query(AuditLog).delete()
    db.query(ScanFinding).delete()
    db.query(ScanTask).delete()
    db.query(ExecutionTask).delete()
    db.query(ThreatEvent).delete()
    db.query(Asset).delete()
    db.query(CollectorConfig).delete()
    db.commit()


def test_chain_status_warns_when_system_is_empty(client, admin_token, db):
    _reset_overview_state(db)

    response = client.get("/api/v1/overview/chain-status", headers=_h(admin_token))
    assert response.status_code == 200

    data = response.json()["data"]
    defense = {item["key"]: item for item in data["defense"]}
    probe = {item["key"]: item for item in data["probe"]}

    assert defense["hfish_ingest"]["ok"] is False
    assert defense["hfish_ingest"]["note"] == "HFish 未启用"
    assert probe["asset_inventory"]["ok"] is False
    assert probe["asset_inventory"]["note"] == "未配置资产"


def test_demo_seed_is_idempotent_and_exposes_real_chain_status(client, admin_token, db):
    _reset_overview_state(db)

    first_summary = seed_demo_data(db)
    second_summary = seed_demo_data(db)

    assert first_summary == second_summary
    assert db.query(Asset).filter(Asset.tags.like(f"%{DEMO_TAG}%")).count() == first_summary["assets"]
    assert db.query(ThreatEvent).filter(ThreatEvent.trace_id.like("demo_%")).count() == first_summary["threat_events"]
    assert db.query(ScanTask).filter(ScanTask.trace_id.like("demo_%")).count() == first_summary["scan_tasks"]
    assert db.query(ScanFinding).filter(ScanFinding.trace_id.like("demo_%")).count() == first_summary["scan_findings"]

    response = client.get("/api/v1/overview/chain-status", headers=_h(admin_token))
    assert response.status_code == 200

    data = response.json()["data"]
    defense = {item["key"]: item for item in data["defense"]}
    probe = {item["key"]: item for item in data["probe"]}

    assert defense["hfish_ingest"]["ok"] is True
    assert defense["ai_scoring"]["ok"] is True
    assert probe["task_scheduler"]["ok"] is True
    assert probe["asset_inventory"]["ok"] is True
    assert probe["scan_executor"]["ok"] is False
    assert "扫描失败" in probe["scan_executor"]["note"]
