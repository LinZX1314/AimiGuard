import { apiClient } from './client'

export interface DeviceCredential {
  id: number
  device_id: number
  username: string
  created_at: string | null
  updated_at: string | null
}

export interface DeviceInfo {
  id: number
  name: string
  ip: string
  port: number
  vendor: string
  device_type: string | null
  enabled: boolean
  description: string | null
  credentials: DeviceCredential[]
  created_at: string | null
  updated_at: string | null
}

export interface DeviceCreatePayload {
  name: string
  ip: string
  port?: number
  vendor: string
  device_type?: string
  enabled?: boolean
  description?: string
}

export interface DeviceUpdatePayload {
  name?: string
  ip?: string
  port?: number
  vendor?: string
  device_type?: string
  enabled?: boolean
  description?: string
}

export const deviceApi = {
  async list(): Promise<DeviceInfo[]> {
    return apiClient.get('/device/list')
  },

  async create(payload: DeviceCreatePayload) {
    return apiClient.post('/device/create', payload)
  },

  async update(deviceId: number, payload: DeviceUpdatePayload) {
    return apiClient.put(`/device/${deviceId}`, payload)
  },

  async remove(deviceId: number) {
    return apiClient.delete(`/device/${deviceId}`)
  },

  async addCredential(deviceId: number, username: string, password: string) {
    return apiClient.post(`/device/${deviceId}/credentials`, { username, password })
  },

  async updateCredential(deviceId: number, credId: number, payload: { username?: string; password?: string }) {
    return apiClient.put(`/device/${deviceId}/credentials/${credId}`, payload)
  },

  async removeCredential(deviceId: number, credId: number) {
    return apiClient.delete(`/device/${deviceId}/credentials/${credId}`)
  },

  async testConnection(deviceId: number): Promise<{ ok: boolean; message: string }> {
    const res: any = await apiClient.post(`/device/${deviceId}/test`)
    return res?.data ?? res
  },
}
