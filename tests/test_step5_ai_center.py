"""Step 5 AI 中枢 — 对话/报告/TTS 基础验证"""
import pytest
from starlette.testclient import TestClient


# ── AI Chat ──

def test_chat_creates_session(client: TestClient, admin_token: str):
    """首次对话应自动创建会话并返回 session_id"""
    res = client.post(
        "/api/v1/ai/chat",
        json={"message": "当前有哪些高危告警？"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert "session_id" in data
    assert "message" in data
    assert len(data["message"]) > 0


def test_chat_multi_turn(client: TestClient, admin_token: str):
    """同一 session 多轮对话应保持上下文"""
    # 第一轮
    r1 = client.post(
        "/api/v1/ai/chat",
        json={"message": "分析最近告警趋势"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r1.status_code == 200
    d1 = r1.json().get("data") or r1.json()
    sid = d1["session_id"]

    # 第二轮 — 引用同一 session
    r2 = client.post(
        "/api/v1/ai/chat",
        json={"message": "能展开说说吗？", "session_id": sid},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r2.status_code == 200
    d2 = r2.json().get("data") or r2.json()
    assert d2["session_id"] == sid


def test_get_sessions(client: TestClient, admin_token: str):
    """创建对话后 sessions 列表应包含该会话"""
    client.post(
        "/api/v1/ai/chat",
        json={"message": "hello"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    res = client.get(
        "/api/v1/ai/sessions",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    body = res.json()
    items = body.get("data") if isinstance(body.get("data"), list) else body
    assert isinstance(items, list)
    assert len(items) >= 1


def test_get_session_messages(client: TestClient, admin_token: str):
    """获取会话消息应返回 user + assistant 两条"""
    r = client.post(
        "/api/v1/ai/chat",
        json={"message": "测试消息历史"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    sid = (r.json().get("data") or r.json())["session_id"]
    res = client.get(
        f"/api/v1/ai/sessions/{sid}/messages",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    msgs = res.json() if isinstance(res.json(), list) else res.json().get("data", res.json())
    # 至少有 user + assistant
    assert len(msgs) >= 2
    roles = {m["role"] for m in msgs}
    assert "user" in roles
    assert "assistant" in roles


def test_delete_session(client: TestClient, admin_token: str):
    """删除会话应成功"""
    r = client.post(
        "/api/v1/ai/chat",
        json={"message": "待删除会话"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    sid = (r.json().get("data") or r.json())["session_id"]
    res = client.delete(
        f"/api/v1/ai/sessions/{sid}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200


# ── Report ──

def test_generate_daily_report(client: TestClient, admin_token: str):
    """生成日报应返回 report_id 和 summary"""
    res = client.post(
        "/api/v1/report/generate",
        json={"report_type": "daily"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert "report_id" in data
    assert "summary" in data


def test_generate_scan_report(client: TestClient, admin_token: str):
    """生成扫描报告应返回 report_id"""
    res = client.post(
        "/api/v1/report/generate",
        json={"report_type": "scan"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert "report_id" in data


def test_list_reports(client: TestClient, admin_token: str):
    """生成报告后列表应包含该报告"""
    client.post(
        "/api/v1/report/generate",
        json={"report_type": "weekly"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    res = client.get(
        "/api/v1/report/reports?page=1&page_size=10",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    body = res.json().get("data") or res.json()
    items = body.get("items", [])
    assert len(items) >= 1


def test_get_report_content(client: TestClient, admin_token: str):
    """获取报告内容应返回 Markdown 正文"""
    r = client.post(
        "/api/v1/report/generate",
        json={"report_type": "daily"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    rid = (r.json().get("data") or r.json())["report_id"]
    res = client.get(
        f"/api/v1/report/reports/{rid}/content",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert "content" in data
    assert len(data["content"]) > 0


# ── TTS ──

def test_create_tts_task(client: TestClient, admin_token: str):
    """创建 TTS 任务应返回 task_id"""
    res = client.post(
        "/api/v1/tts/tasks",
        json={"text": "这是一段测试文本，用于 TTS 合成验证。"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert "task_id" in data
    assert data.get("state") == "PENDING"


def test_list_tts_tasks(client: TestClient, admin_token: str):
    """创建 TTS 任务后列表应包含该任务"""
    client.post(
        "/api/v1/tts/tasks",
        json={"text": "列表测试文本"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    res = client.get(
        "/api/v1/tts/tasks",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    body = res.json().get("data") or res.json()
    items = body.get("items", [])
    assert len(items) >= 1


def test_get_tts_task_detail(client: TestClient, admin_token: str):
    """获取 TTS 任务详情应包含 text_content"""
    r = client.post(
        "/api/v1/tts/tasks",
        json={"text": "详情测试文本"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    tid = (r.json().get("data") or r.json())["task_id"]
    res = client.get(
        f"/api/v1/tts/tasks/{tid}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["text_content"] == "详情测试文本"
    assert data["state"] == "PENDING"
