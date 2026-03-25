<script setup lang="ts">
import { ref } from 'vue'
import DevicePanel from './DevicePanel.vue'
import AiChatPanel from './AiChatPanel.vue'
import { useSwitchWorkbenchStore } from '@/stores/switchWorkbench'

const aiInputRef = ref<InstanceType<typeof AiChatPanel> | null>(null)
const store = useSwitchWorkbenchStore()

function handleSendToTerminal(command: string) {
  store.setPendingTerminalCommand(command)
}

defineExpose({
  sendCommandToTerminal: (command: string) => {
    store.setPendingTerminalCommand(command)
  }
})
</script>

<template>
  <div class="flex flex-col h-full">
    <div class="h-[220px] shrink-0 border-b">
      <DevicePanel />
    </div>

    <div class="flex-1 min-h-0">
      <AiChatPanel ref="aiInputRef" @send-to-terminal="handleSendToTerminal" />
    </div>
  </div>
</template>
