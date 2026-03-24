"""
AimiGuard API Module
Integrates all API blueprints
"""

# Import and register all sub-modules
from .auth import auth_bp
from .overview import overview_bp
from .defense import defense_bp
from .ai import ai_bp
from .workflow import workflow_bp
from .system import system_bp
from .nmap_routes import nmap_bp
from .switch_workbench import switch_workbench_bp
from .topology_routes import topology_bp
from .legacy import legacy_bp


def register_blueprints(app):
    """Register all blueprints to Flask app"""
    app.register_blueprint(auth_bp)
    app.register_blueprint(overview_bp)
    app.register_blueprint(defense_bp)
    app.register_blueprint(ai_bp, url_prefix='/api/v1/ai')
    app.register_blueprint(workflow_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(nmap_bp)
    app.register_blueprint(switch_workbench_bp)
    app.register_blueprint(topology_bp)
    app.register_blueprint(legacy_bp)


# Export for external use
__all__ = [
    'register_blueprints',
    'auth_bp',
    'overview_bp',
    'defense_bp',
    'nmap_bp',
    'ai_bp',
    'workflow_bp',
    'system_bp',
    'switch_workbench_bp',
    'legacy_bp',
]
