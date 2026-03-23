# AimiGuard 代码创建说明文档

## 项目概述

**AimiGuard (玄枢·AI攻防指挥官)** 是一个基于 MVC 架构的智能安全与资产监控平台，整合了 Nmap 网络扫描、HFish 蜜罐攻击日志，并通过 Vue 3 前端 + Flask 后端提供企业级安全管理界面。

---

## 项目架构

```
AimiGuard/
├── main.py                    # 项目统一入口
├── config.json                # 核心配置文件
├── requirements.txt           # Python 依赖
├── database/                  # 数据层 [Model]
│   ├── db.py                  # SQLite 连接与建表
│   └── models.py              # 面向对象查询/写入接口
├── plugin/                    # 扫描与蜜罐插件
│   ├── attack_log_sync.py     # HFish API 对接
│   ├── hfish_ai_ban.py        # AI 攻击日志分析与封禁
│   ├── network_scan.py        # 主机探活、端口扫描
│   └── web_screenshot.py      # 网页截图
├── ai/                        # AI 核心模块
│   ├── client.py              # LLM 客户端封装
│   ├── tools.py               # AI 工具集
│   ├── utils.py               # 工具函数
│   └── skills/                # AI 技能模块
│       ├── registry.py        # 技能注册表
│       └── drill_executor/    # 演练执行器
│           ├── executor.py     # 执行器主逻辑
│           ├── drill_tools.py  # 演练工具
│           └── bruteforce.py   # 暴力破解模块
├── web/                       # Web 层 [Controller + View]
│   ├── flask_app.py           # Flask 主入口
│   ├── api/                   # RESTful API Blueprint
│   │   ├── __init__.py        # 蓝图注册
│   │   ├── auth.py            # 认证接口
│   │   ├── overview.py        # 总览仪表盘
│   │   ├── defense.py         # 防御事件
│   │   ├── ai.py              # AI 对话
│   │   ├── nmap_routes.py     # Nmap 扫描
│   │   ├── system.py          # 系统配置
│   │   ├── legacy.py          # 遗留接口
│   │   └── helpers.py         # 辅助函数
│   ├── static/vue-dist/       # Vue 构建产物
│   └── vue/                   # Vue 3 源码
│       └── src/
│           ├── main.ts        # 前端入口
│           ├── App.vue        # 根组件
│           ├── views/         # 页面组件
│           ├── components/    # 公共组件
│           ├── stores/        # Pinia 状态
│           ├── router/        # 路由配置
│           └── api/           # 前端 API 封装
└── utils/                     # 工具函数
    └── logger.py              # 日志模块
```

---

## 核心技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 后端 | Python 3.8+ / Flask 3.0+ | RESTful API 服务 |
| 数据库 | SQLite | 轻量级数据库存储 |
| 网络扫描 | Nmap / fscan | 主机发现、端口扫描、漏洞检测 |
| 蜜罐 | HFish | 攻击行为日志采集 |
| AI | OpenAI Compatible API | 大语言模型安全分析 |
| 交换机 | Telnet / ACL | 网络封禁联动 |
| 前端 | Vue 3 + Vuetify 3 + Vite | 响应式管理界面 |
| 图表 | ECharts / vue-echarts | 数据可视化 |
| 认证 | JWT | 接口鉴权 |

---

## 数据库表结构

### 1. scans (扫描任务表)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| scan_time | TEXT | 扫描时间 |
| ip_ranges | TEXT | IP 范围 |
| arguments | TEXT | Nmap 参数 |
| hosts_count | INTEGER | 发现主机数 |

### 2. hosts (主机表)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| scan_id | INTEGER | 关联扫描任务 |
| ip | TEXT | IP 地址 |
| mac_address | TEXT | MAC 地址 |
| vendor | TEXT | 设备厂商 |
| hostname | TEXT | 主机名 |
| state | TEXT | 状态 |
| os_type | TEXT | 操作系统类型 |
| os_tags | TEXT | OS 标签 |
| open_ports | TEXT | 开放端口 |
| services | TEXT | 服务信息 |

### 3. assets (资产表)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| mac_address | TEXT | MAC 地址（唯一） |
| current_ip | TEXT | 当前 IP |
| hostname | TEXT | 主机名 |
| vendor | TEXT | 厂商 |
| os_type | TEXT | 操作系统 |
| first_seen | TEXT | 首次发现时间 |
| last_seen | TEXT | 最后发现时间 |

### 4. attack_logs (攻击日志表)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| attack_ip | TEXT | 攻击者 IP |
| ip_location | TEXT | IP 地理位置 |
| client_name | TEXT | 蜜罐客户端名称 |
| service_name | TEXT | 服务名称 |
| service_port | TEXT | 服务端口 |
| threat_level | TEXT | 威胁等级 |
| create_time_str | TEXT | 创建时间字符串 |
| create_time_timestamp | INTEGER | 创建时间戳 |

### 5. ai_analysis_logs (AI分析记录表)
| 字段 | 类型 | 说明 |
|------|------|------|
| ip | TEXT | IP 地址（主键） |
| analysis_text | TEXT | 分析文本 |
| decision | TEXT | 决策结果 |
| scan_time | TEXT | 扫描时间 |
| status | TEXT | 状态 |

### 6. ai_chat_sessions (AI会话表)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| title | TEXT | 会话标题 |
| context_type | TEXT | 上下文类型 |
| is_drill_mode | INTEGER | 是否演练模式 |
| created_at | TEXT | 创建时间 |
| updated_at | TEXT | 更新时间 |

### 7. ai_chat_history (AI聊天历史表)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| session_id | INTEGER | 关联会话 |
| role | TEXT | 角色（user/assistant） |
| content | TEXT | 消息内容 |
| tool_calls | TEXT | 工具调用 JSON |
| create_time | TEXT | 创建时间 |

### 8. switch_acl_rules (交换机ACL规则表)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| switch_ip | TEXT | 交换机 IP |
| acl_number | INTEGER | ACL 编号 |
| action | TEXT | 动作（permit/deny） |
| target_ip | TEXT | 目标 IP |
| rule_text | TEXT | 规则文本 |
| created_at | TEXT | 创建时间 |

### 9. web_fingerprints (Web指纹表)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| ip | TEXT | IP 地址 |
| port | INTEGER | 端口 |
| service | TEXT | 服务 |
| title | TEXT | 网页标题 |
| url | TEXT | 完整 URL |
| status_code | INTEGER | HTTP 状态码 |
| server | TEXT | 服务器类型 |

### 10. web_screenshots (网页截图表)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| ip | TEXT | IP 地址 |
| port | INTEGER | 端口 |
| url | TEXT | 页面 URL |
| screenshot_path | TEXT | 截图路径 |
| scan_time | TEXT | 扫描时间 |

---

## API 接口规范

所有 `/api/v1/` 接口需携带 JWT Token（登录接口除外）。

### 认证接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/auth/login` | POST | 登录获取 Token |
| `/api/v1/auth/logout` | POST | 登出 |
| `/api/v1/auth/refresh` | POST | 刷新 Token |
| `/api/v1/auth/profile` | GET | 获取用户信息 |

### 总览接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/overview/metrics` | GET | 仪表盘核心指标 |
| `/api/v1/overview/trends` | GET | 趋势数据 |
| `/api/v1/overview/defense-stats` | GET | 防御统计 |

### 防御接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/defense/events` | GET/POST | 防御事件 |
| `/api/v1/defense/hfish/logs` | GET | HFish 攻击日志 |
| `/api/v1/defense/hfish/config` | GET/POST | HFish 配置 |

### 扫描接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/scan/tasks` | GET/POST | 扫描任务 |
| `/api/v1/scan/findings` | GET | 漏洞发现 |
| `/api/v1/scan/assets` | GET | 资产列表 |
| `/api/v1/nmap/screenshots/all` | GET | 所有截图 |

### AI 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/ai/chat` | POST | AI 对话 |
| `/api/v1/ai/chat/history` | GET | 聊天历史 |
| `/api/v1/ai/chat/sessions` | GET | 会话列表 |

### 系统接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/system/profile` | GET | 系统信息 |
| `/api/v1/system/ai-config` | GET/POST | AI 配置 |
| `/api/v1/system/tts-config` | GET/POST | TTS 配置 |

---

## 配置文件说明 (config.json)

```json
{
  "jwt_secret": "JWT密钥",
  "hfish": {
    "host_port": "HFish地址:端口",
    "api_key": "HFish API密钥",
    "sync_interval": 同步间隔(秒),
    "sync_enabled": 是否启用
  },
  "ai": {
    "enabled": 是否启用,
    "auto_ban": 自动封禁,
    "api_url": "AI API地址",
    "api_key": "AI API密钥",
    "model": "模型名称",
    "timeout": 超时时间,
    "ban_threshold": 封禁阈值
  },
  "switches": [
    {
      "host": "交换机IP",
      "port": 23,
      "password": "密码",
      "acl_number": ACL编号
    }
  ],
  "nmap": {
    "ip_ranges": ["扫描IP范围"],
    "fscan_timeout": 超时时间,
    "scan_interval": 扫描间隔,
    "scan_enabled": 是否启用
  },
  "server": {
    "host": "0.0.0.0",
    "port": 5000
  },
  "logging": {
    "api_request_log": true,
    "sync_log": true,
    "scan_log": true,
    "ai_log": true,
    "error_log": true
  }
}
```

---

## 前端页面结构

| 页面 | 路由 | 说明 |
|------|------|------|
| 登录页 | `/login` | 用户认证 |
| 仪表盘 | `/` | 总览与统计 |
| HFish攻击 | `/hfish` | 蜜罐攻击日志 |
| 防御事件 | `/defense` | 防御事件管理 |
| 资产探测 | `/nmap` | 网络资产扫描 |
| 截图展示 | `/nmap/screenshots` | Web 截图 |
| AI 对话 | `/ai-chat` | AI 安全助手 |
| 报告中心 | `/reports` | 报告管理 |
| 系统设置 | `/settings` | 配置管理 |

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 config.json

修改项目根目录的 `config.json`，配置 HFish、AI、交换机等参数。

### 3. 启动后端

```bash
python main.py          # 生产模式
python main.py --debug  # 调试模式
```

### 4. 启动前端（开发模式）

```bash
cd web/vue
pnpm install
pnpm run dev
```

### 5. 访问

- 生产模式: http://localhost:5000
- 开发模式: http://localhost:3001

**默认账号**: admin / admin123

---

## 开发规范

### Python 代码规范
- 使用 type hints 类型注解
- 异常处理使用 try-except-finally
- 日志输出使用统一的 `log()` 函数
- 数据库操作使用上下文管理器

### Vue 代码规范
- 使用 Composition API (`<script setup>`)
- 组件名使用 PascalCase
- 样式使用 scoped 隔离
- API 调用封装在 `src/api/` 目录

### Git 提交规范
```
feat: 新功能
fix: 修复bug
docs: 文档更新
style: 代码格式
refactor: 重构
test: 测试
chore: 构建/工具
```
