"""
修复数据库表结构 - 添加缺失的列
"""
import sqlite3
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.logger import log

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_FILE = os.path.join(BASE_DIR, "aimiguard.db")


def check_and_fix_columns():
    """检查并修复数据库表结构"""
    if not os.path.exists(DB_FILE):
        log("DB", f"数据库文件不存在: {DB_FILE}", "ERROR")
        return False

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # 检查 hosts 表结构
    cursor.execute("PRAGMA table_info(hosts)")
    hosts_columns = {row[1] for row in cursor.fetchall()}

    # 检查 assets 表结构
    cursor.execute("PRAGMA table_info(assets)")
    assets_columns = {row[1] for row in cursor.fetchall()}

    fixed = False

    # 修复 hosts 表
    if 'web_fingerprints' not in hosts_columns:
        try:
            cursor.execute('ALTER TABLE hosts ADD COLUMN web_fingerprints TEXT')
            log("DB", "已添加 hosts.web_fingerprints 列", "INFO")
            fixed = True
        except Exception as e:
            log("DB", f"添加 hosts.web_fingerprints 失败: {e}", "ERROR")

    if 'services' not in hosts_columns:
        try:
            cursor.execute('ALTER TABLE hosts ADD COLUMN services TEXT')
            log("DB", "已添加 hosts.services 列", "INFO")
            fixed = True
        except Exception as e:
            log("DB", f"添加 hosts.services 失败: {e}", "ERROR")

    # 修复 assets 表
    if 'web_fingerprints' not in assets_columns:
        try:
            cursor.execute('ALTER TABLE assets ADD COLUMN web_fingerprints TEXT')
            log("DB", "已添加 assets.web_fingerprints 列", "INFO")
            fixed = True
        except Exception as e:
            log("DB", f"添加 assets.web_fingerprints 失败: {e}", "ERROR")

    conn.commit()
    conn.close()

    if fixed:
        log("DB", "数据库表结构修复完成", "INFO")
    else:
        log("DB", "数据库表结构检查完成，无需修复", "INFO")

    return True


if __name__ == "__main__":
    check_and_fix_columns()
