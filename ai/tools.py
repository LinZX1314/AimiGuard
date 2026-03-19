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


def _get_active_switches(cfg: dict | None) -> list[dict]:
    """返回已启用且配置有效的交换机列表。"""
    if not isinstance(cfg, dict):
        return []
    switches = cfg.get('switches', [])
    if not isinstance(switches, list):
        return []

    active: list[dict] = []
    for sw in switches:
        if not isinstance(sw, dict):
            continue
        if not sw.get('host'):
            continue
        if sw.get('enabled', True) is False:
            continue
        active.append(sw)
    return active


# ──────────────────────────────────────────────────────────────────────────────
# 工具定义（使用装饰器）
# ──────────────────────────────────────────────────────────────────────────────


@tool_registry.register(
    name='dhcp_query',
    description='查询锐捷交换机DHCP绑定表，获取当前网络中所有通过DHCP获取IP的设备列表（IP地址、MAC地址、租约时间）',
    parameters={
        'type': 'object',
        'properties': {},
        'required': [],
    },
)
def _dhcp_query(args: dict, cfg: dict = None) -> dict:
    """DHCP查询工具 - 查询交换机DHCP绑定表"""
    import re
    import telnetlib3 as telnetlib
    import time

    if cfg is None:
        return {'ok': False, 'error': '缺少配置信息'}

    # 从配置获取交换机信息
    switches = _get_active_switches(cfg)
    if not switches:
        return {'ok': False, 'error': '未找到已启用的交换机配置'}

    switch = switches[0]
    host = switch.get('host', '192.168.0.1')
    port = switch.get('port', 23)
    password = switch.get('password', 'admin')
    secret = switch.get('secret', password)

    try:
        tn = telnetlib.Telnet(host, port, 30)
        time.sleep(2)

        # 读取欢迎信息
        tn.read_very_eager()

        # 发送密码进入特权模式
        tn.write((password + '\r').encode('utf-8'))
        time.sleep(1)

        # 进入enable模式
        tn.write(b'en\r')
        time.sleep(1)
        tn.write((secret + '\r').encode('utf-8'))
        time.sleep(1)

        # 执行DHCP查询命令
        tn.write(b'show ip dhcp binding\r')
        time.sleep(2)

        # 读取输出
        output = tn.read_very_eager().decode('utf-8', errors='ignore')
        tn.close()

        # 解析输出
        bindings = []
        lines = output.strip().split('\n')

        # 跳过表头（前两行）
        for line in lines[2:]:
            line = line.strip()
            if not line:
                continue

            # 正则匹配
            match = re.match(r'^(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F.]+)\s+(\d+\s+days.*?)\s+(Automatic|Dynamic)$', line)
            if match:
                ip = match.group(1)
                mac = match.group(2)
                # 格式化MAC地址
                if len(mac) == 14 and '.' in mac:
                    mac_clean = mac.replace('.', '')
                    mac_formatted = ':'.join([mac_clean[i:i+2] for i in range(0, 12, 2)])
                else:
                    mac_formatted = mac

                bindings.append({
                    'ip': ip,
                    'mac': mac_formatted,
                    'lease': match.group(3).strip(),
                    'type': match.group(4),
                })

        return {
            'ok': True,
            'count': len(bindings),
            'devices': bindings,
        }

    except Exception as e:
        return {'ok': False, 'error': f'DHCP查询失败: {e}'}


@tool_registry.register(
    name='nmap_scan',
    description='执行 Nmap 网络扫描（备选，仅当fscan不可用时使用）。发现存活主机、开放端口、服务版本和操作系统信息',
    parameters={
        'type': 'object',
        'properties': {
            'target': {
                'type': 'string',
                'description': '扫描目标：单个IP、网段(CIDR)或主机名，如 192.168.0.1 或 192.168.0.0/24',
            },
            'arguments': {
                'type': 'string',
                'description': 'nmap参数，默认 -sS -T5，常用：-sV(版本) -O(系统) -p(端口) -sn(仅ping)',
                'default': '-sS -T5',
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
    raw_args = args.get('arguments', '-sS -T5')
    nmap_args = str(raw_args).strip() or '-sS -T5'

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
    import telnetlib3 as telnetlib

    from database.models import SwitchAclModel

    # 从cfg配置文件中读取交换机信息
    action = args.get('action', 'ban')
    target_ip = args.get('target_ip', '')

    if cfg is None:
        return {'ok': False, 'error': '缺少配置信息'}

    # 从配置获取交换机信息
    switches = _get_active_switches(cfg)
    if not switches:
        return {'ok': False, 'error': '未找到已启用的交换机配置'}

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

    # ban 前检查目标IP是否已存在（去重）
    if action == 'ban':
        existing_rules = SwitchAclModel.get_rules(host, acl_number)
        for r in existing_rules:
            if r.get('target_ip') == target_ip and r.get('action') == 'ban':
                return {'ok': False, 'error': f'IP {target_ip} 已在封禁列表中，无需重复封禁'}

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


@tool_registry.register(
    name='get_ban_records',
    description='获取封禁记录列表，查看所有已封禁的IP地址和封禁时间',
    parameters={
        'type': 'object',
        'properties': {
            'switch_ip': {
                'type': 'string',
                'description': '交换机IP地址，不传则查询所有交换机',
            },
            'limit': {
                'type': 'integer',
                'description': '返回记录数量限制，默认50条',
                'default': 50,
            },
        },
        'required': [],
    },
)
def _get_ban_records(args: dict, cfg: dict = None) -> dict:
    """获取封禁记录工具"""
    from database.models import SwitchAclModel

    switch_ip = args.get('switch_ip')
    limit = args.get('limit', 50)

    try:
        rules = SwitchAclModel.get_rules(switch_ip=switch_ip)
        # 只返回封禁中的记录（action=ban）
        ban_records = [r for r in rules if r.get('action') == 'ban']
        ban_records = ban_records[:limit]

        # 格式化记录便于阅读
        formatted = []
        for r in ban_records:
            formatted.append({
                'ip': r.get('target_ip', 'N/A'),
                '封禁时间': r.get('created_at', ''),
                '交换机': r.get('switch_ip', ''),
                '描述': r.get('description', ''),
            })

        return {
            'ok': True,
            'total': len(ban_records),
            '已封禁IP列表': formatted,
            '说明': '列表中的IP当前处于封禁状态，如需解封请使用 switch_acl_config 工具',
        }
    except Exception as e:
        return {'ok': False, 'error': f'获取封禁记录失败: {e}'}


@tool_registry.register(
    name='get_honeypot_logs',
    description='查询蜜罐攻击日志，获取攻击来源IP、服务类型等信息。支持按服务类型筛选和分页。',
    parameters={
        'type': 'object',
        'properties': {
            'service_name': {
                'type': 'string',
                'description': '服务名称筛选，如 ssh、http、mysql、redis 等',
            },
            'limit': {
                'type': 'integer',
                'description': '返回记录数量，默认50条，最大200条',
                'default': 50,
            },
            'offset': {
                'type': 'integer',
                'description': '分页偏移量，默认0',
                'default': 0,
            },
        },
        'required': [],
    },
)
def _get_honeypot_logs(args: dict, cfg: dict = None) -> dict:
    """蜜罐日志查询工具"""
    from database.models import HFishModel

    service_name = args.get('service_name')
    limit = min(int(args.get('limit', 50)), 200)
    offset = int(args.get('offset', 0))

    try:
        logs = HFishModel.get_attack_logs(
            limit=limit,
            offset=offset,
            service_name=service_name,
        )

        formatted = []
        for log in logs:
            formatted.append({
                '攻击IP': log.get('attack_ip', 'N/A'),
                '来源地区': log.get('ip_location', '未知'),
                '服务': log.get('service_name', '未知'),
                '攻击时间': log.get('create_time_str', ''),
            })

        return {
            'ok': True,
            '查询参数': {
                '服务': service_name or '全部',
                'limit': limit,
                'offset': offset,
            },
            '总数': len(formatted),
            '攻击记录': formatted,
        }
    except Exception as e:
        return {'ok': False, 'error': f'蜜罐日志查询失败: {e}'}


@tool_registry.register(
    name='get_honeypot_stats',
    description='获取蜜罐系统整体态势统计，包括热门攻击服务、攻击来源Top10、7天趋势等',
    parameters={
        'type': 'object',
        'properties': {},
        'required': [],
    },
)
def _get_honeypot_stats(args: dict, cfg: dict = None) -> dict:
    """蜜罐态势统计工具"""
    from database.models import HFishModel

    try:
        stats = HFishModel.get_stats()

        return {
            'ok': True,
            '总攻击次数': stats.get('total', 0),
            '热门攻击服务': stats.get('service_stats', []),
            '攻击来源Top10': stats.get('ip_stats', []),
            '7天趋势': stats.get('time_stats', []),
        }
    except Exception as e:
        return {'ok': False, 'error': f'蜜罐态势获取失败: {e}'}


@tool_registry.register(
    name='run_fscan',
    description='【网络扫描工具】当你需要扫描局域网IP段、发现存活主机、探测端口服务时，必须使用此工具。参数说明：target可以是IP(192.168.1.1)、CIDR网段(192.168.1.0/24)或多IP(192.168.1.1,192.168.1.2)。port是端口列表如22,80,443。threads是线程数默认6000。重要：扫描局域网时必须用此工具！',
    parameters={
        'type': 'object',
        'properties': {
            'target': {
                'type': 'string',
                'description': '扫描目标：单个IP(如192.168.1.1)、CIDR网段(如192.168.1.0/24)、或多IP逗号分隔(如192.168.1.1,192.168.1.2,192.168.1.3)',
            },
            'port': {
                'type': 'string',
                'description': '指定扫描端口，如 22,80,443 或 1-65535（所有端口），默认常用端口',
                'default': '21,22,23,80,81,135,139,443,445,1433,3306,5432,6379,8080,8443',
            },
            'threads': {
                'type': 'integer',
                'description': '扫描线程数，默认6000',
                'default': 6000,
            },
        },
        'required': ['target'],
    },
)
def _run_fscan(args: dict, cfg: dict = None) -> dict:
    """fscan网络探测工具"""
    import subprocess
    import re
    import shutil
    import os
    from datetime import datetime

    target = str(args.get('target', '')).strip()
    port = args.get('port', '21,22,23,80,81,135,139,443,445,1433,3306,5432,6379,8080,8443')
    threads = int(args.get('threads', 6000))

    if not target:
        return {'ok': False, 'error': '缺少 target 参数'}

    # 查找fscan可执行文件
    fscan_path = None
    # 先在项目lib目录查找
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_fscan = os.path.join(base_dir, 'lib', 'fscan.exe')
    if os.path.isfile(local_fscan):
        fscan_path = local_fscan
    else:
        # 从系统PATH查找
        system_fscan = shutil.which('fscan')
        if system_fscan:
            fscan_path = system_fscan

    if not fscan_path:
        return {'ok': False, 'error': '未找到fscan.exe，请将fscan.exe放置在 lib/fscan.exe 或配置到系统PATH'}

    try:
        import tempfile
        # 创建临时文件存储JSON输出
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as tf:
            json_file = tf.name

        # 构建fscan命令: fscan -h <target> -t <threads> -p <ports> -nobr -nopoc -o <tmpfile> -f json
        cmd = [fscan_path, '-h', target, '-t', str(threads), '-p', port, '-nobr', '-nopoc', '-o', json_file, '-f', 'json']

        # 执行扫描
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 最多等待5分钟
            encoding='utf-8',
            errors='ignore',
        )

        # 先执行扫描（不等待完成）
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='ignore',
        )

        # 等待完成（最多5分钟）
        try:
            stdout, stderr = proc.communicate(timeout=300)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            if os.path.exists(json_file):
                os.unlink(json_file)
            return {'ok': False, 'error': 'fscan扫描超时（超过5分钟）'}

        output = stdout + stderr

        # 尝试读取JSON文件
        scan_data = None
        if os.path.exists(json_file):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if content.strip():
                        scan_data = json.loads(content)
            except Exception:
                pass
            finally:
                try:
                    os.unlink(json_file)
                except Exception:
                    pass

        # 如果成功解析JSON
        if scan_data:
            hosts = []
            vulns = []

            # 解析主机列表
            items = scan_data if isinstance(scan_data, list) else scan_data.get('data', [])
            for h in items:
                host_info = {
                    'ip': h.get('ip', ''),
                    'hostname': h.get('host', ''),
                }
                ports = h.get('ports', [])
                if ports:
                    host_info['ports'] = ','.join(str(p.get('port', '')) for p in ports if p.get('port'))
                hosts.append(host_info)

            # 解析漏洞列表
            for v in scan_data.get('vulns', []) if isinstance(scan_data, dict) else []:
                vulns.append({
                    'ip': v.get('ip', ''),
                    'port': v.get('port', ''),
                    'service': v.get('type', ''),
                    'vuln': v.get('info', ''),
                })

            return {
                'ok': True,
                'target': target,
                '扫描时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                '发现主机': len(hosts),
                '主机列表': hosts[:30],
                '漏洞列表': vulns[:20],
            }

        # Fallback: 解析纯文本输出
        lines = output.split('\n')
        host_ports = {}
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if '端口开放' in line:
                # 提取 "端口开放 192.168.0.5:445" 格式
                parts = line.split('端口开放')
                if len(parts) >= 2:
                    ip_port = parts[-1].strip()
                    if ':' in ip_port:
                        ip, port = ip_port.rsplit(':', 1)
                        if ip not in host_ports:
                            host_ports[ip] = []
                        host_ports[ip].append(port)

        # 合并为一行
        summary = []
        for ip in sorted(host_ports.keys()):
            ports = ', '.join(sorted(host_ports[ip], key=lambda x: int(x) if x.isdigit() else 0))
            summary.append(f'{ip}: {ports}')

        return {
            'ok': True,
            'target': target,
            '扫描时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            '概要': summary if summary else ['扫描完成'],
        }

    except subprocess.TimeoutExpired:
        return {'ok': False, 'error': 'fscan扫描超时（超过5分钟）'}
    except Exception as e:
        return {'ok': False, 'error': f'fscan执行失败: {e}'}


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
