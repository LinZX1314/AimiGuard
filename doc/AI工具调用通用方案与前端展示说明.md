# AI 工具调用通用方案与前端展示说明

## 1. 目标

本次改造把原先散落在 `web/api/ai.py` 里的 OpenAI 工具调用逻辑拆成了两层：

- `web/ai_runtime/client.py`
- `web/ai_runtime/tools.py`

这样处理后，后端聊天接口只负责：

- 维护会话
- 保存用户消息
- 调用 AI
- 记录工具调用结果
- 返回前端展示数据

而真正和 OpenAI `tools` / `tool_calls` 协议有关的部分，被统一收敛到公共层，后续新增功能时不需要再把工具定义、参数解析、工具执行、二次请求都重新写一遍。

## 2. 目录结构

当前与 AI 工具调用最相关的目录如下：

```text
plugin/
├─ ai_tools.py
web/
├─ api/
│  └─ ai.py
└─ ai_runtime/
   ├─ __init__.py
   ├─ client.py
   └─ tools.py
```

职责划分如下：

### `web/api/ai.py`

负责 HTTP 接口与会话管理：

- `/api/v1/ai/chat`
- `/api/v1/ai/sessions`
- `/api/v1/ai/sessions/<id>/messages`

### `web/ai_runtime/client.py`

负责 OpenAI 兼容协议处理：

- 兼容 `api_url` 自动补全到 `/v1/chat/completions`
- 发起 OpenAI-compatible Chat Completions 请求
- 解析 `message.tool_calls`
- 把本地历史消息重新组装成 OpenAI 兼容的 `messages`

### `web/ai_runtime/tools.py`

负责工具注册与执行：

- 统一注册 `tools`
- 统一执行 `tool_calls`
- 当前内置 `nmap_scan`
- 后续新增功能时，只需要继续注册新的工具函数

### `plugin/ai_tools.py`

负责 HFish 攻击日志的 AI 分析与自动封禁：

- `analyze_and_ban(...)` 用于蜜罐日志判定
- 不再承担聊天扫描工具调用职责
- 聊天扫描工具调用已经统一迁移到 `web/ai_runtime/`

### `plugin/nmap_plugin`

该目录当前是空遗留目录，不参与现有 AI 聊天或扫描主流程。

- 如果后续没有重新启用其中内容，可以直接删除
- 当前真正生效的扫描能力来自 `plugin/network_scan.py`

## 3. 当前采用的 OpenAI tools 标准格式

本次实现遵循 OpenAI 官方 `function calling / tool calling` 流程：

### 第一步：向模型发送 tools

请求体中带上：

- `model`
- `messages`
- `tools`
- `tool_choice: "auto"`

示意结构：

```json
{
  "model": "your-model",
  "messages": [
    {"role": "system", "content": "你是安全助手"},
    {"role": "user", "content": "帮我扫描 192.168.1.1"}
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "nmap_scan",
        "description": "执行 Nmap 网络扫描",
        "parameters": {
          "type": "object",
          "properties": {
            "target": {"type": "string"},
            "arguments": {"type": "string"}
          },
          "required": ["target"]
        }
      }
    }
  ],
  "tool_choice": "auto"
}
```

### 第二步：模型返回 `tool_calls`

模型如果决定调用工具，会返回：

```json
{
  "role": "assistant",
  "content": "",
  "tool_calls": [
    {
      "id": "call_xxx",
      "type": "function",
      "function": {
        "name": "nmap_scan",
        "arguments": "{\"target\":\"192.168.1.1\",\"arguments\":\"-sV -T4\"}"
      }
    }
  ]
}
```

### 第三步：后端执行工具

后端根据：

- `tool_calls[i].function.name`
- `tool_calls[i].function.arguments`

找到已注册的工具函数，然后执行。

### 第四步：将工具结果回填为 `role=tool`

工具执行完成后，回填消息格式如下：

```json
{
  "role": "tool",
  "tool_call_id": "call_xxx",
  "name": "nmap_scan",
  "content": "{\"ok\":true,\"scan_id\":12,...}"
}
```

### 第五步：再次请求模型，得到最终回复

把：

- 原始用户消息
- assistant 的 `tool_calls`
- tool 的执行结果

一起继续发给模型，获取最终可读回复。

## 4. 如何创建一个新工具

后续新增工具时，主要改 `web/ai_runtime/tools.py`。

### 4.1 注册新工具

在 `tool_registry` 上注册一个新函数。

示例：

```python
@tool_registry.register_function(
    name='asset_lookup',
    description='查询资产信息',
    parameters={
        'type': 'object',
        'properties': {
            'ip': {'type': 'string', 'description': '资产 IP'}
        },
        'required': ['ip'],
    },
)
def _asset_lookup(args: dict):
    ip = str(args.get('ip') or '').strip()
    if not ip:
        return {'ok': False, 'error': '缺少 ip 参数'}

    return {
        'ok': True,
        'ip': ip,
        'asset': {
            'owner': 'example',
            'risk': 'medium'
        }
    }
```

关键要求：

- `name` 必须唯一
- `parameters` 必须是标准 JSON Schema 风格对象
- 工具函数参数统一接收 `args: dict`
- 返回值建议是 `dict` 或 `str`
- 如果返回 `dict`，系统会自动转为 JSON 字符串再发回模型

## 5. 如何调用工具

### 5.1 AI 自动调用

默认方式是由模型决定是否调用工具。

后端在 `web/api/ai.py` 中会自动读取：

```python
_TOOL_DEFS = get_tool_definitions()
```

随后带着这些工具定义调用 `call_openai_chat_completion(...)`。

如果模型判断当前问题适合调用某个工具，就会返回 `tool_calls`。

### 5.2 手动限制工具范围

如果你后面想做“某个页面只允许某些工具可用”，可以扩展成：

- 先取全部工具
- 再按页面或业务场景筛选工具列表
- 最后只把筛选后的列表传给 `call_openai_chat_completion(...)`

例如：

```python
all_tools = get_tool_definitions()
allowed = [tool for tool in all_tools if tool['function']['name'] in {'nmap_scan'}]
```

然后把 `allowed` 作为 `tools` 传给模型。

## 6. 前端如何显示工具调用

前端页面：

- `web/vue/src/views/AiChatView.vue`

本次改造后，后端返回的不再只有纯文本 `reply`，还会返回一组结构化消息：

```json
{
  "session_id": 3,
  "reply": "扫描结果显示目标开放了 22 和 80 端口...",
  "messages": [
    {
      "role": "assistant",
      "content": "我先帮你执行扫描。",
      "tool_calls": [
        {
          "id": "call_xxx",
          "name": "nmap_scan",
          "arguments": {
            "target": "192.168.1.1",
            "arguments": "-sV -T4"
          }
        }
      ]
    },
    {
      "role": "tool",
      "name": "nmap_scan",
      "tool_call_id": "call_xxx",
      "content": "{\"ok\":true,\"scan_id\":12,...}"
    },
    {
      "role": "assistant",
      "content": "扫描完成，目标开放端口如下..."
    }
  ]
}
```

### 6.1 assistant 消息展示什么

`assistant` 消息建议展示两部分：

- `content`：模型的自然语言解释
- `tool_calls`：模型决定调用了哪些工具、参数是什么

适合展示成：

- 一段 Markdown 回复
- 下方一个“工具调用”区域
- 每个工具显示：工具名 + JSON 参数

### 6.2 tool 消息展示什么

`tool` 消息建议展示：

- 工具名
- 原始执行结果
- JSON 格式化后的结果预览

因为工具返回值通常是 JSON 字符串，前端可以这样处理：

1. 先尝试 `JSON.parse(content)`
2. 如果成功，则 `JSON.stringify(obj, null, 2)` 美化展示
3. 如果失败，就按普通文本展示

### 6.3 为什么要前端单独显示 tool 消息

原因有三个：

- 方便你调试 AI 是否真的调用了工具
- 方便后续加入更多功能时做可观测性展示
- 用户可以看见调用参数与执行结果，避免 AI 过程完全黑盒

## 7. 以后新增功能的推荐步骤

以后你想新增更多能力，建议按照下面顺序做：

### 场景一：新增一个后端工具

1. 在 `web/ai_runtime/tools.py` 注册新工具
2. 定义 JSON Schema 参数
3. 编写工具处理函数
4. 返回结构化 JSON 结果
5. 前端在聊天页自动就能看到调用与结果

### 场景二：让某个页面只开放部分工具

1. 在对应接口中筛选 `get_tool_definitions()` 的结果
2. 只把允许的工具传给模型
3. 保持其余流程不变

### 场景三：前端做更精细的工具展示

可以继续扩展：

- 不同工具使用不同图标
- 对 `nmap_scan` 的结果做表格化展示
- 对扫描结果增加“跳转到扫描详情页”按钮
- 对失败结果显示错误态样式

## 8. 本次改造后的收益

### 可维护性

AI 协议处理不再和业务工具实现写在一起。

### 可扩展性

后续新增工具时，只需要注册，不需要重复写整套调用流程。

### 兼容性

兼容 OpenAI Chat Completions 的 `tools` / `tool_calls` 消息结构，更容易对接其他 OpenAI-compatible 平台。

### 前端可观测性

前端现在可以清楚展示：

- AI 何时调用工具
- 调用了哪个工具
- 参数是什么
- 返回了什么

## 9. 建议

如果你后面工具越来越多，可以继续把 `web/ai_runtime/tools.py` 再拆成：

```text
web/ai_runtime/
├─ client.py
├─ registry.py
└─ tools/
   ├─ network.py
   ├─ assets.py
   └─ defense.py
```

目前工具数量还不多，保留为 `client.py + tools.py` 两层结构会更简单，维护成本也更低。
