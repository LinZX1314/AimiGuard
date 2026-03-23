<script setup lang="ts">
import { ref } from 'vue'
import { Server, Plus } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import DeviceList from './DeviceList.vue'
import DeviceDialog from './DeviceDialog.vue'
import { useSwitchWorkbenchStore } from '@/stores/switchWorkbench'

const store = useSwitchWorkbenchStore()
const showDialog = ref(false)
const editingDevice = ref<any>(null)

function handleAddDevice() {
  editingDevice.value = null
  showDialog.value = true
}

function handleEditDevice(device: any) {
  editingDevice.value = device
  showDialog.value = true
}

function handleDialogClose() {
  showDialog.value = false
  editingDevice.value = null
}

function handleDeviceSaved() {
  showDialog.value = false
  editingDevice.value = null
}
</script>

<template>
  <div class="flex flex-col h-full bg-card">
    <!-- 头部 -->
    <div class="shrink-0 flex items-center justify-between px-4 py-3 border-b">
      <div class="flex items-center gap-2">
        <Server :size="16" class="text-primary" />
        <span class="font-medium text-sm">设备列表</span>
        <span class="text-xs text-muted-foreground">({{ store.devices.length }})</span>
      </div>
      <Button size="sm" variant="outline" @click="handleAddDevice">
        <Plus :size="14" class="mr-1" />
        添加设备
      </Button>
    </div>

    <!-- 设备列表 -->
    <div class="flex-1 min-h-0 overflow-y-auto">
      <DeviceList @edit="handleEditDevice" />
    </div>

    <!-- 添加/编辑设备弹窗 -->
    <DeviceDialog
      v-if="showDialog"
      :device="editingDevice"
      @close="handleDialogClose"
      @saved="handleDeviceSaved"
    />
  </div>
</template>
