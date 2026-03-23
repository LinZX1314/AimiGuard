<script setup lang="ts">
import { computed } from 'vue'
import { MoreHorizontal, Pencil, Trash2 } from 'lucide-vue-next'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import type { SwitchWorkbenchDevice } from '@/api/switchWorkbench'

const props = defineProps<{
  device: SwitchWorkbenchDevice
  selected: boolean
}>()

const emit = defineEmits<{
  (e: 'select', id: number): void
  (e: 'edit', device: SwitchWorkbenchDevice): void
}>()

const statusDot = computed(() => {
  return props.device.online ? 'bg-green-500' : 'bg-gray-400'
})

const statusText = computed(() => {
  return props.device.online ? '在线' : '离线'
})
</script>

<template>
  <div
    class="flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer transition-colors"
    :class="selected ? 'bg-primary/10 border border-primary/30' : 'hover:bg-muted/50'"
    @click="emit('select', device.id)"
  >
    <div class="flex items-center gap-2 min-w-0">
      <div :class="['w-2 h-2 rounded-full shrink-0', statusDot]"></div>
      <div class="min-w-0">
        <div class="text-sm font-medium truncate">{{ device.name }}</div>
        <div class="text-xs text-muted-foreground truncate">{{ device.host }}:{{ device.port }}</div>
      </div>
    </div>

    <div class="flex items-center gap-2 shrink-0">
      <span class="text-xs text-muted-foreground">{{ statusText }}</span>

      <DropdownMenu>
        <DropdownMenuTrigger as-child>
          <button
            class="p-1 rounded hover:bg-muted"
            @click.stop
          >
            <MoreHorizontal :size="14" class="text-muted-foreground" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem @click="emit('edit', device)">
            <Pencil :size="14" class="mr-2" />
            编辑
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  </div>
</template>
