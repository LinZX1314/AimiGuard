"""
System Module - System configuration and profile endpoints
"""
from flask import Blueprint
from .helpers import (
    require_auth, ok, err, _body, _load_cfg, _save_cfg,
    _as_bool, _read_chat_system_prompt
)

system_bp = Blueprint('system', __name__, url_prefix='/system')


@system_bp.route('/ai-config', methods=['GET'])
@require_auth
def system_ai_config_get():
    """Get AI config"""
    cfg = _load_cfg()
    ai = cfg.get('ai', {})
    return ok({
        'provider': ai.get('provider', 'openai-compatible'),
        'base_url': ai.get('api_url', ''),
        'model': ai.get('model', ''),
        'model_name': ai.get('model', ''),
        'enabled': ai.get('enabled', False),
        'auto_ban': ai.get('auto_ban', False),
        'ban_threshold': ai.get('ban_threshold', 80),
        'api_key_configured': bool(ai.get('api_key', '')),
    })


@system_bp.route('/ai-config', methods=['POST'])
@require_auth
def system_ai_config_save():
    """Save AI config"""
    body = _body()
    cfg = _load_cfg()
    ai = cfg.setdefault('ai', {})
    if 'provider' in body:
        ai['provider'] = body['provider']
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
    if 'ban_threshold' in body:
        try:
            ai['ban_threshold'] = int(body['ban_threshold'])
        except Exception:
            pass
    if 'api_key' in body and body['api_key']:
        ai['api_key'] = body['api_key']
    _save_cfg(cfg)
    return ok()


@system_bp.route('/ai-prompt', methods=['GET'])
@require_auth
def system_prompt_get():
    """Get AI prompt"""
    cfg = _load_cfg()
    prompt, migrated = _read_chat_system_prompt(cfg)
    if migrated:
        _save_cfg(cfg)
    return ok({'prompt': prompt})


@system_bp.route('/ai-prompt', methods=['POST'])
@require_auth
def system_prompt_save():
    """Save AI prompt"""
    body = _body()
    prompt = body.get('prompt', '').strip()
    if not prompt:
        return err('提示词不能为空')
    cfg = _load_cfg()
    ai_cfg = cfg.setdefault('ai', {})
    ai_cfg.setdefault('analysis_map', {})['chat_system_prompt'] = prompt
    ai_cfg.pop('system_prompt', None)
    _save_cfg(cfg)
    return ok()
