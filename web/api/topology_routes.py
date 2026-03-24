from flask import Blueprint, request

from database.models import TopologyModel
from .helpers import require_auth, ok, err

topology_bp = Blueprint('topology', __name__, url_prefix='/api/v1/topology')


@topology_bp.route('', methods=['GET'])
@require_auth
def get_topology():
    """Get the current topology layout."""
    return ok(TopologyModel.get_topology())


@topology_bp.route('', methods=['POST'])
@require_auth
def save_topology():
    """Save the updated topology layout."""
    data = request.json
    if not isinstance(data, dict) or 'nodes' not in data or 'links' not in data:
        return err('Invalid topology data')

    TopologyModel.save_topology(data)
    return ok({'message': 'Topology saved successfully'})

