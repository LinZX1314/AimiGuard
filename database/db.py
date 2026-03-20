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
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_time TEXT NOT NULL,
            ip_ranges TEXT,
            arguments TEXT,
            hosts_count INTEGER DEFAULT 0
        )
    ''')

    cursor.execute('''
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
    ''')

    cursor.execute('''
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
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS asset_ip_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL,
            ip TEXT NOT NULL,
            scan_id INTEGER,
            seen_time TEXT NOT NULL,
            UNIQUE(asset_id, ip, scan_id),
            FOREIGN KEY (asset_id) REFERENCES assets(id)
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_assets_mac ON assets(mac_address)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_assets_ip ON assets(current_ip)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_asset_ip_history_asset ON asset_ip_history(asset_id)')
    
    # 性能优化索引（attack_logs 和 ai_analysis_logs 的索引在各表创建后）
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_hosts_scan_id ON hosts(scan_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_hosts_state ON hosts(state)')

    # ================= HFish蜜罐攻击日志相关表 =================
    cursor.execute('''
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
    ''')

    # attack_logs 表创建后的索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_attack_logs_ip ON attack_logs(attack_ip)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_attack_logs_time ON attack_logs(create_time_timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_attack_logs_service ON attack_logs(service_name)')

    # ================= AI 分析记录表 =================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_analysis_logs (
            ip TEXT PRIMARY KEY,
            analysis_text TEXT,
            decision TEXT,
            scan_time TEXT,
            status TEXT DEFAULT 'pending'
        )
    ''')

    # ai_analysis_logs 表创建后的索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ai_analysis_ip ON ai_analysis_logs(ip)')

    # ================= AI 聊天与会话持久化表 =================
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            context_type TEXT,
            context_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            role TEXT DEFAULT 'user',
            query TEXT,           -- 旧版兼容：query
            response TEXT,        -- 旧版兼容：response
            content TEXT,         -- 新版统一：content
            tool_calls TEXT,      -- 存储 JSON 格式的工具库调用
            tool_call_id TEXT,    -- tool 消息对应的 tool_call_id
            create_time TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES ai_chat_sessions(id)
        )
    ''')

    # ================= 交换机ACL策略表 =================
    cursor.execute('''
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
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_acl_switch ON switch_acl_rules(switch_ip, acl_number)')

    # ================= Web 指纹表（fscan SERVICE 条目） =================
    cursor.execute('''
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
    ''')

    # web_fingerprints 表索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_web_fp_ip ON web_fingerprints(ip)')

    # ================= Web 页面截图表 =================
    cursor.execute('''
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
    ''')

    # 添加 scan_id 列（如果不存在）
    try:
        cursor.execute('ALTER TABLE web_screenshots ADD COLUMN scan_id INTEGER')
    except Exception:
        pass  # 列已存在

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_web_ss_ip ON web_screenshots(ip)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_web_ss_scan_id ON web_screenshots(scan_id)')

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    log("DB", "Database aimiguard.db initialized.")
