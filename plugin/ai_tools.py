#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 工具模块
包含:
- AI 扫描器: 用于 AI 驱动的 Nmap 网络扫描
- AI 分析器: 用于分析蜜罐攻击日志并决定是否封禁 IP
"""

import os
import json
import sys
from datetime import datetime

from openai import OpenAI

# 确保可以导入项目中的模块
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

try:
    from network_scan import scan_hosts, scan_hosts_rustscan, parse_scan_results, check_rustscan_available
except ImportError:
    # 针对在其他目录下运行时的路径调整
    sys.path.append(os.path.join(BASE_DIR, "plugin"))
    from network_scan import scan_hosts, scan_hosts_rustscan, parse_scan_results, check_rustscan_available

from database.models import ScannerModel
from utils.logger import log


# ==================== AI 扫描器 ====================

class AIScanner:
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = os.path.join(BASE_DIR, "config.json")

        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self.ai_config = self.config.get("ai", {})
        self.analysis_map = self.ai_config.get("analysis_map", {})
        self.api_url = self.ai_config.get("api_url")
        self.api_key = self.ai_config.get("api_key")
        self.model = self.ai_config.get("model")
        self.timeout = self.ai_config.get("timeout", 160)

        self.client = OpenAI(api_key=self.api_key, base_url=self.api_url)

    def _get_prompt(self, key, default=""):
        """统一从 ai.analysis_map 获取提示词，并兼容旧字段。"""
        value = self.analysis_map.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

        # 兼容历史字段：chat_system_prompt 作为通用系统提示词
        legacy = self.ai_config.get("system_prompt")
        if isinstance(legacy, str) and legacy.strip():
            return legacy.strip()

        return default

    def get_tools_definition(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "nmap_scan",
                    "description": "执行一次 Nmap 网络扫描",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target": {
                                "type": "string",
                                "description": "要扫描的目标 IP、域名或网段",
                            },
                            "arguments": {
                                "type": "string",
                                "description": "Nmap 参数，如 -sV -T4 -O",
                            },
                        },
                        "required": ["target"],
                    },
                },
            }
        ]

    def chat_and_scan_stream(self, user_input, history=None):
        """
        使用 OpenAI 库的流式 + 函数调用
        """
        system_prompt = self._get_prompt(
            "nmap_scan_system_prompt",
            "你是一个专业的网络安全助手，拥有实时的 Nmap 扫描能力。请直接回复用户，如果需要扫描，请调用工具。",
        )

        messages = [
            {
                "role": "system",
                "content": system_prompt,
            }
        ]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_input})

        try:
            log("AI", f"发起请求: {self.model}")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.get_tools_definition(),
                stream=True,
            )

            content_buffer = ""
            # 按 index 累积工具调用分片，key=index, value={id, name, arguments_buf}
            tool_calls_buf: dict[int, dict] = {}
            _status_yielded = False

            for chunk in response:
                choice = chunk.choices[0]
                delta = choice.delta

                if delta.content:
                    content_buffer += delta.content
                    yield {"type": "text", "content": delta.content}

                if delta.tool_calls:
                    if not _status_yielded:
                        yield {"type": "status", "content": "AI 正在构造扫描指令..."}
                        _status_yielded = True
                    for tc in delta.tool_calls:
                        idx = tc.index if tc.index is not None else 0
                        if idx not in tool_calls_buf:
                            tool_calls_buf[idx] = {
                                "id": tc.id or "",
                                "name": tc.function.name or "",
                                "arguments": "",
                            }
                        else:
                            # 后续分片可能补充 id/name
                            if tc.id:
                                tool_calls_buf[idx]["id"] = tc.id
                            if tc.function.name:
                                tool_calls_buf[idx]["name"] = tc.function.name
                        if tc.function.arguments:
                            tool_calls_buf[idx]["arguments"] += tc.function.arguments

            # 还原有序工具列表
            tool_calls = [tool_calls_buf[k] for k in sorted(tool_calls_buf.keys())]

            if tool_calls:
                tool_call = tool_calls[0]
                func_name = tool_call["name"]

                if func_name == "nmap_scan":
                    raw_args = tool_call.get("arguments", "{}")
                    log("AI", f"准备执行工具: {func_name}, 参数: {raw_args}")

                    try:
                        args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        yield {"type": "error", "content": "AI 生成的扫描参数格式错误"}
                        return

                    target = args.get("target")
                    nmap_args = args.get("arguments", "-sV -T4")

                    yield {"type": "status", "content": f"正在启动 Nmap 扫描目标: {target}..."}

                    # 使用 rustscan 加速模式（如果可用）
                    rustscan_path = check_rustscan_available()
                    if rustscan_path:
                        yield {"type": "status", "content": "使用 RustScan 加速模式..."}
                        nm = scan_hosts_rustscan(target, rustscan_path)
                    else:
                        nm = scan_hosts(target, nmap_args)

                    if not nm:
                        yield {"type": "error", "content": "Nmap 执行失败，请检查系统环境。"}
                        return

                    hosts_data = parse_scan_results(nm)

                    scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    scan_id = ScannerModel.create_scan([target], nmap_args, scan_time)
                    save_scan_to_db(scan_id, hosts_data)

                    yield {"type": "scan", "scan_id": scan_id}
                    yield {"type": "status", "content": "扫描完成，分析中..."}

                    messages.append(
                        {
                            "role": "assistant",
                            "content": content_buffer if content_buffer else "",
                            "tool_calls": [
                                {
                                    "id": tc["id"],
                                    "type": "function",
                                    "function": {
                                        "name": tc["name"],
                                        "arguments": tc["arguments"],
                                    },
                                }
                                for tc in tool_calls
                            ],
                        }
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "name": func_name,
                            "content": json.dumps(hosts_data[:15], ensure_ascii=False),
                        }
                    )

                    log("AI", "发起结果解读请求...")
                    final_response = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        stream=True,
                    )

                    for chunk in final_response:
                        if chunk.choices[0].delta.content:
                            yield {"type": "text", "content": chunk.choices[0].delta.content}

        except Exception as e:
            import traceback

            traceback.print_exc()
            yield {"type": "error", "content": f"AI 引擎内部错误: {str(e)}"}


def save_scan_to_db(scan_id, hosts_data):
    """保存扫描结果到数据库（与 network_scan.save_to_db 逻辑一致）"""
    if not hosts_data:
        return
    scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    count = 0
    for host in hosts_data:
        try:
            open_ports_str = ','.join(map(str, host.get('open_ports') or []))
            services_list = []
            for svc in host.get('services') or []:
                svc_str = f"{svc.get('port', '')}/{svc.get('service', '')}"
                if svc.get('product'):
                    svc_str += f" {svc['product']}"
                if svc.get('version'):
                    svc_str += f" {svc['version']}"
                services_list.append(svc_str)
            services_str = '; '.join(services_list)
            ScannerModel.save_host(scan_id, host, scan_time, open_ports_str, services_str)
            ScannerModel.upsert_asset(scan_id, host, scan_time)
            count += 1
        except Exception:
            pass
    if count > 0:
        ScannerModel.increment_hosts_count(scan_id, count)


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
    return re.sub(r'<(/?ban|/?</think>)>', '', reply, flags=re.IGNORECASE | re.DOTALL).strip()


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
    acl_number = switch_config.get("acl_number", 3000)
    device_type = switch_config.get("device_type")

    if not host or not username or not password or not device_type:
        _error(f"某台交换机(Switch: {host})的配置不完整。必须包含 host, username, password 和 device_type。")
        return

    try:
        _info(f"正在通过 Netmiko 连接到交换机 {host}:{port} ({device_type})...")
        device = {
            'device_type': device_type,
            'host': host,
            'username': username,
            'password': password,
            'port': port,
        }

        # 建立智能连接，自动处理登录和等待提示符
        net_connect = ConnectHandler(**device)

        _info(f"成功登录交换机 {host}。正在下发 ACL {acl_number} 封禁 {ip} 的命令集...")

        # 定义要执行的策略命令集合
        config_commands = [
            f'acl number {acl_number}',
            f'rule deny ip source {ip} 0'
        ]

        # Netmiko 会自动进入系统视图(system-view 或 conf t)并按顺序执行
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
