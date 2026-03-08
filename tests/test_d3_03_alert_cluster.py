"""D3-03 告警聚类降噪 测试"""
import uuid
import pytest
from starlette.testclient import TestClient
from sqlalchemy.orm import Session as SASession
from sqlalchemy import text


def _seed_events(db: SASession, ip: str, label: str, count: int):
    """插入 count 条同源告警"""
    for _ in range(count):
        tid = str(uuid.uuid4())
        db.execute(
            text(
                "INSERT INTO threat_event (ip, source, threat_label, status, ai_score, trace_id, created_at, updated_at) "
                "VALUES (:ip, 'test', :label, 'PENDING', 50, :tid, datetime('now'), datetime('now'))"
            ),
            {"ip": ip, "label": label, "tid": tid},
        )
    db.commit()


# ── 聚类逻辑 ──

def test_cluster_groups_same_ip_label(db: SASession):
    """相同 IP+label 应被聚合为一个聚类"""
    from services.alert_cluster import cluster_events
    _seed_events(db, "10.0.0.1", "SSH暴力破解", 5)
    clusters = cluster_events(db, hours=24)
    assert len(clusters) == 1
    assert clusters[0]["total_count"] == 5
    assert clusters[0]["ip"] == "10.0.0.1"


def test_cluster_separates_different_ips(db: SASession):
    """不同 IP 应分别聚类"""
    from services.alert_cluster import cluster_events
    _seed_events(db, "10.0.0.1", "SSH暴力破解", 3)
    _seed_events(db, "10.0.0.2", "SSH暴力破解", 2)
    clusters = cluster_events(db, hours=24)
    assert len(clusters) == 2
    ips = {c["ip"] for c in clusters}
    assert ips == {"10.0.0.1", "10.0.0.2"}


def test_cluster_separates_different_labels(db: SASession):
    """同 IP 不同 label 应分别聚类"""
    from services.alert_cluster import cluster_events
    _seed_events(db, "10.0.0.1", "SSH暴力破解", 3)
    _seed_events(db, "10.0.0.1", "端口扫描", 2)
    clusters = cluster_events(db, hours=24)
    assert len(clusters) == 2


def test_cluster_sorted_by_count(db: SASession):
    """聚类结果应按 total_count 降序排列"""
    from services.alert_cluster import cluster_events
    _seed_events(db, "10.0.0.1", "SSH暴力破解", 10)
    _seed_events(db, "10.0.0.2", "端口扫描", 3)
    clusters = cluster_events(db, hours=24)
    assert clusters[0]["total_count"] >= clusters[1]["total_count"]


def test_cluster_empty(db: SASession):
    """无告警时应返回空列表"""
    from services.alert_cluster import cluster_events
    clusters = cluster_events(db, hours=24)
    assert clusters == []


# ── API 端点 ──

def test_clusters_api(client: TestClient, admin_token: str, db: SASession):
    """GET /defense/events/clusters 应返回聚类结果"""
    _seed_events(db, "192.168.1.1", "HTTP探测", 4)
    res = client.get(
        "/api/v1/defense/events/clusters?hours=24",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total_clusters"] >= 1
    assert data["clusters"][0]["total_count"] == 4


def test_clusters_api_empty(client: TestClient, admin_token: str):
    """无告警时 API 应返回空聚类"""
    res = client.get(
        "/api/v1/defense/events/clusters?hours=24",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["total_clusters"] == 0
    assert data["clusters"] == []
