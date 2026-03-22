# 玄枢·AI 攻防指挥官 — 演练（Drill）系统设计文档

---

## 一、整体架构

```
用户上传演练文档
        │
        ▼
┌─────────────────────────────┐
│   ai_chat_stream (Flask)    │
│  检测 drill_mode / drill_   │
│  工具调用 → 创建 DrillState │
└──────────┬──────────────────┘
           │ 传入 drill_state
           ▼
┌─────────────────────────────┐
│   _run_agent_loop           │
│  Agent 多轮工具调用循环      │
│  最大 30 步                 │
│  step_count → drill_state   │
└──────────┬──────────────────┘
           │
           ├─ 工具执行 → 结果存入 drill_state
           │
           ▼
    报告生成时机
    ┌─────────────────────────────────────────────┐
    │ ① AI 无工具调用自然结束（纯文本回复）       │
    │ ② AI 调用 drill_generate_report 工具        │
    │ ③ Agent 循环 30 步自然退出（兜底）         │
    └─────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────┐
    │ call_openai_chat_    │
    │ completion (单次)     │  ← 超时 120s，超时 → Markdown fallback
    │ 生成 HTML 报告        │
    └──────────┬───────────┘
               │
               ▼
    SSE: { drill_complete: { report, summary, findings_count, is_html } }
               │
               ▼
    前端 AiChatView.vue
    右侧「演练报告预览」侧边栏
    HTML 报告 → <iframe srcdoc>
    Markdown → <div prose>
```

---

## 二、进入演练模式的两种方式

| 方式 | 条件 | 说明 |
|------|------|------|
| **显式演练** | `body.drill_mode = true` 或消息含 `【演练文档】` | 用户主动上传文档 |
| **隐式演练** | 普通对话中 AI 首次调用 `drill_*` 工具 | AI 智能触发，后端自动创建 DrillState |

---

## 三、DrillState 数据结构

位置：`ai/skills/drill_executor/executor.py` 第 40 行

```python
class DrillState:
    document_content: str = ''          # 原始文档内容
    document_summary: str = ''           # AI 分析后的摘要
    action_plan: str = ''              # 执行计划
    scan_results: list[dict] = []      # 扫描结果
    screenshot_results: list[dict] = []# 截图结果
    bruteforce_results: list[dict] = []# 弱口令结果
    honeypot_results: list[dict] = []  # 蜜罐日志
    ban_records: list[dict] = []        # 封禁记录
    findings: list[dict] = []          # 发现的问题（severity: critical/high/medium/info）
    report_content: str = ''            # 最终报告
    step_count: int = 0                # 已执行步骤数
    max_steps: int = 30                # 最大循环次数
    is_complete: bool = False          # 是否已完成
    target_network: str = ''           # 目标网络范围
    history: list[dict] = []           # Agent 对话历史
    _start_time: datetime              # 演练开始时间

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
```

---

## 四、工具清单（共 11 个）

### 4.1 文档与规划

#### drill_analyze_document
- **功能**：解析演练文档，提取目标网络、扫描范围、服务类型
- **参数**：
  - `document_content` (string, 可选，后端自动从 drill_state 注入)

#### drill_plan_actions
- **功能**：制定分阶段行动计划（5 阶段）
- **参数**：
  - `analysis_result` (string, required) — drill_analyze_document 的结果

---

### 4.2 网络扫描

#### drill_network_scan
- **功能**：资产发现 + 端口扫描（调用 fscan）
- **参数**：
  - `target` (string, **必填**) — IP / 网段(CIDR) / 多IP逗号分隔
  - `ports` (string, 默认 `21,22,23,80,81,135,139,443,445,1433,3306,5432,6379,8080,8443`)
  - `threads` (integer, 默认 6000)
- **drill_state 写入**：`scan` 结果 + `finding`（主机列表 + 漏洞列表）

#### drill_web_screenshot
- **功能**：Web 页面截图
- **参数**：
  - `url` (string, **必填**) — 完整 URL
  - `ip` (string, **必填**) — 目标 IP
  - `port` (integer, **必填**)
- **drill_state 写入**：`screenshot` 结果 + `finding`（web_service）

---

### 4.3 弱口令检测

#### drill_bruteforce_ssh
- **功能**：SSH 弱口令检测（端口 22）
- **参数**：
  - `target_ip` (string, **必填**)
  - `port` (integer, 默认 22)

#### drill_bruteforce_rdp
- **功能**：RDP 弱口令检测（端口 3389）
- **参数**：
  - `target_ip` (string, **必填**)
  - `port` (integer, 默认 3389)

#### drill_bruteforce_mysql
- **功能**：MySQL 弱口令检测（端口 3306）
- **参数**：
  - `target_ip` (string, **必填**)
  - `port` (integer, 默认 3306)
- **drill_state 写入**：`bruteforce` 结果 + `finding`（若发现弱口令，severity=critical）

---

### 4.4 蜜罐审计

#### drill_honeypot_audit
- **功能**：查询 HFish 蜜罐攻击日志
- **参数**：
  - `service_name` (string, 可选) — 服务筛选，如 ssh/http/mysql/redis
  - `limit` (integer, 默认 50)
- **drill_state 写入**：`honeypot` 结果（service 字段取自攻击记录，而非请求参数）

#### drill_honeypot_stats
- **功能**：获取 HFish 整体态势统计
- **参数**：无
- **返回**：总攻击次数、热门服务 Top10、攻击来源 Top10、7天趋势

---

### 4.5 封禁工具

#### drill_ban_ip
- **功能**：将恶意 IP 添加到交换机 ACL 封禁列表
- **参数**：
  - `target_ip` (string, **必填**)
  - `reason` (string, 可选，默认"演练中发现的可疑IP")
- **drill_state 写入**：`ban` 记录

---

### 4.6 状态与系统

#### drill_get_status
- **功能**：查询当前演练进度和已收集的证据
- **参数**：无
- **返回**：drill_state 完整 to_dict()

#### drill_get_local_ip
- **功能**：获取本机 IP 信息（**纯本地，不联网**）
- **参数**：无
- **返回**：
  ```json
  {
    "ok": true,
    "hostname": "AimiGuard-Server",
    "local_ip": "192.168.0.5",
    "all_ips": ["192.168.0.5"],
    "network": "192.168.0.0/24"
  }
  ```

---

### 4.7 报告生成

#### drill_generate_report
- **功能**：生成完整演练报告（显式调用）
- **参数**：
  - `exec_summary` (string, required)
  - `findings` (string, 可选)
  - `scan_results` (string, 可选)
  - `screenshot_count` (integer, 可选)
  - `bruteforce_results` (string, 可选)
  - `honeypot_summary` (string, 可选)
- **注意**：此工具生成 **Markdown 报告**，直接返回给前端；自动报告生成使用 AI 调用生成 **HTML 报告**

---

## 五、系统提示词

### 5.1 ai.py 中定义的演练系统提示词（主用）

> 注入位置：`web/api/ai.py` 第 300-331 行
> 触发条件：显式演练模式（`is_drill_mode=True`）

```
你叫玄枢指挥官，是一个专业的网络安全 AI 攻防 Agent。
你的专有能力是：分析安全演练文档 → 智能决策执行工具 → 生成完整演练报告。

## 你的可用工具（必须使用 drill_ 前缀的工具）
- drill_analyze_document: 分析演练文档，提取目标网络、扫描范围
- drill_plan_actions: 制定分阶段行动计划
- drill_network_scan: 对目标网络进行资产探测和端口扫描
- drill_web_screenshot: 对 Web 服务采集截图
- drill_bruteforce_ssh/rdp/mysql: 弱口令检测
- drill_honeypot_audit: 查询蜜罐攻击日志
- drill_honeypot_stats: 获取蜜罐态势统计
- drill_ban_ip: 封禁恶意 IP
- drill_generate_report: 生成完整演练报告（必须最后调用）
- drill_get_status: 查询当前演练进度
- drill_get_local_ip: 查询本机IP地址

## 正确的工作流
1. 立即调用 drill_analyze_document 分析演练文档
2. 调用 drill_plan_actions 制定行动计划
3. 按计划执行：先网络扫描 → 再服务枚举 → 再漏洞检测
4. 发现 Web 服务立即截图
5. 发现 SSH/RDP/MySQL 服务立即尝试弱口令
6. 定期查询蜜罐日志，发现攻击者立即封禁
7. 所有步骤完成后调用 drill_generate_report
8. 最多执行 30 步，遇到 drill_generate_report 立即结束

## 重要原则
- 发现漏洞必须记录（severity: critical/high/medium/info）
- 弱口令发现是 critical 级别，必须在 finding 中记录
- 扫描结果中的可疑 IP 要主动尝试封禁
- 报告要用中文，包含所有发现的问题

## 背景信息
{_get_system_context()}

现在请开始分析演练文档并执行安全演练！
```

其中 `_get_system_context()` 返回内容示例：
```
### 当前系统态势摘要 ###
- DHCP在线设备数: 12
- 24小时内遭受攻击次数: 47

### 蜜罐态势统计 ###
- 总攻击次数: 312
- 热门攻击服务(Top5): SSH(89次), HTTP(67次), MySQL(43次)
- 主要攻击来源(Top5): 192.168.1.100(23次), 10.0.0.55(18次)
```

---

### 5.2 executor.py 中的 DRILL_SYSTEM_PROMPT

> 位置：`ai/skills/drill_executor/executor.py` 第 584-656 行
> 用途：独立 executor 模式（create_drill_stream）

```
你叫**玄枢指挥官**，是一个专业的网络安全 Agent，专精安全演练与渗透测试。

## 核心能力
你具备调用多种安全工具的能力，在安全演练中扮演"智能渗透测试 Agent"的角色。

## 你的工具集
- drill_analyze_document: 分析安全演练文档
- drill_plan_actions: 制定演练行动计划
- drill_network_scan: 网络资产探测与端口扫描
- drill_web_screenshot: Web 服务截图采集
- drill_bruteforce_ssh: SSH 弱口令检测
- drill_bruteforce_rdp: RDP 弱口令检测
- drill_bruteforce_mysql: MySQL 弱口令检测
- drill_honeypot_audit: 蜜罐日志审计
- drill_honeypot_stats: 蜜罐态势统计
- drill_ban_ip: 封禁恶意IP
- drill_generate_report: 生成演练报告
- drill_get_status: 查询当前演练进度

## 演练工作流（Agent 循环）

### 第一步：文档分析
当用户提供演练文档后：
1. 先用 drill_analyze_document 分析文档，提取：
   - 目标网络范围（IP/网段）
   - 重点检查的服务（Web、SSH、数据库等）
   - 演练的具体要求

### 第二步：制定计划
使用 drill_plan_actions 制定行动计划，包括：
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
1. 调用 drill_get_status 汇总所有结果
2. 调用 drill_generate_report 生成完整报告
3. 用中文向用户展示报告摘要

## 重要原则
1. 循序渐进：先扫描网络，再深入服务，最后弱口令检测
2. 实事求是：发现的漏洞如实记录，不夸大不缩小
3. 自动决策：根据扫描结果自动决定下一步（如发现SSH服务→尝试弱口令）
4. 证据保存：截图和扫描结果自动保存
5. 防御响应：发现攻击者IP时，主动封禁

## Agent 循环终止条件
- 已调用 drill_generate_report 生成了报告
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
```

---

## 六、报告生成流程

### 6.1 触发时机（三选一）

| 触发条件 | 报告格式 | 生成方式 |
|---------|---------|---------|
| AI 无工具调用自然结束 | **HTML**（ECharts 图表） | AI 单次调用 `_build_report_prompt` |
| AI 调用 `drill_generate_report` | **Markdown** | 工具返回本地 `_generate_drill_report()` |
| Agent 循环 30 步退出（兜底） | **HTML**（ECharts 图表） | AI 单次调用 `_build_report_prompt` |

### 6.2 AI 报告生成 Prompt（`_build_report_prompt`）

位置：`web/api/ai.py` 第 864-987 行

**输入数据**（JSON 上下文）：
```json
{
  "演练开始时间": "2026-03-22 15:30:00",
  "运行时长": "2分30秒",
  "目标网络": "192.168.0.0/24",
  "执行步骤": 8,
  "扫描结果": [...],
  "弱口令检测结果": [...],
  "蜜罐审计结果": [...],
  "封禁记录": [...],
  "发现的问题": [...],
  "截图记录": [...],
  "蜜罐总攻击次数": 312,
  "蜜罐服务统计": [...],
  "蜜罐攻击来源Top10": [...],
  "蜜罐7天趋势": [...],
  "网络扫描次数": 3,
  "发现主机数": 12,
  "弱口令风险数": 2,
  "蜜罐审计次数": 2,
  "封禁IP数": 5,
  "安全问题数": 8
}
```

**核心要求**：
1. 输出完整的单个 HTML 页面（含 `<!DOCTYPE html>` 和 `<html>`）
2. 使用 **ECharts**（CDN: `https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js`）
3. 使用 **Bootstrap 5**（CDN）响应式布局
4. **暗黑军事风格**：深色背景 `#0a0e14`，亮色文字 `#00ff88 / #ff6b6b / #ffd93d`
5. 所有中文内容

**必须包含的板块**：
1. 报告头部（标题、副标题、风险等级标签）
2. 执行摘要 KPI 卡片（6 项指标）
3. ECharts 图表区（至少 3 个）：
   - 图表1：`7天攻击趋势`（折线图，数据：蜜罐7天趋势）
   - 图表2：`攻击服务分布`（饼图，数据：蜜罐服务统计）
   - 图表3：`Top 10 攻击来源`（水平柱状图，数据：蜜罐攻击来源Top10）
4. 网络扫描详情（目标、发现主机列表）
5. 弱口令检测结果（红色高亮发现的弱口令）
6. 蜜罐审计记录（攻击记录表格）
7. 封禁IP列表
8. 安全问题汇总表（按 severity 分组）
9. 修复建议
10. 页脚

**超时处理**：AI 调用超时 120s，超时后 fallback 到本地 `_generate_drill_report()` 生成 Markdown 报告。

---

## 七、前端展示

### 7.1 报告渲染逻辑

位置：`web/vue/src/views/AiChatView.vue`

- **HTML 报告**（`drillReportHtml = true`）：`<iframe :srcdoc="drillReport" sandbox="allow-scripts">`
- **Markdown 报告**（`drillReportHtml = false`）：`<div class="prose prose-invert ...">`

### 7.2 关键状态变量

```javascript
const drillMode = ref(false)        // 演练模式激活
const drillPanelOpen = ref(false)   // 演练面板展开
const drillReport = ref('')         // 报告内容
const drillReportHtml = ref(false)   // 是否为 HTML 格式
const drillSummary = ref('')        // 报告摘要
const drillFindingCount = ref(0)    // 发现数量
const drillHostsFound = ref(0)      // 发现主机数
const drillScreenshotsTaken = ref(0) // 截图数量
const drillElapsed = ref(0)         // 已用时间
const drillStep = ref(0)            // 当前步数
const drillMaxStep = ref(30)       // 最大步数
const drillProgress = ref(0)        // 进度百分比
```

### 7.3 演练界面 UI 布局

```
┌──────────────────────────────────────────────────────────────────┐
│  顶部导航栏                                                         │
├────────────┬─────────────────────────────────────┬────────────────┤
│            │  演练 Agent Loop 终端 (drillLog)    │                │
│  左侧导航   │  - 欢迎横幅                        │  右侧边栏        │
│            │  - 工具调用日志                      │  (有报告时)      │
│  会话记录   │    [THINKING] AI 决策中             │  演练报告预览    │
│            │    [TOOL_CALL] drill_network_scan   │  - 报告头部      │
│            │    [TOOL_RESULT] 发现 5 台主机       │  - iframe/div   │
│            │    ...                               │  - 新窗口按钮    │
│            │                                      │                │
│            │  AI 正在执行中...                    │  (无报告时)     │
│            │                                      │  实时统计卡片    │
│            │                                      │  - 步数/主机    │
│            │                                      │  - 截图/安全问题 │
│            │                                      │  - 已用时间      │
└────────────┴─────────────────────────────────────┴────────────────┘
```

---

## 八、工具执行处理器

位置：`web/api/ai.py` `_execute_tool()` 函数（行 416-597）

每个工具对应的实际执行逻辑：

| 工具 | 实际调用 | drill_state 写入 |
|------|---------|----------------|
| `drill_analyze_document` | 内联解析（正则提取 IP/服务） | `document_content`, `document_summary` |
| `drill_plan_actions` | 内联生成 5 阶段计划 | `action_plan` |
| `drill_network_scan` | `execute_tool('run_fscan', {...})` | `scan` + `finding`(主机+漏洞) |
| `drill_web_screenshot` | `execute_tool('take_screenshot', {...})` | `screenshot` |
| `drill_bruteforce_ssh/rdp/mysql` | `drill_bruteforce()` (bruteforce.py) | `bruteforce` + `finding`(若发现) |
| `drill_honeypot_audit` | `execute_tool('get_honeypot_logs', {...})` | `honeypot` |
| `drill_honeypot_stats` | `execute_tool('get_honeypot_stats', {...})` | 无 |
| `drill_ban_ip` | `execute_tool('switch_acl_config', {...})` | `ban` |
| `drill_generate_report` | `_generate_drill_report(state)` | `report_content`, `is_complete=True` |
| `drill_get_status` | 内联返回 `drill_state.to_dict()` | 无 |
| `drill_get_local_ip` | 纯本地（socket + psutil） | 无 |

---

## 九、SSE 事件流

演练执行过程中后端 yield 的所有 SSE 事件类型：

| 事件类型 | 字段 | 说明 |
|---------|------|------|
| `session_id` | `session_id` | 新建会话时返回 |
| `drill_mode` | `true` | 演练模式启动 |
| `drill_step` | `{step, status, message}` | 每步开始时发送，status: thinking |
| `content` | `text` | AI 文本流输出 |
| `tool_call` | `{id, name, arguments, status}` | 工具调用开始 |
| `tool_result` | `{id, tool_call_id, name, result, full_result, status}` | 工具执行结果 |
| `drill_complete` | `{report, summary, findings_count, auto_generated, is_html}` | 演练完成（报告生成） |
| `done` | `{session_id}` | 流结束 |

---

## 十、关键代码路径

```
web/api/ai.py
├── ai_chat_stream()         # 入口，检测 drill_mode
├── _run_agent_loop()        # Agent 多轮循环（generator）
│   ├── _execute_tool()     # 工具执行器
│   │   ├── drill_analyze_document
│   │   ├── drill_plan_actions
│   │   ├── drill_network_scan       → execute_tool('run_fscan')
│   │   ├── drill_web_screenshot     → execute_tool('take_screenshot')
│   │   ├── drill_bruteforce_*     → drill_bruteforce()
│   │   ├── drill_honeypot_audit   → execute_tool('get_honeypot_logs')
│   │   ├── drill_honeypot_stats    → execute_tool('get_honeypot_stats')
│   │   ├── drill_ban_ip           → execute_tool('switch_acl_config')
│   │   ├── drill_generate_report   → _generate_drill_report()
│   │   ├── drill_get_status
│   │   └── drill_get_local_ip
│   ├── call_openai_chat_completion()  # 生成 HTML 报告（单次调用）
│   ├── _build_report_prompt()          # AI 报告 Prompt
│   └── _generate_drill_report()        # 本地 Markdown 报告（fallback）
│
├── _normalize_uploaded_files()  # 文件上传处理（支持图片 base64）
└── _get_system_context()        # 蜜罐态势摘要（注入系统提示词）

ai/skills/drill_executor/executor.py
├── DrillState              # 演练状态类
├── DRILL_SYSTEM_PROMPT    # 独立 executor 用的系统提示词
└── create_drill_stream()   # 独立演练流式执行器

ai/skills/drill_executor/drill_tools.py
└── get_drill_tool_definitions()  # 11 个工具定义（Tool Calling schema）

ai/skills/drill_executor/bruteforce.py
└── run_bruteforce()  # 弱口令检测（fscan + Python 原生 fallback）

web/vue/src/views/AiChatView.vue
├── drillMode / drillReport / drillReportHtml     # 核心状态
├── send()                    # 发送消息，触发 SSE 流
├── formatToolResult()        # 工具结果格式化
├── openReportWindow()        # 新窗口打开报告
└── drillAdd()               # 添加演练日志条目
```
