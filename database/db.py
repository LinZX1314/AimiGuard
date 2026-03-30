import sqlite3
import os
import sys
from contextlib import contextmanager

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.logger import log

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_FILE = os.path.join(BASE_DIR, "aimiguard.db")


def get_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_FILE, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except Exception:
        pass
    return conn


@contextmanager
def get_db_cursor():
    """
    数据库连接上下文管理器，自动处理异常和关闭连接

    使用示例:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM users")
            return cursor.fetchall()
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        log("Database", f"数据库操作失败: {e}", "ERROR")
        raise
    finally:
        if conn:
            conn.close()


def init_db():
    """初始化数据库表结构"""
    conn = get_connection()
    cursor = conn.cursor()

    # ================= Nmap网络扫描相关表 =================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_time TEXT NOT NULL,
            ip_ranges TEXT,
            arguments TEXT,
            hosts_count INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hosts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_id INTEGER NOT NULL,
            ip TEXT NOT NULL,
            mac_address TEXT,
            vendor TEXT,
            hostname TEXT,
            state TEXT,
            os_type TEXT,
            os_accuracy TEXT,
            os_tags TEXT,
            open_ports TEXT,
            services TEXT,
            web_fingerprints TEXT,
            scan_time TEXT,
            last_seen TEXT,
            FOREIGN KEY (scan_id) REFERENCES scans(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mac_address TEXT UNIQUE,
            current_ip TEXT,
            hostname TEXT,
            vendor TEXT,
            state TEXT,
            os_type TEXT,
            os_accuracy TEXT,
            os_tags TEXT,
            web_fingerprints TEXT,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            last_scan_id INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS asset_ip_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL,
            ip TEXT NOT NULL,
            scan_id INTEGER,
            seen_time TEXT NOT NULL,
            UNIQUE(asset_id, ip, scan_id),
            FOREIGN KEY (asset_id) REFERENCES assets(id)
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_assets_mac ON assets(mac_address)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_assets_ip ON assets(current_ip)")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_asset_ip_history_asset ON asset_ip_history(asset_id)"
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_hosts_scan_id ON hosts(scan_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_hosts_state ON hosts(state)")

    # ================= HFish蜜罐攻击日志相关表 =================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attack_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attack_ip TEXT,
            ip_location TEXT,
            client_id TEXT,
            client_name TEXT,
            service_name TEXT,
            service_port TEXT,
            threat_level TEXT,
            create_time_str TEXT,
            create_time_timestamp INTEGER
        )
    """)

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_attack_logs_ip ON attack_logs(attack_ip)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_attack_logs_time ON attack_logs(create_time_timestamp)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_attack_logs_service ON attack_logs(service_name)"
    )

    # ================= AI 分析记录表 =================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_analysis_logs (
            ip TEXT PRIMARY KEY,
            analysis_text TEXT,
            decision TEXT,
            scan_time TEXT,
            status TEXT DEFAULT 'pending'
        )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_analysis_ip ON ai_analysis_logs(ip)"
    )

    # ================= AI 聊天与会话持久化表 =================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            context_type TEXT,
            context_id TEXT,
            is_drill_mode INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    try:
        cursor.execute(
            "ALTER TABLE ai_chat_sessions ADD COLUMN is_drill_mode INTEGER DEFAULT 0"
        )
    except Exception:
        pass

    try:
        cursor.execute(
            "ALTER TABLE ai_chat_sessions ADD COLUMN is_incident_mode INTEGER DEFAULT 0"
        )
    except Exception:
        pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            role TEXT DEFAULT 'user',
            query TEXT,
            response TEXT,
            content TEXT,
            openai_content TEXT,
            tool_calls TEXT,
            tool_call_id TEXT,
            create_time TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES ai_chat_sessions(id)
        )
    """)

    # 迁移：添加 openai_content 字段
    try:
        cursor.execute("ALTER TABLE ai_chat_history ADD COLUMN openai_content TEXT")
    except:
        pass

    # 迁移：添加 name 字段（工具消息的工具名称）
    try:
        cursor.execute("ALTER TABLE ai_chat_history ADD COLUMN name TEXT")
    except:
        pass

    # ================= 交换机ACL策略表 =================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS switch_acl_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            switch_ip TEXT NOT NULL,
            acl_number INTEGER NOT NULL,
            rule_id INTEGER,
            action TEXT NOT NULL,
            target_ip TEXT,
            rule_text TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_acl_switch ON switch_acl_rules(switch_ip, acl_number)"
    )

    # ================= Web 指纹表（fscan SERVICE 条目） =================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS web_fingerprints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT NOT NULL,
            port INTEGER NOT NULL,
            service TEXT,
            title TEXT,
            url TEXT,
            status_code INTEGER,
            server TEXT,
            content_length INTEGER,
            scan_time TEXT NOT NULL,
            UNIQUE(ip, port)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_web_fp_ip ON web_fingerprints(ip)")

    # ================= Web 页面截图表 =================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS web_screenshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT NOT NULL,
            port INTEGER NOT NULL,
            url TEXT NOT NULL,
            screenshot_path TEXT NOT NULL,
            scan_time TEXT NOT NULL,
            scan_id INTEGER,
            UNIQUE(ip, port)
        )
    """)

    try:
        cursor.execute("ALTER TABLE web_screenshots ADD COLUMN scan_id INTEGER")
    except Exception:
        pass

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_web_ss_ip ON web_screenshots(ip)")
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_web_ss_scan_id ON web_screenshots(scan_id)"
    )

    # ================= 工作流定义与运行记录表 =================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workflows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT DEFAULT 'system',
            status TEXT DEFAULT 'draft',
            definition_json TEXT NOT NULL,
            trigger_json TEXT NOT NULL,
            version INTEGER DEFAULT 1,
            webhook_token TEXT,
            next_run_at TEXT,
            last_run_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_workflows_status ON workflows(status)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_workflows_next_run_at ON workflows(next_run_at)"
    )
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_workflows_webhook_token ON workflows(webhook_token)"
    )

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workflow_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_id INTEGER NOT NULL,
            trigger_type TEXT NOT NULL,
            trigger_payload TEXT,
            status TEXT DEFAULT 'queued',
            started_at TEXT,
            ended_at TEXT,
            summary TEXT,
            error_message TEXT,
            FOREIGN KEY (workflow_id) REFERENCES workflows(id)
        )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_workflow_runs_workflow ON workflow_runs(workflow_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_workflow_runs_status ON workflow_runs(status)"
    )

    # ================= 交换机工作台执行记录表 =================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS switch_workbench_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_name TEXT NOT NULL,
            device_host TEXT NOT NULL,
            command_text TEXT NOT NULL,
            source TEXT NOT NULL,
            status TEXT NOT NULL,
            stdout TEXT,
            summary TEXT,
            created_at TEXT NOT NULL,
            completed_at TEXT
        )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_switch_workbench_runs_created_at ON switch_workbench_runs(created_at DESC)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_switch_workbench_runs_device_host ON switch_workbench_runs(device_host)"
    )

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workflow_run_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            node_id TEXT NOT NULL,
            node_type TEXT NOT NULL,
            node_name TEXT,
            status TEXT DEFAULT 'queued',
            input_json TEXT,
            output_json TEXT,
            started_at TEXT,
            ended_at TEXT,
            error_message TEXT,
            FOREIGN KEY (run_id) REFERENCES workflow_runs(id)
        )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_workflow_run_steps_run ON workflow_run_steps(run_id)"
    )

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workflow_webhooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_id INTEGER NOT NULL UNIQUE,
            token TEXT NOT NULL UNIQUE,
            secret TEXT,
            enabled INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (workflow_id) REFERENCES workflows(id)
        )
    """)
    try:
        cursor.execute("ALTER TABLE workflow_webhooks ADD COLUMN secret TEXT")
    except Exception:
        pass
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_workflow_webhooks_token ON workflow_webhooks(token)"
    )

    # ================= 终端取证元数据表 =================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS terminal_evidence_meta (
            event_key TEXT PRIMARY KEY,
            meta_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_terminal_evidence_meta_updated ON terminal_evidence_meta(updated_at DESC)"
    )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    log("DB", "Database aimiguard.db initialized.")
