# Aimiguan 值班手册 · 应急预案 · 联系人清单

> **版本**: v1.0.0  
> **生效日期**: 2025-07-06  
> **维护人**: 运维团队  

---

## 一、值班制度

### 1.1 值班安排

| 时段 | 值班角色 | 职责 |
|------|---------|------|
| 工作日 09:00–18:00 | 主值班（安全运营） | 监控告警、事件研判、一线处置 |
| 工作日 18:00–09:00 | 副值班（轮值） | 响应 P0/P1 告警，必要时拉起主值班 |
| 周末 / 节假日 | 轮值（每周轮换） | 全职责覆盖，重大事件上报 |

### 1.2 值班交接清单

- [ ] 检查 `/api/health` 返回 `healthy`
- [ ] 检查 Aimiguan 前端页面可正常登录
- [ ] 检查最近 1 小时无未处理 P0/P1 告警
- [ ] 检查防火墙同步队列无 `MANUAL_REQUIRED` 积压
- [ ] 检查 AI 引擎健康（无连续降级标记）
- [ ] 确认值班通讯工具畅通（钉钉/企微/电话）
- [ ] 阅读上一班次值班日志

### 1.3 值班日志模板

```
日期: YYYY-MM-DD
班次: 日班 / 夜班
值班人: xxx

## 事件记录
| 时间 | 事件摘要 | 级别 | 处置结果 | 备注 |
|------|---------|------|---------|------|
|      |         |      |         |      |

## 待跟进事项
- 

## 交接说明
- 
```

---

## 二、应急预案

### 2.1 故障分级

| 级别 | 定义 | 响应时间 | 恢复目标 |
|------|------|---------|---------|
| **P0** | 系统完全不可用 / 数据泄露 | ≤ 5 分钟 | ≤ 30 分钟 |
| **P1** | 核心功能不可用（防御链/AI 评分） | ≤ 15 分钟 | ≤ 1 小时 |
| **P2** | 非核心功能异常（报告/TTS） | ≤ 1 小时 | ≤ 4 小时 |
| **P3** | 轻微问题 / UI 瑕疵 | 下一工作日 | 下一迭代 |

### 2.2 通用应急流程

```
发现故障
   │
   ├─ 1. 确认影响范围（P0/P1/P2/P3）
   │
   ├─ 2. 通知相关人员（按联系人清单）
   │
   ├─ 3. 止血措施（参见各场景预案）
   │
   ├─ 4. 根因定位 & 修复
   │
   ├─ 5. 验证恢复
   │
   └─ 6. 事后复盘（P0/P1 必须 48h 内完成）
```

### 2.3 场景预案

#### 场景 A：后端服务宕机

**现象**: `/api/health` 不可达，前端报网络错误

**处置步骤**:
1. SSH 登录服务器，检查进程状态
   ```powershell
   # Windows
   Get-Process -Name python | Where-Object {$_.CommandLine -match "main.py"}
   # Linux
   ps aux | grep "python.*main.py"
   ```
2. 检查日志：`backend/logs/` 或终端输出
3. 如 OOM，重启服务：
   ```powershell
   cd backend
   python main.py
   ```
4. 如数据库损坏，从备份恢复：
   ```powershell
   copy aimiguard.db.bak aimiguard.db
   python main.py
   ```
5. 验证 `/api/health` 返回 200

#### 场景 B：AI/LLM 服务不可用

**现象**: AI 评分全部返回 `degraded: true`，聊天无响应

**处置步骤**:
1. 检查 Ollama / LLM 服务状态
   ```powershell
   curl http://localhost:11434/api/tags
   ```
2. 如服务停止，重启 Ollama
3. 如模型未加载：`ollama pull llama2`
4. **降级策略已内置**：AI 不可用时自动使用规则引擎评分，不影响防御链
5. 确认降级后核心功能正常（事件列表、审批、封禁）

#### 场景 C：MCP 插件不可用

**现象**: 封禁/解封操作超时或失败

**处置步骤**:
1. 检查 MCP 服务器连接
2. 检查防火墙同步任务队列：`GET /api/v1/firewall/tasks?state=FAILED`
3. 手动重试失败任务：`POST /api/v1/firewall/tasks/{id}/retry`
4. 超过 3 次重试自动转 `MANUAL_REQUIRED`，需人工在防火墙控制台操作
5. 记录手动操作的 IP 和动作，后续补录系统

#### 场景 D：防火墙 API 不可达

**现象**: 同步任务全部 `PENDING` 或 `FAILED`

**处置步骤**:
1. 检查防火墙设备网络连通性
2. 检查防火墙 API 密钥是否过期
3. 检查配置：`GET /api/v1/firewall/config`
4. 临时措施：手动登录防火墙设备执行封禁
5. 恢复后批量重试积压任务

#### 场景 E：数据库异常

**现象**: API 返回 500，日志显示 SQLite 错误

**处置步骤**:
1. 检查磁盘空间：`df -h` / `Get-PSDrive C`
2. 检查数据库文件完整性：
   ```powershell
   python -c "import sqlite3; conn=sqlite3.connect('backend/aimiguard.db'); print(conn.execute('PRAGMA integrity_check').fetchone())"
   ```
3. 如完整性校验失败，从备份恢复
4. 运行迁移脚本补齐表结构：
   ```powershell
   cd backend
   python -c "from core.database import init_db; init_db()"
   ```
5. 验证核心接口恢复

#### 场景 F：前端不可访问

**现象**: 浏览器无法加载页面

**处置步骤**:
1. 检查前端开发服务器是否运行（开发环境）
2. 检查 Nginx / 静态文件服务（生产环境）
3. 检查 CORS 配置
4. 清除浏览器缓存后重试
5. 检查后端 API 是否可达

---

## 三、联系人清单

| 角色 | 姓名 | 联系方式 | 备注 |
|------|------|---------|------|
| **技术负责人** | [待填写] | 电话: [待填写] / 钉钉: [待填写] | P0 事件第一联系人 |
| **后端开发** | [待填写] | 电话: [待填写] / 钉钉: [待填写] | 后端/数据库问题 |
| **前端开发** | [待填写] | 电话: [待填写] / 钉钉: [待填写] | 前端/UI 问题 |
| **安全运营** | [待填写] | 电话: [待填写] / 钉钉: [待填写] | 安全事件研判 |
| **网络管理员** | [待填写] | 电话: [待填写] / 钉钉: [待填写] | 防火墙/网络问题 |
| **AI/算法** | [待填写] | 电话: [待填写] / 钉钉: [待填写] | AI 模型/评分问题 |
| **运维** | [待填写] | 电话: [待填写] / 钉钉: [待填写] | 服务器/部署问题 |

### 升级路径

```
一线值班
   │ (15min 未解决)
   ├──> 对应技术负责人
   │ (30min 未解决)
   ├──> 技术总负责人
   │ (P0 事件)
   └──> 全员拉群
```

---

## 四、监控检查项

### 4.1 健康检查端点

| 端点 | 预期 | 检查频率 |
|------|------|---------|
| `GET /api/health` | `{"status": "healthy"}` | 每 30 秒 |
| `GET /api/v1/overview/metrics` | 200 OK | 每 5 分钟 |
| `GET /api/v1/defense/events` | 200 OK | 每 5 分钟 |

### 4.2 关键指标阈值

| 指标 | 告警阈值 | 级别 |
|------|---------|------|
| API P95 延迟 | > 500ms | P2 |
| API P99 延迟 | > 2000ms | P1 |
| API 5xx 错误率 | > 1% | P1 |
| API 5xx 错误率 | > 5% | P0 |
| 防火墙 MANUAL_REQUIRED 积压 | > 10 | P2 |
| AI 连续降级次数 | > 20 | P2 |
| 数据库文件大小 | > 5GB | P3 |
| 磁盘使用率 | > 90% | P1 |

### 4.3 日常巡检脚本

```powershell
# 快速巡检（每日执行）
$baseUrl = "http://localhost:8000"

# 1. 健康检查
$health = Invoke-RestMethod "$baseUrl/api/health"
Write-Host "Health: $($health.data.status)"

# 2. 登录获取 token
$login = Invoke-RestMethod -Method POST "$baseUrl/api/v1/auth/login" `
  -ContentType "application/json" `
  -Body '{"username":"admin","password":"admin123"}'
$token = $login.access_token
$headers = @{ Authorization = "Bearer $token" }

# 3. 检查待处理事件
$events = Invoke-RestMethod "$baseUrl/api/v1/defense/pending" -Headers $headers
Write-Host "Pending events: $($events.data.Count)"

# 4. 检查防火墙积压
$fwTasks = Invoke-RestMethod "$baseUrl/api/v1/firewall/tasks?state=MANUAL_REQUIRED" -Headers $headers
Write-Host "Manual required FW tasks: $($fwTasks.data.total)"

# 5. 检查概览指标
$metrics = Invoke-RestMethod "$baseUrl/api/v1/overview/metrics" -Headers $headers
Write-Host "Metrics: OK"
```

---

## 五、回滚预案

### 5.1 代码回滚

```powershell
# 查看最近发布记录
git log --oneline -10

# 回滚到上一个稳定版本
git revert HEAD --no-edit
# 或回滚到指定 commit
git checkout <stable-commit-hash> -- .

# 重启服务
cd backend
python main.py
```

### 5.2 数据库回滚

```powershell
# 1. 停止服务
# 2. 恢复备份
copy backend\aimiguard.db.bak backend\aimiguard.db

# 3. 如需回滚工作流表
cd backend
python -c "from migrations.rollback_workflow_tables_v1 import rollback; rollback()"

# 4. 重启服务
python main.py
```

### 5.3 配置回滚

- 环境变量恢复：对照 `backend/.env.example` 检查
- 防火墙配置恢复：通过 `POST /api/v1/firewall/config` 重新设置

---

## 六、事后复盘模板

```markdown
# 事故复盘报告

## 基本信息
- 事故级别: P0 / P1
- 发现时间: YYYY-MM-DD HH:MM
- 恢复时间: YYYY-MM-DD HH:MM
- 影响时长: X 分钟
- 影响范围: 

## 时间线
| 时间 | 事件 | 操作人 |
|------|------|--------|
|      |      |        |

## 根因分析
- 直接原因: 
- 根本原因: 

## 改进措施
| 措施 | 负责人 | 截止日期 | 状态 |
|------|--------|---------|------|
|      |        |         |      |

## 经验教训
- 
```
