import type { WorkflowCatalogNode, WorkflowDefinition, WorkflowEdgeConfig, WorkflowNodeConfig } from '@/api/workflow'

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

function normalizeWorkflowEdge(edge: WorkflowEdgeConfig): WorkflowEdgeConfig {
  return {
    ...edge,
    type: !edge.type || edge.type === 'animated' ? 'smoothstep' : edge.type,
  }
}

export function normalizeWorkflowDefinition(definition?: Partial<WorkflowDefinition> | null): WorkflowDefinition {
  return {
    nodes: Array.isArray(definition?.nodes) ? (definition?.nodes as WorkflowNodeConfig[]) : [],
    edges: Array.isArray(definition?.edges) ? definition.edges.map(normalizeWorkflowEdge) : [],
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
  const common = {
    id,
    type: 'workflow',
    position,
  }

  if (template.type === 'trigger') {
    return {
      ...common,
      data: {
        kind: template.kind,
        label: template.label,
        description: template.kind === 'schedule' ? '按计划时间自动执行' : template.kind === 'webhook' ? '由外部事件推送触发' : '由用户手动启动',
        handles: { target: false, source: true },
        config: template.kind === 'schedule' ? { interval_seconds: 60 } : {},
      },
    }
  }

  if (template.type === 'result') {
    return {
      ...common,
      data: {
        kind: template.kind,
        label: template.label,
        description: template.kind === 'notify_in_app' ? '将结果发送到站内通知' : template.kind === 'call_internal_api' ? '调用系统内已有 API' : '将结果写入系统日志',
        handles: { target: true, source: false },
        config: template.kind === 'write_log' ? { level: 'INFO' } : {},
      },
    }
  }

  return {
    ...common,
    data: {
      kind: template.kind,
      label: template.label,
      description: template.kind === 'generate_ai_summary' ? '调用 AI 生成安全摘要' : '读取 HFish 攻击日志作为输入',
      handles: { target: true, source: true },
      config: template.kind === 'query_hfish_logs' ? { limit: 10 } : {},
    },
  }
}
