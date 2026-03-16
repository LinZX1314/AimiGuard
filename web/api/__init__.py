"""
AimiGuard API Module
Integrates all API blueprints
"""
from flask import Blueprint

# Create main blueprint
v1 = Blueprint('v1', __name__, url_prefix='/api/v1')

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
    app.register_blueprint(auth_bp, url_prefix='/api/v1/auth')
    app.register_blueprint(overview_bp, url_prefix='/api/v1')
    app.register_blueprint(defense_bp, url_prefix='/api/v1/defense')
    app.register_blueprint(scan_bp, url_prefix='/api/v1')
    app.register_blueprint(ai_bp, url_prefix='/api/v1/ai')
    app.register_blueprint(system_bp, url_prefix='/api/v1/system')
    app.register_blueprint(settings_bp, url_prefix='/api/v1')
    app.register_blueprint(nmap_bp, url_prefix='/api/v1')
    app.register_blueprint(legacy_bp)


# Export for external use
__all__ = [
    'v1',
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
