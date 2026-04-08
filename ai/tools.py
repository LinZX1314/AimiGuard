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
        'properties': {
            'switch_ip': {
                'type': 'string',
                'description': '交换机IP地址，默认为192.168.0.2',
                'default': '192.168.0.2',
            },
        },
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

    # 获取交换机IP，默认192.168.0.2
    switch_ip = args.get('switch_ip', '192.168.0.2')

    # 从配置获取交换机信息
    switches = _get_active_switches(cfg)

    # 查找指定的交换机
    switch = None
    for sw in switches:
        if sw.get('host') == switch_ip:
            switch = sw
            break

    if not switch:
        return {'ok': False, 'error': f'未找到交换机 {switch_ip} 的配置'}

    host = switch.get('host', '192.168.0.2')
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
    """nmap扫描工具（使用 fscan）"""
    import sys
    import os
    from datetime import datetime

    plugin_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'plugin')
    if plugin_dir not in sys.path:
        sys.path.insert(0, plugin_dir)

    try:
        from network_scan import run_fscan
        from database.models import ScannerModel
    except ImportError as e:
        return {'ok': False, 'error': f'无法导入模块: {e}'}

    target = str(args.get('target', '')).strip()
    raw_args = args.get('arguments', '-sS -T5')
    nmap_args = str(raw_args).strip() or '-sS -T5'
    timeout = 30000  # 30 秒超时

    if not target:
        return {'ok': False, 'error': '缺少 target 参数'}

    try:
        scan_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        scan_id = ScannerModel.create_scan([target], nmap_args, scan_time)

        # 使用 run_fscan 执行扫描（复用已有逻辑）
        hosts = run_fscan(target, timeout=timeout)
        if not hosts:
            return {'ok': False, 'error': '扫描未发现存活主机'}

        # 保存到数据库
        try:
            from network_scan import save_to_db
            save_to_db(scan_id, hosts)
        except Exception:
            pass

        return {
            'ok': True,
            'scan_id': scan_id,
            'target': target,
            'arguments': nmap_args,
            'host_count': len(hosts),
            'hosts': hosts[:15],
        }
    except Exception as e:
        return {'ok': False, 'error': f'扫描失败: {e}'}


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

    # 从配置获取所有已启用的交换机
    switches = _get_active_switches(cfg)
    if not switches:
        return {'ok': False, 'error': '未找到已启用的交换机配置'}

    results = []
    success_count = 0
    fail_count = 0

    # 遍历所有交换机执行封禁/解封操作
    for switch in switches:
        host = switch.get('host', '')
        port = switch.get('port', 23)
        password = switch.get('password', '')
        secret = switch.get('secret', password)
        acl_number = switch.get('acl_number', 30)
        switch_name = switch.get('name', host)

        if not host or not password:
            results.append({
                'host': host,
                'switch_name': switch_name,
                'ok': False,
                'error': '缺少必要参数: host, password'
            })
            fail_count += 1
            continue

        if action in ['ban', 'unban'] and not target_ip:
            results.append({
                'host': host,
                'switch_name': switch_name,
                'ok': False,
                'error': '缺少目标IP: target_ip'
            })
            fail_count += 1
            continue

        rule_id = None

        # 白名单检查
        whitelist = cfg.get('ai', {}).get('whitelist', []) if cfg else []
        if action == 'ban' and target_ip in whitelist:
            results.append({
                'host': host,
                'switch_name': switch_name,
                'ok': True,
                'message': f'IP {target_ip} 在白名单中，已跳过封禁'
            })
            continue

        # ban 前检查目标IP是否已存在（去重）
        if action == 'ban':
            existing_rules = SwitchAclModel.get_rules(host, acl_number)
            for r in existing_rules:
                if r.get('target_ip') == target_ip and r.get('action') == 'ban':
                    results.append({
                        'host': host,
                        'switch_name': switch_name,
                        'ok': False,
                        'error': f'IP {target_ip} 已在封禁列表中，无需重复封禁'
                    })
                    fail_count += 1
                    continue

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
                    results.append({
                        'host': host,
                        'switch_name': switch_name,
                        'ok': False,
                        'error': '无可用规则ID（1-19999已用完）'
                    })
                    fail_count += 1
                    continue

                rule_text = f'{rule_id} deny host {target_ip}'
                description = f'Block {target_ip}'
                SwitchAclModel.add_rule(host, acl_number, rule_id, 'ban', target_ip, rule_text, description)

            elif action == 'unban':
                rules = SwitchAclModel.get_rules(host, acl_number)
                for r in rules:
                    if r.get('target_ip') == target_ip and r.get('action') == 'ban':
                        rule_id = r.get('rule_id')
                        break

                if rule_id is None:
                    results.append({
                        'host': host,
                        'switch_name': switch_name,
                        'ok': False,
                        'error': f'未找到IP {target_ip} 的封禁规则'
                    })
                    fail_count += 1
                    continue

                SwitchAclModel.remove_rule(host, acl_number, target_ip)
            else:
                results.append({
                    'host': host,
                    'switch_name': switch_name,
                    'ok': False,
                    'error': f'未知操作: {action}'
                })
                fail_count += 1
                continue

            # 构建命令序列
            if action == 'ban':
                cmd = f'{rule_id} deny host {target_ip}'
            else:
                cmd = f'no {rule_id}'

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

            tn.read_very_eager()

            for line in commands.strip().split('\n'):
                tn.write((line + '\r').encode('utf-8'))
                time.sleep(1.5)

            time.sleep(5)
            output = tn.read_very_eager().decode('utf-8', errors='ignore')

            tn.close()

            results.append({
                'host': host,
                'switch_name': switch_name,
                'ok': True,
                'acl_number': acl_number,
                'action': action,
                'target_ip': target_ip if action == 'ban' else None,
                'rule_id': rule_id if action in ['ban', 'unban'] else None,
                'message': f"{'封禁' if action == 'ban' else '解封'}成功",
            })
            success_count += 1

        except Exception as e:
            results.append({
                'host': host,
                'switch_name': switch_name,
                'ok': False,
                'error': f'ACL配置失败: {e}'
            })
            fail_count += 1

    # 返回汇总结果
    return {
        'ok': success_count > 0,
        'total': len(switches),
        'success_count': success_count,
        'fail_count': fail_count,
        'action': action,
        'target_ip': target_ip if action == 'ban' else None,
        'results': results,
        'message': f"{'封禁' if action == 'ban' else '解封'}完成: 成功 {success_count}/{len(switches)} 台交换机"
    }


@tool_registry.register(
    name='get_ban_records',
    description='获取封禁记录列表，查看所有已封禁的IP地址和封禁时间',
    parameters={
        'type': 'object',
        'properties': {
            'switch_ip': {
                'type': 'string',
                'description': '交换机IP地址，默认为192.168.0.1',
                'default': '192.168.0.1',
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

    switch_ip = args.get('switch_ip', '192.168.0.1')
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

        # 获取攻击来源Top10（按IP聚合）
        from database.db import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT attack_ip, COUNT(*) as count
            FROM attack_logs
            GROUP BY attack_ip
            ORDER BY count DESC
            LIMIT 10
        """)
        top_ips = [
            {"ip": row["attack_ip"], "count": row["count"]}
            for row in cursor.fetchall()
        ]
        conn.close()

        return {
            'ok': True,
            '总攻击次数': stats.get('total', 0),
            '热门攻击服务': stats.get('service_stats', []),
            '攻击来源Top10': top_ips,
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

    # 查找 fscan 可执行文件：环境变量 -> 本地目录 -> 系统 PATH
    fscan_path = None
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_fscan = os.environ.get('FSCAN_PATH', '').strip().strip('"')
    local_candidates = [
        os.path.join(base_dir, 'lib', 'fscan.exe'),
        os.path.join(base_dir, 'bin', 'fscan.exe'),
        os.path.join(base_dir, 'plugin', 'bin', 'fscan.exe'),
    ]

    if env_fscan:
        if os.path.isfile(env_fscan):
            fscan_path = env_fscan
        else:
            return {'ok': False, 'error': f'环境变量 FSCAN_PATH 指向文件不存在: {env_fscan}'}

    if not fscan_path:
        for candidate in local_candidates:
            if os.path.isfile(candidate):
                fscan_path = candidate
                break

    if not fscan_path:
        system_fscan = shutil.which('fscan')
        if system_fscan:
            fscan_path = system_fscan

    if not fscan_path:
        fallback_dirs = ' | '.join(sorted({os.path.dirname(p) for p in local_candidates}))
        return {'ok': False, 'error': f'未找到 fscan.exe，请放置到: {fallback_dirs}，或配置 FSCAN_PATH，或加入系统 PATH'}

    try:
        import tempfile
        # 创建临时文件存储JSON输出
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as tf:
            json_file = tf.name

        # 构建fscan命令: fscan -h <target> -t <threads> -p <ports> -nobr -nopoc -o <tmpfile> -f json
        cmd = [fscan_path, '-h', target, '-t', str(threads), '-p', port, '-nobr', '-nopoc', '-o', json_file, '-f', 'json']

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
                        # fscan 输出是 JSON Lines 格式（每行一个JSON），尝试解析
                        try:
                            scan_data = json.loads(content)
                        except json.JSONDecodeError:
                            # JSON Lines 格式：使用 }\n{ 分隔符分割
                            items = []
                            content_replaced = content.replace('}\n{', '}§{')
                            for chunk in content_replaced.split('§'):
                                chunk = chunk.strip()
                                if chunk:
                                    try:
                                        items.append(json.loads(chunk))
                                    except json.JSONDecodeError:
                                        continue
                            scan_data = items if items else None
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

            # 判断是否为 JSON Lines 格式（每行一个JSON对象）
            if isinstance(scan_data, list) and len(scan_data) > 0:
                # JSON Lines 格式：解析 fscan 的输出格式
                host_ports = {}
                for item in scan_data:
                    item_type = item.get('type', '')
                    target_ip = item.get('target', '')
                    if not target_ip:
                        continue
                    if item_type == 'HOST':
                        if target_ip not in host_ports:
                            host_ports[target_ip] = []
                    elif item_type == 'PORT':
                        port = item.get('details', {}).get('port')
                        if port and target_ip not in host_ports:
                            host_ports[target_ip] = []
                        if port:
                            host_ports.setdefault(target_ip, []).append(str(port))
                        elif target_ip not in host_ports:
                            host_ports.setdefault(target_ip, [])

                for ip in sorted(host_ports.keys()):
                    hosts.append({
                        'ip': ip,
                        'hostname': '',
                        'ports': ','.join(sorted(host_ports[ip], key=lambda x: int(x) if x.isdigit() else 0)) if host_ports[ip] else ''
                    })
            else:
                # 旧格式：解析主机列表
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


@tool_registry.register(
    name='take_screenshot',
    description='对指定 IP 的 Web 服务进行页面截图。当用户需要查看某个 IP 的 Web 界面、登录后台、查看设备管理页面时使用此工具。返回截图文件路径。',
    parameters={
        'type': 'object',
        'properties': {
            'url': {
                'type': 'string',
                'description': '要截图的完整 URL，如 http://192.168.0.1 或 https://example.com:8443',
            },
            'ip': {
                'type': 'string',
                'description': '目标 IP 地址（如 192.168.0.1）',
            },
            'port': {
                'type': 'integer',
                'description': '目标端口（如 80, 443, 8080）',
            },
        },
        'required': ['url', 'ip', 'port'],
    },
)
def _take_screenshot(args: dict, cfg: dict = None) -> dict:
    """Web 页面截图工具"""
    import os
    import sys
    import json as _json

    url = str(args.get('url', '')).strip()
    ip = str(args.get('ip', '')).strip()
    port = int(args.get('port', 80))

    if not url or not ip:
        return {'ok': False, 'error': '缺少必要参数: url, ip'}

    try:
        plugin_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'plugin')
        if plugin_dir not in sys.path:
            sys.path.insert(0, plugin_dir)

        from web_screenshot import take_screenshot
        from database.models import ScreenshotModel

        from datetime import datetime
        scan_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        path = take_screenshot(url, ip, port)
        if path and os.path.exists(path):
            ScreenshotModel.save_screenshot(ip, port, url, path, scan_time)
            return {
                'ok': True,
                'ip': ip,
                'port': port,
                'url': url,
                'screenshot_path': path,
                'screenshot_url': f'/api/nmap/screenshot/{ip}/{port}',
                'message': '截图成功',
            }
        else:
            return {'ok': False, 'error': '截图失败，请检查目标是否可访问'}
    except ImportError as e:
        return {'ok': False, 'error': f'缺少依赖: {e}，请安装 playwright'}
    except Exception as e:
        return {'ok': False, 'error': f'截图异常: {e}'}


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
