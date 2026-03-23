<script setup lang="ts">
import type { WorkflowRunRecord } from '@/api/workflow'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import WorkflowRunDetailContent from './WorkflowRunDetailContent.vue'

defineProps<{
  open: boolean
  run: WorkflowRunRecord | null
}>()

const emit = defineEmits<{
  'update:open': [open: boolean]
}>()
</script>

<template>
  <Sheet :open="open" @update:open="(value) => emit('update:open', value)">
    <SheetContent side="right" class="w-full overflow-y-auto sm:max-w-2xl">
      <SheetHeader>
        <SheetTitle>运行详情</SheetTitle>
        <SheetDescription>查看工作流运行的触发参数与逐步执行结果。</SheetDescription>
      </SheetHeader>
      <div class="mt-6">
        <WorkflowRunDetailContent :run="run" />
      </div>
    </SheetContent>
  </Sheet>
</template>
