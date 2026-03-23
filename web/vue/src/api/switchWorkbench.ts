import { api } from './index'

export interface SwitchWorkbenchDevice {
  id: number
  name: string
  host: string
  port: number
  protocol: 'telnet'
  vendor: string
  model: string
  group_id: string
  enabled: boolean
  online: boolean
  status: 'online' | 'degraded' | 'offline'
  acl_number: number
  readonly_only: boolean
  tags: string[]
  notes: string
  last_seen: string
}

export interface SwitchWorkbenchDeviceConfig {
  id: number
  name: string
  host: string
  port: number
  vendor: string
  model: string
  group_id: string
  password: string
  secret: string
  acl_number: number
  enabled: boolean
  readonly_only: boolean
  notes: string
  paging_disable: string
  tags: string[]
}

export interface SwitchWorkbenchScript {
  id: string
  title: string
  description: string
  scope: 'single' | 'batch'
  risk: '低风险' | '只读' | '谨慎'
  commands: string[]
}

export interface SwitchWorkbenchHistoryRecord {
  id: number
  device_name: string
  device_host: string
  command_text: string
  source: 'manual' | 'ai' | 'script'
  status: 'success' | 'pending' | 'failed'
  stdout: string
  summary: string
  created_at: string
  completed_at?: string | null
}

export interface SwitchWorkbenchAiSuggestion {
  id: string
  title: string
  command: string
  risk: '低风险' | '只读' | '谨慎'
  reason: string
  auto_runnable: boolean
}

export interface SwitchWorkbenchTestResult {
  reachable: boolean
  host: string
  port: number
  warning?: string
}

export interface SwitchWorkbenchCommandRunResult {
  run_id?: number
  device: {
    id: number
    name: string
    host: string
    port: number
  }
  command: string
  source: 'manual' | 'ai' | 'script'
  status: 'success' | 'failed'
  output: string
  analysis: string
  created_at: string
}

export interface SwitchWorkbenchBatchResult {
  script_id: string
  script_title: string
  summary: string
  items: SwitchWorkbenchCommandRunResult[]
}

export interface SwitchWorkbenchAiTurn {
  answer: string
  summary: string
  next_steps: string[]
  suggested_commands: SwitchWorkbenchAiSuggestion[]
}

export const switchWorkbenchApi = {
  devices(probe = true) {
    return api.get<SwitchWorkbenchDevice[]>(`/api/v1/switch-workbench/devices?probe=${probe ? 1 : 0}`)
  },

  deviceConfigs() {
    return api.get<SwitchWorkbenchDeviceConfig[]>('/api/v1/switch-workbench/devices/config')
  },

  saveDeviceConfigs(payload: { devices: Array<Omit<SwitchWorkbenchDeviceConfig, 'id'> | SwitchWorkbenchDeviceConfig> }) {
    return api.post<{ items: SwitchWorkbenchDeviceConfig[] }>('/api/v1/switch-workbench/devices/config', payload)
  },

  scripts() {
    return api.get<SwitchWorkbenchScript[]>('/api/v1/switch-workbench/scripts')
  },

  history(limit = 30) {
    return api.get<SwitchWorkbenchHistoryRecord[]>(`/api/v1/switch-workbench/history?limit=${limit}`)
  },

  testDevice(payload: { device_id?: number; host?: string; port?: number; password?: string }) {
    return api.post<SwitchWorkbenchTestResult>('/api/v1/switch-workbench/devices/test', payload)
  },

  generateCommands(payload: { device_id?: number; prompt: string }) {
    return api.post<{ summary: string; items: SwitchWorkbenchAiSuggestion[] }>('/api/v1/switch-workbench/ai/generate', payload)
  },

  analyzeTurn(payload: {
    device_id?: number
    prompt: string
    command_output?: string
    command?: string
    conversation?: Array<{ role: 'user' | 'assistant'; content: string }>
  }) {
    return api.post<SwitchWorkbenchAiTurn>('/api/v1/switch-workbench/ai/turn', payload)
  },

  runCommand(payload: { device_id?: number; command: string; source: 'manual' | 'ai' | 'script' }) {
    return api.post<SwitchWorkbenchCommandRunResult>('/api/v1/switch-workbench/commands/run', payload)
  },

  runScript(payload: { script_id: string; device_ids: number[] }) {
    return api.post<SwitchWorkbenchBatchResult>('/api/v1/switch-workbench/scripts/run', payload)
  },
}
