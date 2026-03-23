<script setup lang="ts">
import { useSwitchWorkbenchStore } from '@/stores/switchWorkbench'
import DeviceItem from './DeviceItem.vue'

const emit = defineEmits<{
  (e: 'edit', device: any): void
}>()

const store = useSwitchWorkbenchStore()

function handleSelect(id: number) {
  store.selectDevice(id)
}

function handleEdit(device: any) {
  emit('edit', device)
}
</script>

<template>
  <div class="p-2 space-y-1">
    <div v-if="store.devices.length === 0" class="text-center py-8 text-sm text-muted-foreground">
      暂无设备，请点击"添加设备"添加
    </div>
    <DeviceItem
      v-for="device in store.devices"
      :key="device.id"
      :device="device"
      :selected="device.id === store.selectedDeviceId"
      @select="handleSelect"
      @edit="handleEdit"
    />
  </div>
</template>
