"""S4-01 AI 决策行为审计强化 测试"""
import pytest
from starlette.testclient import TestClient
from sqlalchemy.orm import Session as SASession
from sqlalchemy import text


# ── 决策日志自动写入 ──

def test_chat_creates_decision_log(client: TestClient, admin_token: str, db: SASession):
    """AI 对话应自动写入决策日志"""
    res = client.post(
        "/api/v1/ai/chat",
        json={"message": "测试决策日志写入"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200

    row = db.execute(
        text("SELECT context_type, model_name, prompt_hash, inference_ms, model_params FROM ai_decision_log WHERE context_type = 'chat' ORDER BY id DESC LIMIT 1")
    ).fetchone()
    assert row is not None
    assert row[0] == "chat"
    assert row[1] is not None  # model_name
    assert row[2] is not None  # prompt_hash
    assert len(row[2]) == 16  # sha256 truncated to 16 chars
    assert row[3] is not None  # inference_ms
    assert row[3] >= 0
    assert row[4] is not None  # model_params JSON


def test_report_creates_decision_log(client: TestClient, admin_token: str, db: SASession):
    """报告生成应自动写入决策日志"""
    res = client.post(
        "/api/v1/report/generate",
        json={"report_type": "daily"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200

    row = db.execute(
        text("SELECT context_type, prompt_hash, inference_ms, model_params FROM ai_decision_log WHERE context_type = 'report' ORDER BY id DESC LIMIT 1")
    ).fetchone()
    assert row is not None
    assert row[0] == "report"
    assert row[1] is not None  # prompt_hash
    assert row[2] is not None  # inference_ms
    assert row[3] is not None  # model_params JSON
    assert "report_type" in row[3]


# ── 决策日志查询 API ──

def test_list_decisions_empty(client: TestClient, admin_token: str):
    """无决策记录时应返回空列表"""
    res = client.get(
        "/api/v1/ai/decisions?range=all",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_list_decisions_after_chat(client: TestClient, admin_token: str):
    """对话后决策列表应包含记录"""
    client.post(
        "/api/v1/ai/chat",
        json={"message": "查询决策日志测试"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    res = client.get(
        "/api/v1/ai/decisions?range=all",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["total"] >= 1
    item = data["items"][0]
    assert item["context_type"] == "chat"
    assert item["prompt_hash"] is not None
    assert item["inference_ms"] is not None
    assert item["trace_id"] is not None


def test_list_decisions_filter_by_type(client: TestClient, admin_token: str):
    """按 context_type 筛选决策日志"""
    # Create both chat and report decisions
    client.post(
        "/api/v1/ai/chat",
        json={"message": "筛选测试"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    client.post(
        "/api/v1/report/generate",
        json={"report_type": "daily"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # Filter chat only
    res = client.get(
        "/api/v1/ai/decisions?context_type=chat&range=all",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    for item in data["items"]:
        assert item["context_type"] == "chat"

    # Filter report only
    res2 = client.get(
        "/api/v1/ai/decisions?context_type=report&range=all",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res2.status_code == 200
    data2 = res2.json().get("data") or res2.json()
    for item in data2["items"]:
        assert item["context_type"] == "report"
