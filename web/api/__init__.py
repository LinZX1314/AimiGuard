"""
AimiGuard API Module
Integrates all API blueprints
"""

# Import and register all sub-modules
from .auth import auth_bp
from .overview import overview_bp
from .defense import defense_bp
from .scan import scan_bp
from .ai import ai_bp
from .system import system_bp
from .settings import settings_bp
from .nmap_routes import nmap_bp
from .legacy import legacy_bp


def register_blueprints(app):
    """Register all blueprints to Flask app"""
    # 各模块 blueprint 已声明最终对外路径，这里直接注册，避免 url_prefix 覆盖子蓝图前缀。
    app.register_blueprint(auth_bp)
    app.register_blueprint(overview_bp)
    app.register_blueprint(defense_bp)
    app.register_blueprint(scan_bp)
    app.register_blueprint(ai_bp, url_prefix='/api/v1/ai')
    app.register_blueprint(system_bp)
    app.register_blueprint(settings_bp, url_prefix='/api/v1')
    app.register_blueprint(nmap_bp)
    app.register_blueprint(legacy_bp)


# Export for external use
__all__ = [
    'register_blueprints',
    'auth_bp',
    'overview_bp',
    'defense_bp',
    'scan_bp',
    'ai_bp',
    'system_bp',
    'settings_bp',
    'nmap_bp',
    'legacy_bp',
]
