"""In-app notification service for system alerts and event notifications."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from core.database import Notification, User

logger = logging.getLogger(__name__)


class NotificationService:

    @staticmethod
    def create(
        db: Any,
        *,
        title: str,
        content: str = "",
        category: str = "system",
        severity: str = "info",
        link: str = "",
        trace_id: str = "",
        user_id: Optional[int] = None,
    ) -> Optional[int]:
        """Create a notification. If user_id is None, broadcast to all users."""
        try:
            if user_id is not None:
                n = Notification(
                    user_id=user_id,
                    title=title,
                    content=content,
                    category=category,
                    severity=severity,
                    link=link,
                    trace_id=trace_id,
                )
                db.add(n)
                db.commit()
                return n.id
            else:
                users = db.query(User).filter(User.enabled == 1).all()
                ids = []
                for u in users:
                    n = Notification(
                        user_id=u.id,
                        title=title,
                        content=content,
                        category=category,
                        severity=severity,
                        link=link,
                        trace_id=trace_id,
                    )
                    db.add(n)
                    ids.append(n)
                db.commit()
                return ids[0].id if ids else None
        except Exception as exc:
            logger.error("notification_create error: %s", exc)
            try:
                db.rollback()
            except Exception:
                pass
            return None

    @staticmethod
    def broadcast(
        db_session_factory: Any,
        *,
        title: str,
        content: str = "",
        category: str = "system",
        severity: str = "info",
        link: str = "",
        trace_id: str = "",
    ) -> None:
        """Broadcast notification to all enabled users. Safe to call from background tasks."""
        db = db_session_factory()
        try:
            NotificationService.create(
                db,
                title=title,
                content=content,
                category=category,
                severity=severity,
                link=link,
                trace_id=trace_id,
                user_id=None,
            )
        finally:
            db.close()

    @staticmethod
    def list_for_user(
        db: Any,
        user_id: int,
        *,
        limit: int = 50,
        offset: int = 0,
        unread_only: bool = False,
    ) -> Dict[str, Any]:
        q = db.query(Notification).filter(Notification.user_id == user_id)
        if unread_only:
            q = q.filter(Notification.read == 0)
        total = q.count()
        unread = db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.read == 0,
        ).count()
        items = q.order_by(Notification.created_at.desc()).offset(offset).limit(limit).all()
        return {
            "total": total,
            "unread": unread,
            "items": [
                {
                    "id": n.id,
                    "title": n.title,
                    "content": n.content,
                    "category": n.category,
                    "severity": n.severity,
                    "link": n.link,
                    "read": bool(n.read),
                    "trace_id": n.trace_id,
                    "created_at": n.created_at.isoformat().replace("+00:00", "Z") if n.created_at else None,
                }
                for n in items
            ],
        }

    @staticmethod
    def mark_read(db: Any, notification_id: int, user_id: int) -> bool:
        n = db.query(Notification).filter(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        ).first()
        if not n:
            return False
        n.read = 1
        db.commit()
        return True

    @staticmethod
    def mark_all_read(db: Any, user_id: int) -> int:
        count = db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.read == 0,
        ).update({"read": 1})
        db.commit()
        return count
