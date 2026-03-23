import type { WorkflowCatalogNode, WorkflowDefinition, WorkflowEdgeConfig, WorkflowNodeConfig, WorkflowNodeData } from '@/api/workflow'

export const workflowCategoryMeta: Record<string, { label: string; color: string }> = {
  trigger: { label: '触发器', color: 'text-sky-500' },
  discovery: { label: '资产发现', color: 'text-violet-500' },
  threat: { label: '威胁采集', color: 'text-amber-500' },
  ai: { label: 'AI 分析', color: 'text-indigo-500' },
  defense: { label: '防御处置', color: 'text-rose-500' },
  system: { label: '系统数据', color: 'text-emerald-500' },
  result: { label: '结果输出', color: 'text-orange-500' },
}

export const defaultWorkflowCatalogNodes: WorkflowCatalogNode[] = [
  { kind: 'manual', type: 'trigger', label: '手动触发' },
  { kind: 'schedule', type: 'trigger', label: '定时触发' },
  { kind: 'webhook', type: 'trigger', label: 'Webhook 触发' },
  { kind: 'query_hfish_logs', type: 'threat', label: '查询 HFish 日志' },
  { kind: 'generate_ai_summary', type: 'ai', label: 'AI 摘要' },
  { kind: 'condition', type: 'system', label: '条件分支' },
  { kind: 'write_log', type: 'result', label: '写入系统日志' },
  { kind: 'notify_in_app', type: 'result', label: '站内通知' },
  { kind: 'call_internal_api', type: 'result', label: '调用内部 API' },
]

function inferCategory(kind?: string, rawType?: string): string {
  if (rawType && rawType in workflowCategoryMeta) return rawType
  if (kind === 'manual' || kind === 'schedule' || kind === 'webhook') return 'trigger'
  if (kind === 'query_hfish_logs') return 'threat'
  if (kind === 'generate_ai_summary') return 'ai'
  if (kind === 'condition') return 'system'
  if (kind === 'write_log' || kind === 'notify_in_app' || kind === 'call_internal_api') return 'result'
  return 'system'
}

function defaultDescription(kind?: string, category?: string): string {
  if (kind === 'schedule') return '按计划时间自动执行'
  if (kind === 'webhook') return '由外部事件推送触发'
  if (kind === 'manual') return '由用户手动启动'
  if (kind === 'generate_ai_summary') return '调用 AI 生成安全摘要'
  if (kind === 'query_hfish_logs') return '读取 HFish 攻击日志作为输入'
  if (kind === 'condition') return '根据条件决定后续分支'
  if (kind === 'notify_in_app') return '将结果发送到站内通知'
  if (kind === 'call_internal_api') return '调用系统内已有 API'
  if (kind === 'write_log') return '将结果写入系统日志'
  return workflowCategoryMeta[category || 'system']?.label || '工作流节点'
}

function defaultHandles(category: string) {
  if (category === 'trigger') return { target: false, source: true }
  if (category === 'result') return { target: true, source: false }
  return { target: true, source: true }
}

function normalizeConfig(kind?: string, input?: Record<string, unknown>) {
  const config = input && typeof input === 'object' && !Array.isArray(input) ? { ...input } : {}

  if (kind === 'schedule') {
    return { interval_seconds: Number(config.interval_seconds ?? 60) || 60 }
  }
  if (kind === 'query_hfish_logs') {
    return {
      limit: Number(config.limit ?? 10) || 10,
      ...(config.service_name ? { service_name: String(config.service_name) } : {}),
    }
  }
  if (kind === 'condition') {
    return {
      source: String(config.source ?? 'trigger_payload'),
      path: String(config.path ?? 'severity'),
      operator: String(config.operator ?? 'eq'),
      expected: config.expected ?? 'high',
    }
  }
  if (kind === 'write_log') {
    return {
      level: String(config.level ?? 'INFO'),
      ...(config.message ? { message: String(config.message) } : {}),
    }
  }
  if (kind === 'notify_in_app') {
    return {
      ...(config.title ? { title: String(config.title) } : {}),
      ...(config.message ? { message: String(config.message) } : {}),
    }
  }
  if (kind === 'call_internal_api') {
    return {
      endpoint: String(config.endpoint ?? '/api/v1/overview/chain-status'),
      method: String(config.method ?? 'GET').toUpperCase(),
    }
  }
  if (kind === 'generate_ai_summary') {
    return {
      ...(config.prompt ? { prompt: String(config.prompt) } : {}),
    }
  }
  return config
}

function normalizeWorkflowNode(node: WorkflowNodeConfig): WorkflowNodeConfig {
  const kind = String(node.data?.kind || 'system')
  const rawType = String(node.data?.nodeType || node.type || inferCategory(kind))
  const category = String(node.data?.category || inferCategory(kind, rawType))

  return {
    ...node,
    type: 'workflow',
    data: {
      ...node.data,
      kind,
      nodeType: rawType,
      category,
      label: node.data?.label || '未命名节点',
      description: node.data?.description || defaultDescription(kind, category),
      handles: node.data?.handles || defaultHandles(category),
      config: normalizeConfig(kind, node.data?.config),
    },
  }
}

function normalizeWorkflowEdge(edge: WorkflowEdgeConfig): WorkflowEdgeConfig {
  return {
    ...edge,
    type: !edge.type || edge.type === 'animated' ? 'smoothstep' : edge.type,
  }
}

export function normalizeWorkflowDefinition(definition?: Partial<WorkflowDefinition> | null): WorkflowDefinition {
  return {
    nodes: Array.isArray(definition?.nodes) ? (definition.nodes as WorkflowNodeConfig[]).map(normalizeWorkflowNode) : [],
    edges: Array.isArray(definition?.edges) ? definition.edges.map(normalizeWorkflowEdge) : [],
  }
}

export function toPersistedWorkflowDefinition(definition?: Partial<WorkflowDefinition> | null): WorkflowDefinition {
  const normalized = normalizeWorkflowDefinition(definition)
  return {
    nodes: normalized.nodes.map((node): WorkflowNodeConfig => {
      const data: WorkflowNodeData = { ...(node.data || {}) }
      const rawType = String(data.nodeType || inferCategory(String(data.kind || ''), String(node.type || 'workflow')))
      delete data.nodeType
      delete data.category
      return {
        ...node,
        type: rawType,
        data,
      }
    }),
    edges: normalized.edges.map(normalizeWorkflowEdge),
  }
}

export function createDefaultWorkflowDefinition(): WorkflowDefinition {
  return {
    nodes: [
      createWorkflowNode({ kind: 'manual', type: 'trigger', label: '手动触发' }, { x: 0, y: 0 }, 'trigger-1'),
      createWorkflowNode({ kind: 'query_hfish_logs', type: 'threat', label: '读取 HFish 日志' }, { x: 360, y: 0 }, 'threat-1'),
      createWorkflowNode({ kind: 'write_log', type: 'result', label: '写入日志' }, { x: 720, y: 0 }, 'result-1'),
    ],
    edges: [
      { id: 'edge-1', source: 'trigger-1', target: 'threat-1', type: 'smoothstep' },
      { id: 'edge-2', source: 'threat-1', target: 'result-1', type: 'smoothstep' },
    ],
  }
}

export function createWorkflowNode(template: WorkflowCatalogNode, position: { x: number; y: number }, id: string): WorkflowNodeConfig {
  const category = inferCategory(template.kind, template.type)
  const common = {
    id,
    type: 'workflow',
    position,
  }

  return {
    ...common,
    data: {
      kind: template.kind,
      nodeType: template.type,
      category,
      label: template.label,
      description: defaultDescription(template.kind, category),
      handles: defaultHandles(category),
      config: normalizeConfig(template.kind),
    },
  }
}

export function summarizeNodeConfig(kind?: string, config?: Record<string, unknown>) {
  if (!config) return [] as string[]

  if (kind === 'schedule') return [`每 ${config.interval_seconds ?? 60} 秒执行`]
  if (kind === 'query_hfish_logs') {
    return [
      `最多读取 ${config.limit ?? 10} 条`,
      ...(config.service_name ? [`服务: ${String(config.service_name)}`] : []),
    ]
  }
  if (kind === 'condition') return [`${String(config.path ?? 'value')} ${String(config.operator ?? 'eq')} ${String(config.expected ?? '')}`]
  if (kind === 'write_log') return [`级别: ${String(config.level ?? 'INFO')}`, ...(config.message ? [String(config.message)] : [])]
  if (kind === 'notify_in_app') return [String(config.title ?? '站内通知'), ...(config.message ? [String(config.message)] : [])]
  if (kind === 'call_internal_api') return [`${String(config.method ?? 'GET')} ${String(config.endpoint ?? '/')}`]
  if (kind === 'generate_ai_summary' && config.prompt) return ['已配置 AI 提示词']
  return [] as string[]
}
