<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { Terminal, Plug, PlugZap, Trash2 } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { useSwitchWorkbenchStore } from '@/stores/switchWorkbench'
import TelnetTerminal from './TelnetTerminal.vue'

const store = useSwitchWorkbenchStore()

const terminalRef = ref<InstanceType<typeof TelnetTerminal> | null>(null)

const statusColor = computed(() => {
  switch (store.connectionStatus) {
    case 'connected':
      return 'bg-green-500'
    case 'connecting':
      return 'bg-yellow-500 animate-pulse'
    default:
      return 'bg-gray-400'
  }
})

const statusText = computed(() => {
  switch (store.connectionStatus) {
    case 'connected':
      return '已连接'
    case 'connecting':
      return '连接中...'
    default:
      return '未连接'
  }
})

function handleConnect() {
  if (store.selectedDevice) {
    store.setConnectionStatus('connecting')
    terminalRef.value?.connect(store.selectedDevice)
  }
}

function handleDisconnect() {
  terminalRef.value?.disconnect()
  store.setConnectionStatus('disconnected')
}

function handleClear() {
  store.clearTerminal()
  terminalRef.value?.clear()
}

function handleCommand(command: string) {
  // Commands from terminal are handled directly in TelnetTerminal
  // This is used for logging/analytics if needed
  console.debug('Command sent:', command)
}
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- 顶部栏 -->
    <div class="shrink-0 flex items-center justify-between px-4 py-3 border-b bg-card">
      <div class="flex items-center gap-2">
        <Terminal :size="18" class="text-primary" />
        <span class="font-medium text-sm">终端</span>
        <div class="flex items-center gap-1.5 ml-3">
          <div :class="['w-2 h-2 rounded-full', statusColor]"></div>
          <span class="text-xs text-muted-foreground">{{ statusText }}</span>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <Button
          v-if="store.connectionStatus === 'disconnected'"
          size="sm"
          variant="default"
          :disabled="!store.selectedDevice"
          @click="handleConnect"
        >
          <Plug :size="14" class="mr-1" />
          连接
        </Button>
        <Button
          v-else-if="store.connectionStatus === 'connected'"
          size="sm"
          variant="destructive"
          @click="handleDisconnect"
        >
          <PlugZap :size="14" class="mr-1" />
          断开
        </Button>
        <Button
          size="sm"
          variant="outline"
          @click="handleClear"
        >
          <Trash2 :size="14" class="mr-1" />
          清除
        </Button>
      </div>
    </div>

    <!-- 终端区域 -->
    <div class="flex-1 min-h-0 bg-[#1E1E1E]">
      <TelnetTerminal ref="terminalRef" @command-sent="handleCommand" />
    </div>
  </div>
</template>
