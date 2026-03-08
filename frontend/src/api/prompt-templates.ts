import { apiClient } from './client'

export interface PromptTemplate {
  id: number
  template_key: string
  version: number
  content: string
  description?: string
  is_active: boolean
  approved_by?: string
  approved_at?: string
  created_by?: string
  created_at: string
}

export interface PromptTemplateListResult {
  total: number
  page: number
  items: PromptTemplate[]
}

export interface PromptTemplateDiff {
  from_version: number
  to_version: number
  diff: string
}

export interface PromptTemplateVersions {
  template_key: string
  total_versions: number
  versions: PromptTemplate[]
}

export const promptTemplateApi = {
  async list(params?: {
    template_key?: string
    active_only?: boolean
    page?: number
    page_size?: number
  }): Promise<PromptTemplateListResult> {
    const res = await apiClient.get('/ai/prompt-templates', { params })
    const d = (res as any)?.data ?? res
    return d as PromptTemplateListResult
  },

  async get(id: number): Promise<PromptTemplate> {
    const res = await apiClient.get(`/ai/prompt-templates/${id}`)
    const d = (res as any)?.data ?? res
    return d as PromptTemplate
  },

  async create(data: {
    template_key: string
    content: string
    description?: string
  }): Promise<PromptTemplate> {
    const res = await apiClient.post('/ai/prompt-templates', data)
    const d = (res as any)?.data ?? res
    return d as PromptTemplate
  },

  async update(id: number, data: {
    content: string
    description?: string
  }): Promise<{ id: number; template_key: string; version: number; diff: string }> {
    const res = await apiClient.put(`/ai/prompt-templates/${id}`, data)
    const d = (res as any)?.data ?? res
    return d as any
  },

  async getDiff(id: number): Promise<PromptTemplateDiff> {
    const res = await apiClient.get(`/ai/prompt-templates/${id}/diff`)
    const d = (res as any)?.data ?? res
    return d as PromptTemplateDiff
  },

  async getVersions(key: string): Promise<PromptTemplateVersions> {
    const res = await apiClient.get(`/ai/prompt-templates/key/${key}/versions`)
    const d = (res as any)?.data ?? res
    return d as PromptTemplateVersions
  },
}
