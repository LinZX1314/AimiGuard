"""
DrillExecutor - 演练执行器核心
管理 Agent 多轮工具调用循环：
  1. AI 分析文档 → 决策工具
  2. 执行工具 → 获取结果
  3. AI 分析结果 → 决策下一步
  4. 循环直到任务完成 → 生成报告
"""
import json
import re
import os
import sys
from datetime import datetime
from typing import Generator

# 确保能导入项目模块
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

from ai.client import build_openai_messages, stream_openai_chat_with_tools, stream_openai_chat_completion
from ai.tools import execute_tool as execute_existing_tool
from .drill_tools import get_drill_tool_definitions
from utils.logger import log as unified_log


# ── 公共辅助函数 ──────────────────────────────────────────────────────────────
def _safe_parse_json(result_str):
    """安全解析 JSON，失败时返回错误结构"""
    if isinstance(result_str, str):
        try:
            return json.loads(result_str)
        except (json.JSONDecodeError, ValueError):
            return {'ok': False, 'error': result_str}
    return result_str if isinstance(result_str, dict) else {'ok': False, 'error': str(result_str)}


def _analyze_document(doc_content: str) -> dict:
    """
    解析安全演练文档，提取结构化信息

    返回:
        {
            'summary': str,           # 文档摘要
            'target_network': str,     # 目标网络
            'key_services': list,     # 重点服务
            'requirements': str,      # 演练要求
            'action_plan': str,       # 行动计划
        }
    """
    # ── 提取目标网络/IP段 ────────────────────────────────────────────────
    ip_patterns = [
        r'(?:目标|扫描范围|网络(?:地址|段)?)[\s:：]*([^\s\n,，]+(?:/[0-9]+)?)',
        r'(?:IP|ip)[\s:：]*([^\s\n,，]+(?:/[0-9]+)?)',
        r'((?:192\.168|10\.|172\.(?:1[6-9]|2[0-9]|3[01]))(?:[0-9.]+(?:/[0-9]+)?)?)',
        r'((?:172\.(?:1[6-9]|2[0-9]|3[01])\.[0-9]+\.[0-9]+(?:/[0-9]+)?))',
    ]

    target_network = ''
    for pattern in ip_patterns:
        match = re.search(pattern, doc_content)
        if match:
            target_network = match.group(1).strip()
            break

    # 如果没找到，尝试查找整个网段格式
    if not target_network:
        cidr_match = re.search(r'(\d+\.\d+\.\d+\.\d+/\d+)', doc_content)
        if cidr_match:
            target_network = cidr_match.group(1)

    # ── 提取重点服务 ────────────────────────────────────────────────────
    service_keywords = {
        'web': ['web', 'http', 'https', '网站', '80', '443', '8080', '8443'],
        'ssh': ['ssh', '22', '远程登录', 'linux', '服务器'],
        'rdp': ['rdp', '3389', '远程桌面', 'windows'],
        'mysql': ['mysql', '3306', '数据库', 'db', 'mariadb'],
        'redis': ['redis', '6379', '缓存'],
        'mongodb': ['mongodb', '27017', 'nosql'],
        'ftp': ['ftp', '21', '文件传输'],
        'smb': ['smb', '445', '139', '共享', 'samba'],
        'telnet': ['telnet', '23'],
        'dns': ['dns', '53', '域名'],
        'mail': ['mail', 'smtp', '110', '143', '邮件'],
    }

    found_services = []
    doc_lower = doc_content.lower()
    for service, keywords in service_keywords.items():
        if any(kw.lower() in doc_lower for kw in keywords):
            found_services.append(service)

    # 如果没找到明确服务，默认检查常见服务
    if not found_services:
        found_services = ['web', 'ssh', 'rdp', 'mysql']

    # ── 提取演练要求 ────────────────────────────────────────────────────
    requirement_patterns = [
        r'(?:演练|测试|检测|要求|目标)[\s:：]*(.{10,200}?)(?:\n|$)',
        r'需[要求]?.{10,100}',
        r'请.{10,100}',
    ]

    requirements = ''
    for pattern in requirement_patterns:
        match = re.search(pattern, doc_content)
        if match:
            req = match.group(1).strip()
            if len(req) > 10:
                requirements = req
                break

    if not requirements:
        requirements = '全面检测网络安全漏洞，发现问题如实记录'

    # ── 生成行动计划 ────────────────────────────────────────────────────
    action_plan_lines = [
        f"1. drill_analyze_and_plan → 分析 {target_network or '目标网络'}",
        f"2. drill_network_scan → 扫描网络",
    ]

    if 'ssh' in found_services:
        action_plan_lines.append("3. drill_bruteforce_ssh → SSH检测")
    if 'rdp' in found_services:
        action_plan_lines.append("4. drill_bruteforce_rdp → RDP检测")
    if 'mysql' in found_services:
        action_plan_lines.append("5. drill_bruteforce_mysql → MySQL检测")

    action_plan_lines.extend([
        "6. drill_honeypot_audit → 蜜罐审计",
        "7. drill_generate_report → 生成报告",
    ])

    action_plan = '\n'.join(action_plan_lines)

    # ── 生成摘要 ────────────────────────────────────────────────────────
    summary = f"""目标网络：{target_network or '未明确指定'}
重点服务：{', '.join(found_services)}
演练要求：{requirements}
已制定{len(action_plan_lines)}步行动计划"""

    return {
        'summary': summary,
        'target_network': target_network,
        'key_services': found_services,
        'requirements': requirements,
        'action_plan': action_plan,
    }


# ─── 演练状态 ────────────────────────────────────────────────────────────────

class DrillState:
    """演练执行状态，贯穿整个 Agent 循环"""

    def __init__(self):
        self.document_content: str = ''          # 原始文档内容
        self.document_summary: str = ''           # AI 分析后的摘要
        self.action_plan: str = ''               # 执行计划
        self.scan_results: list[dict] = []        # 扫描结果
        self.screenshot_results: list[dict] = []  # 截图结果
        self.bruteforce_results: list[dict] = [] # 弱口令结果
        self.honeypot_results: list[dict] = []    # 蜜罐日志
        self.ban_records: list[dict] = []          # 封禁记录
        self.findings: list[dict] = []            # 发现的问题
        self.report_content: str = ''             # 最终报告
        self.step_count: int = 0                  # 已执行步骤数
        self.max_steps: int = 30                 # 最大循环次数，防止死循环
        self.is_complete: bool = False           # 是否已完成
        self.target_network: str = ''             # 目标网络范围
        self.history: list[dict] = []             # Agent 对话历史
        self._start_time = datetime.now()

    def add_result(self, result_type: str, result: dict):
        """通用结果收集，支持类型：scan/screenshot/bruteforce/honeypot/finding/ban"""
        mapping = {
            'scan': self.scan_results,
            'screenshot': self.screenshot_results,
            'bruteforce': self.bruteforce_results,
            'honeypot': self.honeypot_results,
            'finding': self.findings,
            'ban': self.ban_records,
        }
        mapping.get(result_type, self.findings).append(result)

    def get_exec_summary(self) -> str:
        elapsed = (datetime.now() - self._start_time).total_seconds()
        return (
            f"演练开始时间: {self._start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"已运行时长: {int(elapsed)}秒\n"
            f"已执行步骤: {self.step_count}/{self.max_steps}\n"
            f"目标网络: {self.target_network or '待确定'}\n"
            f"网络扫描: {len(self.scan_results)}次\n"
            f"Web截图: {len(self.screenshot_results)}张\n"
            f"弱口令检测: {len(self.bruteforce_results)}次\n"
            f"蜜罐审计: {len(self.honeypot_results)}次\n"
            f"封禁IP: {len(self.ban_records)}个\n"
            f"发现问题: {len(self.findings)}个"
        )

    def to_dict(self) -> dict:
        return {
            'document_summary': self.document_summary,
            'action_plan': self.action_plan,
            'scan_results': self.scan_results,
            'screenshot_results': self.screenshot_results,
            'bruteforce_results': self.bruteforce_results,
            'honeypot_results': self.honeypot_results,
            'ban_records': self.ban_records,
            'findings': self.findings,
            'exec_summary': self.get_exec_summary(),
            'step_count': self.step_count,
            'is_complete': self.is_complete,
            'target_network': self.target_network,
        }


# ─── 工具执行器映射 ──────────────────────────────────────────────────────────

def _execute_drill_tool(tool_name: str, arguments: dict, cfg: dict, state: DrillState) -> dict:
    """执行演练专用工具"""
    import threading
    from datetime import datetime

    # ── drill_analyze_and_plan ──────────────────────────────────────────────
    if tool_name == 'drill_analyze_and_plan':
        doc_content = arguments.get('document_content', state.document_content)
        if not doc_content:
            doc_content = state.document_content

        if not doc_content:
            return {'ok': False, 'error': '无文档内容'}

        analysis = _analyze_document(doc_content)
        state.document_summary = analysis['summary']
        state.target_network = analysis['target_network']
        state.action_plan = analysis['action_plan']

        return {
            'ok': True,
            'target_network': analysis['target_network'],
            'key_services': analysis['key_services'],
            'action_plan': analysis['action_plan'],
        }

    # ── drill_network_scan ─────────────────────────────────────────────────
    if tool_name == 'drill_network_scan':
        target = arguments.get('target', '')
        ports = arguments.get('ports', '21,22,23,80,81,135,139,443,445,1433,3306,5432,6379,8080,8443')

        if not target:
            return {'ok': False, 'error': '缺少目标'}

        state.target_network = target

        result_str = execute_existing_tool('run_fscan', {
            'target': target,
            'port': ports,
            'threads': arguments.get('threads', 6000),
        }, cfg)

        result = _safe_parse_json(result_str)

        if result.get('ok'):
            state.add_result('scan', {
                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'target': target,
                'result': result,
            })

            # 提取发现的主机和漏洞
            hosts = result.get('主机列表', [])
            vuln_list = result.get('漏洞列表', [])

            for h in hosts:
                ports_str = h.get('ports', '')
                if ports_str:
                    state.add_result('finding', {
                        'ip': h.get('ip'),
                        'ports': ports_str,
                        'type': 'open_ports',
                        'severity': 'info',
                    })
            for v in vuln_list:
                state.add_result('finding', {
                    'ip': v.get('ip'),
                    'port': v.get('port'),
                    'service': v.get('service'),
                    'vuln': v.get('vuln'),
                    'type': 'vulnerability',
                    'severity': 'high',
                })

        return result

    # ── drill_web_screenshot ────────────────────────────────────────────────
    if tool_name == 'drill_web_screenshot':
        url = arguments.get('url', '')
        ip = arguments.get('ip', '')
        port = arguments.get('port', 80)

        if not url or not ip:
            return {'ok': False, 'error': '缺少参数'}

        result_str = execute_existing_tool('take_screenshot', {
            'url': url,
            'ip': ip,
            'port': port,
        }, cfg)

        result = _safe_parse_json(result_str)

        if result.get('ok'):
            state.add_result('screenshot', {
                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'ip': ip,
                'port': port,
                'url': url,
                'screenshot_url': result.get('screenshot_url', ''),
            })

        return result

    # ── 弱口令检测 ─────────────────────────────────────────────────────────
    if tool_name in ('drill_bruteforce_ssh', 'drill_bruteforce_rdp', 'drill_bruteforce_mysql'):
        target_ip = arguments.get('target_ip', '')
        port = arguments.get('port', 22 if 'ssh' in tool_name else (3389 if 'rdp' in tool_name else 3306))

        if not target_ip:
            return {'ok': False, 'error': '缺少目标IP'}

        from .bruteforce import run_bruteforce
        result = run_bruteforce(tool_name, target_ip, port)

        if result.get('ok'):
            state.add_result('bruteforce', {
                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'tool': tool_name,
                'target': target_ip,
                'port': port,
                'result': result,
            })

            if result.get('vulnerable'):
                state.add_result('finding', {
                    'ip': target_ip,
                    'port': port,
                    'service': tool_name.replace('drill_bruteforce_', '').upper(),
                    'type': 'weak_password',
                    'severity': 'critical',
                    'description': f"发现弱口令: {result.get('vulnerable_creds', [])}",
                    'credentials': result.get('vulnerable_creds', []),
                })

        return result

    # ── 蜜罐审计 ────────────────────────────────────────────────────────────
    if tool_name == 'drill_honeypot_audit':
        service_name = arguments.get('service_name')
        limit = arguments.get('limit', 50)

        logs_str = execute_existing_tool('get_honeypot_logs', {
            'service_name': service_name,
            'limit': limit,
        }, cfg)
        logs_result = _safe_parse_json(logs_str)

        stats_str = execute_existing_tool('get_honeypot_stats', {}, cfg)
        stats_result = _safe_parse_json(stats_str)

        if logs_result.get('ok'):
            state.add_result('honeypot', {
                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'service': service_name or '全部',
                'count': logs_result.get('总数', 0),
                'records': logs_result.get('攻击记录', [])[:10],
                'total_attacks': stats_result.get('总攻击次数', 0),
                'top_services': stats_result.get('热门攻击服务', [])[:10],
                'top_sources': stats_result.get('攻击来源Top10', []),
                'trend': stats_result.get('7天攻击趋势', {}),
            })

            records = logs_result.get('攻击记录', [])
            for rec in records:
                state.add_result('finding', {
                    'ip': rec.get('攻击IP'),
                    'service': rec.get('服务'),
                    'type': 'honeypot_attack',
                    'severity': 'medium',
                    'description': f"蜜罐遭受来自 {rec.get('攻击IP')} 的攻击",
                    'location': rec.get('来源地区'),
                })

        return {'ok': logs_result.get('ok', False), 'logs': logs_result, 'stats': stats_result}

    # ── 本机IP查询 ──────────────────────────────────────────────────────────
    if tool_name == 'drill_get_local_ip':
        import socket
        lan_ip = '无法获取'
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            lan_ip = s.getsockname()[0]
            s.close()
        except Exception:
            pass
        return {'ok': True, 'lan_ip': f"{lan_ip}/24"}

    # ── 报告生成 ────────────────────────────────────────────────────────────
    if tool_name == 'drill_generate_report':
        exec_summary = arguments.get('exec_summary', state.get_exec_summary())
        scan_results_str = json.dumps(state.scan_results, ensure_ascii=False, indent=2)
        bruteforce_str = json.dumps(state.bruteforce_results, ensure_ascii=False, indent=2)
        honeypot_str = json.dumps(state.honeypot_results, ensure_ascii=False, indent=2)
        findings_str = json.dumps(state.findings, ensure_ascii=False, indent=2)

        # 生成 Markdown 报告
        report = _generate_markdown_report(state, exec_summary, scan_results_str, bruteforce_str, honeypot_str, findings_str)
        state.report_content = report
        state.is_complete = True

        return {
            'ok': True,
            'report': report,
            'summary': state.get_exec_summary(),
        }

    # ── 未知工具 ────────────────────────────────────────────────────────────
    return {'ok': False, 'error': f'未知演练工具: {tool_name}'}


def _generate_markdown_report(state: DrillState, exec_summary: str, scan_results: str,
                                bruteforce_results: str, honeypot_results: str, findings: str) -> str:
    """生成 Markdown 格式的演练报告"""
    from datetime import datetime

    # 按严重级别分组（一次遍历）
    grouped = {'critical': [], 'high': [], 'medium': [], 'info': []}
    for f in state.findings:
        sev = f.get('severity', 'info')
        grouped.get(sev, grouped['info']).append(f)
    critical, high, medium, info = grouped['critical'], grouped['high'], grouped['medium'], grouped['info']

    report = f"""# 🛡️ 安全演练报告

> **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
> **目标网络**: {state.target_network or '未指定'}

---

## 一、执行摘要

```
{exec_summary}
```

---

## 二、演练文档分析

**文档摘要**:
{state.document_summary or '未提供文档内容'}

**执行计划**:
{state.action_plan or '无明确执行计划'}

---

## 三、安全问题发现

### 3.1 🔴 严重风险 ({len(critical)} 项)

"""

    for i, f in enumerate(critical, 1):
        report += f"""
**{i}. {f.get('type', '未知类型').upper()}**
- **IP**: {f.get('ip', 'N/A')}
- **端口**: {f.get('port', 'N/A')}
- **服务**: {f.get('service', 'N/A')}
- **描述**: {f.get('description', 'N/A')}
"""
        if f.get('credentials'):
            creds = f.get('credentials', [])
            report += f"- **泄露凭据**: `{'`, `'.join(creds)}`\n"

    report += f"""
### 3.2 🟠 高危问题 ({len(high)} 项)

"""
    for i, f in enumerate(high, 1):
        report += f"""
**{i}. {f.get('type', '未知类型').upper()}**
- **IP**: {f.get('ip', 'N/A')}
- **端口**: {f.get('port', 'N/A')}
- **漏洞**: {f.get('vuln', f.get('description', 'N/A'))}
"""

    report += f"""
### 3.3 🟡 中危问题 ({len(medium)} 项)

"""
    for i, f in enumerate(medium, 1):
        report += f"""
**{i}. {f.get('type', '未知类型')}**
- **IP**: {f.get('ip', 'N/A')}
- **服务**: {f.get('service', 'N/A')}
- **描述**: {f.get('description', 'N/A')}
"""

    report += f"""
### 3.4 ℹ️ 信息类 ({len(info)} 项)

"""
    for i, f in enumerate(info, 1):
        report += f"""
**{i}. {f.get('description', 'Web服务发现')}**
- **IP**: {f.get('ip', 'N/A')}:{f.get('port', 'N/A')}
- **URL**: {f.get('url', 'N/A')}
"""

    report += f"""
---

## 四、网络扫描结果

**扫描次数**: {len(state.scan_results)}

"""
    for sr in state.scan_results:
        r = sr.get('result', {})
        hosts = r.get('主机列表', [])
        vulns = r.get('漏洞列表', [])
        report += f"""
### 扫描目标: `{sr.get('target', 'N/A')}` @ {sr.get('time', 'N/A')}
- **发现主机**: {r.get('发现主机', 0)} 台
- **发现漏洞**: {len(vulns)} 个

**存活主机**:
"""
        for h in hosts[:20]:
            report += f"- `{h.get('ip', 'N/A')}` - 端口: {h.get('ports', 'N/A')}\n"

    report += f"""
---

## 五、Web 截图采集

**截图数量**: {len(state.screenshot_results)} 张

| # | IP | 端口 | URL | 采集时间 |
|---|----|------|-----|----------|
"""

    for i, sr in enumerate(state.screenshot_results, 1):
        report += f"| {i} | `{sr.get('ip', 'N/A')}` | {sr.get('port', 'N/A')} | {sr.get('url', 'N/A')} | {sr.get('time', 'N/A')} |\n"

    report += f"""
---

## 六、弱口令检测结果

**检测次数**: {len(state.bruteforce_results)}

"""
    vulnerable_count = sum(1 for r in state.bruteforce_results if r.get('result', {}).get('vulnerable'))
    if vulnerable_count > 0:
        report += f"""
::: warning
⚠️ 发现 **{vulnerable_count}** 个服务存在弱口令风险！
:::

"""
    for sr in state.bruteforce_results:
        r = sr.get('result', {})
        status = '🔴 存在弱口令' if r.get('vulnerable') else '🟢 未发现弱口令'
        report += f"""
**{sr.get('tool', 'N/A').upper()}** - `{sr.get('target', 'N/A')}:{sr.get('port', 'N/A')}`
- **状态**: {status}
- **时间**: {sr.get('time', 'N/A')}
"""
        if r.get('vulnerable_creds'):
            for cred in r.get('vulnerable_creds', []):
                report += f"- **弱口令**: `{cred.get('username')}` / `{cred.get('password')}`\n"

    report += """
---

## 七、蜜罐态势分析

"""
    for hr in state.honeypot_results:
        report += f"""
### 服务: {hr.get('service', 'N/A')} ({hr.get('count', 0)} 次攻击)
"""
        for rec in hr.get('records', [])[:10]:
            report += f"- **{rec.get('攻击IP', 'N/A')}** ({rec.get('来源地区', '未知')}) @ {rec.get('攻击时间', 'N/A')}\n"

    if state.ban_records:
        report += """
---

## 八、封禁记录

"""
        for br in state.ban_records:
            report += f"- 🛡️ 已封禁 `{br.get('ip', 'N/A')}` - 原因: {br.get('reason', 'N/A')} @ {br.get('time', 'N/A')}\n"

    report += f"""
---

## 九、修复建议

### 9.1 紧急修复（24小时内）
"""
    for f in critical:
        report += f"""
1. **修复 {f.get('ip', '')}:{f.get('port', '')} {f.get('type', '').upper()} 问题**
   - 立即修改弱口令为强密码（12位以上，包含大小写、数字、特殊字符）
   - 限制管理接口访问来源 IP
"""

    report += """
### 9.2 短期修复（1周内）
"""
    for f in high:
        report += f"""
1. **处理 {f.get('ip', '')}:{f.get('port', '')} 的漏洞**
   - {f.get('vuln', f.get('description', '及时更新补丁'))}
"""

    report += """
### 9.3 长期加固
1. 定期更换所有服务密码，启用双因素认证
2. 部署入侵检测系统（IDS）
3. 建立安全应急响应流程
4. 定期进行渗透测试

---

## 十、演练结论

本次安全演练共发现 **严重风险 {len(critical)} 项**，**高危问题 {len(high)} 项**，**中危问题 {len(medium)} 项**。

"""
    if critical:
        report += """
> ⚠️ **演练结论**: 发现严重安全问题，建议立即处理后再上线。
"""
    elif high:
        report += """
> 🟠 **演练结论**: 发现多项安全问题，建议尽快修复。
"""
    else:
        report += """
> 🟢 **演练结论**: 未发现严重安全问题，系统安全状况良好。
"""

    report += """
---

*本报告由 AI 攻防指挥官 自动生成 | 玄枢·AI安全系统*
"""
    return report


# ─── 系统提示词 ─────────────────────────────────────────────────────────────

DRILL_SYSTEM_PROMPT = """你叫**玄枢指挥官**，专业的网络安全 Agent。

## 工作流
1. drill_analyze_and_plan → 分析文档
2. drill_network_scan → 扫描网络
3. drill_bruteforce_ssh/rdp/mysql → 弱口令检测
4. drill_honeypot_audit → 蜜罐审计
5. drill_generate_report → 生成报告

## 决策规则
- 扫描发现端口 22 → drill_bruteforce_ssh
- 扫描发现端口 3389 → drill_bruteforce_rdp
- 扫描发现端口 3306 → drill_bruteforce_mysql
- 所有检测完成后 → drill_generate_report

现在开始执行演练。"""


# ─── 主执行器 ────────────────────────────────────────────────────────────────

def create_drill_stream(
    document_content: str,
    cfg: dict,
    state: DrillState | None = None,
) -> Generator[str, None, DrillState]:
    """
    创建演练 Agent 流式执行器（生成器）。

    参数:
        document_content: 演练文档内容
        cfg: 系统配置
        state: 演练状态（可外部传入，用于支持断点续传）

    返回:
        Generator[str, None, DrillState]: 生成 SSE 数据行的生成器
    """
    if state is None:
        state = DrillState()
    state.document_content = document_content

    tools = get_drill_tool_definitions()
    history: list[dict] = []

    # 注入系统提示
    history.append({'role': 'system', 'content': DRILL_SYSTEM_PROMPT})

    # 注入文档内容作为用户消息（触发 Agent 启动）
    history.append({
        'role': 'user',
        'content': (
            f'请开始执行以下安全演练任务：\n\n'
            f'## 安全演练文档内容\n\n{document_content}\n\n'
            f'请按以下步骤执行：\n'
            f'1. 分析文档内容，提取目标网络和演练要求\n'
            f'2. 制定行动计划\n'
            f'3. 按计划执行各项检测\n'
            f'4. 生成完整演练报告\n\n'
            f'开始执行！'
        )
    })

    # ─── Agent 主循环 ────────────────────────────────────────────────────────
    while state.step_count < state.max_steps and not state.is_complete:
        state.step_count += 1
        unified_log('DrillExecutor', f'=== Agent Step {state.step_count}/{state.max_steps} ===', 'INFO')

        # 发送步骤开始信息
        yield json.dumps({
            'content': f'🤔 AI 正在分析并决策下一步行动... (第 {state.step_count} 步)'
        }) + '\n\n'

        # LLM 决策：是否调用工具
        tool_calls = []
        text_chunks = []

        for chunk, error, tool_call in stream_openai_chat_with_tools(
            build_openai_messages(history), cfg, tools=tools
        ):
            if error:
                yield json.dumps({'error': error}) + '\n\n'
                return

            if chunk:
                text_chunks.append(chunk)
                yield json.dumps({'content': chunk}) + '\n\n'

            if tool_call:
                tool_calls.append(tool_call)

        # 合并文本响应
        response_text = ''.join(text_chunks)

        # ─── 如果没有工具调用，结束循环 ─────────────────────────────────────
        if not tool_calls:
            # 只有在无工具调用时才追加纯文本消息，避免与后面带 tool_calls 的消息重复
            if response_text:
                history.append({'role': 'assistant', 'content': response_text})
            unified_log('DrillExecutor', 'AI 无更多工具调用，演练结束', 'INFO')
            break

        # ─── 执行工具调用 ─────────────────────────────────────────────────
        for tc in tool_calls:
            tool_name = tc['name']
            tool_args = tc['arguments']

            unified_log('DrillExecutor', f'🤖 执行工具: {tool_name} | 参数: {json.dumps(tool_args, ensure_ascii=False)[:200]}', 'INFO')

            # 发送工具调用开始
            yield json.dumps({
                'tool_call': {
                    'id': tc['id'],
                    'name': tool_name,
                    'arguments': tool_args,
                }
            }) + '\n\n'

            # 保存 AI 的 tool_call 消息（仅在第一个工具时附带 content，避免重复追加）
            if tc is tool_calls[0]:
                history.append({
                    'role': 'assistant',
                    'content': response_text if response_text else None,
                    'tool_calls': [{
                        'id': t['id'],
                        'type': 'function',
                        'function': {
                            'name': t['name'],
                            'arguments': json.dumps(t['arguments'], ensure_ascii=False),
                        }
                    } for t in tool_calls]
                })

            # 执行工具
            tool_result = _execute_drill_tool(tool_name, tool_args, cfg, state)

            # 序列化结果
            if isinstance(tool_result, dict):
                result_str = json.dumps(tool_result, ensure_ascii=False)
            else:
                result_str = str(tool_result)

            # 发送给前端（截断过长的结果）
            display_result = result_str[:2000] + '...' if len(result_str) > 2000 else result_str
            yield json.dumps({
                'tool_result': {
                    'id': tc['id'],
                    'name': tool_name,
                    'result': display_result,
                    'full_result': result_str,
                }
            }) + '\n\n'

            # 保存工具结果到历史
            history.append({
                'role': 'tool',
                'tool_call_id': tc['id'],
                'content': result_str,
            })

            # 检查是否已生成报告（演练完成）
            if tool_name == 'drill_generate_report' and tool_result.get('ok'):
                state.is_complete = True
                yield json.dumps({
                    'content': f'✅ 演练完成，共发现 {len(state.findings)} 个安全问题'
                }) + '\n\n'
                break

    # ─── 循环结束 ────────────────────────────────────────────────────────────
    if not state.is_complete and state.step_count >= state.max_steps:
        yield json.dumps({
            'content': '⚠️ 演练达到最大步数限制，自动结束'
        }) + '\n\n'

    unified_log('DrillExecutor', f'演练完成 | 总步骤: {state.step_count} | 发现: {len(state.findings)}项 | 截图: {len(state.screenshot_results)}张', 'INFO')

    return state
