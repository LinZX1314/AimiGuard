<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'
import { useSwitchWorkbenchStore } from '@/stores/switchWorkbench'
import { switchWorkbenchTerminal } from '@/api/switchWorkbench'
import type { SwitchWorkbenchDevice } from '@/api/switchWorkbench'

const emit = defineEmits<{
  (e: 'command-sent', command: string): void
}>()

const store = useSwitchWorkbenchStore()
const terminalContainer = ref<HTMLDivElement | null>(null)

let terminal: Terminal | null = null
let fitAddon: FitAddon | null = null
let currentDevice: SwitchWorkbenchDevice | null = null
let commandBuffer = ''
let socketBound = false
let connectingDevice: SwitchWorkbenchDevice | null = null

const terminalOptions = {
  theme: {
    background: '#1E1E1E',
    foreground: '#CCCCCC',
    cursor: '#CCCCCC',
  },
  fontSize: 14,
  fontFamily: 'Menlo, Monaco, "Courier New", monospace',
  cursorBlink: true,
  scrollback: 10000,
}

const handleSocketConnected = () => {
  switchWorkbenchTerminal.join(store.terminalSession.sessionId)
}

const handleTerminalConnected = (_payload: { device: { id: number; name: string; host: string; port: number } }) => {
  currentDevice = connectingDevice ?? currentDevice
  connectingDevice = null
  store.setConnectionStatus('connected')
  terminal?.writeln('\x1b[32m[已连接]\x1b[0m')
  terminal?.writeln('')
  store.appendTerminalMessage({
    type: 'system',
    content: `已连接到 ${currentDevice?.name || '交换机'}`,
  })

  const pendingCommand = store.terminalSession.pendingCommand.trim()
  if (pendingCommand) {
    store.setPendingTerminalCommand('')
    sendCommand(pendingCommand)
  }
}

const handleTerminalOutput = (payload: { output: string }) => {
  if (!payload.output) return
  terminal?.write(payload.output)
  store.appendTerminalMessage({
    type: 'received',
    content: payload.output,
  })
}

const handleTerminalError = (payload: { message: string }) => {
  const message = payload.message || '终端执行失败'
  terminal?.writeln(`\r\n\x1b[31m[错误] ${message}\x1b[0m`)
  store.appendTerminalMessage({
    type: 'system',
    content: `错误: ${message}`,
  })
  if (store.connectionStatus === 'connecting') {
    connectingDevice = null
    store.setConnectionStatus('disconnected')
  }
}

const handleSocketConnectError = (error: Error) => {
  const message = error?.message || 'Socket 连接失败'
  terminal?.writeln(`\r\n\x1b[31m[错误] ${message}\x1b[0m`)
  store.appendTerminalMessage({
    type: 'system',
    content: `错误: ${message}`,
  })
  connectingDevice = null
  store.setConnectionStatus('disconnected')
}

const handleSocketDisconnected = (reason: string) => {
  if (store.connectionStatus === 'disconnected') return
  handleTerminalDisconnected({ message: `Socket 已断开: ${reason}` })
}

const handleTerminalDisconnected = (payload: { message: string }) => {
  store.setConnectionStatus('disconnected')
  currentDevice = null
  commandBuffer = ''
  const message = payload.message || '已断开连接'
  terminal?.writeln(`\r\n\x1b[33m[${message}]\x1b[0m`)
  store.appendTerminalMessage({
    type: 'system',
    content: message,
  })
}

function bindSocketEvents() {
  if (socketBound) return
  socketBound = true
  switchWorkbenchTerminal.on('connected', handleSocketConnected)
  switchWorkbenchTerminal.on('terminal_connected', handleTerminalConnected)
  switchWorkbenchTerminal.on('terminal_output', handleTerminalOutput)
  switchWorkbenchTerminal.on('terminal_error', handleTerminalError)
  switchWorkbenchTerminal.on('terminal_disconnected', handleTerminalDisconnected)
  switchWorkbenchTerminal.on('connect_error', handleSocketConnectError)
  switchWorkbenchTerminal.on('disconnect', handleSocketDisconnected)
}

function unbindSocketEvents() {
  if (!socketBound) return
  socketBound = false
  switchWorkbenchTerminal.off('connected', handleSocketConnected)
  switchWorkbenchTerminal.off('terminal_connected', handleTerminalConnected)
  switchWorkbenchTerminal.off('terminal_output', handleTerminalOutput)
  switchWorkbenchTerminal.off('terminal_error', handleTerminalError)
  switchWorkbenchTerminal.off('terminal_disconnected', handleTerminalDisconnected)
  switchWorkbenchTerminal.off('connect_error', handleSocketConnectError)
  switchWorkbenchTerminal.off('disconnect', handleSocketDisconnected)
}

onMounted(async () => {
  await nextTick()
  initTerminal()
  bindSocketEvents()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  disconnect(false)
  unbindSocketEvents()
  terminal?.dispose()
})

watch(
  () => store.terminalSession.pendingCommand,
  (command) => {
    if (!command) return
    if (store.connectionStatus === 'connected') {
      store.setPendingTerminalCommand('')
      sendCommand(command)
      return
    }
    if (store.connectionStatus === 'disconnected' && store.selectedDevice) {
      connect(store.selectedDevice)
    }
  }
)

function initTerminal() {
  if (!terminalContainer.value) return

  terminal = new Terminal(terminalOptions)
  fitAddon = new FitAddon()
  terminal.loadAddon(fitAddon)
  terminal.open(terminalContainer.value)

  try {
    fitAddon.fit()
  } catch (e) {
    console.warn('Failed to fit terminal:', e)
  }

  terminal.writeln('\x1b[36m=== 交换机工作台终端 ===\x1b[0m')
  terminal.writeln('\x1b[33m提示: 请先选择设备并点击"连接"\x1b[0m')
  terminal.writeln('')

  terminal.onData((data: string) => {
    if (store.connectionStatus !== 'connected') return

    if (data === '\r') {
      if (commandBuffer.trim()) {
        sendCommand(commandBuffer.trim())
      } else {
        switchWorkbenchTerminal.sendCommand('\r', store.terminalSession.sessionId)
        terminal?.write('\r\n')
      }
      commandBuffer = ''
    } else if (data === '\u0003') {
      switchWorkbenchTerminal.sendCommand('\u0003', store.terminalSession.sessionId)
      terminal?.write('^C')
      commandBuffer = ''
    } else if (data === '\x7f') {
      if (commandBuffer.length > 0) {
        commandBuffer = commandBuffer.slice(0, -1)
        terminal?.write('\b \b')
      }
    } else {
      commandBuffer += data
      terminal?.write(data)
    }
  })
}

function handleResize() {
  if (fitAddon) {
    try {
      fitAddon.fit()
    } catch (e) {
      console.warn('Failed to fit terminal on resize:', e)
    }
  }
}

async function connect(device: SwitchWorkbenchDevice) {
  if (store.connectionStatus === 'connecting') return

  currentDevice = device
  commandBuffer = ''
  store.rotateTerminalSession()
  store.setConnectionStatus('connecting')

  terminal?.writeln(`\r\n\x1b[33m[连接中] ${device.name} (${device.host}:${device.port})...\x1b[0m`)

  switchWorkbenchTerminal.connect()
  switchWorkbenchTerminal.join(store.terminalSession.sessionId)
  switchWorkbenchTerminal.connectDevice(device, store.terminalSession.sessionId)
}

function disconnect(graceful = true) {
  if (store.connectionStatus !== 'disconnected') {
    switchWorkbenchTerminal.disconnectDevice(store.terminalSession.sessionId, graceful)
  }
  store.setConnectionStatus('disconnected')
  currentDevice = null
  commandBuffer = ''
}

function sendCommand(command: string) {
  const trimmed = command.trim()
  if (!trimmed || store.connectionStatus !== 'connected') return

  terminal?.write('\r\n')
  emit('command-sent', trimmed)
  store.setLastTerminalCommand(trimmed)
  store.appendTerminalMessage({
    type: 'sent',
    content: trimmed,
  })
  switchWorkbenchTerminal.sendCommand(`${trimmed}\r`, store.terminalSession.sessionId)
}

function clear() {
  terminal?.clear()
  terminal?.writeln('\x1b[36m=== 终端已清除 ===\x1b[0m')
  if (store.connectionStatus === 'connected') {
    terminal?.write('\r\n')
  }
}

defineExpose({
  connect,
  disconnect,
  sendCommand,
  clear,
})
</script>

<template>
  <div ref="terminalContainer" class="h-full w-full"></div>
</template>

<style scoped>
:deep(.xterm) {
  padding: 8px;
}

:deep(.xterm-viewport) {
  overflow-y: auto !important;
}
</style>
