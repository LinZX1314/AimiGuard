#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IP 范围扫描脚本
自动扫描指定 IP 范围，将存活的电脑信息存储到数据库
支持两种扫描模式：
1. rustscan + nmap（快速模式）：先用 rustscan 快速发现端口，再用 nmap 做服务识别
2. nmap（普通模式）：直接使用 nmap 扫描
"""

import nmap
import sqlite3
import time
import os
import subprocess
import re
from datetime import datetime

# nmap 路径配置
# 现在使用系统环境变量中的 nmap

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from database.db import get_connection
from database.models import ScannerModel, VulnModel, NmapModel
from utils.logger import log

import json

# 扫描模式配置
USE_RUSTSCAN = True  # 是否使用 rustscan 加速
RUSTSCAN_TIMEOUT = 1500  # rustscan 超时时间(毫秒)
RUSTSCAN_BATCH_SIZE = 4500  # rustscan 批量大小

def get_vuln_scripts_map():
    """获取系统标签与漏洞检测脚本的映射字典（优先从配置读取）"""
    config_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config.json")
    try:
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                vuln_map = config.get('nmap', {}).get('vuln_scripts_by_tag')
                if vuln_map:
                    return vuln_map
    except Exception:
        pass
    return {}


def scan_hosts(ip_range, arguments='-sV -O -T4'):
    """
    扫描指定 IP 范围

    参数:
        ip_range: IP 范围，如 '192.168.1.1/24'
        arguments: nmap 扫描参数

    返回:
        扫描结果字典
    """
    nm = nmap.PortScanner()

    try:
        nm.scan(hosts=ip_range, arguments=arguments)
        return nm
    except Exception as e:
        log("Nmap", f"Nmap Scan Error: {str(e)}", "ERROR")
        return None


def check_rustscan_available():
    """检查 rustscan 是否可用"""
    # 检查多个可能的路径
    possible_paths = ['rustscan', 'rustscan.exe',
                      'C:/Users/lzx78/rustscan.exe',
                      os.path.expanduser('~/rustscan.exe')]

    for path in possible_paths:
        try:
            result = subprocess.run([path, '-V'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return path  # 返回找到的路径
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue
    return False


def scan_hosts_rustscan(ip_range, rustscan_path='rustscan'):
    """
    使用 rustscan 快速扫描端口，再用 nmap 做服务识别

    参数:
        ip_range: IP 范围，如 '192.168.1.1/24'
        rustscan_path: rustscan 可执行文件路径

    返回:
        nmap.PortScanner 对象
    """
    try:
        # 1. 用 rustscan 快速发现开放端口
        log("RustScan", f"快速端口扫描: {ip_range}")

        rustscan_cmd = [
            rustscan_path,
            '-a', ip_range,
            '--',  # 分隔符，之后的参数传给 nmap
            '-p-',  # 扫描所有端口
            '-oG', '-'  # grepable 输出格式
        ]

        result = subprocess.run(
            rustscan_cmd,
            capture_output=True,
            text=True,
            timeout=RUSTSCAN_TIMEOUT / 1000 * 2  # 稍微增加超时
        )

        # 2. 解析 rustscan 结果，提取开放端口
        open_ports = {}  # {ip: [ports]}

        for line in result.stdout.split('\n'):
            if 'Ports:' in line:
                # 解析 grepable 格式: Host: 192.168.1.1 ()	Status: Up
                # Host: 192.168.1.1 ()	Ports: 22/open/tcp//ssh///, 80/open/tcp//http///

                # 提取 IP
                ip_match = re.search(r'Host: (\d+\.\d+\.\d+\.\d+)', line)
                if not ip_match:
                    continue

                ip = ip_match.group(1)

                # 提取端口
                ports_match = re.search(r'Ports: (.+)', line)
                if not ports_match:
                    continue

                ports_str = ports_match.group(1)
                ports = []

                for port_info in ports_str.split(', '):
                    # 格式: 22/open/tcp//ssh///
                    parts = port_info.split('/')
                    if len(parts) >= 2 and parts[1] == 'open':
                        try:
                            ports.append(int(parts[0]))
                        except ValueError:
                            pass

                if ports:
                    open_ports[ip] = ports
                    log("RustScan", f"发现主机 {ip} 开放端口: {ports}")

        if not open_ports:
            log("RustScan", "未发现开放主机")
            return None

        # 3. 对开放端口的主机用 nmap 做服务版本识别
        log("Nmap", "开始服务版本识别...")

        # 构造 nmap 扫描参数
        for ip, ports in open_ports.items():
            ports_str = ','.join(map(str, ports))
            log("Nmap", f"扫描 {ip} 端口: {ports_str}")

        nm = nmap.PortScanner()
        # 批量扫描所有发现的主机
        hosts_list = ','.join(open_ports.keys())
        ports_list = ','.join(str(p) for ports in open_ports.values() for p in ports)

        if hosts_list and ports_list:
            nm.scan(hosts=hosts_list, arguments=f'-sV -p {ports_list} -T4')
            return nm
        else:
            return None

    except subprocess.TimeoutExpired:
        log("RustScan", "扫描超时", "ERROR")
        return None
    except Exception as e:
        log("RustScan", f"扫描错误: {str(e)}", "ERROR")
        return None


def parse_scan_results(nm):
    """解析扫描结果"""
    hosts_data = []

    if nm is None:
        return hosts_data

    for host in nm.all_hosts():
        host_info = {
            'ip': host,
            'mac_address': '',
            'vendor': '',
            'hostname': nm[host].hostname() if nm[host].hostname() else '',
            'state': nm[host].state(),
            'os_type': '',
            'os_accuracy': '',
            'os_tags': 'unknown',
            'open_ports': [],
            'services': []
        }

        # MAC 地址信息
        if 'addresses' in nm[host]:
            addresses = nm[host]['addresses']
            if 'mac' in addresses:
                host_info['mac_address'] = addresses['mac']
            # 厂商信息通常和 MAC 地址在一起
            if 'mac' in addresses and 'vendor' in nm[host]:
                vendor_info = nm[host].get('vendor', {})
                host_info['vendor'] = vendor_info.get(addresses['mac'], '')

        # 操作系统信息
        if 'osmatch' in nm[host] and nm[host]['osmatch']:
            osmatch = nm[host]['osmatch'][0]
            host_info['os_type'] = osmatch.get('name', '')
            host_info['os_accuracy'] = osmatch.get('accuracy', '')
            # 自动识别系统标签
            host_info['os_tags'] = auto_detect_os_tags(osmatch)

        # 端口和服务信息
        for proto in nm[host].all_protocols():
            ports = nm[host][proto].keys()
            for port in ports:
                port_info = nm[host][proto][port]
                if port_info.get('state') == 'open':
                    host_info['open_ports'].append(port)

                    service_info = {
                        'port': port,
                        'service': port_info.get('name', ''),
                        'product': port_info.get('product', ''),
                        'version': port_info.get('version', ''),
                        'extrainfo': port_info.get('extrainfo', '')
                    }
                    host_info['services'].append(service_info)

        hosts_data.append(host_info)

    return hosts_data


def auto_detect_os_tags(osmatch):
    """
    根据 nmap 的 osmatch 信息自动识别系统标签

    参数:
        osmatch: nmap 返回的 osmatch 字典, 包含 'name', 'line', 'classes' 等信息

    返回:
        逗号分隔的系统标签字符串，如 "win7,windows,workstation"
    """
    if not osmatch:
        return ''

    tags = set()
    os_name = osmatch.get('name', '').lower()
    classes = osmatch.get('classes', [])

    # 定义关键词到标签的映射规则
    keyword_mapping = {
        'windows 10': 'windows 10','windows 11': 'windows 10',
        'windows 8': 'win8', 'win8': 'win8',
        'windows 7': 'windows 7', 'vista': 'windows 7',
        'xp': 'windows xp', '2000': 'windows xp', '2003': 'windows xp', '2008': 'windows xp',
        'server': 'winserver',
        'linux': 'linux',
        'bsd': 'bsd',
        'mac': 'macos', 'apple': 'macos', 'os x': 'macos'
    }

    # 合并字符串进行全局搜索，提高匹配命中率
    search_texts = [os_name]
    for cls in classes:
        search_texts.append(cls.get('osfamily', '').lower())
        search_texts.append(cls.get('osgen', '').lower())
    
    full_text = " || ".join(search_texts)

    # 基础家族判断
    if 'windows' in full_text or 'win' in full_text:
        tags.add('windows')

    # 基于关键字映射规则添加标签
    for keyword, tag_values in keyword_mapping.items():
        if keyword in full_text:
            if isinstance(tag_values, list):
                tags.update(tag_values)
            else:
                tags.add(tag_values)

    return ','.join(sorted(tags)) if tags else 'unknown'


def get_vuln_scripts_for_os(os_tags):
    """
    根据系统标签获取需要扫描的漏洞脚本列表

    参数:
        os_tags: 系统标签字符串，如 "windows 10,linux"

    返回:
        漏洞脚本名称列表
    """
    if not os_tags:
        return []

    tag_list = [tag.strip().lower() for tag in os_tags.split(',')]
    vuln_scripts = set()
    
    # 动态获取映射配置
    vuln_scripts_by_tag = get_vuln_scripts_map()

    # 遍历所有标签，收集对应的漏洞脚本
    for tag in tag_list:
        if tag in vuln_scripts_by_tag:
            vuln_scripts.update(vuln_scripts_by_tag[tag])

    return list(vuln_scripts)


def should_skip_vuln(mac_address, vuln_name):
    """判断是否跳过某漏洞的扫描"""
    status = VulnModel.get_vuln_status(mac_address, vuln_name)
    return status == 'safe'


def scan_vuln(nm, host_ip, vuln_script):
    """
    对指定主机执行单个漏洞扫描

    参数:
        nm: nmap 端口扫描器对象
        host_ip: 目标 IP
        vuln_script: 漏洞脚本名称

    返回:
        (result, details): (结果字符串, 详情)
    """
    try:
        # 使用 --script 参数执行漏洞检测
        nm.scan(hosts=host_ip, arguments=f'--script {vuln_script} -T4')

        if host_ip in nm.all_hosts():
            # 检查脚本输出
            if 'script' in nm[host_ip]:
                for script_id, script_output in nm[host_ip]['script'].items():
                    if script_id == vuln_script:
                        output = script_output.lower()
                        # 注意：必须先判断 'not vulnerable'，因为它包含 'vulnerable' 子串
                        if 'not vulnerable' in output or 'failed' in output:
                            return 'safe', script_output
                        elif 'vulnerable' in output or 'expl' in output:
                            return 'vulnerable', script_output
                        elif 'error' in output:
                            return 'error', script_output
                        else:
                            return 'safe', script_output

            # 没有找到脚本输出，认为安全
            return 'safe', 'No vulnerability detected'
        else:
            return 'error', 'Host not reachable'

    except Exception as e:
        return 'error', str(e)


def run_vuln_scan(hosts_data):
    """
    对发现的主机执行漏洞扫描
    """
    stats = {'total': 0, 'skipped': 0, 'vulnerable': 0, 'safe': 0, 'error': 0}

    nm = nmap.PortScanner()

    for host in hosts_data:
        mac_address = host.get('mac_address')
        ip = host.get('ip')
        os_tags = host.get('os_tags', '')

        if not mac_address:
            mac_address = ip
        
        if not mac_address:
            continue

        vuln_scripts = get_vuln_scripts_for_os(os_tags)

        if not vuln_scripts:
            continue

        stats['total'] += len(vuln_scripts)

        for vuln_script in vuln_scripts:
            if should_skip_vuln(mac_address, vuln_script):
                stats['skipped'] += 1
                log("VulnScan", f"[跳过] {ip} ({mac_address}): {vuln_script} (历史确认安全)", "DEBUG")
                continue

            prev_status = VulnModel.get_vuln_status(mac_address, vuln_script)
            if prev_status == 'vulnerable':
                log("VulnScan", f"[警告] {ip} ({mac_address}): {vuln_script} (历史发现漏洞)", "WARN")
                stats['vulnerable'] += 1
                continue

            log("VulnScan", f"[扫描] {ip} ({mac_address}): {vuln_script}")
            result, details = scan_vuln(nm, ip, vuln_script)

            VulnModel.save_vuln_result(mac_address, ip, vuln_script, result, details, os_tags, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

            if result == 'vulnerable':
                stats['vulnerable'] += 1
                log("VulnScan", f"发现漏洞: {details[:100]}...", "WARN")
            elif result == 'safe':
                stats['safe'] += 1
            else:
                stats['error'] += 1

            # 避免扫描过快
            time.sleep(0.5)

    return stats


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
            pass

    ScannerModel.increment_hosts_count(scan_id, count)
    return count


def main(ip_ranges=None, scan_args=None, scan_interval=0):
    """主函数"""
    # 读取配置
    import json
    config_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config.json")
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
            nmap_config = config.get('nmap', {})
            ip_ranges = ip_ranges or nmap_config.get('ip_ranges')
            scan_args = scan_args or nmap_config.get('arguments')
    
    # 如果既没有传入参数，配置文件里也没有，则直接退出
    if not ip_ranges or not scan_args:
        log("Nmap", "未指定 IP 范围或扫描参数 (配置文件缺失或参数为空)", "ERROR")
        return

    # 确保ip_ranges是列表
    if isinstance(ip_ranges, str):
        ip_ranges = [ip_ranges]

    scan_interval = scan_interval  # 0 表示只扫描一次

    while True:
        total_hosts = 0
        total_count = 0
        all_hosts_data = []  # 收集所有主机的数据
        try:
            scan_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            scan_id = ScannerModel.create_scan(ip_ranges, scan_args, scan_time)

            log("Nmap", f"开始扫描 #{scan_id}: {ip_ranges}")

            # 检查是否使用 rustscan 加速模式
            rustscan_path = USE_RUSTSCAN and check_rustscan_available()
            use_rustscan = bool(rustscan_path)

            if use_rustscan:
                log("ScanMode", "使用 RustScan + Nmap 加速模式")
            else:
                log("ScanMode", "使用纯 Nmap 扫描模式")

            for ip_range in ip_ranges:
                if use_rustscan:
                    # 使用 rustscan 快速扫描 + nmap 服务识别
                    nm = scan_hosts_rustscan(ip_range, rustscan_path)
                else:
                    # 使用纯 nmap 扫描
                    nm = scan_hosts(ip_range, scan_args)

                if nm:
                    hosts_data = parse_scan_results(nm)
                    all_hosts_data.extend(hosts_data)

                    count = save_to_db(scan_id, hosts_data)
                    total_hosts += len(hosts_data)

            log("Nmap", f"扫描完成，发现 {total_hosts} 台主机")

            if all_hosts_data:
                log("VulnScan", "开始漏洞扫描...")
                vuln_stats = run_vuln_scan(all_hosts_data)
                log("VulnScan", f"漏洞扫描完成: 总计 {vuln_stats['total']}, "
                      f"跳过 {vuln_stats['skipped']}, "
                      f"发现漏洞 {vuln_stats['vulnerable']}, "
                      f"安全 {vuln_stats['safe']}, "
                      f"错误 {vuln_stats['error']}")

        except Exception as e:
            import traceback
            log("Nmap", f"扫描引擎发生致命错误: {e}", "ERROR")
            traceback.print_exc()

        if scan_interval <= 0:
            break

        time.sleep(scan_interval)




if __name__ == "__main__":
    main()
