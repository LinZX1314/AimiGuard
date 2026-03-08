"""
执行器服务测试

覆盖 services/executor.py：
  1. 任务提交与幂等检查
  2. 状态流转（QUEUED → RUNNING → SUCCESS/FAILED）
  3. 重试机制（指数退避）
  4. 排队任务查询
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from services.executor import ExecutorService, MAX_RETRIES, BASE_RETRY_DELAY


class TestSubmitTask:

    def test_submit_success(self, db):
        task = ExecutorService.submit_task(
            db,
            event_id=1,
            action="BLOCK",
            trace_id="exec_test_001",
        )
        assert task is not None
        assert task.event_id == 1
        assert task.action == "BLOCK"
        assert task.state == "QUEUED"

    def test_submit_with_approval(self, db):
        task = ExecutorService.submit_task(
            db,
            event_id=2,
            action="BLOCK",
            approved_by="admin",
            trace_id="exec_test_002",
        )
        assert task is not None
        assert task.approved_by == "admin"
        assert task.state == "QUEUED"

    def test_duplicate_rejected(self, db):
        ExecutorService.submit_task(
            db, event_id=100, action="BLOCK", trace_id="dup1"
        )
        dup = ExecutorService.submit_task(
            db, event_id=100, action="BLOCK", trace_id="dup2"
        )
        assert dup is None

    def test_different_action_not_duplicate(self, db):
        ExecutorService.submit_task(
            db, event_id=101, action="BLOCK", trace_id="d1"
        )
        task2 = ExecutorService.submit_task(
            db, event_id=101, action="UNBLOCK", trace_id="d2"
        )
        assert task2 is not None


class TestIsDuplicate:

    def test_no_duplicate(self, db):
        assert ExecutorService.is_duplicate(db, 9999, "BLOCK") is False

    def test_has_duplicate(self, db):
        ExecutorService.submit_task(
            db, event_id=200, action="BLOCK", trace_id="idup"
        )
        assert ExecutorService.is_duplicate(db, 200, "BLOCK") is True


class TestStatusTransitions:

    def test_mark_running(self, db):
        task = ExecutorService.submit_task(
            db, event_id=300, action="BLOCK", trace_id="st1"
        )
        assert ExecutorService.mark_running(db, task.id) is True
        db.refresh(task)
        assert task.state == "RUNNING"

    def test_mark_success(self, db):
        task = ExecutorService.submit_task(
            db, event_id=301, action="BLOCK", trace_id="st2"
        )
        ExecutorService.mark_running(db, task.id)
        assert ExecutorService.mark_success(db, task.id) is True
        db.refresh(task)
        assert task.state == "SUCCESS"

    def test_mark_failed(self, db):
        task = ExecutorService.submit_task(
            db, event_id=302, action="BLOCK", trace_id="st3"
        )
        ExecutorService.mark_running(db, task.id)
        assert ExecutorService.mark_failed(db, task.id, "timeout") is True
        db.refresh(task)
        assert task.state == "FAILED"

    def test_mark_running_nonexistent(self, db):
        assert ExecutorService.mark_running(db, 99999) is False

    def test_mark_success_nonexistent(self, db):
        assert ExecutorService.mark_success(db, 99999) is False


class TestRetry:

    def test_should_retry_after_failure(self, db):
        task = ExecutorService.submit_task(
            db, event_id=400, action="BLOCK", trace_id="rt1"
        )
        ExecutorService.mark_running(db, task.id)
        ExecutorService.mark_failed(db, task.id, "err")
        assert ExecutorService.should_retry(db, task.id) is True

    def test_no_retry_after_max(self, db):
        task = ExecutorService.submit_task(
            db, event_id=401, action="BLOCK", trace_id="rt2"
        )
        ExecutorService.mark_running(db, task.id)
        ExecutorService.mark_failed(db, task.id, "err")
        for _ in range(MAX_RETRIES):
            ExecutorService.increment_retry(db, task.id)
        ExecutorService.mark_failed(db, task.id, "err")
        assert ExecutorService.should_retry(db, task.id) is False

    def test_increment_retry(self, db):
        task = ExecutorService.submit_task(
            db, event_id=402, action="BLOCK", trace_id="rt3"
        )
        ExecutorService.mark_running(db, task.id)
        ExecutorService.mark_failed(db, task.id, "err")
        count = ExecutorService.increment_retry(db, task.id)
        assert count == 1

    def test_retry_delay_exponential(self):
        assert ExecutorService.get_retry_delay(0) == BASE_RETRY_DELAY
        assert ExecutorService.get_retry_delay(1) == BASE_RETRY_DELAY * 2
        assert ExecutorService.get_retry_delay(2) == BASE_RETRY_DELAY * 4


class TestQueuedTasks:

    def test_get_queued(self, db):
        ExecutorService.submit_task(
            db, event_id=500, action="BLOCK", trace_id="pt1"
        )
        tasks = ExecutorService.get_queued_tasks(db)
        assert any(t.event_id == 500 for t in tasks)

    def test_queued_excludes_running(self, db):
        task = ExecutorService.submit_task(
            db, event_id=501, action="BLOCK", trace_id="pt2"
        )
        ExecutorService.mark_running(db, task.id)
        tasks = ExecutorService.get_queued_tasks(db)
        assert not any(t.event_id == 501 and t.state == "RUNNING" for t in tasks)

    def test_get_task(self, db):
        task = ExecutorService.submit_task(
            db, event_id=502, action="BLOCK", trace_id="pt3"
        )
        found = ExecutorService.get_task(db, task.id)
        assert found is not None
        assert found.event_id == 502

    def test_get_task_nonexistent(self, db):
        assert ExecutorService.get_task(db, 99999) is None
