<script setup lang="ts">
import { onMounted } from 'vue'
import { useSwitchWorkbenchStore } from '@/stores/switchWorkbench'
import { switchWorkbenchApi } from '@/api/switchWorkbench'
import LeftPanel from '@/components/switch/LeftPanel.vue'
import RightPanel from '@/components/switch/RightPanel.vue'

const store = useSwitchWorkbenchStore()

onMounted(async () => {
  try {
    const devices = await switchWorkbenchApi.devices()
    store.setDevices(devices)
  } catch (e) {
    console.error('Failed to load devices:', e)
  }
})
</script>

<template>
  <div class="flex h-full">
    <!-- 左侧：终端，占 45% -->
    <div class="w-[45%] border-r flex flex-col">
      <LeftPanel />
    </div>

    <!-- 右侧：设备列表 + AI 对话，占 55% -->
    <div class="w-[55%] flex flex-col">
      <RightPanel />
    </div>
  </div>
</template>
