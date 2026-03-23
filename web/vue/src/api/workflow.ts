import { api } from '@/api/index'

export type WorkflowTriggerType = 'manual' | 'schedule' | 'webhook'

export type WorkflowNodeKind =
  | 'manual'
  | 'schedule'
  | 'webhook'
  | 'query_hfish_logs'
  | 'generate_ai_summary'
  | 'condition'
  | 'write_log'
  | 'notify_in_app'
  | 'call_internal_api'

export interface WorkflowNodeData {
  kind: WorkflowNodeKind | string
  nodeType?: string
  category?: string
  label: string
  description?: string
  config?: Record<string, unknown>
  handles?: { target?: boolean; source?: boolean }
}

export interface WorkflowNodeConfig {
  id: string
  type: string
  position: { x: number; y: number }
  data: WorkflowNodeData
}

export interface WorkflowEdgeConfig {
  id: string
  source: string
  target: string
  type?: string
  branch?: 'true' | 'false' | string
}

export interface WorkflowDefinition {
  nodes: WorkflowNodeConfig[]
  edges: WorkflowEdgeConfig[]
}

export interface WorkflowRecord {
  id: number
  name: string
  description: string
  category: string
  status: string
  definition: WorkflowDefinition
  trigger: Record<string, unknown>
  webhook_token?: string | null
  webhook_secret?: string | null
  webhook_signature_hint?: string
  template_id?: string | null
  template_name?: string | null
  next_run_at?: string | null
  last_run_at?: string | null
  created_at?: string
  updated_at?: string
}

export interface WorkflowRunStepRecord {
  id: number
  node_id: string
  node_type: string
  node_name: string
  status: string
  started_at?: string
  ended_at?: string
  input?: Record<string, unknown>
  output?: Record<string, unknown>
  error_message?: string
}

export interface WorkflowRunRecord {
  id: number
  workflow_id: number
  trigger_type: string
  trigger_payload?: Record<string, unknown>
  status: string
  summary?: string
  error_message?: string
  started_at?: string
  ended_at?: string
  steps_count?: number
  notifications?: Array<Record<string, unknown>>
  steps?: WorkflowRunStepRecord[]
}

export interface WorkflowCatalogCategory {
  id: string
  label: string
}

export interface WorkflowCatalogNode {
  kind: WorkflowNodeKind | string
  type: string
  label: string
}

export interface WorkflowTemplateRecord {
  id: string
  name: string
  description: string
  category: string
  trigger_type: WorkflowTriggerType
  tags: string[]
  definition: WorkflowDefinition
  defaults?: Record<string, unknown>
}

export type WorkflowRunDetail = WorkflowRunRecord
export type WorkflowTemplate = WorkflowTemplateRecord

const workflowApiBase = {
  catalog: () => api.get<{ categories: WorkflowCatalogCategory[]; nodes: WorkflowCatalogNode[] }>('/api/v1/workflows/catalog'),
  templates: () => api.get<WorkflowTemplateRecord[]>('/api/v1/workflows/templates'),
  instantiateTemplate: (templateId: string, payload?: Record<string, unknown>) =>
    api.post<WorkflowRecord>(`/api/v1/workflows/templates/${templateId}/instantiate`, payload ?? {}),
  list: () => api.get<WorkflowRecord[]>('/api/v1/workflows'),
  create: (payload: Record<string, unknown>) => api.post<WorkflowRecord>('/api/v1/workflows', payload),
  update: (id: number, payload: Record<string, unknown>) => api.put<WorkflowRecord>(`/api/v1/workflows/${id}`, payload),
  publish: (id: number) => api.post<WorkflowRecord>(`/api/v1/workflows/${id}/publish`, {}),
  remove: (id: number) => api.delete<{ deleted: boolean }>(`/api/v1/workflows/${id}`),
  run: (id: number, payload?: Record<string, unknown>) => api.post<WorkflowRunRecord>(`/api/v1/workflows/${id}/run`, payload ?? {}),
  runs: (id: number) => api.get<WorkflowRunRecord[]>(`/api/v1/workflows/${id}/runs`),
  runDetail: (runId: number) => api.get<WorkflowRunRecord>(`/api/v1/workflows/runs/${runId}`),
}

export const workflowApi = {
  ...workflowApiBase,
  listTemplates: workflowApiBase.templates,
  listRuns: workflowApiBase.runs,
  getRunDetail: workflowApiBase.runDetail,
}
