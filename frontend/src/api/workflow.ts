import { apiClient } from './client'

export type WorkflowDefinitionState = 'DRAFT' | 'VALIDATED' | 'PUBLISHED' | 'ARCHIVED' | string

export interface WorkflowDefinitionItem {
  id: number
  workflow_key: string
  name: string
  description: string | null
  definition_state: WorkflowDefinitionState
  latest_version: number
  published_version: number | null
  version_tag: number
  created_by: string | null
  updated_by: string | null
  created_at: string | null
  updated_at: string | null
}

export interface WorkflowVersionSnapshot {
  id: number
  version: number
  definition_state: WorkflowDefinitionState
  change_note: string | null
  created_by: string | null
  created_at: string | null
  updated_at: string | null
}

export interface WorkflowRetryPolicy {
  max_retries: number
  backoff_seconds: number
  backoff_multiplier: number
  retry_on: string[]
}

export interface WorkflowNode {
  id: string
  type: string
  name: string
  config: Record<string, unknown>
  timeout: number
  retry_policy: WorkflowRetryPolicy
}

export interface WorkflowEdge {
  from: string
  to: string
  condition: string
  priority: number
}

export interface WorkflowDsl {
  schema_version: string
  workflow_id: string
  version: number
  name: string
  description?: string
  status: WorkflowDefinitionState
  context: {
    inputs: Record<string, unknown>
    outputs: Record<string, unknown>
    trace_id?: string
  }
  runtime: {
    initial_state: string
    terminal_states: string[]
    state_enum: string[]
  }
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
  metadata?: Record<string, unknown>
}

export interface WorkflowListResult {
  total: number
  page: number
  page_size: number
  items: WorkflowDefinitionItem[]
}

export interface WorkflowDetailResult {
  workflow: WorkflowDefinitionItem
  version: WorkflowVersionSnapshot
  dsl: WorkflowDsl
}

export interface WorkflowListParams {
  page?: number
  page_size?: number
  keyword?: string
  definition_state?: string
}

export interface WorkflowCreatePayload {
  workflow_key: string
  name: string
  description?: string
  dsl: Record<string, unknown>
  change_note?: string
}

export interface WorkflowUpdatePayload {
  version_tag: number
  name?: string
  description?: string
  dsl: Record<string, unknown>
  change_note?: string
}

export interface WorkflowPublishPayload {
  version_tag?: number
  canary_percent: number
  effective_at?: string
  approval_reason: string
  approval_passed: boolean
  confirmation_text: string
  trace_id?: string
}

export interface WorkflowPublishResult {
  workflow_id: number
  workflow_key: string
  version: number
  published_version: number | null
  previous_published_version: number | null
  definition_state: WorkflowDefinitionState
  canary_percent: number
  effective_at: string | null
  approval_reason: string
  trace_id: string | null
}

export interface WorkflowRollbackPayload {
  target_version: number
  reason: string
  confirmation_text: string
  trace_id?: string
}

export interface WorkflowRollbackResult {
  workflow_id: number
  workflow_key: string
  rolled_back_to_version: number
  previous_published_version: number | null
  published_version: number | null
  definition_state: WorkflowDefinitionState
  reason: string
  trace_id: string | null
}

export interface WorkflowValidateIssue {
  code: string
  category: string
  level: string
  message: string
  path: string
  node_id?: string
  value?: unknown
  allowed_values?: string[]
}

export interface WorkflowValidateSummary {
  error_count: number
  warning_count: number
  categories: Record<string, number>
}

export interface WorkflowValidateResult {
  workflow_id: number
  workflow_key: string
  version: number
  valid: boolean
  errors: WorkflowValidateIssue[]
  warnings: WorkflowValidateIssue[]
  summary: WorkflowValidateSummary
}

const toNumber = (value: unknown, fallback: number): number => {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

const toStringOrNull = (value: unknown): string | null => {
  if (typeof value === 'string') return value
  return null
}

const normalizeValidationIssue = (value: unknown): WorkflowValidateIssue => {
  const record = (value && typeof value === 'object' ? value : {}) as Record<string, unknown>
  return {
    code: typeof record.code === 'string' ? record.code : 'WF_UNKNOWN',
    category: typeof record.category === 'string' ? record.category : 'unknown',
    level: typeof record.level === 'string' ? record.level : 'error',
    message: typeof record.message === 'string' ? record.message : String(value ?? '未知校验错误'),
    path: typeof record.path === 'string' ? record.path : 'dsl',
    node_id: typeof record.node_id === 'string' ? record.node_id : undefined,
    value: record.value,
    allowed_values: Array.isArray(record.allowed_values) ? record.allowed_values.map((item) => String(item)) : undefined,
  }
}

const normalizePublishResult = (value: unknown, workflowId: number): WorkflowPublishResult => {
  const record = (value && typeof value === 'object' ? value : {}) as Record<string, unknown>
  return {
    workflow_id: toNumber(record.workflow_id, workflowId),
    workflow_key: typeof record.workflow_key === 'string' ? record.workflow_key : '',
    version: toNumber(record.version, 0),
    published_version: record.published_version == null ? null : toNumber(record.published_version, 0),
    previous_published_version: record.previous_published_version == null ? null : toNumber(record.previous_published_version, 0),
    definition_state: typeof record.definition_state === 'string' ? record.definition_state : 'PUBLISHED',
    canary_percent: toNumber(record.canary_percent, 100),
    effective_at: toStringOrNull(record.effective_at),
    approval_reason: typeof record.approval_reason === 'string' ? record.approval_reason : '',
    trace_id: toStringOrNull(record.trace_id),
  }
}

const normalizeRollbackResult = (value: unknown, workflowId: number): WorkflowRollbackResult => {
  const record = (value && typeof value === 'object' ? value : {}) as Record<string, unknown>
  return {
    workflow_id: toNumber(record.workflow_id, workflowId),
    workflow_key: typeof record.workflow_key === 'string' ? record.workflow_key : '',
    rolled_back_to_version: toNumber(record.rolled_back_to_version, 0),
    previous_published_version: record.previous_published_version == null ? null : toNumber(record.previous_published_version, 0),
    published_version: record.published_version == null ? null : toNumber(record.published_version, 0),
    definition_state: typeof record.definition_state === 'string' ? record.definition_state : 'PUBLISHED',
    reason: typeof record.reason === 'string' ? record.reason : '',
    trace_id: toStringOrNull(record.trace_id),
  }
}

const normalizeDefinition = (value: unknown): WorkflowDefinitionItem => {
  const record = (value && typeof value === 'object' ? value : {}) as Record<string, unknown>
  const id = toNumber(record.id, 0)
  const latestVersion = toNumber(record.latest_version, 1)
  const publishedVersion = record.published_version == null ? null : toNumber(record.published_version, 0)
  const versionTag = toNumber(record.version_tag, latestVersion)
  return {
    id,
    workflow_key: typeof record.workflow_key === 'string' ? record.workflow_key : `workflow-${id || 'unknown'}`,
    name: typeof record.name === 'string' ? record.name : 'Untitled Workflow',
    description: toStringOrNull(record.description),
    definition_state: typeof record.definition_state === 'string' ? record.definition_state : 'DRAFT',
    latest_version: latestVersion,
    published_version: publishedVersion,
    version_tag: versionTag,
    created_by: toStringOrNull(record.created_by),
    updated_by: toStringOrNull(record.updated_by),
    created_at: toStringOrNull(record.created_at),
    updated_at: toStringOrNull(record.updated_at),
  }
}

const normalizeVersion = (value: unknown): WorkflowVersionSnapshot => {
  const record = (value && typeof value === 'object' ? value : {}) as Record<string, unknown>
  return {
    id: toNumber(record.id, 0),
    version: toNumber(record.version, 1),
    definition_state: typeof record.definition_state === 'string' ? record.definition_state : 'DRAFT',
    change_note: toStringOrNull(record.change_note),
    created_by: toStringOrNull(record.created_by),
    created_at: toStringOrNull(record.created_at),
    updated_at: toStringOrNull(record.updated_at),
  }
}

const normalizeDsl = (value: unknown): WorkflowDsl => {
  const record = (value && typeof value === 'object' ? value : {}) as Record<string, any>
  const nodes = Array.isArray(record.nodes) ? record.nodes : []
  const edges = Array.isArray(record.edges) ? record.edges : []
  return {
    schema_version: typeof record.schema_version === 'string' ? record.schema_version : '1.0.0',
    workflow_id: typeof record.workflow_id === 'string' ? record.workflow_id : '',
    version: toNumber(record.version, 1),
    name: typeof record.name === 'string' ? record.name : 'Untitled Workflow',
    description: typeof record.description === 'string' ? record.description : undefined,
    status: typeof record.status === 'string' ? record.status : 'DRAFT',
    context: {
      inputs: record.context && typeof record.context === 'object' && record.context.inputs && typeof record.context.inputs === 'object'
        ? record.context.inputs
        : {},
      outputs: record.context && typeof record.context === 'object' && record.context.outputs && typeof record.context.outputs === 'object'
        ? record.context.outputs
        : {},
      trace_id: record.context && typeof record.context === 'object' && typeof record.context.trace_id === 'string'
        ? record.context.trace_id
        : undefined,
    },
    runtime: {
      initial_state: record.runtime && typeof record.runtime === 'object' && typeof record.runtime.initial_state === 'string'
        ? record.runtime.initial_state
        : 'QUEUED',
      terminal_states: record.runtime && typeof record.runtime === 'object' && Array.isArray(record.runtime.terminal_states)
        ? record.runtime.terminal_states.map((item: unknown) => String(item))
        : [],
      state_enum: record.runtime && typeof record.runtime === 'object' && Array.isArray(record.runtime.state_enum)
        ? record.runtime.state_enum.map((item: unknown) => String(item))
        : [],
    },
    nodes: nodes.map((node: Record<string, any>, index: number) => ({
      id: typeof node?.id === 'string' ? node.id : `node-${index}`,
      type: typeof node?.type === 'string' ? node.type : 'action',
      name: typeof node?.name === 'string' ? node.name : `Node ${index + 1}`,
      config: node?.config && typeof node.config === 'object' ? node.config : {},
      timeout: toNumber(node?.timeout, 30),
      retry_policy: {
        max_retries: toNumber(node?.retry_policy?.max_retries, 0),
        backoff_seconds: toNumber(node?.retry_policy?.backoff_seconds, 1),
        backoff_multiplier: toNumber(node?.retry_policy?.backoff_multiplier, 1),
        retry_on: Array.isArray(node?.retry_policy?.retry_on)
          ? node.retry_policy.retry_on.map((item: unknown) => String(item))
          : [],
      },
    })),
    edges: edges.map((edge: Record<string, any>) => ({
      from: typeof edge?.from === 'string' ? edge.from : '',
      to: typeof edge?.to === 'string' ? edge.to : '',
      condition: typeof edge?.condition === 'string' ? edge.condition : 'true',
      priority: toNumber(edge?.priority, 0),
    })),
    metadata: record.metadata && typeof record.metadata === 'object' ? record.metadata : undefined,
  }
}

export const workflowApi = {
  async getWorkflows(params?: WorkflowListParams): Promise<WorkflowListResult> {
    const data = await apiClient.get('/workflows', { params }) as unknown
    const record = (data && typeof data === 'object' ? data : {}) as Record<string, unknown>
    const items = Array.isArray(record.items) ? record.items : []
    return {
      total: toNumber(record.total, 0),
      page: toNumber(record.page, params?.page ?? 1),
      page_size: toNumber(record.page_size, params?.page_size ?? 20),
      items: items.map((item) => normalizeDefinition(item)),
    }
  },

  async getWorkflowDetail(workflowId: number): Promise<WorkflowDetailResult> {
    const data = await apiClient.get(`/workflows/${workflowId}`) as unknown
    const record = (data && typeof data === 'object' ? data : {}) as Record<string, unknown>
    return {
      workflow: normalizeDefinition(record.workflow),
      version: normalizeVersion(record.version),
      dsl: normalizeDsl(record.dsl),
    }
  },

  async createWorkflow(payload: WorkflowCreatePayload): Promise<WorkflowDefinitionItem> {
    const data = await apiClient.post('/workflows', payload) as unknown
    const record = (data && typeof data === 'object' ? data : {}) as Record<string, unknown>
    return normalizeDefinition(record)
  },

  async updateWorkflow(workflowId: number, payload: WorkflowUpdatePayload): Promise<WorkflowDefinitionItem> {
    const data = await apiClient.put(`/workflows/${workflowId}`, payload) as unknown
    const record = (data && typeof data === 'object' ? data : {}) as Record<string, unknown>
    return normalizeDefinition(record)
  },

  async validateWorkflow(workflowId: number): Promise<WorkflowValidateResult> {
    const data = await apiClient.post(`/workflows/${workflowId}/validate`) as unknown
    const record = (data && typeof data === 'object' ? data : {}) as Record<string, unknown>
    const errors = Array.isArray(record.errors) ? record.errors.map((e: unknown) => normalizeValidationIssue(e)) : []
    const warnings = Array.isArray(record.warnings) ? record.warnings.map((e: unknown) => normalizeValidationIssue(e)) : []
    const summaryRecord = (record.summary && typeof record.summary === 'object' ? record.summary : {}) as Record<string, unknown>
    return {
      workflow_id: toNumber(record.workflow_id, workflowId),
      workflow_key: typeof record.workflow_key === 'string' ? record.workflow_key : '',
      version: toNumber(record.version, 0),
      valid: record.valid === true,
      errors,
      warnings,
      summary: {
        error_count: toNumber(summaryRecord.error_count, errors.length),
        warning_count: toNumber(summaryRecord.warning_count, warnings.length),
        categories: summaryRecord.categories && typeof summaryRecord.categories === 'object'
          ? Object.fromEntries(Object.entries(summaryRecord.categories).map(([key, value]) => [key, toNumber(value, 0)]))
          : {},
      },
    }
  },

  async publishWorkflow(workflowId: number, payload: WorkflowPublishPayload): Promise<WorkflowPublishResult> {
    const data = await apiClient.post(`/workflows/${workflowId}/publish`, payload) as unknown
    return normalizePublishResult(data, workflowId)
  },

  async rollbackWorkflow(workflowId: number, payload: WorkflowRollbackPayload): Promise<WorkflowRollbackResult> {
    const data = await apiClient.post(`/workflows/${workflowId}/rollback`, payload) as unknown
    return normalizeRollbackResult(data, workflowId)
  },
}
