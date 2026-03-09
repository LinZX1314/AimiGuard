"""Audit service tests — hash chain integrity, trace_id, and chain verification."""
import pytest
from services.audit_service import AuditService, _compute_hash
from core.database import AuditLog


def _clear_audit(db):
    """Clear audit_log table for chain-sensitive tests."""
    db.query(AuditLog).delete()
    db.commit()


# ── Basic logging ──

def test_audit_log_creates_record(db):
    entry = AuditService.log(db, actor="admin", action="login", target="system")
    assert entry.id is not None
    assert entry.actor == "admin"
    assert entry.action == "login"
    assert entry.target == "system"
    assert entry.result == "success"
    assert entry.trace_id is not None
    assert entry.integrity_hash is not None


def test_audit_log_custom_fields(db):
    entry = AuditService.log(
        db, actor="operator", action="block_ip", target="192.168.1.100",
        result="success", target_type="ip", target_ip="10.0.0.1",
        reason="Suspicious traffic", trace_id="custom-trace-001",
    )
    assert entry.target_type == "ip"
    assert entry.target_ip == "10.0.0.1"
    assert entry.reason == "Suspicious traffic"
    assert entry.trace_id == "custom-trace-001"


def test_audit_log_error_message(db):
    entry = AuditService.log(
        db, actor="system", action="backup", target="database",
        result="failed", error_message="Disk full",
    )
    assert entry.result == "failed"
    assert entry.error_message == "Disk full"


def test_audit_log_normalizes_uppercase_result(db):
    entry = AuditService.log(
        db, actor="scheduler", action="hfish_auto_sync", target="hfish_collector",
        result="SUCCESS", error_message="无新数据",
    )
    assert entry.result == "success"
    assert entry.error_message == "无新数据"


def test_audit_log_normalizes_alias_result(db):
    entry = AuditService.log(
        db, actor="security_test", action="hardening_check", target="system",
        result="pass", trace_id="audit-pass-normalized",
    )
    assert entry.result == "success"
    assert entry.trace_id == "audit-pass-normalized"


def test_audit_log_auto_generates_trace_id(db):
    entry = AuditService.log(db, actor="admin", action="test", target="x")
    assert entry.trace_id is not None
    assert len(entry.trace_id) == 36  # UUID format


# ── Hash chain ──

def test_first_entry_uses_genesis(db):
    _clear_audit(db)
    entry = AuditService.log(db, actor="admin", action="init", target="system")
    assert entry.prev_hash == "GENESIS"


def test_chain_links_to_previous(db):
    _clear_audit(db)
    e1 = AuditService.log(db, actor="admin", action="a1", target="t1")
    e2 = AuditService.log(db, actor="admin", action="a2", target="t2")
    assert e2.prev_hash == e1.integrity_hash
    assert e2.prev_hash != "GENESIS"


def test_three_entry_chain(db):
    _clear_audit(db)
    e1 = AuditService.log(db, actor="a", action="x1", target="t")
    e2 = AuditService.log(db, actor="a", action="x2", target="t")
    e3 = AuditService.log(db, actor="a", action="x3", target="t")
    assert e1.prev_hash == "GENESIS"
    assert e2.prev_hash == e1.integrity_hash
    assert e3.prev_hash == e2.integrity_hash
    assert len({e1.integrity_hash, e2.integrity_hash, e3.integrity_hash}) == 3


def test_integrity_hash_is_deterministic():
    h1 = _compute_hash("a", "b", "c", "d", "e", "f", "g")
    h2 = _compute_hash("a", "b", "c", "d", "e", "f", "g")
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex digest


def test_integrity_hash_changes_with_input():
    h1 = _compute_hash("a", "b", "c", "d", "e", "f", "g")
    h2 = _compute_hash("a", "b", "c", "d", "e", "f", "DIFFERENT")
    assert h1 != h2


# ── Chain verification ──

def test_verify_chain_empty(db):
    _clear_audit(db)
    result = AuditService.verify_chain(db)
    assert result["valid"] is True
    assert result["checked"] == 0
    assert result["broken_at"] is None


def test_verify_chain_valid(db):
    _clear_audit(db)
    AuditService.log(db, actor="a", action="x1", target="t")
    AuditService.log(db, actor="a", action="x2", target="t")
    AuditService.log(db, actor="a", action="x3", target="t")
    result = AuditService.verify_chain(db)
    assert result["valid"] is True
    assert result["checked"] == 3
    assert result["broken_at"] is None


def test_verify_chain_detects_tampered_hash(db):
    _clear_audit(db)
    AuditService.log(db, actor="a", action="x1", target="t")
    e2 = AuditService.log(db, actor="a", action="x2", target="t")
    # Tamper with the integrity hash
    e2.integrity_hash = "0000000000000000000000000000000000000000000000000000000000000000"
    db.commit()
    result = AuditService.verify_chain(db)
    assert result["valid"] is False
    assert result["broken_at"] == e2.id


def test_verify_chain_detects_broken_prev_hash(db):
    _clear_audit(db)
    AuditService.log(db, actor="a", action="x1", target="t")
    e2 = AuditService.log(db, actor="a", action="x2", target="t")
    AuditService.log(db, actor="a", action="x3", target="t")
    # Break the chain link
    e2.prev_hash = "TAMPERED"
    db.commit()
    db.expire_all()
    result = AuditService.verify_chain(db)
    assert result["valid"] is False


def test_verify_chain_limit(db):
    _clear_audit(db)
    for i in range(5):
        AuditService.log(db, actor="a", action=f"x{i}", target="t")
    result = AuditService.verify_chain(db, limit=3)
    assert result["valid"] is True
    assert result["checked"] == 3


# ── auto_commit=False ──

def test_audit_log_no_auto_commit(db):
    entry = AuditService.log(
        db, actor="admin", action="test", target="x", auto_commit=False,
    )
    assert entry.actor == "admin"
    # Manually commit to persist
    db.commit()
    found = db.query(AuditLog).filter(AuditLog.id == entry.id).first()
    assert found is not None
