"""
Helper module - Shared utilities for API modules
Contains: imports, config, JWT, decorators, response helpers
"""
from __future__ import annotations
import os, sys, json, hmac, hashlib, base64, time, threading
from datetime import datetime
from functools import wraps
from flask import Blueprint, request, jsonify, g

# ─── path setup ───────────────────────────────────────────────────────────────
# BASE_DIR should be the project root (parent of web)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
WEB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WEB_DIR not in sys.path:
    sys.path.insert(0, WEB_DIR)

from database.models import (
    NmapModel, VulnModel, HFishModel, AiModel
)
from utils.logger import log as unified_log

CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')

# ─── Config Functions ───────────────────────────────────────────────────────
def _load_cfg():
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def _save_cfg(cfg):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

# ─── JWT Config ───────────────────────────────────────────────────────────────
_JWT_SECRET = os.environ.get('AIMIGUARD_SECRET', 'aimiguard-secret-key-2026')
_JWT_TTL = 86400 * 7  # 7 days
_DEFAULT_USERS = [{'username': 'admin', 'password': 'admin123', 'role': 'admin'}]

# ─── JWT Functions ───────────────────────────────────────────────────────────
def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()

def _b64d(s: str) -> bytes:
    pad = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + '=' * (pad % 4))

def _make_token(payload: dict) -> str:
    hdr = _b64e(json.dumps({'typ': 'JWT', 'alg': 'HS256'}).encode())
    pld = _b64e(json.dumps({**payload, 'exp': int(time.time()) + _JWT_TTL}).encode())
    sig = _b64e(hmac.new(_JWT_SECRET.encode(), f'{hdr}.{pld}'.encode(), hashlib.sha256).digest())
    return f'{hdr}.{pld}.{sig}'

def _decode_token(token: str) -> dict | None:
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        hdr, pld, sig = parts
        expected = _b64e(hmac.new(_JWT_SECRET.encode(), f'{hdr}.{pld}'.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(_b64d(pld))
        if payload.get('exp', 0) < time.time():
            return None
        return payload
    except Exception:
        return None

# ─── Auth Decorator ───────────────────────────────────────────────────────
def require_auth(f):
    """Simple Bearer auth decorator"""
    @wraps(f)
    def wrapped(*args, **kwargs):
        header = request.headers.get('Authorization', '')
        token = header.removeprefix('Bearer ').strip()

        if request.path == '/api/v1/ai/chat':
            auth_header = request.headers.get('Authorization', '')
            unified_log(
                'AIChat',
                f'入口命中 path={request.path} from={request.remote_addr} pid={os.getpid()} auth={"yes" if auth_header else "no"}',
                'INFO'
            )

        payload = _decode_token(token)
        if payload is None:
            if request.path == '/api/v1/ai/chat':
                unified_log('AIChat', '鉴权失败: token 缺失、格式错误或已过期', 'WARN')
            return jsonify({'code': 401, 'message': '未授权'}), 401
        g.user = payload
        return f(*args, **kwargs)
    return wrapped

# ─── Response Helpers ───────────────────────────────────────────────────────
def ok(data=None, **extra):
    """统一成功响应结构"""
    return jsonify({'code': 0, 'message': 'ok', 'data': data, **extra})

def err(msg, code=400):
    """统一错误响应结构"""
    return jsonify({'code': code, 'message': msg}), code

# ─── Common Helpers ───────────────────────────────────────────────────────
def _now_iso() -> str:
    return datetime.now().isoformat()

def _body() -> dict:
    return request.get_json(force=True) or {}

def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in ('1', 'true', 'yes', 'on')
    return bool(value)

def _parse_int_arg(name: str, default: int) -> int:
    raw = request.args.get(name, default)
    try:
        return int(raw)
    except Exception:
        return default

def _run_daemon(task):
    threading.Thread(target=task, daemon=True).start()

def _normalize_host_fields(host: dict | None) -> dict | None:
    if not host:
        return host
    for key in ('open_ports', 'services'):
        value = host.get(key)
        if isinstance(value, str) and value:
            try:
                host[key] = json.loads(value)
            except Exception:
                host[key] = [p.strip() for p in value.split(',') if p.strip()]
    return host

