import { apiClient } from './client'

export interface Plugin {
  id: number
  name: string
  plugin_type: string
  endpoint: string
  enabled: boolean
  source_url?: string
  declared_permissions?: string
  risk_score?: number
  created_at: string
}

export interface PluginVerifyResult {
  safe: boolean
  risk_level: string
  reason: string
  checks: Record<string, any>
}

export interface PluginCallLog {
  id: number
  plugin_id: number
  tool_name: string
  args_hash: string
  result_hash?: string
  latency_ms?: number
  status: string
  block_reason?: string
  trace_id: string
  created_at: string
}

export interface PluginAnomaly {
  type: string
  level: string
  message: string
  detected_at: string
}

export interface PluginPermissions {
  declared_permissions: string
  actual_calls_json?: string
  risk_score: number
}

export const pluginsApi = {
  async verify(data: {
    source_url: string
    publisher_signature?: string
    content_hash?: string
    content?: string
  }): Promise<PluginVerifyResult> {
    const res = await apiClient.post('/plugins/verify', data)
    const d = (res as any)?.data ?? res
    return d as PluginVerifyResult
  },

  async getBlacklist(): Promise<string[]> {
    const res = await apiClient.get('/plugins/blacklist')
    const d = (res as any)?.data ?? res
    return d as string[]
  },

  async addBlacklist(data: { source: string }): Promise<any> {
    return apiClient.post('/plugins/blacklist', data)
  },

  async getPermissions(pluginId: number): Promise<PluginPermissions> {
    const res = await apiClient.get(`/plugins/${pluginId}/permissions`)
    const d = (res as any)?.data ?? res
    return d as PluginPermissions
  },

  async updatePermissions(pluginId: number, data: {
    declared_permissions: string
  }): Promise<any> {
    return apiClient.put(`/plugins/${pluginId}/permissions`, data)
  },

  async getCallLogs(pluginId: number, params?: {
    page?: number
    page_size?: number
  }): Promise<{ total: number; items: PluginCallLog[] }> {
    const res = await apiClient.get(`/plugins/${pluginId}/call-logs`, { params })
    const d = (res as any)?.data ?? res
    return d as { total: number; items: PluginCallLog[] }
  },

  async getAnomalies(pluginId: number, params?: {
    page?: number
    page_size?: number
  }): Promise<{ total: number; items: PluginAnomaly[] }> {
    const res = await apiClient.get(`/plugins/${pluginId}/anomalies`, { params })
    const d = (res as any)?.data ?? res
    return d as { total: number; items: PluginAnomaly[] }
  },
}
