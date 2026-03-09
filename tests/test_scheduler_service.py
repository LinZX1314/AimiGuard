"""SchedulerService tests — start/stop lifecycle, audit logging, error handling."""
import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from services.scheduler_service import SchedulerService, _write_audit, SCHEDULER_ACTOR


# ── Lifecycle ──

@pytest.mark.asyncio
async def test_start_sets_running():
    svc = SchedulerService()
    with patch.object(svc, "_hfish_sync_loop", new_callable=AsyncMock):
        with patch.object(svc, "_nmap_scan_loop", new_callable=AsyncMock):
            await svc.start()
            assert svc.is_running() is True
            await svc.stop()
            assert svc.is_running() is False


@pytest.mark.asyncio
async def test_start_twice_is_noop():
    svc = SchedulerService()
    with patch.object(svc, "_hfish_sync_loop", new_callable=AsyncMock):
        with patch.object(svc, "_nmap_scan_loop", new_callable=AsyncMock):
            await svc.start()
            await svc.start()  # should not raise
            assert svc.is_running() is True
            await svc.stop()


@pytest.mark.asyncio
async def test_stop_twice_is_noop():
    svc = SchedulerService()
    await svc.stop()  # not running, should not raise
    assert svc.is_running() is False


@pytest.mark.asyncio
async def test_stop_cancels_tasks():
    svc = SchedulerService()
    with patch.object(svc, "_hfish_sync_loop", new_callable=AsyncMock):
        with patch.object(svc, "_nmap_scan_loop", new_callable=AsyncMock):
            await svc.start()
            assert svc.hfish_task is not None
            assert svc.nmap_task is not None
            await svc.stop()
            assert svc.is_running() is False


# ── _write_audit ──

def test_write_audit_calls_audit_service():
    mock_db = MagicMock()
    with patch("services.scheduler_service.AuditService") as mock_audit:
        _write_audit(
            mock_db,
            action="test_action",
            target="test_target",
            result="SUCCESS",
            trace_id="tr1",
        )
        mock_audit.log.assert_called_once_with(
            db=mock_db,
            actor=SCHEDULER_ACTOR,
            action="test_action",
            target="test_target",
            target_type="auto_task",
            result="SUCCESS",
            error_message=None,
            trace_id="tr1",
        )


def test_write_audit_handles_exception():
    mock_db = MagicMock()
    with patch("services.scheduler_service.AuditService") as mock_audit:
        mock_audit.log.side_effect = Exception("db error")
        _write_audit(
            mock_db,
            action="fail_action",
            target="fail_target",
            result="FAILED",
            trace_id="tr2",
            error_message="something broke",
        )
        mock_db.rollback.assert_called_once()


def test_write_audit_rollback_also_fails():
    mock_db = MagicMock()
    mock_db.rollback.side_effect = Exception("rollback failed")
    with patch("services.scheduler_service.AuditService") as mock_audit:
        mock_audit.log.side_effect = Exception("db error")
        _write_audit(mock_db, action="a", target="t", result="F", trace_id="tr3")
        # Should not raise despite double failure
