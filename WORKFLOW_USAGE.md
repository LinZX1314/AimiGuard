# AimiGuard 工作流使用说明

本文档专门说明 AimiGuard 中“AI 工作流”功能的用途、配置方式、使用步骤、接口行为、运行逻辑、测试情况与当前已发现问题。

## 1. 功能概述

AimiGuard 的工作流系统用于把平台已有能力编排成一条可执行流程。当前已支持：

- 手动触发
- 定时触发
- Webhook 触发
- 查询 HFish 攻击日志
- 生成 AI 摘要
- 条件分支
- 写入系统日志
- 站内通知
- 调用内部 API

后端执行入口位于：

- `workflow/engine.py`
- `workflow/templates.py`
- `web/api/workflow.py`
- `web/api/runtime.py`
- `database/workflow_models.py`

前端页面位于：

- `web/vue/src/views/WorkflowView.vue`
- `web/vue/src/components/workflow/WorkflowCanvas.vue`

## 2. 工作流是怎么运行的

### 2.1 核心执行链路

1. 前端进入“AI工作流”页面。
2. 页面通过 `/api/v1/workflows/catalog` 获取节点目录。
3. 页面通过 `/api/v1/workflows` 获取已有工作流列表。
4. 页面可通过模板中心、快速创建入口或画布右键菜单构建工作流。
5. 用户编辑并保存工作流定义。
6. 用户发布后，工作流状态变为 `active`。
7. 根据触发方式执行：
   - 手动触发：调用 `/api/v1/workflows/<id>/run`
   - Webhook 触发：外部系统调用 `/api/v1/workflows/webhook/<token>`
   - 定时触发：后台线程轮询到期工作流并执行
8. 执行结果与步骤明细写入数据库：
   - `workflow_runs`
   - `workflow_run_steps`

### 2.2 执行器逻辑

执行器在 `workflow/engine.py` 中，主要流程如下：

- 对 `definition.nodes` 和 `definition.edges` 做归一化
- 找出起始节点（没有入边的节点）
- 逐个节点执行 `_execute_node`
- 将每一步的输入、输出、状态写入 `workflow_run_steps`
- 将整次运行状态写入 `workflow_runs`
- 若遇到条件节点，仅继续命中的分支
- 若是定时任务，执行后自动更新 `last_run_at` 和 `next_run_at`

### 2.3 当前支持的节点类型

| kind | 说明 |
|------|------|
| `manual` | 手动触发 |
| `schedule` | 定时触发 |
| `webhook` | Webhook 触发 |
| `query_hfish_logs` | 查询 HFish 攻击日志 |
| `generate_ai_summary` | 调用 AI 生成摘要 |
| `condition` | 条件分支 |
| `write_log` | 写入系统日志 |
| `notify_in_app` | 站内通知 |
| `call_internal_api` | 调用平台内部 API |

## 3. 启用前需要哪些配置

工作流调度配置在根目录 `config.json`：

```json
{
  "workflow": {
    "enabled": true,
    "poll_interval": 15
  }
}
```

说明：

- `enabled`: 是否启用工作流调度线程
- `poll_interval`: 调度轮询间隔，单位秒，代码里最小有效间隔为 5 秒

如果工作流中使用了 AI 摘要节点，还需要同时配置：

```json
{
  "ai": {
    "enabled": true,
    "api_url": "你的兼容 OpenAI 的接口地址",
    "api_key": "你的密钥",
    "model": "模型名"
  }
}
```

如果工作流中使用了 `query_hfish_logs`，则需要平台已有 HFish 数据，或者 HFish 同步线程已正常工作。

## 4. 如何启动工作流功能

### 4.1 启动后端

在项目根目录执行：

```bash
python main.py
```

调试模式：

```bash
python main.py --debug
```

启动后：

- `main.py` 会创建 Flask 应用
- `web/api/runtime.py` 中的 `start_runtime_workers()` 会按配置启动后台线程
- 如果 `workflow.enabled=true`，会启动工作流调度线程

### 4.2 启动前端开发环境

```bash
cd web/vue
pnpm install
pnpm run dev
```

如果只用后端集成后的静态页面，则前端可以直接构建：

```bash
cd web/vue
pnpm build
```

## 5. 页面上怎么用

前端页面是 `web/vue/src/views/WorkflowView.vue`。

### 5.1 新建工作流

页面顶部有四个主要入口：

- `新建工作流`：创建手动触发工作流
- `模板中心`：从后端内置模板真正实例化工作流
- `快速定时流`：快速创建定时触发工作流草稿
- `快速Webhook流`：快速创建 Webhook 触发工作流草稿

说明：

- `模板中心` 会调用后端模板 API，属于真实模板实例化
- `快速定时流` / `快速Webhook流` 仍然是便捷创建默认流程，适合快速起草

### 5.2 画布里怎么创建功能模块

现在画布支持两种创建节点方式：

1. 顶部按钮 `新增节点`
2. 在画布空白处点击鼠标右键，打开“创建节点”菜单

右键菜单会：

- 在当前鼠标位置打开
- 展示可创建节点清单
- 点击后直接把节点创建到当前右键位置

这就是你说的“右键这个画布应该有创建节点、创建功能模块之类的”，现在已经加上了。

### 5.3 编辑工作流

页面由三部分组成：

- 左侧：工作流列表
- 中间：流程画布
- 右侧：节点属性检查器

你可以：

- 在画布上新增节点
- 连接节点
- 选中节点后在右侧修改：
  - 标题
  - 描述
  - 配置 JSON
- 条件节点可额外配置：
  - `source`
  - `path`
  - `operator`
  - `expected`

保存时点击 `保存工作流`。

### 5.4 发布工作流

点击 `发布` 后，后端调用：

```text
POST /api/v1/workflows/<id>/publish
```

发布后状态变为 `active`，此时：

- 手动工作流可以立即运行
- 定时工作流会被调度线程扫描执行
- Webhook 工作流可以接收外部请求

### 5.5 手动运行

点击 `立即运行`，输入 JSON 参数，例如：

```json
{
  "severity": "high",
  "source": "manual-test"
}
```

这些数据会作为 `trigger payload` 注入执行上下文，条件节点和后续节点都可以读取。

## 6. 三种触发方式怎么用

### 6.1 手动触发

适合临时运行、调试节点链路。

接口：

```text
POST /api/v1/workflows/<id>/run
Authorization: Bearer <token>
Content-Type: application/json
```

请求示例：

```json
{
  "payload": {
    "severity": "high",
    "source": "manual-test"
  }
}
```

### 6.2 定时触发

定时触发依赖：

- 工作流 `status = active`
- `trigger.type = schedule`
- `trigger.enabled = true`
- `workflow.enabled = true`

定时频率来自 `trigger.interval_seconds`。

执行逻辑：

- 调度线程在 `web/api/runtime.py` 中循环运行
- 每轮通过 `WorkflowModel.list_due_workflows()` 查到期任务
- 调用 `run_workflow(..., trigger_type='schedule')`
- 执行结束后更新下次时间

### 6.3 Webhook 触发

Webhook 接口：

```text
POST /api/v1/workflows/webhook/<token>
Content-Type: application/json
```

可以直接发送 JSON 请求体作为触发载荷。

返回工作流详情接口中会包含：

- `webhook_token`：Webhook 调用路径中的 token
- `webhook_secret`：用于签名的独立密钥
- `webhook_signature_hint`：签名头说明

可选签名头：

- `X-Workflow-Timestamp`
- `X-Workflow-Signature`

签名算法说明：

- 将请求体按 JSON 排序序列化
- 拼接为：`<timestamp>.<canonical_json>`
- 使用 `webhook_secret` 作为 HMAC-SHA256 密钥
- 十六进制摘要写入 `X-Workflow-Signature`

示例 Python：

```python
import json
import time
import hmac
import hashlib
import requests

url = 'http://127.0.0.1:5000/api/v1/workflows/webhook/<token>'
payload = {'event': 'external-alert', 'severity': 'high'}
timestamp = str(int(time.time()))
canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True)
signature = hmac.new(
    '<webhook_secret>'.encode('utf-8'),
    f'{timestamp}.{canonical}'.encode('utf-8'),
    hashlib.sha256,
).hexdigest()

resp = requests.post(
    url,
    json=payload,
    headers={
        'X-Workflow-Timestamp': timestamp,
        'X-Workflow-Signature': signature,
    },
)
print(resp.status_code, resp.text)
```

注意：如果不传签名头，当前实现仍会执行，只要 token 正确即可。

## 7. 条件分支怎么配

条件节点在 `workflow/engine.py` 中由 `_evaluate_condition()` 处理。

支持配置：

- `source`
  - `trigger_payload`
  - `last_step_output`
  - `step_output_by_node_id`
- `path`
  - 例如 `severity`
  - 例如 `logs.0.attack_ip`
- `operator`
  - `eq`
  - `neq`
  - `contains`
  - `gt`
  - `gte`
  - `lt`
  - `lte`
  - `exists`
  - `empty`
- `expected`

示例：根据触发参数中的 `severity` 判断是否高危：

```json
{
  "source": "trigger_payload",
  "path": "severity",
  "operator": "eq",
  "expected": "high"
}
```

如果判断为真，执行带 `branch: "true"` 的边；否则执行 `branch: "false"` 的边。

## 8. 当前内置模板

后端模板定义在 `workflow/templates.py`，目前已扩展为 6 套：

1. `hfish-ai-summary`
   - 手动触发
   - 查询 HFish 日志
   - AI 摘要
   - 站内通知

2. `hfish-triage-route`
   - 手动触发
   - 查询 HFish 日志
   - 条件分支
   - 有日志走 AI 摘要和通知
   - 无日志写入普通日志

3. `scheduled-severity-route`
   - 定时触发
   - 判断 severity
   - 高危走通知
   - 非高危写日志

4. `scheduled-daily-digest`
   - 定时触发
   - 查询 HFish 日志
   - 生成 AI 安全日报
   - 写日志 + 推送通知

5. `webhook-alert-intake`
   - Webhook 触发
   - 判断外部告警级别
   - 高危通知
   - 普通告警写日志

6. `webhook-api-bridge`
   - Webhook 触发
   - 调用内部 API
   - 记录桥接结果
   - 推送通知

对应 API：

- `GET /api/v1/workflows/templates`
- `POST /api/v1/workflows/templates/<template_id>/instantiate`

## 9. 常用 API 一览

### 9.1 工作流目录

```text
GET /api/v1/workflows/catalog
```

返回节点分类与节点目录。

### 9.2 模板列表

```text
GET /api/v1/workflows/templates
```

### 9.3 从模板创建

```text
POST /api/v1/workflows/templates/<template_id>/instantiate
```

### 9.4 工作流 CRUD

```text
GET    /api/v1/workflows
POST   /api/v1/workflows
GET    /api/v1/workflows/<id>
PUT    /api/v1/workflows/<id>
DELETE /api/v1/workflows/<id>
```

### 9.5 发布与运行

```text
POST /api/v1/workflows/<id>/publish
POST /api/v1/workflows/<id>/run
```

### 9.6 运行记录

```text
GET /api/v1/workflows/<id>/runs
GET /api/v1/workflows/runs/<run_id>
GET /api/v1/workflows/runs/<run_id>/steps
```

## 10. 数据库存储

工作流相关表：

- `workflows`：定义、触发器、状态、调度信息
- `workflow_runs`：每次运行主记录
- `workflow_run_steps`：每个节点执行步骤
- `workflow_webhooks`：Webhook token / secret 映射表

说明：

- 工作流定义存在 `definition_json`
- 触发器定义存在 `trigger_json`
- Webhook token 同时也保存在 `workflows.webhook_token`
- Webhook secret 单独保存在 `workflow_webhooks.secret`

## 11. 已执行测试

本次检查中执行了：

### 11.1 Python 测试

```bash
python -m unittest discover -s tests -v
```

以及回归确认：

```bash
python -m unittest discover -s tests -q
```

仓库中目前核心测试文件为：

- `tests/test_workflow_api.py`

该文件覆盖了：

- catalog 接口
- template 列表与实例化
- 多模板存在性校验
- 创建/发布/运行工作流
- 条件分支执行
- `success_with_skips` 状态
- 运行详情接口
- Webhook 触发
- Webhook secret 返回
- Webhook 正确签名
- Webhook 错误签名拒绝
- 到期定时任务查询
- 调度器执行一次

### 11.2 前端构建测试

```bash
cd web/vue
pnpm build
```

前端构建已成功完成，说明当前 TypeScript 编译与打包链路正常。

## 12. 当前发现的问题 / 风险点

### 12.1 画布右键创建节点已补上

现在在画布空白区域点击鼠标右键，会弹出“创建节点”菜单，并可直接在当前位置创建功能模块。

### 12.2 模板数量已扩充

现在模板中心不再只有很少的模板，而是已经提供：

- 手动分析模板
- 手动分诊模板
- 定时分流模板
- 定时日报模板
- Webhook 告警接入模板
- Webhook API 桥接模板

### 12.3 `success_with_skips` 已按成功态展示

后端在条件节点跳过未命中分支时，会返回：

- `success_with_skips`

前端运行历史和运行详情现在都已把它按成功态展示，并增加了更明确的标签显示。

### 12.4 Webhook 已改为 token / secret 分离

当前实现已经调整为：

- `token` 用于路由定位
- `secret` 单独存储在 `workflow_webhooks.secret`
- 签名校验使用 `webhook_secret`

这样安全模型更清晰，也更符合常见 Webhook 设计。

### 12.5 仍然缺少更广泛的自动化测试

当前仓库里仍未发现：

- pytest 测试套件
- vitest/jest 前端单元测试
- Playwright 前端端到端测试

所以“全部测试”目前主要还是：

- 工作流后端接口单测
- 前端构建测试

## 13. 推荐使用方式

如果你现在要实际用这套工作流，我建议按下面方式：

### 场景 A：先验证链路

1. 启动后端
2. 打开前端“AI工作流”页面
3. 新建一个手动工作流
4. 右键画布继续补充功能节点
5. 连上：
   - 手动触发
   - 查询 HFish 日志
   - 写入系统日志
6. 发布
7. 手动运行，传一个简单 JSON
8. 查看运行历史和步骤详情

### 场景 B：做告警分流

1. 使用模板中心创建定时模板，或快速新建一个定时流
2. 添加条件节点
3. 用 `severity` 做条件判断
4. 高危走通知，低危走日志
5. 发布后等待调度器自动轮询

### 场景 C：接第三方系统

1. 创建 Webhook 工作流
2. 发布
3. 获取 `webhook_token`
4. 如需验签，同时保存 `webhook_secret`
5. 让外部系统向 `/api/v1/workflows/webhook/<token>` 发 POST
6. 可选加入签名头提高安全性

## 14. 后续建议

建议下一步继续补强以下几项：

1. 为前端补充页面交互测试，特别是右键菜单创建节点
2. 为执行器补充更复杂的分支和异常路径测试
3. 如果后续需要更强安全性，可增加 Webhook 重放保护记录
4. 可继续扩展模板中心的模板预览、搜索与分类筛选

---

如果你愿意，我下一步可以继续帮你：

1. 再补一套前端自动化测试
2. 再补 workflow engine 的单测
3. 再给模板中心做搜索和分类筛选
