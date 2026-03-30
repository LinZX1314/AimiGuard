"""
System Module - System configuration and profile endpoints
"""
from flask import Blueprint
from .helpers import (
    require_auth, ok, err, _body, _load_cfg, _save_cfg,
    _as_bool
)

system_bp = Blueprint('system', __name__, url_prefix='/api/v1/system')


@system_bp.route('/ai-config', methods=['GET'])
@require_auth
def system_ai_config_get():
    """Get AI config"""
    cfg = _load_cfg()
    ai = cfg.get('ai', {})
    return ok({
        'base_url': ai.get('api_url', ''),
        'model': ai.get('model', ''),
        'model_name': ai.get('model', ''),
        'enabled': ai.get('enabled', False),
        'auto_ban': ai.get('auto_ban', False),
        'api_key_configured': bool(ai.get('api_key', '')),
    })


@system_bp.route('/ai-config', methods=['POST'])
@require_auth
def system_ai_config_save():
    """Save AI config"""
    body = _body()
    cfg = _load_cfg()
    ai = cfg.setdefault('ai', {})
    if 'base_url' in body:
        ai['api_url'] = body['base_url']
    if 'model' in body:
        ai['model'] = body['model']
    if 'model_name' in body:
        ai['model'] = body['model_name']
    if 'enabled' in body:
        ai['enabled'] = _as_bool(body['enabled'])
    if 'auto_ban' in body:
        ai['auto_ban'] = _as_bool(body['auto_ban'])
    if 'api_key' in body and body['api_key']:
        ai['api_key'] = body['api_key']
    _save_cfg(cfg)
    return ok()


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


