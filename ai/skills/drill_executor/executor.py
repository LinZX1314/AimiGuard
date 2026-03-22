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
    """
    执行演练专用工具的核心逻辑
    包含 drill_* 前缀的工具和现有系统工具的桥接
    """
    import threading
    from datetime import datetime

    # ── drill_analyze_document ───────────────────────────────────────────────
    if tool_name == 'drill_analyze_document':
        # 文档分析不需要真正执行，由 AI 直接处理
        return {'ok': True, 'message': '请直接分析以下文档内容，提取目标网络、扫描范围和演练要求。'}

    # ── drill_plan_actions ───────────────────────────────────────────────────
    if tool_name == 'drill_plan_actions':
        return {'ok': True, 'message': '请基于分析结果制定行动计划。'}

    # ── drill_network_scan ───────────────────────────────────────────────────
    if tool_name == 'drill_network_scan':
        target = arguments.get('target', '')
        ports = arguments.get('ports', '21,22,23,80,81,135,139,443,445,1433,3306,5432,6379,8080,8443')
        threads = arguments.get('threads', 6000)

        if not target:
            return {'ok': False, 'error': '缺少扫描目标'}

        state.target_network = target

        # 调用已有的 fscan 工具
        result_str = execute_existing_tool('run_fscan', {
            'target': target,
            'port': ports,
            'threads': threads,
        }, cfg)

        result = _safe_parse_json(result_str)

        if result.get('ok'):
            state.add_result('scan', {
                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'target': target,
                'result': result,
            })

            # 智能分析：提取可疑服务
            hosts = result.get('主机列表', [])
            vuln_list = result.get('漏洞列表', [])
            findings = []
            for h in hosts:
                ports_str = h.get('ports', '')
                if ports_str:
                    findings.append({
                        'ip': h.get('ip'),
                        'ports': ports_str,
                        'type': 'open_ports',
                        'severity': 'info',
                    })
            for v in vuln_list:
                findings.append({
                    'ip': v.get('ip'),
                    'port': v.get('port'),
                    'service': v.get('service'),
                    'vuln': v.get('vuln'),
                    'type': 'vulnerability',
                    'severity': 'high',
                })
            for f in findings:
                state.add_result('finding', f)

            host_count = result.get('发现主机', 0)
            result['analysis'] = f'发现 {host_count} 台存活主机，已记录到演练状态'

        return result

    # ── drill_web_screenshot ─────────────────────────────────────────────────
    if tool_name == 'drill_web_screenshot':
        url = arguments.get('url', '')
        ip = arguments.get('ip', '')
        port = arguments.get('port', 80)

        if not url or not ip:
            return {'ok': False, 'error': '缺少 url 或 ip 参数'}

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
            state.add_result('finding', {
                'ip': ip,
                'port': port,
                'url': url,
                'type': 'web_service',
                'severity': 'info',
                'description': '发现 Web 服务，已采集截图',
            })

        return result

    # ── 弱口令检测 ──────────────────────────────────────────────────────────
    if tool_name in ('drill_bruteforce_ssh', 'drill_bruteforce_rdp', 'drill_bruteforce_mysql'):
        target_ip = arguments.get('target_ip', '')
        port = arguments.get('port', 22 if 'ssh' in tool_name else (3389 if 'rdp' in tool_name else 3306))

        if not target_ip:
            return {'ok': False, 'error': '缺少目标IP'}

        # 调用 bruteforce 模块
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

        result_str = execute_existing_tool('get_honeypot_logs', {
            'service_name': service_name,
            'limit': limit,
        }, cfg)

        result = _safe_parse_json(result_str)

        if result.get('ok'):
            state.add_result('honeypot', {
                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'service': service_name or '全部',
                'count': result.get('总数', 0),
                'records': result.get('攻击记录', [])[:10],
            })

            records = result.get('攻击记录', [])
            for rec in records:
                state.add_result('finding', {
                    'ip': rec.get('攻击IP'),
                    'service': rec.get('服务'),
                    'type': 'honeypot_attack',
                    'severity': 'medium',
                    'description': f"蜜罐遭受来自 {rec.get('攻击IP')} 的攻击",
                    'location': rec.get('来源地区'),
                })

        return result

    if tool_name == 'drill_honeypot_stats':
        result_str = execute_existing_tool('get_honeypot_stats', {}, cfg)

        result = _safe_parse_json(result_str)

        return result

    # ── 封禁IP ───────────────────────────────────────────────────────────────
    if tool_name == 'drill_ban_ip':
        target_ip = arguments.get('target_ip', '')
        reason = arguments.get('reason', '演练中发现的可疑IP')

        if not target_ip:
            return {'ok': False, 'error': '缺少目标IP'}

        result_str = execute_existing_tool('switch_acl_config', {
            'action': 'ban',
            'target_ip': target_ip,
            'description': reason,
        }, cfg)

        result = _safe_parse_json(result_str)

        if result.get('ok'):
            state.add_result('ban', {
                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'ip': target_ip,
                'reason': reason,
                'result': result,
            })

        return result

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

    # ── 状态查询 ────────────────────────────────────────────────────────────
    if tool_name == 'drill_get_status':
        return {
            'ok': True,
            **state.to_dict(),
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

    report += """
---

## 五、Web 截图采集

**截图数量**: {len(state.screenshot_results)} 张

| # | IP | 端口 | URL | 采集时间 |
|---|----|------|-----|----------|
""".format(len=len(state.screenshot_results))

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

DRILL_SYSTEM_PROMPT = """你叫**玄枢指挥官**，是一个专业的网络安全 Agent，专精安全演练与渗透测试。

## 核心能力
你具备调用多种安全工具的能力，在安全演练中扮演"智能渗透测试 Agent"的角色。

## 你的工具集
- `drill_analyze_document`: 分析安全演练文档
- `drill_plan_actions`: 制定演练行动计划
- `drill_network_scan`: 网络资产探测与端口扫描
- `drill_web_screenshot`: Web 服务截图采集
- `drill_bruteforce_ssh`: SSH 弱口令检测
- `drill_bruteforce_rdp`: RDP 弱口令检测
- `drill_bruteforce_mysql`: MySQL 弱口令检测
- `drill_honeypot_audit`: 蜜罐日志审计
- `drill_honeypot_stats`: 蜜罐态势统计
- `drill_ban_ip`: 封禁恶意IP
- `drill_generate_report`: 生成演练报告
- `drill_get_status`: 查询当前演练进度

## 演练工作流（Agent 循环）

### 第一步：文档分析
当用户提供演练文档后：
1. 先用 `drill_analyze_document` 分析文档，提取：
   - 目标网络范围（IP/网段）
   - 重点检查的服务（Web、SSH、数据库等）
   - 演练的具体要求

### 第二步：制定计划
使用 `drill_plan_actions` 制定行动计划，包括：
- 扫描阶段：先 Ping 探测存活主机，再端口扫描
- 服务枚举：重点端口的详细探测
- 漏洞检测：弱口令测试、Web 截图等
- 分析报告：汇总发现

### 第三步：执行循环
按照计划逐步执行，每一步：
1. AI 决策：决定调用哪个工具
2. 工具执行：获取实时结果
3. 结果分析：判断是否需要下一步
4. 继续循环直到任务完成

### 第四步：生成报告
所有演练步骤完成后：
1. 调用 `drill_get_status` 汇总所有结果
2. 调用 `drill_generate_report` 生成完整报告
3. 用中文向用户展示报告摘要

## 重要原则
1. **循序渐进**：先扫描网络，再深入服务，最后弱口令检测
2. **实事求是**：发现的漏洞如实记录，不夸大不缩小
3. **自动决策**：根据扫描结果自动决定下一步（如发现SSH服务→尝试弱口令）
4. **证据保存**：截图和扫描结果自动保存
5. **防御响应**：发现攻击者IP时，主动封禁

## Agent 循环终止条件
- 已调用 `drill_generate_report` 生成了报告
- 已执行超过 30 步（防止无限循环）
- 所有计划步骤已完成

## 报告要求
生成中文报告，包含：
1. 执行摘要（时间、步骤、目标）
2. 文档分析结果
3. 发现的安全问题（按严重级别分类）
4. 扫描结果详情
5. Web 截图证据
6. 弱口令检测结果
7. 蜜罐审计结果
8. 修复建议

现在，请分析用户提供的演练文档，开始执行安全演练任务。
"""


# ─── 主执行器 ────────────────────────────────────────────────────────────────

def create_drill_stream(
    document_content: str,
    cfg: dict,
    yield_func: callable,
    state: DrillState | None = None,
) -> DrillState:
    """
    创建演练 Agent 流式执行器。

    参数:
        document_content: 演练文档内容
        cfg: 系统配置
        yield_func: 用于向客户端发送 SSE 数据的回调函数，签名为 yield_func(data: dict)
        state: 演练状态（可外部传入，用于支持断点续传）

    返回:
        DrillState: 最终的演练状态
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
        yield_func({
            'drill_step': {
                'step': state.step_count,
                'max_steps': state.max_steps,
                'status': 'thinking',
                'message': f'🧠 AI 正在分析并决策下一步行动... (第 {state.step_count} 步)',
            }
        })

        # LLM 决策：是否调用工具
        tool_calls = []
        text_chunks = []

        for chunk, error, tool_call in stream_openai_chat_with_tools(
            build_openai_messages(history), cfg, tools=tools
        ):
            if error:
                yield_func({'error': error})
                return state

            if chunk:
                text_chunks.append(chunk)
                yield_func({'content': chunk, 'drill_step': {
                    'step': state.step_count,
                    'status': 'thinking',
                }})

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
            yield_func({
                'tool_call': {
                    'id': tc['id'],
                    'name': tool_name,
                    'arguments': tool_args,
                    'status': 'executing',
                    'drill_step': {
                        'step': state.step_count,
                        'status': 'executing',
                        'tool': tool_name,
                    },
                }
            })

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
            yield_func({
                'tool_result': {
                    'id': tc['id'],
                    'name': tool_name,
                    'result': display_result,
                    'status': 'done',
                    'full_result': result_str,
                    'drill_step': {
                        'step': state.step_count,
                        'status': 'done',
                        'tool': tool_name,
                    },
                }
            })

            # 保存工具结果到历史
            history.append({
                'role': 'tool',
                'tool_call_id': tc['id'],
                'content': result_str,
            })

            # 检查是否已生成报告（演练完成）
            if tool_name == 'drill_generate_report' and tool_result.get('ok'):
                state.is_complete = True
                yield_func({
                    'drill_complete': {
                        'report': tool_result.get('report', ''),
                        'summary': state.get_exec_summary(),
                        'findings_count': len(state.findings),
                    }
                })
                break

    # ─── 循环结束 ────────────────────────────────────────────────────────────
    if not state.is_complete and state.step_count >= state.max_steps:
        yield_func({
            'drill_warning': '演练达到最大步数限制，自动结束',
        })

    unified_log('DrillExecutor', f'演练完成 | 总步骤: {state.step_count} | 发现: {len(state.findings)}项 | 截图: {len(state.screenshot_results)}张', 'INFO')

    return state
