# LZX 对接 API 分析

## 1. 总入口

- 后端统一启动入口在 `backend/main.py`。
- 路由注册位置也在 `backend/main.py`，这里把防御、扫描、防火墙、蜜罐、蜜标等模块全部挂进 FastAPI。
- 后台自动任务入口在 `backend/services/scheduler_service.py`，启动时会拉起 HFish 自动同步和 Nmap 自动扫描。

## 2. 你说的“蜜罐 API”实际分成两条线

### 2.1 蜜罐配置管理 API

位置：`backend/api/honeypot.py`

当前提供：

- `GET /api/v1/honeypots`：查询蜜罐配置列表
- `POST /api/v1/honeypots`：创建蜜罐配置
- `GET /api/v1/honeypots/{honeypot_id}`：查看单个蜜罐配置
- `PUT /api/v1/honeypots/{honeypot_id}`：更新蜜罐配置
- `GET /api/v1/honeypots/{honeypot_id}/alerts`：查看蜜罐告警
- `GET /api/v1/honeypots/strategy/suggest`：AI 推荐蜜罐策略

对应数据表：

- `honeypot_config`：模型在 `backend/core/database.py`
- `threat_event`：蜜罐告警最终落这里

当前这条线的特点：

- 这是“本地平台内的蜜罐配置管理”。
- 现在只做了 CRUD 和 AI 建议，没有真正去调用 HFish 创建/更新远端蜜罐节点。
- 表里虽然有 `hfish_node_id` 字段，但 `backend/api/honeypot.py` 里并没有真正写入或使用它。

### 2.2 HFish 接入 API

位置：`backend/api/defense.py` + `backend/services/hfish_collector.py`

当前提供：

- `POST /api/v1/defense/hfish/config`：保存 HFish 配置
- `GET /api/v1/defense/hfish/config`：读取 HFish 配置
- `POST /api/v1/defense/hfish/sync`：手动拉取一次 HFish 日志
- `POST /api/v1/defense/hfish/test`：测试 HFish 连接
- `GET /api/v1/defense/hfish/logs`：读取已入库的 HFish 攻击日志
- `GET /api/v1/defense/hfish/stats`：读取 HFish 统计
- `GET /api/v1/defense/ip-info/{ip}`：把 HFish 告警 IP 和 Nmap 结果关联起来

服务实现位置：

- `backend/services/hfish_collector.py`

真正干活的地方：

- `fetch_attack_logs()`：请求 HFish API
- `ingest_logs()`：把 HFish 返回转换成 `ThreatEvent`
- `sync_once()`：一次完整同步

## 3. Nmap 在哪里

### 3.1 Nmap API 路由

位置：`backend/api/scan.py`

和 Nmap 直接相关的接口主要在这里：

- `POST /api/v1/scan/nmap/config`
- `GET /api/v1/scan/nmap/config`
- `POST /api/v1/scan/nmap/scan`
- `GET /api/v1/scan/nmap/hosts`
- `GET /api/v1/scan/nmap/scans`
- `GET /api/v1/scan/nmap/stats`
- `GET /api/v1/scan/nmap/host/{ip}`
- `POST /api/v1/scan/nmap/vuln/scan`

### 3.2 Nmap 服务实现

位置：`backend/services/nmap_scanner.py`

关键函数：

- `_load_config()`：从 `collector_config` 载入配置
- `save_config()`：保存 Nmap 配置
- `execute_nmap_scan()`：调用本机 Nmap
- `parse_nmap_xml()`：解析 XML 结果
- `save_scan_results()`：写入 `scan_task` 和 `scan_finding`
- `scan_target()`：完整扫描流程

对应数据表：

- `scan_task`
- `scan_finding`
- `asset`

## 4. “nmcp” 基本可以判定是 MCP

我全仓库搜了 `nmcp`，后端代码里没有独立的 `nmcp` 模块。

当前能对得上的实际模块是：

- `backend/services/mcp_client.py`

这个模块负责：

- `block_ip()`
- `unblock_ip()`
- `get_device_status()`
- `get_acl_rules()`
- `execute_on_device()`

调用位置最关键的是：

- `backend/api/defense.py`

这里在自动处置链路里直接调用：

- `mcp_client.block_ip(event_ip, device_id)`

也就是说，当前“告警自动封禁”走的是 `defense -> MCP`，不是 `defense -> firewall api`。

## 5. 防火墙 API 在哪里

位置：`backend/api/firewall.py`

当前提供：

- `GET /api/v1/firewall/config`
- `POST /api/v1/firewall/config`
- `POST /api/v1/firewall/sync`
- `POST /api/v1/firewall/tasks/{task_id}/receipt`
- `POST /api/v1/firewall/tasks/{task_id}/retry`
- `GET /api/v1/firewall/tasks`
- `GET /api/v1/firewall/tasks/{task_id}`

对应数据表：

- `firewall_sync_task`
- `collector_config`

当前这条线的实际行为：

- 它更像“防火墙同步任务中心”。
- 它会创建任务、做签名、收回执、做失败重试状态流转。
- 但是这里没有看到真正向外部防火墙厂商 API 发请求的服务层实现。
- 目前更像等待外部系统拉取任务或者由别的联动程序处理回执。

## 6. 当前真实调用链

### 6.1 HFish 自动同步链

`backend/main.py`
-> `backend/services/scheduler_service.py`
-> `backend/services/hfish_collector.py`
-> `threat_event`
-> `backend/api/defense.py` 后续审批/处置逻辑

### 6.2 Nmap 自动扫描链

`backend/main.py`
-> `backend/services/scheduler_service.py`
-> `backend/services/nmap_scanner.py`
-> `scan_task` / `scan_finding`

### 6.3 自动封禁链

`backend/api/defense.py`
-> `backend/services/mcp_client.py`
-> 外部 MCP 工具

### 6.4 防火墙任务链

`backend/api/firewall.py`
-> `firewall_sync_task`
-> 回执接口更新状态

注意：

- 当前自动封禁链和防火墙任务链是两套并行设计，没有统一收口。
- 如果你后面要接真实设备，首先要决定“封禁动作以 MCP 为准”还是“封禁动作以 firewall task 为准”。

## 7. 现在最值得你改的地方

### 7.1 第一优先级：调度器首次启动可能读不到 HFish/Nmap 配置

问题位置：

- `backend/services/scheduler_service.py`
- `backend/services/hfish_collector.py`
- `backend/services/nmap_scanner.py`

原因：

- 调度循环里直接判断 `hfish_collector.enabled` 和 `nmap_scanner.enabled`。
- 但这两个单例默认值是 `False`，配置需要 `_ensure_config_loaded()` 才会从数据库载入。
- 调度器里在判断前没有主动调用 `_ensure_config_loaded()`。

结果：

- 服务刚启动时，即使数据库里已经配好了 HFish / Nmap，也可能完全不跑自动任务。

建议改法：

- 在调度器启动时先显式调用一次：
  - `hfish_collector._ensure_config_loaded()`
  - `nmap_scanner._ensure_config_loaded()`
- 或者每轮循环先刷新配置，再判断 `enabled`。

### 7.2 第二优先级：Nmap 路径判断过死，`nmap` 这种 PATH 写法会失败

问题位置：

- `backend/services/nmap_scanner.py` 的 `execute_nmap_scan()`

原因：

- 现在用的是 `os.path.exists(self.nmap_path)`。
- 但配置和测试里常写的是 `nmap`，这属于 PATH 命令，不是绝对路径。
- 这种情况下 `os.path.exists("nmap")` 会返回假。

结果：

- 你明明系统装了 Nmap，但代码仍然报路径不存在。

建议改法：

- 用 `shutil.which()` 兼容 PATH 命令。
- 兼容绝对路径和命令名两种配置方式。

### 7.3 第三优先级：HFish/Nmap 配置读取接口可能返回陈旧值

问题位置：

- `backend/api/defense.py` 的 HFish 配置读取接口
- `backend/api/scan.py` 的 Nmap 配置读取接口

原因：

- 读取时直接返回单例对象属性。
- 如果进程刚启动但还没触发过 `_ensure_config_loaded()`，会返回默认值。

建议改法：

- 在读取配置接口前先调用对应服务的 `_ensure_config_loaded()`。
- 更稳妥的是封装成统一的 `get_config()`，不要让 API 直接摸单例字段。

### 7.4 第四优先级：蜜罐管理和 HFish 接入没有真正打通

问题位置：

- `backend/api/honeypot.py`
- `backend/services/hfish_collector.py`
- `backend/core/database.py` 的 `honeypot_config`

现状：

- `honeypot_config` 只是本地表。
- `hfish_node_id` 字段存在，但没有真正写入流程。
- `get_honeypot_alerts()` 只是查全部 `ThreatEvent.source == "hfish"`，没有按某个蜜罐实例关联。

这说明什么：

- 现在的“蜜罐管理 API”还不是“真实 HFish 节点管理 API”。
- 如果你要对接远端 HFish 节点创建、停用、更新，这块必须补服务层。

建议改法：

- 先明确是否需要“平台内配置”同步到 HFish 实际节点。
- 如果要，就新增一个 HFish 节点管理服务，例如：
  - create node
  - update node
  - disable node
  - bind node id to `hfish_node_id`
- 同时把 `get_honeypot_alerts()` 改成能按 `hfish_node_id`、service_name、client_id 或额外绑定字段做真实关联。

### 7.5 第五优先级：防火墙链路和 MCP 链路没有统一

问题位置：

- `backend/api/defense.py`
- `backend/services/mcp_client.py`
- `backend/api/firewall.py`

现状：

- 自动处置直接走 MCP。
- 防火墙 API 只是在维护同步任务状态。
- 没有一个统一的“封禁执行抽象层”。

建议改法：

- 如果以后厂商接入会增加，建议抽一个 `block_executor` / `firewall_provider` 层。
- 上层 defense 只管下发 `block_ip`。
- 底层再选择：
  - MCP 执行
  - firewall 任务执行
  - mock 执行

这样改完以后，`defense.py` 不会继续直接耦合 `mcp_client`。

### 7.6 第六优先级：防火墙 API 目前缺少“真正出站调用厂商”的实现

问题位置：

- `backend/api/firewall.py`

现状：

- 这里只实现了任务创建、签名、回执、重试、查询。
- 没有看到对应的 `services/firewall_provider.py` 或者实际 HTTP 推送厂商接口的代码。

如果你后续是要“真的把 IP 推到防火墙里”：

- 这里需要补一个服务层。
- 然后决定是同步调用还是异步 worker 调用。

## 8. 如果你准备改代码，按目标拆分建议如下

### 目标 A：只是想把 HFish 接进来并稳定跑起来

优先改：

- `backend/services/scheduler_service.py`
- `backend/services/hfish_collector.py`
- `backend/api/defense.py`

重点：

- 启动加载配置
- 连接测试
- HFish 返回格式兼容
- 重复事件去重

### 目标 B：想把 Nmap 真正跑起来

优先改：

- `backend/services/nmap_scanner.py`
- `backend/api/scan.py`

重点：

- `nmap` 命令路径兼容
- Windows 下路径和权限
- XML 解析异常处理
- 扫描结果和资产模型的关联

### 目标 C：想把自动封禁做成真实防火墙联动

优先改：

- `backend/api/defense.py`
- `backend/services/mcp_client.py`
- `backend/api/firewall.py`
- 新增 `backend/services/firewall_provider.py`

重点：

- 统一封禁抽象
- 厂商适配器
- 幂等和回执
- 失败重试和人工介入

### 目标 D：想让“蜜罐配置”真的控制 HFish 远端节点

优先改：

- `backend/api/honeypot.py`
- 新增 `backend/services/hfish_node_service.py`
- `backend/core/database.py` 的 `honeypot_config` 关联字段

重点：

- 创建/更新/停用远端蜜罐节点
- 回填 `hfish_node_id`
- 告警按实例关联

## 9. 现有测试覆盖情况

已经有的测试：

- `tests/test_hfish_nmap_integration.py`：HFish/Nmap 配置和手动触发
- `tests/test_hfish_collector.py`：HFish 采集器细节
- `tests/test_mcp_client.py`：MCP mock、错误分类、业务方法
- `tests/test_d2_01_honeypot.py`：蜜罐 CRUD
- `tests/test_d2_02_03_honeypot_adv.py`：AI 蜜罐策略和 Honeytoken 生命周期
- `tests/test_firewall_api.py`：目前只测了防火墙 helper 函数

明显缺的测试：

- 防火墙任务接口完整流转测试
- 调度器启动后自动加载配置测试
- Nmap PATH 命令兼容测试
- 蜜罐实例与 HFish 告警真实关联测试
- defense 自动封禁链和 firewall 任务链二选一的集成测试

## 10. 我建议你先从哪里开始改

如果你现在马上要落地，我建议顺序是：

1. 先修调度器加载配置问题。
2. 再修 Nmap 命令路径兼容问题。
3. 然后决定自动封禁到底统一走 MCP 还是统一走 firewall task。
4. 最后再做蜜罐配置和 HFish 节点打通。

这是因为前两个属于“当前就可能跑不起来”的根问题，后两个属于架构收口问题。

## 11. 本轮结论

- 蜜罐相关不是一个模块，而是 `honeypot.py` 和 `defense.py + hfish_collector.py` 两条线。
- 你说的 `nmcp`，代码里基本可以视为 `mcp_client.py`。
- 防火墙目前是任务中心，不是完整的厂商执行器。
- 真正最先该动的不是前端，而是调度器加载配置、Nmap 路径兼容、蜜罐实例关联、防火墙与 MCP 收口。
