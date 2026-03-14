"""
AI 工具注册系统 - 使用装饰器模式
"""
import json
from typing import Callable


class ToolRegistry:
    """工具注册器 - 使用装饰器模式"""

    def __init__(self):
        self._definitions: dict[str, dict] = {}
        self._handlers: dict[str, Callable] = {}

    def register(self, *, name: str, description: str, parameters: dict):
        """装饰器：注册工具函数"""
        definition = {
            'type': 'function',
            'function': {
                'name': name,
                'description': description,
                'parameters': parameters,
            },
        }

        def decorator(func: Callable):
            self._definitions[name] = definition
            self._handlers[name] = func
            return func

        return decorator

    def get_tools(self) -> list[dict]:
        """获取所有工具定义"""
        return list(self._definitions.values())

    def execute(self, tool_name: str, arguments: dict, cfg: dict = None) -> str:
        """执行工具"""
        handler = self._handlers.get(tool_name)
        if handler is None:
            return json.dumps({'ok': False, 'error': f'未知工具: {tool_name}'})

        try:
            # 将 cfg 传入工具函数
            result = handler(arguments, cfg)
            if isinstance(result, dict):
                return json.dumps(result, ensure_ascii=False)
            return str(result)
        except Exception as e:
            return json.dumps({'ok': False, 'error': str(e)})


# 全局工具注册器
tool_registry = ToolRegistry()


# ──────────────────────────────────────────────────────────────────────────────
# 工具定义（使用装饰器）
# ──────────────────────────────────────────────────────────────────────────────

@tool_registry.register(
    name='telnet',
    description=(
        '通过Telnet连接交换机并执行命令。'
        '用于查看交换机配置、执行配置命令。'
    ),
    parameters={
        'type': 'object',
        'properties': {
            'host': {'type': 'string', 'description': '交换机IP地址'},
            'port': {'type': 'integer', 'description': 'Telnet端口，默认23', 'default': 23},
            'username': {'type': 'string', 'description': '用户名', 'default': ''},
            'password': {'type': 'string', 'description': '登录密码'},
            'secret': {'type': 'string', 'description': '特权模式密码', 'default': ''},
            'command': {'type': 'string', 'description': '要执行的命令'},
            'mode': {
                'type': 'string',
                'description': '操作模式：view(查看配置) 或 exec(执行命令)',
                'enum': ['view', 'exec'],
                'default': 'view',
            },
        },
        'required': ['host', 'password', 'command'],
    },
)
def _telnet(args: dict, cfg: dict = None) -> dict:
    """Telnet工具 - 供嵌套AI调用"""
    import time
    import telnetlib
    import socket
    import re

    host = args.get('host', '')
    port = args.get('port', 23)
    username = args.get('username', '')
    password = args.get('password', '')
    secret = args.get('secret', '')
    command = args.get('command', '')
    mode = args.get('mode', 'view')

    if not host or not password or not command:
        return {'ok': False, 'error': '缺少必要参数'}

    try:
        socket.setdefaulttimeout(30)
        tn = telnetlib.Telnet(host, port, 30)
        time.sleep(2)

        # 读取欢迎信息
        output = tn.read_very_eager().decode('utf-8', errors='ignore')

        # 第一次：发送登录密码
        tn.write((password + '\r').encode('utf-8'))
        time.sleep(2)
        output = tn.read_very_eager().decode('utf-8', errors='ignore')

        # 第二次：检查是否在特权模式，否则输入en和特权密码
        if '#' not in output:
            # 输入en进入特权模式
            tn.write(b'en\r')
            time.sleep(1)
            output = tn.read_very_eager().decode('utf-8', errors='ignore')

            # 如果需要特权密码
            if 'Password' in output or '#' not in output:
                enable_pass = secret if secret else password
                tn.write((enable_pass + '\r').encode('utf-8'))
                time.sleep(2)
                output = tn.read_very_eager().decode('utf-8', errors='ignore')

        # 如果是exec模式，需要进入配置模式
        if mode == 'exec':
            # 检查是否在配置模式（#提示符但不是config）
            if '#' in output and 'config' not in output.lower():
                tn.write(b'config\r')
                time.sleep(1)
                output = tn.read_very_eager().decode('utf-8', errors='ignore')

        # 执行命令
        tn.write((command + '\r').encode('utf-8'))
        time.sleep(2)
        output = tn.read_very_eager().decode('utf-8', errors='ignore')

        tn.close()

        # 清理输出
        lines = output.split('\n')
        cleaned = '\n'.join([line.strip() for line in lines if line.strip()])

        return {
            'ok': True,
            'host': host,
            'command': command,
            'output': cleaned[:2000],
        }

    except Exception as e:
        return {'ok': False, 'error': f'Telnet执行失败: {e}'}


@tool_registry.register(
    name='nmap_scan',
    description='执行 Nmap 网络扫描，发现存活主机、开放端口、服务版本和操作系统信息',
    parameters={
        'type': 'object',
        'properties': {
            'target': {
                'type': 'string',
                'description': '扫描目标：单个IP、网段(CIDR)或主机名，如 192.168.0.1 或 192.168.0.0/24',
            },
            'arguments': {
                'type': 'string',
                'description': 'nmap参数，默认 -sV -T5，常用：-sV(版本) -O(系统) -p(端口) -sn(仅ping)',
                'default': '-sV -T5',
            },
        },
        'required': ['target'],
    },
)
def _nmap_scan(args: dict, cfg: dict = None) -> dict:
    """nmap扫描工具"""
    import sys
    import os
    from datetime import datetime

    plugin_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'plugin')
    if plugin_dir not in sys.path:
        sys.path.insert(0, plugin_dir)

    try:
        from network_scan import scan_hosts, parse_scan_results
        from database.models import ScannerModel
    except ImportError as e:
        return {'ok': False, 'error': f'无法导入模块: {e}'}

    target = str(args.get('target', '')).strip()
    raw_args = args.get('arguments', '-sV -T5')
    nmap_args = str(raw_args).strip() or '-sV -T5'

    if not target:
        return {'ok': False, 'error': '缺少 target 参数'}

    # 执行扫描
    nm = scan_hosts(target, nmap_args)
    if not nm:
        return {'ok': False, 'error': 'Nmap 执行失败'}

    hosts = parse_scan_results(nm)
    scan_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    scan_id = ScannerModel.create_scan([target], nmap_args, scan_time)

    # 保存结果到数据库
    try:
        for host in hosts:
            try:
                open_ports = ','.join(map(str, host.get('open_ports', []) or []))
                services = []
                for svc in host.get('services', []) or []:
                    svc_str = f"{svc.get('port','')}/{svc.get('service','')}"
                    if svc.get('product'):
                        svc_str += f" {svc['product']}"
                    services.append(svc_str)
                services_str = '; '.join(services)
                ScannerModel.save_host(scan_id, host, scan_time, open_ports, services_str)
                ScannerModel.upsert_asset(scan_id, host, scan_time)
            except Exception:
                pass
        ScannerModel.increment_hosts_count(scan_id, len(hosts))
    except Exception as e:
        pass  # 忽略数据库写入错误

    return {
        'ok': True,
        'scan_id': scan_id,
        'target': target,
        'arguments': nmap_args,
        'host_count': len(hosts),
        'hosts': hosts[:15],
    }


@tool_registry.register(
    name='switch_acl_config',
    description=(
        '通过Telnet连接交换机并配置ACL访问控制列表。'
        '用于封禁/解封IP、配置访问控制策略。'
        '此工具会智能生成配置命令并执行。'
    ),
    parameters={
        'type': 'object',
        'properties': {
            'host': {'type': 'string', 'description': '交换机IP地址'},
            'port': {'type': 'integer', 'description': 'Telnet端口，默认23', 'default': 23},
            'username': {'type': 'string', 'description': '用户名（Telnet可为空）', 'default': ''},
            'password': {'type': 'string', 'description': '登录密码'},
            'secret': {'type': 'string', 'description': '特权模式密码', 'default': ''},
            'acl_number': {'type': 'integer', 'description': 'ACL编号，默认3000', 'default': 3000},
            'action': {
                'type': 'string',
                'description': '操作类型',
                'enum': ['ban', 'unban', 'custom'],
            },
            'target_ip': {'type': 'string', 'description': '目标IP（ban/unban时使用）', 'default': ''},
            'custom_commands': {'type': 'string', 'description': '自定义命令（custom时使用）', 'default': ''},
            'description': {'type': 'string', 'description': '配置描述', 'default': ''},
        },
        'required': ['host', 'password', 'action'],
    },
)
def _switch_acl_config(args: dict, cfg: dict = None) -> dict:
    """交换机ACL配置工具 - 嵌套AI自主调用telnet工具"""
    import time
    import telnetlib
    import socket

    from .utils import _get_base_url
    from utils.logger import log as unified_log
    from openai import OpenAI

    host = args.get('host', '')
    port = args.get('port', 23)
    username = args.get('username', '')
    password = args.get('password', '')
    secret = args.get('secret', '')
    acl_number = args.get('acl_number', 3000)
    action = args.get('action', 'ban')
    target_ip = args.get('target_ip', '')
    custom_commands = args.get('custom_commands', '')
    description = args.get('description', '')

    if cfg is None:
        return {'ok': False, 'error': '配置加载失败'}

    if action in ['ban', 'unban'] and not target_ip:
        return {'ok': False, 'error': 'ban/unban操作需要指定target_ip'}

    unified_log('SwitchACL', f'开始配置交换机 {host}, action={action}', 'INFO')

    # 获取AI配置
    ai_cfg = cfg.get('ai', {})
    api_url = ai_cfg.get('api_url', '')
    api_key = ai_cfg.get('api_key', '')
    model = ai_cfg.get('model', 'gpt-3.5-turbo')
    timeout = int(ai_cfg.get('timeout', 60))
    base_url = _get_base_url(api_url)

    if not api_url or not api_key:
        return {'ok': False, 'error': 'AI API未配置'}

    # 构造嵌套AI的system prompt
    system_prompt = f"""你是一个专业的网络设备配置助手。你可以通过telnet工具来配置交换机。

可用工具：
1. telnet - 用于连接交换机并执行命令
   - mode=view: 查看配置（执行display命令）
   - mode=exec: 执行配置命令

你需要完成的任务："""

    if action == 'ban':
        system_prompt += f"在交换机 ACL {acl_number} 中封禁IP {target_ip}"
    elif action == 'unban':
        system_prompt += f"在交换机 ACL {acl_number} 中解封IP {target_ip}"
    elif action == 'custom':
        system_prompt += f"在交换机 ACL {acl_number} 中执行自定义配置: {custom_commands}"

    system_prompt += f"""

交换机信息：
- IP: {host}
- 端口: {port}
- ACL编号: {acl_number}

命令参考（锐捷交换机）：
- 进入特权模式: en
- 进入配置模式: config
- 创建标准ACL: ip access-list standard <num> 或 access-list <num>
- 在ACL内添加规则: deny host <ip> 或 permit any
- 在全局添加规则: access-list <num> deny host <ip>
- 绑定到接口: interface range gigabitethernet 0/1-24 然后 ip access-group <num> in
- 保存配置: wr

重要要求：
1. 先使用telnet工具(mode=view)查看当前ACL配置: show access-list {acl_number}
2. 分析现有配置：
   - 如果ACL不存在，需要创建ACL并绑定到接口
   - 如果ACL已存在，直接添加规则
3. 使用telnet工具(mode=exec)执行配置命令
4. 完成后用 'show access-list {acl_number}' 确认配置
5. 最后用 'wr' 保存配置"""

    # 准备工具定义给嵌套AI使用
    telnet_tool_def = {
        "type": "function",
        "function": {
            "name": "telnet",
            "description": "通过Telnet连接交换机并执行命令。mode=view用于查看配置，mode=exec用于执行配置命令。",
            "parameters": {
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "交换机IP地址"},
                    "port": {"type": "integer", "description": "Telnet端口，默认23"},
                    "username": {"type": "string", "description": "用户名"},
                    "password": {"type": "string", "description": "登录密码"},
                    "secret": {"type": "string", "description": "特权模式密码"},
                    "command": {"type": "string", "description": "要执行的命令"},
                    "mode": {"type": "string", "description": "模式：view(查看)或exec(执行)", "enum": ["view", "exec"]},
                },
                "required": ["host", "password", "command"],
            },
        }
    }

    # 构建初始消息
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "请开始配置交换机。"}
    ]

    max_iterations = 10  # 最多迭代次数，防止无限循环
    iteration = 0
    executed_commands = []

    try:
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

        while iteration < max_iterations:
            iteration += 1
            unified_log('SwitchACL', f'嵌套AI迭代 {iteration}', 'INFO')

            # 调用AI，判断是否需要调用工具
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=[telnet_tool_def],
                    tool_choice="auto"
                )
            except Exception as e:
                return {'ok': False, 'error': f'AI调用失败: {e}'}

            if not response.choices:
                return {'ok': False, 'error': 'AI返回为空'}

            assistant_msg = response.choices[0].message
            if assistant_msg is None:
                return {'ok': False, 'error': 'AI返回消息为空'}

            messages.append({
                "role": "assistant",
                "content": assistant_msg.content,
                "tool_calls": assistant_msg.tool_calls if assistant_msg.tool_calls else None
            })

            # 检查是否有工具调用
            if not assistant_msg.tool_calls:
                # AI没有调用工具，说明任务完成，返回结果
                result = assistant_msg.content or "操作完成"
                break

            # 处理工具调用
            for tool_call in assistant_msg.tool_calls:
                if tool_call.function is None:
                    continue
                tool_name = tool_call.function.name
                tool_args = tool_call.function.arguments

                # 解析参数
                if tool_args is None:
                    tool_args = {}
                elif isinstance(tool_args, str):
                    import json
                    try:
                        tool_args = json.loads(tool_args)
                    except:
                        tool_args = {}

                if not isinstance(tool_args, dict):
                    tool_args = {}

                # 填充缺失的参数
                tool_args.setdefault('host', host)
                tool_args.setdefault('port', port)
                tool_args.setdefault('username', username)
                tool_args.setdefault('password', password)
                tool_args.setdefault('secret', secret)

                unified_log('SwitchACL', f'嵌套AI调用工具: {tool_name}, 参数: {tool_args}', 'INFO')

                # 调用telnet工具
                if tool_name == 'telnet':
                    result = _telnet(tool_args, cfg)
                else:
                    result = {'ok': False, 'error': f'未知工具: {tool_name}'}

                # 记录执行的命令
                if tool_args.get('mode') == 'exec':
                    executed_commands.append(tool_args.get('command', ''))

                # 将工具结果返回给AI
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, ensure_ascii=False)
                })

        else:
            # 超过最大迭代次数
            return {
                'ok': False,
                'error': '操作超时，已达到最大迭代次数',
                'executed_commands': executed_commands
            }

        return {
            'ok': True,
            'message': f'交换机 {host} 配置完成',
            'action': action,
            'target_ip': target_ip,
            'acl_number': acl_number,
            'description': description,
            'executed_commands': executed_commands,
            'ai_response': result
        }

    except Exception as e:
        return {'ok': False, 'error': f'执行失败: {e}'}


# ──────────────────────────────────────────────────────────────────────────────
# 导出
# ──────────────────────────────────────────────────────────────────────────────

AI_TOOLS = tool_registry.get_tools()


def get_tool_definitions() -> list[dict]:
    """获取工具定义列表"""
    return tool_registry.get_tools()


def execute_tool(tool_name: str, arguments: dict, cfg: dict = None) -> str:
    """执行工具，cfg 必须由调用方传入"""
    if cfg is None:
        return json.dumps({'ok': False, 'error': '缺少配置参数'})
    return tool_registry.execute(tool_name, arguments, cfg)
