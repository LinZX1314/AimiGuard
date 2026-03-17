import { api } from './index'

export interface ChainStatus {
  hfish_sync: boolean
  nmap_scan: boolean
  ai_analysis: boolean
  acl_auto_ban: boolean
}

export const overviewApi = {
  async getChainStatus(): Promise<ChainStatus> {
    return api.get<ChainStatus>('/api/v1/overview/chain-status')
  },
}
