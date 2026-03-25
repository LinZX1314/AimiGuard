import os
import sys
import json
from datetime import datetime
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from database.db import get_connection, get_db_cursor
from database.workflow_models import WorkflowModel, WorkflowRunModel, WorkflowWebhookModel


def _time_str_to_timestamp(time_str: str) -> int:
    """将 `%Y-%m-%d %H:%M:%S` 时间字符串转为秒级时间戳；失败返回 0。"""
    try:
        return int(datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S').timestamp())
    except Exception:
        return 0


class NmapModel:
    """Nmap 结果查询模型：仅封装读取类接口。"""
    @staticmethod
    def get_latest_scan_id():
        with get_db_cursor() as cursor:
            cursor.execute('SELECT id FROM scans ORDER BY id DESC LIMIT 1')
            result = cursor.fetchone()
            return dict(result)['id'] if result else None

    @staticmethod
    def get_hosts(scan_id=None, limit=100, offset=0, state=None):
        with get_db_cursor() as cursor:
            if scan_id is None:
                cursor.execute('SELECT id FROM scans ORDER BY id DESC LIMIT 1')
                row = cursor.fetchone()
                scan_id = row['id'] if row else None

            if scan_id is None:
                return []

            query = "SELECT * FROM hosts WHERE scan_id = ?"
            params = [scan_id]

            if state:
                query += " AND state = ?"
                params.append(state)

            query += " ORDER BY ip LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_scans():
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM scans ORDER BY scan_time DESC LIMIT 50")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def clear_scan_history():
        """清理 Nmap 扫描历史（scans + hosts）。"""
        with get_db_cursor() as cursor:
            cursor.execute("DELETE FROM hosts")
            cursor.execute("DELETE FROM scans")

    @staticmethod
    def get_assets(limit=100, offset=0, mac_address=None, ip=None):
        with get_db_cursor() as cursor:
            query = "SELECT * FROM assets WHERE 1=1"
            params = []
            if mac_address:
                query += " AND mac_address LIKE ?"
                params.append(f"%{mac_address}%")
            if ip:
                query += " AND current_ip LIKE ?"
                params.append(f"%{ip}%")

            query += " ORDER BY last_seen DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_asset_ip_history(asset_id=None, mac_address=None, limit=200):
        with get_db_cursor() as cursor:
            resolved_asset_id = asset_id
            if resolved_asset_id is None and mac_address:
                cursor.execute("SELECT id FROM assets WHERE mac_address = ?", (mac_address,))
                row = cursor.fetchone()
                resolved_asset_id = row["id"] if row else None

            if resolved_asset_id is None:
                return []

            cursor.execute("""
                SELECT id, asset_id, ip, scan_id, seen_time
                FROM asset_ip_history
                WHERE asset_id = ?
                ORDER BY seen_time DESC
                LIMIT ?
            """, (resolved_asset_id, limit))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def get_stats():
        try:
            with get_db_cursor() as cursor:
                cursor.execute('SELECT id FROM scans ORDER BY id DESC LIMIT 1')
                row = cursor.fetchone()
                latest_scan_id = row['id'] if row else None
                if latest_scan_id is None:
                    return {"total": 0, "state_stats": [], "vendor_stats": []}

                cursor.execute("SELECT state, COUNT(*) as count FROM hosts WHERE scan_id = ? GROUP BY state", (latest_scan_id,))
                state_stats = [{"state": r[0], "count": r[1]} for r in cursor.fetchall()]

                cursor.execute("SELECT vendor, COUNT(*) as count FROM hosts WHERE scan_id = ? AND vendor != '' GROUP BY vendor ORDER BY count DESC LIMIT 10", (latest_scan_id,))
                vendor_stats = [{"vendor": r[0], "count": r[1]} for r in cursor.fetchall()]

                cursor.execute("SELECT COUNT(*) FROM hosts WHERE scan_id = ?", (latest_scan_id,))
                total = cursor.fetchone()[0]
                return {"total": total, "state_stats": state_stats, "vendor_stats": vendor_stats}
        except Exception:
            return {"total": 0, "state_stats": [], "vendor_stats": []}

    @staticmethod
    def get_latest_up_hosts():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM scans ORDER BY id DESC LIMIT 1')
        row = cursor.fetchone()
        if not row:
            conn.close()
            return []
        latest_scan_id = row['id']
        cursor.execute("SELECT ip, mac_address, os_type, os_tags FROM hosts WHERE scan_id = ? AND state = 'up'", (latest_scan_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def get_host_by_ip(ip, scan_id=None):
        conn = get_connection()
        cursor = conn.cursor()
        if scan_id:
            cursor.execute("SELECT * FROM hosts WHERE ip = ? AND scan_id = ?", (ip, scan_id))
        else:
            cursor.execute("""
                SELECT * FROM hosts WHERE ip = ? AND scan_id = (
                    SELECT id FROM scans ORDER BY id DESC LIMIT 1
                )
            """, (ip,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None


class ScannerModel:
    """Nmap 扫描落库模型：负责 scans/hosts/assets 写入。"""

    @staticmethod
    def create_scan(ip_ranges, arguments, scan_time):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO scans (scan_time, ip_ranges, arguments, hosts_count)
            VALUES (?, ?, ?, 0)
        ''', (scan_time, ','.join(ip_ranges) if isinstance(ip_ranges, list) else ip_ranges, arguments))
        scan_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return scan_id

    @staticmethod
    def save_host(scan_id, host, scan_time, open_ports_str, services_str):
        conn = get_connection()
        cursor = conn.cursor()
        web_fingerprints = host.get('web_fingerprints', [])
        cursor.execute('''
            INSERT INTO hosts
            (scan_id, ip, mac_address, vendor, hostname, state, os_type, os_accuracy, os_tags, open_ports, services, web_fingerprints, scan_time, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            scan_id, host.get('ip'), host.get('mac_address'), host.get('vendor'),
            host.get('hostname'), host.get('state'), host.get('os_type'),
            host.get('os_accuracy'), host.get('os_tags'), open_ports_str,
            services_str, json.dumps(web_fingerprints, ensure_ascii=False), scan_time, scan_time
        ))
        conn.commit()
        conn.close()

    @staticmethod
    def upsert_asset(scan_id, host, scan_time):
        conn = get_connection()
        cursor = conn.cursor()

        ip = (host.get('ip') or '').strip()
        mac_address = (host.get('mac_address') or '').strip()
        hostname = (host.get('hostname') or '').strip()
        vendor = (host.get('vendor') or '').strip()
        state = (host.get('state') or '').strip()
        os_type = (host.get('os_type') or '').strip()
        os_accuracy = (host.get('os_accuracy') or '').strip()
        os_tags = (host.get('os_tags') or '').strip()
        web_fingerprints = json.dumps(host.get('web_fingerprints', []), ensure_ascii=False)

        if not ip and not mac_address:
            conn.close()
            return

        if mac_address:
            cursor.execute('SELECT id, current_ip FROM assets WHERE mac_address = ?', (mac_address,))
        else:
            cursor.execute('SELECT id, current_ip FROM assets WHERE mac_address IS NULL AND current_ip = ? ORDER BY id DESC LIMIT 1', (ip,))

        existing = cursor.fetchone()
        old_ip = None

        if existing:
            asset_id, old_ip = existing[0], existing[1]
            cursor.execute('''
                UPDATE assets
                SET current_ip = ?, hostname = ?, vendor = ?, state = ?, os_type = ?, os_accuracy = ?, os_tags = ?,
                    web_fingerprints = ?, last_seen = ?, last_scan_id = ?
                WHERE id = ?
            ''', (ip, hostname, vendor, state, os_type, os_accuracy, os_tags, web_fingerprints, scan_time, scan_id, asset_id))
        else:
            cursor.execute('''
                INSERT INTO assets
                (mac_address, current_ip, hostname, vendor, state, os_type, os_accuracy, os_tags, web_fingerprints, first_seen, last_seen, last_scan_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (mac_address if mac_address else None, ip, hostname, vendor, state, os_type, os_accuracy, os_tags,
                  web_fingerprints, scan_time, scan_time, scan_id))
            asset_id = cursor.lastrowid

        if ip and old_ip != ip:
            cursor.execute('''
                INSERT OR IGNORE INTO asset_ip_history (asset_id, ip, scan_id, seen_time)
                VALUES (?, ?, ?, ?)
            ''', (asset_id, ip, scan_id, scan_time))

        conn.commit()
        conn.close()

    @staticmethod
    def increment_hosts_count(scan_id, count):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE scans SET hosts_count = hosts_count + ? WHERE id = ?', (count, scan_id))
        conn.commit()
        conn.close()


class HFishModel:
    """HFish 蜜罐数据模型"""

    @staticmethod
    def get_attack_logs(limit=50, offset=0, service_name=None):
        conn = get_connection()
        cursor = conn.cursor()
        query = 'SELECT * FROM attack_logs WHERE 1=1'
        params = []
        if service_name:
            query += ' AND service_name = ?'
            params.append(service_name)
        query += ' ORDER BY create_time_timestamp DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def get_attack_logs_by_ip(ip):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM attack_logs WHERE attack_ip = ? ORDER BY create_time_timestamp DESC',
            (ip,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def get_last_timestamp():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT MAX(COALESCE(create_time_timestamp, 0)) as last_timestamp FROM attack_logs')
        row = cursor.fetchone()
        conn.close()
        return int((row['last_timestamp'] if row and row['last_timestamp'] is not None else 0) or 0)

    @staticmethod
    def save_logs(logs):
        if not logs:
            return 0

        conn = get_connection()
        cursor = conn.cursor()
        inserted = 0

        for item in logs:
            attack_ip = item.get('attack_ip') or item.get('ip') or ''
            ip_location = item.get('ip_location') or item.get('location') or ''
            client_id = str(item.get('client_id') or '')
            client_name = item.get('client_name') or ''
            service_name = item.get('service_name') or ''
            service_port = str(item.get('service_port') or item.get('attack_port') or '')
            threat_level = item.get('threat_level') or ''
            create_time_str = item.get('create_time_str') or ''
            create_time_timestamp = item.get('create_time_timestamp')

            if create_time_timestamp in (None, ''):
                if item.get('create_time') not in (None, ''):
                    create_time_timestamp = int(item.get('create_time') or 0)
                elif create_time_str:
                    create_time_timestamp = _time_str_to_timestamp(create_time_str)
                else:
                    create_time_timestamp = 0

            if not create_time_str and create_time_timestamp:
                try:
                    create_time_str = datetime.fromtimestamp(int(create_time_timestamp)).strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    create_time_str = ''

            create_time_timestamp = int(create_time_timestamp or 0)

            cursor.execute(
                '''
                SELECT id FROM attack_logs
                WHERE attack_ip = ? AND service_name = ? AND service_port = ? AND create_time_timestamp = ?
                LIMIT 1
                ''',
                (attack_ip, service_name, service_port, create_time_timestamp)
            )
            if cursor.fetchone():
                continue

            cursor.execute(
                '''
                INSERT INTO attack_logs (
                    attack_ip, ip_location, client_id, client_name,
                    service_name, service_port, threat_level,
                    create_time_str, create_time_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    attack_ip,
                    ip_location,
                    client_id,
                    client_name,
                    service_name,
                    service_port,
                    threat_level,
                    create_time_str,
                    create_time_timestamp,
                )
            )
            inserted += 1

        conn.commit()
        conn.close()
        return inserted

    @staticmethod
    def get_stats():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) as total FROM attack_logs')
        total = cursor.fetchone()['total']
        cursor.execute('SELECT COUNT(DISTINCT attack_ip) as ip_count FROM attack_logs')
        ip_count = cursor.fetchone()['ip_count']
        cursor.execute('SELECT COUNT(DISTINCT service_name) as service_count FROM attack_logs')
        service_count = cursor.fetchone()['service_count']
        conn.close()
        return {
            'total': total,
            'unique_ips': ip_count,
            'services': service_count,
        }


class StatsModel:
    """统计分析模型"""

    @staticmethod
    def get_dashboard_stats():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) as total_hosts FROM hosts')
        total_hosts = cursor.fetchone()['total_hosts']
        cursor.execute('SELECT COUNT(*) as total_attacks FROM attack_logs')
        total_attacks = cursor.fetchone()['total_attacks']
        conn.close()
        return {
            'total_hosts': total_hosts,
            'total_attacks': total_attacks,
        }


class AiModel:
    """AI 分析与聊天记录模型"""

    @staticmethod
    def save_analysis(ip, analysis_text, decision, scan_time=None, status='pending'):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO ai_analysis_logs (ip, analysis_text, decision, scan_time, status)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(ip) DO UPDATE SET
                analysis_text = excluded.analysis_text,
                decision = excluded.decision,
                scan_time = excluded.scan_time,
                status = excluded.status
        ''', (ip, analysis_text, decision, scan_time or datetime.now().strftime('%Y-%m-%d %H:%M:%S'), status))
        conn.commit()
        conn.close()

    @staticmethod
    def get_all_analyses():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM ai_analysis_logs')
        rows = cursor.fetchall()
        conn.close()
        return {row['ip']: dict(row) for row in rows}

    @staticmethod
    def create_session(title='新对话', context_type=None, context_id=None, is_drill_mode=0):
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO ai_chat_sessions (title, context_type, context_id, is_drill_mode, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (title, context_type, context_id, is_drill_mode, now, now))
        session_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return session_id

    @staticmethod
    def list_sessions(limit=50):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM ai_chat_sessions ORDER BY updated_at DESC LIMIT ?', (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def save_message(session_id, role, content, tool_calls=None, tool_call_id=None):
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO ai_chat_history (session_id, role, content, tool_calls, tool_call_id, create_time)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (session_id, role, content, json.dumps(tool_calls, ensure_ascii=False) if tool_calls is not None else None, tool_call_id, now))
        if session_id:
            cursor.execute('UPDATE ai_chat_sessions SET updated_at = ? WHERE id = ?', (now, session_id))
        message_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return message_id

    @staticmethod
    def get_messages(session_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM ai_chat_history WHERE session_id = ? ORDER BY id ASC', (session_id,))
        rows = cursor.fetchall()
        conn.close()
        results = []
        for row in rows:
            data = dict(row)
            if data.get('tool_calls'):
                try:
                    data['tool_calls'] = json.loads(data['tool_calls'])
                except Exception:
                    data['tool_calls'] = []
            results.append(data)
        return results

    @staticmethod
    def delete_session(session_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM ai_chat_history WHERE session_id = ?', (session_id,))
        cursor.execute('DELETE FROM ai_chat_sessions WHERE id = ?', (session_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def get_reports(limit=50):
        reports = []
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                'SELECT id, title, created_at, updated_at FROM ai_chat_sessions WHERE is_drill_mode = 1 ORDER BY created_at DESC LIMIT ?',
                (limit,),
            )
            sessions = [dict(row) for row in cursor.fetchall()]

            for s in sessions:
                cursor.execute(
                    '''
                    SELECT content, create_time FROM ai_chat_history
                    WHERE session_id = ? AND role = 'tool'
                    AND content LIKE '%"report":%'
                    ORDER BY id DESC LIMIT 1
                    ''',
                    (s['id'],),
                )
                row = cursor.fetchone()
                if row:
                    try:
                        data = json.loads(row['content'])
                        cursor.execute(
                            '''
                            SELECT content FROM ai_chat_history
                            WHERE session_id = ? AND role = 'user'
                            ORDER BY id ASC LIMIT 1
                            ''',
                            (s['id'],),
                        )
                        user_row = cursor.fetchone()

                        report_content = data.get('report', '')
                        original_input = user_row['content'] if user_row else None

                        if original_input and not data.get('is_html', False):
                            report_content = f"> **原始演练输入**: {original_input}\n\n---\n\n" + report_content

                        reports.append({
                            'session_id': s['id'],
                            'title': s['title'],
                            'created_at': s['created_at'],
                            'updated_at': s.get('updated_at'),
                            'report': report_content,
                            'summary': data.get('summary'),
                            'is_html': data.get('is_html', False),
                            'original_input': original_input,
                        })
                    except Exception as e:
                        print(f"[AiModel.get_reports] 解析报告失败 session_id={s['id']}: {e}")
                else:
                    reports.append({
                        'session_id': s['id'],
                        'title': s['title'],
                        'created_at': s['created_at'],
                        'updated_at': s.get('updated_at'),
                        'report': '',
                        'summary': None,
                        'is_html': False,
                        'original_input': None,
                    })
        except Exception:
            pass
        finally:
            if conn:
                conn.close()
        return reports

    @staticmethod
    def save_chat_history(query, response="", scan_id=None, history_id=None):
        return AiModel.save_message(None, 'user', query)


class SwitchAclModel:
    """交换机ACL策略管理"""

    @staticmethod
    def add_rule(switch_ip, acl_number, rule_id, action, target_ip, rule_text, description=''):
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO switch_acl_rules
            (switch_ip, acl_number, rule_id, action, target_ip, rule_text, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (switch_ip, acl_number, rule_id, action, target_ip, rule_text, description, now, now))
        rule_id_db = cursor.lastrowid
        conn.commit()
        conn.close()
        return rule_id_db

    @staticmethod
    def remove_rule(switch_ip, acl_number, target_ip):
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE switch_acl_rules SET action = 'removed', updated_at = ?
            WHERE switch_ip = ? AND acl_number = ? AND target_ip = ? AND action != 'removed'
        ''', (now, switch_ip, acl_number, target_ip))
        conn.commit()
        conn.close()

    @staticmethod
    def get_rules(switch_ip=None, acl_number=None):
        conn = get_connection()
        cursor = conn.cursor()

        sql = 'SELECT * FROM switch_acl_rules WHERE action != "removed"'
        params = []
        if switch_ip:
            sql += ' AND switch_ip = ?'
            params.append(switch_ip)
        if acl_number:
            sql += ' AND acl_number = ?'
            params.append(acl_number)
        sql += ' ORDER BY acl_number, rule_id'

        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def clear_all():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM switch_acl_rules')
        conn.commit()
        conn.close()


class SwitchWorkbenchModel:
    """交换机工作台执行记录模型"""

    @staticmethod
    def add_command_run(device_name, device_host, command_text, source, status, stdout='', summary=''):
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        completed_at = created_at
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO switch_workbench_runs
            (device_name, device_host, command_text, source, status, stdout, summary, created_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (device_name, device_host, command_text, source, status, stdout, summary, created_at, completed_at))
        run_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return run_id

    @staticmethod
    def list_command_runs(limit=30):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM switch_workbench_runs ORDER BY id DESC LIMIT ?', (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]


class ScreenshotModel:
    """Web 页面截图模型"""

    @staticmethod
    def save_screenshot(ip, port, url, screenshot_path, scan_time, scan_id=None):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO web_screenshots (ip, port, url, screenshot_path, scan_time, scan_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(ip, port) DO UPDATE SET
                url = excluded.url,
                screenshot_path = excluded.screenshot_path,
                scan_time = excluded.scan_time,
                scan_id = COALESCE(excluded.scan_id, web_screenshots.scan_id)
        ''', (ip, port, url, screenshot_path, scan_time, scan_id))
        conn.commit()
        conn.close()

    @staticmethod
    def get_screenshot(ip, port=None):
        conn = get_connection()
        cursor = conn.cursor()
        if port:
            cursor.execute('SELECT * FROM web_screenshots WHERE ip = ? AND port = ?', (ip, port))
        else:
            cursor.execute('SELECT * FROM web_screenshots WHERE ip = ?', (ip,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def get_all_screenshots(limit=100):
        import os as _os
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM web_screenshots ORDER BY scan_time DESC LIMIT ?', (limit,))
        rows = cursor.fetchall()
        conn.close()
        result = []
        for r in rows:
            d = dict(r)
            path = d.get('screenshot_path')
            if path and _os.path.exists(path):
                result.append(d)
            else:
                try:
                    conn2 = get_connection()
                    cur2 = conn2.cursor()
                    cur2.execute('DELETE FROM web_screenshots WHERE ip = ? AND port = ?', (d.get('ip'), d.get('port')))
                    conn2.commit()
                    conn2.close()
                except Exception:
                    pass
        return result

    @staticmethod
    def delete_screenshot(ip, port):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM web_screenshots WHERE ip = ? AND port = ?', (ip, port))
        conn.commit()
        conn.close()


class TopologyModel:
    """Topology persistence model (JSON based)."""

    TOPOLOGY_FILE = os.path.join(BASE_DIR, 'database', 'topology.json')

    @staticmethod
    def get_topology():
        if not os.path.exists(TopologyModel.TOPOLOGY_FILE):
            return {'nodes': [], 'links': []}
        try:
            with open(TopologyModel.TOPOLOGY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            return {'nodes': [], 'links': []}

        if not isinstance(data, dict):
            return {'nodes': [], 'links': []}

        nodes = data.get('nodes')
        links = data.get('links')
        return {
            'nodes': nodes if isinstance(nodes, list) else [],
            'links': links if isinstance(links, list) else [],
        }

    @staticmethod
    def save_topology(data):
        payload = data if isinstance(data, dict) else {}
        nodes = payload.get('nodes')
        links = payload.get('links')
        normalized = {
            'nodes': nodes if isinstance(nodes, list) else [],
            'links': links if isinstance(links, list) else [],
        }

        os.makedirs(os.path.dirname(TopologyModel.TOPOLOGY_FILE), exist_ok=True)
        with open(TopologyModel.TOPOLOGY_FILE, 'w', encoding='utf-8') as f:
            json.dump(normalized, f, ensure_ascii=False, indent=2)
        return True


__all__ = [
    'NmapModel',
    'ScannerModel',
    'HFishModel',
    'StatsModel',
    'AiModel',
    'SwitchAclModel',
    'SwitchWorkbenchModel',
    'ScreenshotModel',
    'TopologyModel',
    'WorkflowModel',
    'WorkflowRunModel',
    'WorkflowWebhookModel',
]
