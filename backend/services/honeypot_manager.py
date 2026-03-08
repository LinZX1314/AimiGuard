"""
D2-01 蜜罐策略管理服务

功能：
  - create_honeypot(config) — 创建蜜罐配置
  - list_honeypots(filters) — 查询蜜罐列表
  - update_honeypot(id, updates) — 更新蜜罐配置
  - get_honeypot(id) — 获取蜜罐详情
  - update_honeytoken(id, status) — 更新蜜标状态
  - decommission_expired() — 清理过期/停用蜜罐
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from core.database import HoneypotConfig, Honeytoken


VALID_TYPES = {"ssh", "http", "ftp", "rdp", "smb", "telnet", "mysql", "redis", "custom"}
VALID_STATUSES = {"ACTIVE", "INACTIVE", "DEPLOYING", "FAILED"}
HONEYTOKEN_STATUSES = {"active", "triggered", "expired", "revoked"}


class HoneypotManager:
    """蜜罐与蜜标生命周期管理"""

    @staticmethod
    def create_honeypot(
        db: Session,
        *,
        name: str,
        honeypot_type: str,
        target_service: Optional[str] = None,
        bait_data: Optional[str] = None,
        trace_id: str = "",
    ) -> HoneypotConfig:
        """创建蜜罐配置"""
        if honeypot_type not in VALID_TYPES:
            raise ValueError(f"Invalid type: {honeypot_type}, must be one of {VALID_TYPES}")

        hp = HoneypotConfig(
            name=name,
            type=honeypot_type,
            target_service=target_service,
            bait_data=bait_data,
            status="INACTIVE",
            trace_id=trace_id,
        )
        db.add(hp)
        db.commit()
        db.refresh(hp)
        return hp

    @staticmethod
    def list_honeypots(
        db: Session,
        *,
        status: Optional[str] = None,
        honeypot_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """查询蜜罐列表（分页）"""
        query = db.query(HoneypotConfig)
        if status:
            query = query.filter(HoneypotConfig.status == status)
        if honeypot_type:
            query = query.filter(HoneypotConfig.type == honeypot_type)

        total = query.count()
        items = (
            query.order_by(HoneypotConfig.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return {"total": total, "page": page, "items": items}

    @staticmethod
    def get_honeypot(db: Session, honeypot_id: int) -> Optional[HoneypotConfig]:
        """获取单个蜜罐详情"""
        return db.query(HoneypotConfig).filter(HoneypotConfig.id == honeypot_id).first()

    @staticmethod
    def update_honeypot(
        db: Session,
        honeypot_id: int,
        *,
        name: Optional[str] = None,
        target_service: Optional[str] = None,
        bait_data: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Optional[HoneypotConfig]:
        """更新蜜罐配置"""
        hp = db.query(HoneypotConfig).filter(HoneypotConfig.id == honeypot_id).first()
        if not hp:
            return None

        updates: dict = {}
        if name is not None:
            updates["name"] = name
        if target_service is not None:
            updates["target_service"] = target_service or None
        if bait_data is not None:
            updates["bait_data"] = bait_data or None
        if status and status in VALID_STATUSES:
            updates["status"] = status

        if updates:
            updates["updated_at"] = datetime.now(timezone.utc)
            db.query(HoneypotConfig).filter(HoneypotConfig.id == honeypot_id).update(updates)
            db.commit()

        return db.query(HoneypotConfig).filter(HoneypotConfig.id == honeypot_id).first()

    @staticmethod
    def update_honeytoken(
        db: Session,
        honeytoken_id: int,
        *,
        status: str,
        attacker_ip: Optional[str] = None,
    ) -> Optional[Honeytoken]:
        """更新蜜标状态（如触发/过期/撤销）"""
        if status not in HONEYTOKEN_STATUSES:
            raise ValueError(f"Invalid status: {status}, must be one of {HONEYTOKEN_STATUSES}")

        ht = db.query(Honeytoken).filter(Honeytoken.id == honeytoken_id).first()
        if not ht:
            return None

        updates = {"status": status, "updated_at": datetime.now(timezone.utc)}
        if status == "triggered":
            updates["triggered_at"] = datetime.now(timezone.utc)
        if attacker_ip:
            updates["attacker_ip"] = attacker_ip

        db.query(Honeytoken).filter(Honeytoken.id == honeytoken_id).update(updates)
        db.commit()
        return db.query(Honeytoken).filter(Honeytoken.id == honeytoken_id).first()

    @staticmethod
    def decommission_expired(db: Session) -> int:
        """将过期的临时蜜罐标记为停用"""
        now = datetime.now(timezone.utc)
        count = (
            db.query(HoneypotConfig)
            .filter(
                HoneypotConfig.status == "ACTIVE",
            )
            .count()
        )
        # 蜜罐本身无过期时间，但蜜标有
        expired_tokens = (
            db.query(Honeytoken)
            .filter(Honeytoken.status == "active")
            .count()
        )
        return count + expired_tokens
