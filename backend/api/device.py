"""设备（交换机）与凭证管理 API"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

from core.database import get_db, Device, Credential, User
from api.auth import require_permissions
from services import crypto_service

router = APIRouter(prefix="/api/v1/device", tags=["device"])


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat().replace("+00:00", "Z") if dt else None


# ── Schemas ──

class DeviceCreate(BaseModel):
    name: str
    ip: str
    port: int = 23
    vendor: str
    device_type: Optional[str] = None
    enabled: bool = True
    description: Optional[str] = None


class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    ip: Optional[str] = None
    port: Optional[int] = None
    vendor: Optional[str] = None
    device_type: Optional[str] = None
    enabled: Optional[bool] = None
    description: Optional[str] = None


class CredentialCreate(BaseModel):
    username: str
    password: str


class CredentialUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None


def _device_dict(d: Device, credentials: Optional[list] = None) -> dict:
    out = {
        "id": d.id,
        "name": d.name,
        "ip": d.ip,
        "port": d.port,
        "vendor": d.vendor,
        "device_type": d.device_type,
        "enabled": bool(d.enabled),
        "description": d.description,
        "created_at": _iso(d.created_at),
        "updated_at": _iso(d.updated_at),
    }
    if credentials is not None:
        out["credentials"] = credentials
    return out


def _credential_dict(c: Credential) -> dict:
    return {
        "id": c.id,
        "device_id": c.device_id,
        "username": c.username,
        "created_at": _iso(c.created_at),
        "updated_at": _iso(c.updated_at),
    }


# ── 设备 CRUD ──

@router.get("/list")
async def list_devices(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions(["system:config"])),
):
    devices = db.query(Device).order_by(Device.id.desc()).all()
    result = []
    for d in devices:
        creds = db.query(Credential).filter(Credential.device_id == d.id).all()
        result.append(_device_dict(d, [_credential_dict(c) for c in creds]))
    return {"code": 0, "data": result}


@router.post("/create")
async def create_device(
    payload: DeviceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions(["system:config"])),
):
    existing = db.query(Device).filter(Device.name == payload.name).first()
    if existing:
        raise HTTPException(400, f"设备名 '{payload.name}' 已存在")

    device = Device(
        name=payload.name,
        ip=payload.ip,
        port=payload.port,
        vendor=payload.vendor,
        device_type=payload.device_type,
        enabled=1 if payload.enabled else 0,
        description=payload.description,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return {"code": 0, "data": _device_dict(device, []), "message": "设备已创建"}


@router.put("/{device_id}")
async def update_device(
    device_id: int,
    payload: DeviceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions(["system:config"])),
):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(404, "设备不存在")

    if payload.name is not None:
        dup = db.query(Device).filter(Device.name == payload.name, Device.id != device_id).first()
        if dup:
            raise HTTPException(400, f"设备名 '{payload.name}' 已被占用")
        device.name = payload.name
    if payload.ip is not None:
        device.ip = payload.ip
    if payload.port is not None:
        device.port = payload.port
    if payload.vendor is not None:
        device.vendor = payload.vendor
    if payload.device_type is not None:
        device.device_type = payload.device_type
    if payload.enabled is not None:
        device.enabled = 1 if payload.enabled else 0
    if payload.description is not None:
        device.description = payload.description

    device.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(device)
    return {"code": 0, "data": _device_dict(device), "message": "设备已更新"}


@router.delete("/{device_id}")
async def delete_device(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions(["system:config"])),
):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(404, "设备不存在")

    db.query(Credential).filter(Credential.device_id == device_id).delete()
    db.delete(device)
    db.commit()
    return {"code": 0, "message": "设备及关联凭证已删除"}


# ── 凭证 CRUD ──

@router.get("/{device_id}/credentials")
async def list_credentials(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions(["system:config"])),
):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(404, "设备不存在")

    creds = db.query(Credential).filter(Credential.device_id == device_id).order_by(Credential.id).all()
    return {"code": 0, "data": [_credential_dict(c) for c in creds]}


@router.post("/{device_id}/credentials")
async def add_credential(
    device_id: int,
    payload: CredentialCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions(["system:config"])),
):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(404, "设备不存在")

    ciphertext, key_version = crypto_service.encrypt(payload.password)
    cred = Credential(
        device_id=device_id,
        username=payload.username,
        secret_ciphertext=ciphertext,
        key_version=key_version,
    )
    db.add(cred)
    db.commit()
    db.refresh(cred)
    return {"code": 0, "data": _credential_dict(cred), "message": "凭证已添加"}


@router.put("/{device_id}/credentials/{cred_id}")
async def update_credential(
    device_id: int,
    cred_id: int,
    payload: CredentialUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions(["system:config"])),
):
    cred = db.query(Credential).filter(
        Credential.id == cred_id, Credential.device_id == device_id
    ).first()
    if not cred:
        raise HTTPException(404, "凭证不存在")

    if payload.username is not None:
        cred.username = payload.username
    if payload.password is not None:
        ciphertext, key_version = crypto_service.encrypt(payload.password)
        cred.secret_ciphertext = ciphertext
        cred.key_version = key_version

    cred.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(cred)
    return {"code": 0, "data": _credential_dict(cred), "message": "凭证已更新"}


@router.post("/{device_id}/test")
async def test_device_connection(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions(["system:config"])),
):
    """测试交换机连接（TCP 端口可达性）"""
    import socket

    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(404, "设备不存在")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((device.ip, device.port))
        sock.close()
        if result == 0:
            return {"code": 0, "ok": True, "message": f"{device.ip}:{device.port} 连接成功"}
        return {"code": 1, "ok": False, "message": f"{device.ip}:{device.port} 端口不可达"}
    except socket.timeout:
        return {"code": 1, "ok": False, "message": f"{device.ip}:{device.port} 连接超时"}
    except Exception as e:
        return {"code": 1, "ok": False, "message": str(e)}


@router.delete("/{device_id}/credentials/{cred_id}")
async def delete_credential(
    device_id: int,
    cred_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions(["system:config"])),
):
    cred = db.query(Credential).filter(
        Credential.id == cred_id, Credential.device_id == device_id
    ).first()
    if not cred:
        raise HTTPException(404, "凭证不存在")

    db.delete(cred)
    db.commit()
    return {"code": 0, "message": "凭证已删除"}
