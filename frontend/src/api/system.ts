import { apiClient } from './client'

export interface SystemProfile {
  username: string
  email?: string | null
  full_name?: string | null
  role: string
  permissions: string[]
}

export interface AIAPIConfig {
  provider: string
  base_url: string
  model_name: string
  enabled: boolean
  api_key_configured: boolean
}

export interface AIAPIConfigRequest {
  provider: string
  base_url: string
  model_name: string
  api_key?: string
  enabled: boolean
}

export interface TTSConfig {
  provider: string
  endpoint: string | null
  model_name: string
  voice_model: string
  enabled: boolean
}

export interface TTSConfigRequest {
  provider: string
  endpoint?: string
  model_name: string
  voice_model?: string
  enabled: boolean
}

export const systemApi = {
  getProfile: (): Promise<SystemProfile> => apiClient.get('/system/profile') as any,
  getAIConfig: async (): Promise<AIAPIConfig> => {
    try {
      return await apiClient.get('/system/ai-config') as any
    } catch (error: any) {
      if (error?.response?.status === 404) {
        const res = await apiClient.get('/system/ai-config', { baseURL: '/api' })
        return res as AIAPIConfig
      }
      throw error
    }
  },
  saveAIConfig: async (payload: AIAPIConfigRequest): Promise<AIAPIConfig> => {
    try {
      return await apiClient.post('/system/ai-config', payload) as any
    } catch (error: any) {
      if (error?.response?.status === 404) {
        const res = await apiClient.post('/system/ai-config', payload, { baseURL: '/api' })
        return res as AIAPIConfig
      }
      throw error
    }
  },
  getTTSConfig: async (): Promise<TTSConfig> => {
    try {
      return await apiClient.get('/system/tts-config') as any
    } catch (error: any) {
      if (error?.response?.status === 404) {
        const res = await apiClient.get('/system/tts-config', { baseURL: '/api' })
        return res as TTSConfig
      }
      throw error
    }
  },
  saveTTSConfig: async (payload: TTSConfigRequest): Promise<TTSConfig> => {
    try {
      return await apiClient.post('/system/tts-config', payload) as any
    } catch (error: any) {
      if (error?.response?.status === 404) {
        const res = await apiClient.post('/system/tts-config', payload, { baseURL: '/api' })
        return res as TTSConfig
      }
      throw error
    }
  },
}
