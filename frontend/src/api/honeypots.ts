import { apiClient } from './client'

export interface HoneypotConfig {
  id: number
  name: string
  honeypot_type: string
  target_service: string
  bait_data?: string
  status: string
  managed_by: string
  external_id?: string
  created_at: string
  updated_at: string
}

export interface Honeytoken {
  id: number
  token_type: string
  value_hash: string
  deployed_location: string
  status: string
  triggered_at?: string
  attacker_ip?: string
  trace_id?: string
  created_at: string
}

export interface HoneypotAlert {
  id: number
  honeypot_id: number
  attack_type: string
  source_ip: string
  detail?: string
  created_at: string
}

export interface HoneypotSuggestion {
  recommended_type: string
  reason: string
  target_service: string
  priority: string
}

export const honeypotApi = {
  async list(params?: {
    status?: string
    page?: number
    page_size?: number
  }): Promise<{ total: number; items: HoneypotConfig[] }> {
    const res = await apiClient.get('/honeypots', { params })
    const d = (res as any)?.data ?? res
    return d as { total: number; items: HoneypotConfig[] }
  },

  async create(data: {
    name: string
    honeypot_type: string
    target_service: string
    bait_data?: string
  }): Promise<HoneypotConfig> {
    const res = await apiClient.post('/honeypots', data)
    const d = (res as any)?.data ?? res
    return d as HoneypotConfig
  },

  async update(id: number, data: {
    name?: string
    status?: string
    bait_data?: string
  }): Promise<HoneypotConfig> {
    const res = await apiClient.put(`/honeypots/${id}`, data)
    const d = (res as any)?.data ?? res
    return d as HoneypotConfig
  },

  async getAlerts(id: number, params?: {
    page?: number
    page_size?: number
  }): Promise<{ total: number; items: HoneypotAlert[] }> {
    const res = await apiClient.get(`/honeypots/${id}/alerts`, { params })
    const d = (res as any)?.data ?? res
    return d as { total: number; items: HoneypotAlert[] }
  },

  async getSuggestion(): Promise<HoneypotSuggestion> {
    const res = await apiClient.get('/honeypots/suggestion')
    const d = (res as any)?.data ?? res
    return d as HoneypotSuggestion
  },
}

export const honeytokenApi = {
  async list(params?: {
    status?: string
    page?: number
    page_size?: number
  }): Promise<{ total: number; items: Honeytoken[] }> {
    const res = await apiClient.get('/honeytokens', { params })
    const d = (res as any)?.data ?? res
    return d as { total: number; items: Honeytoken[] }
  },

  async generate(data: {
    token_type: string
    deployed_location: string
  }): Promise<Honeytoken> {
    const res = await apiClient.post('/honeytokens/generate', data)
    const d = (res as any)?.data ?? res
    return d as Honeytoken
  },

  async trigger(data: {
    value: string
    attacker_ip?: string
  }): Promise<any> {
    return apiClient.post('/honeytokens/trigger', data)
  },
}
