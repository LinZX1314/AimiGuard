"""
Defense Module - HFish and defense endpoints
"""
import time
from flask import Blueprint, request
from database.models import HFishModel, AiModel
from database.db import get_connection
from .helpers import (
    require_auth, ok, err, _body, _load_cfg, _save_cfg,
    _parse_int_arg, _as_bool
)
from .runtime import run_hfish_sync, _run_daemon
from .upload import (
    TERMINAL_COUNTER_SERVICE_NAME,
    collect_terminal_evidence_events,
)

defense_bp = Blueprint('defense', __name__, url_prefix='/api/v1/defense')


def _build_terminal_hfish_logs():
    """将终端取证事件映射为蜜罐日志结构，便于与现有前端统一展示。"""
    events = collect_terminal_evidence_events()
    logs = []
    for index, item in enumerate(events):
        timestamp = int(item.get('mtime') or 0)
        report_ip = item.get('report_ip') or item.get('terminal_ip') or item.get('client_ip') or '-'
        logs.append({
            'id': timestamp * 1000 + index,
            'attack_ip': report_ip,
            'ip_location': item.get('client_host') or '终端回传节点',
            'service_name': TERMINAL_COUNTER_SERVICE_NAME,
            'service_port': '-',
            'client_id': item.get('event_key') or '-',
            'client_name': '终端取证',
            'attack_time': item.get('time') or '-',
            'create_time_str': item.get('time') or '-',
            'create_time_timestamp': timestamp,
            'threat_level': 'high',
            'payload': (
                f"截图: {item.get('screenshot_filename') or '-'}; "
                f"摄像头: {item.get('camera_filename') or '-'}; "
                f"上报IP: {report_ip}; "
                f"客户端时间: {item.get('client_time') or '-'}; "
                f"终端IP: {item.get('terminal_ip') or item.get('client_ip') or '-'}"
            ),
            'preview_url': item.get('preview_url') or '',
            'screenshot_url': item.get('screenshot_url') or '',
            'camera_url': item.get('camera_url') or '',
            'screenshot_filename': item.get('screenshot_filename') or '',
            'camera_filename': item.get('camera_filename') or '',
            'upload_api': report_ip,
            'report_ip': report_ip,
            'upload_endpoint': item.get('upload_endpoint') or '',
            'client_time': item.get('client_time') or '',
            'client_name': item.get('client_name') or '终端取证客户端',
            'client_host': item.get('client_host') or '',
            'terminal_ip': item.get('terminal_ip') or item.get('client_ip') or '',
            'client_ip': item.get('terminal_ip') or item.get('client_ip') or '',
            'capture_summary': item.get('capture_summary') or '截图',
            'jump_path': item.get('jump_path') or '/screenshots',
            'is_combined': bool(item.get('is_combined')),
            'attack_count': 1,
        })
    return logs


@defense_bp.route('/terminal-evidence', methods=['GET'])
@require_auth
def defense_terminal_evidence():
    """终端取证列表：归属于防御域，供首页/蜜罐/截图取证统一消费。"""
    limit = _parse_int_arg('limit', 200, max_value=1000)
    items = collect_terminal_evidence_events(limit=limit)
    return ok({
        'items': items,
        'total': len(items),
        'high_count': len(items),
    })


@defense_bp.route('/hfish/logs', methods=['GET'])
@require_auth
def defense_hfish_logs():
    """Get HFish attack logs with pagination"""
    page = _parse_int_arg('page', 1, max_value=10000)
    page_size = _parse_int_arg('page_size', 50, max_value=500)
    offset = (page - 1) * page_size
    aggregated = _as_bool(request.args.get('aggregated', '0'))
    service_name = request.args.get('service_name')

    # 终端取证是反制蜜罐的一部分：按单次取证事件返回。
    if service_name == TERMINAL_COUNTER_SERVICE_NAME:
        terminal_logs = _build_terminal_hfish_logs()
        total = len(terminal_logs)

        if aggregated:
            grouped: dict[str, dict] = {}
            for row in terminal_logs:
                key = row['attack_ip']
                hit = grouped.get(key)
                if hit is None:
                    grouped[key] = {
                        'attack_ip': row['attack_ip'],
                        'ip_location': row['ip_location'],
                        'service_name': TERMINAL_COUNTER_SERVICE_NAME,
                        'attack_count': 1,
                        'latest_time': row['create_time_str'],
                    }
                else:
                    hit['attack_count'] += 1
                    if str(row['create_time_str']) > str(hit['latest_time']):
                        hit['latest_time'] = row['create_time_str']

            grouped_rows = sorted(grouped.values(), key=lambda x: x['attack_count'], reverse=True)
            paged_grouped = grouped_rows[offset: offset + page_size]
            return ok({'items': paged_grouped, 'total': total, 'page': page, 'page_size': page_size})

        paged_logs = terminal_logs[offset: offset + page_size]
        return ok({'items': paged_logs, 'total': total, 'page': page, 'page_size': page_size})

    conn = get_connection()
    c = conn.cursor()

    # Get total count first
    count_q = "SELECT COUNT(*) as total FROM attack_logs WHERE 1=1"
    count_params = []
    if service_name:
        count_q += ' AND service_name = ?'
        count_params.append(service_name)
    c.execute(count_q, count_params)
    total = c.fetchone()['total']

    if aggregated:
        q = """
            SELECT attack_ip,
                   MAX(ip_location) as ip_location,
                   GROUP_CONCAT(DISTINCT service_name) as service_name,
                   COUNT(*) as attack_count,
                   MAX(create_time_str) as latest_time
            FROM attack_logs WHERE 1=1
        """
        params = []
        if service_name:
            q += ' AND service_name = ?'
            params.append(service_name)
        q += ' GROUP BY attack_ip ORDER BY attack_count DESC LIMIT ? OFFSET ?'
        params += [page_size, offset]
        c.execute(q, params)
        rows = [dict(r) for r in c.fetchall()]

        ai_all = AiModel.get_all_analyses()
        for row in rows:
            a = ai_all.get(row['attack_ip'])
            row['decision'] = a['decision'] if a else None
            row['ai_analysis'] = a['analysis_text'] if a else None
        conn.close()
        return ok({'items': rows, 'total': total, 'page': page, 'page_size': page_size})

    logs = HFishModel.get_attack_logs(limit=page_size, offset=offset,
                                       service_name=service_name)
    conn.close()
    return ok({'items': logs, 'total': total, 'page': page, 'page_size': page_size})


@defense_bp.route('/hfish/stats', methods=['GET'])
@require_auth
def defense_hfish_stats():
    """Get HFish stats"""
    conn = get_connection()
    c = conn.cursor()

    # Get overall stats
    c.execute('SELECT COUNT(*) as total FROM attack_logs')
    total = c.fetchone()['total']
    c.execute('SELECT COUNT(DISTINCT attack_ip) as ip_count FROM attack_logs')
    ip_count = c.fetchone()['ip_count']
    c.execute('SELECT COUNT(DISTINCT service_name) as service_count FROM attack_logs')
    service_count = c.fetchone()['service_count']

    terminal_events = collect_terminal_evidence_events()
    terminal_total = len(terminal_events)

    # Get per-service stats (service_stats for frontend compatibility)
    c.execute("""
        SELECT
            COALESCE(service_name, '未知') as name,
            COUNT(*) as count
        FROM attack_logs
        GROUP BY service_name
        ORDER BY count DESC
    """)
    service_stats = [{'name': r['name'], 'count': r['count']} for r in c.fetchall()]

    if terminal_total > 0:
        service_stats.append({'name': TERMINAL_COUNTER_SERVICE_NAME, 'count': terminal_total})
        service_stats.sort(key=lambda x: x['count'], reverse=True)
        service_count += 1
        total += terminal_total

    conn.close()
    return ok({
        'total': total,
        'unique_ips': ip_count,
        'services': service_count,
        'service_stats': service_stats,
    })


@defense_bp.route('/hfish/types', methods=['GET'])
@require_auth
def defense_hfish_types():
    """Get attack types overview with aggregated stats per type"""
    conn = get_connection()
    c = conn.cursor()

    # Get all service types with aggregated stats
    q = """
        SELECT
            service_name,
            COUNT(*) as total_attacks,
            COUNT(DISTINCT attack_ip) as unique_ips,
            COUNT(DISTINCT client_id) as unique_nodes,
            MAX(create_time_str) as latest_attack_time,
            MAX(create_time_str) as latest_attack_time_str
        FROM attack_logs
        GROUP BY service_name
        ORDER BY total_attacks DESC
    """
    c.execute(q)
    rows = [dict(r) for r in c.fetchall()]

    # Get total count
    c.execute("SELECT COUNT(*) as total FROM attack_logs")
    total_count = c.fetchone()['total']

    conn.close()

    types = [
        {
            'name': r['service_name'] or '未知',
            'total_attacks': r['total_attacks'],
            'unique_ips': r['unique_ips'],
            'unique_nodes': r['unique_nodes'],
            'latest_attack_time': r['latest_attack_time_str'] or '-'
        }
        for r in rows
    ]

    return ok({'types': types, 'total_count': total_count})


@defense_bp.route('/hfish/type/<service_name>', methods=['GET'])
@require_auth
def defense_hfish_type_detail(service_name):
    """Get detailed data for a specific attack type"""
    page = _parse_int_arg('page', 1)
    page_size = _parse_int_arg('page_size', 20)
    offset = (page - 1) * page_size

    conn = get_connection()
    c = conn.cursor()

    # Decode service_name (URL encoded)
    from urllib.parse import unquote
    svc_name = unquote(service_name)

    # Build where clause
    where_sql = "WHERE service_name = ?" if svc_name != 'ALL' else "WHERE 1=1"
    params = [svc_name] if svc_name != 'ALL' else []

    # 1. Get aggregated stats for this type
    stats_q = f"""
        SELECT
            COUNT(*) as total_attacks,
            COUNT(DISTINCT attack_ip) as unique_ips,
            COUNT(DISTINCT client_id) as unique_nodes,
            MAX(create_time_str) as latest_attack_time
        FROM attack_logs {where_sql}
    """
    c.execute(stats_q, params)
    stats_row = dict(c.fetchone())

    # 2. Get attack trend (last 7 days, hourly)
    import time
    from datetime import datetime, timedelta

    trend_q = f"""
        SELECT
            strftime('%Y-%m-%d %H:00', create_time_str) as hour,
            COUNT(*) as count
        FROM attack_logs {where_sql}
        AND create_time_str >= datetime('now', '-7 days')
        GROUP BY hour
        ORDER BY hour ASC
    """
    c.execute(trend_q, params)
    trend_rows = [dict(r) for r in c.fetchall()]

    # 3. Get top source IPs for this type
    top_ips_q = f"""
        SELECT attack_ip, COUNT(*) as count
        FROM attack_logs {where_sql}
        GROUP BY attack_ip
        ORDER BY count DESC
        LIMIT 10
    """
    c.execute(top_ips_q, params)
    top_ips = [dict(r) for r in c.fetchall()]

    # 4. Get paginated raw logs as cards
    logs_q = f"""
        SELECT
            id, attack_ip, ip_location, service_name, service_port,
            client_id, create_time_str
        FROM attack_logs {where_sql}
        ORDER BY create_time_timestamp DESC
        LIMIT ? OFFSET ?
    """
    c.execute(logs_q, params + [page_size, offset])

    logs = []
    for r in c.fetchall():
        row = dict(r)
        logs.append({
            'id': row['id'],
            'attack_ip': row['attack_ip'],
            'ip_location': row['ip_location'] or '未知',
            'service_port': row['service_port'],
            'client_id': row['client_id'],
            'attack_time': row['create_time_str'],
        })

    # 5. Get total count for pagination
    count_q = f"SELECT COUNT(*) as total FROM attack_logs {where_sql}"
    c.execute(count_q, params)
    total = c.fetchone()['total']

    conn.close()

    return ok({
        'stats': {
            'total_attacks': stats_row['total_attacks'] or 0,
            'unique_ips': stats_row['unique_ips'] or 0,
            'unique_nodes': stats_row['unique_nodes'] or 0,
            'latest_attack_time': stats_row['latest_attack_time'] or '-'
        },
        'trend': {
            'labels': [r['hour'] for r in trend_rows],
            'values': [r['count'] for r in trend_rows]
        },
        'top_ips': top_ips,
        'logs': logs,
        'total': total,
        'page': page,
        'page_size': page_size
    })


@defense_bp.route('/hfish/charts', methods=['GET'])
@require_auth
def defense_hfish_charts():
    """Get HFish chart data (computed on backend for performance)"""
    service_name = request.args.get('service_name')

    conn = get_connection()
    c = conn.cursor()

    # Build where clause
    where_sql = "WHERE 1=1"
    params = []
    if service_name:
        where_sql += " AND service_name = ?"
        params.append(service_name)

    # 1. 攻击来源 Top 15 IP
    ip_q = f"""
        SELECT attack_ip, SUM(attack_count) as attack_count
        FROM (
            SELECT attack_ip, COUNT(*) as attack_count
            FROM attack_logs {where_sql}
            GROUP BY attack_ip
        )
        GROUP BY attack_ip
        ORDER BY attack_count DESC
        LIMIT 15
    """
    c.execute(ip_q, params * 2 if service_name else params)
    ip_rows = [dict(r) for r in c.fetchall()]

    # Reverse for bar chart (top IP at top)
    top_ips = {
        'labels': [r['attack_ip'] for r in reversed(ip_rows)],
        'values': [r['attack_count'] for r in reversed(ip_rows)]
    }

    # 2. 攻击服务分布 Top 8
    svc_q = f"""
        SELECT service_name, COUNT(*) as attack_count
        FROM attack_logs {where_sql}
        GROUP BY service_name
        ORDER BY attack_count DESC
        LIMIT 8
    """
    c.execute(svc_q, params)
    svc_rows = [dict(r) for r in c.fetchall()]

    # Get total for percentage calculation
    total_q = f"SELECT COUNT(*) as total FROM attack_logs {where_sql}"
    c.execute(total_q, params)
    total_count = c.fetchone()['total']

    service_dist = {
        'items': [
            {
                'name': r['service_name'] or '未知',
                'value': r['attack_count'],
                'percent': round(r['attack_count'] / total_count * 100, 1) if total_count > 0 else 0
            }
            for r in svc_rows
        ]
    }

    conn.close()
    return ok({
        'top_ips': top_ips,
        'service_dist': service_dist,
        'total_count': total_count
    })


@defense_bp.route('/hfish/sync', methods=['POST'])
@require_auth
def defense_hfish_sync():
    """Trigger HFish sync"""
    result = run_hfish_sync()
    return ok(result)


@defense_bp.route('/hfish/test', methods=['POST'])
@require_auth
def defense_hfish_test():
    """Test HFish connectivity"""
    body = _body()
    cfg = _load_cfg()
    hcfg = cfg.get('hfish', {})
    host_port = (body.get('host_port') or hcfg.get('host_port') or '').strip()
    api_base_url = (body.get('api_base_url') or hcfg.get('api_base_url') or '').strip().rstrip('/')
    api_key = (body.get('api_key') or hcfg.get('api_key') or '').strip()

    if (not host_port and not api_base_url) or not api_key:
        return err('请先填写 HFish 地址和 API Key', 400)

    try:
        import requests
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        def build_test_urls() -> list[str]:
            urls: list[str] = []

            if api_base_url:
                urls.append(f"{api_base_url}/api/v1/attack/detail?api_key={api_key}")

            if host_port:
                hp = host_port.rstrip('/')
                if hp.startswith('http://') or hp.startswith('https://'):
                    urls.append(f"{hp}/api/v1/attack/detail?api_key={api_key}")
                else:
                    # 优先 HTTPS，再自动回退 HTTP，兼容历史部署
                    urls.append(f"https://{hp}/api/v1/attack/detail?api_key={api_key}")
                    urls.append(f"http://{hp}/api/v1/attack/detail?api_key={api_key}")

            # 去重，保留顺序
            return list(dict.fromkeys(urls))

        urls = build_test_urls()
        if not urls:
            return err('HFish 地址配置无效', 400)

        payload = {
            'start_time': int(time.time()) - 60,
            'end_time': 0,
            'page_no': 1,
            'page_size': 1,
            'intranet': -1,
            'threat_label': [],
            'client_id': [],
            'service_name': [],
            'info_confirm': '0',
        }

        last_error: Exception | None = None
        for url in urls:
            try:
                resp = requests.post(url, json=payload, verify=False, timeout=15)
                resp.raise_for_status()
                _ = resp.json()
                return ok({'reachable': True, 'host_port': host_port, 'url': url})
            except Exception as e:
                last_error = e

        return err(f'HFish 连接失败: {last_error}', 502)
    except Exception as e:
        return err(f'HFish 连接失败: {e}', 502)


@defense_bp.route('/switch/test', methods=['POST'])
@require_auth
def defense_switch_test():
    """Test switch connectivity"""
    body = _body()
    host = body.get('host', '').strip()
    port = body.get('port', 23)
    password = body.get('password', '').strip()

    if not host:
        return err('请提供交换机IP地址', 400)

    try:
        import socket
        import telnetlib3 as telnetlib
        import asyncio

        # 测试端口连通性
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, int(port)))
        sock.close()

        if result != 0:
            return err(f'无法连接到 {host}:{port}，端口不可达', 502)

        # 尝试Telnet登录 (telnetlib3 是异步的)
        try:
            async def test_telnet():
                try:
                    # telnetlib3 使用异步连接
                    reader, writer = await asyncio.wait_for(
                        telnetlib.open_connection(host, int(port)),
                        timeout=5.0
                    )
                    
                    # 等待登录提示
                    data = await asyncio.wait_for(reader.read(1024), timeout=3.0)
                    
                    # 发送密码
                    if b'Password' in data or b'password' in data:
                        writer.write(password.encode('ascii') + b'\r\n')
                        await writer.drain()
                        await asyncio.sleep(1)
                        
                        # 读取响应
                        response = await asyncio.wait_for(reader.read(1024), timeout=3.0)
                        response_text = response.decode('ascii', errors='ignore')
                        
                        writer.close()
                        await writer.wait_closed()
                        
                        if '>' in response_text or '#' in response_text:
                            return {'success': True, 'response': response_text}
                        else:
                            return {'success': True, 'warning': '已连接但可能需要验证密码'}
                    else:
                        writer.close()
                        await writer.wait_closed()
                        return {'success': True, 'warning': '已连接但未收到密码提示'}
                        
                except asyncio.TimeoutError:
                    return {'success': False, 'error': '连接超时'}
                except Exception as e:
                    return {'success': False, 'error': str(e)}
            
            # 运行异步测试
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(test_telnet())
            loop.close()
            
            if result.get('success'):
                return ok({
                    'reachable': True, 
                    'host': host, 
                    'port': port,
                    'warning': result.get('warning')
                })
            else:
                return ok({
                    'reachable': True, 
                    'host': host, 
                    'port': port, 
                    'warning': f'端口可达但Telnet连接失败: {result.get("error")}'
                })
                
        except Exception as e:
            return ok({'reachable': True, 'host': host, 'port': port, 'warning': f'端口可达但Telnet连接失败: {str(e)}'})

    except socket.timeout:
        return err(f'连接 {host}:{port} 超时', 504)
    except Exception as e:
        return err(f'测试失败: {str(e)}', 500)


@defense_bp.route('/switch/statuses', methods=['GET'])
@require_auth
def defense_switch_statuses():
    """Get switch online statuses (TCP reachability)."""
    cfg = _load_cfg()
    strict_mode = _as_bool(request.args.get('strict', '0'))
    raw_switches = cfg.get('switches', [])

    items = []
    total = 0
    enabled = 0
    online = 0

    try:
        import socket

        async def _telnet_probe(host: str, port: int, password: str) -> tuple[bool, str]:
            try:
                import asyncio
                import telnetlib3 as telnetlib

                reader, writer = await asyncio.wait_for(
                    telnetlib.open_connection(host, int(port)),
                    timeout=4.0
                )

                banner = await asyncio.wait_for(reader.read(1024), timeout=2.5)
                banner_text = (banner or '').lower()

                # 严格模式：要求至少出现密码提示并返回命令提示符
                if 'password' in banner_text:
                    writer.write((password or '') + '\r\n')
                    await writer.drain()
                    await asyncio.sleep(0.8)
                    response = await asyncio.wait_for(reader.read(1024), timeout=2.5)
                    response_text = response or ''
                    ok = ('>' in response_text) or ('#' in response_text)
                else:
                    response_text = banner or ''
                    ok = ('>' in response_text) or ('#' in response_text)

                writer.close()
                await writer.wait_closed()
                return (ok, '' if ok else 'Telnet握手成功但未进入命令模式')
            except Exception as e:
                return (False, str(e))

        for sw in raw_switches:
            if not isinstance(sw, dict):
                continue

            host = str(sw.get('host', '')).strip()
            if not host:
                continue

            port = int(sw.get('port', 23))
            acl_number = int(sw.get('acl_number', 30))
            is_enabled = _as_bool(sw.get('enabled', True))

            total += 1
            if is_enabled:
                enabled += 1

            is_online = False
            error = ''
            if is_enabled:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(2)
                    result = sock.connect_ex((host, port))
                    sock.close()
                    if result != 0:
                        error = f'端口不可达({result})'
                    else:
                        if strict_mode:
                            try:
                                import asyncio
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                telnet_ok, telnet_error = loop.run_until_complete(_telnet_probe(host, port, str(sw.get('password', '')).strip()))
                                loop.close()
                                is_online = telnet_ok
                                if not telnet_ok:
                                    error = telnet_error or 'Telnet 登录验证失败'
                            except Exception as e:
                                is_online = False
                                error = f'严格模式检测失败: {e}'
                        else:
                            is_online = True

                        if is_online:
                            online += 1
                except Exception as e:
                    error = str(e)

            items.append({
                'host': host,
                'port': port,
                'acl_number': acl_number,
                'enabled': is_enabled,
                'online': is_online,
                'error': error,
            })

        return ok({
            'items': items,
            'total': total,
            'enabled': enabled,
            'online': online,
            'strict': strict_mode,
        })
    except Exception as e:
        return err(f'获取交换机状态失败: {e}', 500)




@defense_bp.route('/events', methods=['GET'])
@require_auth
def defense_events():
    """Get defense events with pagination"""
    page = _parse_int_arg('page', 1)
    page_size = _parse_int_arg('page_size', 50)
    offset = (page - 1) * page_size

    conn = get_connection()
    c = conn.cursor()

    # 确保status字段存在
    try:
        c.execute("ALTER TABLE ai_analysis_logs ADD COLUMN status TEXT DEFAULT 'pending'")
        conn.commit()
    except Exception:
        pass  # 字段可能已存在

    # 查询events，按 IP 合并，关联AI分析结果
    q = """
        SELECT
            MAX(al.id) as id,
            al.attack_ip,
            MAX(al.ip_location) as ip_location,
            COUNT(*) as attack_count,
            GROUP_CONCAT(DISTINCT al.service_name) as event_type,
            MAX(al.create_time_str) as created_at,
            am.decision as ai_decision,
            am.analysis_text as ai_analysis,
            COALESCE(am.status, 'pending') as status
        FROM attack_logs al
        LEFT JOIN ai_analysis_logs am ON al.attack_ip = am.ip
        GROUP BY al.attack_ip
        ORDER BY id DESC
        LIMIT ? OFFSET ?
    """
    c.execute(q, [page_size, offset])
    rows = [dict(r) for r in c.fetchall()]

    # 获取总IP数
    c.execute("SELECT COUNT(DISTINCT attack_ip) as total FROM attack_logs")
    total = c.fetchone()['total']

    conn.close()
    return ok({'items': rows, 'total': total})


@defense_bp.route('/events/<int:event_id>/approve', methods=['POST'])
@require_auth
def defense_event_approve(event_id: int):
    """Approve a defense event and trigger physical ban"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT attack_ip FROM attack_logs WHERE id = ?", (event_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return err('事件不存在', 404)
        
    attack_ip = row['attack_ip']
    
    # 1. 物理封禁 (如果尚未封禁)
    cfg = _load_cfg()
    from ai.tools import execute_tool
    import json
    
    # 获取AI决策状态
    c.execute("SELECT decision FROM ai_analysis_logs WHERE ip = ?", (attack_ip,))
    ai_row = c.fetchone()
    already_banned = ai_row and ai_row['decision'] == '已封禁'
    
    if not already_banned:
        # 触发物理封禁
        res_str = execute_tool('switch_acl_config', {'action': 'ban', 'target_ip': attack_ip, 'description': '手动确认封禁'}, cfg)
        try:
            res = json.loads(res_str)
            if not res.get('ok'):
                conn.close()
                return err(f"物理封禁失败: {res.get('error')}", 500)
        except:
            pass

    # 2. 更新数据库状态
    c.execute("UPDATE ai_analysis_logs SET status = 'approved', decision = '已封禁' WHERE ip = ?", (attack_ip,))
    conn.commit()
    conn.close()
    return ok({'message': '已批准并执行物理封禁'})


@defense_bp.route('/events/<int:event_id>/reject', methods=['POST'])
@require_auth
def defense_event_reject(event_id: int):
    """Reject a defense event (Optional: trigger unban)"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT attack_ip FROM attack_logs WHERE id = ?", (event_id,))
    row = c.fetchone()
    if row:
        attack_ip = row['attack_ip']
        # 更新状态为已拒绝
        c.execute("UPDATE ai_analysis_logs SET status = 'rejected' WHERE ip = ?", (attack_ip,))
        conn.commit()
    conn.close()
    return ok({'message': '已拒绝'})


@defense_bp.route('/events/<int:event_id>/false-positive', methods=['POST'])
@require_auth
def defense_event_false_positive(event_id: int):
    """Mark event as false positive and trigger unban if needed"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT attack_ip FROM attack_logs WHERE id = ?", (event_id,))
    row = c.fetchone()
    if row:
        attack_ip = row['attack_ip']
        
        # 尝试物理回滚 (解封)
        cfg = _load_cfg()
        from ai.tools import execute_tool
        execute_tool('switch_acl_config', {'action': 'unban', 'target_ip': attack_ip}, cfg)
        
        c.execute("UPDATE ai_analysis_logs SET status = 'false_positive', decision = '不封禁' WHERE ip = ?", (attack_ip,))
        conn.commit()
    conn.close()
    return ok({'message': '已标记为误报并尝试解除封禁'})

