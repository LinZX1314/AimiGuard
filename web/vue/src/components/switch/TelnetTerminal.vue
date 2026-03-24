<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'
import { useSwitchWorkbenchStore } from '@/stores/switchWorkbench'
import { switchWorkbenchApi } from '@/api/switchWorkbench'
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

onMounted(async () => {
  await nextTick()
  initTerminal()

  window.addEventListener('send-to-terminal', handleSendToTerminal as EventListener)
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('send-to-terminal', handleSendToTerminal as EventListener)
  window.removeEventListener('resize', handleResize)
  disconnect()
  terminal?.dispose()
})

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
        executeCommand(commandBuffer.trim())
      }
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

function handleSendToTerminal(event: CustomEvent<{ command: string }>) {
  const { command } = event.detail
  if (store.connectionStatus === 'connected') {
    terminal?.write(`\r\n`)
    executeCommand(command)
  }
}

async function executeCommand(command: string) {
  if (!currentDevice || store.connectionStatus !== 'connected') return

  terminal?.writeln('')
  emit('command-sent', command)

  try {
    const result = await switchWorkbenchApi.runCommand({
      device_id: currentDevice.id,
      command,
      source: 'manual',
    })

    if (result.output) {
      terminal?.writeln(result.output)
      store.appendTerminalMessage({
        type: 'received',
        content: result.output,
      })
    }

    if (result.analysis) {
      terminal?.writeln(`\x1b[36m[AI] ${result.analysis}\x1b[0m`)
    }
  } catch (e: any) {
    terminal?.writeln(`\x1b[31m[错误] ${e.message || '命令执行失败'}\x1b[0m`)
    store.appendTerminalMessage({
      type: 'system',
      content: `错误: ${e.message || '命令执行失败'}`,
    })
  }

  terminal?.write('\r\n> ')
}

async function connect(device: SwitchWorkbenchDevice) {
  currentDevice = device
  store.setConnectionStatus('connecting')

  terminal?.writeln(`\r\n\x1b[33m[连接中] ${device.name} (${device.host}:${device.port})...\x1b[0m`)

  try {
    const result = await switchWorkbenchApi.runCommand({
      device_id: device.id,
      command: 'display version',
      source: 'manual',
    })

    if (result.status === 'failed') {
      store.setConnectionStatus('disconnected')
      terminal?.writeln(`\r\n\x1b[31m[连接失败] ${result.output || '无法连接到设备'}\x1b[0m`)
      terminal?.write('\r\n> ')
      store.appendTerminalMessage({
        type: 'system',
        content: `连接失败: ${result.output || '无法连接到设备'}`,
      })
      return
    }

    store.setConnectionStatus('connected')
    terminal?.writeln('\x1b[32m[已连接]\x1b[0m')
    terminal?.writeln('')

    if (result.output) {
      terminal?.writeln(result.output)
    }

    terminal?.write('\r\n> ')

    store.appendTerminalMessage({
      type: 'system',
      content: `已连接到 ${device.name}`,
    })
  } catch (e: any) {
    store.setConnectionStatus('disconnected')
    terminal?.writeln(`\r\n\x1b[31m[连接失败] ${e.message || '无法连接到设备'}\x1b[0m`)
    terminal?.write('\r\n> ')

    store.appendTerminalMessage({
      type: 'system',
      content: `连接失败: ${e.message || '无法连接到设备'}`,
    })
  }
}

function disconnect() {
  store.setConnectionStatus('disconnected')
  currentDevice = null
  terminal?.writeln('\r\n\x1b[33m[已断开连接]\x1b[0m')
}

function sendCommand(command: string) {
  if (store.connectionStatus === 'connected') {
    terminal?.write(`\r\n`)
    executeCommand(command)
  }
}

function clear() {
  terminal?.clear()
  terminal?.writeln('\x1b[36m=== 终端已清除 ===\x1b[0m')
  terminal?.write('\r\n> ')
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
