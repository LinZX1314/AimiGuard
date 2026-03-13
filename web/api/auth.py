"""
Auth Module - Authentication endpoints
"""
from flask import Blueprint, jsonify, g
from .helpers import (
    require_auth, ok, err, _body, _load_cfg, _make_token, _DEFAULT_USERS
)

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['POST'])
def auth_login():
    """User login"""
    body = _body()
    username = body.get('username', '').strip()
    password = body.get('password', '').strip()

    cfg = _load_cfg()
    users = cfg.get('users', _DEFAULT_USERS)
    matched = next((u for u in users if u['username'] == username and u['password'] == password), None)
    if not matched:
        return err('用户名或密码错误', 401)

    user_info = {
        'username': matched['username'],
        'role': matched.get('role', 'operator'),
        'permissions': matched.get('permissions', ['*']),
    }
    token = _make_token({'sub': username, **user_info})
    return jsonify({
        'access_token': token,
        'token_type': 'bearer',
        'user': user_info,
    })


@auth_bp.route('/logout', methods=['POST'])
def auth_logout():
    """User logout"""
    return ok()


@auth_bp.route('/refresh', methods=['POST'])
@require_auth
def auth_refresh():
    """Refresh token"""
    token = _make_token({k: v for k, v in g.user.items() if k != 'exp'})
    return jsonify({'access_token': token, 'token_type': 'bearer'})


@auth_bp.route('/profile', methods=['GET'])
@require_auth
def auth_profile():
    """Get user profile"""
    return ok({
        'username': g.user.get('username'),
        'role': g.user.get('role'),
        'permissions': g.user.get('permissions', [])
    })
