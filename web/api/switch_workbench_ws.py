"""
Switch Workbench WebSocket Module
Provides WebSocket proxy for Telnet connections using Flask-SocketIO
"""
import json
import time
import threading
import telnetlib3 as telnetlib
from flask_socketio import SocketIO, emit, join_room, leave_room

# SocketIO instance - will be initialized when app is created
socketio: SocketIO = None

# Store active telnet connections per session
_telnet_connections: dict = {}


def init_socketio(socketio_instance: SocketIO):
    """Initialize SocketIO instance and register handlers"""
    global socketio
    socketio = socketio_instance
    register_handlers()


def register_handlers():
    """Register WebSocket event handlers"""

    @socketio.on('connect', namespace='/ws/switch-workbench/telnet')
    def handle_connect():
        print('[SwitchWorkbench WS] Client connected')
        emit('connected', {'status': 'connected'})

    @socketio.on('disconnect', namespace='/ws/switch-workbench/telnet')
    def handle_disconnect():
        print('[SwitchWorkbench WS] Client disconnected')

    @socketio.on('join', namespace='/ws/switch-workbench/telnet')
    def handle_join(data):
        session_id = data.get('session_id', 'default')
        join_room(session_id)
        emit('joined', {'session_id': session_id})

    @socketio.on('leave', namespace='/ws/switch-workbench/telnet')
    def handle_leave(data):
        session_id = data.get('session_id', 'default')
        leave_room(session_id)

    @socketio.on('connect_device', namespace='/ws/switch-workbench/telnet')
    def handle_connect_device(data):
        """Handle device connection request"""
        session_id = data.get('session_id', 'default')
        device_info = data.get('device', {})

        host = device_info.get('ip') or device_info.get('host')
        port = int(device_info.get('port', 23))
        username = device_info.get('username', '')
        password = device_info.get('password', '')

        if not host:
            emit('error', {'message': '缺少主机地址'}, room=session_id)
            return

        try:
            # Create telnet connection
            tn = telnetlib.Telnet(host, port, 8)
            time.sleep(1.5)

            # Read initial banner
            banner = _read_telnet_buffer(tn)

            # Login if needed
            if 'password' in banner.lower():
                tn.write((password + '\r').encode('utf-8'))
                time.sleep(1.0)
                banner += '\n' + _read_telnet_buffer(tn)

            # Store connection
            _telnet_connections[session_id] = {
                'tn': tn,
                'host': host,
                'port': port,
            }

            emit('connected', {
                'banner': banner,
                'host': host,
                'port': port,
            }, room=session_id)

        except Exception as exc:
            emit('error', {'message': f'连接失败: {str(exc)}'}, room=session_id)

    @socketio.on('send_command', namespace='/ws/switch-workbench/telnet')
    def handle_send_command(data):
        """Handle command send request"""
        session_id = data.get('session_id', 'default')
        command = data.get('command', '')

        if not command:
            emit('error', {'message': '命令不能为空'}, room=session_id)
            return

        conn = _telnet_connections.get(session_id)
        if not conn:
            emit('error', {'message': '未连接到设备'}, room=session_id)
            return

        try:
            tn = conn['tn']

            # Send command
            tn.write((command + '\r').encode('utf-8'))
            time.sleep(1.2)

            # Read response
            response = _read_telnet_buffer(tn)

            emit('command_output', {
                'command': command,
                'output': response,
            }, room=session_id)

        except Exception as exc:
            emit('error', {'message': f'命令执行失败: {str(exc)}'}, room=session_id)

    @socketio.on('disconnect_device', namespace='/ws/switch-workbench/telnet')
    def handle_disconnect_device(data):
        """Handle device disconnect request"""
        session_id = data.get('session_id', 'default')

        conn = _telnet_connections.pop(session_id, None)
        if conn and conn.get('tn'):
            try:
                conn['tn'].close()
            except Exception:
                pass

        emit('disconnected', {'message': '已断开连接'}, room=session_id)


def _read_telnet_buffer(tn) -> str:
    """Read and decode telnet buffer"""
    try:
        chunk = tn.read_very_eager()
    except Exception:
        return ''
    if isinstance(chunk, bytes):
        return chunk.decode('utf-8', errors='ignore')
    return str(chunk or '')
