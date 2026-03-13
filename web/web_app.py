import os
import json
import threading
from datetime import datetime
from flask import Flask, jsonify, request

# 导入nmap扫描模块 (位于 nmap_plugin 目录)
import sys
# nmap_plugin 包含 network_scan.py，确保其目录在 sys.path 中，以便直接导入
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'nmap_plugin'))
import network_scan

# 导入 MVC 模型层
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from database.db import init_db
from database.models import NmapModel, VulnModel, HFishModel, AiModel
from utils.logger import log as unified_log

app = Flask(__name__)

# 关闭Flask访问日志
import logging
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.WARNING)

# ── 注册 /api/v1/ Blueprint ──────────────────────────────────────────────────
try:
    from api_v1 import v1 as _v1_bp, legacy_api as _legacy_api_bp
    app.register_blueprint(_v1_bp)
    app.register_blueprint(_legacy_api_bp)
    # /api/system/ai-config  ← reference frontend tries this prefix too
    from flask import Blueprint as _BP
    _sys = _BP('sys_compat', __name__, url_prefix='/api/system')

    @_sys.route('/ai-config', methods=['GET', 'POST'])
    def _sys_ai():
        from flask import request as _req
        from api_v1 import system_ai_config_get, system_ai_config_save
        if _req.method == 'GET':
            return system_ai_config_get()
        return system_ai_config_save()

    app.register_blueprint(_sys)
except Exception as _e:
    import traceback; traceback.print_exc()
    unified_log("WebApp", f"/api/v1/ Blueprint 注册失败: {_e}", "WARN")

# 配置路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

# 加载配置
def load_config():
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def reload_config():
    """从文件重新加载配置，支持动态更新"""
    global config
    try:
        config = load_config()
        return config
    except Exception as e:
        unified_log("WebApp", f"配置重载失败: {e}", "ERROR")
        return config


config = load_config()

# ==================== 日志缓冲（供 Web 展示） ====================
_log_buffer = []
_log_max = 500
_log_lock = threading.Lock()

def append_log(level, message, category="system"):
    """追加日志到缓冲，供 /api/logs 拉取"""
    cfg = config.get("logging", {})
    if category == "sync" and not cfg.get("sync_log", True):
        return
    if category == "scan" and not cfg.get("scan_log", True):
        return
    if category == "ai" and not cfg.get("ai_log", True):
        return
    if category == "error" and not cfg.get("error_log", True):
        return
    if category == "api" and not cfg.get("api_request_log", True):
        return
    with _log_lock:
        _log_buffer.append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "level": level,
            "message": message,
            "category": category
        })
        if len(_log_buffer) > _log_max:
            _log_buffer.pop(0)

# 扫描锁，防止同时执行多次扫描
is_scanning = False

# 线程启动标志
sync_thread_started = False
scan_thread_started = False

# 启动时初始化数据库（每个进程都需要确保表存在）
init_db()

def _log(level, msg, category="system"):
    """同时输出到控制台并追加到日志缓冲"""
    unified_log("WebApp", msg, level.upper())
    append_log(level, msg, category)

_log("info", f"[{datetime.now()}] 统一数据库初始化完成", "system")

# ==================== 数据解析工具 ====================

def _int_arg(name, default):
    """读取并解析 query 参数中的整数值；非法值时回落默认值。"""
    raw = request.args.get(name, default)
    try:
        return int(raw)
    except Exception:
        return default

# ==================== 后台任务 ====================

def run_nmap_scan(ip_ranges, arguments):
    """在后台运行Nmap扫描"""
    global is_scanning

    # 检查是否正在扫描
    if is_scanning:
        return

    is_scanning = True
    try:
        # 直接调用main函数，传入0表示只扫描一次
        network_scan.main(ip_ranges=ip_ranges, scan_args=arguments, scan_interval=0)
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        is_scanning = False

is_vuln_scanning = False

def run_vuln_scan_task():
    """在后台运行漏洞扫描（基于最新的主机数据）"""
    global is_vuln_scanning
    if is_vuln_scanning:
        return

    is_vuln_scanning = True
    try:
        hosts_data = NmapModel.get_latest_up_hosts()

        if not hosts_data:
            _log("warn", f"[{datetime.now()}] 漏洞扫描失败: 没有在线主机", "scan")
            return

        _log("info", f"[{datetime.now()}] 开始漏洞扫描，共 {len(hosts_data)} 台主机", "scan")
        stats = network_scan.run_vuln_scan(hosts_data)
        _log("info", f"[{datetime.now()}] 漏洞扫描完成: {stats}", "scan")
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        is_vuln_scanning = False

def run_hfish_sync():
    """运行HFish数据同步（单次）"""
    try:
        sys.path.insert(0, os.path.join(BASE_DIR, "hfish"))
        from attack_log_sync import get_attack_logs

        current_config = load_config()
        host_port = current_config["hfish"]["host_port"]
        api_key = current_config["hfish"]["api_key"]

        last_timestamp = HFishModel.get_last_timestamp()

        logs = get_attack_logs(last_timestamp, 0, host_port, api_key)

        if logs:
            count = HFishModel.save_logs(logs)
            _log("info", f"[{datetime.now()}] 同步完成: 获取 {len(logs)} 条, 新增 {count} 条", "sync")
            
            # 开始分组和调用 AI 分析
            if count > 0:
                try:
                    from hfish.ai_analyzer import analyze_and_ban
                    ip_logs = {}
                    for log in logs:
                        ip = log.get("attack_ip")
                        if ip:
                            if ip not in ip_logs:
                                ip_logs[ip] = []
                            ip_logs[ip].append(log)
                            
                    for ip, ip_log_list in ip_logs.items():
                        # 新建线程执行 AI 判定，避免阻塞全局同步日志任务
                        threading.Thread(target=analyze_and_ban, args=(ip, ip_log_list, current_config), daemon=True).start()
                except Exception as e:
                    _log("error", f"[{datetime.now()}] 调度 AI 分析线程时发生异常: {e}", "ai")
            
            return {"success": True, "total": len(logs), "new": count}
        else:
            _log("info", f"[{datetime.now()}] 同步完成: 无新数据", "sync")
            return {"success": True, "total": 0, "new": 0}

    except Exception as e:
        _log("error", f"[{datetime.now()}] 同步错误: {e}", "sync")
        return {"success": False, "error": str(e)}

def run_hfish_sync_loop():
    """持续同步HFish数据"""
    import time as time_module

    while True:
        try:
            # 每次循环重新加载配置
            current_config = load_config()

            # 检查是否启用同步
            if not current_config.get("hfish", {}).get("sync_enabled", False):
                time_module.sleep(10)
                continue

            sync_interval = current_config.get("hfish", {}).get("sync_interval", 60)

            # 执行同步
            run_hfish_sync()

            # 等待下次同步
            time_module.sleep(sync_interval)

        except Exception as e:
            _log("error", f"[{datetime.now()}] 持续同步错误: {e}", "sync")
            time_module.sleep(10)

def run_nmap_scan_loop():
    """定时Nmap扫描"""
    import time as time_module

    # 启动后先等待一次扫描间隔，再开始第一次扫描
    time_module.sleep(5)  # 等待5秒让服务完全启动

    while True:
        global is_scanning

        try:
            # 每次循环重新加载配置
            current_config = load_config()

            # 检查是否启用扫描
            if not current_config.get("nmap", {}).get("scan_enabled", False):
                time_module.sleep(10)
                continue

            nmap_cfg = current_config.get("nmap", {})
            scan_interval = nmap_cfg.get("scan_interval")
            ip_ranges = nmap_cfg.get("ip_ranges")
            arguments = nmap_cfg.get("arguments")

            # 如果关键配置缺失，则跳过
            if scan_interval is None or not ip_ranges or not arguments:
                time_module.sleep(10)
                continue

            # 检查是否正在扫描
            if is_scanning:
                time_module.sleep(10)
                continue

            # 设置扫描标志
            is_scanning = True

            # 执行扫描
            try:
                network_scan.main(ip_ranges=ip_ranges, scan_args=arguments, scan_interval=0)
            finally:
                is_scanning = False

            # 等待下次扫描
            time_module.sleep(scan_interval)

        except Exception as e:
            _log("error", f"[{datetime.now()}] Nmap定时扫描错误: {e}", "scan")
            is_scanning = False
            time_module.sleep(10)

# 启动持续同步线程
def start_sync_thread():
    """启动持续同步和定时扫描线程"""
    global config, sync_thread_started, scan_thread_started

    # 防止重复启动
    if sync_thread_started and scan_thread_started:
        return

    config = load_config()

    # HFish同步线程 - 只有启用时才启动
    if config.get("hfish", {}).get("sync_enabled", False) and not sync_thread_started:
        sync_thread = threading.Thread(target=run_hfish_sync_loop, daemon=True)
        sync_thread.start()
        sync_thread_started = True
        _log("info", f"[{datetime.now()}] HFish同步线程已启动", "system")
    else:
        _log("info", f"[{datetime.now()}] HFish同步已禁用", "system")

    # Nmap扫描线程 - 只有启用时才启动
    if config.get("nmap", {}).get("scan_enabled", False) and not scan_thread_started:
        scan_thread = threading.Thread(target=run_nmap_scan_loop, daemon=True)
        scan_thread.start()
        scan_thread_started = True
        _log("info", f"[{datetime.now()}] Nmap扫描线程已启动", "system")
    else:
        _log("info", f"[{datetime.now()}] Nmap扫描已禁用", "system")

# ==================== API 请求日志 ====================

@app.before_request
def log_api_request():
    """根据 config.logging.api_request_log 记录 API 请求"""
    if (request.path.startswith('/api/') and request.path != '/api/logs' and
            config.get("logging", {}).get("api_request_log", False)):
        append_log("info", f"API {request.method} {request.path}", "api")


# ==================== 路由 ====================

@app.route('/api/logs')
def api_logs():
    """获取系统日志（供 Web 日志页展示）"""
    limit = _int_arg('limit', 200)
    category = request.args.get('category')
    with _log_lock:
        logs = list(_log_buffer)
    if category:
        logs = [l for l in logs if l.get("category") == category]
    logs = logs[-limit:]
    return jsonify(logs)


# ======================================================
# Vue SPA 入口（仅 SPA 模式）
# 已移除旧 Jinja 页面与模板渲染路径。
# Vue Router 使用 hash 历史 (如 /#/hfish)，Flask 只需返回 index.html
# ======================================================
from flask import send_from_directory as _sfd

_VUE_DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'vue-dist')

@app.route('/')
def spa_index():
    """Vue SPA 入口"""
    return _sfd(_VUE_DIST, 'index.html')

@app.route('/assets/<path:filename>')
def spa_assets(filename):
    """Vue SPA 静态资源"""
    return _sfd(os.path.join(_VUE_DIST, 'assets'), filename)

@app.route('/favicon.ico')
def spa_favicon():
    try: return _sfd(_VUE_DIST, 'favicon.ico')
    except: return '', 204


def print_startup_banner():
    """打印 玄枢·AI攻防指挥官 启动横幅及模块状态"""
    server_config = config.get('server', {})
    host = server_config.get('host', '0.0.0.0')
    port = server_config.get('port', 5000)
    display_host = 'localhost' if host in ('0.0.0.0', '127.0.0.1') else host
    ai_cfg = config.get('ai', {})
    ai_enabled = ai_cfg.get('enabled', False)
    auto_ban = ai_cfg.get('auto_ban', False)
    switches = config.get('switches', [])

    unified_log("WebApp", "=" * 58)
    unified_log("WebApp", "[*] 玄枢·AI攻防指挥官 已启动")
    unified_log("WebApp", "=" * 58)
    unified_log("WebApp", f"控制台地址: http://{display_host}:{port}")
    unified_log("WebApp", f"HFish 同步: {'已启用' if config.get('hfish', {}).get('sync_enabled') else '已禁用'}  |  Nmap 扫描: {'已启用' if config.get('nmap', {}).get('scan_enabled') else '已禁用'}")
    unified_log("WebApp", f"AI 分析: {'已启用' if ai_enabled else '已禁用'}  |  ACL 自动封禁: {'已启用' if (ai_enabled and auto_ban and switches) else '已禁用'}")
    unified_log("WebApp", "=" * 58)


if __name__ == '__main__':

    server_config = config.get('server', {})
    host = server_config.get('host', '0.0.0.0')
    port = server_config.get('port', 5000)
    debug_mode = server_config.get('debug', False)

    # 如果关键服务器配置缺失，则报错提示或退出
    if not host or not port:
        unified_log("WebApp", "关键服务器配置缺失 (host, port)", "ERROR")
        sys.exit(1)

    # Flask debug 模式会启动两个进程：
    # 只在主运行环境中启动后台线程，防止端口占用和重复启动
    if debug_mode:
        if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
            unified_log("WebApp", "主进程启动后台线程 (Debug模式)")
            start_sync_thread()
            print_startup_banner()
        else:
            unified_log("WebApp", "初始进程，跳过后台线程 (等待主进程重载)", "WARN")
    else:
        unified_log("WebApp", "启动后台线程 (生产模式)")
        start_sync_thread()
        print_startup_banner()

    app.run(host=host, port=port, debug=debug_mode)
