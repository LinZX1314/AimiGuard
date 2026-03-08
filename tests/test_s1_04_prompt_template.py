"""S1-04 Prompt模板版本管理与审计 测试"""
import pytest
from starlette.testclient import TestClient


def test_create_template(client: TestClient, admin_token: str):
    """创建新Prompt模板"""
    res = client.post(
        "/api/v1/ai/prompt-templates",
        json={
            "template_key": "risk_assessment",
            "content": "你是一个安全AI助手，请根据以下数据进行风险评估：\n{context}",
            "description": "风险评估Prompt模板",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["template_key"] == "risk_assessment"
    assert data["version"] == 1


def test_create_duplicate_template(client: TestClient, admin_token: str):
    """重复创建同key模板应409"""
    client.post(
        "/api/v1/ai/prompt-templates",
        json={"template_key": "dup_test", "content": "v1 content"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    res = client.post(
        "/api/v1/ai/prompt-templates",
        json={"template_key": "dup_test", "content": "v1 again"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 409


def test_list_templates(client: TestClient, admin_token: str):
    """列出模板"""
    client.post(
        "/api/v1/ai/prompt-templates",
        json={"template_key": "list_test", "content": "content"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    res = client.get(
        "/api/v1/ai/prompt-templates",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["total"] >= 1


def test_get_template_detail(client: TestClient, admin_token: str):
    """查看模板详情"""
    r = client.post(
        "/api/v1/ai/prompt-templates",
        json={"template_key": "detail_test", "content": "full content here"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    tid = (r.json().get("data") or r.json())["id"]

    res = client.get(
        f"/api/v1/ai/prompt-templates/{tid}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["content"] == "full content here"


def test_update_template_creates_new_version(client: TestClient, admin_token: str):
    """更新模板应创建新版本"""
    r = client.post(
        "/api/v1/ai/prompt-templates",
        json={"template_key": "version_test", "content": "v1 original"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    tid = (r.json().get("data") or r.json())["id"]

    res = client.put(
        f"/api/v1/ai/prompt-templates/{tid}",
        json={"content": "v2 updated content"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["version"] == 2
    assert "diff" in data


def test_update_deactivates_old_version(client: TestClient, admin_token: str):
    """更新后旧版本应被停用"""
    r = client.post(
        "/api/v1/ai/prompt-templates",
        json={"template_key": "deactivate_test", "content": "old"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    tid = (r.json().get("data") or r.json())["id"]

    client.put(
        f"/api/v1/ai/prompt-templates/{tid}",
        json={"content": "new"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # 旧版本应不在active列表中
    res = client.get(
        "/api/v1/ai/prompt-templates?template_key=deactivate_test&active_only=true",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    data = res.json().get("data") or res.json()
    active_versions = [t["version"] for t in data["items"]]
    assert 2 in active_versions
    assert 1 not in active_versions


def test_get_template_diff(client: TestClient, admin_token: str):
    """查看模板版本差异"""
    r = client.post(
        "/api/v1/ai/prompt-templates",
        json={"template_key": "diff_test", "content": "line1\nline2\nline3"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    tid = (r.json().get("data") or r.json())["id"]

    r2 = client.put(
        f"/api/v1/ai/prompt-templates/{tid}",
        json={"content": "line1\nline2_modified\nline3\nline4"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    new_tid = (r2.json().get("data") or r2.json())["id"]

    res = client.get(
        f"/api/v1/ai/prompt-templates/{new_tid}/diff",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["from_version"] == 1
    assert data["to_version"] == 2
    assert "diff" in data


def test_list_template_versions(client: TestClient, admin_token: str):
    """列出模板所有版本"""
    client.post(
        "/api/v1/ai/prompt-templates",
        json={"template_key": "ver_list_test", "content": "v1"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    res = client.get(
        "/api/v1/ai/prompt-templates/key/ver_list_test/versions",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json().get("data") or res.json()
    assert data["template_key"] == "ver_list_test"
    assert data["total_versions"] >= 1


def test_get_nonexistent_template(client: TestClient, admin_token: str):
    """不存在的模板应404"""
    res = client.get(
        "/api/v1/ai/prompt-templates/99999",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 404
