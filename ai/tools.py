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
        '封禁或解封IP地址。'
        '用于防御攻击时封禁恶意IP，或解封已封的IP。'
        '只需要传入action(ban/unban)和target_ip即可。'
    ),
    parameters={
        'type': 'object',
        'properties': {
            'action': {
                'type': 'string',
                'description': '操作类型：ban(封禁) 或 unban(解封)',
                'enum': ['ban', 'unban'],
            },
            'target_ip': {'type': 'string', 'description': '要封禁/解封的目标IP地址'},
        },
        'required': ['action', 'target_ip'],
    },
)
def _switch_acl_config(args: dict, cfg: dict = None) -> dict:
    """交换机ACL配置工具"""
    import time
    import telnetlib

    from database.models import SwitchAclModel

    # 从cfg配置文件中读取交换机信息
    action = args.get('action', 'ban')
    target_ip = args.get('target_ip', '')

    if cfg is None:
        return {'ok': False, 'error': '缺少配置信息'}

    # 从配置获取交换机信息
    switches = cfg.get('switches', [])
    if not switches:
        return {'ok': False, 'error': '配置文件中未找到交换机信息'}

    switch = switches[0]
    host = switch.get('host', '')
    port = switch.get('port', 23)
    password = switch.get('password', '')
    secret = switch.get('secret', password)
    acl_number = switch.get('acl_number', 30)
    action = args.get('action', 'ban')
    target_ip = args.get('target_ip', '')
    description = args.get('description', '')

    if not host or not password:
        return {'ok': False, 'error': '缺少必要参数: host, password'}

    if action in ['ban', 'unban'] and not target_ip:
        return {'ok': False, 'error': '缺少目标IP: target_ip'}

    rule_id = None

    try:
        # 获取规则ID
        if action == 'ban':
            used_ids = set()
            rules = SwitchAclModel.get_rules(host, acl_number)
            for r in rules:
                rid = r.get('rule_id')
                if rid and 1 <= rid < 20000:
                    used_ids.add(rid)

            rule_id = 1
            while rule_id in used_ids and rule_id < 20000:
                rule_id += 1

            if rule_id >= 20000:
                return {'ok': False, 'error': '无可用规则ID（1-19999已用完）'}

            rule_text = f'{rule_id} deny host {target_ip}'
            SwitchAclModel.add_rule(host, acl_number, rule_id, 'ban', target_ip, rule_text, description)

        elif action == 'unban':
            rules = SwitchAclModel.get_rules(host, acl_number)
            for r in rules:
                if r.get('target_ip') == target_ip and r.get('action') == 'ban':
                    rule_id = r.get('rule_id')
                    break

            if rule_id is None:
                return {'ok': False, 'error': f'未找到IP {target_ip} 的封禁规则'}

            SwitchAclModel.remove_rule(host, acl_number, target_ip)
        else:
            return {'ok': False, 'error': f'未知操作: {action}'}

        # 构建命令序列，一次性发送
        if action == 'ban':
            cmd = f'{rule_id} deny host {target_ip}'
        else:
            cmd = f'no {rule_id}'

        # 一次性发送所有命令
        commands = f'''{password}
en
{secret}
config
ip access-list standard {acl_number}
{cmd}
exit
exit
wr
'''

        tn = telnetlib.Telnet(host, port, 30)
        time.sleep(3)

        # 读取欢迎信息
        tn.read_very_eager()

        # 一次性发送命令，每个命令之间等待
        for line in commands.strip().split('\n'):
            tn.write((line + '\r').encode('utf-8'))
            time.sleep(1.5)

        # 等待命令执行完成
        time.sleep(5)
        output = tn.read_very_eager().decode('utf-8', errors='ignore')

        tn.close()

        return {
            'ok': True,
            'host': host,
            'acl_number': acl_number,
            'action': action,
            'target_ip': target_ip if action != 'ban' else None,
            'rule_id': rule_id if action in ['ban', 'unban'] else None,
            'message': f"{'封禁' if action == 'ban' else '解封'}成功",
            'debug': output[:500],
        }

    except Exception as e:
        return {'ok': False, 'error': f'ACL配置失败: {e}'}


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
