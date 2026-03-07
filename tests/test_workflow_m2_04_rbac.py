from copy import deepcopy
from uuid import uuid4

from services.workflow_dsl import load_default_defense_workflow


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_payload() -> dict:
    suffix = uuid4().hex[:8]
    workflow_key = f"wf-m2-04-{suffix}"
    dsl = deepcopy(load_default_defense_workflow())
    dsl["workflow_id"] = workflow_key
    dsl["name"] = f"Workflow {suffix}"
    dsl["version"] = 1
    dsl["status"] = "DRAFT"
    return {
        "workflow_key": workflow_key,
        "name": dsl["name"],
        "description": "workflow rbac test",
        "dsl": dsl,
        "change_note": "initial draft",
    }


def test_workflow_permission_matrix_view_operator_admin(client, admin_token, operator_token, viewer_token):
    admin_headers = _auth(admin_token)
    operator_headers = _auth(operator_token)
    viewer_headers = _auth(viewer_token)
    payload = _create_payload()

    create_resp = client.post("/api/v1/workflows", json=payload, headers=admin_headers)
    assert create_resp.status_code == 200
    workflow_id = create_resp.json()["data"]["id"]

    viewer_list = client.get("/api/v1/workflows", headers=viewer_headers)
    assert viewer_list.status_code == 403
    assert viewer_list.json()["code"] == 40301
    assert viewer_list.json()["message"] == "缺少权限: workflow_view"

    operator_list = client.get(
        f"/api/v1/workflows?page=1&page_size=10&keyword={payload['workflow_key']}",
        headers=operator_headers,
    )
    assert operator_list.status_code == 200
    assert any(item["id"] == workflow_id for item in operator_list.json()["data"]["items"])

    operator_detail = client.get(f"/api/v1/workflows/{workflow_id}", headers=operator_headers)
    assert operator_detail.status_code == 200

    operator_update = client.put(
        f"/api/v1/workflows/{workflow_id}",
        json={
            "version_tag": 1,
            "name": "operator update",
            "description": "forbidden",
            "dsl": operator_detail.json()["data"]["dsl"],
            "change_note": "operator update",
        },
        headers=operator_headers,
    )
    assert operator_update.status_code == 403
    assert operator_update.json()["message"] == "缺少权限: workflow_edit"

    operator_publish = client.post(
        f"/api/v1/workflows/{workflow_id}/publish",
        json={
            "version_tag": 1,
            "canary_percent": 10,
            "approval_reason": "operator publish",
            "approval_passed": True,
            "confirmation_text": payload["workflow_key"],
        },
        headers=operator_headers,
    )
    assert operator_publish.status_code == 403
    assert operator_publish.json()["message"] == "缺少权限: workflow_publish"

    operator_rollback = client.post(
        f"/api/v1/workflows/{workflow_id}/rollback",
        json={
            "target_version": 1,
            "reason": "operator rollback",
            "confirmation_text": payload["workflow_key"],
        },
        headers=operator_headers,
    )
    assert operator_rollback.status_code == 403
    assert operator_rollback.json()["message"] == "缺少权限: workflow_rollback"


def test_workflow_publish_requires_approval_and_confirmation(client, admin_token):
    headers = _auth(admin_token)
    payload = _create_payload()

    create_resp = client.post("/api/v1/workflows", json=payload, headers=headers)
    assert create_resp.status_code == 200
    workflow_id = create_resp.json()["data"]["id"]

    no_approval = client.post(
        f"/api/v1/workflows/{workflow_id}/publish",
        json={
            "version_tag": 1,
            "canary_percent": 10,
            "approval_reason": "未审批",
            "approval_passed": False,
            "confirmation_text": payload["workflow_key"],
        },
        headers=headers,
    )
    assert no_approval.status_code == 400
    assert no_approval.json()["code"] == 40042

    wrong_confirmation = client.post(
        f"/api/v1/workflows/{workflow_id}/publish",
        json={
            "version_tag": 1,
            "canary_percent": 10,
            "approval_reason": "审批已通过",
            "approval_passed": True,
            "confirmation_text": "wrong-confirmation",
        },
        headers=headers,
    )
    assert wrong_confirmation.status_code == 400
    assert wrong_confirmation.json()["code"] == 40043


def test_workflow_rollback_requires_confirmation(client, admin_token):
    headers = _auth(admin_token)
    payload = _create_payload()

    create_resp = client.post("/api/v1/workflows", json=payload, headers=headers)
    assert create_resp.status_code == 200
    workflow_id = create_resp.json()["data"]["id"]

    publish_resp = client.post(
        f"/api/v1/workflows/{workflow_id}/publish",
        json={
            "version_tag": 1,
            "canary_percent": 10,
            "approval_reason": "先发布",
            "approval_passed": True,
            "confirmation_text": payload["workflow_key"],
        },
        headers=headers,
    )
    assert publish_resp.status_code == 200

    rollback_resp = client.post(
        f"/api/v1/workflows/{workflow_id}/rollback",
        json={
            "target_version": 1,
            "reason": "确认失败",
            "confirmation_text": "wrong-confirmation",
        },
        headers=headers,
    )
    assert rollback_resp.status_code == 400
    assert rollback_resp.json()["code"] == 40044
