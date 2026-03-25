import { io, type Socket } from 'socket.io-client'
import { api, getToken } from './index'

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

export interface SwitchWorkbenchTerminalEventMap {
  connected: (payload: { status: string }) => void
  joined: (payload: { session_id: string }) => void
  terminal_connected: (payload: { device: { id: number; name: string; host: string; port: number } }) => void
  terminal_output: (payload: { output: string }) => void
  terminal_error: (payload: { message: string }) => void
  terminal_disconnected: (payload: { message: string }) => void
  connect_error: (error: Error) => void
  disconnect: (reason: string) => void
}

export interface SwitchWorkbenchTerminalClient {
  connect(): void
  disconnect(): void
  isConnected(): boolean
  join(sessionId?: string): void
  leave(sessionId?: string): void
  connectDevice(device: SwitchWorkbenchDevice, sessionId?: string): void
  sendCommand(command: string, sessionId?: string): void
  disconnectDevice(sessionId?: string, graceful?: boolean): void
  on<K extends keyof SwitchWorkbenchTerminalEventMap>(event: K, handler: SwitchWorkbenchTerminalEventMap[K]): void
  off<K extends keyof SwitchWorkbenchTerminalEventMap>(event: K, handler?: SwitchWorkbenchTerminalEventMap[K]): void
}

function buildTerminalClient(): SwitchWorkbenchTerminalClient {
  const socket: Socket = io('/ws/switch-workbench/telnet', {
    path: '/socket.io',
    transports: ['websocket', 'polling'],
    autoConnect: false,
    reconnection: false,
    auth: { token: getToken() || '' },
    extraHeaders: getToken() ? { Authorization: `Bearer ${getToken()}` } : undefined,
  })

  return {
    connect() {
      const token = getToken() || ''
      socket.auth = { token }
      ;((socket.io.opts as any).extraHeaders) = token ? { Authorization: `Bearer ${token}` } : undefined
      if (!socket.connected) {
        socket.connect()
      }
    },
    disconnect() {
      socket.disconnect()
    },
    isConnected() {
      return socket.connected
    },
    join(sessionId) {
      socket.emit('join', { session_id: sessionId })
    },
    leave(sessionId) {
      socket.emit('leave', { session_id: sessionId })
    },
    connectDevice(device, sessionId) {
      socket.emit('connect_device', {
        session_id: sessionId,
        device: { id: device.id },
      })
    },
    sendCommand(command, sessionId) {
      socket.emit('send_command', { session_id: sessionId, command })
    },
    disconnectDevice(sessionId, graceful = true) {
      socket.emit('disconnect_device', { session_id: sessionId, graceful })
    },
    on(event, handler) {
      ;(socket as any).on(event, handler)
    },
    off(event, handler) {
      if (handler) {
        ;(socket as any).off(event, handler)
      } else {
        ;(socket as any).off(event)
      }
    },
  }
}

export const switchWorkbenchTerminal = buildTerminalClient()

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
