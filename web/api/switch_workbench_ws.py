from __future__ import annotations

import threading
import time
from typing import Any

from flask import request
from flask_socketio import SocketIO, emit, join_room, leave_room

from .helpers import _as_bool, _decode_token
from .switch_workbench import _normalize_switch, _read_telnet_buffer, _resolve_device

try:
    import telnetlib3 as telnetlib
except Exception:
    telnetlib = None

socketio: SocketIO | None = None
_handlers_registered = False
_NAMESPACE = '/ws/switch-workbench/telnet'
_telnet_connections: dict[str, dict[str, Any]] = {}
_telnet_lock = threading.Lock()


def _session_key(raw_session_id: str | None = None) -> str:
    base_sid = request.sid or 'anonymous'
    if raw_session_id:
        return f'{base_sid}:{raw_session_id}'
    return base_sid


def _extract_token(auth: Any | None = None) -> str:
    header = request.headers.get('Authorization', '')
    token = header.removeprefix('Bearer ').strip()
    if not token and isinstance(auth, dict):
        token = str(auth.get('token', '')).strip()
    if not token:
        token = request.args.get('token', '').strip()
    return token


def _emit_room(event: str, payload: dict[str, Any], session_key: str) -> None:
    if socketio is not None:
        socketio.emit(event, payload, room=session_key, namespace=_NAMESPACE)


def _close_socket_connections(base_sid: str) -> None:
    with _telnet_lock:
        keys = [key for key in _telnet_connections if key == base_sid or key.startswith(f'{base_sid}:')]
    for key in keys:
        _close_connection(key)


def _close_connection(session_key: str) -> None:
    with _telnet_lock:
        conn = _telnet_connections.pop(session_key, None)
    if not conn:
        return
    conn['closed'] = True
    try:
        tn = conn.get('tn')
        if tn:
            tn.close()
    except Exception:
        pass


def _reader_loop(session_key: str) -> None:
    while True:
        with _telnet_lock:
            conn = _telnet_connections.get(session_key)
        if not conn or conn.get('closed'):
            break
        try:
            chunk = _read_telnet_buffer(conn['tn'])
        except Exception as exc:
            _emit_room('terminal_error', {'message': f'终端连接异常: {exc}'}, session_key)
            _close_connection(session_key)
            _emit_room('terminal_disconnected', {'message': '终端连接已断开'}, session_key)
            break
        if chunk:
            _emit_room('terminal_output', {'output': chunk}, session_key)
            conn['last_output_at'] = time.time()
        else:
            time.sleep(0.08)


def init_socketio(socketio_instance: SocketIO):
    global socketio
    socketio = socketio_instance
    register_handlers()


def register_handlers():
    global _handlers_registered
    if socketio is None or _handlers_registered:
        return
    _handlers_registered = True

    @socketio.on('connect', namespace=_NAMESPACE)
    def handle_connect(auth=None):
        if _decode_token(_extract_token(auth)) is None:
            return False
        emit('connected', {'status': 'connected'})

    @socketio.on('disconnect', namespace=_NAMESPACE)
    def handle_disconnect():
        _close_socket_connections(request.sid or 'anonymous')

    @socketio.on('join', namespace=_NAMESPACE)
    def handle_join(data):
        session_key = _session_key((data or {}).get('session_id'))
        join_room(session_key)
        emit('joined', {'session_id': session_key})

    @socketio.on('leave', namespace=_NAMESPACE)
    def handle_leave(data):
        session_key = _session_key((data or {}).get('session_id'))
        leave_room(session_key)
        _close_connection(session_key)

    @socketio.on('connect_device', namespace=_NAMESPACE)
    def handle_connect_device(data):
        payload = data or {}
        raw_device = payload.get('device') if isinstance(payload.get('device'), dict) else {}
        session_key = _session_key(payload.get('session_id'))
        host = str(raw_device.get('host') or raw_device.get('ip') or '').strip()
        if not host:
            emit('terminal_error', {'message': '缺少主机地址'})
            return
        if telnetlib is None:
            emit('terminal_error', {'message': 'Telnet 依赖不可用'})
            return

        raw_id = raw_device.get('id')
        if not raw_id and host:
            emit('terminal_error', {'message': '缺少设备标识，禁止直连未登记主机'})
            return

        resolved_device = None
        try:
            resolved_device = _resolve_device(int(raw_id) if raw_id else None, probe=False)
        except Exception:
            resolved_device = None

        if not resolved_device:
            emit('terminal_error', {'message': '未找到已登记的交换机设备'})
            return

        device = resolved_device
        password = device.get('_password', '')
        if not password:
            emit('terminal_error', {'message': '当前交换机未配置 Telnet 密码'})
            return


        _close_connection(session_key)
        try:
            tn = telnetlib.Telnet(device['host'], int(device['port']), 15)
            conn = {
                'tn': tn,
                'device': device,
                'closed': False,
                'last_output_at': time.time(),
            }
            with _telnet_lock:
                _telnet_connections[session_key] = conn
            reader = threading.Thread(target=_reader_loop, args=(session_key,), daemon=True)
            conn['reader'] = reader
            reader.start()

            time.sleep(0.5)
            tn.write((password + '\r').encode('utf-8'))
            time.sleep(0.35)
            secret = device.get('_secret', '')
            if secret:
                tn.write(b'en\r')
                time.sleep(0.2)
                tn.write((secret + '\r').encode('utf-8'))
                time.sleep(0.2)
            paging_disable = device.get('_paging_disable', '')
            vendor = str(device.get('vendor', '')).lower()
            paging_cmd = paging_disable or ('screen-length disable' if 'huawei' in vendor or 'h3c' in vendor else 'terminal length 0')
            if paging_cmd:
                tn.write((paging_cmd + '\r').encode('utf-8'))
            emit('terminal_connected', {
                'device': {
                    'id': device['id'],
                    'name': device['name'],
                    'host': device['host'],
                    'port': device['port'],
                }
            })
        except Exception as exc:
            _close_connection(session_key)
            emit('terminal_error', {'message': f'连接失败: {exc}'})

    @socketio.on('send_command', namespace=_NAMESPACE)
    def handle_send_command(data):
        payload = data or {}
        session_key = _session_key(payload.get('session_id'))
        command = str(payload.get('command', ''))
        if not command:
            emit('terminal_error', {'message': '命令不能为空'}, room=session_key)
            return
        with _telnet_lock:
            conn = _telnet_connections.get(session_key)
        if not conn:
            emit('terminal_error', {'message': '未连接到设备'})
            return
        try:
            conn['tn'].write(command.encode('utf-8'))
        except Exception as exc:
            emit('terminal_error', {'message': f'命令发送失败: {exc}'})
            _close_connection(session_key)
            emit('terminal_disconnected', {'message': '终端连接已断开'})

    @socketio.on('disconnect_device', namespace=_NAMESPACE)
    def handle_disconnect_device(data):
        payload = data or {}
        session_key = _session_key(payload.get('session_id'))
        graceful = _as_bool(payload.get('graceful', True))
        with _telnet_lock:
            conn = _telnet_connections.get(session_key)
        if conn and graceful:
            try:
                conn['tn'].write(b'exit\r')
                time.sleep(0.15)
            except Exception:
                pass
        _close_connection(session_key)
        emit('terminal_disconnected', {'message': '已断开连接'}, room=session_key)
