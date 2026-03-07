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

let aiConfigEndpointAvailable: boolean | null = null
let ttsConfigEndpointAvailable: boolean | null = null

const systemGet = async <T>(path: string): Promise<T> => {
  try {
    const res = await apiClient.get(`/api/system${path}`, { baseURL: '' })
    return res as T
  } catch (error: any) {
    if (error?.response?.status === 404) {
      const res = await apiClient.get(`/api/v1/system${path}`, { baseURL: '' })
      return res as T
    }
    throw error
  }
}

const systemPost = async <T>(path: string, payload: unknown): Promise<T> => {
  try {
    const res = await apiClient.post(`/api/system${path}`, payload, { baseURL: '' })
    return res as T
  } catch (error: any) {
    if (error?.response?.status === 404) {
      const res = await apiClient.post(`/api/v1/system${path}`, payload, { baseURL: '' })
      return res as T
    }
    throw error
  }
}

const createDefaultAIConfig = (): AIAPIConfig => ({
  provider: 'ollama',
  base_url: 'http://localhost:11434',
  model_name: 'llama2',
  enabled: true,
  api_key_configured: false,
})

const createDefaultTTSConfig = (): TTSConfig => ({
  provider: 'local',
  endpoint: null,
  model_name: 'local-tts-v1',
  voice_model: 'local-tts-v1',
  enabled: true,
})

export const systemApi = {
  getProfile: (): Promise<SystemProfile> => apiClient.get('/system/profile') as any,
  getAIConfig: async (): Promise<AIAPIConfig> => {
    if (aiConfigEndpointAvailable === false) {
      return createDefaultAIConfig()
    }

    try {
      const res = await systemGet<AIAPIConfig>('/ai-config')
      aiConfigEndpointAvailable = true
      return (res as AIAPIConfig) ?? createDefaultAIConfig()
    } catch (error: any) {
      if (error?.response?.status === 404) {
        aiConfigEndpointAvailable = false
        return createDefaultAIConfig()
      }
      throw error
    }
  },
  saveAIConfig: (payload: AIAPIConfigRequest): Promise<AIAPIConfig> => systemPost<AIAPIConfig>('/ai-config', payload),
  getTTSConfig: async (): Promise<TTSConfig> => {
    if (ttsConfigEndpointAvailable === false) {
      return createDefaultTTSConfig()
    }

    try {
      const res = await systemGet<TTSConfig>('/tts-config')
      ttsConfigEndpointAvailable = true
      return (res as TTSConfig) ?? createDefaultTTSConfig()
    } catch (error: any) {
      if (error?.response?.status === 404) {
        ttsConfigEndpointAvailable = false
        return createDefaultTTSConfig()
      }
      throw error
    }
  },
  saveTTSConfig: (payload: TTSConfigRequest): Promise<TTSConfig> => systemPost<TTSConfig>('/tts-config', payload),
}
