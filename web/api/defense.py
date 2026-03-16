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

defense_bp = Blueprint('defense', __name__, url_prefix='/defense')


def _run_daemon(task):
    import threading
    threading.Thread(target=task, daemon=True).start()


@defense_bp.route('/hfish/logs', methods=['GET'])
@require_auth
def defense_hfish_logs():
    """Get HFish attack logs"""
    limit = _parse_int_arg('limit', 200)
    offset = _parse_int_arg('offset', 0)
    aggregated = _as_bool(request.args.get('aggregated', '0'))
    service_name = request.args.get('service_name')
    threat_level = request.args.get('threat_level')

    if aggregated:
        conn = get_connection()
        c = conn.cursor()
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
        params += [limit, offset]
        c.execute(q, params)
        rows = [dict(r) for r in c.fetchall()]
        conn.close()

        ai_all = AiModel.get_all_analyses()
        for row in rows:
            a = ai_all.get(row['attack_ip'])
            row['decision'] = a['decision'] if a else None
            row['ai_analysis'] = a['analysis_text'] if a else None
        return ok({'items': rows, 'total': len(rows)})

    logs = HFishModel.get_attack_logs(limit=limit, offset=offset,
                                       threat_level=threat_level,
                                       service_name=service_name)
    return ok({'items': logs, 'total': len(logs)})


@defense_bp.route('/hfish/stats', methods=['GET'])
@require_auth
def defense_hfish_stats():
    """Get HFish stats"""
    return ok(HFishModel.get_stats())


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

    # 查询events，关联AI分析结果
    q = """
        SELECT
            al.id,
            al.attack_ip,
            al.service_name as event_type,
            al.threat_level as severity,
            al.create_time_str as created_at,
            am.decision as ai_decision,
            am.analysis_text as ai_analysis,
            COALESCE(am.status, 'pending') as status
        FROM attack_logs al
        LEFT JOIN ai_analysis_logs am ON al.attack_ip = am.ip
        ORDER BY al.id DESC
        LIMIT ? OFFSET ?
    """
    c.execute(q, [page_size, offset])
    rows = [dict(r) for r in c.fetchall()]

    # 获取总数
    c.execute("SELECT COUNT(*) as total FROM attack_logs")
    total = c.fetchone()['total']

    conn.close()
    return ok({'items': rows, 'total': total})


@defense_bp.route('/events/<int:event_id>/approve', methods=['POST'])
@require_auth
def defense_event_approve(event_id: int):
    """Approve a defense event"""
    conn = get_connection()
    c = conn.cursor()
    # 通过event_id获取attack_ip，然后更新ai_analysis_logs表
    c.execute("SELECT attack_ip FROM attack_logs WHERE id = ?", (event_id,))
    row = c.fetchone()
    if row:
        attack_ip = row['attack_ip']
        c.execute("UPDATE ai_analysis_logs SET status = 'approved' WHERE ip = ?", (attack_ip,))
        conn.commit()
    conn.close()
    return ok({'message': '已批准'})


@defense_bp.route('/events/<int:event_id>/reject', methods=['POST'])
@require_auth
def defense_event_reject(event_id: int):
    """Reject a defense event"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT attack_ip FROM attack_logs WHERE id = ?", (event_id,))
    row = c.fetchone()
    if row:
        attack_ip = row['attack_ip']
        c.execute("UPDATE ai_analysis_logs SET status = 'rejected' WHERE ip = ?", (attack_ip,))
        conn.commit()
    conn.close()
    return ok({'message': '已拒绝'})


@defense_bp.route('/events/<int:event_id>/false-positive', methods=['POST'])
@require_auth
def defense_event_false_positive(event_id: int):
    """Mark event as false positive"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT attack_ip FROM attack_logs WHERE id = ?", (event_id,))
    row = c.fetchone()
    if row:
        attack_ip = row['attack_ip']
        c.execute("UPDATE ai_analysis_logs SET status = 'false_positive' WHERE ip = ?", (attack_ip,))
        conn.commit()
    conn.close()
    return ok({'message': '已标记为误报'})

