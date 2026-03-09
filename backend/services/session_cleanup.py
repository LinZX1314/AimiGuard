"""会话清理服务"""
from sqlalchemy.orm import Session
from core.database import AIChatSession, AIChatMessage
import logging

logger = logging.getLogger(__name__)


class SessionCleanupService:
    """会话管理服务"""

    @staticmethod
    def delete_session(db: Session, session_id: int) -> bool:
        """删除会话及其所有消息"""
        session = db.query(AIChatSession).filter(AIChatSession.id == session_id).first()
        if not session:
            return False

        db.query(AIChatMessage).filter(
            AIChatMessage.session_id == session_id
        ).delete()
        db.delete(session)

        db.commit()
        logger.info(f"Deleted session {session_id}")
        return True
