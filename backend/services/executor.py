"""
执行器服务 — 任务编排、队列执行、重试与幂等

功能：
  1. 提交执行任务（封禁/解封/扫描触发等）
  2. 指数退避重试机制
  3. 幂等检查（同一 event_id + action 避免重复）
  4. 任务状态管理（QUEUED → RUNNING → SUCCESS/FAILED）
  5. 超时与失败处理

注意：ExecutionTask 模型字段：
  - state (非 status): QUEUED / RUNNING / SUCCESS / FAILED
  - event_id: 关联 threat_event.id
  - 无 ip 列（IP 在关联的 ThreatEvent 上）
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from core.database import ExecutionTask

logger = logging.getLogger("executor")

MAX_RETRIES = 3
BASE_RETRY_DELAY = 1.0


class ExecutorService:
    """任务执行器"""

    @staticmethod
    def is_duplicate(db: Session, event_id: int, action: str) -> bool:
        """幂等检查 — 同一 event_id 同一动作是否已有待处理/运行中任务"""
        existing = (
            db.query(ExecutionTask)
            .filter(
                ExecutionTask.event_id == event_id,
                ExecutionTask.action == action,
                ExecutionTask.state.in_(["QUEUED", "RUNNING"]),
            )
            .first()
        )
        return existing is not None

    @staticmethod
    def submit_task(
        db: Session,
        *,
        event_id: int,
        action: str,
        approved_by: Optional[str] = None,
        trace_id: str = "",
    ) -> Optional[ExecutionTask]:
        """
        提交执行任务

        Returns:
            ExecutionTask if created, None if duplicate
        """
        if ExecutorService.is_duplicate(db, event_id, action):
            logger.info("Duplicate task skipped: event_id=%s action=%s", event_id, action)
            return None

        now = datetime.now(timezone.utc)
        task = ExecutionTask(
            event_id=event_id,
            action=action,
            state="QUEUED",
            approved_by=approved_by,
            trace_id=trace_id,
            retry_count=0,
            created_at=now,
            updated_at=now,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    @staticmethod
    def mark_running(db: Session, task_id: int) -> bool:
        """将任务标记为运行中"""
        task = db.query(ExecutionTask).filter(ExecutionTask.id == task_id).first()
        if not task or task.state != "QUEUED":
            return False
        task.state = "RUNNING"
        task.started_at = datetime.now(timezone.utc)
        task.updated_at = datetime.now(timezone.utc)
        db.commit()
        return True

    @staticmethod
    def mark_success(db: Session, task_id: int) -> bool:
        """将任务标记为成功"""
        task = db.query(ExecutionTask).filter(ExecutionTask.id == task_id).first()
        if not task:
            return False
        task.state = "SUCCESS"
        task.ended_at = datetime.now(timezone.utc)
        task.updated_at = datetime.now(timezone.utc)
        db.commit()
        return True

    @staticmethod
    def mark_failed(db: Session, task_id: int, error: str = "") -> bool:
        """将任务标记为失败"""
        task = db.query(ExecutionTask).filter(ExecutionTask.id == task_id).first()
        if not task:
            return False
        task.state = "FAILED"
        task.error_message = error
        task.ended_at = datetime.now(timezone.utc)
        task.updated_at = datetime.now(timezone.utc)
        db.commit()
        return True

    @staticmethod
    def should_retry(db: Session, task_id: int) -> bool:
        """检查任务是否可以重试"""
        task = db.query(ExecutionTask).filter(ExecutionTask.id == task_id).first()
        if not task:
            return False
        return task.state == "FAILED" and (task.retry_count or 0) < MAX_RETRIES

    @staticmethod
    def increment_retry(db: Session, task_id: int) -> int:
        """增加重试计数并重置为 RUNNING"""
        task = db.query(ExecutionTask).filter(ExecutionTask.id == task_id).first()
        if not task:
            return -1
        task.retry_count = (task.retry_count or 0) + 1
        task.state = "RUNNING"
        task.updated_at = datetime.now(timezone.utc)
        db.commit()
        return task.retry_count

    @staticmethod
    def get_retry_delay(retry_count: int) -> float:
        """指数退避延迟（秒）"""
        return BASE_RETRY_DELAY * (2 ** retry_count)

    @staticmethod
    def get_queued_tasks(db: Session, limit: int = 50) -> list:
        """获取待执行的排队任务"""
        return (
            db.query(ExecutionTask)
            .filter(ExecutionTask.state == "QUEUED")
            .order_by(ExecutionTask.created_at.asc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_task(db: Session, task_id: int) -> Optional[ExecutionTask]:
        """获取任务详情"""
        return db.query(ExecutionTask).filter(ExecutionTask.id == task_id).first()


executor_service = ExecutorService()
