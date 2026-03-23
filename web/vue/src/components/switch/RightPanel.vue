<script setup lang="ts">
import { ref } from 'vue'
import DevicePanel from './DevicePanel.vue'
import AiChatPanel from './AiChatPanel.vue'

const aiInputRef = ref<InstanceType<typeof AiChatPanel> | null>(null)

function handleSendToTerminal(command: string) {
  // 通过 emit 通知父组件或直接通过事件传递命令
  window.dispatchEvent(new CustomEvent('send-to-terminal', { detail: { command } }))
}

defineExpose({
  sendCommandToTerminal: (command: string) => {
    window.dispatchEvent(new CustomEvent('send-to-terminal', { detail: { command } }))
  }
})
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- 上部：设备列表 (固定高度) -->
    <div class="h-[220px] shrink-0 border-b">
      <DevicePanel />
    </div>

    <!-- 下部：AI 对话 (flex-1 填充剩余空间) -->
    <div class="flex-1 min-h-0">
      <AiChatPanel ref="aiInputRef" @send-to-terminal="handleSendToTerminal" />
    </div>
  </div>
</template>
