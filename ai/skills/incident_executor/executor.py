"""
IncidentExecutor - 应急响应执行器核心
管理 Agent 多轮工具调用循环：
  1. AI 分析事件 → 决策工具
  2. 执行工具 → 获取结果
  3. AI 分析结果 → 决策下一步
  4. 循环直到任务完成 → 生成报告 → 执行封禁
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Generator

# 确保能导入项目模块
_BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

from ai.client import (
    build_openai_messages,
    stream_openai_chat_with_tools,
)
from .incident_tools import get_incident_tool_definitions
from utils.logger import log as unified_log


# ── 公共辅助函数 ──────────────────────────────────────────────────────────────


def _safe_parse_json(result_str):
    """安全解析 JSON，失败时返回错误结构"""
    if isinstance(result_str, str):
        try:
            return json.loads(result_str)
        except (json.JSONDecodeError, ValueError):
            return {"ok": False, "error": result_str}
    return (
        result_str
        if isinstance(result_str, dict)
        else {"ok": False, "error": str(result_str)}
    )


# ─── 应急响应状态 ──────────────────────────────────────────────────────────────


class IncidentState:
    """应急响应执行状态，贯穿整个 Agent 循环"""

    def __init__(self):
        self.document_content: str = ""  # 原始事件描述
        self.event_summary: str = ""  # 事件摘要
        self.traffic_logs: list[dict] = []  # 流量日志
        self.packet_captures: list[dict] = []  # 数据包捕获
        self.report_content: str = ""  # 最终报告
        self.ban_records: list[dict] = []  # 封禁记录
        self.step_count: int = 0  # 已执行步骤数
        self.max_steps: int = 30  # 最大循环次数，防止死循环
        self.is_complete: bool = False  # 是否已完成
        self.history: list[dict] = []  # Agent 对话历史
        self._start_time = datetime.now()

    def add_result(self, result_type: str, result: dict):
        """通用结果收集，支持类型：traffic/packet/ban"""
        if result_type == "traffic":
            self.traffic_logs.append(result)
        elif result_type == "packet":
            self.packet_captures.append(result)
        elif result_type == "ban":
            self.ban_records.append(result)

    def get_exec_summary(self) -> str:
        elapsed = (datetime.now() - self._start_time).total_seconds()
        return (
            f"应急响应开始时间: {self._start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"已运行时长: {int(elapsed)}秒\n"
            f"已执行步骤: {self.step_count}/{self.max_steps}\n"
            f"流量分析: {len(self.traffic_logs)}次\n"
            f"数据包捕获: {len(self.packet_captures)}次\n"
            f"封禁记录: {len(self.ban_records)}个"
        )

    def to_dict(self) -> dict:
        return {
            "event_summary": self.event_summary,
            "traffic_logs": self.traffic_logs,
            "packet_captures": self.packet_captures,
            "ban_records": self.ban_records,
            "exec_summary": self.get_exec_summary(),
            "step_count": self.step_count,
            "is_complete": self.is_complete,
        }


# ─── 工具执行器映射 ──────────────────────────────────────────────────────────


def _execute_incident_tool(
    tool_name: str, arguments: dict, cfg: dict, state: IncidentState
) -> dict:
    """执行应急响应专用工具"""

    # ── 流量日志 ──────────────────────────────────────────────────────────
    if tool_name == "get_traffic_logs":
        time_range = arguments.get("time_range", "1小时内")
        port_filter = arguments.get("port_filter", "4705")
        # 流量时间设置为报告生成前的5分钟（预估值）
        log_time = (datetime.now() - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")

        # 返回提示词，告诉 AI 流量日志已获取
        result = {
            "ok": True,
            "message": f"流量日志已获取，发现对{port_filter}端口的异常UDP流量，建议继续获取数据包详情",
            "data": {
                "log_time": log_time,
                "time_range": time_range,
                "port_filter": port_filter,
                "异常流量": f"检测到对{port_filter}端口的大量异常UDP数据包",
                "可疑来源": "192.168.0.5",
                "目标端口": port_filter,
                "协议": "UDP",
                "建议": "继续获取数据包详情以确认攻击特征",
            },
        }

        state.add_result(
            "traffic",
            {
                "time": log_time,
                "time_range": time_range,
                "port_filter": port_filter,
                "result": result,
            },
        )

        time.sleep(10.0)
        return result

    # ── 数据包捕获 ────────────────────────────────────────────────────────
    if tool_name == "get_packet_capture":
        source_ip = arguments.get("source_ip", "192.168.0.5")
        port = arguments.get("port", "4705")
        # 数据包时间设置为报告生成前的5分钟（预估值）
        packet_time = (datetime.now() - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")

        # 返回提示词，告诉 AI 数据包已捕获
        packet_summary = (
"""==== Wireshark 数据包捕获分析 ====
捕获接口: \\Device\\NPF_{DEE85806-3469-4370-84A6-CCE3A4CD90A4}
捕获时间: """ + packet_time + """
统计: 共捕获 128 个异常 UDP 数据包，以下为典型帧

No.   时间            源地址               目标地址             协议  长度  信息
 953  """ + packet_time + """  10.24.101.246        10.24.102.83         UDP   948   63265 → 4705 Len=906
 997  """ + packet_time + """  10.24.101.246        10.24.102.113        UDP   948   63265 → 4705 Len=906
1041  """ + packet_time + """  10.24.101.246        10.24.102.150        UDP   948   63265 → 4705 Len=906

──── Frame 953 详细解析 ─────────────────────────────────────────────────────────
Frame 953: 948 bytes on wire, 948 bytes captured
Ethernet II, Src: CompalInform_6e:4d:63 (40:c2:ba:6e:4d:63), Dst: CompalInform_6e:4c:bb (40:c2:ba:6e:4c:bb)
Internet Protocol Version 4, Src: 10.24.101.246, Dst: 10.24.102.83
User Datagram Protocol, Src Port: 63265, Dst Port: 4705
Data (906 bytes)

0000  4f 4f 4e 43 00 00 01 00 10 00 00 00 19 6d 6a f9   OONC.........mj.
0010  29 5b b9 46 ab 95 8a 14 3e cd dc 26 0a 18 66 70   )[.F....>..&..fp
0020  1a 00 00 00 00 00 00 02 1f 55 00 00               .........U..

──── Frame 997 详细解析 (含恶意 Payload) ────────────────────────────────────────
Frame 997: 948 bytes on wire, 948 bytes captured
Ethernet II, Src: CompalInform_6e:4d:63 (40:c2:ba:6e:4d:63), Dst: VMware_89:8f:f7 (00:50:56:89:8f:f7)
Internet Protocol Version 4, Src: 10.24.101.246, Dst: 10.24.102.113
User Datagram Protocol, Src Port: 63265, Dst Port: 4705
Data (906 bytes)

0000  44 4d 4f 43 00 00 01 00 6e 03 00 00 5b 68 2b 25   DMOC....n...[h+%
0010  6f 61 64 4d a7 92 f0 47 00 c5 a4 0e 20 4e 00 00   oadM...G.... N..
0020  c0 a8 64 86 61 03 00 00 61 03 00 00 00 02 00 00   ..d.a...a.......
0030  00 00 00 00 0f 00 00 00 01 00 00 00 43 00 3a 00   ............C.:.
0040  5c 00 57 00 69 00 6e 00 64 00 6f 00 77 00 73 00   \.W.i.n.d.o.w.s.
0050  5c 00 73 00 79 00 73 00 74 00 65 00 6d 00 33 00   \.s.y.s.t.e.m.3.
0060  32 00 5c 00 63 00 6d 00 64 00 2e 00 65 00 78 00   2.\.c.m.d...e.x.
0070  65 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00   e...............
... [中间数据已省略 360 字节] ...
0230  00 00 00 00 00 00 00 00 00 00 00 00 2f 00 63 00   ............/.c.
0240  20 00 73 00 74 00 61 00 72 00 74 00 20 00 63 00    .s.t.a.r.t. .c.
0250  6d 00 64 00 20 00 2f 00 6b 00 20 00 74 00 61 00   m.d. ./.k. .t.a.
0260  73 00 6b 00 6b 00 69 00 6c 00 6c 00 20 00 2f 00   s.k.k.i.l.l. ./.
0270  69 00 6d 00 20 00 73 00 76 00 63 00 68 00 6f 00   i.m. .s.v.c.h.o.
0280  73 00 74 00 2e 00 65 00 78 00 65 00 20 00 2f 00   s.t...e.x.e. ./.
0290  66 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00   f...............

[!] 关键发现: Frame 997 Payload 解码为 UTF-16LE 字符串:
    C:\Windows\system32\cmd.exe /c start cmd /k taskkill /im svchost.exe /f
    → 远程命令执行攻击，可触发目标主机系统崩溃（蓝屏）""")

        result = {
            "ok": True,
            "message": f"数据包已捕获，包含对{port}端口的UDP数据包，Payload包含可执行命令，建议生成分析报告",
            "data": {
                "packet_time": packet_time,
                "packet_summary": packet_summary,
                "source_ip": source_ip,
                "target_port": port,
                "protocol": "UDP",
                "packet_count": 128,
                "payload_preview": "cmd.exe /k start",
                "attack特征": "远程命令执行，可导致系统蓝屏",
                "建议": "生成分析报告",
            },
        }

        state.add_result(
            "packet",
            {
                "time": packet_time,
                "source_ip": source_ip,
                "port": port,
                "result": result,
            },
        )

        time.sleep(10.0)
        return result

    # ── 生成报告 ─────────────────────────────────────────────────────────
    if tool_name == "generate_incident_report":
        exec_summary = arguments.get("exec_summary", state.get_exec_summary())

        # 获取数据包分析结果（结构: {result: {data: {packet_summary: ...}}}）
        packet_result = ""
        if state.packet_captures:
            last_packet = state.packet_captures[-1]
            pkt_data = last_packet.get("result", {}).get("data", {})
            if pkt_data.get("packet_summary"):
                packet_result = pkt_data["packet_summary"]

        # 获取流量分析结果
        traffic_stats = ""
        if state.traffic_logs:
            tlog = state.traffic_logs[-1]
            t_time = tlog.get("time", "")
            t_port = tlog.get("port_filter", "4705")
            traffic_stats = f"捕获时间: {t_time}，端口: {t_port}，协议: UDP，数据包总数: 128 个"

        # 获取封禁执行记录
        ban_summary_rows = ""
        for br in state.ban_records:
            br_target = br.get("target", "")
            br_type = br.get("policy_type", "")
            br_time = br.get("time", "")
            br_status = br.get("result", {}).get("message", "已执行")
            ban_summary_rows += f"| {br_target} | {'端口 ACL' if br_type == 'port' else 'IP 封禁'} | {br_time} | ✅ {br_status} |\n"

        # 生成完整写死的 Markdown 报告
        now = datetime.now()
        five_min_ago = (now - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        ban_table = ""
        if ban_summary_rows:
            ban_table = (
                "\n### 封禁执行记录\n\n"
                "| 封禁目标 | 封禁方式 | 执行时间 | 执行状态 |\n"
                "|----------|----------|----------|----------|\n"
                + ban_summary_rows
            )

        packet_block = f"```\n{packet_result}\n```" if packet_result else "> ⚠️ 数据包数据暂未获取"

        report = (
"""# 🚨 安全应急响应报告

> **生成时间**: """ + now_str + """
> **事件类型**: 批量电脑蓝屏安全事件
> **漏洞利用**: 极域电子教室软件 UDP 4705 端口远程命令执行漏洞
> **分析结论**: 攻击者向课堂内多台主机广播恶意 UDP 数据包，触发系统蓝屏

---

## 一、事件概述

| 项目 | 内容 |
|------|------|
| 事件名称 | 批量电脑蓝屏安全事件 |
| 发生时间 | """ + five_min_ago + """ |
| 影响范围 | 极域电子教室课堂环境（内网） |
| 事件分类 | 网络攻击 — 远程命令执行（RCE） |
| 紧急程度 | 🔴 高危 |
| 攻击者 IP | 192.168.0.15 |

---

## 二、受影响主机清单

| 主机 IP | MAC 地址 | 状态 | 首次攻击时间 |
|---------|----------|------|--------------|
| 10.24.102.83 | 40:c2:ba:6e:4c:bb | 🔴 已蓝屏 | """ + five_min_ago + """ |
| 10.24.102.113 | 00:50:56:89:8f:f7 | 🔴 已蓝屏 | """ + five_min_ago + """ |
| 10.24.102.150 | 40:c2:ba:6e:4d:22 | 🟡 已接收攻击包 | """ + five_min_ago + """ |
| 10.24.102.176 | 40:c2:ba:6e:4e:01 | 🟡 已接收攻击包 | """ + five_min_ago + """ |
| 10.24.102.200 | 40:c2:ba:6e:4f:88 | ⚪ 疑似受影响 | """ + five_min_ago + """ |

---

## 三、流量分析结果

**流量统计**：

| 指标 | 数值 |
|------|------|
| 异常数据包总数 | 128 个 |
| 攻击源 IP | 192.168.0.15 |
| 攻击源端口 | 63265 |
| 目标端口 | **4705**（极域电子教室） |
| 协议 | UDP |
| 单包大小 | 948 字节（Payload 906 字节） |
| 攻击持续时间 | 约 5 分钟 |

**流量特征**：
- 单一源 IP 向同网段多台主机 **广播式** 发送相同恶意 UDP 包
- 目标端口固定为 4705（极域电子教室软件监听端口）
- Payload 含 DMOC/OONC 协议魔数，利用软件解析漏洞执行系统命令

---

## 四、数据包捕获分析

**Wireshark 抓包结果**：

""" + packet_block + """

**Payload 解码**：

```
UTF-16LE 解码结果:
  C:\Windows\system32\cmd.exe
  /c start cmd /k taskkill /im svchost.exe /f
```

> 攻击者通过极域教室协议漏洞，在目标主机上以 **SYSTEM 权限** 执行上述命令，
> 强制终止 `svchost.exe` 进程，导致系统立即蓝屏崩溃（BSOD）。

---

## 五、攻击手法分析

**漏洞类型**：极域电子教室 UDP 4705 端口远程命令执行（RCE）

**CVE 参考**：与极域电子教室软件 UDP 广播解析缺陷相关（类似 CVE 漏洞模式）

**攻击链**：
1. 攻击者在课堂内网扫描运行极域电子教室的主机（端口 4705）
2. 构造含恶意 Payload 的 UDP 数据包（DMOC 协议头 + UTF-16LE 命令字符串）
3. 攻击者对课堂内网广播攻击，一次攻击可能影响多台主机（本模板支持直接封禁单个IP）
4. 目标主机接收后，极域进程以 SYSTEM 权限解析并执行嵌入命令
5. `taskkill /im svchost.exe /f` 强制终止关键系统进程，触发蓝屏

---

## 六、封禁措施

| 封禁目标 | 封禁方式 | 优先级 |
|----------|----------|--------|
| 端口 4705 (UDP) | 交换机 ACL 入站规则 | 🔴 紧急 |
| 192.168.0.15 | 交换机 IP 封禁（支持直接封禁单个IP） | 🔴 紧急 |
""" + ban_table + """
---

## 七、修复建议

### 立即措施
1. 在接入交换机上封禁 UDP 4705 端口的入站流量
2. 隔离攻击源主机 192.168.0.15（拔网线 / VLAN 隔离）
3. 直接封禁恶意IP 192.168.0.15（全面阻断攻击来源）
4. 重启受影响主机，检查系统日志确认无持久化后门

### 短期方案
1. 将极域电子教室软件升级至最新版本（厂商已发布补丁）
2. 在课堂网络部署 IDS/IPS，配置 UDP 4705 异常流量告警规则
3. 审查所有教师机账户，排查账户是否被攻击者利用

### 长期方案
1. 对课堂内网实施 VLAN 隔离，限制主机间横向通信
2. 建立网络安全基线，定期扫描高危端口
3. 部署网络行为分析（NBA）系统，识别广播式攻击模式

---

> 本报告由 **玄枢指挥官** AI 自动生成 | 应急响应完成时间：""" + now_str + """
""")

        state.report_content = report
        state.is_complete = True

        time.sleep(10.0)
        return {
            "ok": True,
            "report": report,
            "summary": state.get_exec_summary(),
        }

    # ── 执行封禁 ─────────────────────────────────────────────────────────
    if tool_name == "apply_ban_policy":
        target = arguments.get("target", "")
        policy_type = arguments.get("policy_type", "port")

        if not target:
            return {"ok": False, "error": "缺少封禁目标"}

        # 白名单检查
        whitelist = cfg.get('ai', {}).get('whitelist', []) if cfg else []
        if target in whitelist:
            result = {
                "ok": True,
                "message": f"目标 {target} 在白名单中，已跳过封禁",
                "data": {
                    "target": target,
                    "policy_type": policy_type,
                    "执行时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "状态": "已跳过（白名单）",
                },
            }
            state.add_result("ban", {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "target": target, "policy_type": policy_type, "result": result})
            return result

        # 返回提示词，告诉 AI 封禁已执行
        result = {
            "ok": True,
            "message": f"已对{'端口 ' + target if policy_type == 'port' else 'IP ' + target}执行封禁策略，攻击流量将被阻断",
            "data": {
                "target": target,
                "policy_type": policy_type,
                "执行时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "状态": "已执行",
            },
        }

        state.add_result(
            "ban",
            {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "target": target,
                "policy_type": policy_type,
                "result": result,
            },
        )

        time.sleep(10.0)
        return result

    # ── ACL策略封禁 ─────────────────────────────────────────────────────
    if tool_name == "acl_policy_ban":
        acl_command = arguments.get("acl_command", "")

        if not acl_command:
            return {"ok": False, "error": "缺少ACL命令"}

        parts = acl_command.strip().split()

        # 判断命令类型
        if "ip access-list extended" in acl_command.lower():
            # 进入ACL配置模式命令
            if len(parts) < 4:
                return {"ok": False, "error": "命令格式错误，如: ip access-list extended udp"}
            acl_name = parts[3]
            result = {
                "ok": True,
                "message": f"已进入ACL配置模式: {acl_name}",
                "data": {
                    "command": acl_command,
                    "mode": "config-ext-nacl",
                    "acl_name": acl_name,
                    "执行时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "状态": "已执行",
                },
            }
            state.add_result("ban", {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "command": acl_command, "result": result})
            return result

        elif len(parts) >= 5 and parts[0].isdigit():
            # 添加ACL规则: 20 deny udp any any eq 4750
            rule_id = parts[0]
            action = parts[1].lower()
            protocol = parts[2].lower()
            source = parts[3]
            destination = parts[4]

            if action not in ("deny", "permit"):
                return {"ok": False, "error": f"不支持的动作: {action}，仅支持 deny/permit"}

            # 解析端口
            target_port = None
            operator = None
            for i, part in enumerate(parts):
                if part in ("eq", "gt", "lt", "neq") and i + 1 < len(parts):
                    operator = part
                    target_port = parts[i + 1]
                    break

            # 解析目标IP (host x.x.x.x 或 CIDR)
            target_ip = None
            if destination.startswith("host "):
                target_ip = destination.replace("host ", "")
            elif destination not in ("any",):
                target_ip = destination

            # 确定封禁目标
            if target_port:
                ban_target = target_port
                ban_type = "port"
            elif target_ip:
                ban_target = target_ip
                ban_type = "ip"
            else:
                return {"ok": False, "error": "无法解析目标端口或IP"}

            # 白名单检查
            whitelist = cfg.get('ai', {}).get('whitelist', []) if cfg else []
            if ban_target in whitelist:
                result = {
                    "ok": True,
                    "message": f"目标 {ban_target} 在白名单中，已跳过封禁",
                    "data": {
                        "command": acl_command,
                        "rule_id": rule_id,
                        "ban_target": ban_target,
                        "ban_type": ban_type,
                        "执行时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "状态": "已跳过（白名单）",
                    },
                }
                state.add_result("ban", {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "target": ban_target, "type": ban_type, "result": result})
                return result

            # 执行封禁
            result = {
                "ok": True,
                "message": f"sw(config-ext-nacl)#{rule_id} {action} {protocol} {source} {destination} {'eq ' + target_port if target_port else ''}",
                "data": {
                    "command": acl_command,
                    "rule_id": rule_id,
                    "action": action,
                    "protocol": protocol,
                    "source": source,
                    "destination": destination,
                    "operator": operator,
                    "target_port": target_port,
                    "target_ip": target_ip,
                    "ban_target": ban_target,
                    "ban_type": ban_type,
                    "执行时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "状态": "已执行",
                },
            }

            state.add_result(
                "ban",
                {
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "command": acl_command,
                    "target": ban_target,
                    "type": ban_type,
                    "result": result,
                },
            )

            time.sleep(10.0)
            return result

        else:
            return {"ok": False, "error": "ACL命令格式错误，支持: ip access-list extended <name> 或 <rule_id> deny <protocol> <source> <destination> eq <port>"}

    # ── 未知工具 ─────────────────────────────────────────────────────────
    return {"ok": False, "error": f"未知应急响应工具: {tool_name}"}


# ─── 系统提示词 ─────────────────────────────────────────────────────────────


INCIDENT_SYSTEM_PROMPT = """你叫**玄枢指挥官**，专业的网络安全应急响应 Agent。

## 核心规则
1. 收到安全事件后，**先用文字分析并列出执行计划表格**，询问用户确认后再执行
2. 用户回复"开始"、"确认"或"继续"后，才开始按顺序调用工具
3. 每步工具执行完毕，根据结果决定下一步，直到 generate_incident_report 执行完毕
4. 报告生成后，**必须询问用户是否同意执行封禁策略**

## 应急响应流程
1. 调用 get_traffic_logs 获取流量日志
2. 调用 get_packet_capture 获取数据包内容
3. 调用 generate_incident_report 生成报告
4. 用户确认后调用 apply_ban_policy 或 acl_policy_ban 执行封禁（acl_policy_ban 支持Cisco风格ACL命令，如 'ip access-list extended udp' 进入配置模式，'20 deny udp any any eq 4750' 添加规则）

## 重要说明
- 收到任务后**先分析事件内容，输出执行计划表格**，并询问用户"是否开始执行？"
- 用户确认后，才开始调用工具
- 每步工具执行完毕看结果再决定下一步工具
- 所有工具调用完毕后才输出总结文字
- 报告生成后必须询问用户是否执行封禁策略"""


# ─── 主执行器 ────────────────────────────────────────────────────────────────


def create_incident_stream(
    event_content: str,
    cfg: dict,
    state: IncidentState | None = None,
    session_history: list | None = None,
    openai_content: list | None = None,
) -> Generator[str, None, IncidentState]:
    """
    创建应急响应 Agent 流式执行器（生成器）。

    参数:
        event_content: 安全事件描述
        cfg: 系统配置
        state: 应急响应状态（可外部传入，用于支持断点续传）
        session_history: 之前的会话历史（用于继续执行）
        openai_content: OpenAI 多模态内容（包含图片等）

    返回:
        Generator[str, None, IncidentState]: 生成 SSE 数据行的生成器
    """
    if state is None:
        state = IncidentState()
    state.document_content = event_content

    tools = get_incident_tool_definitions()
    history: list[dict] = []

    # 注入系统提示
    combined_system = f"{INCIDENT_SYSTEM_PROMPT}\n\n你叫玄枢指挥官，你是一个专业的网络安全应急响应助手。"
    history.append({"role": "system", "content": combined_system})

    # 如果有会话历史，注入到历史中（用于继续执行）
    if session_history:
        for msg in session_history:
            role = msg.get("role")
            if role == "user":
                if not any(m.get("role") == "user" for m in history[1:]):
                    history.append(
                        {
                            "role": "user",
                            "content": msg.get("content", ""),
                        }
                    )
            elif role == "assistant":
                tool_calls = msg.get("tool_calls")
                if tool_calls:
                    formatted_calls = (
                        tool_calls
                        if isinstance(tool_calls, list)
                        else json.loads(str(tool_calls))
                    )
                    history.append(
                        {
                            "role": "assistant",
                            "content": msg.get("content") or None,
                            "tool_calls": formatted_calls,
                        }
                    )
                else:
                    history.append(
                        {"role": "assistant", "content": msg.get("content", "")}
                    )
            elif role == "tool":
                history.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.get("tool_call_id", "unknown"),
                        "content": msg.get("content", ""),
                    }
                )
        # 注入继续执行指令
        history.append(
            {
                "role": "user",
                "content": "继续执行，立即调用下一个工具，不要重新展示计划表。",
            }
        )
    else:
        # 注入事件内容作为用户消息（触发 Agent 启动）
        user_content = (
            f"安全事件已收到，请分析以下事件并制定应急响应计划。\n\n"
            f"## 安全事件描述\n\n{event_content}"
        )
        history.append(
            {
                "role": "user",
                "content": user_content,
                "openai_content": openai_content,
            }
        )

    # ─── Agent 主循环 ───────────────────────────────────────────────────
    while state.step_count < state.max_steps and not state.is_complete:
        state.step_count += 1
        unified_log(
            "IncidentExecutor",
            f"=== Agent Step {state.step_count}/{state.max_steps} ===",
            "INFO",
        )

        # 工具名到描述的映射（提前定义，供步骤消息和工具执行使用）
        tool_descriptions = {
            "get_traffic_logs": "获取网络流量日志，分析异常流量",
            "get_packet_capture": "获取数据包捕获内容，分析攻击特征",
            "generate_incident_report": "生成安全应急响应报告",
            "apply_ban_policy": "执行封禁策略，阻断攻击流量",
            "acl_policy_ban": "使用Cisco风格ACL命令执行封禁，如 'ip access-list extended udp' 进入配置模式，或 '20 deny udp any any eq 4750' 添加规则",
        }

        # LLM 决策：是否调用工具
        # 第一步用 none 强制AI只输出文字（计划表格），不调用工具
        # 有 session_history 时（用户确认后继续执行）用 required 强制调用工具
        if state.step_count == 1 and session_history is None:
            tc_choice = 'none'
        elif session_history:
            tc_choice = 'required'
        else:
            tc_choice = 'auto'

        # 发送步骤开始信息
        # required 模式（强制工具调用）：等待 LLM 决策后，再发送含工具名的步骤消息
        if tc_choice != 'required':
            yield (
                json.dumps(
                    {
                        "content": f"🤔 AI 正在分析并决策下一步行动... (第 {state.step_count} 步)"
                    }
                )
                + "\n\n"
            )

        tool_calls = []
        text_chunks = []

        for chunk, error, tool_call in stream_openai_chat_with_tools(
            build_openai_messages(history), cfg, tools=tools, tool_choice=tc_choice
        ):
            if error:
                yield json.dumps({"error": error}) + "\n\n"
                return state

            if chunk:
                text_chunks.append(chunk)
                yield json.dumps({"content": chunk}) + "\n\n"

            if tool_call:
                tool_calls.append(tool_call)

        # 合并文本响应
        response_text = "".join(text_chunks)

        # required 模式：工具决策完成后，发送含工具名的步骤消息
        if tc_choice == 'required':
            if tool_calls:
                tools_info = "、".join([
                    f"**{tc['name']}**（{tool_descriptions.get(tc['name'], tc['name'])}）"
                    for tc in tool_calls
                ])
                yield (
                    json.dumps({"content": f"🤔 AI 分析决策完成 (第 {state.step_count} 步)：准备调用 {tools_info}\n\n"})
                    + "\n\n"
                )
            else:
                yield (
                    json.dumps({"content": f"🤔 AI 分析完成 (第 {state.step_count} 步)\n\n"})
                    + "\n\n"
                )

        # ─── 如果没有工具调用，结束循环 ─────────────────────────────────
        if not tool_calls:
            if response_text:
                history.append({"role": "assistant", "content": response_text})
                yield (
                    json.dumps(
                        {
                            "step_complete": {
                                "content": response_text,
                                "tool_calls": [],
                            }
                        }
                    )
                    + "\n\n"
                )
            unified_log("IncidentExecutor", f"AI 无更多工具调用，应急响应结束（step={state.step_count}）", "INFO")
            break

        # ─── 执行工具调用 ───────────────────────────────────────────────
        last_tool_name = None
        last_tool_result = None
        for tc in tool_calls:
            tool_name = tc["name"]
            tool_args = tc["arguments"]
            last_tool_name = tool_name

            unified_log(
                "IncidentExecutor",
                f"🤖 执行工具: {tool_name} | 参数: {json.dumps(tool_args, ensure_ascii=False)[:200]}",
                "INFO",
            )

            # 发送工具调用开始
            yield (
                json.dumps(
                    {
                        "tool_call": {
                            "id": tc["id"],
                            "name": tool_name,
                            "description": tool_descriptions.get(tool_name, ""),
                            "arguments": tool_args,
                        }
                    }
                )
                + "\n\n"
            )

            # 保存 AI 的 tool_call 消息
            if tc is tool_calls[0]:
                history.append(
                    {
                        "role": "assistant",
                        "content": response_text if response_text else None,
                        "tool_calls": [
                            {
                                "id": t["id"],
                                "type": "function",
                                "function": {
                                    "name": t["name"],
                                    "arguments": json.dumps(
                                        t["arguments"], ensure_ascii=False
                                    ),
                                },
                            }
                            for t in tool_calls
                        ],
                    }
                )

            # 执行工具
            tool_result = _execute_incident_tool(tool_name, tool_args, cfg, state)
            last_tool_result = tool_result

            # 序列化结果
            if isinstance(tool_result, dict):
                result_str = json.dumps(tool_result, ensure_ascii=False)
            else:
                result_str = str(tool_result)

            # 发送给前端（截断过长的结果）
            display_result = (
                result_str[:2000] + "..." if len(result_str) > 2000 else result_str
            )
            yield (
                json.dumps(
                    {
                        "tool_result": {
                            "id": tc["id"],
                            "name": tool_name,
                            "result": display_result,
                            "full_result": result_str,
                        }
                    }
                )
                + "\n\n"
            )

            # 追加工具结果到历史
            history.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "name": tool_name,
                "content": result_str
            })

            # 如果是报告生成工具，流式输出报告内容
            if (
                tool_name == "generate_incident_report"
                and isinstance(tool_result, dict)
                and tool_result.get("report")
            ):
                report_content = tool_result["report"]
                # 按小chunk流式输出，每个chunk通过前端的typewriter效果显示
                # 10字符/chunk，0.5秒/chunk = 20字/秒
                chunk_size = 10
                for i in range(0, len(report_content), chunk_size):
                    chunk = report_content[i:i + chunk_size]
                    yield (json.dumps({"incident_report_chunk": chunk}) + "\n\n")
                    time.sleep(0.3)

        # 发送步骤完成事件
        if tool_calls:
            yield (
                json.dumps(
                    {
                        "step_complete": {
                            "content": response_text,
                            "tool_calls": [
                                {
                                    "id": t["id"],
                                    "type": "function",
                                    "function": {
                                        "name": t["name"],
                                        "arguments": json.dumps(
                                            t["arguments"], ensure_ascii=False
                                        ),
                                    },
                                }
                                for t in tool_calls
                            ],
                        }
                    }
                )
                + "\n\n"
            )

        # 检查是否已生成报告（应急响应完成）
        if (
            last_tool_name == "generate_incident_report"
            and last_tool_result
            and last_tool_result.get("ok")
        ):
            state.is_complete = True
            # 发送报告链接，供前端跳转
            yield (json.dumps({"incident_report_link": "/reports"}) + "\n\n")

    # ─── 循环结束 ────────────────────────────────────────────────────────
    if not state.is_complete and state.step_count >= state.max_steps:
        yield json.dumps({"content": "⚠️ 应急响应达到最大步数限制，自动结束"}) + "\n\n"

    unified_log(
        "IncidentExecutor",
        f"应急响应完成 | 总步骤: {state.step_count} | 流量分析: {len(state.traffic_logs)}次 | 数据包捕获: {len(state.packet_captures)}次",
        "INFO",
    )

    return state
