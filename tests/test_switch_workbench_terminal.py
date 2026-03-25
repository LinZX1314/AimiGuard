from web.flask_app import create_app, socketio
from web.api.helpers import _make_token


def _auth_headers():
    token = _make_token({'username': 'tester', 'role': 'admin'})
    return {'Authorization': f'Bearer {token}'}


def test_manual_command_not_blocked_by_readonly(monkeypatch):
    app = create_app()
    client = app.test_client()

    device = {
        'id': 1,
        'name': 'SW-01',
        'host': '192.168.0.2',
        'port': 23,
        'readonly_only': True,
    }

    monkeypatch.setattr('web.api.switch_workbench._resolve_device', lambda *args, **kwargs: device)
    monkeypatch.setattr('web.api.switch_workbench._execute_telnet_command', lambda *_args, **_kwargs: 'ok')
    monkeypatch.setattr('web.api.switch_workbench._summarize_output', lambda *_args, **_kwargs: 'summary')
    monkeypatch.setattr('database.models.SwitchWorkbenchModel.add_command_run', lambda **_kwargs: 1)

    response = client.post('/api/v1/switch-workbench/commands/run', json={
        'device_id': 1,
        'command': 'system-view',
        'source': 'manual',
    }, headers=_auth_headers())

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['code'] == 0
    assert payload['data']['status'] == 'success'
    assert payload['data']['command'] == 'system-view'
    assert payload['data']['source'] == 'manual'


def test_socketio_initialized():
    app = create_app()
    assert app is not None
    assert socketio is not None
