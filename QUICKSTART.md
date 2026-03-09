# Aimiguan 快速启动指南

## 环境要求

- **Python 3.9+**（推荐 3.12/3.13）
- **Node.js 18+**
- **SQLite 3**（系统自带）
- Git

## 一键启动（推荐）

`powershell
# 克隆仓库后，在项目根目录执行：
.\scripts\dev.ps1
`

脚本自动完成：
- 检测 Python / Node.js 环境
- 创建后端虚拟环境并安装依赖
- 自动生成 .env（含随机 JWT_SECRET）
- 初始化 SQLite 数据库
- 安装前端依赖
- 启动后端（:8000）+ 前端（:3000）

**常用参数：**
`powershell
.\scripts\dev.ps1 -PrepareOnly          # 仅初始化环境，不启动服务
.\scripts\dev.ps1 -SkipFrontend         # 仅启动后端
.\scripts\dev.ps1 -Verify               # 启动前执行离线验收
.\scripts\dev.ps1 -InstallBackendDependencies  # 强制重装后端依赖
`

## 手动启动

### 后端

`powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env    # 编辑 .env 填写 JWT_SECRET
python init_db.py
python main.py                 # http://localhost:8000
`

### 前端

`powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev                    # http://localhost:3000
`

## 访问应用

| 地址 | 说明 |
|------|------|
| http://localhost:3000 | 前端界面 |
| http://localhost:8000/docs | API 交互文档（Swagger） |
| http://localhost:8000/api/health | 健康检查 |

**默认管理员账号：** dmin / dmin123

## 目录结构

`
aimiguan/
 backend/                # 后端（FastAPI + SQLAlchemy）
    api/               # API 路由（15+ 模块）
    core/              # 数据库 ORM（45 张表）
    services/          # 业务服务（37 个模块）
    main.py            # 入口文件
 frontend/              # 前端（Vue 3 + TailwindCSS）
    src/
       api/          # API 客户端（19 模块）
       views/        # 页面组件（18 页面）
       stores/       # Pinia 状态管理
       components/   # 通用组件
    package.json
 scripts/               # 运维脚本
    dev.ps1           # 一键启动
    backup_db.py      # 数据库备份
    restore_db.py     # 数据库恢复
    check_db_health.py # 数据库健康检查
    verify.ps1        # 离线验收
 sql/mvp_schema.sql     # 完整数据库 DDL
 tests/                 # 测试套件（632+ 用例）
 README.md              # 完整文档
`

## 核心功能模块

| 模块 | 路径 | 说明 |
|------|------|------|
| 防御监控 | /defense | 威胁事件审批、自动封禁、状态机 |
| 探测扫描 | /scan | Nmap 扫描、漏洞管理、修复工单 |
| AI 中枢 | /ai | 对话、报告生成、TTS 播报 |
| 可观测性 | /observability | 指标看板、告警闭环、阈值管理 |
| 威胁情报 | /threat-intel | CVE 查询、EPSS 评分、KEV 检查 |
| 蜜罐管理 | /honeypots | 蜜罐配置、蜜标管理、告警 |
| 系统管理 | /settings | RBAC、备份恢复、审计导出 |
| 工作流 | /workflows | 可视化编排、版本管理、运行监控 |

## 运行测试

`powershell
# 全量测试
python -m pytest tests/ -q

# 指定模块
python -m pytest tests/test_p0_system_apis.py -v

# 覆盖率
python -m pytest --cov=backend --cov-report=html
`

## 故障排查

| 问题 | 排查步骤 |
|------|---------|
| 后端无法启动 | python --version / 检查端口 
etstat -ano \| findstr :8000 |
| 前端连不上后端 | 检查 ite.config.ts 代理配置 / 检查 CORS |
| 数据库损坏 | python scripts/check_db_health.py / python scripts/restore_db.py |
| 依赖冲突 | 删除 env 重建 / 
pm cache clean --force |

## 下一步

参考 [README.md](./README.md) 了解完整的架构设计、安全加固和前沿能力演进规划。
