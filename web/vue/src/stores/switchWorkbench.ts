import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { SwitchWorkbenchDevice, SwitchWorkbenchAiSuggestion } from '@/api/switchWorkbench'

export const HUAWEI_COMMANDS = [
  { cmd: 'display version', desc: '查看设备版本信息' },
  { cmd: 'display interface brief', desc: '查看端口状态摘要' },
  { cmd: 'display vlan', desc: '查看VLAN配置' },
  { cmd: 'display mac-address', desc: '查看MAC地址表' },
  { cmd: 'display arp', desc: '查看ARP表' },
]

export interface AiMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  commands?: string[]
  timestamp: number
}

export interface TerminalMessage {
  id: string
  type: 'sent' | 'received' | 'system'
  content: string
  timestamp: number
}

export const useSwitchWorkbenchStore = defineStore('switchWorkbench', () => {
  // State
  const devices = ref<SwitchWorkbenchDevice[]>([])
  const selectedDeviceId = ref<number | null>(null)
  const isConnected = ref(false)
  const connectionStatus = ref<'disconnected' | 'connecting' | 'connected'>('disconnected')
  const aiMessages = ref<AiMessage[]>([])
  const terminalMessages = ref<TerminalMessage[]>([])

  // Getters
  const selectedDevice = computed(() =>
    devices.value.find(d => d.id === selectedDeviceId.value) || null
  )

  // AI 命令匹配（简单关键字匹配）
  function matchCommands(userInput: string): string[] {
    const input = userInput.toLowerCase()
    const matched: string[] = []
    for (const item of HUAWEI_COMMANDS) {
      if (input.includes(item.desc.slice(2)) || input.includes(item.cmd.split(' ')[1])) {
        matched.push(item.cmd)
      }
    }
    return matched.length > 0 ? matched : ['display version']
  }

  // Actions
  function setDevices(newDevices: SwitchWorkbenchDevice[]) {
    devices.value = newDevices
  }

  function selectDevice(id: number | null) {
    selectedDeviceId.value = id
  }

  function setConnectionStatus(status: 'disconnected' | 'connecting' | 'connected') {
    connectionStatus.value = status
    isConnected.value = status === 'connected'
  }

  function appendTerminalMessage(msg: Omit<TerminalMessage, 'id' | 'timestamp'>) {
    terminalMessages.value.push({
      ...msg,
      id: `tm-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      timestamp: Date.now(),
    })
  }

  function appendAiMessage(msg: Omit<AiMessage, 'id' | 'timestamp'>) {
    aiMessages.value.push({
      ...msg,
      id: `am-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      timestamp: Date.now(),
    })
  }

  function clearTerminal() {
    terminalMessages.value = []
  }

  function clearAiMessages() {
    aiMessages.value = []
  }

  function updateDeviceStatus(deviceId: number, status: 'online' | 'offline') {
    const device = devices.value.find(d => d.id === deviceId)
    if (device) {
      device.online = status === 'online'
      device.status = status
    }
  }

  return {
    devices,
    selectedDeviceId,
    isConnected,
    connectionStatus,
    aiMessages,
    terminalMessages,
    selectedDevice,
    HUAWEI_COMMANDS,
    matchCommands,
    setDevices,
    selectDevice,
    setConnectionStatus,
    appendTerminalMessage,
    appendAiMessage,
    clearTerminal,
    clearAiMessages,
    updateDeviceStatus,
  }
})
