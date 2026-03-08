import { apiClient } from './client'

export interface ThreatIntelSource {
  id: number
  name: string
  source_type: string
  enabled: boolean
  last_sync?: string
}

export interface CVEDetail {
  vuln_id: string
  cvss_score?: number
  cvss_vector?: string
  epss_score?: number
  epss_percentile?: number
  is_in_kev?: boolean
  affected_versions?: string
  patch_url?: string
  exploit_available?: boolean
  exploit_sources?: string
}

export interface ThreatIntelOverview {
  total_cves: number
  kev_hits: number
  epss_top10: any[]
  findings_total: number
  enriched_count: number
}

export interface IntelQueryResult {
  found: boolean
  data: Record<string, any>
}

export const threatIntelApi = {
  async getOverview(): Promise<ThreatIntelOverview> {
    const res = await apiClient.get('/threat-intel/overview')
    const d = (res as any)?.data ?? res
    return d as ThreatIntelOverview
  },

  async queryCVE(cveId: string): Promise<CVEDetail> {
    const res = await apiClient.get(`/threat-intel/cve/${cveId}`)
    const d = (res as any)?.data ?? res
    return d as CVEDetail
  },

  async queryIP(ip: string): Promise<IntelQueryResult> {
    const res = await apiClient.get(`/threat-intel/ip/${ip}`)
    const d = (res as any)?.data ?? res
    return d as IntelQueryResult
  },

  async getSources(): Promise<ThreatIntelSource[]> {
    const res = await apiClient.get('/threat-intel/sources')
    const d = (res as any)?.data ?? res
    return (Array.isArray(d) ? d : d?.items ?? []) as ThreatIntelSource[]
  },

  async registerSource(data: {
    name: string
    source_type: string
    config?: Record<string, any>
  }): Promise<any> {
    return apiClient.post('/threat-intel/sources', data)
  },
}
