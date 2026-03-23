<script setup lang="ts">
import { ref, watch } from 'vue'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'

const props = defineProps<{
  open: boolean
  running?: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  confirm: [payload: Record<string, unknown>]
}>()

const jsonText = ref('{\n  "source": "ui"\n}')
const parseError = ref('')

watch(() => props.open, (open) => {
  if (open) parseError.value = ''
})

function handleConfirm() {
  try {
    const payload = jsonText.value.trim() ? JSON.parse(jsonText.value) : {}
    parseError.value = ''
    emit('confirm', payload)
  } catch (error) {
    parseError.value = error instanceof Error ? error.message : 'JSON 解析失败'
  }
}
</script>

<template>
  <Dialog :open="props.open" @update:open="(value) => emit('update:open', value)">
    <DialogContent>
      <DialogHeader>
        <DialogTitle>手动运行工作流</DialogTitle>
        <DialogDescription>填写本次触发的 JSON 参数，系统会作为 trigger payload 注入工作流上下文。</DialogDescription>
      </DialogHeader>

      <div class="space-y-2">
        <Label for="workflow-run-json">运行参数(JSON)</Label>
        <Textarea id="workflow-run-json" v-model="jsonText" class="min-h-40 font-mono text-xs" />
        <p v-if="parseError" class="text-sm text-destructive">{{ parseError }}</p>
      </div>

      <DialogFooter>
        <Button variant="outline" class="cursor-pointer" @click="emit('update:open', false)">取消</Button>
        <Button class="cursor-pointer" :disabled="props.running" @click="handleConfirm">
          {{ props.running ? '运行中...' : '开始运行' }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
