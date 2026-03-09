#!/usr/bin/env python3
"""Database initialization script"""
import sys
import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime, timezone

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
SQL_SCHEMA = PROJECT_ROOT / "sql" / "mvp_schema.sql"
DB_PATH = Path(__file__).parent / "aimiguard.db"

def hash_password(password: str) -> str:
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def execute_sql_file(conn: sqlite3.Connection, sql_file: Path):
    """Execute SQL file with proper error handling"""
    print(f"📄 Reading schema from: {sql_file}")
    with open(sql_file, 'r', encoding='utf-8') as f:
        sql_script = f.read()
    
    # Execute the entire script
    conn.executescript(sql_script)
    print("✓ Schema created successfully")

def insert_sample_data(conn: sqlite3.Connection):
    """Insert sample data for development"""
    cursor = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    
    # Check if data already exists
    cursor.execute("SELECT COUNT(*) FROM user")
    if cursor.fetchone()[0] > 0:
        print("⚠️  Sample data already exists, skipping...")
        return
    
    print("\n📦 Inserting sample data...")
    
    # 1. Create roles
    roles = [
        ("admin", "系统管理员，拥有所有权限"),
        ("operator", "操作员，可审批和执行操作"),
        ("viewer", "查看者，只读权限")
    ]
    cursor.executemany(
        "INSERT INTO role (name, description, created_at, updated_at) VALUES (?, ?, ?, ?)",
        [(name, desc, now, now) for name, desc in roles]
    )
    print("✓ Created 3 roles")
    
    # 2. Create permissions
    permissions = [
        ("ai_chat", "ai", "chat", "AI 对话"),
        ("view_ai_sessions", "ai", "view", "查看 AI 会话"),
        ("system:config", "system", "config", "系统配置"),
        ("defense:manage", "defense", "manage", "防御管理"),
        ("view_events", "defense", "view", "查看事件"),
        ("approve_event", "defense", "approve", "批准事件"),
        ("reject_event", "defense", "reject", "拒绝事件"),
        ("firewall_sync", "firewall", "sync", "防火墙同步"),
        ("view_firewall_tasks", "firewall", "view", "查看防火墙任务"),
        ("scan:execute", "scan", "execute", "执行扫描"),
        ("scan:view", "scan", "view", "查看扫描"),
        ("view_push", "push", "view", "查看推送"),
        ("manage_push", "push", "manage", "管理推送"),
        ("manage_plugins", "plugin", "manage", "管理插件"),
        ("view_plugins", "plugin", "view", "查看插件"),
        ("create_tts_task", "tts", "create", "创建 TTS 任务"),
        ("view_tts_tasks", "tts", "view", "查看 TTS 任务"),
        ("view_audit", "audit", "view", "查看审计日志"),
        ("view_system_mode", "system", "view_mode", "查看系统模式"),
        ("set_system_mode", "system", "set_mode", "设置系统模式"),
        ("system_rollback", "system", "rollback", "系统回滚"),
        ("generate_report", "report", "generate", "生成报告"),
        ("workflow_view", "workflow", "view", "查看工作流"),
        ("workflow_edit", "workflow", "edit", "编辑工作流"),
        ("workflow_publish", "workflow", "publish", "发布工作流"),
        ("workflow_rollback", "workflow", "rollback", "回滚工作流"),
    ]
    cursor.executemany(
        "INSERT INTO permission (name, resource, action, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        [(name, res, act, desc, now, now) for name, res, act, desc in permissions]
    )
    print(f"✓ Created {len(permissions)} permissions")
    
    # 3. Assign permissions to roles
    # Admin gets all permissions
    cursor.execute("SELECT id FROM role WHERE name = 'admin'")
    admin_role_id = cursor.fetchone()[0]
    cursor.execute("SELECT id FROM permission")
    all_permission_ids = [row[0] for row in cursor.fetchall()]
    cursor.executemany(
        "INSERT INTO role_permission (role_id, permission_id, created_at) VALUES (?, ?, ?)",
        [(admin_role_id, pid, now) for pid in all_permission_ids]
    )
    
    # Operator gets read + operate permissions
    cursor.execute("SELECT id FROM role WHERE name = 'operator'")
    operator_role_id = cursor.fetchone()[0]
    cursor.execute("""
        SELECT id FROM permission 
        WHERE name IN (
          'view_events', 'approve_event', 'reject_event',
          'scan:view', 'scan:execute',
          'ai_chat', 'view_ai_sessions',
          'firewall_sync', 'view_firewall_tasks',
          'view_push', 'manage_push',
          'view_plugins',
          'create_tts_task', 'view_tts_tasks',
          'view_audit', 'view_system_mode',
          'system:config', 'defense:manage',
          'generate_report',
          'workflow_view', 'workflow_edit'
        )
    """)
    operator_permission_ids = [row[0] for row in cursor.fetchall()]
    cursor.executemany(
        "INSERT INTO role_permission (role_id, permission_id, created_at) VALUES (?, ?, ?)",
        [(operator_role_id, pid, now) for pid in operator_permission_ids]
    )
    
    # Viewer gets read-only permissions
    cursor.execute("SELECT id FROM role WHERE name = 'viewer'")
    viewer_role_id = cursor.fetchone()[0]
    cursor.execute("""
        SELECT id FROM permission
        WHERE name IN (
          'view_events',
          'scan:view',
          'view_ai_sessions',
          'view_audit',
          'view_push',
          'view_plugins',
          'view_tts_tasks',
          'view_firewall_tasks',
          'view_system_mode',
          'workflow_view'
        )
    """)
    viewer_permission_ids = [row[0] for row in cursor.fetchall()]
    cursor.executemany(
        "INSERT INTO role_permission (role_id, permission_id, created_at) VALUES (?, ?, ?)",
        [(viewer_role_id, pid, now) for pid in viewer_permission_ids]
    )
    print("✓ Assigned permissions to roles")
    
    # 4. Create users
    users = [
        ("admin", hash_password("admin123"), "admin@aimiguan.local", "系统管理员"),
        ("operator", hash_password("operator123"), "operator@aimiguan.local", "安全操作员"),
        ("viewer", hash_password("viewer123"), "viewer@aimiguan.local", "安全查看者")
    ]
    cursor.executemany(
        "INSERT INTO user (username, password_hash, email, full_name, enabled, created_at, updated_at) VALUES (?, ?, ?, ?, 1, ?, ?)",
        [(u, p, e, f, now, now) for u, p, e, f in users]
    )
    print("✓ Created 3 users")
    
    # 5. Assign roles to users
    cursor.execute("SELECT id, username FROM user")
    user_map = {username: uid for uid, username in cursor.fetchall()}
    
    cursor.execute("SELECT id, name FROM role")
    role_map = {name: rid for rid, name in cursor.fetchall()}
    
    user_roles = [
        (user_map["admin"], role_map["admin"]),
        (user_map["operator"], role_map["operator"]),
        (user_map["viewer"], role_map["viewer"])
    ]
    cursor.executemany(
        "INSERT INTO user_role (user_id, role_id, granted_by, reason, created_at, updated_at) VALUES (?, ?, 'system', '系统初始化', ?, ?)",
        [(uid, rid, now, now) for uid, rid in user_roles]
    )
    print("✓ Assigned roles to users")
    
    # 6. Add default device
    cursor.execute("""
        INSERT INTO device (name, ip, port, vendor, device_type, enabled, description, created_at, updated_at)
        VALUES ('默认交换机', '192.168.1.1', 23, 'generic', 'switch', 0, '示例设备（已禁用），请修改为实际地址后启用', ?, ?)
    """, (now, now))
    print("✓ Added default device")
    
    # 7. Add default model profile
    cursor.execute("""
        INSERT INTO model_profile (model_name, model_type, is_local, endpoint, priority, enabled, config_json, created_at, updated_at)
        VALUES ('llama2', 'llm', 1, 'http://localhost:11434', 10, 1, '{"temperature": 0.7, "max_tokens": 2048}', ?, ?)
    """, (now, now))
    print("✓ Added default model profile")
    
    # 8. Add initial release record
    cursor.execute("""
        INSERT INTO release_history (version, git_commit, schema_version, deploy_env, status, deployed_by, created_at, updated_at)
        VALUES ('v0.1.0', 'initial', '1.0.0', 'dev', 'active', 'system', ?, ?)
    """, (now, now))
    print("✓ Added initial release record")
    
    conn.commit()
    print("✓ Sample data inserted successfully")

def main():
    """Main initialization function"""
    import argparse
    parser = argparse.ArgumentParser(description='Initialize Aimiguan database')
    parser.add_argument('--force', '-f', action='store_true', help='Force recreate database without confirmation')
    args = parser.parse_args()
    
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("🚀 Aimiguan Database Initialization")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"📍 Database: {DB_PATH}")
    print(f"📍 Schema: {SQL_SCHEMA}")
    print()
    
    # Check if schema file exists
    if not SQL_SCHEMA.exists():
        print(f"✗ Schema file not found: {SQL_SCHEMA}")
        sys.exit(1)
    
    # Check if database already exists
    db_exists = DB_PATH.exists()
    if db_exists:
        if args.force:
            print("⚠️  Database file already exists (force mode)")
            DB_PATH.unlink()
            print("✓ Old database removed")
        else:
            print("⚠️  Database file already exists")
            response = input("Do you want to recreate it? (yes/no): ").strip().lower()
            if response != 'yes':
                print("❌ Initialization cancelled")
                sys.exit(0)
            DB_PATH.unlink()
            print("✓ Old database removed")
    
    try:
        # Create database connection
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign key constraints
        
        # Execute schema
        execute_sql_file(conn, SQL_SCHEMA)
        
        # Insert sample data
        insert_sample_data(conn)
        
        # Close connection
        conn.close()
        
        print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("✅ Database initialization complete!")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("\n📋 Default User Accounts:")
        print("  👤 admin / admin123      (管理员 - 所有权限)")
        print("  👤 operator / operator123 (操作员 - 审批和执行)")
        print("  👤 viewer / viewer123     (查看者 - 只读)")
        print("\n🎯 Next Steps:")
        print("  1. Review and update device configuration")
        print("  2. Configure AI model endpoint if needed")
        print("  3. Start the server: python main.py")
        print()
        
    except Exception as e:
        print(f"\n✗ Error during initialization: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
