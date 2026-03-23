from __future__ import annotations

import json
import socket
import time
from datetime import datetime
from typing import Any

from flask import Blueprint, request

from ai import call_openai_chat_completion
from database.models import SwitchWorkbenchModel
from .helpers import require_auth, ok, err, _body, _load_cfg, _parse_int_arg, _as_bool, _save_cfg

switch_workbench_bp = Blueprint('switch_workbench', __name__, url_prefix='/api/v1/switch-workbench')

_DEFAULT_SCRIPTS = [
    {
        'id': 'health-check',
        'title': '批量接口巡检',
        'description': '读取接口摘要、错误计数和波动状态，适合批量健康检查。',
        'scope': 'batch',
        'risk': '只读',
        'commands': ['display interface brief', 'display interface counters'],
    },
    {
        'id': 'acl-audit',
        'title': 'ACL 快速核查',
        'description': '抽取 ACL 与命中统计，交给 AI 判断是否有误封、漏拦截。',
        'scope': 'single',
        'risk': '谨慎',
        'commands': ['display acl all', 'display current-configuration | include acl'],
    },
    {
        'id': 'baseline',
        'title': '配置基线采样',
        'description': '抓取当前配置、版本与保存状态，用于生成配置基线快照。',
        'scope': 'batch',
        'risk': '低风险',
        'commands': ['display version', 'display current-configuration'],
    },
]

_ALLOWED_READONLY_PREFIXES = (
    'display ',
    'show ',
    'dis ',
    'ping ',
    'tracert ',
    'traceroute ',
)


def _guess_group(index: int, vendor: str) -> str:
    lower_vendor = (vendor or '').lower()
    if index == 0 or 'core' in lower_vendor:
        return 'core'
    if index <= 2:
        return 'aggregation'
    return 'access'


def _normalize_switch(sw: dict[str, Any], index: int, probe: bool = False) -> dict[str, Any] | None:
    host = str(sw.get('host', '')).strip()
    if not host:
        return None

    port = int(sw.get('port', 23) or 23)
    enabled = _as_bool(sw.get('enabled', True))
    online = _tcp_probe(host, port) if probe and enabled else bool(enabled)
    status = 'online' if online else 'offline'

    vendor = str(sw.get('vendor', sw.get('brand', 'Generic'))).strip() or 'Generic'
    model = str(sw.get('model', 'Telnet Switch')).strip() or 'Telnet Switch'
    group_id = str(sw.get('group_id', _guess_group(index, vendor))).strip() or 'access'
    name = str(sw.get('name', f'SW-{index + 1:02d}')).strip() or f'SW-{index + 1:02d}'

    tags = sw.get('tags') if isinstance(sw.get('tags'), list) else []
    tags = [str(item).strip() for item in tags if str(item).strip()]
    if 'Telnet' not in tags:
        tags.insert(0, 'Telnet')

    return {
        'id': index + 1,
        'name': name,
        'host': host,
        'port': port,
        'protocol': 'telnet',
        'vendor': vendor,
        'model': model,
        'group_id': group_id,
        'enabled': enabled,
        'online': online,
        'status': status,
        'acl_number': int(sw.get('acl_number', 30) or 30),
        'readonly_only': _as_bool(sw.get('readonly_only', True)),
        'tags': tags,
        'notes': str(sw.get('notes', '')).strip(),
        'last_seen': datetime.now().strftime('%Y-%m-%d %H:%M:%S') if online else '离线',
        '_password': str(sw.get('password', '')).strip(),
        '_secret': str(sw.get('secret', sw.get('password', ''))).strip(),
        '_paging_disable': str(sw.get('paging_disable', '')).strip(),
    }


def _serialize_switch_config(sw: dict[str, Any], index: int) -> dict[str, Any] | None:
    host = str(sw.get('host', '')).strip()
    if not host:
        return None

    tags = sw.get('tags') if isinstance(sw.get('tags'), list) else []
    tags = [str(item).strip() for item in tags if str(item).strip()]

    return {
        'id': index + 1,
        'name': str(sw.get('name', f'SW-{index + 1:02d}')).strip() or f'SW-{index + 1:02d}',
        'host': host,
        'port': int(sw.get('port', 23) or 23),
        'vendor': str(sw.get('vendor', 'Generic')).strip() or 'Generic',
        'model': str(sw.get('model', 'Telnet Switch')).strip() or 'Telnet Switch',
        'group_id': str(sw.get('group_id', _guess_group(index, str(sw.get('vendor', ''))))).strip() or 'access',
        'password': str(sw.get('password', '')).strip(),
        'secret': str(sw.get('secret', sw.get('password', ''))).strip(),
        'acl_number': int(sw.get('acl_number', 30) or 30),
        'enabled': _as_bool(sw.get('enabled', True)),
        'readonly_only': _as_bool(sw.get('readonly_only', True)),
        'notes': str(sw.get('notes', '')).strip(),
        'paging_disable': str(sw.get('paging_disable', '')).strip(),
        'tags': tags,
    }


def _normalize_config_payload_item(raw: dict[str, Any], index: int) -> dict[str, Any]:
    host = str(raw.get('host', '')).strip()
    if not host:
        raise ValueError(f'第 {index + 1} 台交换机缺少 IP 地址')

    tags = raw.get('tags', [])
    if isinstance(tags, str):
        tags = [item.strip() for item in tags.split(',') if item.strip()]
    elif isinstance(tags, list):
        tags = [str(item).strip() for item in tags if str(item).strip()]
    else:
        tags = []

    return {
        'name': str(raw.get('name', f'SW-{index + 1:02d}')).strip() or f'SW-{index + 1:02d}',
        'host': host,
        'port': int(raw.get('port', 23) or 23),
        'vendor': str(raw.get('vendor', 'Generic')).strip() or 'Generic',
        'model': str(raw.get('model', 'Telnet Switch')).strip() or 'Telnet Switch',
        'group_id': str(raw.get('group_id', 'access')).strip() or 'access',
        'password': str(raw.get('password', '')).strip(),
        'secret': str(raw.get('secret', raw.get('password', ''))).strip(),
        'acl_number': int(raw.get('acl_number', 30) or 30),
        'enabled': _as_bool(raw.get('enabled', True)),
        'readonly_only': _as_bool(raw.get('readonly_only', True)),
        'notes': str(raw.get('notes', '')).strip(),
        'paging_disable': str(raw.get('paging_disable', '')).strip(),
        'tags': tags,
    }


def _load_devices(probe: bool = False) -> list[dict[str, Any]]:
    cfg = _load_cfg()
    raw_switches = cfg.get('switches', [])
    devices: list[dict[str, Any]] = []
    for index, switch in enumerate(raw_switches):
        if not isinstance(switch, dict):
            continue
        normalized = _normalize_switch(switch, index, probe=probe)
        if normalized:
            devices.append(normalized)
    return devices


def _load_device_configs() -> list[dict[str, Any]]:
    cfg = _load_cfg()
    raw_switches = cfg.get('switches', [])
    items: list[dict[str, Any]] = []
    for index, switch in enumerate(raw_switches):
        if not isinstance(switch, dict):
            continue
        normalized = _serialize_switch_config(switch, index)
        if normalized:
            items.append(normalized)
    return items


def _save_device_configs(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cfg = _load_cfg()
    cfg['switches'] = devices
    _save_cfg(cfg)
    return _load_device_configs()


def _public_device(device: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in device.items() if not k.startswith('_')}


def _resolve_device(device_id: int | None = None, host: str | None = None, probe: bool = False) -> dict[str, Any] | None:
    devices = _load_devices(probe=probe)
    for device in devices:
        if device_id is not None and device['id'] == device_id:
            return device
        if host and device['host'] == host:
            return device
    return None


def _tcp_probe(host: str, port: int, timeout: float = 1.8) -> bool:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, int(port)))
        sock.close()
        return result == 0
    except Exception:
        return False


def _test_telnet(host: str, port: int, password: str) -> tuple[bool, str]:
    try:
        import telnetlib3 as telnetlib
    except Exception as exc:
        return False, f'Telnet 依赖不可用: {exc}'

    try:
        tn = telnetlib.Telnet(host, port, 8)
        time.sleep(1.8)
        banner = _read_telnet_buffer(tn)
        if password:
            tn.write((password + '\r').encode('utf-8'))
            time.sleep(0.8)
            banner += '\n' + _read_telnet_buffer(tn)
        tn.close()
        text = banner.lower()
        if 'password' in text and 'incorrect' in text:
            return False, '密码错误'
        if '#' in banner or '>' in banner or 'password' in text or 'login' in text:
            return True, 'Telnet 握手正常'
        return True, 'TCP 可达，但提示符未完全识别'
    except Exception as exc:
        return False, str(exc)


def _read_telnet_buffer(tn) -> str:
    try:
        chunk = tn.read_very_eager()
    except Exception:
        return ''
    if isinstance(chunk, bytes):
        return chunk.decode('utf-8', errors='ignore')
    return str(chunk or '')


def _is_readonly_command(command: str) -> bool:
    lowered = command.strip().lower()
    return any(lowered.startswith(prefix) for prefix in _ALLOWED_READONLY_PREFIXES)


def _build_ai_suggestions(prompt: str, device: dict[str, Any] | None, command_output: str = '', command_text: str = '') -> list[dict[str, Any]]:
    lowered = prompt.lower()
    output_lower = (command_output or '').lower()
    suggestions: list[dict[str, Any]] = []

    def add(command: str, title: str, risk: str, reason: str, auto_runnable: bool = True):
        suggestions.append({
            'id': f'sg-{len(suggestions) + 1}',
            'title': title,
            'command': command,
            'risk': risk,
            'reason': reason,
            'auto_runnable': auto_runnable,
        })

    if command_output:
        if 'down' in output_lower or 'error' in output_lower or 'crc' in output_lower:
            add('display interface counters', '深入查看接口计数器', '只读', '当前回显出现 down / error / CRC 迹象，建议继续确认链路质量。')
            add('display logbuffer | include interface', '查看接口相关日志', '只读', '继续追踪异常端口是否伴随 flap 或硬件告警。')
        if 'acl' in (command_text or '').lower() or 'matched 0' in output_lower:
            add('display current-configuration | include acl', '拉取 ACL 配置片段', '谨慎', '回显提示 ACL 命中异常，建议抓取配置片段做差异比对。', auto_runnable=False)
        if 'version' in (command_text or '').lower():
            add('display device manuinfo', '补充设备资产信息', '低风险', '继续确认硬件与版本基线，便于后续排障。')

    if 'acl' in lowered or '策略' in prompt:
        add('display acl all', '查看 ACL 列表', '只读', '先确认 ACL 内容、命中与空规则。')
        add('display current-configuration | include acl', '抓取 ACL 配置片段', '谨慎', '便于与基线做差异对比。', auto_runnable=False)
    if '接口' in prompt or '端口' in prompt or 'down' in lowered:
        add('display interface brief', '查看接口状态', '只读', '先定位 down 口与高利用率端口。')
        add('display interface counters', '查看接口计数器', '只读', '进一步确认 CRC / error 是否持续增长。')
    if '配置' in prompt or '基线' in prompt or '版本' in prompt:
        add('display version', '查看版本信息', '低风险', '确认设备软件版本和平台信息。')
        add('display current-configuration', '抓取当前配置', '只读', '便于留档和生成基线快照。')

    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in suggestions:
        if item['command'] in seen:
            continue
        seen.add(item['command'])
        deduped.append(item)

    if not deduped:
        device_name = device['name'] if device else '当前设备'
        add('display interface brief', f'{device_name} 接口总览', '只读', '默认先读取接口摘要，快速建立问题上下文。')
        add('display current-configuration', '配置快照采样', '只读', '采样当前配置，供 AI 进一步分析。')
        deduped = suggestions

    return deduped[:4]


def _summarize_output(command: str, output: str) -> str:
    lowered_cmd = command.lower()
    lowered_output = (output or '').lower()

    if 'interface' in lowered_cmd and ('down' in lowered_output or 'error' in lowered_output or 'crc' in lowered_output):
        return 'AI 判断：接口侧存在波动或错误计数，请优先排查链路质量与光模块。'
    if 'acl' in lowered_cmd and ('deny' in lowered_output or 'matched 0' in lowered_output):
        return 'AI 判断：ACL 命中分布异常，建议核对规则是否漂移或业务已迁移。'
    if 'current-configuration' in lowered_cmd:
        return 'AI 判断：配置片段已采样，可继续做基线快照或与历史配置对比。'
    if 'version' in lowered_cmd:
        return 'AI 判断：已获取版本信息，可作为设备画像与兼容性核对依据。'
    if 'invalid input' in lowered_output or 'error' in lowered_output:
        return 'AI 判断：命令执行返回错误，请检查设备厂商命令兼容性或权限级别。'
    return 'AI 判断：本次回显未发现明显危险动作，可继续追加只读命令完成诊断闭环。'


def _build_ai_turn(device: dict[str, Any] | None, prompt: str, command_output: str = '', command_text: str = '', conversation: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    suggestions = _build_ai_suggestions(prompt, device, command_output=command_output, command_text=command_text)
    fallback_summary = _summarize_output(command_text or prompt, command_output or prompt)
    device_snapshot = {
        'name': device.get('name') if device else '未知设备',
        'host': device.get('host') if device else '',
        'vendor': device.get('vendor') if device else '',
        'model': device.get('model') if device else '',
        'group_id': device.get('group_id') if device else '',
        'readonly_only': device.get('readonly_only') if device else True,
    }

    cfg = _load_cfg()
    ai_enabled = cfg.get('ai', {}).get('enabled', False)
    ai_answer = ''

    if ai_enabled:
        system_prompt = '''你是一个专业的网络设备命令助手。请根据用户需求从以下固定命令池中选择最合适的命令。

## 命令池（仅可使用这些命令）
- display version - 查看设备版本信息
- display interface brief - 查看端口状态摘要
- display vlan - 查看VLAN配置
- display mac-address - 查看MAC地址表
- display arp - 查看ARP表
- display interface counters - 查看接口计数器
- display logbuffer | include interface - 查看接口相关日志
- display current-configuration | include acl - 拉取ACL配置片段
- display device manuinfo - 查看设备资产信息
- display current-configuration - 查看当前配置

## 回复格式
必须按以下 Markdown 格式回复：
### 建议执行的命令
1. `命令1` - 用途说明
2. `命令2` - 用途说明

## 重要约束
- 只回复命令，不要做其他操作
- 最多选择3条最相关的命令
- 如果用户需求不明确，选择最常用的相关命令
- 优先选择只读命令
'''
        user_content = (
            f'设备信息: {json.dumps(device_snapshot, ensure_ascii=False)}\n'
            f'用户意图: {prompt}\n'
            f'最近执行命令: {command_text or "无"}\n'
            f'最近命令回显:\n{command_output or "无"}\n'
            f'最近对话: {json.dumps(conversation or [], ensure_ascii=False)}\n'
            '请从命令池中选择最合适的命令并按格式回复。'
        )
        result = call_openai_chat_completion([
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_content},
        ], cfg)
        ai_answer = (result.get('content') or result.get('message') or '').strip()

    if not ai_answer:
        ai_answer = fallback_summary + '\n\n建议继续执行只读命令，确认异常是否可复现，并结合版本/配置快照做进一步对比。'

    next_steps = [item['command'] for item in suggestions[:3]]
    return {
        'answer': ai_answer,
        'summary': fallback_summary,
        'next_steps': next_steps,
        'suggested_commands': suggestions,
    }


def _execute_telnet_command(device: dict[str, Any], command: str) -> str:
    try:
        import telnetlib3 as telnetlib
    except Exception as exc:
        raise RuntimeError(f'Telnet 依赖不可用: {exc}')

    host = device['host']
    port = int(device['port'])
    password = device.get('_password', '')
    secret = device.get('_secret', '')
    paging_disable = device.get('_paging_disable', '')
    vendor = str(device.get('vendor', '')).lower()

    if not password:
        raise RuntimeError('当前交换机未配置 Telnet 密码')

    commands = [password]
    if secret:
        commands.extend(['en', secret])

    if paging_disable:
        commands.append(paging_disable)
    elif 'huawei' in vendor or 'h3c' in vendor:
        commands.append('screen-length disable')
    else:
        commands.append('terminal length 0')

    commands.append(command)
    commands.append('exit')

    tn = telnetlib.Telnet(host, port, 15)
    time.sleep(2.0)
    output_chunks = []

    initial = _read_telnet_buffer(tn)
    if initial:
        output_chunks.append(initial)

    for line in commands:
        tn.write((line + '\r').encode('utf-8'))
        time.sleep(1.2)
        chunk = _read_telnet_buffer(tn)
        if chunk:
            output_chunks.append(chunk)

    time.sleep(0.8)
    final_chunk = _read_telnet_buffer(tn)
    if final_chunk:
        output_chunks.append(final_chunk)

    tn.close()

    merged = '\n'.join(chunk.strip() for chunk in output_chunks if chunk and chunk.strip()).strip()
    if not merged:
        return f'命令 {command} 已发送，但设备没有返回可解析输出。'
    return merged


@switch_workbench_bp.route('/devices', methods=['GET'])
@require_auth
def workbench_devices():
    probe = _as_bool(request.args.get('probe', '1'))
    devices = [_public_device(device) for device in _load_devices(probe=probe)]
    return ok(devices)


@switch_workbench_bp.route('/devices/config', methods=['GET'])
@require_auth
def workbench_device_configs_get():
    return ok(_load_device_configs())


@switch_workbench_bp.route('/devices/config', methods=['POST'])
@require_auth
def workbench_device_configs_save():
    body = _body()
    raw_devices = body.get('devices')
    if not isinstance(raw_devices, list):
        return err('devices 必须为数组', 400)

    try:
        normalized_devices = [_normalize_config_payload_item(item if isinstance(item, dict) else {}, index) for index, item in enumerate(raw_devices)]
    except Exception as exc:
        return err(str(exc), 400)

    hosts = [item['host'] for item in normalized_devices]
    if len(set(hosts)) != len(hosts):
        return err('交换机 IP 不允许重复', 400)

    items = _save_device_configs(normalized_devices)
    return ok({'items': items})


@switch_workbench_bp.route('/scripts', methods=['GET'])
@require_auth
def workbench_scripts():
    return ok(_DEFAULT_SCRIPTS)


@switch_workbench_bp.route('/history', methods=['GET'])
@require_auth
def workbench_history():
    limit = _parse_int_arg('limit', 30, max_value=200)
    return ok(SwitchWorkbenchModel.list_command_runs(limit=limit))


@switch_workbench_bp.route('/devices/test', methods=['POST'])
@require_auth
def workbench_test_device():
    body = _body()
    device_id = body.get('device_id')
    host = str(body.get('host', '')).strip() or None
    device = _resolve_device(int(device_id) if device_id else None, host=host, probe=False)

    if device:
        host = device['host']
        port = device['port']
        password = device.get('_password', '')
    else:
        host = host or ''
        port = int(body.get('port', 23) or 23)
        password = str(body.get('password', '')).strip()

    if not host:
        return err('未找到目标交换机', 404)

    if not _tcp_probe(host, int(port)):
        return err(f'无法连接到 {host}:{port}', 502)

    telnet_ok, detail = _test_telnet(host, int(port), password)
    return ok({
        'reachable': telnet_ok or True,
        'host': host,
        'port': int(port),
        'warning': None if telnet_ok else detail,
    })


@switch_workbench_bp.route('/ai/generate', methods=['POST'])
@require_auth
def workbench_ai_generate():
    body = _body()
    prompt = str(body.get('prompt', '')).strip()
    if not prompt:
        return err('请输入 AI 意图', 400)

    device_id = body.get('device_id')
    device = _resolve_device(int(device_id) if device_id else None, probe=False)
    suggestions = _build_ai_suggestions(prompt, device)

    summary = 'AI 已根据当前意图生成建议命令，默认优先使用只读巡检指令。'
    if device:
        summary = f'AI 已结合 {device["name"]} 生成命令建议，建议先从只读命令开始。'

    return ok({
        'summary': summary,
        'items': suggestions,
    })


@switch_workbench_bp.route('/ai/turn', methods=['POST'])
@require_auth
def workbench_ai_turn():
    body = _body()
    prompt = str(body.get('prompt', '')).strip()
    command_output = str(body.get('command_output', '')).strip()
    command_text = str(body.get('command', '')).strip()
    raw_conversation = body.get('conversation') if isinstance(body.get('conversation'), list) else []

    if not prompt and not command_output:
        return err('请提供 AI 意图或命令回显', 400)

    conversation = []
    for item in raw_conversation[-8:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get('role', '')).strip()
        content = str(item.get('content', '')).strip()
        if role in ('user', 'assistant') and content:
            conversation.append({'role': role, 'content': content})

    device_id = body.get('device_id')
    device = _resolve_device(int(device_id) if device_id else None, probe=False)
    turn = _build_ai_turn(device, prompt or '请分析最近回显', command_output=command_output, command_text=command_text, conversation=conversation)
    return ok(turn)


@switch_workbench_bp.route('/commands/run', methods=['POST'])
@require_auth
def workbench_run_command():
    body = _body()
    device_id = body.get('device_id')
    command = str(body.get('command', '')).strip()
    source = str(body.get('source', 'manual')).strip() or 'manual'

    if not command:
        return err('命令不能为空', 400)

    device = _resolve_device(int(device_id) if device_id else None, probe=False)
    if not device:
        return err('未找到目标交换机', 404)

    if device.get('readonly_only', True) and not _is_readonly_command(command):
        return err('当前工作台仅允许执行只读巡检命令', 403)

    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    status = 'success'

    try:
        output = _execute_telnet_command(device, command)
        analysis = _summarize_output(command, output)
    except Exception as exc:
        status = 'failed'
        output = str(exc)
        analysis = 'AI 判断：命令执行失败，请确认 Telnet 凭据、命令兼容性与设备状态。'

    run_id = SwitchWorkbenchModel.add_command_run(
        device_name=device['name'],
        device_host=device['host'],
        command_text=command,
        source=source,
        status=status,
        stdout=output,
        summary=analysis,
    )

    return ok({
        'run_id': run_id,
        'device': {
            'id': device['id'],
            'name': device['name'],
            'host': device['host'],
            'port': device['port'],
        },
        'command': command,
        'source': source,
        'status': status,
        'output': output,
        'analysis': analysis,
        'created_at': created_at,
    })


@switch_workbench_bp.route('/scripts/run', methods=['POST'])
@require_auth
def workbench_run_script():
    body = _body()
    script_id = str(body.get('script_id', '')).strip()
    device_ids = body.get('device_ids') if isinstance(body.get('device_ids'), list) else []

    script = next((item for item in _DEFAULT_SCRIPTS if item['id'] == script_id), None)
    if not script:
        return err('未找到脚本模板', 404)

    targets = []
    for raw_id in device_ids:
        try:
            device = _resolve_device(int(raw_id), probe=False)
        except Exception:
            device = None
        if device:
            targets.append(device)

    if not targets:
        return err('请至少选择一台交换机', 400)

    items = []
    success_count = 0
    for device in targets:
        for command in script['commands']:
            try:
                output = _execute_telnet_command(device, command)
                analysis = _summarize_output(command, output)
                status = 'success'
                success_count += 1
            except Exception as exc:
                output = str(exc)
                analysis = 'AI 判断：脚本命令执行失败，请确认设备可达与命令兼容性。'
                status = 'failed'

            run_id = SwitchWorkbenchModel.add_command_run(
                device_name=device['name'],
                device_host=device['host'],
                command_text=command,
                source='script',
                status=status,
                stdout=output,
                summary=analysis,
            )
            items.append({
                'run_id': run_id,
                'device': {
                    'id': device['id'],
                    'name': device['name'],
                    'host': device['host'],
                    'port': device['port'],
                },
                'command': command,
                'source': 'script',
                'status': status,
                'output': output,
                'analysis': analysis,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            })

    summary = f"{script['title']} 已完成，成功执行 {success_count}/{len(items)} 条命令。"
    return ok({
        'script_id': script['id'],
        'script_title': script['title'],
        'summary': summary,
        'items': items,
    })
