# 🔥 AimiGuard (玄枢·AI攻防指挥官)

**AimiGuard** 是一个基于 MVC 架构的智能安全与资产监控平台。它将 **Nmap (网络发现与漏洞扫描)** 与 **HFish (蜜罐攻击日志)** 深度整合，并通过 **Vue 3 + Vuetify + Vite** 构建的响应式前端界面，以及完整的 **JWT 认证 RESTful API**，提供企业级的内部安全资产大屏展示与防御管理。

---

## ✨ 核心功能

1. **自动资产测绘与 OS 标签** - 自动将 Nmap 扫描到的主机操作系统指纹标准化
2. **智能化漏洞探测 (NSE)** - 根据 OS 标签自动挂载专属 Nmap Vulnerability 探测脚本
3. **威胁情报中枢 (HFish)** - 图表化分析蜜罐攻击行为日志
4. **AI 驱动的"对话即扫描"** - 集成大语言模型，支持自然语言指令触发扫描
5. **交换机联动封禁** - 通过 Telnet/ACL 自动封禁恶意 IP
6. **JWT 鉴权 API** - 完整的 RESTful API，支持前后端分离

---

## 🏗️ 技术架构

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.8+ / Flask 3.0+ |
| 数据库 | SQLite |
| 网络扫描 | Nmap / fscan |
| 蜜罐 | HFish |
| AI | OpenAI Compatible API |
| 交换机 | Telnet / ACL |
| 前端 | Vue 3 + Vuetify 3 + Vite 6 |
| 图表 | ECharts / vue-echarts |
| 认证 | JWT |

---

## 📂 目录结构

```
AimiGuard/
├── main.py                  # 项目入口
├── config.json              # 核心配置文件
├── requirements.txt        # Python 依赖
│
├── database/               # 数据层 [Model]
│   ├── db.py              # SQLite 连接与建表
│   └── models.py          # 面向对象查询接口
│
├── plugin/                 # 插件模块
│   ├── attack_log_sync.py # HFish 日志同步
│   ├── hfish_ai_ban.py    # AI 封禁联动
│   ├── network_scan.py    # 网络扫描
│   └── web_screenshot.py  # 网页截图
│
├── ai/                    # AI 核心模块
│   ├── client.py          # LLM 客户端
│   ├── tools.py           # AI 工具集
│   └── skills/            # AI 技能
│       └── drill_executor/ # 演练执行器
│
├── web/                   # Web 层 [Controller + View]
│   ├── flask_app.py       # Flask 主入口
│   ├── api/              # RESTful API
│   │   ├── auth.py       # 认证
│   │   ├── overview.py   # 总览
│   │   ├── defense.py    # 防御
│   │   ├── ai.py         # AI 对话
│   │   ├── nmap_routes.py# Nmap 扫描
│   │   └── system.py     # 系统
│   ├── static/vue-dist/  # Vue 构建产物
│   └── vue/              # Vue 源码
│
└── utils/                # 工具函数
    └── logger.py         # 日志模块
```

---

## 🚀 快速开始

### 环境要求

- Python 3.8+
- Node.js 18+
- pnpm 8+
- Nmap (需加入系统 PATH)

### 第一步：安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 第二步：配置 config.json

在项目根目录修改 `config.json`：

```json
{
  "server": { "host": "0.0.0.0", "port": 5000 },
  "nmap": {
    "ip_ranges": ["192.168.1.0/24"],
    "scan_enabled": true
  },
  "hfish": {
    "host_port": "127.0.0.1:4433",
    "api_key": "YOUR_KEY",
    "sync_enabled": true
  },
  "ai": {
    "enabled": true,
    "api_url": "https://api.example.com",
    "api_key": "YOUR_API_KEY",
    "model": "gpt-4o"
  }
}
```

### 第三步：启动后端

```bash
python main.py          # 生产模式
python main.py --debug  # 调试模式
```

### 第四步：启动前端（可选，开发模式）

```bash
cd web/vue
pnpm install
pnpm run dev
```

### 第五步：访问

| 模式 | 地址 |
|------|------|
| 生产模式 | http://localhost:5000 |
| 开发模式 | http://localhost:3001 |

**默认账号**: `admin` / `admin123`

---

## 🌐 前端页面

| 页面 | 路由 | 说明 |
|------|------|------|
| 登录 | `/login` | 用户认证 |
| 仪表盘 | `/` | 总览与统计 |
| HFish | `/hfish` | 蜜罐攻击日志 |
| 防御 | `/defense` | 防御事件 |
| 资产探测 | `/nmap` | 网络资产 |
| 截图 | `/nmap/screenshots` | Web 截图 |
| AI 对话 | `/ai-chat` | AI 安全助手 |
| 报告 | `/reports` | 报告管理 |
| 设置 | `/settings` | 系统配置 |

---

## 📡 API 接口

所有 `/api/v1/` 接口需携带 `Authorization: Bearer <token>` (登录接口除外)。

### 认证

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/auth/login` | POST | 登录 |
| `/api/v1/auth/logout` | POST | 登出 |
| `/api/v1/auth/refresh` | POST | 刷新 Token |
| `/api/v1/auth/profile` | GET | 用户信息 |

### 总览

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/overview/metrics` | GET | 核心指标 |
| `/api/v1/overview/trends` | GET | 趋势数据 |

### 防御

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/defense/events` | GET/POST | 防御事件 |
| `/api/v1/defense/hfish/logs` | GET | HFish 日志 |

### AI

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/ai/chat` | POST | AI 对话 |
| `/api/v1/ai/chat/history` | GET | 聊天历史 |

---

## 📦 依赖

```
openai>=1.0.0
python-nmap
requests
telnetlib3
Flask>=3.0.0
urllib3>=2.0.0
bcrypt>=4.0.0
playwright>=1.40.0
Pillow>=10.0.0
```

---
