# Aimiguan 快速启动指南

## 环境要求

| 依赖 | 最低版本 | 快速安装（Windows winget） |
|------|---------|--------------------------|
| Python | 3.9+ | `winget install Python.Python.3.12` |
| Node.js | 18+ | `winget install OpenJS.NodeJS.LTS` |
| Git | 任意 | `winget install Git.Git` |

> **新机一键准备**（管理员 PowerShell）：
> ```powershell
> winget install Python.Python.3.12 OpenJS.NodeJS.LTS Git.Git
> ```
> 安装完成后**重开终端**使 PATH 生效，再执行下方启动命令。

---

## 一键启动（推荐）

```powershell
git clone <仓库地址>
cd aimiguan
.\scripts\dev.ps1
```

脚本自动完成：检测（并引导安装）Python / Node.js  创建虚拟环境  安装依赖  生成 `.env`（随机 JWT_SECRET） 初始化数据库  同时启动前后端。

**常用参数：**

```powershell
.\scripts\dev.ps1 -PrepareOnly                # 仅初始化，不启动
.\scripts\dev.ps1 -SkipFrontend               # 仅启动后端
.\scripts\dev.ps1 -InstallBackendDependencies # 强制重装后端依赖
.\scripts\dev.ps1 -Verify                     # 启动前离线验收
```

---

## 手动启动

### 后端
```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python init_db.py
python main.py        #  http://localhost:8000
```

### 前端
```powershell
cd frontend
npm install
npm run dev           #  http://localhost:3000
```

> `.env` 首次运行由脚本自动生成；手动操作时复制 `.env.example` 并修改 `JWT_SECRET`。

---

## 访问地址

| 地址 | 说明 |
|------|------|
| http://localhost:3000 | 前端 |
| http://localhost:8000/docs | API 文档（Swagger） |
| http://localhost:8000/api/health | 健康检查 |

**默认管理员账号：** admin / admin123

---

## 运行测试

```powershell
python -m pytest tests/ -q                              # 全量
python -m pytest tests/test_auth_api.py -v              # 单模块
python -m pytest --cov=backend --cov-report=html        # 覆盖率报告
```

---

## 故障排查

| 问题 | 解决方法 |
|------|---------|
| `python`/`node` 命令找不到 | 重开终端；脚本会自动尝试 winget 安装 |
| 端口 8000/3000 被占用 | `netstat -ano \| findstr :8000`  `taskkill /PID <pid> /F` |
| 前端连不上后端 | 检查 `frontend/.env` 中 `VITE_API_BASE_URL=http://localhost:8000` |
| 数据库损坏 | `python scripts/check_db_health.py` 或 `python scripts/restore_db.py` |
| 依赖冲突 | 删除 `backend/venv` 重建；前端执行 `npm cache clean --force` |

---

参考 [README.md](./README.md) 了解完整架构设计与安全加固规划。