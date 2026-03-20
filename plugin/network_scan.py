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
from database.db import get_connection
from database.models import ScannerModel, VulnModel
from utils.logger import log


def get_project_root():
    """获取项目根目录（AimiGuard）。"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_fscan_executable():
    """检测可用的 fscan 可执行文件路径。"""
    import shutil

    fscan_path = shutil.which('fscan')
    if fscan_path:
        log("Fscan", f"找到 fscan: {fscan_path}", "INFO")
        return fscan_path

    log("Fscan", "未找到 fscan！请确保已安装并添加到 PATH。", "ERROR")
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

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=max(timeout / 1000 + 30, 300)
        )
    except subprocess.TimeoutExpired:
        log("Fscan", "扫描超时", "ERROR")
        return None
    except Exception as e:
        log("Fscan", f"扫描执行失败: {e}", "ERROR")
        return None

    # 解析 JSON Lines 输出文件
    hosts = {}  # ip -> host_info

    try:
        if not os.path.exists(output_file):
            log("Fscan", f"输出文件不存在: {output_file}", "ERROR")
            log("Fscan", f"stderr: {result.stderr}", "ERROR")
            return None

        with open(output_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue

                item_type = item.get('type', '')
                target = item.get('target', '')
                details = item.get('details', {})

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
                        'services': []
                    }

                if item_type == 'PORT' and item.get('status') == 'open':
                    port = details.get('port')
                    if port:
                        port = int(port)
                        if port not in hosts[target]['open_ports']:
                            hosts[target]['open_ports'].append(port)
                            hosts[target]['services'].append({
                                'port': port,
                                'service': details.get('service', ''),
                                'product': details.get('product', ''),
                                'version': '',
                                'extrainfo': ''
                            })

                elif item_type == 'SERVICE':
                    hostname = details.get('hostname')
                    if hostname:
                        hosts[target]['hostname'] = hostname
                    # SERVICE 可能带端口信息
                    port = details.get('port')
                    service_name = details.get('service', '')
                    if port and service_name:
                        port = int(port)
                        existing = next((s for s in hosts[target]['services'] if s['port'] == port), None)
                        if existing:
                            existing['service'] = service_name
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

        # 删除临时文件
        try:
            os.remove(output_file)
        except Exception:
            pass

        log("Fscan", f"解析完成，共发现 {len(hosts)} 台主机", "INFO")
        return list(hosts.values())

    except Exception as e:
        log("Fscan", f"解析 JSON 结果失败: {e}", "ERROR")
        try:
            os.remove(output_file)
        except Exception:
            pass
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
                    'vuln_scripts_by_tag': nmap_cfg.get('vuln_scripts_by_tag', {}),
                    'vuln_scripts_by_service': nmap_cfg.get('vuln_scripts_by_service', {}),
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


def run_vuln_scan(hosts_data):
    """
    对发现的主机执行漏洞扫描（基于 nmap 脚本，仍需 python-nmap）
    fscan 本身不包含漏洞扫描脚本，此功能暂时保留 python-nmap
    """
    try:
        import nmap
    except ImportError:
        log("VulnScan", "python-nmap 未安装，跳过漏洞扫描", "WARNING")
        return {'total': 0, 'skipped': 0, 'vulnerable': 0, 'safe': 0, 'error': 0}

    stats = {'total': 0, 'skipped': 0, 'vulnerable': 0, 'safe': 0, 'error': 0}

    # 复用原有漏洞扫描逻辑，读取配置中的 vuln_scripts_by_tag/service
    vuln_map = get_fscan_config().get('vuln_scripts_by_tag', {})

    for host in hosts_data:
        mac_address = host.get('mac_address') or host.get('ip')
        ip = host.get('ip')
        os_tags = host.get('os_tags', '')

        if not ip:
            continue

        if not mac_address:
            mac_address = ip

        # 根据 os_tags 查找对应脚本
        tag_list = [tag.strip().lower() for tag in os_tags.split(',')]
        vuln_scripts = set()
        for tag in tag_list:
            if tag in vuln_map:
                vuln_scripts.update(vuln_map[tag])

        if not vuln_scripts:
            continue

        stats['total'] += len(vuln_scripts)

        nm = nmap.PortScanner()
        for vuln_script in vuln_scripts:
            if should_skip_vuln(mac_address, vuln_script):
                stats['skipped'] += 1
                log("VulnScan", f"[跳过] {ip} ({mac_address}): {vuln_script}", "DEBUG")
                continue

            prev_status = VulnModel.get_vuln_status(mac_address, vuln_script)
            if prev_status == 'vulnerable':
                log("VulnScan", f"[警告] {ip} ({mac_address}): {vuln_script} (历史发现漏洞)", "WARN")
                stats['vulnerable'] += 1
                continue

            log("VulnScan", f"[扫描] {ip} ({mac_address}): {vuln_script}")
            result, details = scan_vuln_impl(nm, ip, vuln_script)
            VulnModel.save_vuln_result(mac_address, ip, vuln_script, result, details, os_tags, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

            if result == 'vulnerable':
                stats['vulnerable'] += 1
            elif result == 'safe':
                stats['safe'] += 1
            else:
                stats['error'] += 1

            time.sleep(0.5)

    return stats


def should_skip_vuln(mac_address, vuln_name):
    """判断是否跳过某漏洞的扫描"""
    status = VulnModel.get_vuln_status(mac_address, vuln_name)
    return status == 'safe'


def scan_vuln_impl(nm, host_ip, vuln_script):
    """对指定主机执行单个漏洞扫描"""
    try:
        nm.scan(hosts=host_ip, arguments=f'--script {vuln_script} -T5')
        if host_ip in nm.all_hosts():
            if 'script' in nm[host_ip]:
                for script_id, script_output in nm[host_ip]['script'].items():
                    if script_id == vuln_script:
                        output = script_output.lower()
                        if 'not vulnerable' in output or 'failed' in output:
                            return 'safe', script_output
                        elif 'vulnerable' in output or 'expl' in output:
                            return 'vulnerable', script_output
                        elif 'error' in output:
                            return 'error', script_output
                        else:
                            return 'safe', script_output
            return 'safe', 'No vulnerability detected'
        else:
            return 'error', 'Host not reachable'
    except Exception as e:
        return 'error', str(e)


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
