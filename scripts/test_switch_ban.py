#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交换机ACL封禁测试脚本
用于测试AI工具封禁交换机IP功能
"""

import os
import sys
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from ai.tools import execute_tool


def load_config():
    """加载配置文件"""
    config_path = os.path.join(BASE_DIR, 'config.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def test_ban_ip(target_ip: str):
    """封禁指定IP"""
    cfg = load_config()
    switches = cfg.get('switches', [])

    if not switches:
        print("[!] 配置文件中未找到交换机信息")
        return

    switch = switches[0]
    ai_cfg = cfg.get('ai', {})

    # 构建参数
    args = {
        'host': switch.get('host', '192.168.0.1'),
        'port': switch.get('port', 23),
        'password': switch.get('password', 'admin'),
        'secret': switch.get('secret', ''),
        'acl_number': switch.get('acl_number', 3000),
        'action': 'ban',
        'target_ip': target_ip,
        'description': f'测试封禁 IP {target_ip}',
    }

    print(f"[*] 开始封禁 IP: {target_ip}")
    print(f"[*] 交换机: {args['host']}")
    print(f"[*] ACL编号: {args['acl_number']}")
    print("[*] 调用AI工具中...\n")

    result = execute_tool('switch_acl_config', args, cfg)

    print(f"[+] 返回结果:")
    print(result)


def test_unban_ip(target_ip: str):
    """解封指定IP"""
    cfg = load_config()
    switches = cfg.get('switches', [])

    if not switches:
        print("[!] 配置文件中未找到交换机信息")
        return

    switch = switches[0]

    args = {
        'host': switch.get('host', '192.168.0.1'),
        'port': switch.get('port', 23),
        'password': switch.get('password', 'admin'),
        'secret': switch.get('secret', ''),
        'acl_number': switch.get('acl_number', 3000),
        'action': 'unban',
        'target_ip': target_ip,
    }

    print(f"[*] 开始解封 IP: {target_ip}")
    result = execute_tool('switch_acl_config', args, cfg)
    print(f"[+] 返回结果:")
    print(result)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='交换机ACL封禁测试')
    parser.add_argument('--ip', type=str, required=True, help='要封禁/解封的IP地址')
    parser.add_argument('--action', type=str, choices=['ban', 'unban'], default='ban',
                        help='操作类型: ban(封禁) 或 unban(解封)')

    args = parser.parse_args()

    if args.action == 'ban':
        test_ban_ip(args.ip)
    else:
        test_unban_ip(args.ip)
