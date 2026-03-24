from flask import Blueprint, request
from database.models import TopologyModel
from .helpers import require_auth, ok, err

topology_bp = Blueprint('topology', __name__, url_prefix='/api/v1/topology')

@topology_bp.route('', methods=['GET'])
@require_auth
def get_topology():
    """Get the current topology layout"""
    data = TopologyModel.get_topology()
    return ok(data)

@topology_bp.route('', methods=['POST'])
@require_auth
def save_topology():
    """Save the updated topology layout"""
    data = request.json
    if not data or 'nodes' not in data:
        return err("Invalid topology data")
    
    TopologyModel.save_topology(data)
    return ok({"message": "Topology saved successfully"})
