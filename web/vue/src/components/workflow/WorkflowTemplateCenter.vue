<script setup lang="ts">
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
</script>

<template>
  <Dialog :open="open" @update:open="(value) => emit('update:open', value)">
    <DialogContent class="max-h-[85vh] max-w-5xl overflow-hidden p-0">
      <div class="flex h-full max-h-[85vh] flex-col overflow-hidden">
        <DialogHeader class="border-b border-border/60 px-6 py-4">
          <DialogTitle>模板中心</DialogTitle>
          <DialogDescription>从内置模板快速创建工作流草稿，后续可继续在画布中编辑。</DialogDescription>
        </DialogHeader>
        <div class="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          <div v-if="loading" class="rounded-xl border border-dashed border-border/60 p-8 text-sm text-muted-foreground">
            正在加载模板...
          </div>
          <div v-else-if="!templates.length" class="rounded-xl border border-dashed border-border/60 p-8 text-sm text-muted-foreground">
            暂无可用模板。
          </div>
          <div v-else class="grid gap-4 lg:grid-cols-2">
            <Card v-for="template in templates" :key="template.id" class="border-border/60 bg-card/80">
              <CardHeader>
                <div class="flex flex-wrap items-center gap-2">
                  <CardTitle class="text-base">{{ template.name }}</CardTitle>
                  <Badge variant="secondary">{{ template.category }}</Badge>
                  <Badge variant="outline">{{ template.trigger_type }}</Badge>
                </div>
                <CardDescription>{{ template.description }}</CardDescription>
              </CardHeader>
              <CardContent class="space-y-4">
                <div class="flex flex-wrap gap-2">
                  <Badge v-for="tag in template.tags" :key="tag" variant="outline">{{ tag }}</Badge>
                </div>
                <Button type="button" class="min-h-11 w-full cursor-pointer" @click="emit('instantiate', template.id)">
                  使用此模板
                </Button>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </DialogContent>
  </Dialog>
</template>
