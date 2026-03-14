#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 工具模块
包含:
- AI 分析器: 用于分析蜜罐攻击日志并决定是否封禁 IP
"""

import json
import sys
from datetime import datetime

from openai import OpenAI

from utils.logger import log


# ==================== AI 分析器 ====================

def _info(msg):
    log("AI", msg, "INFO")

def _warn(msg):
    log("AI", msg, "WARN")

def _error(msg):
    log("AI", msg, "ERROR")

def _debug(msg):
    log("AI", msg, "DEBUG")

# 尝试导入 netmiko，用于交换机封禁
try:
    from netmiko import ConnectHandler
except ImportError:
    ConnectHandler = None

def _group_logs_for_prompt(logs):
    """
    将日志按时间聚合，生成简化版日志列表供 AI 分析。
    返回: (ip归属地, 简化日志列表)
    """
    if not logs:
        return "", []

    # 提取 IP 归属地
    ip_location = ""
    for log_entry in logs:
        location = log_entry.get("location") or log_entry.get("source_location") or ""
        if location:
            ip_location = location
            break

    # 按时间聚合
    log_map = {}
    for log_entry in logs:
        # 提取关键字段
        timestamp = log_entry.get("timestamp", "") or log_entry.get("created_at", "") or ""
        event_type = log_entry.get("event_type", "") or log_entry.get("type", "")
        protocol = log_entry.get("protocol", "")
        attack_type = log_entry.get("attack_type", "") or log_entry.get("attack", "")
        remote_port = log_entry.get("remote_port", "") or log_entry.get("port", "")
        raw_data = log_entry.get("raw_data", "") or log_entry.get("data", "") or log_entry.get("message", "")
        honeypot = log_entry.get("honeypot", "") or log_entry.get("source", "")

        # 构造唯一 key
        key = f"{timestamp}|{event_type}|{attack_type}"
        if key not in log_map:
            log_map[key] = {
                "timestamp": timestamp,
                "event_type": event_type,
                "protocol": protocol,
                "attack_type": attack_type,
                "remote_port": remote_port,
                "raw_data": raw_data[:200] if raw_data else "",
                "count": 1,
                "honeypots": {honeypot} if honeypot else set(),
            }
        else:
            log_map[key]["count"] += 1
            if honeypot:
                log_map[key]["honeypots"].add(honeypot)

    # 转换为简化列表
    simplified_logs = []
    for v in log_map.values():
        simplified_logs.append({
            "timestamp": v["timestamp"],
            "event_type": v["event_type"],
            "protocol": v["protocol"],
            "attack_type": v["attack_type"],
            "remote_port": v["remote_port"],
            "raw_data": v["raw_data"],
            "count": v["count"],
            "honeypots": list(v["honeypots"])[:3] if v["honeypots"] else [],  # 最多保留 3 个
        })

    return ip_location, simplified_logs


def _extract_ban_decision(reply):
    """从 AI 回复中提取封禁决策"""
    import re
    match = re.search(r'<ban>(true|false)</ban>', reply, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    return "false"


def _clean_reply(reply):
    """清理 AI 回复，移除 <ban> 和 <think> 标签"""
    import re
    cleaned = re.sub(r'<think>.*?</think>', '', reply, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r'</?ban>', '', cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def analyze_and_ban(ip, logs, config):
    """
    使用 AI 分析特定 IP 的攻击日志，并根据分析结果决定是否执行封禁。
    """
    ai_config = config.get("ai", {})
    if not ai_config.get("enabled", False):
        return

    api_url = ai_config.get("api_url", "")
    api_key = ai_config.get("api_key", "")
    model = ai_config.get("model", "")
    timeout = ai_config.get("timeout", 600)

    if not api_key or not api_url:
        _error("AI API 密钥或接口地址 (api_url) 未配置，跳过 AI 分析阶段。")
        return

    # 精简并聚合日志，避免将大量重复记录直接发给模型。
    ip_location, simplified_logs = _group_logs_for_prompt(logs)


    # 准备提示词 (Prompt)
    prompt = f"""
请分析以下来自同一IP ({ip}) 的蜜罐攻击日志。
作为专业的网络安全专家，请判断该IP的攻击行为是否具有高威胁且严需要封禁。

要求：
1. 请简要陈述你的分析理由简单回答不要超过400字。
2. 必须在回复的最后使用特定标签包裹你的最终判断：
   - 如果需要封禁，请输出：<ban>true</ban>
   - 如果不需要封禁，请输出：<ban>false</ban>

攻击源IP: {ip}
源IP归属地: {ip_location}
攻击行为日志明细：
{json.dumps(simplified_logs, ensure_ascii=False, indent=2)}
"""

    try:
        _info(f"正在将 IP [{ip}] 的 {len(logs)} 条日志发送给 AI 进行决断 (超时设置: {timeout}s)...")
        client = OpenAI(api_key=api_key, base_url=api_url, timeout=timeout)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一个专业的安全分析与自动化防御策略分配专家助手。"},
                {"role": "user", "content": prompt}
            ]
        )

        reply = response.choices[0].message.content or ""
        _info(f"AI 对 IP [{ip}] 的分析回复:\n{reply}")

        decision = _extract_ban_decision(reply)
        if decision != "true":
            _info(f"ℹ️ AI 决断结果: 无需封禁 IP [{ip}]。")
        else:
            auto_ban = ai_config.get("auto_ban", False)
            if auto_ban:
                _warn(f"🚨 AI 决断结果: 必须封禁 IP [{ip}]! 准备执行多台交换机访问控制 ACL 更新...")
                switches = config.get("switches", [])
                if not switches:
                    _error("未在 config.json 中找到 'switches' 配置。")
                for switch_config in switches:
                    execute_switch_ban(ip, switch_config)
            else:
                _warn(f"🚨 AI 决断结果: 建议封禁 IP [{ip}]，但设定的 'auto_ban' 自动封禁开关未开启，已跳过设备执行。")

        # 隐藏 <ban> 和 <think> 标签内容并保存到数据库
        clean_reply = _clean_reply(reply)
        from database.models import AiModel
        AiModel.save_analysis(ip, clean_reply, decision)

    except Exception as e:
        _error(f"❌ 调用 AI 分析 IP [{ip}] 时发生错误: {e}")


def _ban_ip_via_telnet(host, port, username, password, secret, acl_number, ip):
    """
    使用telnetlib直接连接锐捷交换机并下发ACL封禁命令
    """
    import socket
    # 设置更长的超时
    socket.setdefaulttimeout(30)

    tn = telnetlib.Telnet(host, port, 30)

    # 等待一下让连接稳定
    time.sleep(2)

    # 读取欢迎信息
    output = tn.read_very_eager().decode('utf-8', errors='ignore')
    print(f"欢迎信息: {output[:200]}")

    # 发送密码登录
    tn.write((password + '\r').encode('utf-8'))
    time.sleep(2)

    # 读取登录后的输出
    output = tn.read_very_eager().decode('utf-8', errors='ignore')
    print(f"登录后: {output[:200]}")

    # 进入特权模式 - 锐捷用 en 不是 enable
    tn.write(b'en\r')
    time.sleep(1)
    enable_pass = secret if secret else password
    tn.write((enable_pass + '\r').encode('utf-8'))
    time.sleep(1)

    # 读取特权模式输出
    output = tn.read_very_eager().decode('utf-8', errors='ignore')
    print(f"enable后: {output[:200]}")

    # 进入全局配置模式 - 锐捷用 config ter
    tn.write(b'config ter\r')
    time.sleep(1)

    # 读取配置模式输出
    output = tn.read_very_eager().decode('utf-8', errors='ignore')
    print(f"configure后: {output[:200]}")

    # 创建ACL
    acl_cmd = f'ip access-list extended {acl_number}'
    tn.write((acl_cmd + '\r').encode('utf-8'))
    time.sleep(1)

    output = tn.read_very_eager().decode('utf-8', errors='ignore')
    print(f"创建ACL后: {output[:200]}")

    # 如果创建ACL失败，抛出异常包含详细错误
    if 'Invalid' in output or 'error' in output.lower() or '%' in output:
        error_msg = f"锐捷交换机ACL命令不被支持。请手动在交换机上执行以下命令:\n"
        error_msg += f"1. en -> 输入特权密码\n"
        error_msg += f"2. config ter\n"
        error_msg += f"3. ip access-list extended {acl_number}\n"
        error_msg += f"4. deny ip host {ip} any\n"
        error_msg += f"5. permit ip any any\n"
        error_msg += f"6. exit\n"
        error_msg += f"7. interface vlan 1 (或具体VLAN)\n"
        error_msg += f"8. ip access-group {acl_number} in\n"
        error_msg += f"9. wr\n"
        raise Exception(error_msg)

    # 添加允许规则 (permit)
    permit_cmd = f'permit ip host {ip} any'
    tn.write((permit_cmd + '\r').encode('utf-8'))
    time.sleep(1)

    output = tn.read_very_eager().decode('utf-8', errors='ignore')
    print(f"permit规则后: {output[:200]}")

    # 退出
    tn.write(b'exit\r')
    time.sleep(0.5)

    # 保存配置 - 锐捷用 wr
    tn.write(b'wr\r')
    time.sleep(2)

    # 读取最终输出
    output = tn.read_very_eager().decode('utf-8', errors='ignore')
    print(f"保存后: {output[:200]}")

    tn.close()

    return output


def execute_switch_ban(ip, switch_config):
    """
    通过 Netmiko 登录交换机并配置 ACL 策略封禁指定 IP
    """
    if ConnectHandler is None:
        _error("未安装 netmiko 库，无法执行交换机封禁。")
        return

    host = switch_config.get("host", "")
    port = switch_config.get("port", 23)
    username = switch_config.get("username", "")
    password = switch_config.get("password", "")
    secret = switch_config.get("secret", "")  # 特权模式密码
    acl_number = switch_config.get("acl_number", 3000)
    device_type = switch_config.get("device_type")

    # 验证配置 - Telnet模式允许username为空
    port = switch_config.get("port", 23)
    if not host or not password or not device_type:
        _error(f"某台交换机(Switch: {host})的配置不完整。必须包含 host, password 和 device_type。")
        return
    if not username and port != 23:
        _error(f"某台交换机(Switch: {host})的配置不完整。SSH模式需要 username。")
        return

    # 根据端口自动选择连接方式
    # 23=Telnet, 22=SSH
    if port == 23:
        # Telnet连接
        if device_type == 'ruijie_os':
            # 锐捷Telnet专用类型
            device_type = 'ruijie_os_telnet'
        elif device_type == 'huawei_telnet':
            device_type = 'huawei_telnet'
        # 其他类型也尝试添加_telnet后缀
        elif not device_type.endswith('_telnet'):
            device_type = device_type + '_telnet'

    try:
        _info(f"正在通过 Netmiko 连接到交换机 {host}:{port} ({device_type})...")

        device = {
            'device_type': device_type,
            'host': host,
            'password': password,
            'port': port,
        }

        # 如果用户名不为空，添加用户名
        if username:
            device['username'] = username

        # 如果特权密码不为空，添加secret
        if secret:
            device['secret'] = secret

        # 建立智能连接，自动处理登录和等待提示符
        net_connect = ConnectHandler(**device)

        # 尝试进入特权模式（锐捷需要手动进入）
        try:
            if secret:
                net_connect.enable(cmd='enable', pattern=r'Password')
                net_connect.send_command(secret, pattern=r'#')
            elif username:  # 如果有用户名，可能密码也是特权密码
                net_connect.enable(cmd='enable', pattern=r'Password')
                net_connect.send_command(password, pattern=r'#')
        except:
            pass  # 可能已经自动进入特权模式

        # 根据原始设备类型生成不同的命令
        original_device_type = switch_config.get("device_type", "")
        if original_device_type == 'ruijie_os':
            # 锐捷交换机 - 使用telnetlib直接连接
            try:
                output = _ban_ip_via_telnet(host, port, username, password, secret, acl_number, ip)
                _info(f"成功在交换机 {host} 的 ACL {acl_number} 中添加了对 IP {ip} 的封禁策略！")
                _debug(f"交换机命令行输出记录:\n{output}")
                return
            except Exception as e:
                _error(f"锐捷交换机Telnet连接失败: {e}")
                return  # 直接返回，不尝试netmiko后备
        else:
            # 华为交换机命令 (默认)
            config_commands = [
                'system-view',                         # 进入系统视图
                f'acl number {acl_number}',            # 创建ACL
                f'rule 5 deny ip source {ip} 0',      # 拒绝该IP(优先级5)
                'rule 10 permit ip source any any',   # 允许其他流量
                'quit',                                # 退出ACL视图
                'quit',                                # 退出系统视图
                'save force'                           # 保存配置
            ]
            acl_name = f"ACL {acl_number}"

        _info(f"成功登录交换机 {host}。正在下发 {acl_name} 封禁 {ip} 的命令集...")

        # Netmiko 会自动进入系统视图并按顺序执行
        output = net_connect.send_config_set(config_commands)

        # 尝试保存配置并正常断开
        try:
            net_connect.save_config()
        except:
            pass # 部分设备可能不支持默认的 save_config 命令，不影响下发

        net_connect.disconnect()

        _info(f"✅ 成功在交换机 {host} 的 ACL {acl_number} 中添加了对 IP {ip} 的封禁策略！")
        _debug(f"交换机命令行输出记录:\n{output}")

    except Exception as e:
        _error(f"❌ 自动化封禁 IP {ip} 到交换机时发生异常: {e}")
