# 🔥 AimiGuard (智能安全与资产监控平台)

**AimiGuard** 是一个基于全新 MVC 架构重构的现代原生主机安全、资产发现与威胁监控平台。它将 **Nmap (网络发现与漏洞扫描)** 与 **HFish (蜜罐攻击日志)** 深度整合，并通过一套基于 **Vue 3 + Vuetify + Vite** 构建的全新响应式前端界面，以及完整的 **JWT 认证 RESTful API**，为你提供企业级的内部安全资产大屏展示与防御管理。

---v

## ✨ 核心功能亮点

1. **自动资产测绘与 OS 标签**：自动将 Nmap 扫描到的主机操作系统指纹标准化（`windows`、`linux`、`bsd`），方便分类管理。
2. **智能化漏洞探测 (NSE)**：根据 OS 标签自动挂载专属 Nmap Vulnerability 探测脚本，精准覆盖 MS17-010 等主流漏洞。
3. **威胁情报中枢 (HFish)**：图表化分析蜜罐攻击行为日志，实时掌握内网横向移动痕迹。
4. **全自动后台轮询**：扫描与蜜罐同步任务均在守护线程中静默运行，间隔可配置。
5. **🤖 AI 驱动的"对话即扫描"**：集成大语言模型（LLM），支持自然语言指令触发扫描与报告生成。
6. **JWT 鉴权 API**：全新 `/api/v1/` 路由体系，Bearer Token 保护，前后端彻底分离。

---

## 📂 目录结构

```
AimiGuard/
├── config.json              # 核心配置文件 (服务端口、Nmap、HFish、AI、交换机等)
├── README.md
├── main.py                  # 项目启动入口
├── database/                # 数据层 [Model]
│   ├── db.py                # SQLite 连接与建表初始化
│   ├── models.py            # 面向对象查询/写入接口
│   └── aimiguard.db         # (运行后自动生成) 统一数据库
├── plugin/                  # 扫描与蜜罐插件
│   ├── attack_log_sync.py   # HFish API 对接与日志格式化
│   ├── ai_tools.py          # AI 攻击日志分析与自动封禁
│   └── network_scan.py      # 主机探活、端口扫描、NSE 漏洞执行
└── web/                     # Web 层 [Controller + View]
    ├── flask_app.py         # Flask 主入口，注册 Blueprint，启动后台线程
    ├── api/                 # ★ RESTful API Blueprint (/api/v1)
    ├── ai_runtime/          # AI tools/tool_calls 通用运行时
    ├── vue/                 # ★ Vue 3 + Vuetify 3 + Vite 6 前端源码
    │   ├── package.json
    │   ├── vite.config.ts   # 开发端口 3001，代理 /api → :5000，ECharts 分包
    │   └── src/
    │       ├── views/       # 各功能页面 Vue 组件
    │       ├── stores/      # Pinia 状态管理
    │       └── api/         # 前端 Axios API 封装层
    ├── static/
    │   └── vue-dist/        # pnpm build 后的生产构建产物 (Flask 伺服于 /)
```

---

## ⚙️ 快速开始

### 环境要求

| 依赖 | 版本要求 | 说明 |
| :--- | :--- | :--- |
| Python | 3.8+ | 后端运行环境 |
| Nmap | 任意 | **必须加入系统 PATH** |
| Node.js | 18+ | 前端构建 |
| pnpm | 8+ | 前端包管理（推荐） |

### 第一步：安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 第二步：配置 config.json

在项目根目录修改 `config.json`，关键节点如下：

```json
{
  "server": { "host": "0.0.0.0", "port": 5000, "debug": false },
  "nmap": {
    "ip_ranges": ["192.168.1.0/24"],
    "arguments": "-sS -O -T5",
    "scan_interval": 86400,
    "scan_enabled": true
  },
  "hfish": {
    "host_port": "127.0.0.1:4433",
    "api_key": "YOUR_KEY",
    "sync_interval": 300,
    "sync_enabled": true
  },
  "ai": {
    "api_key": "YOUR_LLM_KEY",
    "api_url": "https://api.openai.com/v1",
    "model": "gpt-4o"
  }
}
```

### 第三步：启动后端（Flask）

```bash
python .\main.py
```

> Flask 监听 `http://localhost:5000`，首次运行会自动创建 `database/aimiguard.db`。
> Windows 下若弹出防火墙权限提示，请选择允许。

### 第四步：启动前端开发服务器（可选）

> **如果只想快速查看**，跳过此步直接访问 `http://localhost:5000`（Flask 伺服已构建好的静态前端）。
> **开发调试**时才需要启动 Vite Dev Server：

```bash
cd web/vue
pnpm install     # 首次执行
pnpm run dev
```

Vite 监听 `http://localhost:3001`，所有 `/api` 请求自动代理到 `:5000`。

### 第五步：访问控制台

| 模式 | 地址 | 说明 |
| :--- | :--- | :--- |
| 快速体验（生产模式） | http://localhost:5000/ | Flask 伺服已构建的 Vue SPA |
| 前端开发模式 | http://localhost:3001 | Vite HMR，支持热更新，代理后端 |

**默认账号**：`admin` / `admin123`

---

## � 构建产物说明

> 以下信息反映最新一次 `pnpm run build` 的实际状态。

| Chunk 文件 | 大小 (min) | 说明 |
| :--- | :--- | :--- |
| `echarts-*.js` | ~520 KB | ECharts + vue-echarts（独立分包） |
| `vuetify-*.js` | ~136 KB | Vuetify 组件库（独立分包） |
| `DashboardView-*.js` | ~190 KB | 仪表盘页面 |
| `index-*.js` | ~37 KB | 公共入口 |

ECharts 已通过 `manualChunks` 拆分，不再与 HFishView 合并打包，可按需懒加载。

---

## �🛠️ API 参考 (v1)

所有接口均需在 Header 中携带 `Authorization: Bearer <token>`（登录接口除外）。

### 认证

| 接口 | 方式 | 说明 |
| :--- | :--- | :--- |
| `/api/v1/auth/login` | POST | 登录，获取 access_token |
| `/api/v1/auth/logout` | POST | 登出 |
| `/api/v1/auth/refresh` | POST | 刷新 Token |
| `/api/v1/auth/profile` | GET | 获取当前用户信息 |

### 总览

| 接口 | 方式 | 说明 |
| :--- | :--- | :--- |
| `/api/v1/overview/metrics` | GET | 仪表盘核心指标（主机数、漏洞数等） |
| `/api/v1/overview/trends` | GET | 趋势折线图数据 |
| `/api/v1/overview/defense-stats` | GET | 防御统计数据 |
| `/api/v1/overview/chain-status` | GET | 防御链路状态 |

### 防御事件 / 蜜罐

| 接口 | 方式 | 说明 |
| :--- | :--- | :--- |
| `/api/v1/defense/events` | GET | 防御事件列表（分页） |
| `/api/v1/defense/events/<id>/approve` | POST | 通过/确认事件 |
| `/api/v1/defense/events/<id>/reject` | POST | 驳回事件 |
| `/api/v1/defense/hfish/logs` | GET | HFish 蜜罐攻击日志 |
| `/api/v1/defense/hfish/config` | GET/POST | HFish 连接配置 |

### 扫描 / 资产 / 漏洞

| 接口 | 方式 | 说明 |
| :--- | :--- | :--- |
| `/api/v1/scan/tasks` | GET/POST | 扫描任务列表 / 发起新扫描 |
| `/api/v1/scan/findings` | GET | 漏洞发现结果 |
| `/api/v1/scan/assets` | GET | 已发现资产列表 |

### 系统配置

| 接口 | 方式 | 说明 |
| :--- | :--- | :--- |
| `/api/v1/system/profile` | GET | 系统信息 |
| `/api/v1/system/ai-config` | GET/POST | AI 大模型配置 |
| `/api/v1/system/tts-config` | GET/POST | TTS 语音配置 |

---

## 👨‍💻 Roadmap

- [x] MVC 架构底层重构
- [x] 主机 OS 标签智能聚类
- [x] 🤖 接入 LLM 安全分析
- [x] JWT 鉴权 + RESTful API v1
- [x] Vue 3 + Vuetify 全新前端（登录、仪表盘、资产、漏洞、防御、蜜罐、AI 对话、审计、威胁情报、设置）
- [x] 登录页粒子动画背景（Canvas requestAnimationFrame）
- [x] Dashboard 30 秒自动刷新（setInterval + onUnmounted 清理）
- [x] Nmap 扫描实时进度条（轮询 + v-progress-linear）
- [x] HFish 攻击来源柱状图 + 服务分布饼图（ECharts + vue-echarts）
- [x] AI 对话 Markdown 渲染（marked.js）+ 语音输入（Web Speech STT）+ 朗读（TTS）
- [x] ECharts 独立分包（manualChunks），首屏包体积优化
- [x] 交换机联动封堵（Netmiko）
- [ ] 钉钉 / 飞书 Webhook 实时告警
- [ ] 导出 PDF 安全体检报告