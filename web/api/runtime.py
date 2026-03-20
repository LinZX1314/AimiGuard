"""
Runtime Module - Background task functions
"""
import os, sys, json, time
import threading
from .helpers import BASE_DIR, _load_cfg

# Global state with locks for thread safety
_is_scanning = False
_sync_thread_started = False
_scan_thread_started = False

# Locks for protecting global state
_scan_lock = threading.Lock()
_sync_lock = threading.Lock()
_thread_lock = threading.Lock()


def _run_daemon(task):
    """将耗时任务以守护线程方式触发"""
    threading.Thread(target=task, daemon=True).start()


def _runtime_log(level: str, msg: str):
    """统一后台任务日志输出"""
    from utils.logger import log as unified_log
    unified_log('Runtime', msg, level.upper())


def get_runtime_scan_status() -> dict:
    with _scan_lock:
        scanning = _is_scanning
    return {
        'is_scanning': scanning,
    }


def run_fscan_scan(ip_ranges, timeout=6000):
    """后台执行一次 Fscan 扫描"""
    global _is_scanning

    # 原子检查并设置标志
    with _scan_lock:
        if _is_scanning:
            return
        _is_scanning = True

    try:
        sys.path.insert(0, os.path.join(BASE_DIR, 'plugin'))
        import network_scan
        network_scan.main(ip_ranges=ip_ranges, timeout=timeout, scan_interval=0)
    except Exception as e:
        _runtime_log('error', f'Fscan 扫描执行失败: {e}')
    finally:
        with _scan_lock:
            _is_scanning = False


def run_nmap_scan(ip_ranges, arguments=None, timeout=6000):
    """后台执行一次 Fscan 扫描（兼容旧 nmap 参数签名）"""
    run_fscan_scan(ip_ranges, timeout)


def run_hfish_sync():
    """执行一次 HFish 同步，并进行AI分析和自动封禁"""
    from database.models import HFishModel

    try:
        sys.path.insert(0, os.path.join(BASE_DIR, 'plugin'))
        from attack_log_sync import get_attack_logs
        from hfish_ai_ban import analyze_and_ban_attack_ips

        cfg = _load_cfg()
        host_port = cfg.get('hfish', {}).get('host_port', '')
        api_key = cfg.get('hfish', {}).get('api_key', '')
        last_timestamp = HFishModel.get_last_timestamp()
        logs = get_attack_logs(last_timestamp, 0, host_port, api_key)

        if logs is None:
            return {'success': False, 'error': '连接异常'}

        if not logs:
            _runtime_log('info', 'HFish 同步完成: 无新数据')
            return {'success': True, 'total': 0, 'new': 0}

        count = HFishModel.save_logs(logs)
        _runtime_log('info', f'HFish 同步完成: 获取 {len(logs)} 条, 新增 {count} 条')

        # 调用AI分析和自动封禁
        ai_result = analyze_and_ban_attack_ips(logs, cfg)
        if ai_result.get('analyzed', 0) > 0:
            _runtime_log('info', f'AI分析完成: 分析 {ai_result["analyzed"]} 个IP, 封禁 {ai_result["ban_count"]} 个')

        return {'success': True, 'total': len(logs), 'new': count, 'ban_count': ai_result.get('ban_count', 0)}
    except Exception as e:
        _runtime_log('error', f'HFish 同步失败: {e}')
        return {'success': False, 'error': str(e)}


def run_hfish_sync_loop():
    """HFish 定时同步循环"""
    while True:
        try:
            cfg = _load_cfg()
            sync_interval = cfg.get('hfish', {}).get('sync_interval', 300)
            run_hfish_sync()
            time.sleep(int(sync_interval))
        except Exception as e:
            _runtime_log('error', f'HFish 同步线程异常: {e}')
            time.sleep(10)


def run_fscan_scan_loop():
    """Fscan 定时扫描循环"""
    while True:
        try:
            cfg = _load_cfg()
            nmap_cfg = cfg.get('nmap', {})
            ip_ranges = nmap_cfg.get('ip_ranges', [])
            timeout = nmap_cfg.get('fscan_timeout', 6000)
            scan_interval = nmap_cfg.get('scan_interval', 0)

            if not ip_ranges:
                _runtime_log('warn', 'Fscan 定时扫描跳过: 未配置 IP 范围')
                time.sleep(60)
                continue

            run_fscan_scan(ip_ranges, timeout)
            time.sleep(int(scan_interval))
        except Exception as e:
            _runtime_log('error', f'Fscan 定时扫描异常: {e}')
            time.sleep(10)


# 向后兼容别名
run_nmap_scan_loop = run_fscan_scan_loop


def start_runtime_workers():
    """按配置启动后台同步与扫描线程"""
    global _sync_thread_started, _scan_thread_started
    cfg = _load_cfg()

    with _thread_lock:
        if cfg.get('hfish', {}).get('sync_enabled', False) and not _sync_thread_started:
            threading.Thread(target=run_hfish_sync_loop, daemon=True).start()
            _sync_thread_started = True
            _runtime_log('info', 'HFish 同步线程已启动')

        if cfg.get('nmap', {}).get('scan_enabled', False) and not _scan_thread_started:
            threading.Thread(target=run_fscan_scan_loop, daemon=True).start()
            _scan_thread_started = True
            _runtime_log('info', 'Fscan 扫描线程已启动')
