<script setup lang="ts">
import { computed } from 'vue'
import type { WorkflowTemplate } from '@/api/workflow'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'

const props = defineProps<{
  open: boolean
  loading?: boolean
  templates: WorkflowTemplate[]
}>()

const emit = defineEmits<{
  'update:open': [open: boolean]
  instantiate: [templateId: string]
}>()

function countNodes(template: WorkflowTemplate) {
  return template.definition?.nodes?.length ?? 0
}

function countEdges(template: WorkflowTemplate) {
  return template.definition?.edges?.length ?? 0
}

const sortedTemplates = computed(() => [...props.templates])
</script>

<template>
  <Dialog :open="open" @update:open="(value) => emit('update:open', value)">
    <DialogContent class="max-h-[85vh] max-w-4xl overflow-hidden p-0">
      <div class="flex h-full max-h-[85vh] flex-col overflow-hidden">
        <DialogHeader class="border-b border-border/60 px-5 py-4">
          <DialogTitle>模板中心</DialogTitle>
          <DialogDescription>直接选择现成流程，创建后再按需微调。</DialogDescription>
        </DialogHeader>
        <div class="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          <div v-if="loading" class="rounded-xl border border-dashed border-border/60 p-6 text-sm text-muted-foreground">
            正在加载模板...
          </div>
          <div v-else-if="!sortedTemplates.length" class="rounded-xl border border-dashed border-border/60 p-6 text-sm text-muted-foreground">
            暂无可用模板。
          </div>
          <div v-else class="grid gap-3 lg:grid-cols-2">
            <Card v-for="template in sortedTemplates" :key="template.id" class="border-border/60 bg-card/80">
              <CardHeader class="space-y-3 pb-4">
                <div class="flex flex-wrap items-center gap-2">
                  <CardTitle class="text-base">{{ template.name }}</CardTitle>
                  <Badge variant="secondary">{{ template.trigger_type }}</Badge>
                </div>
                <CardDescription>{{ template.description }}</CardDescription>
              </CardHeader>
              <CardContent class="space-y-3">
                <div class="flex flex-wrap gap-2">
                  <Badge v-for="tag in template.tags" :key="tag" variant="outline">{{ tag }}</Badge>
                </div>
                <div class="text-xs text-muted-foreground">{{ countNodes(template) }} 个节点 · {{ countEdges(template) }} 条连线</div>
                <Button type="button" size="sm" class="w-full cursor-pointer" @click="emit('instantiate', template.id)">
                  使用模板
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </DialogContent>
  </Dialog>
</template>
