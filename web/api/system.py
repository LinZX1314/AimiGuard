"""
System Module - System configuration and profile endpoints
"""
from flask import Blueprint
from .helpers import (
    require_auth, ok, err, _body, _load_cfg, _save_cfg,
    _as_bool
)

system_bp = Blueprint('system', __name__, url_prefix='/api/v1/system')


@system_bp.route('/ai-whitelist', methods=['GET'])
@require_auth
def system_ai_whitelist_get():
    """Get AI ban whitelist"""
    cfg = _load_cfg()
    whitelist = cfg.get('ai', {}).get('whitelist', [])
    return ok({'whitelist': whitelist})


@system_bp.route('/ai-whitelist', methods=['POST'])
@require_auth
def system_ai_whitelist_save():
    """Save AI ban whitelist"""
    body = _body()
    cfg = _load_cfg()
    ai = cfg.setdefault('ai', {})
    if 'whitelist' in body:
        raw = body['whitelist']
        if isinstance(raw, list):
            ai['whitelist'] = [ip.strip() for ip in raw if ip.strip()]
        elif isinstance(raw, str):
            ai['whitelist'] = [ip.strip() for ip in raw.split('\n') if ip.strip()]
    _save_cfg(cfg)
    return ok({'whitelist': ai.get('whitelist', [])})


