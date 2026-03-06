import { apiClient } from './client'

export interface FirewallConfig {
  enabled: boolean
  api_base_url: string | null
  default_vendor: string
  default_policy_id: string | null
  timeout_seconds: number
  has_custom_sign_secret: boolean
}

export interface FirewallConfigRequest {
  enabled: boolean
  api_base_url?: string
  default_vendor: string
  default_policy_id?: string
  timeout_seconds: number
  sign_secret?: string
}

export const firewallApi = {
  async getConfig(): Promise<FirewallConfig> {
    return apiClient.get('/firewall/config')
  },

  async saveConfig(config: FirewallConfigRequest) {
    return apiClient.post('/firewall/config', config)
  },
}
