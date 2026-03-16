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

defense_bp = Blueprint('defense', __name__, url_prefix='/api/v1/defense')


@defense_bp.route('/hfish/logs', methods=['GET'])
@require_auth
def defense_hfish_logs():
    """Get HFish attack logs with pagination"""
    page = _parse_int_arg('page', 1)
    page_size = _parse_int_arg('page_size', 50)
    offset = (page - 1) * page_size
    aggregated = _as_bool(request.args.get('aggregated', '0'))
    service_name = request.args.get('service_name')
    threat_level = request.args.get('threat_level')

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
                                       threat_level=threat_level,
                                       service_name=service_name)
    conn.close()
    return ok({'items': logs, 'total': total, 'page': page, 'page_size': page_size})


@defense_bp.route('/hfish/stats', methods=['GET'])
@require_auth
def defense_hfish_stats():
    """Get HFish stats"""
    return ok(HFishModel.get_stats())


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
            MAX(create_time) as latest_attack_time,
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
            strftime('%Y-%m-%d %H:00', create_time) as hour,
            COUNT(*) as count
        FROM attack_logs {where_sql}
        AND create_time >= datetime('now', '-7 days')
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
            client_id, create_time_str, threat_level, payload
        FROM attack_logs {where_sql}
        ORDER BY create_time DESC
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
            'threat_level': row['threat_level'],
            'payload': row['payload']
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
    def _do():
        try:
            run_hfish_sync()
        except Exception:
            pass
    _run_daemon(_do)
    return ok({'message': '同步任务已触发'})


@defense_bp.route('/hfish/test', methods=['POST'])
@require_auth
def defense_hfish_test():
    """Test HFish connectivity"""
    body = _body()
    cfg = _load_cfg()
    hcfg = cfg.get('hfish', {})
    host_port = (body.get('host_port') or hcfg.get('host_port') or '').strip()
    api_key = (body.get('api_key') or hcfg.get('api_key') or '').strip()

    if not host_port or not api_key:
        return err('请先填写 HFish 地址和 API Key', 400)

    try:
        import requests
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        url = f"https://{host_port}/api/v1/attack/detail?api_key={api_key}"
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
        resp = requests.post(url, json=payload, verify=False, timeout=15)
        resp.raise_for_status()
        _ = resp.json()
        return ok({'reachable': True, 'host_port': host_port})
    except Exception as e:
        return err(f'HFish 连接失败: {e}', 502)


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

