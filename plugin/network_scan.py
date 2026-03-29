#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP 范围扫描脚本
自动扫描指定 IP 范围，将存活的电脑信息存储到数据库
使用 fscan 二进制执行扫描
"""

import time
import os
import json
import subprocess
from datetime import datetime

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from database.models import ScannerModel, ScreenshotModel
from utils.logger import log


def get_project_root():
    """获取项目根目录（AimiGuard）。"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_fscan_executable():
    """检测可用的 fscan 可执行文件路径。"""
    import shutil

    project_root = get_project_root()
    env_fscan = os.environ.get('FSCAN_PATH', '').strip().strip('"')
    local_candidates = [
        os.path.join(project_root, 'lib', 'fscan.exe'),
        os.path.join(project_root, 'bin', 'fscan.exe'),
        os.path.join(project_root, 'plugin', 'bin', 'fscan.exe'),
    ]

    if env_fscan:
        if os.path.isfile(env_fscan):
            log("Fscan", f"使用环境变量 FSCAN_PATH: {env_fscan}", "INFO")
            return env_fscan
        log("Fscan", f"环境变量 FSCAN_PATH 指向文件不存在: {env_fscan}", "WARN")

    for candidate in local_candidates:
        if os.path.isfile(candidate):
            log("Fscan", f"使用本地 fscan: {candidate}", "INFO")
            return candidate

    fscan_path = shutil.which('fscan')
    if fscan_path:
        log("Fscan", f"使用系统 PATH 中 fscan: {fscan_path}", "INFO")
        return fscan_path

    fallback_dirs = ' | '.join(sorted({os.path.dirname(p) for p in local_candidates}))
    log("Fscan", f"未找到 fscan！可将 fscan.exe 放到: {fallback_dirs}，或配置 FSCAN_PATH，或加入系统 PATH。", "ERROR")
    return None


def run_fscan(ip_range, timeout=6000):
    """
    执行 fscan 扫描，读取 JSON 输出文件

    参数:
        ip_range: IP 范围，如 '192.168.1.1/24'
        timeout: 超时时间（毫秒）

    返回:
        扫描结果字典列表
    """
    fscan_path = get_fscan_executable()
    if not fscan_path:
        return None

    # 每个扫描使用唯一的临时文件
    output_file = os.path.join(get_project_root(), f"fscan_result_{int(time.time() * 1000)}.json")
    cmd = [fscan_path, '-h', ip_range, '-t', str(timeout), '-nobr', '-np', '-f', 'json', '-o', output_file]

    log("Fscan", f"执行命令: {' '.join(cmd)}")

    proc = None
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=max(timeout / 1000 + 30, 300)
        )
    except subprocess.TimeoutExpired as e:
        log("Fscan", "扫描超时", "ERROR")
        if e.stderr:
            log("Fscan", f"stderr: {e.stderr.decode('utf-8', errors='replace')}", "ERROR")
        return None
    except Exception as e:
        log("Fscan", f"扫描执行失败: {e}", "ERROR")
        return None

    # 解析 JSON Lines 输出文件
    hosts = {}  # ip -> host_info

    try:
        if not os.path.exists(output_file):
            log("Fscan", f"输出文件不存在: {output_file}", "ERROR")
            stderr_bytes = proc.stderr if proc and proc.stderr else b''
            log("Fscan", f"stderr: {stderr_bytes.decode('utf-8', errors='replace')}", "ERROR")
            return None

        with open(output_file, 'r', encoding='utf-8') as f:
            raw = f.read()

        # fscan -f json 输出为多行缩进格式：}\n{\n... 依次排列
        # 用 }\n{ 作为精确分隔符，兼容所有情况
        raw = raw.strip()
        raw = raw.replace('\r\n', '\n').replace('\r', '\n')
        # 在 }\n{ 之间插入分隔符，再按分隔符拆分
        raw = raw.replace('}\n{', '}\n§{')
        chunks = raw.split('§')

        for chunk in chunks:
            chunk = chunk.strip().rstrip(',').rstrip(',')
            if not chunk:
                continue
            try:
                item = json.loads(chunk)
            except json.JSONDecodeError:
                continue

            # 跳过非字典类型的行（如纯字符串 banner）
            if not isinstance(item, dict):
                continue

            # details 可能是字符串（如纯文本 banner），确保是字典
            details = item.get('details', {})
            if not isinstance(details, dict):
                details = {}

            item_type = item.get('type', '')
            target = item.get('target', '')

            if not target:
                continue

            # 初始化主机
            if target not in hosts:
                hosts[target] = {
                    'ip': target,
                    'mac_address': '',
                    'vendor': '',
                    'hostname': '',
                    'state': 'alive',
                    'os_type': '',
                    'os_accuracy': '',
                    'os_tags': 'unknown',
                    'open_ports': [],
                    'services': [],
                    'web_fingerprints': []
                }

            if item_type == 'PORT':
                port = details.get('port')
                if port:
                    port = int(port) if not isinstance(port, int) else port
                    # PORT 条目只有 port，service/product 信息在后续 SERVICE 条目补充
                    hosts[target]['open_ports'].append(port)
                    hosts[target]['services'].append({
                        'port': port,
                        'service': '',
                        'product': '',
                        'version': '',
                        'extrainfo': ''
                    })

            elif item_type == 'SERVICE':
                if not isinstance(details, dict):
                    details = {}
                hostname = details.get('hostname')
                if hostname:
                    hosts[target]['hostname'] = hostname
                port_raw = details.get('port')
                service_name = details.get('service', '') or ''
                # 调试：打印所有 SERVICE 条目
                # log("Fscan", f"DEBUG SERVICE: target={target} service={service_name} port={port_raw} url={details.get('url')}", "INFO")
                if port_raw and service_name:
                    try:
                        port = int(port_raw)
                    except (TypeError, ValueError):
                        port = None
                    if port:
                        # 查找是否已通过 PORT 条目添加过该端口，如有则补充信息
                        existing = next((s for s in hosts[target]['services'] if s['port'] == port), None)
                        if existing:
                            existing['service'] = service_name
                            title = details.get('title', '')
                            if title:
                                existing['product'] = title
                        elif port not in hosts[target]['open_ports']:
                            title = details.get('title', '')
                            hosts[target]['open_ports'].append(port)
                            hosts[target]['services'].append({
                                'port': port,
                                'service': service_name,
                                'product': title,
                                'version': '',
                                'extrainfo': ''
                            })
                # 收集 Web 指纹信息（http/https 服务）
                if port and service_name in ('http', 'https'):
                    fp_url = details.get('url')
                    if not fp_url:
                        # fscan SERVICE 条目不包含 url 字段，根据 IP 和端口构造
                        scheme = 'https' if port in (443, 8443) else 'http'
                        fp_url = f"{scheme}://{target}:{port}"
                    fp_status = details.get('status_code')
                    fp_status = details.get('status_code')
                    fp_title = details.get('title', '')
                    server_info = details.get('server_info', {}) or {}
                    fp_server = server_info.get('server', '') or server_info.get('Server', '') or ''
                    fp_length = server_info.get('length')
                    # 避免重复添加同一端口的指纹
                    existing_fp = next((f for f in hosts[target]['web_fingerprints'] if f['port'] == port), None)
                    if not existing_fp:
                        hosts[target]['web_fingerprints'].append({
                            'port': port,
                            'service': service_name,
                            'title': fp_title,
                            'url': fp_url,
                            'status_code': fp_status,
                            'server': fp_server,
                            'content_length': fp_length
                        })

        # 删除临时文件
        try:
            os.remove(output_file)
        except Exception:
            pass

        log("Fscan", f"解析完成，共发现 {len(hosts)} 台主机", "INFO")
        return list(hosts.values())

    except Exception as e:
        log("Fscan", f"解析 JSON 结果失败: {e}", "ERROR")
        return None


def get_fscan_config():
    """从配置中获取 fscan 扫描参数"""
    config_file = os.path.join(get_project_root(), "config.json")
    try:
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                nmap_cfg = config.get('nmap', {})
                return {
                    'ip_ranges': nmap_cfg.get('ip_ranges', []),
                    'timeout': nmap_cfg.get('fscan_timeout', 6000),
                    'scan_interval': nmap_cfg.get('scan_interval', 0),
                    'scan_enabled': nmap_cfg.get('scan_enabled', False),
                }
    except Exception as e:
        log("Fscan", f"读取配置失败: {e}", "ERROR")
    return {}


def save_to_db(scan_id, hosts_data):
    """保存扫描结果到数据库"""
    if not hosts_data:
        return 0

    count = 0
    scan_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    for host in hosts_data:
        try:
            open_ports_str = ','.join(map(str, host['open_ports'])) if host['open_ports'] else ''

            services_list = []
            for svc in host['services']:
                svc_str = f"{svc['port']}/{svc['service']}"
                if svc['product']:
                    svc_str += f" {svc['product']}"
                if svc['version']:
                    svc_str += f" {svc['version']}"
                services_list.append(svc_str)
            services_str = '; '.join(services_list)

            ScannerModel.save_host(scan_id, host, scan_time, open_ports_str, services_str)
            ScannerModel.upsert_asset(scan_id, host, scan_time)
            count += 1
        except Exception as e:
            log("Fscan", f"保存主机失败 {host.get('ip')}: {e}", "ERROR")

    ScannerModel.increment_hosts_count(scan_id, count)
    return count


def capture_web_screenshots(hosts_data, scan_time, scan_id=None):
    """对扫描到的 Web 服务进行截图"""
    try:
        from web_screenshot import take_screenshot

        web_targets = []
        for host in hosts_data:
            ip = host.get('ip', '')
            web_fps = host.get('web_fingerprints', []) or []
            for fp in web_fps:
                url = fp.get('url')
                port = fp.get('port')
                if url and ip and port:
                    web_targets.append({'url': url, 'ip': ip, 'port': port})

        if not web_targets:
            log("Screenshot", "未发现 Web 服务，跳过截图", "INFO")
            return

        log("Screenshot", f"开始截图 {len(web_targets)} 个 Web 页面...", "INFO")
        captured = 0
        for target in web_targets:
            path = take_screenshot(target['url'], target['ip'], target['port'])
            if path:
                ScreenshotModel.save_screenshot(
                    target['ip'], target['port'], target['url'], path, scan_time, scan_id
                )
                captured += 1

        log("Screenshot", f"截图完成: 成功 {captured}/{len(web_targets)}", "INFO")
    except ImportError:
        log("Screenshot", "web_screenshot 模块未安装，跳过截图", "WARN")
    except Exception as e:
        log("Screenshot", f"截图过程出错: {e}", "ERROR")


def main(ip_ranges=None, timeout=6000, scan_interval=0):
    """主函数"""
    config = get_fscan_config()

    # 配置覆盖：优先使用传入参数，否则用配置文件
    ip_ranges = ip_ranges or config.get('ip_ranges', [])
    timeout = timeout or config.get('timeout', 6000)
    scan_interval = scan_interval or config.get('scan_interval', 0)

    # 如果既没有传入参数，配置文件里也没有，则直接退出
    if not ip_ranges:
        log("Fscan", "未指定 IP 范围 (配置文件缺失或参数为空)", "ERROR")
        return

    if isinstance(ip_ranges, str):
        ip_ranges = [ip_ranges]

    while True:
        total_hosts = 0
        try:
            scan_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # 构造 scan_args 用于兼容数据库记录
            scan_args = f"-h {{ip_range}} -t {timeout} -nobr -np -f json -o <file>"
            scan_id = ScannerModel.create_scan(ip_ranges, scan_args, scan_time)

            log("Fscan", f"开始扫描 #{scan_id}: {ip_ranges}")

            all_hosts_data = []

            for ip_range in ip_ranges:
                hosts_data = run_fscan(ip_range, timeout)
                if hosts_data:
                    all_hosts_data.extend(hosts_data)

                    count = save_to_db(scan_id, hosts_data)
                    total_hosts += len(hosts_data)

            # 截图：所有网段扫描完成后统一截图
            if all_hosts_data:
                capture_web_screenshots(all_hosts_data, scan_time, scan_id)

            log("Fscan", f"扫描完成，发现 {total_hosts} 台主机")

        except Exception as e:
            import traceback
            log("Fscan", f"扫描引擎发生致命错误: {e}", "ERROR")
            traceback.print_exc()

        if scan_interval <= 0:
            break

        time.sleep(scan_interval)


if __name__ == "__main__":
    main()
