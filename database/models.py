import os
import sys
import json
from datetime import datetime
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from database.db import get_connection, get_db_cursor


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
        cursor.execute('''
            INSERT INTO hosts
            (scan_id, ip, mac_address, vendor, hostname, state, os_type, os_accuracy, os_tags, open_ports, services, scan_time, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            scan_id, host.get('ip'), host.get('mac_address'), host.get('vendor'),
            host.get('hostname'), host.get('state'), host.get('os_type'),
            host.get('os_accuracy'), host.get('os_tags'), open_ports_str,
            services_str, scan_time, scan_time
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
                    last_seen = ?, last_scan_id = ?
                WHERE id = ?
            ''', (ip, hostname, vendor, state, os_type, os_accuracy, os_tags, scan_time, scan_id, asset_id))
        else:
            cursor.execute('''
                INSERT INTO assets
                (mac_address, current_ip, hostname, vendor, state, os_type, os_accuracy, os_tags, first_seen, last_seen, last_scan_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (mac_address if mac_address else None, ip, hostname, vendor, state, os_type, os_accuracy, os_tags,
                  scan_time, scan_time, scan_id))
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


class VulnModel:
    """漏洞扫描结果模型。"""

    @staticmethod
    def get_vuln_results(limit=1000, offset=0):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ip, mac_address, vuln_name, vuln_result, vuln_details, os_tags, scan_time
            FROM vuln_scan_results
            ORDER BY scan_time DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_vuln_stats():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT vuln_result, COUNT(*) FROM vuln_scan_results GROUP BY vuln_result")
        rows = cursor.fetchall()
        stats = {
            "vulnerable": 0,
            "safe": 0,
            "error": 0,
            "vulnerable_devices": 0
        }
        for row in rows:
            if row[0] == "vulnerable": stats['vulnerable'] = row[1]
            elif row[0] == "safe": stats['safe'] = row[1]
            elif row[0] == "error": stats['error'] = row[1]

        cursor.execute("SELECT COUNT(DISTINCT mac_address) FROM vuln_scan_results WHERE vuln_result = 'vulnerable'")
        vuln_devs = cursor.fetchone()
        if vuln_devs:
            stats['vulnerable_devices'] = vuln_devs[0]

        conn.close()
        return stats

    @staticmethod
    def mark_safe(mac_address, vuln_name):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE vuln_scan_results 
            SET vuln_result = 'safe' 
            WHERE mac_address = ? AND vuln_name = ?
        ''', (mac_address, vuln_name))
        conn.commit()
        success = cursor.rowcount > 0
        conn.close()
        return success

    @staticmethod
    def get_vuln_status(mac_address, vuln_name):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT vuln_result FROM vuln_scan_results
            WHERE mac_address = ? AND vuln_name = ?
            ORDER BY scan_time DESC LIMIT 1
        ''', (mac_address, vuln_name))
        result = cursor.fetchone()
        conn.close()
        return dict(result)['vuln_result'] if result else None

    @staticmethod
    def save_vuln_result(mac_address, ip, vuln_name, vuln_result, vuln_details, os_tags, scan_time):
        if not mac_address or not vuln_name:
            return False
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO vuln_scan_results
                (mac_address, ip, vuln_name, vuln_result, vuln_details, os_tags, scan_time)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (mac_address, ip, vuln_name, vuln_result, vuln_details, os_tags, scan_time))
            conn.commit()
            success = True
        except Exception:
            success = False
        finally:
            conn.close()
        return success


class HFishModel:
    """HFish 攻击日志模型。"""

    @staticmethod
    def get_attack_logs(limit=100, offset=0, service_name=None):
        conn = get_connection()
        cursor = conn.cursor()
        query = "SELECT * FROM attack_logs WHERE 1=1"
        params = []
        if service_name:
            query += " AND service_name = ?"
            params.append(service_name)

        query += " ORDER BY create_time_timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_attack_logs_by_ip(ip: str, limit: int = 1000):
        """获取指定IP的攻击日志"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM attack_logs WHERE attack_ip = ? ORDER BY create_time_timestamp DESC LIMIT ?",
            (ip, limit)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    @staticmethod
    def get_stats():
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT service_name, COUNT(*) as count FROM attack_logs GROUP BY service_name ORDER BY count DESC LIMIT 10")
        service_stats = [{"name": row[0], "count": row[1]} for row in cursor.fetchall()]

        cursor.execute("SELECT attack_ip, COUNT(*) as count FROM attack_logs GROUP BY attack_ip ORDER BY count DESC LIMIT 10")
        ip_stats = [{"ip": row[0], "count": row[1]} for row in cursor.fetchall()]

        cursor.execute("""
            SELECT date(create_time_str) as date, COUNT(*) as count
            FROM attack_logs
            WHERE create_time_str >= date('now', '-7 days')
            GROUP BY date(create_time_str)
            ORDER BY date
        """)
        time_stats = [{"date": row[0], "count": row[1]} for row in cursor.fetchall()]

        cursor.execute("SELECT COUNT(*) FROM attack_logs")
        total = cursor.fetchone()[0]

        conn.close()
        return {
            "total": total,
            "service_stats": service_stats,
            "ip_stats": ip_stats,
            "time_stats": time_stats
        }

    @staticmethod
    def get_last_timestamp():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT create_time_timestamp FROM attack_logs ORDER BY id DESC LIMIT 1")
        result = cursor.fetchone()
        conn.close()
        return result['create_time_timestamp'] if result else 0

    @staticmethod
    def save_logs(logs):
        """批量写入 HFish 日志；用关键字段去重，返回新增条数。"""
        if not logs:
            return 0

        conn = get_connection()
        cursor = conn.cursor()
        count = 0
        for log in logs:
            try:
                timestamp = _time_str_to_timestamp(log.get("create_time_str", ""))
                cursor.execute('''
                    SELECT id FROM attack_logs
                    WHERE attack_ip = ? AND service_name = ? AND service_port = ? AND create_time_str = ?
                ''', (
                    log.get("attack_ip", ""), log.get("service_name", ""),
                    str(log.get("service_port", "")), log.get("create_time_str", "")
                ))
                if cursor.fetchone():
                    continue

                cursor.execute('''
                    INSERT INTO attack_logs
                    (attack_ip, ip_location, client_id, client_name, service_name,
                     service_port, threat_level, create_time_str, create_time_timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    log.get("attack_ip", ""), log.get("ip_location", ""), log.get("client_id", ""), log.get("client_name", ""),
                    log.get("service_name", ""), str(log.get("service_port", "")), log.get("threat_level", ""),
                    log.get("create_time_str", ""), timestamp
                ))
                count += 1
            except Exception:
                pass
        conn.commit()
        conn.close()
        return count


class StatsModel:
    """首页汇总统计模型（保留给兼容接口调用）。"""

    @staticmethod
    def get_dashboard_summary():
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM hosts WHERE state = 'up' AND scan_id = (SELECT id FROM scans ORDER BY id DESC LIMIT 1)")
        online_devices = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(DISTINCT mac_address) FROM vuln_scan_results WHERE vuln_result = 'vulnerable'")
        vuln_devices = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(*) FROM attack_logs WHERE create_time_str >= date('now', '-24 hours')")
        attacks_24h = cursor.fetchone()[0] or 0

        cursor.execute("SELECT MAX(scan_time) FROM scans")
        last_scan = cursor.fetchone()[0] or "尚未扫描"

        conn.close()

        return {
            "online_devices": online_devices,
            "vulnerable_devices": vuln_devices,
            "attacks_24h": attacks_24h,
            "last_scan": last_scan
        }


class AiModel:
    """AI 分析与会话历史持久化模型。"""

    @staticmethod
    def save_analysis(ip, analysis_text, decision, status='pending'):
        scan_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO ai_analysis_logs (ip, analysis_text, decision, scan_time, status)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(ip) DO UPDATE SET
                analysis_text=excluded.analysis_text,
                decision=excluded.decision,
                scan_time=excluded.scan_time,
                status=excluded.status
        ''', (ip, analysis_text, decision, scan_time, status))
        conn.commit()
        conn.close()

    @staticmethod
    def get_analysis_by_ip(ip):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM ai_analysis_logs WHERE ip = ?', (ip,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_all_analyses():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM ai_analysis_logs')
        rows = cursor.fetchall()
        conn.close()
        return {r["ip"]: dict(r) for r in rows}

    # --- 会话持久化管理 ---

    @staticmethod
    def create_session(title="新对话", context_type=None, context_id=None):
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO ai_chat_sessions (title, context_type, context_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (title, context_type, context_id, now, now))
        sid = cursor.lastrowid
        conn.commit()
        conn.close()
        return sid

    @staticmethod
    def get_sessions(limit=50):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM ai_chat_sessions ORDER BY updated_at DESC LIMIT ?', (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def delete_session(session_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM ai_chat_history WHERE session_id = ?', (session_id,))
        cursor.execute('DELETE FROM ai_chat_sessions WHERE id = ?', (session_id,))
        conn.commit()
        conn.close()

    @staticmethod
    def save_message(session_id, role, content, tool_calls=None, tool_call_id=None):
        """保存单条消息到指定会话

        Args:
            session_id: 会话ID
            role: 消息角色 (user/assistant/tool)
            content: 消息内容
            tool_calls: 工具调用信息 (仅 assistant 消息)
            tool_call_id: 工具调用ID (仅 tool 消息)
        """
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = get_connection()
        cursor = conn.cursor()

        # 确保 content 不是 None
        content = content or ''

        tc_json = json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None

        try:
            cursor.execute('''
                INSERT INTO ai_chat_history (session_id, role, content, tool_calls, tool_call_id, create_time, query, response)
                VALUES (?, ?, ?, ?, ?, ?, '', '')
            ''', (session_id, role, content, tc_json, tool_call_id, now))

            # 更新会话最后活跃时间
            if session_id:
                cursor.execute('UPDATE ai_chat_sessions SET updated_at = ? WHERE id = ?', (now, session_id))

            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"[AiModel] 保存消息失败: {e}, session_id={session_id}, role={role}")
        finally:
            conn.close()

    @staticmethod
    def get_messages(session_id):
        """获取指定会话的所有消息历史"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM ai_chat_history WHERE session_id = ? ORDER BY id ASC', (session_id,))
        rows = cursor.fetchall()
        conn.close()

        history = []
        for r in rows:
            d = dict(r)
            msg = {
                'role': d['role'],
                'content': d['content'] or d['response'] or d['query'],  # 兼容旧字段
                'ts': d['create_time']
            }
            if d.get('tool_calls'):
                try:
                    msg['tool_calls'] = json.loads(d['tool_calls'])
                except: pass
            # 恢复 tool 消息的 tool_call_id
            if d['role'] == 'tool' and d.get('tool_call_id'):
                msg['tool_call_id'] = d['tool_call_id']
            history.append(msg)
        return history

    # 为兼容旧版保留的 save_chat_history
    @staticmethod
    def save_chat_history(query, response="", scan_id=None, history_id=None):
        return AiModel.save_message(None, 'user', query)


class SwitchAclModel:
    """交换机ACL策略管理"""

    @staticmethod
    def add_rule(switch_ip, acl_number, rule_id, action, target_ip, rule_text, description=''):
        """添加ACL规则"""
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
        """删除ACL规则"""
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
        """获取ACL规则列表"""
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
        """清空所有ACL规则"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM switch_acl_rules')
        conn.commit()
        conn.close()

