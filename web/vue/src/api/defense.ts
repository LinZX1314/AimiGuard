import { api } from './index'

export interface SwitchStatusItem {
  host: string
  port: number
  acl_number?: number
  enabled: boolean
  online: boolean
  error?: string
}

export interface SwitchStatuses {
  items: SwitchStatusItem[]
  total: number
  enabled: number
  online: number
}

export interface HFishSyncResult {
  success: boolean
  total?: number
  new?: number
  ban_count?: number
  error_code?: string
  error?: string
}

export const defenseApi = {
  async testHFish(): Promise<{ reachable: boolean; host_port?: string }> {
    const res: any = await api.post('/api/v1/defense/hfish/test', {})
    return res?.data ?? res
  },

  async triggerHFishSync(): Promise<HFishSyncResult> {
    const res: any = await api.post('/api/v1/defense/hfish/sync', {})
    return res?.data ?? res
  },

  async getSwitchStatuses(strict = false): Promise<SwitchStatuses> {
    const res: any = await api.get(`/api/v1/defense/switch/statuses?strict=${strict ? 1 : 0}`)
    return res?.data ?? res
  },
  
  async testHFishConnection(): Promise<{ reachable: boolean; host_port?: string }> {
    return this.testHFish()
  },
}
