import { api } from './index'

export const TERMINAL_COUNTER_SERVICE_NAME = '反制蜜罐·终端取证'

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

export interface TerminalEvidenceItem {
  event_key: string
  source: 'terminal'
  severity: 'high'
  severity_label: string
  attack_kind: string
  service_name: string
  attack_source: string
  capture_types: Array<'screenshot' | 'camera'>
  capture_summary: string
  is_combined: boolean
  preview_url: string
  jump_path: string
  attack_count: number
  filename: string
  url: string
  screenshot_filename: string
  screenshot_url: string
  camera_filename: string
  camera_url: string
  report_ip: string
  upload_api: string
  client_time: string
  client_name: string
  client_host: string
  terminal_ip: string
  client_ip: string
  time: string
  mtime: number
}

export interface TerminalEvidencePayload {
  items: TerminalEvidenceItem[]
  total: number
  high_count: number
}

function normalizeTerminalItems(source: any[]): TerminalEvidenceItem[] {
  return source.map((item) => ({
    event_key: item.event_key || item.filename || `${item.time || ''}-${item.mtime || 0}`,
    source: 'terminal',
    severity: 'high',
    severity_label: item.severity_label || '高危回传',
    attack_kind: item.attack_kind || 'counter_honeypot',
    service_name: item.service_name || TERMINAL_COUNTER_SERVICE_NAME,
    attack_source: item.attack_source || item.report_ip || item.terminal_ip || item.client_ip || '终端取证节点',
    capture_types: Array.isArray(item.capture_types)
      ? item.capture_types.map((x: any) => (x === 'camera' ? 'camera' : 'screenshot'))
      : [item.type === 'camera' ? 'camera' : 'screenshot'],
    capture_summary: item.capture_summary || (item.type === 'camera' ? '摄像头' : '截图'),
    is_combined: Boolean(item.is_combined) || (Array.isArray(item.capture_types) && item.capture_types.length > 1),
    preview_url: item.preview_url || item.screenshot_url || item.camera_url || item.url || '',
    jump_path: item.jump_path || '/screenshots',
    attack_count: Number(item.attack_count || 1),
    filename: item.filename || '-',
    url: item.url || item.preview_url || item.screenshot_url || item.camera_url || '',
    screenshot_filename: item.screenshot_filename || (item.type === 'screenshot' ? item.filename || '' : ''),
    screenshot_url: item.screenshot_url || (item.type === 'screenshot' ? item.url || '' : ''),
    camera_filename: item.camera_filename || (item.type === 'camera' ? item.filename || '' : ''),
    camera_url: item.camera_url || (item.type === 'camera' ? item.url || '' : ''),
    report_ip: item.report_ip || item.terminal_ip || item.client_ip || '-',
    upload_api: item.report_ip || item.upload_api || item.api || item.terminal_ip || item.client_ip || '-',
    client_time: item.client_time || item.time || '-',
    client_name: item.client_name || '终端取证客户端',
    client_host: item.client_host || '',
    terminal_ip: item.terminal_ip || item.client_ip || '',
    client_ip: item.terminal_ip || item.client_ip || '',
    time: item.time || '-',
    mtime: Number(item.mtime || 0),
  }))
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

  async getTerminalEvidence(limit = 200): Promise<TerminalEvidencePayload> {
    try {
      // 优先使用上传列表：兼容旧后端并避免 defense 端点缺失时产生 404 噪音
      const list: any = await api.get('/api/upload/list', false)
      const rawItems = Array.isArray(list) ? list : (list?.data ?? [])
      const items = normalizeTerminalItems(rawItems).slice(0, limit)
      return {
        items,
        total: items.length,
        high_count: items.length,
      }
    } catch {
      // 回退到防御域端点：用于读取标准化 total/high_count
      const res: any = await api.get(`/api/v1/defense/terminal-evidence?limit=${limit}`)
      const payload = res?.data ?? res
      const items = normalizeTerminalItems(Array.isArray(payload?.items) ? payload.items : [])
      return {
        items,
        total: Number(payload?.total ?? items.length),
        high_count: Number(payload?.high_count ?? items.length),
      }
    }
  },
  
  async testHFishConnection(): Promise<{ reachable: boolean; host_port?: string }> {
    return this.testHFish()
  },
}
