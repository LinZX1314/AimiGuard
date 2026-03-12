import os
import json
import threading
from datetime import datetime
from flask import Flask, render_template, jsonify, request

# 导入nmap扫描模块
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'nmap'))
import network_scan

# 导入 MVC 模型层
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from database.db import get_connection, init_db
from database.models import NmapModel, VulnModel, HFishModel, StatsModel, ScannerModel, AiModel

app = Flask(__name__)

# 关闭Flask访问日志
import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.WARNING)

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
        print(f"[{datetime.now()}] 配置重载失败: {e}")
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
    print(msg)
    append_log(level, msg, category)

_log("info", f"[{datetime.now()}] 统一数据库初始化完成", "system")

# ==================== 数据解析工具 ====================

def parse_host_row(host):
    """解析主机数据中的端口和服务字符串"""
    if host.get('open_ports') and isinstance(host['open_ports'], str):
        host['open_ports'] = [p.strip() for p in host['open_ports'].split(',') if p.strip()]
    if host.get('services') and isinstance(host['services'], str):
        parsed_services = []
        for svc in host['services'].split(';'):
            svc = svc.strip()
            if not svc:
                continue
            if '/' in svc:
                parts = svc.split('/', 1)
                port = parts[0].strip()
                service_and_version = parts[1].strip() if len(parts) > 1 else '-'
                parsed_services.append({"port": port, "service": service_and_version})
        host['services'] = parsed_services
    else:
        host['services'] = []
    return host

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

        def on_hfish_error(hp, err):
            _log("error", f"HFish 蜜罐连接异常 [{hp}]: {err}", "sync")

        logs = get_attack_logs(last_timestamp, 0, host_port, api_key, on_error=on_hfish_error)

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
    limit = int(request.args.get('limit', 200))
    category = request.args.get('category')
    with _log_lock:
        logs = list(_log_buffer)
    if category:
        logs = [l for l in logs if l.get("category") == category]
    logs = logs[-limit:]
    return jsonify(logs)


@app.route('/')
def index():
    """首页"""
    return render_template('vuetify_index.html', active='index')

@app.route('/hfish')
def hfish():
    """攻击日志页面"""
    return render_template('vuetify_hfish.html', active='hfish')

@app.route('/nmap')
def nmap_page():
    """网络扫描页面"""
    return render_template('vuetify_nmap.html', active='nmap')

@app.route('/vuln')
def vuln_page():
    """漏洞扫描页面"""
    return render_template('vuetify_vuln.html', active='vuln')

@app.route('/logs')
def logs_page():
    """系统日志页面"""
    return render_template('vuetify_logs.html', active='logs')

# ==================== API接口 ====================

# HFish API
@app.route('/api/hfish/logs')
def api_hfish_logs():
    """获取攻击日志列表"""
    limit = int(request.args.get('limit', 100))
    offset = int(request.args.get('offset', 0))
    threat_level = request.args.get('threat_level')
    service_name = request.args.get('service_name')
    return jsonify(HFishModel.get_attack_logs(limit, offset, threat_level, service_name))

@app.route('/api/hfish/aggregated_logs')
def api_hfish_aggregated_logs():
    """获取按IP聚合的攻击日志和AI分析标签"""
    limit = int(request.args.get('limit', 10000))
    logs = HFishModel.get_attack_logs(limit, 0, None, None)
    
    # 聚合逻辑
    aggregated = {}
    for log in logs:
        ip = log.get("attack_ip")
        if not ip: continue
        if ip not in aggregated:
            aggregated[ip] = {
                "attack_ip": ip,
                "ip_location": log.get("ip_location"),
                "attack_count": 0,
                "latest_time": log.get("create_time_str") or "",
                "services": set()
            }
        aggregated[ip]["attack_count"] += 1
        if log.get("service_name"): aggregated[ip]["services"].add(log["service_name"])
        if log.get("create_time_str") and log.get("create_time_str") > aggregated[ip]["latest_time"]:
             aggregated[ip]["latest_time"] = log["create_time_str"]
             
    # 转为列表并附加 AI 分析
    ai_analyses = AiModel.get_all_analyses()
    result = []
    for ip, data in aggregated.items():
        data["services"] = list(data["services"])
        data["service_name"] = ", ".join(data["services"])
        
        analysis = ai_analyses.get(ip)
        if analysis:
            data["ai_analysis"] = analysis.get("analysis_text")
            data["decision"] = analysis.get("decision")
        else:
            data["ai_analysis"] = None
            data["decision"] = None
        result.append(data)
        
    # Sort by latest time
    result.sort(key=lambda x: x["latest_time"], reverse=True)
    return jsonify(result)

@app.route('/api/hfish/stats')
def api_hfish_stats():
    """获取攻击日志统计"""
    return jsonify(HFishModel.get_stats())

@app.route('/api/hfish/sync', methods=['POST'])
def api_hfish_sync():
    """手动同步HFish数据"""
    thread = threading.Thread(target=run_hfish_sync)
    thread.start()
    return jsonify({"success": True, "message": "同步任务已启动"})

# Nmap API
@app.route('/api/nmap/hosts')
def api_nmap_hosts():
    """获取Nmap主机列表"""
    scan_id = request.args.get('scan_id')
    if scan_id:
        scan_id = int(scan_id)
    limit = int(request.args.get('limit', 100))
    offset = int(request.args.get('offset', 0))
    state = request.args.get('state')
    hosts = NmapModel.get_hosts(scan_id=scan_id, limit=limit, offset=offset, state=state)
    return jsonify([parse_host_row(h) for h in hosts])

@app.route('/api/nmap/scans')
def api_nmap_scans():
    """获取扫描历史列表"""
    return jsonify(NmapModel.get_scans())

@app.route('/api/nmap/stats')
def api_nmap_stats():
    """获取Nmap扫描统计"""
    return jsonify(NmapModel.get_stats())

@app.route('/api/nmap/assets')
def api_nmap_assets():
    """Get nmap assets."""
    try:
        limit = int(request.args.get('limit', 100))
    except ValueError:
        limit = 100
    try:
        offset = int(request.args.get('offset', 0))
    except ValueError:
        offset = 0
    mac_address = request.args.get('mac')
    ip = request.args.get('ip')
    return jsonify(NmapModel.get_assets(limit=limit, offset=offset, mac_address=mac_address, ip=ip))


@app.route('/api/nmap/assets/<int:asset_id>/ips')
def api_nmap_asset_ip_history(asset_id):
    """Get asset IP history by asset id."""
    try:
        limit = int(request.args.get('limit', 200))
    except ValueError:
        limit = 200
    return jsonify(NmapModel.get_asset_ip_history(asset_id=asset_id, limit=limit))


@app.route('/api/nmap/assets/mac/<mac_address>/ips')
def api_nmap_asset_ip_history_by_mac(mac_address):
    """Get asset IP history by MAC."""
    try:
        limit = int(request.args.get('limit', 200))
    except ValueError:
        limit = 200
    return jsonify(NmapModel.get_asset_ip_history(mac_address=mac_address, limit=limit))

@app.route('/api/nmap/vuln')
def api_nmap_vuln():
    """获取漏洞扫描结果列表"""
    try:
        limit = int(request.args.get('limit', 1000))
    except ValueError:
        limit = 1000
    try:
        offset = int(request.args.get('offset', 0))
    except ValueError:
        offset = 0
    return jsonify(VulnModel.get_vuln_results(limit, offset))


@app.route('/api/nmap/vuln/stats')
def api_nmap_vuln_stats():
    """获取漏洞扫描统计"""
    return jsonify(VulnModel.get_vuln_stats())


@app.route('/api/nmap/vuln/mark_safe', methods=['POST'])
def api_vuln_mark_safe():
    """手动将漏洞标记为安全"""
    data = request.get_json(silent=True) or {}
    mac_address = data.get('mac_address')
    vuln_name = data.get('vuln_name')
    if not mac_address or not vuln_name:
        return jsonify({"success": False, "message": "参数不全"})
    success = VulnModel.mark_safe(mac_address, vuln_name)
    if success:
        return jsonify({"success": True, "message": "已手动标记为安全"})
    return jsonify({"success": False, "message": "未找到对应记录"})


@app.route('/api/nmap/vuln/scan', methods=['POST'])
def api_vuln_scan():
    """手动触发漏洞扫描"""
    if is_vuln_scanning:
        return jsonify({"success": False, "message": "漏洞扫描正在进行中，请稍后再试"})

    thread = threading.Thread(target=run_vuln_scan_task)
    thread.start()
    return jsonify({"success": True, "message": "漏洞扫描任务已启动"})


@app.route('/api/nmap/scan', methods=['POST'])
def api_nmap_scan():
    """手动触发Nmap扫描"""
    # 检查是否正在扫描
    if is_scanning:
        return jsonify({"success": False, "message": "扫描正在进行中，请稍后再试"})

    data = request.get_json(silent=True) or {}
    nmap_config = config.get("nmap", {})
    ip_ranges = data.get('ip_ranges') or nmap_config.get('ip_ranges', ['192.168.111.1/24'])
    arguments = data.get('arguments') or nmap_config.get('arguments', '-sS -O -T4')

    # 确保是列表
    if isinstance(ip_ranges, str):
        ip_ranges = [ip_ranges]

    # network_scan.py 内部已经配置了 NMAP_PATH
    thread = threading.Thread(target=run_nmap_scan, args=(ip_ranges, arguments))
    thread.start()

    return jsonify({"success": True, "message": "扫描任务已启动", "ip_ranges": ip_ranges})

@app.route('/api/nmap/host/<ip>')
def api_nmap_host(ip):
    """根据IP查询nmap扫描结果"""
    scan_id = request.args.get('scan_id')
    if scan_id:
        scan_id = int(scan_id)
    host = NmapModel.get_host_by_ip(ip, scan_id)
    if host:
        return jsonify(parse_host_row(host))
    return jsonify({})


@app.route('/settings')
def settings_page():
    """设置页面"""
    return render_template('vuetify_settings.html', active='settings')

@app.route('/api/settings', methods=['GET'])
def api_settings_get():
    """获取设置（支持动态更新：每次从文件重载）"""
    reload_config()
    hfish_config = config.get("hfish", {}).copy()
    hfish_config.pop("api_key", None)

    return jsonify({
        "hfish": hfish_config,
        "nmap": config.get("nmap", {}),
        "ai": _safe_ai_config(),
        "logging": config.get("logging", {}),
        "status": _get_module_status()
    })


def _safe_ai_config():
    """返回脱敏后的 AI 配置（不含 api_key）"""
    ai = config.get("ai", {}).copy()
    ai.pop("api_key", None)
    return ai


def _get_module_status():
    """获取各模块当前状态，供动态展示"""
    ai_cfg = config.get("ai", {})
    ai_enabled = ai_cfg.get("enabled", False)
    auto_ban = ai_cfg.get("auto_ban", False)
    switches = config.get("switches", [])
    return {
        "hfish_sync": config.get("hfish", {}).get("sync_enabled", False),
        "nmap_scan": config.get("nmap", {}).get("scan_enabled", False),
        "ai_analysis": ai_enabled,
        "acl_auto_ban": bool(ai_enabled and auto_ban and switches),
    }


@app.route('/api/status')
def api_status():
    """获取模块运行状态（支持动态更新，供前端轮询）"""
    reload_config()
    return jsonify(_get_module_status())

@app.route('/api/settings', methods=['POST'])
def api_settings_save():
    """保存设置"""
    global config
    data = request.get_json(silent=True) or {}

    # 记录之前的启用状态
    prev_hfish_enabled = config.get("hfish", {}).get("sync_enabled", False)
    prev_nmap_enabled = config.get("nmap", {}).get("scan_enabled", False)

    # 1. 深度合并 HFish 配置，防止 api_key 丢失
    if "hfish" in data:
        new_hfish = data["hfish"]
        old_hfish = config.get("hfish", {})
        
        # 如果新数据里没有 api_key 或者 api_key 为空（前端脱敏后的结果）
        # 且旧数据里有 api_key，则保留旧的
        if not new_hfish.get("api_key") and old_hfish.get("api_key"):
            new_hfish["api_key"] = old_hfish["api_key"]
            
        config["hfish"] = new_hfish

    # 2. 合并 Nmap 配置
    if "nmap" in data:
        config["nmap"] = data["nmap"]

    # 3. 合并日志配置
    if "logging" in data:
        config["logging"] = data["logging"]

    # 保存到文件
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        return jsonify({"success": False, "message": f"保存文件失败: {str(e)}"}), 500

    # 检查是否需要启动新线程
    hfish_enabled = config.get("hfish", {}).get("sync_enabled", False)
    nmap_enabled = config.get("nmap", {}).get("scan_enabled", False)

    # 如果HFish同步刚启用，启动线程
    if hfish_enabled and not prev_hfish_enabled:
        if not sync_thread_started:
            sync_thread = threading.Thread(target=run_hfish_sync_loop, daemon=True)
            sync_thread.start()
            _log("info", f"[{datetime.now()}] HFish同步已启用，启动同步线程", "system")

    # 如果Nmap扫描刚启用，启动线程
    if nmap_enabled and not prev_nmap_enabled:
        if not scan_thread_started:
            scan_thread = threading.Thread(target=run_nmap_scan_loop, daemon=True)
            scan_thread.start()
            _log("info", f"[{datetime.now()}] Nmap扫描已启用，启动扫描线程", "system")

    # 重载配置并打印更新后状态（支持动态更新提示）
    reload_config()
    _print_status_update()

    return jsonify({"success": True, "message": "设置已保存", "status": _get_module_status()})


def _print_status_update():
    """打印配置更新后的模块状态（动态更新提示）"""
    s = _get_module_status()
    msg = f"[{datetime.now()}] 配置已更新 | HFish: {'✓' if s['hfish_sync'] else '✗'} | Nmap: {'✓' if s['nmap_scan'] else '✗'} | AI: {'✓' if s['ai_analysis'] else '✗'} | ACL: {'✓' if s['acl_auto_ban'] else '✗'}"
    print(msg)
    append_log("info", msg, "system")


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

    print()
    print("=" * 58)
    print("  [*] 玄枢·AI攻防指挥官 已启动")
    print("=" * 58)
    print(f"  控制台地址: http://{display_host}:{port}")
    print(f"  HFish 同步: {'已启用' if config.get('hfish', {}).get('sync_enabled') else '已禁用'}  |  Nmap 扫描: {'已启用' if config.get('nmap', {}).get('scan_enabled') else '已禁用'}")
    print(f"  AI 分析: {'已启用' if ai_enabled else '已禁用'}  |  ACL 自动封禁: {'已启用' if (ai_enabled and auto_ban and switches) else '已禁用'}")
    print("=" * 58)
    print()


if __name__ == '__main__':

    server_config = config.get('server', {})
    host = server_config.get('host', '0.0.0.0')
    port = server_config.get('port', 5000)
    debug_mode = server_config.get('debug', False)

    # 如果关键服务器配置缺失，则报错提示或退出
    if not host or not port:
        print(f"[{datetime.now()}] 错误: 关键服务器配置缺失 (host, port)")
        sys.exit(1)

    # Flask debug 模式会启动两个进程：
    # 只在主运行环境中启动后台线程，防止端口占用和重复启动
    if debug_mode:
        if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
            print(f"[{datetime.now()}] 主进程启动后台线程 (Debug模式)")
            start_sync_thread()
            print_startup_banner()
        else:
            print(f"[{datetime.now()}] 初始进程，跳过后台线程 (等待主进程重载)")
    else:
        print(f"[{datetime.now()}] 启动后台线程 (生产模式)")
        start_sync_thread()
        print_startup_banner()

    app.run(host=host, port=port, debug=debug_mode)
